import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from book_writer.tts import (
    AUDIO_EXTENSION,
    MAX_TTS_CHARS,
    ParagraphTiming,
    TTSSynthesisError,
    TTSSettings,
    WordTiming,
    _build_paragraph_timings,
    _synthesize_with_edge_tts,
    read_paragraph_timings,
    sanitize_markdown_for_tts,
    split_markdown_paragraphs,
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
            "Emoji check 😃.\n\n"
            "Bad control \u0007 with zero width \u200b spaces.\n\n"
            "```python\n"
            "print('code block')\n"
            "```\n"
        )

        cleaned = sanitize_markdown_for_tts(markdown)

        self.assertIn("Chapter One", cleaned)
        self.assertIn("This is bold text with a link.", cleaned)
        self.assertIn("Bullet item", cleaned)
        self.assertIn("Numbered item", cleaned)
        self.assertIn("inline code and italic text.", cleaned)
        self.assertNotIn("😃", cleaned)
        self.assertNotIn("\u0007", cleaned)
        self.assertNotIn("\u200b", cleaned)
        self.assertNotIn("print('code block')", cleaned)

    def test_split_text_for_tts_chunks_long_text(self) -> None:
        text = "Sentence one. Sentence two. Sentence three."

        chunks = split_text_for_tts(text, max_chars=20)

        self.assertGreater(len(chunks), 1)
        self.assertEqual(" ".join(chunks), text)
        self.assertTrue(all(len(chunk) <= 20 for chunk in chunks))

    def test_split_markdown_paragraphs_discards_headings(self) -> None:
        markdown = "# Title\n\nFirst paragraph.\n\n## Subhead\n\nSecond paragraph."

        paragraphs = split_markdown_paragraphs(markdown)

        self.assertEqual(paragraphs, ["First paragraph.", "Second paragraph."])

    def test_build_paragraph_timings_uses_word_positions(self) -> None:
        paragraphs = ["Hello world", "Another line"]
        word_timings = [
            WordTiming(text="Hello", start=0.0, end=0.5),
            WordTiming(text="world", start=0.5, end=1.0),
            WordTiming(text="Another", start=1.0, end=1.5),
            WordTiming(text="line", start=1.5, end=2.0),
        ]

        timings = _build_paragraph_timings(paragraphs, word_timings)

        self.assertEqual(
            timings,
            [
                ParagraphTiming(text="Hello world", start=0.0, end=1.0),
                ParagraphTiming(text="Another line", start=1.0, end=2.0),
            ],
        )

    def test_read_paragraph_timings_reads_json(self) -> None:
        with TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / f"chapter{AUDIO_EXTENSION}"
            timing_path = audio_path.with_suffix(".timed.json")
            timing_path.write_text(
                json.dumps(
                    {
                        "paragraphs": [
                            {"text": "Hello world", "start": 0.0, "end": 1.0}
                        ]
                    }
                ),
                encoding="utf-8",
            )

            timings = read_paragraph_timings(audio_path)

            self.assertEqual(
                timings,
                [ParagraphTiming(text="Hello world", start=0.0, end=1.0)],
            )

    @patch("book_writer.tts._synthesize_with_edge_tts")
    def test_synthesize_chapter_audio_writes_mp4(
        self, synthesize_mock: Mock
    ) -> None:
        settings = TTSSettings(enabled=True, audio_dirname="audio")
        chapter_content = "# Chapter One\n\nThis is **bold** text."
        synthesize_mock.return_value = []

        with TemporaryDirectory() as tmpdir:
            chapter_path = Path(tmpdir) / "001-chapter-one.md"
            chapter_path.write_text(chapter_content, encoding="utf-8")
            output_dir = Path(tmpdir) / "audio"

            audio_path = synthesize_chapter_audio(
                chapter_path=chapter_path,
                output_dir=output_dir,
                settings=settings,
            )

            self.assertEqual(
                audio_path,
                output_dir / f"001-chapter-one{AUDIO_EXTENSION}",
            )
            self.assertTrue(output_dir.exists())

        synthesize_mock.assert_called_once()
        called_text = synthesize_mock.call_args[0][0]
        self.assertIn("Chapter One", called_text)
        self.assertIn("This is bold text.", called_text)

    @patch("book_writer.tts._synthesize_with_edge_tts")
    def test_synthesize_text_audio_writes_mp4(self, synthesize_mock: Mock) -> None:
        settings = TTSSettings(enabled=True, audio_dirname="audio")
        text = "# Synopsis\n\nThis is a **synopsis**."
        synthesize_mock.return_value = []

        with TemporaryDirectory() as tmpdir:
            output_path = (
                Path(tmpdir)
                / "audio"
                / f"back-cover-synopsis{AUDIO_EXTENSION}"
            )

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

    @patch("book_writer.tts._synthesize_with_edge_tts")
    def test_synthesize_chapter_audio_handles_tts_errors(
        self, synthesize_mock: Mock
    ) -> None:
        settings = TTSSettings(enabled=True, audio_dirname="audio")
        synthesize_mock.side_effect = TTSSynthesisError("No audio was received.")

        with TemporaryDirectory() as tmpdir:
            chapter_path = Path(tmpdir) / "001-chapter-one.md"
            chapter_path.write_text("# Chapter One\n\nContent.", encoding="utf-8")
            output_dir = Path(tmpdir) / "audio"
            expected_output = output_dir / f"001-chapter-one{AUDIO_EXTENSION}"
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

    @patch("book_writer.tts._synthesize_with_edge_tts")
    def test_synthesize_text_audio_handles_tts_errors(
        self, synthesize_mock: Mock
    ) -> None:
        settings = TTSSettings(enabled=True, audio_dirname="audio")
        synthesize_mock.side_effect = TTSSynthesisError("No audio was received.")

        with TemporaryDirectory() as tmpdir:
            output_path = (
                Path(tmpdir)
                / "audio"
                / f"back-cover-synopsis{AUDIO_EXTENSION}"
            )
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

    def test_edge_tts_retries_on_no_audio(self) -> None:
        class FakeNoAudioReceived(Exception):
            pass

        class FakeCommunicate:
            created = 0
            stream_calls = 0

            def __init__(self, *_args: object, **_kwargs: object) -> None:
                FakeCommunicate.created += 1

            async def stream(self):
                FakeCommunicate.stream_calls += 1
                if FakeCommunicate.stream_calls == 1:
                    raise FakeNoAudioReceived("no audio")
                yield {"type": "audio", "data": b"ok"}
                yield {
                    "type": "WordBoundary",
                    "offset": 0,
                    "duration": 5_000_000,
                    "text": "Hello",
                }

        fake_edge_tts = Mock()
        fake_edge_tts.Communicate = FakeCommunicate
        fake_edge_tts.exceptions = Mock(NoAudioReceived=FakeNoAudioReceived)

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / f"chapter{AUDIO_EXTENSION}"
            with patch.dict("sys.modules", {"edge_tts": fake_edge_tts}):
                _synthesize_with_edge_tts(
                    text="Hello world.",
                    output_path=output_path,
                    settings=TTSSettings(enabled=True),
                )

            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_bytes(), b"ok")
            self.assertGreaterEqual(FakeCommunicate.created, 2)

    def test_edge_tts_raises_after_retries(self) -> None:
        class FakeNoAudioReceived(Exception):
            pass

        class FakeCommunicate:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                pass

            async def stream(self):
                if False:
                    yield {}
                raise FakeNoAudioReceived("no audio")

        fake_edge_tts = Mock()
        fake_edge_tts.Communicate = FakeCommunicate
        fake_edge_tts.exceptions = Mock(NoAudioReceived=FakeNoAudioReceived)

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / f"chapter{AUDIO_EXTENSION}"
            with patch.dict("sys.modules", {"edge_tts": fake_edge_tts}):
                with self.assertRaises(TTSSynthesisError):
                    _synthesize_with_edge_tts(
                        text="Hello world.",
                        output_path=output_path,
                        settings=TTSSettings(enabled=True),
                    )

            self.assertFalse(output_path.exists())

    def test_edge_tts_falls_back_to_single_request_on_chunk_failure(self) -> None:
        class FakeNoAudioReceived(Exception):
            pass

        class FakeCommunicate:
            def __init__(self, text: str, *_args: object, **_kwargs: object) -> None:
                self.text = text

            async def stream(self):
                if len(self.text) <= MAX_TTS_CHARS:
                    raise FakeNoAudioReceived("no audio")
                yield {"type": "audio", "data": b"ok"}
                yield {
                    "type": "WordBoundary",
                    "offset": 0,
                    "duration": 5_000_000,
                    "text": "Hello",
                }

        fake_edge_tts = Mock()
        fake_edge_tts.Communicate = FakeCommunicate
        fake_edge_tts.exceptions = Mock(NoAudioReceived=FakeNoAudioReceived)

        long_text = "A" * (MAX_TTS_CHARS + 1)

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / f"chapter{AUDIO_EXTENSION}"
            with patch.dict("sys.modules", {"edge_tts": fake_edge_tts}), patch(
                "book_writer.tts.subprocess.run"
            ) as run_mock:
                run_mock.return_value = Mock()
                _synthesize_with_edge_tts(
                    text=long_text,
                    output_path=output_path,
                    settings=TTSSettings(enabled=True),
                )

            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_bytes(), b"ok")

    def test_edge_tts_raises_when_chunk_fails(self) -> None:
        class FakeChunkError(Exception):
            pass

        class FakeCommunicate:
            def __init__(self, text: str, *_args: object, **_kwargs: object) -> None:
                self.text = text

            async def stream(self):
                if "BAD" in self.text:
                    raise FakeChunkError("bad chunk")
                yield {"type": "audio", "data": b"part"}
                yield {
                    "type": "WordBoundary",
                    "offset": 0,
                    "duration": 5_000_000,
                    "text": "Hello",
                }

        fake_edge_tts = Mock()
        fake_edge_tts.Communicate = FakeCommunicate
        fake_edge_tts.exceptions = Mock(NoAudioReceived=FakeChunkError)

        long_text = ("A" * MAX_TTS_CHARS) + "BAD" + ("B" * 5)

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / f"chapter{AUDIO_EXTENSION}"
            with patch.dict("sys.modules", {"edge_tts": fake_edge_tts}), patch(
                "book_writer.tts.subprocess.run"
            ) as run_mock:
                run_mock.return_value = Mock()
                with self.assertRaises(TTSSynthesisError):
                    _synthesize_with_edge_tts(
                        text=long_text,
                        output_path=output_path,
                        settings=TTSSettings(enabled=True),
                    )

            self.assertFalse(output_path.exists())

if __name__ == "__main__":
    unittest.main()
