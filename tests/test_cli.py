import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from book_writer.cli import write_books_from_outlines


class TestWriteBooksFromOutlines(unittest.TestCase):
    @patch("book_writer.writer.subprocess.run")
    def test_writes_books_and_moves_outlines(self, run_mock: MagicMock) -> None:
        client = MagicMock()
        client.generate.side_effect = [
            "Content for book one",
            "Context for book one",
            "Synopsis for book one",
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

            self.assertFalse((outlines_dir / "alpha.md").exists())
            self.assertFalse((outlines_dir / "beta.md").exists())
            self.assertTrue((completed_dir / "alpha.md").exists())
            self.assertTrue((completed_dir / "beta.md").exists())
            run_mock.assert_called()
