"""HTTP server exposing the Book Writer CLI functionality for the GUI."""
from __future__ import annotations

import json
import math
import mimetypes
import re
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse

from book_writer.cli import (
    _book_chapter_files,
    _book_directories,
    _outline_preview_text,
    _select_chapter_files,
)
from book_writer.cover import CoverSettings, parse_cover_command
from book_writer.gui import get_gui_html
from book_writer.metadata import (
    generate_book_genres,
    read_book_genres,
    write_book_meta,
)
from book_writer.outline import parse_outline_with_title
from book_writer.tts import TTSSettings
from book_writer.video import (
    ParagraphImageSettings,
    VideoSettings,
    parse_video_image_command,
)
from book_writer.writer import (
    LMStudioClient,
    compile_book,
    expand_book,
    generate_book_audio,
    generate_book_cover_asset,
    generate_book_videos,
    generate_chapter_cover_assets,
    generate_outline,
    write_book,
)


class ApiError(ValueError):
    """Raised when API input is invalid."""


WORDS_PER_PAGE = 300
WORD_PATTERN = re.compile(r"\b\w+\b")
SUMMARY_DIRNAME = "summaries"
SUMMARY_CHAPTER_DIRNAME = "chapters"
BOOK_SUMMARY_FILENAME = "book-summary.md"
SUMMARY_SOURCE_LIMIT = 4000
_SUMMARY_TASKS_LOCK = threading.Lock()
_SUMMARY_TASKS: set[str] = set()
_GENRE_TASKS_LOCK = threading.Lock()
_GENRE_TASKS: set[str] = set()


def _estimate_page_count(content: str) -> int:
    words = len(WORD_PATTERN.findall(content))
    if words == 0:
        return 0
    return math.ceil(words / WORDS_PER_PAGE)


def _sum_book_pages(book_dir: Path) -> int:
    total = 0
    for chapter_file in _book_chapter_files(book_dir):
        try:
            content = chapter_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        total += _estimate_page_count(content)
    return total


def _get_value(data: dict[str, Any], key: str, default: Any = None) -> Any:
    value = data.get(key, default)
    if value is None:
        return default
    return value


def _summary_dir(book_dir: Path) -> Path:
    return book_dir / SUMMARY_DIRNAME


def _book_summary_path(book_dir: Path) -> Path:
    return _summary_dir(book_dir) / BOOK_SUMMARY_FILENAME


def _chapter_summary_path(book_dir: Path, chapter_file: Path) -> Path:
    return _summary_dir(book_dir) / SUMMARY_CHAPTER_DIRNAME / f"{chapter_file.stem}.md"


def _normalize_summary_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _truncate_summary_source(text: str) -> str:
    if len(text) <= SUMMARY_SOURCE_LIMIT:
        return text
    return text[:SUMMARY_SOURCE_LIMIT].rstrip()


def _read_summary(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return ""


def _write_summary(path: Path, summary: str) -> None:
    if not summary:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(summary + "\n", encoding="utf-8")


def _read_book_title(book_dir: Path) -> str:
    book_md = book_dir / "book.md"
    if book_md.exists():
        try:
            for line in book_md.read_text(encoding="utf-8").splitlines():
                if line.startswith("# "):
                    return line[2:].strip() or book_dir.name
        except (OSError, UnicodeDecodeError):
            pass
    for chapter_file in _book_chapter_files(book_dir):
        try:
            content = chapter_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        title = _chapter_title_from_content(content, chapter_file.stem)
        if title:
            return title
    return book_dir.name


def _read_book_synopsis(book_dir: Path) -> str:
    synopsis_path = book_dir / "back-cover-synopsis.md"
    if synopsis_path.exists():
        return synopsis_path.read_text(encoding="utf-8").strip()
    return ""


def _select_book_summary_source(book_dir: Path, chapter_files: list[Path]) -> tuple[str, str]:
    synopsis = _read_book_synopsis(book_dir)
    if synopsis:
        return "Synopsis", synopsis
    book_md = book_dir / "book.md"
    if book_md.exists():
        try:
            return "Book content", book_md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            pass
    if chapter_files:
        try:
            return "Chapter content", chapter_files[0].read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            pass
    return "Notes", ""


def _build_book_summary_prompt(title: str, source_label: str, source_text: str) -> str:
    return (
        "Write a single-paragraph summary of the book below. "
        "Keep it concise (3-5 sentences). Return only the summary text.\n\n"
        f"Book title: {title}\n"
        f"{source_label}:\n{source_text}"
    )


def _build_chapter_summary_prompt(title: str, content: str) -> str:
    return (
        "Write a single-paragraph summary of the chapter below. "
        "Keep it concise (2-4 sentences). Return only the summary text.\n\n"
        f"Chapter title: {title}\n"
        f"{content}"
    )


def _summary_task_key(book_dir: Path, chapter_file: Path | None = None) -> str:
    if chapter_file is None:
        return f"book:{book_dir.resolve()}"
    return f"chapter:{book_dir.resolve()}:{chapter_file.resolve()}"


def _schedule_summary_task(task_key: str, task: Callable[[], str | None]) -> None:
    with _SUMMARY_TASKS_LOCK:
        if task_key in _SUMMARY_TASKS:
            return
        _SUMMARY_TASKS.add(task_key)

    def runner() -> None:
        try:
            task()
        finally:
            with _SUMMARY_TASKS_LOCK:
                _SUMMARY_TASKS.discard(task_key)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()


def _genre_task_key(book_dir: Path) -> str:
    return f"genre:{book_dir.resolve()}"


def _schedule_genre_task(task_key: str, task: Callable[[], None]) -> None:
    with _GENRE_TASKS_LOCK:
        if task_key in _GENRE_TASKS:
            return
        _GENRE_TASKS.add(task_key)

    def runner() -> None:
        try:
            task()
        finally:
            with _GENRE_TASKS_LOCK:
                _GENRE_TASKS.discard(task_key)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()


def _generate_book_summary(
    book_dir: Path, book_title: str, payload: dict[str, Any]
) -> str:
    summary_path = _book_summary_path(book_dir)
    summary = _read_summary(summary_path)
    if summary:
        return summary
    chapter_files = _book_chapter_files(book_dir)
    source_label, source_text = _select_book_summary_source(book_dir, chapter_files)
    source_text = _truncate_summary_source(source_text.strip())
    if not source_text:
        return ""
    try:
        client = _build_client(payload)
        prompt = _build_book_summary_prompt(book_title, source_label, source_text)
        summary = _normalize_summary_text(client.generate(prompt))
    except (HTTPError, URLError, OSError, ValueError):
        return ""
    if summary:
        _write_summary(summary_path, summary)
    return summary


def _generate_chapter_summary(
    book_dir: Path,
    chapter_file: Path,
    chapter_title: str,
    content: str,
    payload: dict[str, Any],
) -> str:
    summary_path = _chapter_summary_path(book_dir, chapter_file)
    summary = _read_summary(summary_path)
    if summary:
        return summary
    content = _truncate_summary_source(content.strip())
    if not content:
        return ""
    try:
        client = _build_client(payload)
        prompt = _build_chapter_summary_prompt(chapter_title, content)
        summary = _normalize_summary_text(client.generate(prompt))
    except (HTTPError, URLError, OSError, ValueError):
        return ""
    if summary:
        _write_summary(summary_path, summary)
    return summary


def _ensure_book_summary_async(
    book_dir: Path, book_title: str, payload: dict[str, Any]
) -> str:
    summary_path = _book_summary_path(book_dir)
    summary = _read_summary(summary_path)
    if summary:
        return summary
    task_key = _summary_task_key(book_dir)
    _schedule_summary_task(
        task_key, lambda: _generate_book_summary(book_dir, book_title, payload)
    )
    return ""


def _ensure_chapter_summary_async(
    book_dir: Path,
    chapter_file: Path,
    chapter_title: str,
    content: str,
    payload: dict[str, Any],
) -> str:
    summary_path = _chapter_summary_path(book_dir, chapter_file)
    summary = _read_summary(summary_path)
    if summary:
        return summary
    task_key = _summary_task_key(book_dir, chapter_file)
    _schedule_summary_task(
        task_key,
        lambda: _generate_chapter_summary(
            book_dir, chapter_file, chapter_title, content, payload
        ),
    )
    return ""


def _generate_book_genres_task(
    book_dir: Path, synopsis: str, payload: dict[str, Any]
) -> None:
    if not synopsis.strip():
        return
    try:
        client = _build_client(payload)
        genres = generate_book_genres(client, synopsis)
    except (HTTPError, URLError, OSError, ValueError):
        return
    if genres:
        write_book_meta(book_dir, genres)


def _ensure_book_genres_async(
    book_dir: Path, synopsis: str, payload: dict[str, Any]
) -> list[str]:
    genres = read_book_genres(book_dir)
    if genres:
        return genres
    if not synopsis.strip():
        return []
    task_key = _genre_task_key(book_dir)
    _schedule_genre_task(
        task_key, lambda: _generate_book_genres_task(book_dir, synopsis, payload)
    )
    return []


def _parse_tts_settings(payload: dict[str, Any]) -> TTSSettings:
    tts_payload = payload.get("tts_settings") or {}
    defaults = TTSSettings()
    return TTSSettings(
        enabled=bool(tts_payload.get("enabled", payload.get("tts", True))),
        voice=tts_payload.get("voice", defaults.voice),
        language=tts_payload.get("language", defaults.language),
        instruct=tts_payload.get("instruct", defaults.instruct),
        model_path=tts_payload.get("model_path", defaults.model_path),
        device_map=tts_payload.get("device_map", defaults.device_map),
        dtype=tts_payload.get("dtype", defaults.dtype),
        attn_implementation=tts_payload.get(
            "attn_implementation", defaults.attn_implementation
        ),
        rate=tts_payload.get("rate", defaults.rate),
        pitch=tts_payload.get("pitch", defaults.pitch),
        audio_dirname=tts_payload.get("audio_dirname", defaults.audio_dirname),
        overwrite_audio=bool(tts_payload.get("overwrite_audio", False)),
        book_only=bool(tts_payload.get("book_only", False)),
        keep_model_loaded=bool(
            tts_payload.get("keep_model_loaded", defaults.keep_model_loaded)
        ),
    )


def _parse_video_settings(payload: dict[str, Any]) -> VideoSettings:
    video_payload = payload.get("video_settings") or {}
    paragraph_payload = video_payload.get("paragraph_images") or {}
    default_image_settings = ParagraphImageSettings()

    def parse_int(value: Any, fallback: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    def parse_optional_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def parse_float(value: Any, fallback: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    return VideoSettings(
        enabled=bool(video_payload.get("enabled", payload.get("video", False))),
        background_video=Path(video_payload["background_video"])
        if video_payload.get("background_video")
        else None,
        video_dirname=video_payload.get("video_dirname", "video"),
        paragraph_images=ParagraphImageSettings(
            enabled=bool(paragraph_payload.get("enabled", False)),
            image_dirname=paragraph_payload.get(
                "image_dirname", default_image_settings.image_dirname
            ),
            negative_prompt=paragraph_payload.get("negative_prompt") or None,
            model_path=Path(paragraph_payload["model_path"])
            if paragraph_payload.get("model_path")
            else None,
            module_path=Path(paragraph_payload["module_path"])
            if paragraph_payload.get("module_path")
            else default_image_settings.module_path,
            steps=parse_int(
                paragraph_payload.get("steps", default_image_settings.steps),
                default_image_settings.steps,
            ),
            guidance_scale=parse_float(
                paragraph_payload.get(
                    "guidance_scale", default_image_settings.guidance_scale
                ),
                default_image_settings.guidance_scale,
            ),
            seed=parse_optional_int(paragraph_payload.get("seed")),
            width=parse_int(
                paragraph_payload.get("width", default_image_settings.width),
                default_image_settings.width,
            ),
            height=parse_int(
                paragraph_payload.get("height", default_image_settings.height),
                default_image_settings.height,
            ),
            overwrite=bool(paragraph_payload.get("overwrite", False)),
            command=parse_video_image_command(paragraph_payload.get("command")),
        ),
    )


def _parse_cover_settings(payload: dict[str, Any]) -> CoverSettings:
    cover_payload = payload.get("cover_settings") or {}
    default_module_path = CoverSettings().module_path

    def parse_int(value: Any, fallback: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    def parse_optional_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def parse_float(value: Any, fallback: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    output_name = cover_payload.get("output_name") or "cover.png"
    return CoverSettings(
        enabled=bool(cover_payload.get("enabled", payload.get("cover", False))),
        prompt=cover_payload.get("prompt") or None,
        negative_prompt=cover_payload.get("negative_prompt") or None,
        model_path=Path(cover_payload["model_path"])
        if cover_payload.get("model_path")
        else None,
        module_path=Path(cover_payload["module_path"])
        if cover_payload.get("module_path")
        else default_module_path,
        steps=parse_int(cover_payload.get("steps", 30), 30),
        guidance_scale=parse_float(cover_payload.get("guidance_scale", 7.5), 7.5),
        seed=parse_optional_int(cover_payload.get("seed")),
        width=parse_int(cover_payload.get("width", 768), 768),
        height=parse_int(cover_payload.get("height", 1024), 1024),
        output_name=output_name,
        overwrite=bool(cover_payload.get("overwrite", False)),
        command=parse_cover_command(cover_payload.get("command")),
    )


def _build_client(payload: dict[str, Any]) -> LMStudioClient:
    return LMStudioClient(
        base_url=payload.get("base_url", "http://localhost:1234"),
        model=payload.get("model", "local-model"),
        timeout=payload.get("timeout"),
        author=payload.get("author"),
    )


def _collect_outlines(outlines_dir: Path) -> list[dict[str, Any]]:
    if not outlines_dir.is_dir():
        return []
    outlines = []
    try:
        outline_paths = sorted(outlines_dir.iterdir())
    except OSError:
        return []
    for outline_path in outline_paths:
        if outline_path.suffix != ".md":
            continue
        try:
            title, items = parse_outline_with_title(outline_path)
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        preview = _outline_preview_text(title, items)
        outlines.append(
            {
                "path": str(outline_path),
                "title": title,
                "preview": preview,
                "item_count": len(items),
            }
        )
    return outlines


def _collect_named_files(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    try:
        paths = sorted(directory.iterdir())
    except OSError:
        return []
    return [path.stem for path in paths if path.suffix == ".md"]


def list_authors(payload: dict[str, Any]) -> dict[str, Any]:
    default_dir = Path(__file__).resolve().parents[1] / "authors"
    authors_dir = Path(payload.get("authors_dir", default_dir))
    return {"authors": _collect_named_files(authors_dir)}


def list_tones(payload: dict[str, Any]) -> dict[str, Any]:
    default_dir = Path(__file__).parent / "tones"
    tones_dir = Path(payload.get("tones_dir", default_dir))
    return {"tones": _collect_named_files(tones_dir)}


def _resolve_outline_path(
    outlines_dir: Path,
    outline_path_value: str | None,
    outline_name: str | None,
) -> Path:
    if outline_path_value:
        candidate = Path(outline_path_value)
    else:
        outlines_dir.mkdir(parents=True, exist_ok=True)
        name = outline_name or "outline.md"
        if not name.endswith(".md"):
            name = f"{name}.md"
        candidate = outlines_dir / name
    if not candidate.is_absolute():
        candidate = (outlines_dir / candidate).resolve()
    outlines_root = outlines_dir.resolve()
    if outlines_root not in candidate.parents and candidate != outlines_root:
        raise ApiError("Invalid outline path.")
    return candidate


def list_outlines(payload: dict[str, Any]) -> dict[str, Any]:
    outlines_dir = Path(payload.get("outlines_dir", "outlines"))
    return {"outlines": _collect_outlines(outlines_dir)}


def list_completed_outlines(payload: dict[str, Any]) -> dict[str, Any]:
    outlines_dir = Path(payload.get("completed_outlines_dir", "completed_outlines"))
    return {"outlines": _collect_outlines(outlines_dir)}


def generate_outline_api(payload: dict[str, Any]) -> dict[str, Any]:
    prompt = payload.get("prompt", "")
    if not str(prompt).strip():
        raise ApiError("prompt is required")
    outlines_dir = Path(payload.get("outlines_dir", "outlines"))
    outline_path = _resolve_outline_path(
        outlines_dir,
        payload.get("outline_path"),
        payload.get("outline_name"),
    )
    revision_prompts = payload.get("revision_prompts") or []
    if isinstance(revision_prompts, str):
        revision_prompts = [revision_prompts]
    client = _build_client(payload)
    outline_text = generate_outline(
        prompt=str(prompt),
        client=client,
        revision_prompts=[str(item) for item in revision_prompts if item is not None],
    )
    outline_path.write_text(outline_text + "\n", encoding="utf-8")
    title, items = parse_outline_with_title(outline_path)
    return {
        "outline_path": str(outline_path),
        "title": title,
        "content": outline_text,
        "item_count": len(items),
    }


def save_outline_api(payload: dict[str, Any]) -> dict[str, Any]:
    outline_path_value = payload.get("outline_path")
    if not outline_path_value:
        raise ApiError("outline_path is required")
    outlines_dir = Path(payload.get("outlines_dir", "outlines"))
    outlines_dir.mkdir(parents=True, exist_ok=True)
    outline_path = _resolve_outline_path(outlines_dir, outline_path_value, None)
    content = payload.get("content", "")
    if not str(content).strip():
        raise ApiError("content is required")
    outline_path.write_text(str(content).rstrip() + "\n", encoding="utf-8")
    title, items = parse_outline_with_title(outline_path)
    return {
        "outline_path": str(outline_path),
        "title": title,
        "content": str(content),
        "item_count": len(items),
    }


def list_books(payload: dict[str, Any]) -> dict[str, Any]:
    books_dir = Path(payload.get("books_dir", "books"))
    audio_dir = payload.get("tts_audio_dir", "audio")
    video_dir = payload.get("video_dir", "video")
    books = _book_directories(books_dir, audio_dir, video_dir)
    entries: list[dict[str, Any]] = []
    for book in books:
        synopsis = _read_book_synopsis(book.path)
        entries.append(
            {
                "path": str(book.path),
                "title": book.title,
                "has_text": book.has_text,
                "has_audio": book.has_audio,
                "has_video": book.has_video,
                "has_compilation": book.has_compilation,
                "has_cover": (book.path / "cover.png").exists(),
                "chapter_count": len(_book_chapter_files(book.path)),
                "page_count": _sum_book_pages(book.path),
                "summary": _ensure_book_summary_async(book.path, book.title, payload),
                "genres": _ensure_book_genres_async(book.path, synopsis, payload),
                "cover_url": (
                    _build_media_url(book.path, Path("cover.png"))
                    if (book.path / "cover.png").exists()
                    else None
                ),
                "book_audio_url": (
                    _build_media_url(book.path, Path(audio_dir) / "book.mp3")
                    if (book.path / audio_dir / "book.mp3").exists()
                    else None
                ),
            }
        )
    return {"books": entries}


def _chapter_title_from_content(content: str, fallback: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
    return fallback


def _find_chapter_file(book_dir: Path, chapter_value: str) -> Path:
    chapter_files = _book_chapter_files(book_dir)
    if chapter_value.isdigit():
        index = int(chapter_value)
        if 1 <= index <= len(chapter_files):
            return chapter_files[index - 1]
    for chapter_file in chapter_files:
        if chapter_value in {chapter_file.name, chapter_file.stem}:
            return chapter_file
    raise ApiError(f"Chapter '{chapter_value}' not found in {book_dir}.")


def list_chapters(payload: dict[str, Any]) -> dict[str, Any]:
    book_dir_value = payload.get("book_dir")
    if not book_dir_value:
        raise ApiError("book_dir is required")
    book_dir = Path(book_dir_value)
    audio_dirname = payload.get("audio_dirname", "audio")
    video_dirname = payload.get("video_dirname", "video")
    chapter_cover_dir = payload.get("chapter_cover_dir", "chapter_covers")
    chapters = []
    for index, chapter_file in enumerate(_book_chapter_files(book_dir), start=1):
        content = chapter_file.read_text(encoding="utf-8")
        title = _chapter_title_from_content(content, chapter_file.stem)
        page_count = _estimate_page_count(content)
        summary = _ensure_chapter_summary_async(
            book_dir, chapter_file, title, content, payload
        )
        audio_path = book_dir / audio_dirname / f"{chapter_file.stem}.mp3"
        video_path = book_dir / video_dirname / f"{chapter_file.stem}.mp4"
        cover_path = (
            book_dir / chapter_cover_dir / f"{chapter_file.stem}.png"
        )
        chapters.append(
            {
                "index": index,
                "name": chapter_file.name,
                "stem": chapter_file.stem,
                "title": title,
                "page_count": page_count,
                "summary": summary,
                "cover_url": (
                    _build_media_url(
                        book_dir, cover_path.relative_to(book_dir)
                    )
                    if cover_path.exists()
                    else None
                ),
                "audio_url": (
                    _build_media_url(book_dir, audio_path.relative_to(book_dir))
                    if audio_path.exists()
                    else None
                ),
                "video_url": (
                    _build_media_url(book_dir, video_path.relative_to(book_dir))
                    if video_path.exists()
                    else None
                ),
            }
        )
    return {"chapters": chapters}


def get_outline_content(payload: dict[str, Any]) -> dict[str, Any]:
    outline_path_value = payload.get("outline_path")
    if not outline_path_value:
        raise ApiError("outline_path is required")
    outline_path = Path(outline_path_value)
    if not outline_path.is_file():
        raise ApiError("Outline file not found.")
    content = outline_path.read_text(encoding="utf-8")
    title, items = parse_outline_with_title(outline_path)
    if title is None:
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                candidate = stripped.lstrip("#").strip()
                if candidate:
                    title = candidate
                    break
    if title is None:
        title = outline_path.stem
    return {
        "outline_path": str(outline_path),
        "title": title,
        "content": content,
        "item_count": len(items),
    }


def get_chapter_content(payload: dict[str, Any]) -> dict[str, Any]:
    book_dir_value = payload.get("book_dir")
    chapter_value = payload.get("chapter")
    if not book_dir_value:
        raise ApiError("book_dir is required")
    if not chapter_value:
        raise ApiError("chapter is required")
    book_dir = Path(book_dir_value)
    chapter_file = _find_chapter_file(book_dir, str(chapter_value))
    content = chapter_file.read_text(encoding="utf-8")
    title = _chapter_title_from_content(content, chapter_file.stem)
    summary = _ensure_chapter_summary_async(
        book_dir, chapter_file, title, content, payload
    )
    audio_dirname = payload.get("audio_dirname", "audio")
    video_dirname = payload.get("video_dirname", "video")
    chapter_cover_dir = payload.get("chapter_cover_dir", "chapter_covers")
    audio_path = book_dir / audio_dirname / f"{chapter_file.stem}.mp3"
    video_path = book_dir / video_dirname / f"{chapter_file.stem}.mp4"
    cover_path = book_dir / chapter_cover_dir / f"{chapter_file.stem}.png"
    audio_url = (
        _build_media_url(book_dir, audio_path.relative_to(book_dir))
        if audio_path.exists()
        else None
    )
    video_url = (
        _build_media_url(book_dir, video_path.relative_to(book_dir))
        if video_path.exists()
        else None
    )
    cover_url = (
        _build_media_url(book_dir, cover_path.relative_to(book_dir))
        if cover_path.exists()
        else None
    )
    return {
        "chapter": chapter_file.name,
        "title": title,
        "content": content,
        "page_count": _estimate_page_count(content),
        "summary": summary,
        "cover_url": cover_url,
        "audio_url": audio_url,
        "video_url": video_url,
    }


def get_book_content(payload: dict[str, Any]) -> dict[str, Any]:
    book_dir_value = payload.get("book_dir")
    if not book_dir_value:
        raise ApiError("book_dir is required")
    book_dir = Path(book_dir_value)
    synopsis = _read_book_synopsis(book_dir)
    title = _read_book_title(book_dir)
    summary = _ensure_book_summary_async(book_dir, title, payload)
    return {
        "book_dir": str(book_dir),
        "title": title,
        "summary": summary,
        "synopsis": synopsis,
    }


def generate_book(payload: dict[str, Any]) -> dict[str, Any]:
    outline_path_value = payload.get("outline_path")
    if not outline_path_value:
        raise ApiError("outline_path is required")
    outline_path = Path(outline_path_value)
    output_dir = Path(payload.get("output_dir", "output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    title, items = parse_outline_with_title(outline_path)
    if not items:
        raise ApiError("No outline items found in the outline file.")

    client = _build_client(payload)
    tts_settings = _parse_tts_settings(payload)
    video_settings = _parse_video_settings(payload)
    written_files = write_book(
        items=items,
        output_dir=output_dir,
        client=client,
        verbose=bool(payload.get("verbose", False)),
        tts_settings=tts_settings,
        video_settings=video_settings,
        book_title=payload.get("book_title") or title,
        byline=payload.get("byline", "Marissa Bard"),
        tone=payload.get("tone", "instructive self help guide"),
        resume=bool(payload.get("resume", False)),
        log_prompts=True,
    )
    return {
        "written_files": [str(path) for path in written_files],
        "output_dir": str(output_dir),
    }


def expand_book_api(payload: dict[str, Any]) -> dict[str, Any]:
    book_dir_value = payload.get("expand_book")
    if not book_dir_value:
        raise ApiError("expand_book is required")
    book_dir = Path(book_dir_value)
    client = _build_client(payload)
    tts_settings = _parse_tts_settings(payload)
    video_settings = _parse_video_settings(payload)
    expand_only = _get_value(payload, "expand_only")
    chapter_files = None
    if expand_only:
        chapter_files = _select_chapter_files(
            _book_chapter_files(book_dir),
            str(expand_only),
        )
    expand_book(
        output_dir=book_dir,
        client=client,
        passes=int(payload.get("expand_passes", 1)),
        verbose=bool(payload.get("verbose", False)),
        tts_settings=tts_settings,
        video_settings=video_settings,
        tone=payload.get("tone", "instructive self help guide"),
        chapter_files=chapter_files,
    )
    return {"status": "expanded", "book_dir": str(book_dir)}


def compile_book_api(payload: dict[str, Any]) -> dict[str, Any]:
    book_dir_value = payload.get("book_dir")
    if not book_dir_value:
        raise ApiError("book_dir is required")
    book_dir = Path(book_dir_value)
    compile_book(book_dir)
    return {"status": "compiled", "book_dir": str(book_dir)}


def generate_audio_api(payload: dict[str, Any]) -> dict[str, Any]:
    book_dir_value = payload.get("book_dir")
    if not book_dir_value:
        raise ApiError("book_dir is required")
    book_dir = Path(book_dir_value)
    tts_settings = _parse_tts_settings(payload)
    generate_book_audio(
        output_dir=book_dir,
        tts_settings=tts_settings,
        verbose=bool(payload.get("verbose", False)),
    )
    return {"status": "audio_generated", "book_dir": str(book_dir)}


def generate_videos_api(payload: dict[str, Any]) -> dict[str, Any]:
    book_dir_value = payload.get("book_dir")
    if not book_dir_value:
        raise ApiError("book_dir is required")
    book_dir = Path(book_dir_value)
    video_settings = _parse_video_settings(payload)
    client = _build_client(payload)
    generate_book_videos(
        output_dir=book_dir,
        video_settings=video_settings,
        audio_dirname=payload.get("audio_dirname", "audio"),
        verbose=bool(payload.get("verbose", False)),
        client=client,
    )
    return {"status": "videos_generated", "book_dir": str(book_dir)}


def generate_cover_api(payload: dict[str, Any]) -> dict[str, Any]:
    book_dir_value = payload.get("book_dir")
    if not book_dir_value:
        raise ApiError("book_dir is required")
    book_dir = Path(book_dir_value)
    cover_settings = _parse_cover_settings(payload)
    client = _build_client(payload)
    generate_book_cover_asset(book_dir, cover_settings, client=client)
    return {"status": "cover_generated", "book_dir": str(book_dir)}


def generate_chapter_covers_api(payload: dict[str, Any]) -> dict[str, Any]:
    book_dir_value = payload.get("book_dir")
    if not book_dir_value:
        raise ApiError("book_dir is required")
    book_dir = Path(book_dir_value)
    chapter_value = payload.get("chapter")
    chapter_cover_dir = payload.get("chapter_cover_dir", "chapter_covers")
    cover_settings = _parse_cover_settings(payload)
    client = _build_client(payload)
    chapter_files = None
    if chapter_value:
        chapter_files = [_find_chapter_file(book_dir, str(chapter_value))]
    generated = generate_chapter_cover_assets(
        output_dir=book_dir,
        cover_settings=cover_settings,
        chapter_cover_dir=chapter_cover_dir,
        chapter_files=chapter_files,
        client=client,
    )
    return {
        "status": "chapter_covers_generated",
        "book_dir": str(book_dir),
        "generated": [str(path) for path in generated],
    }


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _send_json(handler: BaseHTTPRequestHandler, payload: dict[str, Any], status: int) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _send_html(handler: BaseHTTPRequestHandler, html: str) -> None:
    body = html.encode("utf-8")
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _send_file(handler: BaseHTTPRequestHandler, path: Path) -> None:
    body = path.read_bytes()
    content_type, _ = mimetypes.guess_type(path.name)
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type or "application/octet-stream")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    try:
        handler.wfile.write(body)
    except (BrokenPipeError, ConnectionResetError):
        return


def _parse_query(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    query = parse_qs(urlparse(handler.path).query)
    return {key: values[0] for key, values in query.items() if values}


def _build_media_url(book_dir: Path, relative_path: Path) -> str:
    return (
        "/media?book_dir="
        + quote(str(book_dir))
        + "&path="
        + quote(str(relative_path))
    )


def _resolve_media_path(book_dir: Path, relative_path: str) -> Path:
    candidate = (book_dir / relative_path).resolve()
    book_root = book_dir.resolve()
    if book_root not in candidate.parents and candidate != book_root:
        raise ApiError("Invalid media path.")
    if not candidate.is_file():
        raise ApiError("Media file not found.")
    return candidate


def _handle_api(handler: BaseHTTPRequestHandler) -> None:
    path = urlparse(handler.path).path
    try:
        if path == "/api/outlines":
            response = list_outlines(_parse_query(handler))
            _send_json(handler, response, HTTPStatus.OK)
            return
        if path == "/api/completed-outlines":
            response = list_completed_outlines(_parse_query(handler))
            _send_json(handler, response, HTTPStatus.OK)
            return
        if path == "/api/books":
            response = list_books(_parse_query(handler))
            _send_json(handler, response, HTTPStatus.OK)
            return
        if path == "/api/authors":
            response = list_authors(_parse_query(handler))
            _send_json(handler, response, HTTPStatus.OK)
            return
        if path == "/api/tones":
            response = list_tones(_parse_query(handler))
            _send_json(handler, response, HTTPStatus.OK)
            return
        if path == "/api/chapters":
            response = list_chapters(_parse_query(handler))
            _send_json(handler, response, HTTPStatus.OK)
            return
        if path == "/api/outline-content":
            response = get_outline_content(_parse_query(handler))
            _send_json(handler, response, HTTPStatus.OK)
            return
        if path == "/api/chapter-content":
            response = get_chapter_content(_parse_query(handler))
            _send_json(handler, response, HTTPStatus.OK)
            return
        if path == "/api/book-content":
            response = get_book_content(_parse_query(handler))
            _send_json(handler, response, HTTPStatus.OK)
            return

        payload = _read_json(handler)
        routes = {
            "/api/generate-book": generate_book,
            "/api/expand-book": expand_book_api,
            "/api/compile-book": compile_book_api,
            "/api/generate-audio": generate_audio_api,
            "/api/generate-videos": generate_videos_api,
            "/api/generate-cover": generate_cover_api,
            "/api/generate-chapter-covers": generate_chapter_covers_api,
            "/api/generate-outline": generate_outline_api,
            "/api/save-outline": save_outline_api,
        }
        handler_fn = routes.get(path)
        if handler_fn is None:
            _send_json(handler, {"error": "Unknown endpoint"}, HTTPStatus.NOT_FOUND)
            return
        response = handler_fn(payload)
        _send_json(handler, response, HTTPStatus.OK)
    except ApiError as exc:
        _send_json(handler, {"error": str(exc)}, HTTPStatus.BAD_REQUEST)
    except json.JSONDecodeError:
        _send_json(handler, {"error": "Invalid JSON payload."}, HTTPStatus.BAD_REQUEST)


def _handle_media(handler: BaseHTTPRequestHandler) -> None:
    try:
        query = _parse_query(handler)
        book_dir_value = query.get("book_dir")
        relative_path = query.get("path")
        if not book_dir_value or not relative_path:
            raise ApiError("book_dir and path are required.")
        media_path = _resolve_media_path(Path(book_dir_value), relative_path)
        _send_file(handler, media_path)
    except ApiError as exc:
        _send_json(handler, {"error": str(exc)}, HTTPStatus.BAD_REQUEST)


class BookWriterRequestHandler(BaseHTTPRequestHandler):
    """Serve the GUI and CLI-equivalent API endpoints."""

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path.startswith("/api/"):
            _handle_api(self)
            return
        if self.path.startswith("/media"):
            _handle_media(self)
            return
        _send_html(self, get_gui_html())

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if not self.path.startswith("/api/"):
            _send_json(self, {"error": "Unsupported endpoint"}, HTTPStatus.NOT_FOUND)
            return
        _handle_api(self)


def run_server(host: str = "127.0.0.1", port: int = 8080) -> ThreadingHTTPServer:
    """Run the Book Writer HTTP server."""
    server = ThreadingHTTPServer((host, port), BookWriterRequestHandler)
    print(f"Book Writer GUI available at http://{host}:{port}")
    server.serve_forever()
    return server
