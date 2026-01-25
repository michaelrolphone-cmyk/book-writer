from __future__ import annotations

import argparse
import hashlib
import importlib
import re
from dataclasses import dataclass, replace
from typing import Callable, Optional
from pathlib import Path

from book_writer.cover import CoverSettings, parse_cover_command
from book_writer.outline import parse_outline, parse_outline_with_title
from book_writer.tts import DEFAULT_QWEN3_MODEL_PATH, TTSSettings
from book_writer.video import (
    ParagraphImageSettings,
    VideoSettings,
    parse_video_image_command,
)
from book_writer.writer import (
    LMStudioClient,
    clear_book_progress,
    compile_book,
    expand_book,
    generate_book_audio,
    generate_book_cover_asset,
    generate_chapter_cover_assets,
    generate_book_title,
    generate_book_videos,
    generate_outline,
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
    selected = questionary.checkbox(
        "Select outlines to generate:",
        choices=choices,
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
) -> tuple[bool, str, TTSSettings, VideoSettings, CoverSettings]:
    questionary = _questionary()
    default_module_path = CoverSettings().module_path
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
        questionary.Choice(
            title="Generate book cover",
            value="cover",
            checked=args.cover,
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
        language=args.tts_language,
        instruct=args.tts_instruct,
        model_path=args.tts_model_path,
        device_map=args.tts_device_map,
        dtype=args.tts_dtype,
        attn_implementation=args.tts_attn_implementation,
        rate=args.tts_rate,
        pitch=args.tts_pitch,
        audio_dirname=args.tts_audio_dir,
        overwrite_audio=args.tts_overwrite,
        book_only=args.tts_book_only,
    )
    if audio_enabled:
        voice = questionary.text(
            "TTS speaker:",
            default=args.tts_voice,
        ).ask()
        language = questionary.text(
            "TTS language:",
            default=args.tts_language,
        ).ask()
        instruct = questionary.text(
            "TTS instruct (optional):",
            default="Read in a clear, professional, and confident adult narrator's voice. Speak at a natural, conversational pace - not too fast, not too slow. Maintain a mature, authoritative tone suitable for adult literature. Use subtle emphasis and natural pauses only where appropriate for clarity, avoiding any condescending or overly dramatic delivery.",
        ).ask()
        model_path = questionary.text(
            "Qwen3 model path:",
            default=args.tts_model_path,
        ).ask()
        audio_dir = questionary.text(
            "Audio output directory:",
            default=args.tts_audio_dir,
        ).ask()
        overwrite_audio = _prompt_yes_no(
            "Overwrite existing audio files?",
            args.tts_overwrite,
        )
        tts_settings = TTSSettings(
            enabled=True,
            voice=voice or args.tts_voice,
            language=language or args.tts_language,
            instruct=instruct or None,
            model_path=model_path or args.tts_model_path,
            device_map=args.tts_device_map,
            dtype=args.tts_dtype,
            attn_implementation=args.tts_attn_implementation,
            rate=args.tts_rate,
            pitch=args.tts_pitch,
            audio_dirname=audio_dir or args.tts_audio_dir,
            overwrite_audio=overwrite_audio,
            book_only=args.tts_book_only,
        )

    video_enabled = "video" in selected
    background_video = args.background_video
    video_dirname = args.video_dir
    paragraph_images = False
    image_settings = _video_image_settings_from_args(args)
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
        paragraph_images = _prompt_yes_no(
            "Generate paragraph images for videos?",
            args.video_paragraph_images,
        )
        if paragraph_images:
            image_settings = _prompt_for_video_image_settings(
                args, image_settings
            )
    video_settings = VideoSettings(
        enabled=video_enabled,
        background_video=background_video,
        video_dirname=video_dirname,
        paragraph_images=replace(
            image_settings,
            enabled=paragraph_images,
        ),
    )
    cover_enabled = "cover" in selected
    cover_settings = CoverSettings(
        enabled=cover_enabled,
        prompt=args.cover_prompt,
        negative_prompt=args.cover_negative_prompt,
        model_path=args.cover_model_path,
        module_path=args.cover_module_path or default_module_path,
        steps=args.cover_steps,
        guidance_scale=args.cover_guidance_scale,
        seed=args.cover_seed,
        width=args.cover_width,
        height=args.cover_height,
        output_name=args.cover_output_name,
        overwrite=args.cover_overwrite,
        command=parse_cover_command(args.cover_command),
    )
    if cover_enabled:
        cover_settings = _prompt_for_cover_settings(args, cover_settings)
    return text_enabled, byline, tts_settings, video_settings, cover_settings


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
    has_cover: bool


@dataclass(frozen=True)
class BookTaskSelection:
    expand: bool
    expand_passes: int
    compile: bool
    tts_settings: TTSSettings
    video_settings: VideoSettings
    cover_settings: CoverSettings
    generate_audio: bool
    generate_video: bool
    generate_cover: bool
    generate_chapter_covers: bool
    chapter_cover_dir: str


def _book_chapter_files(book_dir: Path) -> list[Path]:
    if not book_dir.is_dir():
        return []
    try:
        entries = list(book_dir.iterdir())
    except OSError:
        return []
    return sorted(
        path
        for path in entries
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


def _prompt_for_expand_only(
    chapter_files: list[Path], expand_only: Optional[str]
) -> list[Path]:
    if not chapter_files:
        return chapter_files
    questionary = _questionary()
    default_selection: list[Path] = []
    if expand_only:
        default_selection = _select_chapter_files(chapter_files, expand_only)
    choices = [
        questionary.Choice(f"{index:03d}. {path.name}", value=path)
        for index, path in enumerate(chapter_files, start=1)
    ]
    default_values = default_selection or None
    checkbox_kwargs = {"choices": choices}
    if default_values:
        checkbox_kwargs["default"] = default_values
    selected = questionary.checkbox(
        "Select chapters to expand (leave blank for all):",
        **checkbox_kwargs,
    ).ask()
    if not selected:
        return chapter_files
    return [path for path in chapter_files if path in selected]


def _book_title(book_dir: Path, chapter_files: list[Path]) -> str:
    book_md = book_dir / "book.md"
    if book_md.exists():
        try:
            for line in book_md.read_text(encoding="utf-8").splitlines():
                if line.startswith("# "):
                    return line[2:].strip()
        except (OSError, UnicodeDecodeError):
            pass
    for chapter in chapter_files:
        try:
            for line in chapter.read_text(encoding="utf-8").splitlines():
                if line.startswith("# "):
                    return line[2:].strip()
        except (OSError, UnicodeDecodeError):
            continue
    return book_dir.name


def _summarize_book_status(book_dir: Path, tts_audio_dir: str, video_dir: str) -> BookInfo:
    chapter_files = _book_chapter_files(book_dir)
    has_text = bool(chapter_files)
    title = _book_title(book_dir, chapter_files)
    audio_dir = book_dir / tts_audio_dir
    has_audio = False
    if audio_dir.is_dir():
        try:
            has_audio = any(path.suffix == ".mp3" for path in audio_dir.iterdir())
        except OSError:
            has_audio = False
    video_dir_path = book_dir / video_dir
    has_video = False
    if video_dir_path.is_dir():
        try:
            has_video = any(path.suffix == ".mp4" for path in video_dir_path.iterdir())
        except OSError:
            has_video = False
    has_compilation = (book_dir / "book.pdf").exists()
    has_cover = (book_dir / "cover.png").exists()
    return BookInfo(
        path=book_dir,
        title=title,
        has_text=has_text,
        has_audio=has_audio,
        has_video=has_video,
        has_compilation=has_compilation,
        has_cover=has_cover,
    )


def _book_directories(books_dir: Path, tts_audio_dir: str, video_dir: str) -> list[BookInfo]:
    if not books_dir.is_dir():
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
            flag("cover", book_info.has_cover),
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
        "TTS speaker:",
        default=args.tts_voice,
    ).ask()
    language = questionary.text(
        "TTS language:",
        default=args.tts_language,
    ).ask()
    instruct = questionary.text(
        "TTS instruct (optional):",
        default=args.tts_instruct or "",
    ).ask()
    model_path = questionary.text(
        "Qwen3 model path:",
        default=args.tts_model_path,
    ).ask()
    audio_dir = questionary.text(
        "Audio output directory:",
        default=args.tts_audio_dir,
    ).ask()
    overwrite_audio = _prompt_yes_no(
        "Overwrite existing audio files?",
        args.tts_overwrite,
    )
    book_only = _prompt_yes_no(
        "Generate only the full book audiobook (skip chapter audio)?",
        args.tts_book_only,
    )
    return TTSSettings(
        enabled=True,
        voice=voice or args.tts_voice,
        language=language or args.tts_language,
        instruct=instruct or None,
        model_path=model_path or args.tts_model_path,
        device_map=args.tts_device_map,
        dtype=args.tts_dtype,
        attn_implementation=args.tts_attn_implementation,
        rate=args.tts_rate,
        pitch=args.tts_pitch,
        audio_dirname=audio_dir or args.tts_audio_dir,
        overwrite_audio=overwrite_audio,
        book_only=book_only,
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
    paragraph_images = _prompt_yes_no(
        "Generate paragraph images for videos?",
        args.video_paragraph_images,
    )
    image_settings = _video_image_settings_from_args(args)
    if paragraph_images:
        image_settings = _prompt_for_video_image_settings(args, image_settings)
    return VideoSettings(
        enabled=True,
        background_video=background_video,
        video_dirname=video_dirname,
        paragraph_images=replace(
            image_settings,
            enabled=paragraph_images,
        ),
    )


def _video_image_settings_from_args(
    args: argparse.Namespace,
) -> ParagraphImageSettings:
    default_settings = ParagraphImageSettings()
    return ParagraphImageSettings(
        enabled=args.video_paragraph_images,
        image_dirname=args.video_image_dir,
        negative_prompt=args.video_image_negative_prompt,
        model_path=args.video_image_model_path,
        module_path=args.video_image_module_path or default_settings.module_path,
        steps=args.video_image_steps,
        guidance_scale=args.video_image_guidance_scale,
        seed=args.video_image_seed,
        width=args.video_image_width,
        height=args.video_image_height,
        overwrite=args.video_image_overwrite,
        command=parse_video_image_command(args.video_image_command),
    )


def _prompt_for_video_image_settings(
    args: argparse.Namespace,
    settings: ParagraphImageSettings,
) -> ParagraphImageSettings:
    questionary = _questionary()
    image_dir = questionary.text(
        "Paragraph image output directory:",
        default=settings.image_dirname,
    ).ask()
    negative_prompt = questionary.text(
        "Negative prompt (optional):",
        default=settings.negative_prompt or "",
    ).ask()
    model_path_response = questionary.text(
        "Core ML model path (optional):",
        default=str(settings.model_path or ""),
    ).ask()
    module_path_response = questionary.text(
        "python_coreml_stable_diffusion module path:",
        default=str(settings.module_path or ""),
    ).ask()
    steps_response = questionary.text(
        "Inference steps:",
        default=str(settings.steps),
    ).ask()
    guidance_response = questionary.text(
        "Guidance scale:",
        default=str(settings.guidance_scale),
    ).ask()
    seed_response = questionary.text(
        "Seed (optional):",
        default="" if settings.seed is None else str(settings.seed),
    ).ask()
    width_response = questionary.text(
        "Image width:",
        default=str(settings.width),
    ).ask()
    height_response = questionary.text(
        "Image height:",
        default=str(settings.height),
    ).ask()
    overwrite = _prompt_yes_no(
        "Overwrite existing paragraph images?",
        settings.overwrite,
    )
    command_response = questionary.text(
        "Custom image command (optional):",
        default=args.video_image_command or "",
    ).ask()

    def parse_int(value: Optional[str], fallback: int) -> int:
        if value is None or not value.strip():
            return fallback
        try:
            return int(value)
        except ValueError:
            print(f"Invalid number '{value}', using {fallback}.")
            return fallback

    def parse_float(value: Optional[str], fallback: float) -> float:
        if value is None or not value.strip():
            return fallback
        try:
            return float(value)
        except ValueError:
            print(f"Invalid number '{value}', using {fallback}.")
            return fallback

    def parse_optional_int(value: Optional[str]) -> Optional[int]:
        if value is None or not value.strip():
            return None
        try:
            return int(value)
        except ValueError:
            print(f"Invalid seed '{value}', leaving unset.")
            return None

    model_path = Path(model_path_response) if model_path_response else None
    module_path = (
        Path(module_path_response) if module_path_response else settings.module_path
    )
    command = parse_video_image_command(command_response) or settings.command
    return ParagraphImageSettings(
        enabled=True,
        image_dirname=image_dir or settings.image_dirname,
        negative_prompt=negative_prompt or None,
        model_path=model_path,
        module_path=module_path,
        steps=parse_int(steps_response, settings.steps),
        guidance_scale=parse_float(guidance_response, settings.guidance_scale),
        seed=parse_optional_int(seed_response),
        width=parse_int(width_response, settings.width),
        height=parse_int(height_response, settings.height),
        overwrite=overwrite,
        command=command,
    )


def _prompt_for_cover_settings(
    args: argparse.Namespace,
    settings: CoverSettings,
) -> CoverSettings:
    questionary = _questionary()
    prompt = questionary.text(
        "Cover prompt override (leave blank for auto):",
        default=settings.prompt or "",
    ).ask()
    negative_prompt = questionary.text(
        "Negative prompt (optional):",
        default=settings.negative_prompt or "",
    ).ask()
    model_path_response = questionary.text(
        "Core ML model path (optional):",
        default=str(settings.model_path or ""),
    ).ask()
    module_path_response = questionary.text(
        "python_coreml_stable_diffusion module path:",
        default=str(settings.module_path or ""),
    ).ask()
    steps_response = questionary.text(
        "Inference steps:",
        default=str(settings.steps),
    ).ask()
    guidance_response = questionary.text(
        "Guidance scale:",
        default=str(settings.guidance_scale),
    ).ask()
    seed_response = questionary.text(
        "Seed (optional):",
        default="" if settings.seed is None else str(settings.seed),
    ).ask()
    width_response = questionary.text(
        "Image width:",
        default=str(settings.width),
    ).ask()
    height_response = questionary.text(
        "Image height:",
        default=str(settings.height),
    ).ask()
    output_name = questionary.text(
        "Cover output filename:",
        default=settings.output_name,
    ).ask()
    overwrite = _prompt_yes_no(
        "Overwrite existing cover image?",
        settings.overwrite,
    )
    command_response = questionary.text(
        "Custom cover command (optional):",
        default=args.cover_command or "",
    ).ask()

    def parse_int(value: Optional[str], fallback: int) -> int:
        if value is None or not value.strip():
            return fallback
        try:
            return int(value)
        except ValueError:
            print(f"Invalid number '{value}', using {fallback}.")
            return fallback

    def parse_float(value: Optional[str], fallback: float) -> float:
        if value is None or not value.strip():
            return fallback
        try:
            return float(value)
        except ValueError:
            print(f"Invalid number '{value}', using {fallback}.")
            return fallback

    def parse_optional_int(value: Optional[str]) -> Optional[int]:
        if value is None or not value.strip():
            return None
        try:
            return int(value)
        except ValueError:
            print(f"Invalid seed '{value}', leaving unset.")
            return None

    model_path = Path(model_path_response) if model_path_response else None
    module_path = (
        Path(module_path_response) if module_path_response else settings.module_path
    )
    command = parse_cover_command(command_response) or settings.command
    return CoverSettings(
        enabled=True,
        prompt=prompt or None,
        negative_prompt=negative_prompt or None,
        model_path=model_path,
        module_path=module_path,
        steps=parse_int(steps_response, settings.steps),
        guidance_scale=parse_float(guidance_response, settings.guidance_scale),
        seed=parse_optional_int(seed_response),
        width=parse_int(width_response, settings.width),
        height=parse_int(height_response, settings.height),
        output_name=output_name or settings.output_name,
        overwrite=overwrite,
        command=command,
    )


def _prompt_for_book_tasks(args: argparse.Namespace) -> BookTaskSelection:
    questionary = _questionary()
    default_module_path = CoverSettings().module_path
    task_choices = [
        questionary.Choice("Expand selected books", value="expand"),
        questionary.Choice("Generate compiled book.pdf", value="compile"),
        questionary.Choice("Generate audio narration", value="audio"),
        questionary.Choice("Generate videos", value="video"),
        questionary.Choice("Generate book cover", value="cover"),
        questionary.Choice("Generate chapter covers", value="chapter-cover"),
    ]
    selected = questionary.checkbox(
        "Select tasks for the selected books:",
        choices=task_choices,
    ).ask()
    selected_tasks = set(selected or [])
    expand = "expand" in selected_tasks
    expand_passes = args.expand_passes
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
    generate_audio = "audio" in selected_tasks
    tts_settings = TTSSettings(
        enabled=False,
        voice=args.tts_voice,
        language=args.tts_language,
        instruct=args.tts_instruct,
        model_path=args.tts_model_path,
        device_map=args.tts_device_map,
        dtype=args.tts_dtype,
        attn_implementation=args.tts_attn_implementation,
        rate=args.tts_rate,
        pitch=args.tts_pitch,
        audio_dirname=args.tts_audio_dir,
        overwrite_audio=args.tts_overwrite,
        book_only=args.tts_book_only,
    )
    if generate_audio:
        tts_settings = _prompt_for_audio_settings(args)

    generate_video = "video" in selected_tasks
    video_settings = VideoSettings(
        enabled=False,
        background_video=args.background_video,
        video_dirname=args.video_dir,
        paragraph_images=_video_image_settings_from_args(args),
    )
    if generate_video:
        video_settings = _prompt_for_video_settings(args)

    generate_cover = "cover" in selected_tasks
    generate_chapter_covers = "chapter-cover" in selected_tasks
    cover_settings = CoverSettings(
        enabled=generate_cover or generate_chapter_covers,
        prompt=args.cover_prompt,
        negative_prompt=args.cover_negative_prompt,
        model_path=args.cover_model_path,
        module_path=args.cover_module_path or default_module_path,
        steps=args.cover_steps,
        guidance_scale=args.cover_guidance_scale,
        seed=args.cover_seed,
        width=args.cover_width,
        height=args.cover_height,
        output_name=args.cover_output_name,
        overwrite=args.cover_overwrite,
        command=parse_cover_command(args.cover_command),
    )
    if generate_cover or generate_chapter_covers:
        cover_settings = _prompt_for_cover_settings(args, cover_settings)

    compile_book_assets = "compile" in selected_tasks
    chapter_cover_dir = args.chapter_cover_dir
    if generate_chapter_covers:
        chapter_cover_dir_response = questionary.text(
            "Chapter cover output directory:",
            default=args.chapter_cover_dir,
        ).ask()
        if chapter_cover_dir_response:
            chapter_cover_dir = chapter_cover_dir_response
    return BookTaskSelection(
        expand=expand,
        expand_passes=expand_passes,
        compile=compile_book_assets,
        tts_settings=tts_settings,
        video_settings=video_settings,
        cover_settings=cover_settings,
        generate_audio=generate_audio,
        generate_video=generate_video,
        generate_cover=generate_cover,
        generate_chapter_covers=generate_chapter_covers,
        chapter_cover_dir=chapter_cover_dir,
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
            questionary.Choice("Create a new outline", value="outline"),
            questionary.Choice("Launch GUI server", value="gui"),
        ],
    ).ask()
    return response or "create"


def _normalize_outline_name(filename: str) -> str:
    cleaned = filename.strip() or "outline.md"
    if not cleaned.endswith(".md"):
        cleaned = f"{cleaned}.md"
    return cleaned


def _prompt_for_outline_revisions() -> list[str]:
    questionary = _questionary()
    revisions: list[str] = []
    while _prompt_yes_no("Add a revision prompt?", False):
        response = questionary.text("Revision prompt:").ask()
        if response and response.strip():
            revisions.append(response.strip())
    return revisions


def write_outline_from_prompt(
    outlines_dir: Path,
    client: LMStudioClient,
    prompt: str,
    outline_name: str,
    revision_prompts: Optional[list[str]] = None,
) -> Path:
    outlines_dir.mkdir(parents=True, exist_ok=True)
    outline_path = outlines_dir / _normalize_outline_name(outline_name)
    outline_text = generate_outline(
        prompt=prompt,
        client=client,
        revision_prompts=revision_prompts,
    )
    outline_path.write_text(outline_text + "\n", encoding="utf-8")
    return outline_path


def write_books_from_outlines(
    outlines_dir: Path,
    books_dir: Path,
    completed_outlines_dir: Path,
    client: LMStudioClient,
    verbose: bool = False,
    tts_settings: Optional[TTSSettings] = None,
    video_settings: Optional[VideoSettings] = None,
    cover_settings: Optional[CoverSettings] = None,
    byline: str = "Marissa Bard",
    tone: str = "instructive self help guide",
    resume_decider: Optional[Callable[[Path, Path, dict], bool]] = None,
    outline_files: Optional[list[Path]] = None,
    tone_decider: Optional[Callable[[Path], str]] = None,
    author_decider: Optional[Callable[[Path], Optional[str]]] = None,
    log_prompts: bool = False,
) -> list[Path]:
    tts_settings = tts_settings or TTSSettings()
    video_settings = video_settings or VideoSettings()
    cover_settings = cover_settings or CoverSettings()
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
        outline_text = outline_path.read_text(encoding="utf-8")
        outline_title, items = parse_outline_with_title(outline_path)
        if not items:
            raise ValueError(f"No outline items found in {outline_path}.")
        if author_decider:
            client.set_author(author_decider(outline_path))
        book_title = outline_title or generate_book_title(items, client)
        outline_tone = tone_decider(outline_path) if tone_decider else tone
        outline_hash = hashlib.sha256(outline_text.encode("utf-8")).hexdigest()

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
                cover_settings=cover_settings,
                book_title=book_title,
                byline=byline,
                tone=outline_tone,
                resume=resume,
                log_prompts=log_prompts,
                outline_hash=outline_hash,
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
        default="Ryan",
        help="Speaker name for Qwen3 narration (default: Ryan).",
    )
    parser.add_argument(
        "--tts-language",
        default="English",
        help="Language label for Qwen3 narration (default: English).",
    )
    parser.add_argument(
        "--tts-instruct",
        default=None,
        help="Optional instruction prompt for Qwen3 narration (e.g., 'Very happy.').",
    )
    parser.add_argument(
        "--tts-model-path",
        default=str(DEFAULT_QWEN3_MODEL_PATH),
        help="Path to the Qwen3 TTS model directory.",
    )
    parser.add_argument(
        "--tts-device-map",
        default="auto",
        help="Device map for Qwen3 (e.g., 'auto', 'mps', 'cuda').",
    )
    parser.add_argument(
        "--tts-dtype",
        default="float32",
        help="Torch dtype for Qwen3 (e.g., 'float32', 'float16').",
    )
    parser.add_argument(
        "--tts-attn-implementation",
        default="sdpa",
        help="Attention implementation for Qwen3 (default: sdpa).",
    )
    parser.add_argument(
        "--tts-rate",
        default="+0%",
        help="Rate adjustment for legacy TTS (unused by Qwen3).",
    )
    parser.add_argument(
        "--tts-pitch",
        default="+0Hz",
        help="Pitch adjustment for legacy TTS (unused by Qwen3).",
    )
    parser.add_argument(
        "--tts-audio-dir",
        default="audio",
        help="Directory name for storing chapter audio files.",
    )
    parser.add_argument(
        "--tts-overwrite",
        action="store_true",
        help="Overwrite existing audio files when generating narration.",
    )
    parser.add_argument(
        "--tts-book-only",
        action="store_true",
        help="Generate only the full book MP3 when producing audio narration.",
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
        "--video-paragraph-images",
        action="store_true",
        help=(
            "Generate videos from paragraph images keyed to audio timing instead of "
            "a looping background video."
        ),
    )
    parser.add_argument(
        "--video-image-dir",
        default="video_images",
        help="Directory name for storing per-paragraph video images.",
    )
    parser.add_argument(
        "--video-image-negative-prompt",
        default=None,
        help="Negative prompt for paragraph image generation.",
    )
    parser.add_argument(
        "--video-image-model-path",
        type=Path,
        default=None,
        help="Path to the Core ML model resources for paragraph image generation.",
    )
    parser.add_argument(
        "--video-image-module-path",
        type=Path,
        default=None,
        help=(
            "Path to the python_coreml_stable_diffusion module for paragraph "
            "image generation (default: ../ml-stable-diffusion)."
        ),
    )
    parser.add_argument(
        "--video-image-steps",
        type=int,
        default=30,
        help="Inference steps for paragraph image generation.",
    )
    parser.add_argument(
        "--video-image-guidance-scale",
        type=float,
        default=7.5,
        help="Guidance scale for paragraph image generation.",
    )
    parser.add_argument(
        "--video-image-seed",
        type=int,
        default=None,
        help="Seed for paragraph image generation.",
    )
    parser.add_argument(
        "--video-image-width",
        type=int,
        default=1280,
        help="Width for paragraph image generation.",
    )
    parser.add_argument(
        "--video-image-height",
        type=int,
        default=720,
        help="Height for paragraph image generation.",
    )
    parser.add_argument(
        "--video-image-overwrite",
        action="store_true",
        help="Overwrite existing paragraph images.",
    )
    parser.add_argument(
        "--video-image-command",
        default=None,
        help=(
            "Custom command template for paragraph image generation (uses placeholders "
            "like {prompt} and {output_path})."
        ),
    )
    parser.add_argument(
        "--cover",
        action="store_true",
        help="Generate a book cover image using python_coreml_stable_diffusion.",
    )
    parser.add_argument(
        "--cover-prompt",
        default=None,
        help="Override the prompt used to generate the book cover image.",
    )
    parser.add_argument(
        "--cover-negative-prompt",
        default=None,
        help="Negative prompt to avoid unwanted cover elements.",
    )
    parser.add_argument(
        "--cover-model-path",
        type=Path,
        default=None,
        help="Path to the compiled Core ML resource folder for cover generation.",
    )
    parser.add_argument(
        "--cover-module-path",
        type=Path,
        default=None,
        help=(
            "Path to the python_coreml_stable_diffusion module "
            "(default: ../ml-stable-diffusion)."
        ),
    )
    parser.add_argument(
        "--cover-steps",
        type=int,
        default=30,
        help="Number of inference steps for cover generation.",
    )
    parser.add_argument(
        "--cover-guidance-scale",
        type=float,
        default=7.5,
        help="Guidance scale (CFG) for cover generation.",
    )
    parser.add_argument(
        "--cover-seed",
        type=int,
        default=None,
        help="Random seed for cover generation.",
    )
    parser.add_argument(
        "--cover-width",
        type=int,
        default=768,
        help="Output width for the cover image.",
    )
    parser.add_argument(
        "--cover-height",
        type=int,
        default=1024,
        help="Output height for the cover image.",
    )
    parser.add_argument(
        "--cover-output-name",
        default="cover.png",
        help="Filename for the generated cover image.",
    )
    parser.add_argument(
        "--cover-overwrite",
        action="store_true",
        help="Overwrite any existing cover image.",
    )
    parser.add_argument(
        "--cover-command",
        default=None,
        help=(
            "Custom command template for cover generation. "
            "Use placeholders like {prompt}, {output_path}, {steps}."
        ),
    )
    parser.add_argument(
        "--cover-book",
        type=Path,
        default=None,
        help="Generate a cover for an existing book directory.",
    )
    parser.add_argument(
        "--chapter-covers-book",
        type=Path,
        default=None,
        help="Generate chapter covers for an existing book directory.",
    )
    parser.add_argument(
        "--chapter-cover-dir",
        default="chapter_covers",
        help="Directory name for storing generated chapter covers.",
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
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the Book Writer GUI server.",
    )
    parser.add_argument(
        "--gui-host",
        default="127.0.0.1",
        help="Host interface for the GUI server (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--gui-port",
        type=int,
        default=8080,
        help="Port for the GUI server (default: 8080).",
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
    default_module_path = CoverSettings().module_path

    if args.gui:
        from book_writer.server import run_server

        run_server(host=args.gui_host, port=args.gui_port)
        return 0

    client = LMStudioClient(
        base_url=args.base_url,
        model=args.model,
        timeout=args.timeout,
        author=args.author,
    )
    tts_settings = TTSSettings(
        enabled=args.tts,
        voice=args.tts_voice,
        language=args.tts_language,
        instruct=args.tts_instruct,
        model_path=args.tts_model_path,
        device_map=args.tts_device_map,
        dtype=args.tts_dtype,
        attn_implementation=args.tts_attn_implementation,
        rate=args.tts_rate,
        pitch=args.tts_pitch,
        audio_dirname=args.tts_audio_dir,
        overwrite_audio=args.tts_overwrite,
        book_only=args.tts_book_only,
    )
    video_settings = VideoSettings(
        enabled=args.video,
        background_video=args.background_video,
        video_dirname=args.video_dir,
        paragraph_images=_video_image_settings_from_args(args),
    )
    cover_settings = CoverSettings(
        enabled=args.cover,
        prompt=args.cover_prompt,
        negative_prompt=args.cover_negative_prompt,
        model_path=args.cover_model_path,
        module_path=args.cover_module_path or default_module_path,
        steps=args.cover_steps,
        guidance_scale=args.cover_guidance_scale,
        seed=args.cover_seed,
        width=args.cover_width,
        height=args.cover_height,
        output_name=args.cover_output_name,
        overwrite=args.cover_overwrite,
        command=parse_cover_command(args.cover_command),
    )
    if args.cover_book or args.chapter_covers_book:
        cover_settings = replace(cover_settings, enabled=True)
    tone_options = _tone_options()
    author_options = _author_options()
    if args.cover_book or args.chapter_covers_book:
        if args.cover_book:
            generate_book_cover_asset(
                output_dir=args.cover_book,
                cover_settings=cover_settings,
                client=client,
            )
        if args.chapter_covers_book:
            generate_chapter_cover_assets(
                output_dir=args.chapter_covers_book,
                cover_settings=cover_settings,
                chapter_cover_dir=args.chapter_cover_dir,
                client=client,
            )
        return 0
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
            cover_settings=cover_settings,
            tone=selected_tone,
            chapter_files=selected_chapters,
        )
        return 0
    outline_files = _outline_files(args.outlines_dir)
    if args.prompt:
        primary_action = _prompt_for_primary_action()
        if primary_action == "gui":
            from book_writer.server import run_server

            run_server(host=args.gui_host, port=args.gui_port)
            return 0
        if primary_action == "outline":
            questionary = _questionary()
            outline_prompt = questionary.text("Outline prompt:").ask() or ""
            if not outline_prompt.strip():
                parser.error("Outline prompt cannot be empty.")
            outline_name = questionary.text(
                "Outline filename:",
                default="outline.md",
            ).ask() or "outline.md"
            outlines_dir_value = questionary.text(
                "Outlines directory:",
                default=str(args.outlines_dir),
            ).ask()
            outlines_dir = Path(outlines_dir_value) if outlines_dir_value else args.outlines_dir
            selected_author = _prompt_for_author(
                outline_name, author_options, args.author
            )
            client.set_author(selected_author)
            revision_prompts = _prompt_for_outline_revisions()
            outline_path = write_outline_from_prompt(
                outlines_dir=outlines_dir,
                client=client,
                prompt=outline_prompt,
                outline_name=outline_name,
                revision_prompts=revision_prompts,
            )
            print(f"Saved outline to {outline_path}.")
            return 0
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
                        selected_chapters = _prompt_for_expand_only(
                            _book_chapter_files(book.path), args.expand_only
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
                        cover_settings=task_selection.cover_settings,
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
                        client=client,
                    )
                if task_selection.generate_cover:
                    generate_book_cover_asset(
                        output_dir=book.path,
                        cover_settings=task_selection.cover_settings,
                        client=client,
                    )
                if task_selection.generate_chapter_covers:
                    generate_chapter_cover_assets(
                        output_dir=book.path,
                        cover_settings=task_selection.cover_settings,
                        chapter_cover_dir=task_selection.chapter_cover_dir,
                        client=client,
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
            text_enabled, byline, tts_settings, video_settings, cover_settings = (
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
                    cover_settings=cover_settings,
                    byline=byline,
                    tone=args.tone,
                    resume_decider=lambda outline, output, progress: _prompt_for_resume(
                        output, progress
                    ),
                    outline_files=[info.path for info in selected_outlines],
                    tone_decider=lambda path: tone_map[path],
                    author_decider=lambda path: author_map[path],
                    log_prompts=True,
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
        (
            text_enabled,
            byline,
            tts_settings,
            video_settings,
            cover_settings,
        ) = _prompt_for_task_settings(args)
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
            cover_settings=cover_settings,
            book_title=book_title,
            byline=byline,
            tone=selected_tone,
            resume=resume,
            log_prompts=True,
            outline_hash=hashlib.sha256(
                args.outline.read_text(encoding="utf-8").encode("utf-8")
            ).hexdigest(),
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
                cover_settings=cover_settings,
                byline=args.byline,
                tone=args.tone,
                resume_decider=lambda outline, output, progress: _prompt_for_resume(
                    output, progress
                ),
                log_prompts=True,
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
        cover_settings=cover_settings,
        book_title=book_title,
        byline=args.byline,
        tone=args.tone,
        resume=resume,
        log_prompts=True,
        outline_hash=hashlib.sha256(
            args.outline.read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
