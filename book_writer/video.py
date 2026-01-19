from __future__ import annotations

import subprocess
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VideoSettings:
    enabled: bool = False
    background_video: Path | None = None
    video_dirname: str = "video"
    overlay_text: bool = True


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


def _quote_filter_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


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


def _require_background_video(settings: VideoSettings) -> Path:
    if settings.background_video is None:
        raise ValueError("Background video must be provided when video is enabled.")
    if not settings.background_video.exists():
        raise FileNotFoundError(
            f"Background video not found at {settings.background_video}."
        )
    return settings.background_video


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
            duration = _probe_audio_duration(audio_path)
            if duration:
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
