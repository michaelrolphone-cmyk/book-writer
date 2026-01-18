import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from book_writer.outline import OutlineItem
from book_writer.writer import build_prompt, write_book


class TestWriter(unittest.TestCase):
    def test_build_prompt_includes_outline_and_current_item(self) -> None:
        items = [
            OutlineItem(title="Chapter One", level=1),
            OutlineItem(title="Section A", level=2, parent_title="Chapter One"),
        ]

        prompt = build_prompt(items, items[1])

        self.assertIn("Outline:", prompt)
        self.assertIn("Current item: Section A", prompt)
        self.assertIn("chapter 'Chapter One'", prompt)

    def test_write_book_creates_numbered_files(self) -> None:
        items = [
            OutlineItem(title="Chapter One", level=1),
            OutlineItem(title="Section A", level=2, parent_title="Chapter One"),
        ]
        client = MagicMock()
        client.generate.side_effect = ["Chapter content", "Section content"]

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            files = write_book(items, output_dir, client)

            self.assertEqual(len(files), 2)
            self.assertTrue(files[0].name.startswith("001-"))
            self.assertTrue(files[1].name.startswith("002-"))
            first_content = files[0].read_text(encoding="utf-8")
            second_content = files[1].read_text(encoding="utf-8")

        self.assertIn("# Chapter One", first_content)
        self.assertIn("Chapter content", first_content)
        self.assertIn("## Section A", second_content)
        self.assertIn("Section content", second_content)


if __name__ == "__main__":
    unittest.main()
