import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from book_writer import server


class TestServerHelpers(unittest.TestCase):
    def test_parse_tts_settings_defaults(self) -> None:
        settings = server._parse_tts_settings({})

        self.assertTrue(settings.enabled)
        self.assertEqual(settings.voice, "en-US-JennyNeural")
        self.assertEqual(settings.audio_dirname, "audio")

    def test_parse_video_settings_defaults(self) -> None:
        settings = server._parse_video_settings({})

        self.assertFalse(settings.enabled)
        self.assertEqual(settings.video_dirname, "video")
        self.assertIsNone(settings.background_video)


class TestServerApi(unittest.TestCase):
    def test_list_outlines_returns_preview(self) -> None:
        with TemporaryDirectory() as tmpdir:
            outlines_dir = Path(tmpdir) / "outlines"
            outlines_dir.mkdir()
            outline_path = outlines_dir / "story.md"
            outline_path.write_text("# Book One\n\n## Chapter One\n", encoding="utf-8")

            result = server.list_outlines({"outlines_dir": str(outlines_dir)})

        self.assertEqual(len(result["outlines"]), 1)
        self.assertIn("Chapter One", result["outlines"][0]["preview"])

    def test_list_books_returns_status(self) -> None:
        with TemporaryDirectory() as tmpdir:
            books_dir = Path(tmpdir) / "books"
            book_dir = books_dir / "sample"
            book_dir.mkdir(parents=True)
            (book_dir / "001-chapter-one.md").write_text("# Chapter One", encoding="utf-8")

            result = server.list_books({"books_dir": str(books_dir)})

        self.assertEqual(len(result["books"]), 1)
        self.assertTrue(result["books"][0]["has_text"])

    def test_generate_book_calls_writer(self) -> None:
        with TemporaryDirectory() as tmpdir:
            outline_path = Path(tmpdir) / "outline.md"
            outline_path.write_text("# Book One\n\n## Chapter One\n", encoding="utf-8")

            with patch("book_writer.server.write_book") as write_book:
                write_book.return_value = [Path(tmpdir) / "001.md"]
                response = server.generate_book(
                    {
                        "outline_path": str(outline_path),
                        "output_dir": str(Path(tmpdir) / "output"),
                    }
                )

        self.assertEqual(response["written_files"], [str(Path(tmpdir) / "001.md")])
        write_book.assert_called_once()

    def test_expand_book_supports_expand_only(self) -> None:
        with TemporaryDirectory() as tmpdir:
            book_dir = Path(tmpdir) / "book"
            book_dir.mkdir()
            first = book_dir / "001-chapter-one.md"
            second = book_dir / "002-chapter-two.md"
            first.write_text("# Chapter One", encoding="utf-8")
            second.write_text("# Chapter Two", encoding="utf-8")

            with patch("book_writer.server.expand_book") as expand_book:
                server.expand_book_api(
                    {
                        "expand_book": str(book_dir),
                        "expand_only": "2",
                    }
                )

        expand_book.assert_called_once()
        chapter_files = expand_book.call_args.kwargs["chapter_files"]
        self.assertEqual(chapter_files, [second])


if __name__ == "__main__":
    unittest.main()
