from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional
from urllib import request

from book_writer.outline import OutlineItem, outline_to_text, slugify


@dataclass(frozen=True)
class ChapterContext:
    title: str
    content: str


class LMStudioClient:
    def __init__(self, base_url: str, model: str, timeout: Optional[float] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful writing assistant who writes in markdown.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
        }
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        if self.timeout is None:
            response_context = request.urlopen(req)
        else:
            response_context = request.urlopen(req, timeout=self.timeout)
        with response_context as response:
            body = response.read().decode("utf-8")
        parsed = json.loads(body)
        return parsed["choices"][0]["message"]["content"].strip()


def build_prompt(
    items: Iterable[OutlineItem],
    current: OutlineItem,
    previous_chapter: Optional[ChapterContext] = None,
) -> str:
    outline_text = outline_to_text(items)
    context_parts = []
    if current.parent_title:
        context_parts.append(
            f"The current section belongs to the chapter '{current.parent_title}'."
        )
    if previous_chapter and current.level == 1:
        context_parts.append(
            "Previous chapter context:\n"
            f"Title: {previous_chapter.title}\n"
            f"Content:\n{previous_chapter.content}\n"
            "Carry forward characters, narratives, and themes from the previous chapter."
        )
    context = "\n\n".join(context_parts)
    return (
        "Write the next part of the book based on the outline. "
        "Return only markdown content for the requested item.\n\n"
        f"Outline:\n{outline_text}\n\n"
        f"Current item: {current.title} ({current.type_label}).\n"
        f"{context}".strip()
    )


def build_chapter_context_prompt(title: str, content: str) -> str:
    return (
        "Generate a concise context summary for the next chapter. "
        "Focus on characters, narratives, themes, and unresolved threads. "
        "Return only the summary text.\n\n"
        f"Chapter title: {title}\n\n"
        f"Chapter content:\n{content}"
    )


def build_synopsis_prompt(title: str, outline_text: str, content: str) -> str:
    return (
        "Write a back cover synopsis for this book. "
        "Keep it engaging and concise, avoiding spoilers beyond the setup. "
        "Use the outline to guide the synopsis structure. "
        "Return only the synopsis text.\n\n"
        f"Book title: {title}\n\n"
        f"Outline:\n{outline_text}\n\n"
        f"Book content:\n{content}"
    )


def build_expand_paragraph_prompt(
    current: str,
    previous: Optional[str] = None,
    next_paragraph: Optional[str] = None,
    section_heading: Optional[str] = None,
) -> str:
    context_parts = []
    if section_heading:
        context_parts.append(f"Section heading: {section_heading}")
    if previous:
        context_parts.append(f"Previous section/paragraph:\n{previous}")
    if next_paragraph:
        context_parts.append(f"Next section/paragraph:\n{next_paragraph}")
    context = "\n\n".join(context_parts)
    return (
        "Expand the current paragraph or section with more detail. "
        "Use the surrounding context to maintain continuity. "
        "Return only the expanded markdown for the current paragraph or section.\n\n"
        f"{context}\n\n"
        f"Current paragraph/section:\n{current}"
    ).strip()


@dataclass
class _MarkdownBlock:
    type: str
    text: str


def _split_markdown_blocks(content: str) -> List[_MarkdownBlock]:
    blocks: List[_MarkdownBlock] = []
    buffer: List[str] = []
    for line in content.splitlines():
        if line.startswith("#"):
            if buffer:
                blocks.append(_MarkdownBlock(type="paragraph", text="\n".join(buffer)))
                buffer = []
            blocks.append(_MarkdownBlock(type="heading", text=line))
            continue
        if not line.strip():
            if buffer:
                blocks.append(_MarkdownBlock(type="paragraph", text="\n".join(buffer)))
                buffer = []
            continue
        buffer.append(line)
    if buffer:
        blocks.append(_MarkdownBlock(type="paragraph", text="\n".join(buffer)))
    return blocks


def expand_chapter_content(content: str, client: LMStudioClient) -> str:
    blocks = _split_markdown_blocks(content)
    paragraph_indexes = [i for i, block in enumerate(blocks) if block.type == "paragraph"]
    if not paragraph_indexes:
        return content

    heading_for_block: List[Optional[str]] = []
    current_heading: Optional[str] = None
    for block in blocks:
        if block.type == "heading":
            current_heading = block.text.lstrip("#").strip()
        heading_for_block.append(current_heading)

    original_paragraphs = {index: blocks[index].text for index in paragraph_indexes}

    for position, block_index in enumerate(paragraph_indexes):
        previous_paragraph = None
        next_paragraph = None
        if position > 0:
            previous_paragraph = original_paragraphs[paragraph_indexes[position - 1]]
        if position < len(paragraph_indexes) - 1:
            next_paragraph = original_paragraphs[paragraph_indexes[position + 1]]
        section_heading = heading_for_block[block_index]
        prompt = build_expand_paragraph_prompt(
            current=blocks[block_index].text,
            previous=previous_paragraph,
            next_paragraph=next_paragraph,
            section_heading=section_heading,
        )
        expanded = client.generate(prompt)
        blocks[block_index].text = expanded.strip()

    return "\n\n".join(block.text for block in blocks)


def build_book_markdown(title: str, outline_text: str, chapters: List[str]) -> str:
    chapters_text = "\n\n".join(chapters)
    return (
        f"# {title}\n\n"
        "\\newpage\n\n"
        "## Outline\n"
        f"{outline_text}\n\n"
        "\\newpage\n\n"
        f"{chapters_text}\n"
    )


def generate_book_pdf(
    output_dir: Path,
    title: str,
    outline_text: str,
    chapter_files: List[Path],
) -> Path:
    chapters = [path.read_text(encoding="utf-8") for path in chapter_files]
    book_markdown = build_book_markdown(title, outline_text, chapters)
    markdown_path = output_dir / "book.md"
    markdown_path.write_text(book_markdown, encoding="utf-8")
    pdf_path = output_dir / "book.pdf"
    subprocess.run(
        ["pandoc", str(markdown_path), "--from", "markdown", "-o", str(pdf_path)],
        check=True,
    )
    return pdf_path


def _chapter_files(output_dir: Path) -> List[Path]:
    return sorted(
        path
        for path in output_dir.iterdir()
        if path.suffix == ".md"
        and path.name not in {"book.md", "back-cover-synopsis.md"}
    )


def _derive_outline_from_chapters(chapter_files: List[Path]) -> str:
    items: List[OutlineItem] = []
    current_chapter: Optional[str] = None
    for chapter_file in chapter_files:
        for line in chapter_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                current_chapter = title
                items.append(OutlineItem(title=title, level=1))
            elif line.startswith("## "):
                title = line[3:].strip()
                items.append(
                    OutlineItem(title=title, level=2, parent_title=current_chapter)
                )
    return outline_to_text(items)


def _read_book_metadata(output_dir: Path, chapter_files: List[Path]) -> ChapterContext:
    book_md = output_dir / "book.md"
    if book_md.exists():
        content = book_md.read_text(encoding="utf-8")
        title = "Untitled"
        outline = ""
        for line in content.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        if "## Outline" in content:
            outline_section = content.split("## Outline", 1)[1]
            outline = outline_section.split("\\newpage", 1)[0].strip()
        return ChapterContext(title=title, content=outline)

    outline = _derive_outline_from_chapters(chapter_files)
    title = chapter_files[0].stem if chapter_files else output_dir.name
    for line in chapter_files[0].read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    return ChapterContext(title=title, content=outline)


def expand_book(
    output_dir: Path,
    client: LMStudioClient,
    passes: int = 1,
) -> List[Path]:
    if passes < 1:
        raise ValueError("Expansion passes must be at least 1.")
    chapter_files = _chapter_files(output_dir)
    if not chapter_files:
        raise ValueError(f"No chapter markdown files found in {output_dir}.")

    for _ in range(passes):
        for chapter_file in chapter_files:
            content = chapter_file.read_text(encoding="utf-8")
            expanded_content = expand_chapter_content(content, client)
            chapter_file.write_text(expanded_content.strip() + "\n", encoding="utf-8")

    book_metadata = _read_book_metadata(output_dir, chapter_files)
    outline_text = book_metadata.content
    if not outline_text:
        outline_text = _derive_outline_from_chapters(chapter_files)

    generate_book_pdf(
        output_dir=output_dir,
        title=book_metadata.title,
        outline_text=outline_text,
        chapter_files=chapter_files,
    )
    return chapter_files


def write_book(
    items: List[OutlineItem],
    output_dir: Path,
    client: LMStudioClient,
) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written_files: List[Path] = []
    index = 0
    previous_chapter: Optional[ChapterContext] = None

    while index < len(items):
        item = items[index]
        prompt = build_prompt(items, item, previous_chapter)
        content = client.generate(prompt)
        heading = f"{item.heading_prefix} {item.title}"
        file_name = f"{index + 1:03d}-{slugify(item.display_title)}.md"
        file_path = output_dir / file_name
        file_path.write_text(f"{heading}\n\n{content}\n", encoding="utf-8")
        written_files.append(file_path)
        if item.level == 1:
            context_prompt = build_chapter_context_prompt(item.title, content)
            context_summary = client.generate(context_prompt)
            previous_chapter = ChapterContext(title=item.title, content=context_summary)
        index += 1

    book_title = items[0].title
    outline_text = outline_to_text(items)
    generate_book_pdf(
        output_dir=output_dir,
        title=book_title,
        outline_text=outline_text,
        chapter_files=written_files,
    )
    synopsis_prompt = build_synopsis_prompt(
        title=book_title,
        outline_text=outline_text,
        content="\n\n".join(
            path.read_text(encoding="utf-8") for path in written_files
        ),
    )
    synopsis = client.generate(synopsis_prompt)
    synopsis_path = output_dir / "back-cover-synopsis.md"
    synopsis_path.write_text(synopsis, encoding="utf-8")

    return written_files
