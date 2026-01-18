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
        "Return only the synopsis text.\n\n"
        f"Book title: {title}\n\n"
        f"Outline:\n{outline_text}\n\n"
        f"Book content:\n{content}"
    )


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
