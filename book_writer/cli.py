from __future__ import annotations

import argparse
import importlib
import re
from dataclasses import dataclass
from typing import Callable, Optional
from pathlib import Path

from book_writer.outline import parse_outline, parse_outline_with_title
from book_writer.tts import TTSSettings
from book_writer.video import VideoSettings
from book_writer.writer import (
    LMStudioClient,
    clear_book_progress,
    compile_book,
    expand_book,
    generate_book_audio,
    generate_book_title,
    generate_book_videos,
    load_book_progress,
    write_book,
)


def _outline_files(outlines_dir: Path) -> list[Path]:
    if not outlines_dir.exists():
        return []
    return sorted(path for path in outlines_dir.iterdir() if path.suffix == ".md")


def _tone_files(tones_dir: Path) -> list[Path]:
    if not tones_dir.exists():
        return []
    return sorted(path for path in tones_dir.iterdir() if path.suffix == ".md")


def _author_files(authors_dir: Path) -> list[Path]:
    if not authors_dir.exists():
        return []
    return sorted(path for path in authors_dir.iterdir() if path.suffix == ".md")


def _tone_options() -> list[str]:
    tones_dir = Path(__file__).parent / "tones"
    return [tone.stem for tone in _tone_files(tones_dir)]


def _author_options() -> list[str]:
    authors_dir = Path(__file__).resolve().parents[1] / "authors"
    return [author.stem for author in _author_files(authors_dir)]


def _questionary():
    return importlib.import_module("questionary")


def _prompt_yes_no(prompt: str, default: bool) -> bool:
    questionary = _questionary()
    response = questionary.confirm(prompt, default=default).ask()
    if response is None:
        return default
    return response


def _prompt_for_outline_selection(outline_info: list["OutlineInfo"]) -> list["OutlineInfo"]:
    if not outline_info:
        return []
    questionary = _questionary()
    choices = [
        questionary.Choice(
            title=f"{info.path.name} — {info.title or '(title will be generated)'}",
            value=info,
        )
        for info in outline_info
    ]
    preview_selection = questionary.checkbox(
        "Select outlines to preview (optional):",
        choices=choices,
    ).ask()
    if preview_selection:
        for info in preview_selection:
            print(f"\nPreview for {info.path.name}:")
            print(info.preview_text)

    selection_choices = [
        questionary.Choice(
            title=f"{info.path.name} — {info.title or '(title will be generated)'}",
            value=info,
            checked=True,
        )
        for info in outline_info
    ]
    selected = questionary.checkbox(
        "Select outlines to generate:",
        choices=selection_choices,
    ).ask()
    return selected or []


def _prompt_for_tone(
    outline_name: str,
    tone_options: list[str],
    default: str,
) -> str:
    if not tone_options:
        return default
    questionary = _questionary()
    choices = [
        questionary.Choice(title=tone, value=tone) for tone in tone_options
    ]
    choices.append(questionary.Choice(title="Custom tone...", value="__custom__"))
    selected = questionary.select(
        f"Select a tone for {outline_name}:",
        choices=choices,
        default=default,
    ).ask()
    if selected == "__custom__":
        custom = questionary.text(
            "Enter a custom tone description:",
            default=default,
        ).ask()
        return custom or default
    return selected or default


def _prompt_for_author(
    outline_name: str,
    author_options: list[str],
    default: Optional[str],
) -> Optional[str]:
    if not author_options:
        return default
    questionary = _questionary()
    choices = [
        questionary.Choice(title="Default prompt (PROMPT.md)", value=None),
        *[
            questionary.Choice(
                title=f"{author} (authors/{author}.md)", value=author
            )
            for author in author_options
        ],
    ]
    selected = questionary.select(
        f"Select an author persona for {outline_name}:",
        choices=choices,
        default=default if default in author_options else None,
    ).ask()
    if selected is None:
        return default
    return selected


def _prompt_for_task_settings(
    args: argparse.Namespace,
) -> tuple[bool, str, TTSSettings, VideoSettings]:
    questionary = _questionary()
    task_choices = [
        questionary.Choice(
            title="Generate text content",
            value="text",
            checked=True,
        ),
        questionary.Choice(
            title="Generate audio narration",
            value="audio",
            checked=args.tts,
        ),
        questionary.Choice(
            title="Generate videos",
            value="video",
            checked=args.video,
        ),
    ]
    selected_tasks = questionary.checkbox(
        "Select content to generate:",
        choices=task_choices,
    ).ask()
    selected = set(selected_tasks or [])
    text_enabled = "text" in selected
    byline = args.byline
    if text_enabled:
        byline = (
            questionary.text(
                "Byline:",
                default=args.byline,
            ).ask()
            or args.byline
        )

    audio_enabled = "audio" in selected
    tts_settings = TTSSettings(
        enabled=audio_enabled,
        voice=args.tts_voice,
        rate=args.tts_rate,
        pitch=args.tts_pitch,
        audio_dirname=args.tts_audio_dir,
    )
    if audio_enabled:
        voice = questionary.text(
            "TTS voice:",
            default=args.tts_voice,
        ).ask()
        rate = questionary.text(
            "TTS rate:",
            default=args.tts_rate,
        ).ask()
        pitch = questionary.text(
            "TTS pitch:",
            default=args.tts_pitch,
        ).ask()
        audio_dir = questionary.text(
            "Audio output directory:",
            default=args.tts_audio_dir,
        ).ask()
        tts_settings = TTSSettings(
            enabled=True,
            voice=voice or args.tts_voice,
            rate=rate or args.tts_rate,
            pitch=pitch or args.tts_pitch,
            audio_dirname=audio_dir or args.tts_audio_dir,
        )

    video_enabled = "video" in selected
    background_video = args.background_video
    video_dirname = args.video_dir
    if video_enabled:
        background_response = questionary.text(
            "Background video path (leave blank for none):",
        ).ask()
        if background_response:
            background_video = Path(background_response)
        video_dir_response = questionary.text(
            "Video output directory:",
            default=args.video_dir,
        ).ask()
        if video_dir_response:
            video_dirname = video_dir_response
    video_settings = VideoSettings(
        enabled=video_enabled,
        background_video=background_video,
        video_dirname=video_dirname,
    )
    return text_enabled, byline, tts_settings, video_settings


def _outline_preview_text(title: Optional[str], items: list) -> str:
    lines = []
    if title:
        lines.append(f"Title: {title}")
    if not items:
        lines.append("(No outline items detected.)")
        return "\n".join(lines)
    if title:
        lines.append("Chapters:")
    for item in items:
        indent = "  " if item.level > 1 else ""
        lines.append(f"{indent}- {item.title}")
    return "\n".join(lines)


@dataclass(frozen=True)
class OutlineInfo:
    path: Path
    title: Optional[str]
    items: list
    preview_text: str


@dataclass(frozen=True)
class BookInfo:
    path: Path
    title: str
    has_text: bool
    has_audio: bool
    has_video: bool
    has_compilation: bool


@dataclass(frozen=True)
class BookTaskSelection:
    expand: bool
    expand_passes: int
    expand_only: Optional[str]
    compile: bool
    tts_settings: TTSSettings
    video_settings: VideoSettings
    generate_audio: bool
    generate_video: bool


def _book_chapter_files(book_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in book_dir.iterdir()
        if path.suffix == ".md"
        and path.name not in {"book.md", "back-cover-synopsis.md", "nextsteps.md"}
    )


def _select_chapter_files(
    chapter_files: list[Path], expand_only: Optional[str]
) -> list[Path]:
    if not expand_only:
        return chapter_files
    tokens = [token.strip() for token in expand_only.split(",") if token.strip()]
    if not tokens:
        raise ValueError("Expand-only selection was empty.")
    total = len(chapter_files)
    selection: set[Path] = set()
    chapter_by_name = {path.name: path for path in chapter_files}
    chapter_by_stem = {path.stem: path for path in chapter_files}
    range_pattern = re.compile(r"^(\d+)\s*-\s*(\d+)$")
    for token in tokens:
        range_match = range_pattern.match(token)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            if start < 1 or end < 1 or start > total or end > total:
                raise ValueError(
                    f"Expand-only range '{token}' is out of bounds for {total} chapters."
                )
            if start > end:
                start, end = end, start
            for index in range(start, end + 1):
                selection.add(chapter_files[index - 1])
            continue
        if token.isdigit():
            index = int(token)
            if index < 1 or index > total:
                raise ValueError(
                    f"Expand-only selection '{token}' is out of bounds for {total} chapters."
                )
            selection.add(chapter_files[index - 1])
            continue
        if token in chapter_by_name:
            selection.add(chapter_by_name[token])
            continue
        if token in chapter_by_stem:
            selection.add(chapter_by_stem[token])
            continue
        raise ValueError(
            f"Expand-only selection '{token}' did not match a chapter file."
        )
    return [path for path in chapter_files if path in selection]


def _book_title(book_dir: Path, chapter_files: list[Path]) -> str:
    book_md = book_dir / "book.md"
    if book_md.exists():
        for line in book_md.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    for chapter in chapter_files:
        for line in chapter.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    return book_dir.name


def _summarize_book_status(book_dir: Path, tts_audio_dir: str, video_dir: str) -> BookInfo:
    chapter_files = _book_chapter_files(book_dir)
    has_text = bool(chapter_files)
    title = _book_title(book_dir, chapter_files)
    audio_dir = book_dir / tts_audio_dir
    has_audio = audio_dir.exists() and any(
        path.suffix == ".mp3" for path in audio_dir.iterdir()
    )
    video_dir_path = book_dir / video_dir
    has_video = video_dir_path.exists() and any(
        path.suffix == ".mp4" for path in video_dir_path.iterdir()
    )
    has_compilation = (book_dir / "book.pdf").exists()
    return BookInfo(
        path=book_dir,
        title=title,
        has_text=has_text,
        has_audio=has_audio,
        has_video=has_video,
        has_compilation=has_compilation,
    )


def _book_directories(books_dir: Path, tts_audio_dir: str, video_dir: str) -> list[BookInfo]:
    if not books_dir.exists():
        return []
    book_dirs = sorted(path for path in books_dir.iterdir() if path.is_dir())
    return [
        _summarize_book_status(book_dir, tts_audio_dir, video_dir)
        for book_dir in book_dirs
    ]


def _format_book_status(book_info: BookInfo) -> str:
    def flag(label: str, active: bool) -> str:
        return f"{label}:{'yes' if active else 'no'}"

    return ", ".join(
        [
            flag("text", book_info.has_text),
            flag("audio", book_info.has_audio),
            flag("video", book_info.has_video),
            flag("compiled", book_info.has_compilation),
        ]
    )


def _prompt_for_book_selection(book_info: list[BookInfo]) -> list[BookInfo]:
    if not book_info:
        return []
    questionary = _questionary()
    choices = [
        questionary.Choice(
            title=(
                f"{info.path.name} — {info.title} ({_format_book_status(info)})"
            ),
            value=info,
        )
        for info in book_info
    ]
    selected = questionary.checkbox(
        "Select books to manage (optional):",
        choices=choices,
    ).ask()
    return selected or []


def _prompt_for_audio_settings(args: argparse.Namespace) -> TTSSettings:
    questionary = _questionary()
    voice = questionary.text(
        "TTS voice:",
        default=args.tts_voice,
    ).ask()
    rate = questionary.text(
        "TTS rate:",
        default=args.tts_rate,
    ).ask()
    pitch = questionary.text(
        "TTS pitch:",
        default=args.tts_pitch,
    ).ask()
    audio_dir = questionary.text(
        "Audio output directory:",
        default=args.tts_audio_dir,
    ).ask()
    return TTSSettings(
        enabled=True,
        voice=voice or args.tts_voice,
        rate=rate or args.tts_rate,
        pitch=pitch or args.tts_pitch,
        audio_dirname=audio_dir or args.tts_audio_dir,
    )


def _prompt_for_video_settings(args: argparse.Namespace) -> VideoSettings:
    questionary = _questionary()
    background_video = args.background_video
    video_dirname = args.video_dir
    background_response = questionary.text(
        "Background video path (leave blank for none):",
    ).ask()
    if background_response:
        background_video = Path(background_response)
    video_dir_response = questionary.text(
        "Video output directory:",
        default=args.video_dir,
    ).ask()
    if video_dir_response:
        video_dirname = video_dir_response
    return VideoSettings(
        enabled=True,
        background_video=background_video,
        video_dirname=video_dirname,
    )


def _prompt_for_book_tasks(args: argparse.Namespace) -> BookTaskSelection:
    questionary = _questionary()
    task_choices = [
        questionary.Choice("Expand selected books", value="expand"),
        questionary.Choice("Generate compiled book.pdf", value="compile"),
        questionary.Choice("Generate audio narration", value="audio"),
        questionary.Choice("Generate videos", value="video"),
    ]
    selected = questionary.checkbox(
        "Select tasks for the selected books:",
        choices=task_choices,
    ).ask()
    selected_tasks = set(selected or [])
    expand = "expand" in selected_tasks
    expand_passes = args.expand_passes
    expand_only = args.expand_only
    if expand:
        passes_response = questionary.text(
            "Expansion passes:",
            default=str(args.expand_passes),
        ).ask()
        if passes_response:
            try:
                expand_passes = int(passes_response)
            except ValueError:
                print("Expansion passes must be a whole number.")
                expand_passes = args.expand_passes
        expand_only_response = questionary.text(
            "Expand-only selection (optional):",
            default=args.expand_only or "",
        ).ask()
        if expand_only_response:
            expand_only = expand_only_response
    generate_audio = "audio" in selected_tasks
    tts_settings = TTSSettings(
        enabled=False,
        voice=args.tts_voice,
        rate=args.tts_rate,
        pitch=args.tts_pitch,
        audio_dirname=args.tts_audio_dir,
    )
    if generate_audio:
        tts_settings = _prompt_for_audio_settings(args)

    generate_video = "video" in selected_tasks
    video_settings = VideoSettings(
        enabled=False,
        background_video=args.background_video,
        video_dirname=args.video_dir,
    )
    if generate_video:
        video_settings = _prompt_for_video_settings(args)

    compile_book_assets = "compile" in selected_tasks
    return BookTaskSelection(
        expand=expand,
        expand_passes=expand_passes,
        expand_only=expand_only,
        compile=compile_book_assets,
        tts_settings=tts_settings,
        video_settings=video_settings,
        generate_audio=generate_audio,
        generate_video=generate_video,
    )


def _prompt_for_outline_generation(
    outline_files: list[Path], outline_path: Path
) -> bool:
    if not outline_files and not outline_path.exists():
        return False
    return _prompt_yes_no("Generate new books from outlines", True)


def _prompt_for_primary_action() -> str:
    questionary = _questionary()
    response = questionary.select(
        "Would you like to create new books or modify existing books?",
        choices=[
            questionary.Choice("Create new books", value="create"),
            questionary.Choice("Modify existing books", value="modify"),
        ],
    ).ask()
    return response or "create"


def write_books_from_outlines(
    outlines_dir: Path,
    books_dir: Path,
    completed_outlines_dir: Path,
    client: LMStudioClient,
    verbose: bool = False,
    tts_settings: Optional[TTSSettings] = None,
    video_settings: Optional[VideoSettings] = None,
    byline: str = "Marissa Bard",
    tone: str = "instructive self help guide",
    resume_decider: Optional[Callable[[Path, Path, dict], bool]] = None,
    outline_files: Optional[list[Path]] = None,
    tone_decider: Optional[Callable[[Path], str]] = None,
    author_decider: Optional[Callable[[Path], Optional[str]]] = None,
) -> list[Path]:
    tts_settings = tts_settings or TTSSettings()
    video_settings = video_settings or VideoSettings()
    written_files: list[Path] = []
    outline_files = outline_files or _outline_files(outlines_dir)
    if not outline_files:
        raise ValueError(f"No outline markdown files found in {outlines_dir}.")

    completed_outlines_dir.mkdir(parents=True, exist_ok=True)
    books_dir.mkdir(parents=True, exist_ok=True)

    for index, outline_path in enumerate(outline_files, start=1):
        if verbose:
            print(
                f"[batch] Step {index}/{len(outline_files)}: "
                f"Writing book for {outline_path.name}."
            )
        outline_title, items = parse_outline_with_title(outline_path)
        if not items:
            raise ValueError(f"No outline items found in {outline_path}.")
        if author_decider:
            client.set_author(author_decider(outline_path))
        book_title = outline_title or generate_book_title(items, client)
        outline_tone = tone_decider(outline_path) if tone_decider else tone

        book_short_title = outline_path.stem
        book_output_dir = books_dir / book_short_title
        resume = False
        progress = load_book_progress(book_output_dir)
        if progress:
            if progress.get("status") == "in_progress":
                if resume_decider:
                    resume = resume_decider(outline_path, book_output_dir, progress)
                    if not resume:
                        clear_book_progress(book_output_dir)
                else:
                    resume = True
            else:
                clear_book_progress(book_output_dir)
        written_files.extend(
            write_book(
                items=items,
                output_dir=book_output_dir,
                client=client,
                verbose=verbose,
                tts_settings=tts_settings,
                video_settings=video_settings,
                book_title=book_title,
                byline=byline,
                tone=outline_tone,
                resume=resume,
            )
        )
        reset_supported = client.reset_context()
        if verbose:
            if reset_supported:
                print("[batch] Reset LM Studio context between books.")
            else:
                print("[batch] LM Studio context reset not supported by API.")

        destination = completed_outlines_dir / outline_path.name
        outline_path.replace(destination)
        if verbose:
            print(f"[batch] Archived outline to {destination}.")

    return written_files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate book chapters from OUTLINE.md.")
    parser.add_argument(
        "--outline",
        type=Path,
        default=Path("OUTLINE.md"),
        help="Path to the outline markdown file.",
    )
    parser.add_argument(
        "--outlines-dir",
        type=Path,
        default=Path("outlines"),
        help="Directory containing multiple outline markdown files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory to write generated markdown files.",
    )
    parser.add_argument(
        "--expand-book",
        type=Path,
        default=None,
        help="Path to a completed book directory to expand.",
    )
    parser.add_argument(
        "--expand-passes",
        type=int,
        default=1,
        help="Number of expansion passes to run when expanding a completed book.",
    )
    parser.add_argument(
        "--expand-only",
        default=None,
        help=(
            "Comma-separated list of chapter numbers, ranges, or filenames to expand "
            "(e.g., '1,3-4,002-chapter-two.md')."
        ),
    )
    parser.add_argument(
        "--books-dir",
        type=Path,
        default=Path("books"),
        help="Directory to write book subfolders when using batch outlines.",
    )
    parser.add_argument(
        "--completed-outlines-dir",
        type=Path,
        default=Path("completed_outlines"),
        help="Directory to move completed outline markdown files.",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:1234",
        help="Base URL for the LM Studio API.",
    )
    parser.add_argument(
        "--model",
        default="local-model",
        help="Model name exposed by LM Studio.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Timeout in seconds for the API call. Omit for no timeout.",
    )
    parser.add_argument(
        "--no-tts",
        action="store_false",
        dest="tts",
        help="Disable MP3 narration for chapters and the synopsis.",
    )
    parser.add_argument(
        "--tts-voice",
        default="en-US-JennyNeural",
        help="Voice name for TTS narration (default: en-US-JennyNeural).",
    )
    parser.add_argument(
        "--tts-rate",
        default="+0%",
        help="Rate adjustment for TTS narration (e.g., '+5%').",
    )
    parser.add_argument(
        "--tts-pitch",
        default="+0Hz",
        help="Pitch adjustment for TTS narration (e.g., '+2Hz').",
    )
    parser.add_argument(
        "--tts-audio-dir",
        default="audio",
        help="Directory name for storing chapter audio files.",
    )
    parser.add_argument(
        "--video",
        action="store_true",
        help="Enable MP4 chapter videos using a background video and chapter audio.",
    )
    parser.add_argument(
        "--background-video",
        type=Path,
        default=None,
        help="Path to a local MP4 used as the looping background video.",
    )
    parser.add_argument(
        "--video-dir",
        default="video",
        help="Directory name for storing chapter video files.",
    )
    parser.add_argument(
        "--byline",
        default="Marissa Bard",
        help="Byline shown on the book title page.",
    )
    parser.add_argument(
        "--tone",
        default="instructive self help guide",
        help="Tone to use for chapter generation and expansion.",
    )
    parser.add_argument(
        "--author",
        default=None,
        help=(
            "Author persona to use from the authors/ folder (omit to use PROMPT.md)."
        ),
    )
    parser.add_argument(
        "--prompt",
        action="store_true",
        help="Use interactive prompts to select outlines, tones, and tasks.",
    )
    parser.set_defaults(tts=True)
    return parser


def _prompt_for_resume(output_dir: Path, progress: dict) -> bool:
    completed_steps = progress.get("completed_steps", 0)
    total_steps = progress.get("total_steps", "unknown")
    questionary = _questionary()
    response = questionary.select(
        (
            f"Found in-progress book generation in {output_dir} "
            f"(step {completed_steps}/{total_steps}). Continue from the last saved step?"
        ),
        choices=[
            questionary.Choice("Continue", value=True),
            questionary.Choice("Restart", value=False),
        ],
    ).ask()
    if response is None:
        return False
    return response


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    client = LMStudioClient(
        base_url=args.base_url,
        model=args.model,
        timeout=args.timeout,
        author=args.author,
    )
    tts_settings = TTSSettings(
        enabled=args.tts,
        voice=args.tts_voice,
        rate=args.tts_rate,
        pitch=args.tts_pitch,
        audio_dirname=args.tts_audio_dir,
    )
    video_settings = VideoSettings(
        enabled=args.video,
        background_video=args.background_video,
        video_dirname=args.video_dir,
    )
    tone_options = _tone_options()
    author_options = _author_options()
    if args.expand_book:
        selected_author = _prompt_for_author(
            args.expand_book.name, author_options, args.author
        )
        client.set_author(selected_author)
        selected_tone = _prompt_for_tone(
            args.expand_book.name, tone_options, args.tone
        )
        try:
            selected_chapters = _select_chapter_files(
                _book_chapter_files(args.expand_book), args.expand_only
            )
        except ValueError as exc:
            parser.error(str(exc))
        expand_book(
            output_dir=args.expand_book,
            client=client,
            passes=args.expand_passes,
            verbose=True,
            tts_settings=tts_settings,
            video_settings=video_settings,
            tone=selected_tone,
            chapter_files=selected_chapters,
        )
        return 0
    outline_files = _outline_files(args.outlines_dir)
    if args.prompt:
        primary_action = _prompt_for_primary_action()
        book_info = _book_directories(
            args.books_dir, args.tts_audio_dir, args.video_dir
        )
        if primary_action == "modify":
            selected_books = _prompt_for_book_selection(book_info)
            if not selected_books:
                return 0
            task_selection = _prompt_for_book_tasks(args)
            for book in selected_books:
                if task_selection.expand:
                    selected_author = _prompt_for_author(
                        book.path.name, author_options, args.author
                    )
                    client.set_author(selected_author)
                    selected_tone = _prompt_for_tone(
                        book.path.name, tone_options, args.tone
                    )
                    try:
                        selected_chapters = _select_chapter_files(
                            _book_chapter_files(book.path), task_selection.expand_only
                        )
                    except ValueError as exc:
                        parser.error(str(exc))
                    expand_book(
                        output_dir=book.path,
                        client=client,
                        passes=task_selection.expand_passes,
                        verbose=True,
                        tts_settings=task_selection.tts_settings,
                        video_settings=task_selection.video_settings,
                        tone=selected_tone,
                        chapter_files=selected_chapters,
                    )
                if task_selection.compile:
                    compile_book(book.path)
                if task_selection.generate_audio:
                    generate_book_audio(
                        output_dir=book.path,
                        tts_settings=task_selection.tts_settings,
                        verbose=True,
                    )
                if task_selection.generate_video:
                    generate_book_videos(
                        output_dir=book.path,
                        video_settings=task_selection.video_settings,
                        audio_dirname=task_selection.tts_settings.audio_dirname,
                        verbose=True,
                    )
            return 0
        if not outline_files and not args.outline.exists():
            parser.error("No outlines found to generate.")
        if outline_files:
            outline_info = []
            for outline_path in outline_files:
                outline_title, items = parse_outline_with_title(outline_path)
                preview_text = _outline_preview_text(outline_title, items)
                outline_info.append(
                    OutlineInfo(
                        path=outline_path,
                        title=outline_title,
                        items=items,
                        preview_text=preview_text,
                    )
                )
            selected_outlines = _prompt_for_outline_selection(outline_info)
            if not selected_outlines:
                parser.error("No outlines selected for generation.")
            author_map = {
                info.path: _prompt_for_author(
                    info.path.name, author_options, args.author
                )
                for info in selected_outlines
            }
            tone_map = {
                info.path: _prompt_for_tone(
                    info.path.name, tone_options, args.tone
                )
                for info in selected_outlines
            }
            text_enabled, byline, tts_settings, video_settings = (
                _prompt_for_task_settings(args)
            )
            if not text_enabled:
                print("Text generation disabled; no books were generated.")
                return 0
            try:
                write_books_from_outlines(
                    outlines_dir=args.outlines_dir,
                    books_dir=args.books_dir,
                    completed_outlines_dir=args.completed_outlines_dir,
                    client=client,
                    verbose=True,
                    tts_settings=tts_settings,
                    video_settings=video_settings,
                    byline=byline,
                    tone=args.tone,
                    resume_decider=lambda outline, output, progress: _prompt_for_resume(
                        output, progress
                    ),
                    outline_files=[info.path for info in selected_outlines],
                    tone_decider=lambda path: tone_map[path],
                    author_decider=lambda path: author_map[path],
                )
            except ValueError as exc:
                parser.error(str(exc))
            return 0
        outline_title, items = parse_outline_with_title(args.outline)
        if not items:
            parser.error("No outline items found in the outline file.")
        preview_text = _outline_preview_text(outline_title, items)
        print(f"Preview for {args.outline.name}:")
        print(preview_text)
        selected_author = _prompt_for_author(
            args.outline.name, author_options, args.author
        )
        client.set_author(selected_author)
        selected_tone = _prompt_for_tone(args.outline.name, tone_options, args.tone)
        text_enabled, byline, tts_settings, video_settings = _prompt_for_task_settings(
            args
        )
        if not text_enabled:
            print("Text generation disabled; no book was generated.")
            return 0
        book_title = outline_title or generate_book_title(items, client)
        resume = False
        progress = load_book_progress(args.output_dir)
        if progress:
            if progress.get("status") == "in_progress":
                resume = _prompt_for_resume(args.output_dir, progress)
                if not resume:
                    clear_book_progress(args.output_dir)
            else:
                clear_book_progress(args.output_dir)
        write_book(
            items=items,
            output_dir=args.output_dir,
            client=client,
            verbose=True,
            tts_settings=tts_settings,
            video_settings=video_settings,
            book_title=book_title,
            byline=byline,
            tone=selected_tone,
            resume=resume,
        )
        return 0
    if outline_files:
        try:
            write_books_from_outlines(
                outlines_dir=args.outlines_dir,
                books_dir=args.books_dir,
                completed_outlines_dir=args.completed_outlines_dir,
                client=client,
                verbose=True,
                tts_settings=tts_settings,
                video_settings=video_settings,
                byline=args.byline,
                tone=args.tone,
                resume_decider=lambda outline, output, progress: _prompt_for_resume(
                    output, progress
                ),
            )
        except ValueError as exc:
            parser.error(str(exc))
        return 0

    outline_title, items = parse_outline_with_title(args.outline)
    if not items:
        parser.error("No outline items found in the outline file.")
    book_title = outline_title or generate_book_title(items, client)
    resume = False
    progress = load_book_progress(args.output_dir)
    if progress:
        if progress.get("status") == "in_progress":
            resume = _prompt_for_resume(args.output_dir, progress)
            if not resume:
                clear_book_progress(args.output_dir)
        else:
            clear_book_progress(args.output_dir)
    write_book(
        items=items,
        output_dir=args.output_dir,
        client=client,
        verbose=True,
        tts_settings=tts_settings,
        video_settings=video_settings,
        book_title=book_title,
        byline=args.byline,
        tone=args.tone,
        resume=resume,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
