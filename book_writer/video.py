from __future__ import annotations

import os
import re
import shlex
import subprocess
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path


@dataclass(frozen=True)
class VideoSettings:
    enabled: bool = False
    background_video: Path | None = None
    video_dirname: str = "video"
    overlay_text: bool = True
    paragraph_images: "ParagraphImageSettings" = field(
        default_factory=lambda: ParagraphImageSettings()
    )


def _default_image_module_path() -> Path:
    project_root = Path(__file__).resolve().parents[1]
    return (project_root / ".." / "ml-stable-diffusion").resolve()


@dataclass(frozen=True)
class ParagraphImageSettings:
    enabled: bool = False
    image_dirname: str = "video_images"
    negative_prompt: str | None = None
    model_path: Path | None = None
    module_path: Path | None = field(default_factory=_default_image_module_path)
    steps: int = 30
    guidance_scale: float = 7.5
    seed: int | None = None
    width: int = 1280
    height: int = 720
    overwrite: bool = False
    command: list[str] | None = None


DEFAULT_IMAGE_COMMAND = [
    "swift",
    "run",
    "StableDiffusionSample",
    "{prompt}",
    "{negative_prompt_flag}",
    "{negative_prompt}",
    "--resource-path",
    "{model_path}",
    "{seed_flag}",
    "{seed}",
    "--output-path",
    "{output_dir}",
]

DEFAULT_IMAGE_NEGATIVE_PROMPT = (
    "text, letters, typography, watermark, logo, signature"
)
DEFAULT_IMAGE_GUIDANCE = (
    "Cinematic scene illustration. "
    "No text, no typography, no letters, no watermark, no logo."
)


def parse_video_image_command(command: str | None) -> list[str] | None:
    if not command:
        return None
    return shlex.split(command)


def _build_ffmpeg_command(
    background_video: Path,
    audio_path: Path,
    output_path: Path,
    subtitle_path: Path | None = None,
) -> list[str]:
    command = [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(background_video),
        "-i",
        str(audio_path),
    ]
    if subtitle_path is not None:
        quoted_subtitle_path = _quote_filter_value(str(subtitle_path))
        subtitle_filter = (
            "subtitles="
            f"filename={quoted_subtitle_path}"
            ":force_style="
            f"{_quote_filter_value('Fontsize=48,Alignment=2,Outline=2,Shadow=1')}"
        )
        command.extend(
            [
                "-vf",
                subtitle_filter,
            ]
        )
    command.extend(
        [
            "-shortest",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    return command


def _build_ffmpeg_image_command(
    concat_path: Path,
    audio_path: Path,
    output_path: Path,
    width: int,
    height: int,
) -> list[str]:
    scale_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    )
    return [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
        "-i",
        str(audio_path),
        "-vf",
        scale_filter,
        "-shortest",
        "-vsync",
        "vfr",
        "-pix_fmt",
        "yuv420p",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]


def _render_image_command(
    template: list[str],
    *,
    prompt: str,
    negative_prompt: str | None,
    model_path: Path | None,
    seed: int | None,
    steps: int,
    guidance_scale: float,
    width: int,
    height: int,
    output_path: Path,
    output_dir: Path,
) -> list[str]:
    values = {
        "prompt": prompt,
        "negative_prompt": negative_prompt or "",
        "negative_prompt_flag": "--negative-prompt" if negative_prompt else "",
        "model_path": str(model_path) if model_path else "",
        "model_path_flag": "--model-path" if model_path else "",
        "seed": str(seed) if seed is not None else "",
        "seed_flag": "--seed" if seed is not None else "",
        "steps": str(steps),
        "guidance_scale": str(guidance_scale),
        "width": str(width),
        "height": str(height),
        "output_path": str(output_path),
        "output_dir": str(output_dir),
    }
    rendered: list[str] = []
    for token in template:
        formatted = token.format(**values)
        if not formatted:
            continue
        rendered.append(formatted)
    return rendered


def _resolve_image_command(
    settings: ParagraphImageSettings,
    prompt: str,
    output_path: Path,
    output_dir: Path,
    *,
    model_path: Path | None = None,
) -> list[str]:
    template = settings.command or DEFAULT_IMAGE_COMMAND
    return _render_image_command(
        template,
        prompt=prompt,
        negative_prompt=settings.negative_prompt,
        model_path=model_path if model_path is not None else settings.model_path,
        seed=settings.seed,
        steps=settings.steps,
        guidance_scale=settings.guidance_scale,
        width=settings.width,
        height=settings.height,
        output_path=output_path,
        output_dir=output_dir,
    )


def _quote_filter_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _build_image_env(module_path: Path | None) -> dict[str, str]:
    env = os.environ.copy()
    if module_path:
        module_value = str(module_path)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{module_value}{os.pathsep}{existing}"
            if existing
            else module_value
        )
    return env


def _infer_default_image_model_path(module_path: Path | None) -> Path | None:
    if not module_path:
        return None
    candidate = (
        module_path
        / ".."
        / "coreml-stable-diffusion-v1-4"
        / "original"
        / "compiled"
    ).resolve()
    if candidate.exists():
        return candidate
    return None


def _probe_audio_duration(audio_path: Path) -> float | None:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=nokey=1:noprint_wrappers=1",
        str(audio_path),
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def _ensure_image_prompt(prompt: str) -> str:
    prompt_value = prompt.strip()
    prompt_lower = prompt_value.lower()
    if "no text" in prompt_lower and (
        "no typography" in prompt_lower or "no letters" in prompt_lower
    ):
        return prompt_value
    return f"{prompt_value} {DEFAULT_IMAGE_GUIDANCE}".strip()


def _merge_image_negative_prompt(negative_prompt: str | None) -> str:
    if negative_prompt:
        negative_value = negative_prompt.strip()
        if DEFAULT_IMAGE_NEGATIVE_PROMPT.lower() in negative_value.lower():
            return negative_value
        return f"{negative_value}, {DEFAULT_IMAGE_NEGATIVE_PROMPT}"
    return DEFAULT_IMAGE_NEGATIVE_PROMPT


def _ffmpeg_supports_filter(filter_name: str) -> bool:
    command = [
        "ffmpeg",
        "-filters",
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        message = (
            "ffmpeg is required to generate chapter videos but was not found on your "
            "PATH. Install ffmpeg (https://ffmpeg.org/download.html) or ensure it is "
            "available in your PATH."
        )
        raise RuntimeError(message) from exc
    except subprocess.CalledProcessError:
        return False
    return re.search(rf"\\b{re.escape(filter_name)}\\b", result.stdout) is not None


def _format_srt_timestamp(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours = milliseconds // 3_600_000
    minutes = (milliseconds % 3_600_000) // 60_000
    seconds_part = (milliseconds % 60_000) // 1000
    millis_part = milliseconds % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds_part:02d},{millis_part:03d}"


def _write_word_captions(
    text: str, duration_seconds: float, output_path: Path
) -> bool:
    words = re.findall(r"\S+", text)
    if not words:
        return False
    if duration_seconds <= 0:
        return False
    per_word = duration_seconds / len(words)
    lines: list[str] = []
    for index, word in enumerate(words, start=1):
        start = per_word * (index - 1)
        end = min(per_word * index, duration_seconds)
        if end <= start:
            continue
        lines.extend(
            [
                str(index),
                f"{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}",
                word,
                "",
            ]
        )
    if not lines:
        return False
    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return True


def _write_concat_manifest(
    image_paths: list[Path], durations: list[float], output_path: Path
) -> None:
    if len(image_paths) != len(durations):
        raise ValueError("Image paths and durations must be the same length.")
    lines: list[str] = []
    for path, duration in zip(image_paths, durations):
        lines.append(f"file '{path.as_posix()}'")
        lines.append(f"duration {duration:.3f}")
    if image_paths:
        lines.append(f"file '{image_paths[-1].as_posix()}'")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _require_background_video(settings: VideoSettings) -> Path:
    if settings.background_video is None:
        raise ValueError("Background video must be provided when video is enabled.")
    if not settings.background_video.exists():
        raise FileNotFoundError(
            f"Background video not found at {settings.background_video}."
        )
    return settings.background_video


def generate_paragraph_image(
    prompt: str,
    output_path: Path,
    settings: ParagraphImageSettings,
    verbose: bool = False,
) -> Path | None:
    if not settings.enabled:
        return None
    output_path = output_path.resolve()
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not settings.overwrite:
        return output_path
    if settings.overwrite and output_path.exists():
        output_path.unlink()
    existing_paths = {path.resolve() for path in output_dir.rglob("*.png")}
    settings_to_use = settings
    if settings.command is None and not settings.model_path:
        inferred_path = _infer_default_image_model_path(settings.module_path)
        if inferred_path:
            settings_to_use = replace(settings_to_use, model_path=inferred_path)
        else:
            raise ValueError(
                "Paragraph image generation requires --video-image-model-path "
                "when using the default swift command. Place the Core ML resources "
                "at ../coreml-stable-diffusion-v1-4/original/compiled or pass "
                "--video-image-model-path explicitly."
            )
    prompt_value = _ensure_image_prompt(prompt)
    negative_prompt = _merge_image_negative_prompt(settings_to_use.negative_prompt)
    command = _resolve_image_command(
        replace(settings_to_use, negative_prompt=negative_prompt),
        prompt_value,
        output_path,
        output_dir,
    )
    try:
        subprocess.run(
            command,
            check=True,
            env=_build_image_env(settings_to_use.module_path),
            cwd=str(settings_to_use.module_path)
            if settings_to_use.module_path
            else None,
        )
    except FileNotFoundError as exc:
        message = (
            "Paragraph image generation command not found. "
            "Ensure it is installed and available in your PATH or set "
            "--video-image-command."
        )
        raise RuntimeError(message) from exc
    if output_path.exists():
        if verbose:
            print(f"[video] Wrote {output_path.name}.")
        return output_path
    candidates = [
        path
        for path in output_dir.rglob("*.png")
        if path.resolve() not in existing_paths
    ]
    if not candidates:
        candidates = list(output_dir.rglob("*.png"))
    candidates = sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)
    if candidates:
        candidates[0].replace(output_path)
        if verbose:
            print(f"[video] Wrote {output_path.name}.")
        return output_path
    return None


def synthesize_chapter_video(
    audio_path: Path,
    output_dir: Path,
    settings: VideoSettings,
    verbose: bool = False,
    text: str | None = None,
) -> Path | None:
    from book_writer.tts import sanitize_markdown_for_tts

    if not settings.enabled:
        return None
    if not audio_path.exists():
        return None
    background_video = _require_background_video(settings)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{audio_path.stem}.mp4"
    subtitle_path: Path | None = None
    if settings.overlay_text and text:
        cleaned_text = sanitize_markdown_for_tts(text)
        if cleaned_text:
            subtitles_supported = _ffmpeg_supports_filter("subtitles")
            duration = _probe_audio_duration(audio_path)
            if duration and subtitles_supported:
                with tempfile.TemporaryDirectory() as tmpdir:
                    subtitle_path = Path(tmpdir) / "captions.srt"
                    if _write_word_captions(
                        cleaned_text, duration, subtitle_path
                    ):
                        command = _build_ffmpeg_command(
                            background_video,
                            audio_path,
                            output_path,
                            subtitle_path,
                        )
                        try:
                            subprocess.run(command, check=True)
                        except FileNotFoundError as exc:
                            message = (
                                "ffmpeg is required to generate chapter videos but "
                                "was not found on your PATH. Install ffmpeg "
                                "(https://ffmpeg.org/download.html) or ensure it is "
                                "available in your PATH."
                            )
                            raise RuntimeError(message) from exc
                        if verbose:
                            print(f"[video] Wrote {output_path.name}.")
                        return output_path
            if verbose and not subtitles_supported:
                print("[video] Skipping subtitle overlay; ffmpeg subtitles filter not available.")
            subtitle_path = None

    command = _build_ffmpeg_command(
        background_video,
        audio_path,
        output_path,
        subtitle_path,
    )
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        message = (
            "ffmpeg is required to generate chapter videos but was not found on your "
            "PATH. Install ffmpeg (https://ffmpeg.org/download.html) or ensure it is "
            "available in your PATH."
        )
        raise RuntimeError(message) from exc
    if verbose:
        print(f"[video] Wrote {output_path.name}.")
    return output_path


def synthesize_chapter_video_from_images(
    audio_path: Path,
    output_dir: Path,
    image_paths: list[Path],
    durations: list[float],
    settings: VideoSettings,
    verbose: bool = False,
) -> Path | None:
    if not settings.enabled:
        return None
    if not audio_path.exists():
        return None
    if not image_paths:
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{audio_path.stem}.mp4"
    with tempfile.TemporaryDirectory() as tmpdir:
        concat_path = Path(tmpdir) / "images.txt"
        _write_concat_manifest(image_paths, durations, concat_path)
        image_settings = settings.paragraph_images
        command = _build_ffmpeg_image_command(
            concat_path,
            audio_path,
            output_path,
            image_settings.width,
            image_settings.height,
        )
        try:
            subprocess.run(command, check=True)
        except FileNotFoundError as exc:
            message = (
                "ffmpeg is required to generate chapter videos but was not found on "
                "your PATH. Install ffmpeg (https://ffmpeg.org/download.html) or "
                "ensure it is available in your PATH."
            )
            raise RuntimeError(message) from exc
    if verbose:
        print(f"[video] Wrote {output_path.name}.")
    return output_path
