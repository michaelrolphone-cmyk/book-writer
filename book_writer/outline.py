from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


CHAPTER_PATTERN = re.compile(r"^chapter\b", re.IGNORECASE)
SECTION_PATTERN = re.compile(r"^section\b", re.IGNORECASE)
EPILOGUE_PATTERN = re.compile(r"^epilogue\b", re.IGNORECASE)
INTRODUCTION_PATTERN = re.compile(r"^introduction\b", re.IGNORECASE)
PROLOGUE_PATTERN = re.compile(r"^prologue\b", re.IGNORECASE)
PAGE_PATTERN = re.compile(r"^page\b", re.IGNORECASE)
ACT_PATTERN = re.compile(r"^act\b", re.IGNORECASE)
SCENE_PATTERN = re.compile(r"^scene\b", re.IGNORECASE)
TITLE_LABEL_PATTERN = re.compile(
    r"^(?:book\s+title|title|book\s+name)\b\s*[:\-–]\s*(.+)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class OutlineItem:
    title: str
    level: int
    parent_title: Optional[str] = None
    source: str = "heading"

    @property
    def type_label(self) -> str:
        if self.level == 1:
            if EPILOGUE_PATTERN.match(self.title):
                return "epilogue"
            if INTRODUCTION_PATTERN.match(self.title):
                return "introduction"
            if PROLOGUE_PATTERN.match(self.title):
                return "prologue"
            if ACT_PATTERN.match(self.title):
                return "act"
            if PAGE_PATTERN.match(self.title):
                return "page"
            return "chapter"
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


def _outline_headings(path: Path) -> list[tuple[int, str, int]]:
    headings: list[tuple[int, str, int]] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines()
    ):
        line = raw_line.strip()
        if not line or not line.startswith("#"):
            continue
        hashes = len(line) - len(line.lstrip("#"))
        title = _title_from_heading(line.lstrip("#").strip())
        if title:
            headings.append((line_number, title, hashes))
    return headings


def _explicit_title_from_heading(heading: str) -> Optional[str]:
    match = TITLE_LABEL_PATTERN.match(heading)
    if not match:
        return None
    title = match.group(1).strip()
    return title or None


def _looks_like_outline_item(heading: str) -> bool:
    return any(
        pattern.match(heading)
        for pattern in (
            CHAPTER_PATTERN,
            SECTION_PATTERN,
            EPILOGUE_PATTERN,
            INTRODUCTION_PATTERN,
            PROLOGUE_PATTERN,
            PAGE_PATTERN,
            ACT_PATTERN,
            SCENE_PATTERN,
        )
    )


def parse_outline_with_title(path: Path) -> tuple[Optional[str], List[OutlineItem]]:
    """Parse OUTLINE.md into an optional title plus outline items.

    Supported format is Markdown headings with #/## plus headings that start with
    "Chapter", "Section", "Epilogue", or "Introduction" at any heading level
    (e.g., ### **Chapter 1: ...**).
    """
    items: List[OutlineItem] = []
    current_chapter: Optional[str] = None
    current_level1_depth: Optional[int] = None
    headings = _outline_headings(path)
    if not headings:
        return None, items

    first_line, first_title, first_hashes = headings[0]
    title: Optional[str] = _explicit_title_from_heading(first_title)
    start_index = 0
    title_hashes: Optional[int] = None
    if title:
        start_index = 1
        title_hashes = first_hashes
    else:
        min_hash = min(hashes for _, _, hashes in headings)
        min_level_headings = [
            hashes for _, _, hashes in headings if hashes == min_hash
        ]
        if (
            len(min_level_headings) == 1
            and len(headings) > 1
            and not _looks_like_outline_item(first_title)
        ):
            start_index = 1
            title_hashes = min_hash

    heading_map: dict[int, tuple[int, str]] = {}
    for line_number, heading_title, hashes in headings[start_index:]:
        adjusted_hashes = hashes
        if title_hashes and hashes > title_hashes:
            adjusted_hashes = hashes - title_hashes
        heading_map[line_number] = (adjusted_hashes, heading_title)

    last_outline_level: Optional[int] = None
    last_title_for_level: dict[int, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines()
    ):
        heading = heading_map.get(line_number)
        if heading:
            adjusted_hashes, heading_title = heading
            if current_level1_depth is None or adjusted_hashes <= current_level1_depth:
                current_chapter = heading_title
                current_level1_depth = adjusted_hashes
                level = 1
                items.append(OutlineItem(title=heading_title, level=level))
            else:
                if not _looks_like_outline_item(heading_title):
                    bullet_level = max(adjusted_hashes, 2)
                    parent_title = last_title_for_level.get(bullet_level - 1)
                    if not parent_title:
                        parent_title = last_title_for_level.get(last_outline_level)
                    items.append(
                        OutlineItem(
                            title=heading_title,
                            level=bullet_level,
                            parent_title=parent_title,
                            source="bullet",
                        )
                    )
                    last_title_for_level[bullet_level] = heading_title
                    for depth in list(last_title_for_level):
                        if depth > bullet_level:
                            del last_title_for_level[depth]
                    continue
                level = 2
                items.append(
                    OutlineItem(
                        title=heading_title,
                        level=level,
                        parent_title=current_chapter,
                    )
                )
            last_outline_level = level
            last_title_for_level[level] = heading_title
            for depth in list(last_title_for_level):
                if depth > level:
                    del last_title_for_level[depth]
            continue

        match = re.match(r"^(\s*)(?:[-*+])\s+(.*)$", raw_line)
        if not match or not last_outline_level:
            continue
        bullet_text = _strip_markdown(match.group(2))
        if not bullet_text:
            continue
        indent = len(match.group(1).replace("\t", "  "))
        indent_level = max(indent // 2, 0)
        base_level = last_outline_level + 1
        bullet_level = max(base_level + indent_level, 2)
        parent_title = last_title_for_level.get(bullet_level - 1)
        if not parent_title:
            parent_title = last_title_for_level.get(last_outline_level)
        items.append(
            OutlineItem(
                title=bullet_text,
                level=bullet_level,
                parent_title=parent_title,
                source="bullet",
            )
        )
        last_title_for_level[bullet_level] = bullet_text
        for depth in list(last_title_for_level):
            if depth > bullet_level:
                del last_title_for_level[depth]

    return title, items


def parse_outline(path: Path) -> List[OutlineItem]:
    """Parse OUTLINE.md into a list of outline items."""
    _, items = parse_outline_with_title(path)
    return items


def outline_to_text(items: Iterable[OutlineItem]) -> str:
    lines = []
    for item in items:
        indent = "  " * (item.level - 1)
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
