"""HTTP server exposing the Book Writer CLI functionality for the GUI."""
from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

from book_writer.cli import (
    _book_chapter_files,
    _book_directories,
    _outline_preview_text,
    _select_chapter_files,
)
from book_writer.gui import get_gui_html
from book_writer.outline import parse_outline_with_title
from book_writer.tts import TTSSettings
from book_writer.video import VideoSettings
from book_writer.writer import (
    LMStudioClient,
    compile_book,
    expand_book,
    generate_book_audio,
    generate_book_videos,
    write_book,
)


class ApiError(ValueError):
    """Raised when API input is invalid."""


def _get_value(data: dict[str, Any], key: str, default: Any = None) -> Any:
    value = data.get(key, default)
    if value is None:
        return default
    return value


def _parse_tts_settings(payload: dict[str, Any]) -> TTSSettings:
    tts_payload = payload.get("tts_settings") or {}
    return TTSSettings(
        enabled=bool(tts_payload.get("enabled", payload.get("tts", True))),
        voice=tts_payload.get("voice", "en-US-JennyNeural"),
        rate=tts_payload.get("rate", "+0%"),
        pitch=tts_payload.get("pitch", "+0Hz"),
        audio_dirname=tts_payload.get("audio_dirname", "audio"),
        overwrite_audio=bool(tts_payload.get("overwrite_audio", False)),
        book_only=bool(tts_payload.get("book_only", False)),
    )


def _parse_video_settings(payload: dict[str, Any]) -> VideoSettings:
    video_payload = payload.get("video_settings") or {}
    return VideoSettings(
        enabled=bool(video_payload.get("enabled", payload.get("video", False))),
        background_video=Path(video_payload["background_video"])
        if video_payload.get("background_video")
        else None,
        video_dirname=video_payload.get("video_dirname", "video"),
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


def list_outlines(payload: dict[str, Any]) -> dict[str, Any]:
    outlines_dir = Path(payload.get("outlines_dir", "outlines"))
    return {"outlines": _collect_outlines(outlines_dir)}


def list_completed_outlines(payload: dict[str, Any]) -> dict[str, Any]:
    outlines_dir = Path(payload.get("completed_outlines_dir", "completed_outlines"))
    return {"outlines": _collect_outlines(outlines_dir)}


def list_books(payload: dict[str, Any]) -> dict[str, Any]:
    books_dir = Path(payload.get("books_dir", "books"))
    audio_dir = payload.get("tts_audio_dir", "audio")
    video_dir = payload.get("video_dir", "video")
    books = _book_directories(books_dir, audio_dir, video_dir)
    return {
        "books": [
            {
                "path": str(book.path),
                "title": book.title,
                "has_text": book.has_text,
                "has_audio": book.has_audio,
                "has_video": book.has_video,
                "has_compilation": book.has_compilation,
                "chapter_count": len(_book_chapter_files(book.path)),
                "book_audio_url": (
                    _build_media_url(book.path, Path(audio_dir) / "book.mp3")
                    if (book.path / audio_dir / "book.mp3").exists()
                    else None
                ),
            }
            for book in books
        ]
    }


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
    chapters = []
    for index, chapter_file in enumerate(_book_chapter_files(book_dir), start=1):
        content = chapter_file.read_text(encoding="utf-8")
        title = _chapter_title_from_content(content, chapter_file.stem)
        audio_path = book_dir / audio_dirname / f"{chapter_file.stem}.mp3"
        video_path = book_dir / video_dirname / f"{chapter_file.stem}.mp4"
        chapters.append(
            {
                "index": index,
                "name": chapter_file.name,
                "stem": chapter_file.stem,
                "title": title,
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
    audio_dirname = payload.get("audio_dirname", "audio")
    video_dirname = payload.get("video_dirname", "video")
    audio_path = book_dir / audio_dirname / f"{chapter_file.stem}.mp3"
    video_path = book_dir / video_dirname / f"{chapter_file.stem}.mp4"
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
    return {
        "chapter": chapter_file.name,
        "title": title,
        "content": content,
        "audio_url": audio_url,
        "video_url": video_url,
    }


def generate_book(payload: dict[str, Any]) -> dict[str, Any]:
    outline_path_value = payload.get("outline_path")
    if not outline_path_value:
        raise ApiError("outline_path is required")
    outline_path = Path(outline_path_value)
    output_dir = Path(payload.get("output_dir", "output"))
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
    generate_book_videos(
        output_dir=book_dir,
        video_settings=video_settings,
        audio_dirname=payload.get("audio_dirname", "audio"),
        verbose=bool(payload.get("verbose", False)),
    )
    return {"status": "videos_generated", "book_dir": str(book_dir)}


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
    handler.wfile.write(body)


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

        payload = _read_json(handler)
        routes = {
            "/api/generate-book": generate_book,
            "/api/expand-book": expand_book_api,
            "/api/compile-book": compile_book_api,
            "/api/generate-audio": generate_audio_api,
            "/api/generate-videos": generate_videos_api,
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
