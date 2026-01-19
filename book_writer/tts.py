from __future__ import annotations

import asyncio
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


class TTSSynthesisError(RuntimeError):
    """Raised when TTS synthesis fails but should not crash the workflow."""


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
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
MAX_TTS_CHARS = 3000
MAX_TTS_RETRIES = 2


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

    cleaned_text = "\n".join(collapsed).strip()
    return "".join(
        ch
        for ch in cleaned_text
        if unicodedata.category(ch) not in {"So", "Cs"} and ord(ch) <= 0xFFFF
    )


def split_text_for_tts(text: str, max_chars: int = MAX_TTS_CHARS) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [cleaned]

    chunks: list[str] = []
    buffer: list[str] = []
    buffer_len = 0
    for paragraph in cleaned.splitlines():
        if not paragraph.strip():
            if buffer:
                chunks.append(" ".join(buffer).strip())
                buffer = []
                buffer_len = 0
            continue
        sentences = SENTENCE_SPLIT_PATTERN.split(paragraph.strip())
        for sentence in sentences:
            if not sentence:
                continue
            sentence = sentence.strip()
            sentence_len = len(sentence)
            if sentence_len > max_chars:
                if buffer:
                    chunks.append(" ".join(buffer).strip())
                    buffer = []
                    buffer_len = 0
                for idx in range(0, sentence_len, max_chars):
                    chunks.append(sentence[idx : idx + max_chars].strip())
                continue
            if buffer_len + sentence_len + 1 > max_chars and buffer:
                chunks.append(" ".join(buffer).strip())
                buffer = []
                buffer_len = 0
            buffer.append(sentence)
            buffer_len += sentence_len + 1
        if buffer:
            chunks.append(" ".join(buffer).strip())
            buffer = []
            buffer_len = 0

    if buffer:
        chunks.append(" ".join(buffer).strip())
    return [chunk for chunk in chunks if chunk]


def _concat_audio_files(parts: Iterable[Path], output_path: Path) -> None:
    with output_path.open("wb") as output:
        for part in parts:
            output.write(part.read_bytes())


def _synthesize_with_edge_tts(
    text: str,
    output_path: Path,
    settings: TTSSettings,
) -> None:
    import edge_tts

    async def _save_with_retries(
        communicate_factory: Callable[[], edge_tts.Communicate],
        path: Path,
    ) -> None:
        for attempt in range(MAX_TTS_RETRIES + 1):
            communicate = communicate_factory()
            try:
                await communicate.save(str(path))
                return
            except edge_tts.exceptions.NoAudioReceived as error:
                if attempt >= MAX_TTS_RETRIES:
                    raise TTSSynthesisError(
                        "No audio was received from Edge TTS after retries. "
                        "Verify the voice, rate, pitch, and network connectivity."
                    ) from error

    async def _save_text(text_part: str, path: Path) -> None:
        await _save_with_retries(
            lambda: edge_tts.Communicate(
                text_part,
                voice=settings.voice,
                rate=settings.rate,
                pitch=settings.pitch,
            ),
            path,
        )

    chunks = split_text_for_tts(text, MAX_TTS_CHARS)
    if not chunks:
        return
    if len(chunks) == 1:
        async def _run() -> None:
            try:
                await _save_text(chunks[0], output_path)
            except Exception as error:
                raise error

        asyncio.run(_run())
        return

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            part_paths = []
            for index, chunk in enumerate(chunks, start=1):
                part_path = Path(tmpdir) / f"part-{index:03d}.mp3"

                async def _run_part(text_part: str, path: Path) -> None:
                    try:
                        await _save_text(text_part, path)
                    except Exception as error:
                        raise error

                asyncio.run(_run_part(chunk, part_path))
                part_paths.append(part_path)

            _concat_audio_files(part_paths, output_path)
    except TTSSynthesisError as error:
        async def _fallback() -> None:
            try:
                await _save_text(text, output_path)
            except Exception as fallback_error:
                raise fallback_error

        try:
            asyncio.run(_fallback())
        except TTSSynthesisError:
            raise error


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
    try:
        _synthesize_with_edge_tts(text, output_path, settings)
    except TTSSynthesisError as error:
        if output_path.exists():
            output_path.unlink()
        if verbose:
            print(f"[tts] Skipped {output_path.name}: {error}")
        return None
    if verbose:
        print(f"[tts] Wrote {output_path.name}.")
    return output_path


def synthesize_text_audio(
    text: str,
    output_path: Path,
    settings: TTSSettings,
    verbose: bool = False,
) -> Path | None:
    if not settings.enabled:
        return None

    cleaned = sanitize_markdown_for_tts(text)
    if not cleaned:
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _synthesize_with_edge_tts(cleaned, output_path, settings)
    except TTSSynthesisError as error:
        if output_path.exists():
            output_path.unlink()
        if verbose:
            print(f"[tts] Skipped {output_path.name}: {error}")
        return None
    if verbose:
        print(f"[tts] Wrote {output_path.name}.")
    return output_path
