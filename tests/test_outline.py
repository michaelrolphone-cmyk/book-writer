import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from book_writer.outline import OutlineItem, outline_to_text, parse_outline, slugify


class TestOutlineParsing(unittest.TestCase):
    def test_parse_outline_reads_chapters_and_sections(self) -> None:
        content = """
# Chapter One
## Section A
## Section B
# Chapter Two
## Section C
"""
        with TemporaryDirectory() as tmpdir:
            outline_path = Path(tmpdir) / "OUTLINE.md"
            outline_path.write_text(content.strip(), encoding="utf-8")

            items = parse_outline(outline_path)

        self.assertEqual(
            items,
            [
                OutlineItem(title="Chapter One", level=1),
                OutlineItem(title="Section A", level=2, parent_title="Chapter One"),
                OutlineItem(title="Section B", level=2, parent_title="Chapter One"),
                OutlineItem(title="Chapter Two", level=1),
                OutlineItem(title="Section C", level=2, parent_title="Chapter Two"),
            ],
        )

    def test_parse_outline_accepts_markdown_chapter_headings(self) -> None:
        content = """
**Book Title: Example**

---

### **Chapter 1: Redefining Motherhood**
- Bullet one

### **Chapter 2: The Foundation of Trust**
- Bullet two
"""
        with TemporaryDirectory() as tmpdir:
            outline_path = Path(tmpdir) / "OUTLINE.md"
            outline_path.write_text(content.strip(), encoding="utf-8")

            items = parse_outline(outline_path)

        self.assertEqual(
            items,
            [
                OutlineItem(title="Chapter 1: Redefining Motherhood", level=1),
                OutlineItem(title="Chapter 2: The Foundation of Trust", level=1),
            ],
        )

    def test_parse_outline_accepts_epilogue_headings(self) -> None:
        content = """
# Chapter One
## Section A
### Epilogue
"""
        with TemporaryDirectory() as tmpdir:
            outline_path = Path(tmpdir) / "OUTLINE.md"
            outline_path.write_text(content.strip(), encoding="utf-8")

            items = parse_outline(outline_path)

        self.assertEqual(
            items,
            [
                OutlineItem(title="Chapter One", level=1),
                OutlineItem(title="Section A", level=2, parent_title="Chapter One"),
                OutlineItem(title="Epilogue", level=1),
            ],
        )

    def test_outline_to_text_formats_items(self) -> None:
        items = [
            OutlineItem(title="Chapter One", level=1),
            OutlineItem(title="Section A", level=2, parent_title="Chapter One"),
        ]

        outline = outline_to_text(items)

        self.assertEqual(outline, "- Chapter One\n  - Section A")

    def test_slugify_normalizes_text(self) -> None:
        self.assertEqual(slugify("Chapter 1: Intro"), "chapter-1-intro")
        self.assertEqual(slugify("***"), "untitled")


if __name__ == "__main__":
    unittest.main()
