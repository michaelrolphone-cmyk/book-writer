from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VideoSettings:
    enabled: bool = False
    background_video: Path | None = None
    video_dirname: str = "video"


def _build_ffmpeg_command(
    background_video: Path,
    audio_path: Path,
    output_path: Path,
) -> list[str]:
    return [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(background_video),
        "-i",
        str(audio_path),
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
) -> Path | None:
    if not settings.enabled:
        return None
    if not audio_path.exists():
        return None
    background_video = _require_background_video(settings)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{audio_path.stem}.mp4"
    command = _build_ffmpeg_command(background_video, audio_path, output_path)
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
