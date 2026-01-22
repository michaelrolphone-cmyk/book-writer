from __future__ import annotations

import asyncio
import json
import re
import subprocess
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
    overwrite_audio: bool = False
    book_only: bool = False


@dataclass(frozen=True)
class WordTiming:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class ParagraphTiming:
    text: str
    start: float
    end: float


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
AUDIO_EXTENSION = ".mp4"
EDGE_TTS_AUDIO_FORMAT = "audio-24khz-48kbitrate-mono-mp4"
TIMED_TEXT_SUFFIX = ".timed.json"


def sanitize_markdown_for_tts(markdown: str) -> str:
    cleaned = CODE_BLOCK_PATTERN.sub("", markdown)
    cleaned = unicodedata.normalize("NFKC", cleaned)
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
        if unicodedata.category(ch) not in {"Cc", "Cf", "Cn", "Co", "Cs", "So"}
        and ch != "\uFFFD"
        and ord(ch) <= 0xFFFF
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


def split_markdown_paragraphs(markdown: str) -> list[str]:
    paragraphs: list[str] = []
    for block in re.split(r"\n\s*\n", markdown.strip()):
        if not block.strip():
            continue
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        content_lines = [
            line for line in lines if not line.lstrip().startswith("#")
        ]
        if not content_lines:
            continue
        paragraph = sanitize_markdown_for_tts("\n".join(content_lines))
        paragraph = " ".join(paragraph.splitlines()).strip()
        if paragraph:
            paragraphs.append(paragraph)
    return paragraphs


def _concat_audio_files(parts: Iterable[Path], output_path: Path) -> None:
    with output_path.open("wb") as output:
        for part in parts:
            output.write(part.read_bytes())


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


def _format_vtt_timestamp(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours = milliseconds // 3_600_000
    minutes = (milliseconds % 3_600_000) // 60_000
    seconds_part = (milliseconds % 60_000) // 1000
    millis_part = milliseconds % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds_part:02d}.{millis_part:03d}"


def _write_paragraph_vtt(
    timings: list[ParagraphTiming], output_path: Path
) -> bool:
    if not timings:
        return False
    lines = ["WEBVTT", ""]
    for index, timing in enumerate(timings, start=1):
        if timing.end <= timing.start:
            continue
        lines.extend(
            [
                str(index),
                (
                    f"{_format_vtt_timestamp(timing.start)} --> "
                    f"{_format_vtt_timestamp(timing.end)}"
                ),
                timing.text,
                "",
            ]
        )
    if len(lines) <= 2:
        return False
    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return True


def _write_paragraph_timings_json(
    timings: list[ParagraphTiming], output_path: Path
) -> None:
    payload = {
        "paragraphs": [
            {"text": timing.text, "start": timing.start, "end": timing.end}
            for timing in timings
        ]
    }
    output_path.write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


def read_paragraph_timings(audio_path: Path) -> list[ParagraphTiming] | None:
    timing_path = audio_path.with_suffix(TIMED_TEXT_SUFFIX)
    if not timing_path.exists():
        return None
    try:
        payload = json.loads(timing_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    paragraphs = payload.get("paragraphs")
    if not isinstance(paragraphs, list):
        return None
    timings: list[ParagraphTiming] = []
    for entry in paragraphs:
        if not isinstance(entry, dict):
            continue
        text = str(entry.get("text", "")).strip()
        try:
            start = float(entry.get("start", 0))
            end = float(entry.get("end", 0))
        except (TypeError, ValueError):
            continue
        timings.append(ParagraphTiming(text=text, start=start, end=end))
    return timings or None


def _mux_audio_with_timed_text(audio_path: Path, subtitle_path: Path) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_output = Path(tmpdir) / audio_path.name
        command = [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-i",
            str(audio_path),
            "-i",
            str(subtitle_path),
            "-c",
            "copy",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            "language=eng",
            str(temp_output),
        ]
        try:
            subprocess.run(command, check=True)
        except FileNotFoundError as exc:
            raise TTSSynthesisError(
                "ffmpeg is required to embed timed text into mp4 audio."
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise TTSSynthesisError(
                "ffmpeg failed to embed timed text into mp4 audio."
            ) from exc
        temp_output.replace(audio_path)


def _build_paragraph_timings(
    paragraphs: list[str], word_timings: list[WordTiming]
) -> list[ParagraphTiming]:
    if not paragraphs or not word_timings:
        return []
    timings: list[ParagraphTiming] = []
    word_index = 0
    total_words = len(word_timings)
    for paragraph in paragraphs:
        words = re.findall(r"\S+", paragraph)
        if not words:
            continue
        if word_index >= total_words:
            break
        start_time = word_timings[word_index].start
        end_index = min(word_index + len(words) - 1, total_words - 1)
        end_time = word_timings[end_index].end
        timings.append(
            ParagraphTiming(text=paragraph, start=start_time, end=end_time)
        )
        word_index = end_index + 1
    return timings


def _synthesize_with_edge_tts(
    text: str,
    output_path: Path,
    settings: TTSSettings,
) -> list[WordTiming]:
    import edge_tts

    async def _save_with_retries(
        communicate_factory: Callable[[], edge_tts.Communicate],
        path: Path,
    ) -> list[WordTiming]:
        for attempt in range(MAX_TTS_RETRIES + 1):
            communicate = communicate_factory()
            try:
                word_timings: list[WordTiming] = []
                with path.open("wb") as audio_file:
                    async for chunk in communicate.stream():
                        if chunk.get("type") == "audio":
                            audio_file.write(chunk.get("data", b""))
                        elif chunk.get("type") == "WordBoundary":
                            offset = float(chunk.get("offset", 0))
                            duration = float(chunk.get("duration", 0))
                            text_value = str(chunk.get("text", ""))
                            start = offset / 10_000_000
                            end = (offset + duration) / 10_000_000
                            word_timings.append(
                                WordTiming(text=text_value, start=start, end=end)
                            )
                return word_timings
            except edge_tts.exceptions.NoAudioReceived as error:
                if attempt >= MAX_TTS_RETRIES:
                    raise TTSSynthesisError(
                        "No audio was received from Edge TTS after retries. "
                        "Verify the voice, rate, pitch, and network connectivity."
                    ) from error

    async def _save_text(text_part: str, path: Path) -> list[WordTiming]:
        return await _save_with_retries(
            lambda: edge_tts.Communicate(
                text_part,
                voice=settings.voice,
                rate=settings.rate,
                pitch=settings.pitch,
                output_format=EDGE_TTS_AUDIO_FORMAT,
            ),
            path,
        )

    chunks = split_text_for_tts(text, MAX_TTS_CHARS)
    if not chunks:
        return []
    if len(chunks) == 1:
        async def _run() -> None:
            try:
                return await _save_text(chunks[0], output_path)
            except Exception as error:
                raise error

        try:
            return asyncio.run(_run())
        except TTSSynthesisError:
            if output_path.exists():
                output_path.unlink()
            raise

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            part_paths: list[Path] = []
            chunk_error: TTSSynthesisError | None = None
            full_word_timings: list[WordTiming] = []
            time_offset = 0.0
            for index, chunk in enumerate(chunks, start=1):
                part_path = Path(tmpdir) / f"part-{index:03d}.mp4"

                async def _run_part(
                    text_part: str, path: Path
                ) -> list[WordTiming]:
                    try:
                        return await _save_text(text_part, path)
                    except Exception as error:
                        raise error

                try:
                    chunk_timings = asyncio.run(_run_part(chunk, part_path))
                except TTSSynthesisError as error:
                    chunk_error = error
                    break
                except Exception as error:
                    chunk_error = TTSSynthesisError(str(error))
                    break
                if chunk_timings:
                    full_word_timings.extend(
                        [
                            WordTiming(
                                text=timing.text,
                                start=timing.start + time_offset,
                                end=timing.end + time_offset,
                            )
                            for timing in chunk_timings
                        ]
                    )
                    chunk_duration = chunk_timings[-1].end
                else:
                    duration = _probe_audio_duration(part_path)
                    if duration is None:
                        raise TTSSynthesisError(
                            "ffprobe is required to align timing for long TTS audio."
                        )
                    chunk_duration = duration
                time_offset += chunk_duration
                part_paths.append(part_path)

            if chunk_error is not None:
                raise chunk_error
            if part_paths:
                if len(part_paths) == 1:
                    part_paths[0].replace(output_path)
                else:
                    concat_manifest = Path(tmpdir) / "concat.txt"
                    concat_manifest.write_text(
                        "\n".join(
                            f"file '{part.as_posix()}'" for part in part_paths
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    command = [
                        "ffmpeg",
                        "-nostdin",
                        "-y",
                        "-f",
                        "concat",
                        "-safe",
                        "0",
                        "-i",
                        str(concat_manifest),
                        "-c",
                        "copy",
                        str(output_path),
                    ]
                    try:
                        subprocess.run(command, check=True)
                    except FileNotFoundError as exc:
                        raise TTSSynthesisError(
                            "ffmpeg is required to concatenate mp4 audio chunks."
                        ) from exc
                    except subprocess.CalledProcessError as exc:
                        raise TTSSynthesisError(
                            "ffmpeg failed to concatenate mp4 audio chunks."
                        ) from exc
                return full_word_timings
            return []
    except TTSSynthesisError as error:
        async def _fallback() -> None:
            try:
                return await _save_text(text, output_path)
            except Exception as fallback_error:
                raise fallback_error

        try:
            return asyncio.run(_fallback())
        except TTSSynthesisError:
            if output_path.exists():
                output_path.unlink()
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
    output_path = output_dir / f"{chapter_path.stem}{AUDIO_EXTENSION}"
    try:
        word_timings = _synthesize_with_edge_tts(text, output_path, settings)
    except TTSSynthesisError as error:
        if output_path.exists():
            output_path.unlink()
        if verbose:
            print(f"[tts] Skipped {output_path.name}: {error}")
        return None
    if word_timings:
        paragraphs = split_markdown_paragraphs(chapter_path.read_text(encoding="utf-8"))
        paragraph_timings = _build_paragraph_timings(paragraphs, word_timings)
        if paragraph_timings:
            timing_path = output_path.with_suffix(TIMED_TEXT_SUFFIX)
            _write_paragraph_timings_json(paragraph_timings, timing_path)
            subtitle_path = output_path.with_suffix(".vtt")
            if _write_paragraph_vtt(paragraph_timings, subtitle_path):
                _mux_audio_with_timed_text(output_path, subtitle_path)
    if verbose:
        print(f"[tts] Wrote {output_path.name}.")
    return output_path


def synthesize_text_audio(
    text: str,
    output_path: Path,
    settings: TTSSettings,
    verbose: bool = False,
    raise_on_error: bool = False,
) -> Path | None:
    if not settings.enabled:
        return None

    cleaned = sanitize_markdown_for_tts(text)
    if not cleaned:
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        word_timings = _synthesize_with_edge_tts(cleaned, output_path, settings)
    except TTSSynthesisError as error:
        if output_path.exists():
            output_path.unlink()
        if raise_on_error:
            raise
        if verbose:
            print(f"[tts] Skipped {output_path.name}: {error}")
        return None
    if word_timings:
        paragraphs = split_markdown_paragraphs(text)
        paragraph_timings = _build_paragraph_timings(paragraphs, word_timings)
        if paragraph_timings:
            timing_path = output_path.with_suffix(TIMED_TEXT_SUFFIX)
            _write_paragraph_timings_json(paragraph_timings, timing_path)
            subtitle_path = output_path.with_suffix(".vtt")
            if _write_paragraph_vtt(paragraph_timings, subtitle_path):
                _mux_audio_with_timed_text(output_path, subtitle_path)
    if verbose:
        print(f"[tts] Wrote {output_path.name}.")
    return output_path
