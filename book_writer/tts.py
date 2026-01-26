from __future__ import annotations

import textwrap
import functools
import subprocess
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


class TTSSynthesisError(RuntimeError):
    """Raised when TTS synthesis fails but should not crash the workflow."""


DEFAULT_QWEN3_MODEL_PATH = (
    Path(__file__).resolve().parents[1].parent
    / "audio"
    / "models"
    / "Qwen3-TTS-12Hz-1.7B-CustomVoice"
)


@dataclass(frozen=True)
class TTSSettings:
    enabled: bool = False
    voice: str = "Ryan"
    language: str = "English"
    instruct: str | None = None
    model_path: str = str(DEFAULT_QWEN3_MODEL_PATH)
    device_map: str = "auto"
    dtype: str = "float16"
    attn_implementation: str = "sdpa"
    rate: str = "+0%"
    pitch: str = "+0Hz"
    audio_dirname: str = "audio"
    overwrite_audio: bool = False
    book_only: bool = False
    max_tts_chars: int = 900
    keep_model_loaded: bool = True


CODE_BLOCK_PATTERN = re.compile(r"```.*?```", re.DOTALL)
FENCED_CODE_PATTERN = re.compile(r"(```|~~~).*?\1", re.DOTALL)
HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
LINK_PATTERN = re.compile(r"\[([^\]]+)\]\([^)]+\)")
INLINE_CODE_PATTERN = re.compile(r"`([^`]+)`")
BOLD_PATTERN = re.compile(r"\*\*([^*]+)\*\*")
BOLD_UNDERSCORE_PATTERN = re.compile(r"__([^_]+)__")
ITALIC_PATTERN = re.compile(r"\*([^*]+)\*")
UNDERSCORE_PATTERN = re.compile(r"_([^_]+)_")
STRIKETHROUGH_PATTERN = re.compile(r"~~([^~]+)~~")
NUMBERED_LIST_PATTERN = re.compile(r"^\d+\.\s+")
BULLET_LIST_PATTERN = re.compile(r"^[-*+]\s+")
BLOCKQUOTE_PATTERN = re.compile(r"^>+\s*")
HEADING_PATTERN = re.compile(r"^#+\s*")
HORIZONTAL_RULE_PATTERN = re.compile(r"^(-{3,}|\*{3,}|_{3,})\s*$")
REFERENCE_LINK_PATTERN = re.compile(r"^\[[^\]]+\]:\s+\S+")
TABLE_DIVIDER_PATTERN = re.compile(r"^\s*\|?\s*(:?-{3,}:?\s*\|)+\s*$")
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
PARAGRAPH_SPLIT_PATTERN = re.compile(r"\n\s*\n+")
MAX_TTS_CHARS = 3000


def _wrap_on_words(text: str, width: int) -> list[str]:
    parts = textwrap.wrap(
        text,
        width=width,
        break_long_words=False,   # critical: don't split words
        break_on_hyphens=False,
    )
    if parts:
        return [p.strip() for p in parts if p.strip()]

    # Fallback: if the string contains a single token longer than width,
    # textwrap can return []. In that case, do a safe-ish fallback split.
    return [text[i:i+width].strip() for i in range(0, len(text), width) if text[i:i+width].strip()]

def sanitize_markdown_for_tts(markdown: str) -> str:
    cleaned = CODE_BLOCK_PATTERN.sub("", markdown)
    cleaned = FENCED_CODE_PATTERN.sub("", cleaned)
    cleaned = HTML_COMMENT_PATTERN.sub("", cleaned)
    cleaned = unicodedata.normalize("NFKC", cleaned)
    output_lines: list[str] = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped:
            output_lines.append("")
            continue
        if stripped.startswith("```") or stripped.startswith("~~~"):
            continue
        if HORIZONTAL_RULE_PATTERN.match(stripped):
            output_lines.append("")
            continue
        if TABLE_DIVIDER_PATTERN.match(stripped) or (
            set(stripped) <= {"|", "-", " ", ":"} and "-" in stripped
        ):
            continue
        if REFERENCE_LINK_PATTERN.match(stripped):
            continue
        line_text = HEADING_PATTERN.sub("", stripped)
        line_text = NUMBERED_LIST_PATTERN.sub("", line_text)
        line_text = BULLET_LIST_PATTERN.sub("", line_text)
        line_text = BLOCKQUOTE_PATTERN.sub("", line_text)
        line_text = IMAGE_PATTERN.sub(r"\1", line_text)
        line_text = LINK_PATTERN.sub(r"\1", line_text)
        line_text = INLINE_CODE_PATTERN.sub(r"\1", line_text)
        line_text = BOLD_PATTERN.sub(r"\1", line_text)
        line_text = BOLD_UNDERSCORE_PATTERN.sub(r"\1", line_text)
        line_text = ITALIC_PATTERN.sub(r"\1", line_text)
        line_text = UNDERSCORE_PATTERN.sub(r"\1", line_text)
        line_text = STRIKETHROUGH_PATTERN.sub(r"\1", line_text)
        line_text = HTML_TAG_PATTERN.sub("", line_text)
        line_text = line_text.replace("|", " ")
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
    cleaned_text = " ".join(cleaned_text.split())
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
    paragraph_texts = [
        " ".join(line.strip() for line in paragraph.splitlines() if line.strip())
        for paragraph in PARAGRAPH_SPLIT_PATTERN.split(cleaned)
        if paragraph.strip()
    ]
    if not paragraph_texts:
        return []
    normalized_text = "\n\n".join(paragraph_texts)
    if len(normalized_text) <= max_chars:
        return [normalized_text]

    chunks: list[str] = []
    buffer: list[str] = []
    buffer_len = 0
    for paragraph_text in paragraph_texts:
        if not paragraph_text:
            if buffer:
                chunks.append(" ".join(buffer).strip())
                buffer = []
                buffer_len = 0
            continue
        sentences = SENTENCE_SPLIT_PATTERN.split(paragraph_text)
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
                chunks.extend(_wrap_on_words(sentence, max_chars))
                continue
                ## for idx in range(0, sentence_len, max_chars):
                ##     chunks.append(sentence[idx : idx + max_chars].strip())
                ## continue
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


def _resolve_model_path(settings: TTSSettings) -> Path:
    model_path = Path(settings.model_path or DEFAULT_QWEN3_MODEL_PATH)
    model_path = model_path.expanduser()
    if not model_path.exists():
        raise TTSSynthesisError(
            "Qwen3 model path not found. Update tts_settings.model_path "
            f"or --tts-model-path (missing: {model_path})."
        )
    return model_path


@functools.lru_cache(maxsize=2)
def _load_qwen3_model(
    model_path: str,
    dtype: str,
    attn_implementation: str,
    device_map: str,
):
    import torch
    from qwen_tts import Qwen3TTSModel

    dtype_value = getattr(torch, dtype, None)
    if dtype_value is None:
        raise TTSSynthesisError(f"Unsupported torch dtype '{dtype}'.")
    return Qwen3TTSModel.from_pretrained(
        model_path,
        dtype=dtype_value,
        attn_implementation=attn_implementation,
        device_map=device_map,
    )


def release_qwen3_model_cache() -> None:
    _load_qwen3_model.cache_clear()


def _run_ffmpeg(wav_path: Path, output_path: Path) -> None:
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(wav_path),
                "-codec:a",
                "libmp3lame",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as error:
        raise TTSSynthesisError(
            "ffmpeg is required to convert Qwen3 audio to MP3. "
            "Install ffmpeg and try again."
        ) from error
    if result.returncode != 0:
        raise TTSSynthesisError(
            "ffmpeg failed to convert the audio to MP3. "
            f"stderr: {result.stderr.strip()}"
        )

def _write_wav_streaming(
    chunk_iter,
    wav_path: Path,
) -> int:
    """
    Writes PCM data incrementally to a WAV on disk.
    Returns the sample rate.
    """
    import numpy as np
    import soundfile as sf

    sample_rate: int | None = None
    wav_file: sf.SoundFile | None = None

    try:
        for chunk_waveform, sr in chunk_iter:
            if sample_rate is None:
                sample_rate = sr
                # Mono output assumed; adjust channels if your model returns stereo
                wav_file = sf.SoundFile(
                    str(wav_path),
                    mode="w",
                    samplerate=sample_rate,
                    channels=1,
                    subtype="FLOAT",
                )
            elif sr != sample_rate:
                raise TTSSynthesisError("Qwen3 returned mismatched sample rates.")

            # Ensure we write a numpy float32/float64 array (not Python lists)
            arr = np.asarray(chunk_waveform)
            if arr.ndim != 1:
                arr = arr.reshape(-1)
            wav_file.write(arr)

        if sample_rate is None:
            raise TTSSynthesisError("Qwen3 returned no audio data.")
        return sample_rate
    finally:
        if wav_file is not None:
            wav_file.close()

def _write_mp3_from_waveform(
    waveform: Sequence[float],
    sample_rate: int,
    output_path: Path,
) -> None:
    import soundfile as sf

    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = Path(tmpdir) / "qwen3-tts.wav"
        sf.write(str(wav_path), waveform, sample_rate)
        _run_ffmpeg(wav_path, output_path)


def _synthesize_with_qwen3_tts(
    text: str,
    output_path: Path,
    settings: TTSSettings,
) -> None:
    import gc
    import torch

    tts = None
    try:
        model_path = _resolve_model_path(settings)
        tts = _load_qwen3_model(
            str(model_path),
            settings.dtype,
            settings.attn_implementation,
            settings.device_map,
        )

        chunks = split_text_for_tts(text, settings.max_tts_chars)
        for i in range(len(chunks) - 1):
            a, b = chunks[i].rstrip(), chunks[i + 1].lstrip()
            if a and b and a[-1].isalnum() and b[0].isalnum():
                raise TTSSynthesisError(
                    f"Chunk boundary splits a word between chunk {i} and {i+1}: "
                    f"...{a[-20:]} | {b[:20]}..."
                )
        if not chunks:
            return

        def chunk_generator():
            # inference_mode reduces autograd overhead + can lower memory
            with torch.inference_mode():
                for chunk in chunks:
                    wavs, sr = tts.generate_custom_voice(
                        text=chunk,
                        language=settings.language,
                        speaker=settings.voice,
                        instruct=settings.instruct,
                    )
                    if not wavs:
                        raise TTSSynthesisError("Qwen3 returned no audio data.")
                    yield _normalize_waveform(wavs[0]), sr

                    # Encourage prompt release of large tensors between chunks
                    del wavs
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()

        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "qwen3-tts.wav"
            sample_rate = _write_wav_streaming(chunk_generator(), wav_path)
            _run_ffmpeg(wav_path, output_path)
    finally:
        if not settings.keep_model_loaded:
            if tts is not None:
                del tts
            release_qwen3_model_cache()
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            if hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
                torch.mps.empty_cache()
            if hasattr(torch, "xpu") and hasattr(torch.xpu, "empty_cache"):
                torch.xpu.empty_cache()


def _bak_synthesize_with_qwen3_tts(
    text: str,
    output_path: Path,
    settings: TTSSettings,
) -> None:
    model_path = _resolve_model_path(settings)
    tts = _load_qwen3_model(
        str(model_path),
        settings.dtype,
        settings.attn_implementation,
        settings.device_map,
    )

    chunks = split_text_for_tts(text, MAX_TTS_CHARS)
    if not chunks:
        return

    waveforms: list[list[float]] = []
    sample_rate: int | None = None
    for chunk in chunks:
        wavs, sr = tts.generate_custom_voice(
            text=chunk,
            language=settings.language,
            speaker=settings.voice,
            instruct=settings.instruct,
        )
        if not wavs:
            raise TTSSynthesisError("Qwen3 returned no audio data.")
        chunk_waveform = _normalize_waveform(wavs[0])
        if sample_rate is None:
            sample_rate = sr
        elif sr != sample_rate:
            raise TTSSynthesisError("Qwen3 returned mismatched sample rates.")
        waveforms.append(chunk_waveform)

    if sample_rate is None:
        raise TTSSynthesisError("Qwen3 did not return a sample rate.")
    combined = (
        [sample for waveform in waveforms for sample in waveform]
        if len(waveforms) > 1
        else waveforms[0]
    )
    _write_mp3_from_waveform(combined, sample_rate, output_path)


def _normalize_waveform(waveform: Sequence[float]):
    # Keep as ndarray/tensor-like if possible; avoid .tolist()
    if hasattr(waveform, "detach") and hasattr(waveform, "cpu"):
        return waveform.detach().cpu().numpy()
    if hasattr(waveform, "numpy"):
        return waveform.numpy()
    return waveform  # soundfile/numpy can usually coerce this

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
        _synthesize_with_qwen3_tts(text, output_path, settings)
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
    raise_on_error: bool = False,
) -> Path | None:
    if not settings.enabled:
        return None

    cleaned = sanitize_markdown_for_tts(text)
    if not cleaned:
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _synthesize_with_qwen3_tts(cleaned, output_path, settings)
    except TTSSynthesisError as error:
        if output_path.exists():
            output_path.unlink()
        if raise_on_error:
            raise
        if verbose:
            print(f"[tts] Skipped {output_path.name}: {error}")
        return None
    if verbose:
        print(f"[tts] Wrote {output_path.name}.")
    return output_path
