import runpy
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch


class TestMain(unittest.TestCase):
    def test_module_entrypoint_calls_cli_main(self) -> None:
        with patch("book_writer.cli.main", return_value=0) as mocked_main:
            with self.assertRaises(SystemExit) as context:
                runpy.run_module("book_writer", run_name="__main__")

        mocked_main.assert_called_once()
        self.assertEqual(context.exception.code, 0)

    def test_write_books_from_outlines_resets_context_between_books(self) -> None:
        from book_writer.cli import write_books_from_outlines

        client = Mock()
        client.generate.return_value = "Generated Title"
        client.reset_context.return_value = True

        with TemporaryDirectory() as tmpdir:
            outlines_dir = Path(tmpdir) / "outlines"
            books_dir = Path(tmpdir) / "books"
            completed_dir = Path(tmpdir) / "completed"
            outlines_dir.mkdir()
            (outlines_dir / "first.md").write_text(
                "# Book One\n\n## Chapter One\n", encoding="utf-8"
            )
            (outlines_dir / "second.md").write_text(
                "# Book Two\n\n## Chapter One\n", encoding="utf-8"
            )

            with patch("book_writer.cli.write_book", return_value=[]) as write_mock:
                write_books_from_outlines(
                    outlines_dir=outlines_dir,
                    books_dir=books_dir,
                    completed_outlines_dir=completed_dir,
                    client=client,
                    verbose=False,
                )

        self.assertEqual(write_mock.call_count, 2)
        self.assertEqual(client.reset_context.call_count, 2)


if __name__ == "__main__":
    unittest.main()
