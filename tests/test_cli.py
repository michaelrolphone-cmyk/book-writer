import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from book_writer import cli
from book_writer.cli import write_books_from_outlines


class TestWriteBooksFromOutlines(unittest.TestCase):
    @patch("book_writer.writer.subprocess.run")
    def test_writes_books_and_moves_outlines(self, run_mock: MagicMock) -> None:
        client = MagicMock()
        client.generate.side_effect = [
            "Title for book one",
            "Content for book one",
            "Context for book one",
            "Synopsis for book one",
            "Title for book two",
            "Content for book two",
            "Context for book two",
            "Synopsis for book two",
        ]

        with TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            outlines_dir = base_dir / "outlines"
            books_dir = base_dir / "books"
            completed_dir = base_dir / "completed_outlines"
            outlines_dir.mkdir()

            (outlines_dir / "alpha.md").write_text("# Chapter Alpha\n", encoding="utf-8")
            (outlines_dir / "beta.md").write_text("# Chapter Beta\n", encoding="utf-8")

            written_files = write_books_from_outlines(
                outlines_dir=outlines_dir,
                books_dir=books_dir,
                completed_outlines_dir=completed_dir,
                client=client,
            )

            self.assertEqual(len(written_files), 2)
            alpha_output = books_dir / "alpha"
            beta_output = books_dir / "beta"
            self.assertTrue(alpha_output.is_dir())
            self.assertTrue(beta_output.is_dir())
            self.assertTrue((alpha_output / written_files[0].name).exists())
            self.assertTrue((beta_output / written_files[1].name).exists())

            alpha_book_md = (alpha_output / "book.md").read_text(encoding="utf-8")
            beta_book_md = (beta_output / "book.md").read_text(encoding="utf-8")
            self.assertIn("# Title for book one", alpha_book_md)
            self.assertIn("# Title for book two", beta_book_md)
            self.assertIn("### By Marissa Bard", alpha_book_md)
            self.assertIn("### By Marissa Bard", beta_book_md)

            self.assertFalse((outlines_dir / "alpha.md").exists())
            self.assertFalse((outlines_dir / "beta.md").exists())
            self.assertTrue((completed_dir / "alpha.md").exists())
            self.assertTrue((completed_dir / "beta.md").exists())
            run_mock.assert_called()


class TestCliExpandBook(unittest.TestCase):
    @patch("book_writer.cli.expand_book")
    def test_main_expands_completed_book(self, expand_mock: MagicMock) -> None:
        with TemporaryDirectory() as tmpdir:
            with patch("sys.argv", ["book-writer", "--expand-book", tmpdir]):
                result = cli.main()

        self.assertEqual(result, 0)
        expand_mock.assert_called_once()
        _, kwargs = expand_mock.call_args
        self.assertTrue(kwargs["verbose"])

    @patch("book_writer.cli.expand_book")
    def test_main_expands_completed_book_with_passes(
        self, expand_mock: MagicMock
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            with patch(
                "sys.argv",
                ["book-writer", "--expand-book", tmpdir, "--expand-passes", "3"],
            ):
                result = cli.main()

        self.assertEqual(result, 0)
        expand_mock.assert_called_once()
        _, kwargs = expand_mock.call_args
        self.assertEqual(kwargs["passes"], 3)
        self.assertTrue(kwargs["verbose"])

    @patch("book_writer.cli.expand_book")
    def test_main_expands_completed_book_with_tone(
        self, expand_mock: MagicMock
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            with patch(
                "sys.argv",
                ["book-writer", "--expand-book", tmpdir, "--tone", "novel"],
            ):
                result = cli.main()

        self.assertEqual(result, 0)
        expand_mock.assert_called_once()
        _, kwargs = expand_mock.call_args
        self.assertEqual(kwargs["tone"], "novel")


class TestCliTtsDefaults(unittest.TestCase):
    @patch("book_writer.cli.generate_book_title", return_value="Generated Title")
    @patch("book_writer.cli.write_book")
    def test_main_enables_tts_by_default(
        self, write_mock: MagicMock, _: MagicMock
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            outline_path = Path(tmpdir) / "OUTLINE.md"
            outline_path.write_text("# Chapter One\n", encoding="utf-8")
            current_dir = os.getcwd()
            os.chdir(tmpdir)
            try:
                with patch(
                    "sys.argv", ["book-writer", "--outline", str(outline_path)]
                ):
                    cli.main()
            finally:
                os.chdir(current_dir)

        _, kwargs = write_mock.call_args
        self.assertTrue(kwargs["tts_settings"].enabled)

    @patch("book_writer.cli.generate_book_title", return_value="Generated Title")
    @patch("book_writer.cli.write_book")
    def test_main_passes_tone_to_write_book(
        self, write_mock: MagicMock, _: MagicMock
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            outline_path = Path(tmpdir) / "OUTLINE.md"
            outline_path.write_text("# Chapter One\n", encoding="utf-8")
            current_dir = os.getcwd()
            os.chdir(tmpdir)
            try:
                with patch(
                    "sys.argv",
                    [
                        "book-writer",
                        "--outline",
                        str(outline_path),
                        "--tone",
                        "play write",
                    ],
                ):
                    cli.main()
            finally:
                os.chdir(current_dir)

        _, kwargs = write_mock.call_args
        self.assertEqual(kwargs["tone"], "play write")

    @patch("book_writer.cli.generate_book_title", return_value="Generated Title")
    @patch("book_writer.cli.write_book")
    def test_main_disables_tts_with_flag(
        self, write_mock: MagicMock, _: MagicMock
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            outline_path = Path(tmpdir) / "OUTLINE.md"
            outline_path.write_text("# Chapter One\n", encoding="utf-8")
            current_dir = os.getcwd()
            os.chdir(tmpdir)
            try:
                with patch(
                    "sys.argv",
                    ["book-writer", "--outline", str(outline_path), "--no-tts"],
                ):
                    cli.main()
            finally:
                os.chdir(current_dir)

        _, kwargs = write_mock.call_args
        self.assertFalse(kwargs["tts_settings"].enabled)
