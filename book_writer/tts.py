from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TTSSettings:
    enabled: bool = False
    voice: str = "en-US-JennyNeural"
    rate: str = "+0%"
    pitch: str = "+0Hz"
    audio_dirname: str = "audio"


CODE_BLOCK_PATTERN = re.compile(r"```.*?```", re.DOTALL)
LINK_PATTERN = re.compile(r"\[([^\]]+)\]\([^)]+\)")
INLINE_CODE_PATTERN = re.compile(r"`([^`]+)`")
BOLD_PATTERN = re.compile(r"\*\*([^*]+)\*\*")
ITALIC_PATTERN = re.compile(r"\*([^*]+)\*")
UNDERSCORE_PATTERN = re.compile(r"_([^_]+)_")
NUMBERED_LIST_PATTERN = re.compile(r"^\d+\.\s+")
BULLET_LIST_PATTERN = re.compile(r"^[-*+]\s+")
HEADING_PATTERN = re.compile(r"^#+\s*")


def sanitize_markdown_for_tts(markdown: str) -> str:
    cleaned = CODE_BLOCK_PATTERN.sub("", markdown)
    output_lines: list[str] = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped:
            output_lines.append("")
            continue
        line_text = HEADING_PATTERN.sub("", stripped)
        line_text = NUMBERED_LIST_PATTERN.sub("", line_text)
        line_text = BULLET_LIST_PATTERN.sub("", line_text)
        line_text = LINK_PATTERN.sub(r"\1", line_text)
        line_text = INLINE_CODE_PATTERN.sub(r"\1", line_text)
        line_text = BOLD_PATTERN.sub(r"\1", line_text)
        line_text = ITALIC_PATTERN.sub(r"\1", line_text)
        line_text = UNDERSCORE_PATTERN.sub(r"\1", line_text)
        output_lines.append(line_text)

    collapsed: list[str] = []
    previous_blank = False
    for line in output_lines:
        if not line.strip():
            if not previous_blank:
                collapsed.append("")
            previous_blank = True
        else:
            collapsed.append(line)
            previous_blank = False

    return "\n".join(collapsed).strip()


def _synthesize_with_edge_tts(
    text: str,
    output_path: Path,
    settings: TTSSettings,
) -> None:
    import edge_tts

    async def _run() -> None:
        communicate = edge_tts.Communicate(
            text, voice=settings.voice, rate=settings.rate, pitch=settings.pitch
        )
        await communicate.save(str(output_path))

    asyncio.run(_run())


def synthesize_chapter_audio(
    chapter_path: Path,
    output_dir: Path,
    settings: TTSSettings,
    verbose: bool = False,
) -> Path | None:
    if not settings.enabled:
        return None

    text = sanitize_markdown_for_tts(chapter_path.read_text(encoding="utf-8"))
    if not text:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{chapter_path.stem}.mp3"
    _synthesize_with_edge_tts(text, output_path, settings)
    if verbose:
        print(f"[tts] Wrote {output_path.name}.")
    return output_path
