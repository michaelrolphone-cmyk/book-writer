import sys
import unittest
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType
from unittest.mock import Mock, patch

from book_writer.tts import (
    TTSSynthesisError,
    TTSSettings,
    _synthesize_with_qwen3_tts,
    _write_mp3_from_waveform,
    sanitize_markdown_for_tts,
    split_text_for_tts,
    synthesize_chapter_audio,
    synthesize_text_audio,
)


class TestTTS(unittest.TestCase):
    def test_sanitize_markdown_for_tts_removes_formatting(self) -> None:
        markdown = (
            "# Chapter One\n\n"
            "This is **bold** text with a [link](https://example.com).\n\n"
            "- Bullet item\n"
            "1. Numbered item\n\n"
            "`inline code` and _italic_ text.\n\n"
            "> Blockquote line.\n\n"
            "![Cover](https://example.com/cover.png)\n\n"
            "Name | Value\n"
            "--- | ---\n"
            "Alpha | Beta\n\n"
            "<em>HTML</em> <strong>tags</strong>.\n\n"
            "---\n\n"
            "Emoji check 😃.\n\n"
            "Bad control \u0007 with zero width \u200b spaces.\n\n"
            "[ref]: https://example.com\n\n"
            "```python\n"
            "print('code block')\n"
            "```\n"
            "~~~js\n"
            "console.log('more code')\n"
            "~~~\n"
        )

        cleaned = sanitize_markdown_for_tts(markdown)

        self.assertIn("Chapter One", cleaned)
        self.assertIn("This is bold text with a link.", cleaned)
        self.assertIn("Bullet item", cleaned)
        self.assertIn("Numbered item", cleaned)
        self.assertIn("inline code and italic text.", cleaned)
        self.assertIn("Blockquote line.", cleaned)
        self.assertIn("Cover", cleaned)
        self.assertIn("Name Value", cleaned)
        self.assertIn("Alpha Beta", cleaned)
        self.assertIn("HTML tags.", cleaned)
        self.assertNotIn("😃", cleaned)
        self.assertNotIn("\u0007", cleaned)
        self.assertNotIn("\u200b", cleaned)
        self.assertNotIn("ref", cleaned)
        self.assertNotIn("print('code block')", cleaned)
        self.assertNotIn("console.log('more code')", cleaned)

    def test_split_text_for_tts_chunks_long_text(self) -> None:
        text = "Sentence one. Sentence two. Sentence three."

        chunks = split_text_for_tts(text, max_chars=20)

        self.assertGreater(len(chunks), 1)
        self.assertEqual(" ".join(chunks), text)
        self.assertTrue(all(len(chunk) <= 20 for chunk in chunks))

    def test_split_text_for_tts_merges_soft_line_breaks(self) -> None:
        text = (
            "This is a sentence that\n"
            "wraps onto the next line without a blank line.\n"
            "Still the same paragraph."
        )

        chunks = split_text_for_tts(text, max_chars=200)

        self.assertEqual(
            chunks,
            [
                "This is a sentence that wraps onto the next line without a blank "
                "line. Still the same paragraph."
            ],
        )

    @patch("book_writer.tts._synthesize_with_qwen3_tts")
    def test_synthesize_chapter_audio_writes_mp3(
        self, synthesize_mock: Mock
    ) -> None:
        settings = TTSSettings(enabled=True, audio_dirname="audio")
        chapter_content = "# Chapter One\n\nThis is **bold** text."

        with TemporaryDirectory() as tmpdir:
            chapter_path = Path(tmpdir) / "001-chapter-one.md"
            chapter_path.write_text(chapter_content, encoding="utf-8")
            output_dir = Path(tmpdir) / "audio"

            audio_path = synthesize_chapter_audio(
                chapter_path=chapter_path,
                output_dir=output_dir,
                settings=settings,
            )

            self.assertEqual(audio_path, output_dir / "001-chapter-one.mp3")
            self.assertTrue(output_dir.exists())

        synthesize_mock.assert_called_once()
        called_text = synthesize_mock.call_args[0][0]
        self.assertIn("Chapter One", called_text)
        self.assertIn("This is bold text.", called_text)

    @patch("book_writer.tts._synthesize_with_qwen3_tts")
    def test_synthesize_text_audio_writes_mp3(self, synthesize_mock: Mock) -> None:
        settings = TTSSettings(enabled=True, audio_dirname="audio")
        text = "# Synopsis\n\nThis is a **synopsis**."

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "audio" / "back-cover-synopsis.mp3"

            audio_path = synthesize_text_audio(
                text=text,
                output_path=output_path,
                settings=settings,
            )

            self.assertEqual(audio_path, output_path)
            self.assertTrue(output_path.parent.exists())

        synthesize_mock.assert_called_once()
        called_text = synthesize_mock.call_args[0][0]
        self.assertIn("Synopsis", called_text)
        self.assertIn("This is a synopsis.", called_text)

    @patch("book_writer.tts._run_ffmpeg")
    def test_write_mp3_from_waveform_uses_temp_wav(
        self,
        run_ffmpeg: Mock,
    ) -> None:
        waveform = [0.0, 0.1, -0.1]
        sample_rate = 22050
        fake_soundfile = ModuleType("soundfile")
        fake_soundfile.write = Mock()

        with patch.dict(sys.modules, {"soundfile": fake_soundfile}):
            with TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "output.mp3"
                _write_mp3_from_waveform(waveform, sample_rate, output_path)

        fake_soundfile.write.assert_called_once()
        wav_path = Path(fake_soundfile.write.call_args[0][0])
        self.assertEqual(wav_path.name, "qwen3-tts.wav")
        self.assertEqual(fake_soundfile.write.call_args[0][1], waveform)
        self.assertEqual(fake_soundfile.write.call_args[0][2], sample_rate)

        run_ffmpeg.assert_called_once()
        called_wav_path = run_ffmpeg.call_args[0][0]
        called_output_path = run_ffmpeg.call_args[0][1]
        self.assertEqual(Path(called_wav_path).name, "qwen3-tts.wav")
        self.assertEqual(called_output_path, output_path)

    @patch("book_writer.tts._synthesize_with_qwen3_tts")
    def test_synthesize_chapter_audio_handles_tts_errors(
        self, synthesize_mock: Mock
    ) -> None:
        settings = TTSSettings(enabled=True, audio_dirname="audio")
        synthesize_mock.side_effect = TTSSynthesisError("No audio was received.")

        with TemporaryDirectory() as tmpdir:
            chapter_path = Path(tmpdir) / "001-chapter-one.md"
            chapter_path.write_text("# Chapter One\n\nContent.", encoding="utf-8")
            output_dir = Path(tmpdir) / "audio"
            expected_output = output_dir / "001-chapter-one.mp3"
            output_dir.mkdir(parents=True, exist_ok=True)
            expected_output.write_bytes(b"partial")

            audio_path = synthesize_chapter_audio(
                chapter_path=chapter_path,
                output_dir=output_dir,
                settings=settings,
                verbose=True,
            )

            self.assertIsNone(audio_path)
            self.assertFalse(expected_output.exists())

    @patch("book_writer.tts._synthesize_with_qwen3_tts")
    def test_synthesize_text_audio_handles_tts_errors(
        self, synthesize_mock: Mock
    ) -> None:
        settings = TTSSettings(enabled=True, audio_dirname="audio")
        synthesize_mock.side_effect = TTSSynthesisError("No audio was received.")

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "audio" / "back-cover-synopsis.mp3"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"partial")

            audio_path = synthesize_text_audio(
                text="Summary.",
                output_path=output_path,
                settings=settings,
                verbose=True,
            )

            self.assertIsNone(audio_path)
            self.assertFalse(output_path.exists())

    @patch("book_writer.tts._run_ffmpeg")
    @patch("book_writer.tts._write_wav_streaming")
    @patch("book_writer.tts._load_qwen3_model")
    def test_synthesize_with_qwen3_tts_calls_model(
        self,
        load_mock: Mock,
        write_wav_mock: Mock,
        run_ffmpeg_mock: Mock,
    ) -> None:
        fake_model = Mock()
        fake_model.generate_custom_voice.return_value = ([[0.1, 0.2]], 24000)
        load_mock.return_value = fake_model
        settings = TTSSettings(
            enabled=True,
            model_path="models",
            voice="Ryan",
            language="English",
            instruct="Very happy.",
            device_map="cpu",
            dtype="float32",
            attn_implementation="sdpa",
        )

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "chapter.mp3"
            with patch("book_writer.tts._resolve_model_path", return_value=Path("models")):
                def consume_chunks(chunk_iter, wav_path):
                    chunks = list(chunk_iter)
                    self.assertEqual(len(chunks), 1)
                    waveform, sample_rate = chunks[0]
                    self.assertEqual(waveform, [0.1, 0.2])
                    self.assertEqual(sample_rate, 24000)
                    return sample_rate

                write_wav_mock.side_effect = consume_chunks
                fake_torch = Mock()
                fake_torch.inference_mode.return_value = nullcontext()
                fake_torch.cuda.is_available.return_value = False
                with patch.dict("sys.modules", {"torch": fake_torch}):
                    _synthesize_with_qwen3_tts(
                        text="Hello world.",
                        output_path=output_path,
                        settings=settings,
                    )

        load_mock.assert_called_once_with("models", "float32", "sdpa", "cpu")
        fake_model.generate_custom_voice.assert_called_once_with(
            text="Hello world.",
            language="English",
            speaker="Ryan",
            instruct="Very happy.",
        )
        write_wav_mock.assert_called_once()
        run_ffmpeg_mock.assert_called_once()
        _, output_arg = run_ffmpeg_mock.call_args[0]
        self.assertEqual(output_arg, output_path)

    @patch("book_writer.tts._run_ffmpeg")
    @patch("book_writer.tts._write_wav_streaming")
    @patch("book_writer.tts._load_qwen3_model")
    def test_synthesize_with_qwen3_tts_releases_model_when_unloaded(
        self,
        load_mock: Mock,
        write_wav_mock: Mock,
        run_ffmpeg_mock: Mock,
    ) -> None:
        fake_model = Mock()
        fake_model.generate_custom_voice.return_value = ([[0.1, 0.2]], 24000)
        load_mock.return_value = fake_model
        settings = TTSSettings(
            enabled=True,
            model_path="models",
            voice="Ryan",
            language="English",
            instruct=None,
            device_map="cpu",
            dtype="float32",
            attn_implementation="sdpa",
            keep_model_loaded=False,
        )

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "chapter.mp3"
            with patch("book_writer.tts._resolve_model_path", return_value=Path("models")):
                write_wav_mock.side_effect = lambda chunk_iter, wav_path: 24000
                fake_torch = Mock()
                fake_torch.inference_mode.return_value = nullcontext()
                fake_torch.cuda.is_available.return_value = False
                with (
                    patch.dict("sys.modules", {"torch": fake_torch}),
                    patch("book_writer.tts.release_qwen3_model_cache") as release_mock,
                ):
                    _synthesize_with_qwen3_tts(
                        text="Hello world.",
                        output_path=output_path,
                        settings=settings,
                    )

        release_mock.assert_called_once()
        run_ffmpeg_mock.assert_called_once()

if __name__ == "__main__":
    unittest.main()
