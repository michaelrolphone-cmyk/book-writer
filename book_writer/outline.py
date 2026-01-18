from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


CHAPTER_PATTERN = re.compile(r"^chapter\b", re.IGNORECASE)
SECTION_PATTERN = re.compile(r"^section\b", re.IGNORECASE)
EPILOGUE_PATTERN = re.compile(r"^epilogue\b", re.IGNORECASE)


@dataclass(frozen=True)
class OutlineItem:
    title: str
    level: int
    parent_title: Optional[str] = None

    @property
    def type_label(self) -> str:
        if self.level == 1:
            return "epilogue" if EPILOGUE_PATTERN.match(self.title) else "chapter"
        return "section"

    @property
    def heading_prefix(self) -> str:
        return "#" if self.level == 1 else "##"

    @property
    def display_title(self) -> str:
        if self.parent_title and self.level > 1:
            return f"{self.title} (in {self.parent_title})"
        return self.title


def _strip_markdown(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("**") and stripped.endswith("**"):
        stripped = stripped[2:-2].strip()
    if stripped.startswith("*") and stripped.endswith("*"):
        stripped = stripped[1:-1].strip()
    return stripped


def _title_from_heading(heading: str) -> str:
    cleaned = _strip_markdown(heading)
    return cleaned


def parse_outline(path: Path) -> List[OutlineItem]:
    """Parse OUTLINE.md into a list of outline items.

    Supported format is Markdown headings with #/## plus headings that start with
    "Chapter", "Section", or "Epilogue" at any heading level
    (e.g., ### **Chapter 1: ...**).
    """
    items: List[OutlineItem] = []
    current_chapter: Optional[str] = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or not line.startswith("#"):
            continue

        hashes = len(line) - len(line.lstrip("#"))
        title = _title_from_heading(line.lstrip("#").strip())
        if not title:
            continue

        if CHAPTER_PATTERN.match(title) or EPILOGUE_PATTERN.match(title):
            current_chapter = title
            items.append(OutlineItem(title=title, level=1))
            continue

        if SECTION_PATTERN.match(title):
            items.append(OutlineItem(title=title, level=2, parent_title=current_chapter))
            continue

        if hashes == 1:
            current_chapter = title
            items.append(OutlineItem(title=title, level=1))
        elif hashes == 2:
            items.append(
                OutlineItem(title=title, level=2, parent_title=current_chapter)
            )

    return items


def outline_to_text(items: Iterable[OutlineItem]) -> str:
    lines = []
    for item in items:
        indent = "" if item.level == 1 else "  "
        lines.append(f"{indent}- {item.title}")
    return "\n".join(lines)


def slugify(text: str) -> str:
    cleaned = []
    for char in text.lower():
        if char.isalnum():
            cleaned.append(char)
        elif char in {" ", "-", "_"}:
            cleaned.append("-")
    slug = "".join(cleaned)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "untitled"
