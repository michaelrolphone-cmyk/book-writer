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
TTS_ENGINE_QWEN3 = "qwen3"
TTS_ENGINE_PYTHON = "python"
TTS_ENGINE_COSYVOICE3 = "cosyvoice3"
SUPPORTED_TTS_ENGINES = (TTS_ENGINE_QWEN3, TTS_ENGINE_PYTHON, TTS_ENGINE_COSYVOICE3)


@dataclass(frozen=True)
class TTSSettings:
    enabled: bool = False
    engine: str = TTS_ENGINE_QWEN3
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
    max_text_tokens: int = 384
    max_new_tokens: int = 2048
    do_sample: bool = False
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
SILENCE_RMS_THRESHOLD = 1e-4
RECOVERY_MIN_CHARS = 200
RECOVERY_MAX_CHARS = 800
MAX_RECOVERY_DEPTH = 1


def normalize_tts_engine(engine: str | None) -> str:
    if not engine:
        return TTS_ENGINE_QWEN3
    normalized = engine.strip().lower()
    if normalized in {"qwen", TTS_ENGINE_QWEN3}:
        return TTS_ENGINE_QWEN3
    if normalized in {"pyttsx3", "pyttsx", TTS_ENGINE_PYTHON}:
        return TTS_ENGINE_PYTHON
    if normalized in {"cosyvoice", TTS_ENGINE_COSYVOICE3}:
        return TTS_ENGINE_COSYVOICE3
    raise TTSSynthesisError(
        f"Unsupported TTS engine '{engine}'. "
        f"Choose one of: {', '.join(SUPPORTED_TTS_ENGINES)}."
    )


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


def split_text_for_tts_tokens(
    text: str, model_path: str, max_text_tokens: int = 384
) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []
    tokenizer = _load_qwen_tokenizer(model_path)
    words = cleaned.split()
    if not words:
        return []
    max_text_tokens = max(1, max_text_tokens)
    chunks: list[str] = []
    buffer: list[str] = []

    def token_len(value: str) -> int:
        return len(tokenizer.encode(value, add_special_tokens=False))

    for word in words:
        candidate = f"{' '.join(buffer)} {word}".strip() if buffer else word
        if token_len(candidate) > max_text_tokens and buffer:
            chunks.append(" ".join(buffer))
            buffer = [word]
        else:
            buffer.append(word)
    if buffer:
        chunks.append(" ".join(buffer))
    return chunks


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


@functools.lru_cache(maxsize=2)
def _load_qwen_tokenizer(model_path: str):
    import inspect
    from transformers import AutoTokenizer

    kwargs = {"trust_remote_code": True}
    if "fix_mistral_regex" in inspect.signature(AutoTokenizer.from_pretrained).parameters:
        kwargs["fix_mistral_regex"] = True
    return AutoTokenizer.from_pretrained(model_path, **kwargs)


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


def _adjust_rate_setting(rate_setting: str | None, base_rate: int) -> int | None:
    if not rate_setting:
        return None
    value = rate_setting.strip()
    if not value:
        return None
    try:
        if value.endswith("%"):
            delta = float(value.rstrip("%"))
            return int(base_rate * (1 + delta / 100.0))
        return int(float(value))
    except ValueError:
        return None


def _parse_pitch_setting(pitch_setting: str | None) -> int | None:
    if not pitch_setting:
        return None
    value = pitch_setting.strip().lower()
    if not value:
        return None
    if value.endswith("hz"):
        value = value[:-2]
    try:
        return int(float(value))
    except ValueError:
        return None


def _synthesize_with_python_tts(
    text: str,
    output_path: Path,
    settings: TTSSettings,
) -> None:
    try:
        import pyttsx3
    except ImportError as error:
        raise TTSSynthesisError(
            "Python TTS requires the pyttsx3 package. Install it with "
            "`pip install pyttsx3` and try again."
        ) from error

    engine = pyttsx3.init()
    try:
        if settings.voice:
            try:
                engine.setProperty("voice", settings.voice)
            except Exception:
                pass
        try:
            base_rate = engine.getProperty("rate")
        except Exception:
            base_rate = None
        if isinstance(base_rate, (int, float)):
            adjusted_rate = _adjust_rate_setting(settings.rate, int(base_rate))
            if adjusted_rate is not None:
                try:
                    engine.setProperty("rate", adjusted_rate)
                except Exception:
                    pass
        pitch_value = _parse_pitch_setting(settings.pitch)
        if pitch_value is not None:
            try:
                engine.setProperty("pitch", pitch_value)
            except Exception:
                pass

        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "python-tts.wav"
            engine.save_to_file(text, str(wav_path))
            engine.runAndWait()
            if not wav_path.exists():
                raise TTSSynthesisError("Python TTS did not produce audio.")
            _run_ffmpeg(wav_path, output_path)
    finally:
        try:
            engine.stop()
        except Exception:
            pass


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


def _resolve_cosyvoice_model_path(settings: TTSSettings) -> Path:
    model_path = Path(settings.model_path or "").expanduser()
    if not model_path.exists():
        raise TTSSynthesisError(
            "CosyVoice3 model path not found. Update tts_settings.model_path "
            f"or --tts-model-path (missing: {model_path})."
        )
    return model_path


@functools.lru_cache(maxsize=2)
def _load_cosyvoice3_model(model_path: str):
    try:
        from cosyvoice.cli.cosyvoice import CosyVoice
    except ImportError as error:
        raise TTSSynthesisError(
            "CosyVoice3 requires the cosyvoice package. Install it and try again."
        ) from error
    return CosyVoice(model_path)


def _write_cosyvoice_result(result, output_path: Path) -> None:
    if isinstance(result, (str, Path)):
        wav_path = Path(result)
        if not wav_path.exists():
            raise TTSSynthesisError("CosyVoice3 did not return a valid WAV path.")
        _run_ffmpeg(wav_path, output_path)
        return
    if isinstance(result, (tuple, list)) and len(result) == 2:
        waveform, sample_rate = result
        _write_mp3_from_waveform(waveform, sample_rate, output_path)
        return
    if isinstance(result, dict):
        wav_path = result.get("wav_path") or result.get("path")
        if wav_path:
            wav_path = Path(wav_path)
            if not wav_path.exists():
                raise TTSSynthesisError("CosyVoice3 returned a missing WAV path.")
            _run_ffmpeg(wav_path, output_path)
            return
        waveform = result.get("waveform") or result.get("audio")
        sample_rate = result.get("sample_rate") or result.get("sr")
        if waveform is not None and sample_rate is not None:
            _write_mp3_from_waveform(waveform, int(sample_rate), output_path)
            return
    raise TTSSynthesisError("CosyVoice3 returned an unsupported audio payload.")


def _synthesize_with_cosyvoice3(
    text: str,
    output_path: Path,
    settings: TTSSettings,
) -> None:
    model_path = _resolve_cosyvoice_model_path(settings)
    cosyvoice = _load_cosyvoice3_model(str(model_path))
    if hasattr(cosyvoice, "inference"):
        try:
            result = cosyvoice.inference(text)
        except TypeError:
            result = cosyvoice.inference(text=text)
    elif hasattr(cosyvoice, "tts"):
        try:
            result = cosyvoice.tts(text)
        except TypeError:
            result = cosyvoice.tts(text=text)
    else:
        raise TTSSynthesisError(
            "CosyVoice3 model does not expose an inference/tts method."
        )
    _write_cosyvoice_result(result, output_path)


def _sanitize_waveform(waveform: Sequence[float]):
    import importlib.util
    import math

    if waveform is None:
        return []

    if importlib.util.find_spec("numpy") is None:
        cleaned: list[float] = []
        for value in waveform:
            numeric = float(value)
            if not math.isfinite(numeric):
                numeric = 0.0
            if numeric > 1.0:
                numeric = 1.0
            elif numeric < -1.0:
                numeric = -1.0
            cleaned.append(numeric)
        return cleaned

    import numpy as np

    arr = np.asarray(waveform, dtype=np.float32).reshape(-1)
    if arr.size == 0:
        return arr
    if not np.isfinite(arr).all():
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    max_abs = float(np.max(np.abs(arr)))
    if max_abs > 1.0:
        arr = np.clip(arr, -1.0, 1.0)
    return arr


def _is_waveform_silent(waveform, threshold: float = SILENCE_RMS_THRESHOLD) -> bool:
    if waveform is None:
        return True
    if hasattr(waveform, "size") and waveform.size == 0:
        return True
    import importlib.util
    import math

    if importlib.util.find_spec("numpy") is None:
        values = [float(value) for value in waveform]
        if not values:
            return True
        mean_square = sum(value * value for value in values) / len(values)
        rms = math.sqrt(mean_square)
        return rms < threshold

    import numpy as np

    values = np.asarray(waveform, dtype=np.float32).reshape(-1)
    if values.size == 0:
        return True
    rms = float(np.sqrt(np.mean(np.square(values))))
    return rms < threshold


def _split_text_for_recovery(
    text: str,
    model_path: str,
    max_text_tokens: int,
) -> list[str]:
    max_chars = min(
        RECOVERY_MAX_CHARS,
        max(RECOVERY_MIN_CHARS, len(text) // 2),
    )
    chunks = split_text_for_tts(text, max_chars=max_chars)
    if len(chunks) > 1:
        return chunks
    reduced_tokens = max(1, max_text_tokens // 2)
    if reduced_tokens < max_text_tokens:
        token_chunks = split_text_for_tts_tokens(text, model_path, reduced_tokens)
        if len(token_chunks) > 1:
            return token_chunks
    return [text]


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

        chunks = split_text_for_tts_tokens(
            text,
            str(model_path),
            settings.max_text_tokens,
        )
        if not chunks:
            return

        def chunk_generator():
            # inference_mode reduces autograd overhead + can lower memory
            with torch.inference_mode():
                for chunk in chunks:
                    yield from _generate_chunk_audio(chunk, tts, settings, str(model_path), 0)
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

    chunks = split_text_for_tts_tokens(
        text,
        str(model_path),
        settings.max_text_tokens,
    )
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
            max_new_tokens=settings.max_new_tokens,
            do_sample=settings.do_sample,
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


def _generate_chunk_audio(
    text: str,
    tts,
    settings: TTSSettings,
    model_path: str,
    depth: int,
):
    wavs, sr = tts.generate_custom_voice(
        text=text,
        language=settings.language,
        speaker=settings.voice,
        instruct=settings.instruct,
        max_new_tokens=settings.max_new_tokens,
        do_sample=settings.do_sample,
    )
    if not wavs:
        raise TTSSynthesisError("Qwen3 returned no audio data.")
    waveform = _sanitize_waveform(_normalize_waveform(wavs[0]))
    if _is_waveform_silent(waveform):
        if depth >= MAX_RECOVERY_DEPTH:
            raise TTSSynthesisError("Qwen3 returned near-silent audio.")
        recovery_chunks = _split_text_for_recovery(text, model_path, settings.max_text_tokens)
        if len(recovery_chunks) <= 1:
            raise TTSSynthesisError("Qwen3 returned near-silent audio.")
        for recovery_text in recovery_chunks:
            yield from _generate_chunk_audio(
                recovery_text,
                tts,
                settings,
                model_path,
                depth + 1,
            )
        return
    yield waveform, sr


def _synthesize_with_engine(
    text: str,
    output_path: Path,
    settings: TTSSettings,
) -> None:
    engine = normalize_tts_engine(settings.engine)
    if engine == TTS_ENGINE_QWEN3:
        _synthesize_with_qwen3_tts(text, output_path, settings)
        return
    if engine == TTS_ENGINE_PYTHON:
        _synthesize_with_python_tts(text, output_path, settings)
        return
    if engine == TTS_ENGINE_COSYVOICE3:
        _synthesize_with_cosyvoice3(text, output_path, settings)
        return
    raise TTSSynthesisError(
        f"Unsupported TTS engine '{settings.engine}'. "
        f"Choose one of: {', '.join(SUPPORTED_TTS_ENGINES)}."
    )

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
        _synthesize_with_engine(text, output_path, settings)
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
        _synthesize_with_engine(cleaned, output_path, settings)
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


def merge_chapter_audio(
    chapter_audio_paths: Sequence[Path],
    output_path: Path,
    gap_seconds: float = 1.6,
) -> Path:
    if not chapter_audio_paths:
        raise TTSSynthesisError("No chapter audio files available to merge.")
    missing = [path for path in chapter_audio_paths if not path.exists()]
    if missing:
        missing_list = ", ".join(path.name for path in missing)
        raise TTSSynthesisError(
            "Missing chapter audio files required to build the audiobook: "
            f"{missing_list}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    target_sample_rate = _probe_audio_sample_rate(chapter_audio_paths[0])
    inputs: list[str] = []
    input_count = 0
    for index, audio_path in enumerate(chapter_audio_paths):
        inputs.extend(["-i", str(audio_path)])
        input_count += 1
        if index < len(chapter_audio_paths) - 1:
            inputs.extend(
                [
                    "-f",
                    "lavfi",
                    "-t",
                    str(gap_seconds),
                    "-i",
                    f"anullsrc=channel_layout=mono:sample_rate={target_sample_rate}",
                ]
            )
            input_count += 1

    filter_steps = []
    filter_inputs = []
    for idx in range(input_count):
        label = f"a{idx}"
        filter_steps.append(
            f"[{idx}:a]aresample={target_sample_rate}:async=1,asetpts=N/SR/TB[{label}]"
        )
        filter_inputs.append(f"[{label}]")
    filter_complex = (
        ";".join(filter_steps)
        + f"{''.join(filter_inputs)}concat=n={input_count}:v=0:a=1[outa]"
    )
    command = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        filter_complex,
        "-map",
        "[outa]",
        "-ac",
        "1",
        "-ar",
        str(target_sample_rate),
        "-codec:a",
        "libmp3lame",
        str(output_path),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as error:
        raise TTSSynthesisError(
            "ffmpeg is required to merge chapter audio into a single MP3. "
            "Install ffmpeg and try again."
        ) from error
    if result.returncode != 0:
        raise TTSSynthesisError(
            "ffmpeg failed to merge chapter audio. "
            f"stderr: {result.stderr.strip()}"
        )
    return output_path


def _probe_audio_sample_rate(audio_path: Path) -> int:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=sample_rate",
        "-of",
        "default=nw=1:nk=1",
        str(audio_path),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as error:
        raise TTSSynthesisError(
            "ffmpeg is required to merge chapter audio into a single MP3. "
            "Install ffmpeg and try again."
        ) from error
    if result.returncode != 0:
        raise TTSSynthesisError(
            "ffmpeg failed to probe chapter audio sample rate. "
            f"stderr: {result.stderr.strip()}"
        )
    try:
        return int(result.stdout.strip())
    except ValueError as error:
        raise TTSSynthesisError(
            "ffmpeg returned an invalid chapter audio sample rate."
        ) from error
