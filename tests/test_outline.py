import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from book_writer.outline import (
    OutlineItem,
    outline_to_text,
    parse_outline,
    parse_outline_with_title,
    slugify,
)


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
                OutlineItem(
                    title="Bullet one",
                    level=2,
                    parent_title="Chapter 1: Redefining Motherhood",
                    source="bullet",
                ),
                OutlineItem(title="Chapter 2: The Foundation of Trust", level=1),
                OutlineItem(
                    title="Bullet two",
                    level=2,
                    parent_title="Chapter 2: The Foundation of Trust",
                    source="bullet",
                ),
            ],
        )

    def test_parse_outline_accepts_epilogue_headings(self) -> None:
        content = """
# Chapter One
## Section A
# Epilogue
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

    def test_parse_outline_accepts_introduction_headings(self) -> None:
        content = """
**Book Title: Example**

---

### **Introduction: The Eternal Call of Service**
- Bullet one

### **Chapter 1: The Divine Blueprint**
- Bullet two
"""
        with TemporaryDirectory() as tmpdir:
            outline_path = Path(tmpdir) / "OUTLINE.md"
            outline_path.write_text(content.strip(), encoding="utf-8")

            items = parse_outline(outline_path)

        self.assertEqual(
            items,
            [
                OutlineItem(
                    title="Introduction: The Eternal Call of Service", level=1
                ),
                OutlineItem(
                    title="Bullet one",
                    level=2,
                    parent_title="Introduction: The Eternal Call of Service",
                    source="bullet",
                ),
                OutlineItem(title="Chapter 1: The Divine Blueprint", level=1),
                OutlineItem(
                    title="Bullet two",
                    level=2,
                    parent_title="Chapter 1: The Divine Blueprint",
                    source="bullet",
                ),
            ],
        )

    def test_parse_outline_with_title_promotes_heading_levels(self) -> None:
        content = """
# The Great Book
## Chapter One
### Section A
## Chapter Two
"""
        with TemporaryDirectory() as tmpdir:
            outline_path = Path(tmpdir) / "OUTLINE.md"
            outline_path.write_text(content.strip(), encoding="utf-8")

            title, items = parse_outline_with_title(outline_path)

        self.assertIsNone(title)
        self.assertEqual(
            items,
            [
                OutlineItem(title="Chapter One", level=1),
                OutlineItem(title="Section A", level=2, parent_title="Chapter One"),
                OutlineItem(title="Chapter Two", level=1),
            ],
        )

    def test_parse_outline_with_explicit_title_label(self) -> None:
        content = """
# Book Title: The Great Book
## Chapter One
### Section A
## Chapter Two
"""
        with TemporaryDirectory() as tmpdir:
            outline_path = Path(tmpdir) / "OUTLINE.md"
            outline_path.write_text(content.strip(), encoding="utf-8")

            title, items = parse_outline_with_title(outline_path)

        self.assertEqual(title, "The Great Book")
        self.assertEqual(
            items,
            [
                OutlineItem(title="Chapter One", level=1),
                OutlineItem(title="Section A", level=2, parent_title="Chapter One"),
                OutlineItem(title="Chapter Two", level=1),
            ],
        )

    def test_parse_outline_with_outline_container_heading(self) -> None:
        content = """
# Outline
## Chapter One
## Chapter Two
"""
        with TemporaryDirectory() as tmpdir:
            outline_path = Path(tmpdir) / "OUTLINE.md"
            outline_path.write_text(content.strip(), encoding="utf-8")

            title, items = parse_outline_with_title(outline_path)

        self.assertIsNone(title)
        self.assertEqual(
            items,
            [
                OutlineItem(title="Chapter One", level=1),
                OutlineItem(title="Chapter Two", level=1),
            ],
        )

    def test_parse_outline_with_single_top_level_chapter(self) -> None:
        content = """
# Chapter One
## Section A
## Section B
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
            ],
        )

    def test_parse_outline_includes_page_headings(self) -> None:
        content = """
# Lila’s Secret Garden of Joy
### Page 1-2: Meet Lila, Our Curious Little Girl!
### Page 3-4: The Secret Garden Under the Bed
## Chapter One
### Page 5-6: Lila Investigates the Lights
## Chapter Two
"""
        with TemporaryDirectory() as tmpdir:
            outline_path = Path(tmpdir) / "OUTLINE.md"
            outline_path.write_text(content.strip(), encoding="utf-8")

            items = parse_outline(outline_path)

        self.assertEqual(
            items,
            [
                OutlineItem(
                    title="Page 1-2: Meet Lila, Our Curious Little Girl!",
                    level=1,
                ),
                OutlineItem(
                    title="Page 3-4: The Secret Garden Under the Bed",
                    level=1,
                ),
                OutlineItem(title="Chapter One", level=1),
                OutlineItem(
                    title="Page 5-6: Lila Investigates the Lights",
                    level=2,
                    parent_title="Chapter One",
                ),
                OutlineItem(title="Chapter Two", level=1),
            ],
        )

    def test_parse_outline_accepts_act_and_scene_headings(self) -> None:
        content = """
# Echoes of the Ancients
### Act 1: The Fracture
#### Prologue: The Catalyst
#### Scene 1: Inciting Incident
### Act 2: The New World
#### Scene 2: Arrival
"""
        with TemporaryDirectory() as tmpdir:
            outline_path = Path(tmpdir) / "OUTLINE.md"
            outline_path.write_text(content.strip(), encoding="utf-8")

            items = parse_outline(outline_path)

        self.assertEqual(
            items,
            [
                OutlineItem(title="Act 1: The Fracture", level=1),
                OutlineItem(
                    title="Prologue: The Catalyst",
                    level=2,
                    parent_title="Act 1: The Fracture",
                ),
                OutlineItem(
                    title="Scene 1: Inciting Incident",
                    level=2,
                    parent_title="Act 1: The Fracture",
                ),
                OutlineItem(title="Act 2: The New World", level=1),
                OutlineItem(
                    title="Scene 2: Arrival",
                    level=2,
                    parent_title="Act 2: The New World",
                ),
            ],
        )

    def test_outline_to_text_formats_items(self) -> None:
        items = [
            OutlineItem(title="Chapter One", level=1),
            OutlineItem(title="Section A", level=2, parent_title="Chapter One"),
            OutlineItem(
                title="Beat detail",
                level=3,
                parent_title="Section A",
            ),
        ]

        outline = outline_to_text(items)

        self.assertEqual(
            outline, "- Chapter One\n  - Section A\n    - Beat detail"
        )

    def test_parse_outline_includes_bullets_under_sections(self) -> None:
        content = """
# Chapter One
## Section A
- Beat one
  - Beat two
## Section B
- Beat three
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
                OutlineItem(
                    title="Beat one",
                    level=3,
                    parent_title="Section A",
                    source="bullet",
                ),
                OutlineItem(
                    title="Beat two",
                    level=4,
                    parent_title="Beat one",
                    source="bullet",
                ),
                OutlineItem(title="Section B", level=2, parent_title="Chapter One"),
                OutlineItem(
                    title="Beat three",
                    level=3,
                    parent_title="Section B",
                    source="bullet",
                ),
            ],
        )

    def test_slugify_normalizes_text(self) -> None:
        self.assertEqual(slugify("Chapter 1: Intro"), "chapter-1-intro")
        self.assertEqual(slugify("***"), "untitled")


if __name__ == "__main__":
    unittest.main()
