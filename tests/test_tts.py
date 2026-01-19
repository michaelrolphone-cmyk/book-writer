import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from book_writer.tts import (
    TTSSettings,
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
        self.assertNotIn("print('code block')", cleaned)

    def test_split_text_for_tts_chunks_long_text(self) -> None:
        text = "Sentence one. Sentence two. Sentence three."

        chunks = split_text_for_tts(text, max_chars=20)

        self.assertGreater(len(chunks), 1)
        self.assertEqual(" ".join(chunks), text)
        self.assertTrue(all(len(chunk) <= 20 for chunk in chunks))

    @patch("book_writer.tts._synthesize_with_edge_tts")
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

    @patch("book_writer.tts._synthesize_with_edge_tts")
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


if __name__ == "__main__":
    unittest.main()
