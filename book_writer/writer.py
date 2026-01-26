from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, List, Optional
from urllib import request
from urllib.error import HTTPError

from book_writer.cover import (
    CoverSettings,
    generate_book_cover,
    generate_chapter_cover,
)
from book_writer.metadata import generate_book_genres, write_book_meta
from book_writer.outline import OutlineItem, outline_to_text, slugify
from book_writer.tts import (
    TTSSynthesisError,
    TTSSettings,
    sanitize_markdown_for_tts,
    synthesize_chapter_audio,
    synthesize_text_audio,
)
from book_writer.video import (
    VideoSettings,
    _probe_audio_duration,
    generate_paragraph_image,
    synthesize_chapter_video,
    synthesize_chapter_video_from_images,
)


@dataclass(frozen=True)
class ChapterContext:
    title: str
    content: str


class LMStudioClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: Optional[float] = None,
        base_prompt: Optional[str] = None,
        author: Optional[str] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.base_prompt = base_prompt if base_prompt is not None else _base_prompt(author)

    def generate(self, prompt: str) -> str:
        prompt = self.render_prompt(prompt)
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

    def render_prompt(self, prompt: str) -> str:
        return f"{self.base_prompt}\n\n{prompt}".strip()

    def set_author(self, author: Optional[str]) -> None:
        self.base_prompt = _base_prompt(author)

    def reset_context(self) -> bool:
        payload = {"model": self.model}
        data = json.dumps(payload).encode("utf-8")
        endpoints = ("/v1/chat/reset", "/v1/reset")
        for endpoint in endpoints:
            req = request.Request(
                f"{self.base_url}{endpoint}",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            try:
                if self.timeout is None:
                    response_context = request.urlopen(req)
                else:
                    response_context = request.urlopen(req, timeout=self.timeout)
                with response_context as response:
                    response.read()
                return True
            except HTTPError as exc:
                if exc.code in {404, 405}:
                    continue
                raise
        return False


PROGRESS_FILENAME = ".book_writer_progress.json"


def _progress_path(output_dir: Path) -> Path:
    return output_dir / PROGRESS_FILENAME


def load_book_progress(output_dir: Path) -> Optional[dict]:
    progress_path = _progress_path(output_dir)
    if not progress_path.exists():
        return None
    return json.loads(progress_path.read_text(encoding="utf-8"))


def save_book_progress(output_dir: Path, progress: dict) -> None:
    progress_path = _progress_path(output_dir)
    progress_path.write_text(
        json.dumps(progress, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def clear_book_progress(output_dir: Path) -> None:
    progress_path = _progress_path(output_dir)
    if progress_path.exists():
        progress_path.unlink()


def _tone_preface(tone: Optional[str]) -> str:
    if not tone:
        return ""
    tones_dir = Path(__file__).parent / "tones"
    tone_path = tones_dir / f"{tone}.md"
    if not tone_path.exists():
        raise ValueError(
            f"Tone '{tone}' is not available. Add {tone_path.name} to {tones_dir}."
        )
    content = tone_path.read_text(encoding="utf-8").strip()
    if not content:
        return ""
    return f"{content}\n\n"


def _base_prompt(author: Optional[str] = None) -> str:
    project_root = Path(__file__).resolve().parents[1]
    if author:
        authors_dir = project_root / "authors"
        author_path = authors_dir / f"{author}.md"
        if not author_path.exists():
            raise ValueError(
                f"Author persona '{author}' is not available. Add {author_path.name} "
                f"to {authors_dir}."
            )
        return author_path.read_text(encoding="utf-8").strip()
    prompt_path = project_root / "PROMPT.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Base prompt file not found at {prompt_path}.")
    return prompt_path.read_text(encoding="utf-8").strip()


def _expand_prompt_text() -> str:
    project_root = Path(__file__).resolve().parents[1]
    prompt_path = project_root / "EXPAND_PROMPT.md"
    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Expand prompt file not found at {prompt_path}."
        )
    return prompt_path.read_text(encoding="utf-8").strip()


def _outline_descendant_lines(
    items: Iterable[OutlineItem], current_title: str
) -> list[str]:
    children_map: dict[str, list[OutlineItem]] = {}
    for item in items:
        if item.parent_title:
            children_map.setdefault(item.parent_title, []).append(item)

    def walk(parent_title: str, depth: int) -> list[str]:
        lines: list[str] = []
        for child in children_map.get(parent_title, []):
            indent = "  " * depth
            lines.append(f"{indent}- {child.title}")
            lines.extend(walk(child.title, depth + 1))
        return lines

    return walk(current_title, 0)


def build_prompt(
    items: Iterable[OutlineItem],
    current: OutlineItem,
    previous_chapter: Optional[ChapterContext] = None,
    tone: Optional[str] = None,
) -> str:
    outline_text = outline_to_text(items)
    context_parts = []
    focus_parts = []
    if current.level == 1:
        sections = [
            item.title for item in items if item.parent_title == current.title
        ]
        if sections:
            focus_parts.append(
                "Chapter focus checklist:\n- " + "\n- ".join(sections)
            )
    else:
        focus_parts.append(f"Section focus: {current.title}")
    descendant_lines = _outline_descendant_lines(items, current.title)
    if descendant_lines:
        focus_parts.append(
            "Outline beats to cover:\n" + "\n".join(descendant_lines)
        )
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
    focus_text = "\n\n".join(focus_parts)
    return (
        f"{_tone_preface(tone)}"
        "Write the next part of the book based strictly on the outline. "
        "Cover the themes and plot beats listed for the current item. "
        "Do not introduce new plot threads that are not supported by the outline. "
        "Do not jump ahead to future outline items. "
        "Use only the characters, locations, and events mentioned in the outline. "
        "Return only markdown content for the requested item.\n\n"
        f"Outline:\n{outline_text}\n\n"
        f"Current item: {current.title} ({current.type_label}).\n"
        f"{focus_text}\n\n"
        f"{context}".strip()
    )


def build_chapter_context_prompt(
    title: str,
    content: str,
    tone: Optional[str] = None,
) -> str:
    return (
        f"{_tone_preface(tone)}"
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


def build_book_title_prompt(outline_text: str, first_chapter_title: str) -> str:
    return (
        "Generate a compelling book title based on the outline. "
        "Do not reuse the first chapter name as the title. "
        "Return only the title text.\n\n"
        f"First chapter: {first_chapter_title}\n\n"
        f"Outline:\n{outline_text}"
    )


def build_outline_prompt(prompt: str) -> str:
    return (
        "Create a detailed book outline in markdown. "
        "Include a book title, chapters, and optional sections. "
        "Use # for the title, ## for chapters, and ### for sections. "
        "Return only markdown.\n\n"
        f"Prompt:\n{prompt.strip()}"
    )


def build_outline_revision_prompt(outline_text: str, revision_prompt: str) -> str:
    return (
        "Revise the following book outline based on the revision prompt. "
        "Return the full updated outline in markdown with the same structure. "
        "Do not include commentary.\n\n"
        f"Revision prompt:\n{revision_prompt.strip()}\n\n"
        f"Current outline:\n{outline_text.strip()}"
    )


def generate_outline(
    prompt: str,
    client: LMStudioClient,
    revision_prompts: Optional[Iterable[str]] = None,
) -> str:
    if not prompt.strip():
        raise ValueError("Outline prompt cannot be empty.")
    outline_text = client.generate(build_outline_prompt(prompt))
    for revision_prompt in revision_prompts or []:
        if not revision_prompt or not revision_prompt.strip():
            continue
        outline_text = client.generate(
            build_outline_revision_prompt(outline_text, revision_prompt)
        )
    return outline_text.strip()


def _clean_generated_title(title: str) -> str:
    cleaned = title.strip()
    if cleaned.startswith(("\"", "'")) and cleaned.endswith(("\"", "'")):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def generate_book_title(items: List[OutlineItem], client: LMStudioClient) -> str:
    outline_text = outline_to_text(items)
    first_chapter = next((item.title for item in items if item.level == 1), "Untitled")
    prompt = build_book_title_prompt(outline_text, first_chapter)
    title = _clean_generated_title(client.generate(prompt))
    if title.casefold() == first_chapter.casefold():
        prompt = (
            build_book_title_prompt(outline_text, first_chapter)
            + "\n\nReturn a different title than the first chapter name."
        )
        title = _clean_generated_title(client.generate(prompt))
        if title.casefold() == first_chapter.casefold():
            title = f"{title} (Book)"
    return title or "Untitled"


def build_expand_paragraph_prompt(
    current: str,
    previous: Optional[str] = None,
    next_paragraph: Optional[str] = None,
    section_heading: Optional[str] = None,
    tone: Optional[str] = None,
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
        f"{_tone_preface(tone)}"
        f"{_expand_prompt_text()}\n\n"
        f"{context}\n\n"
        f"Current paragraph/section:\n{current}"
    ).strip()


@dataclass
class _MarkdownBlock:
    type: str
    text: str


IMPLEMENTATION_DETAILS_PATTERN = re.compile(r"^implementation details$", re.IGNORECASE)


def _strip_markdown(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("**") and stripped.endswith("**"):
        stripped = stripped[2:-2].strip()
    if stripped.startswith("*") and stripped.endswith("*"):
        stripped = stripped[1:-1].strip()
    return stripped


def _is_implementation_details(title: str) -> bool:
    return IMPLEMENTATION_DETAILS_PATTERN.match(_strip_markdown(title)) is not None


def _extract_implementation_sections(content: str) -> tuple[str, list[str]]:
    lines = content.splitlines()
    extracted: list[str] = []
    output_lines: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            heading_text = _strip_markdown(line.lstrip("#").strip())
            if _is_implementation_details(heading_text):
                end_index = index + 1
                while end_index < len(lines):
                    next_line = lines[end_index]
                    if next_line.startswith("#"):
                        next_level = len(next_line) - len(next_line.lstrip("#"))
                        if next_level <= level:
                            break
                    end_index += 1
                section = "\n".join(lines[index:end_index]).strip()
                if section:
                    extracted.append(section)
                index = end_index
                continue
        output_lines.append(line)
        index += 1
    cleaned = "\n".join(output_lines).strip()
    return cleaned, extracted


def _normalize_heading_text(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("#"):
        stripped = stripped.lstrip("#").strip()
    stripped = _strip_markdown(stripped)
    stripped = " ".join(stripped.split())
    return stripped.casefold()


def _strip_duplicate_heading(heading: str, content: str) -> str:
    lines = content.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return content
    if _normalize_heading_text(lines[0]) == _normalize_heading_text(heading):
        return "\n".join(lines[1:]).lstrip()
    return content


def _write_nextsteps(output_dir: Path, sections: list[str]) -> None:
    if not sections:
        return
    nextsteps_content = "\n\n".join(
        section.strip() for section in sections if section.strip()
    ).strip()
    if not nextsteps_content:
        return
    nextsteps_path = output_dir / "nextsteps.md"
    nextsteps_path.write_text(nextsteps_content + "\n", encoding="utf-8")


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


def expand_chapter_content(
    content: str, client: LMStudioClient, tone: Optional[str] = None
) -> str:
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
            tone=tone,
        )
        expanded = client.generate(prompt)
        blocks[block_index].text = expanded.strip()

    return "\n\n".join(block.text for block in blocks)


def build_book_markdown(
    title: str,
    outline_text: str,
    chapters: List[str],
    byline: str,
) -> str:
    chapters_text = "\n\n".join(
        _sanitize_markdown_for_latex(chapter) for chapter in chapters
    )
    return (
        f"# {_sanitize_markdown_for_latex(title)}\n\n"
        f"### By {_sanitize_markdown_for_latex(byline)}\n\n"
        "\\newpage\n\n"
        "## Outline\n"
        f"{_sanitize_markdown_for_latex(outline_text)}\n\n"
        "\\newpage\n\n"
        f"{chapters_text}\n"
    )


def build_audiobook_text(title: str, byline: str, chapters: List[str]) -> str:
    header_parts = [title.strip(), f"By {byline}".strip()]
    header = "\n".join(part for part in header_parts if part).strip()
    sections = [header] if header else []
    sections.extend(chapter.strip() for chapter in chapters if chapter.strip())
    return "\n\n".join(sections).strip()


def _sanitize_markdown_for_latex(text: str) -> str:
    cleaned = "".join(
        ch
        for ch in text
        if unicodedata.category(ch) not in {"So", "Cs"} and ord(ch) <= 0xFFFF
    )
    return _escape_latex_commands_outside_math(cleaned)


def _escape_latex_commands_outside_math(text: str) -> str:
    output: list[str] = []
    in_code_block = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            output.append(line)
            continue
        if in_code_block:
            output.append(line)
            continue
        output.append(_escape_latex_line_outside_math(line))
    return "".join(output)


def _escape_latex_line_outside_math(line: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(line):
        if line[index] == "`":
            closing = line.find("`", index + 1)
            if closing != -1:
                result.append(line[index : closing + 1])
                index = closing + 1
                continue
        if line.startswith("$$", index):
            closing = line.find("$$", index + 2)
            if closing != -1:
                result.append(line[index : closing + 2])
                index = closing + 2
                continue
            result.append("\\$\\$")
            index += 2
            continue
        if line[index] == "$":
            closing = line.find("$", index + 1)
            if closing != -1:
                result.append(line[index : closing + 1])
                index = closing + 1
                continue
            result.append("\\$")
            index += 1
            continue
        if line.startswith("\\(", index):
            closing = line.find("\\)", index + 2)
            if closing != -1:
                result.append(line[index : closing + 2])
                index = closing + 2
                continue
        if line.startswith("\\[", index):
            closing = line.find("\\]", index + 2)
            if closing != -1:
                result.append(line[index : closing + 2])
                index = closing + 2
                continue
        if line[index] == "\\":
            result.append("\\textbackslash{}")
            index += 1
            continue
        result.append(line[index])
        index += 1
    return "".join(result)


def generate_book_pdf(
    output_dir: Path,
    title: str,
    outline_text: str,
    chapter_files: List[Path],
    byline: str,
) -> Path:
    chapters = [path.read_text(encoding="utf-8") for path in chapter_files]
    book_markdown = build_book_markdown(title, outline_text, chapters, byline)
    markdown_path = output_dir / "book.md"
    markdown_path.write_text(book_markdown, encoding="utf-8")
    pdf_path = output_dir / "book.pdf"
    try:
        subprocess.run(
            [
                "pandoc",
                str(markdown_path),
                "--from",
                "markdown-yaml_metadata_block",
                "--pdf-engine=xelatex",
                "-o",
                str(pdf_path),
            ],
            check=True,
        )
    except FileNotFoundError as exc:
        message = (
            "pandoc is required to generate PDFs but was not found on your PATH. "
            "Install pandoc (https://pandoc.org/installing.html) or ensure it is "
            "available in your PATH."
        )
        raise RuntimeError(message) from exc
    return pdf_path


def compile_book(output_dir: Path) -> Path:
    chapter_files = _chapter_files(output_dir)
    if not chapter_files:
        raise ValueError(f"No chapter markdown files found in {output_dir}.")
    book_metadata, byline = _read_book_metadata(output_dir, chapter_files)
    outline_text = book_metadata.content or _derive_outline_from_chapters(chapter_files)
    return generate_book_pdf(
        output_dir=output_dir,
        title=book_metadata.title,
        outline_text=outline_text,
        chapter_files=chapter_files,
        byline=byline,
    )


def generate_book_audio(
    output_dir: Path,
    tts_settings: TTSSettings,
    verbose: bool = False,
) -> List[Path]:
    if not tts_settings.enabled:
        return []
    chapter_files = _chapter_files(output_dir)
    if not chapter_files:
        raise ValueError(f"No chapter markdown files found in {output_dir}.")
    created: List[Path] = []
    audio_dir = output_dir / tts_settings.audio_dirname
    if not tts_settings.book_only:
        for chapter_file in chapter_files:
            audio_path = audio_dir / f"{chapter_file.stem}.mp3"
            if audio_path.exists() and not tts_settings.overwrite_audio:
                continue
            generated = synthesize_chapter_audio(
                chapter_path=chapter_file,
                output_dir=audio_dir,
                settings=tts_settings,
                verbose=verbose,
            )
            if generated:
                created.append(generated)

    book_metadata, byline = _read_book_metadata(output_dir, chapter_files)
    audiobook_text = build_audiobook_text(
        book_metadata.title,
        byline,
        [path.read_text(encoding="utf-8") for path in chapter_files],
    )
    book_audio_path = audio_dir / "book.mp3"
    if tts_settings.overwrite_audio or not book_audio_path.exists():
        try:
            generated = synthesize_text_audio(
                text=audiobook_text,
                output_path=book_audio_path,
                settings=tts_settings,
                verbose=verbose,
                raise_on_error=True,
            )
        except TTSSynthesisError as error:
            raise TTSSynthesisError(
                f"Failed to generate full audiobook audio: {error}"
            ) from error
        if generated:
            created.append(generated)

    if not tts_settings.book_only:
        synopsis_path = output_dir / "back-cover-synopsis.md"
        synopsis_audio_path = audio_dir / "back-cover-synopsis.mp3"
        if synopsis_path.exists() and (
            tts_settings.overwrite_audio or not synopsis_audio_path.exists()
        ):
            generated = synthesize_text_audio(
                text=synopsis_path.read_text(encoding="utf-8"),
                output_path=synopsis_audio_path,
                settings=tts_settings,
                verbose=verbose,
            )
            if generated:
                created.append(generated)
    return created


def generate_book_videos(
    output_dir: Path,
    video_settings: VideoSettings,
    audio_dirname: str = "audio",
    verbose: bool = False,
    client: LMStudioClient | None = None,
) -> List[Path]:
    if not video_settings.enabled:
        return []
    chapter_files = _chapter_files(output_dir)
    if not chapter_files:
        raise ValueError(f"No chapter markdown files found in {output_dir}.")
    image_theme: str | None = None
    if video_settings.paragraph_images.enabled:
        if client is None:
            raise ValueError(
                "LM Studio client is required to generate paragraph images."
            )
        book_metadata, _ = _read_book_metadata(output_dir, chapter_files)
        outline_text = book_metadata.content
        if not outline_text:
            outline_text = _derive_outline_from_chapters(chapter_files)
        image_theme = _generate_image_theme(
            client,
            book_metadata.title,
            outline_text,
        )
    created: List[Path] = []
    video_dir = output_dir / video_settings.video_dirname
    audio_dir = output_dir / audio_dirname
    for chapter_file in chapter_files:
        audio_path = audio_dir / f"{chapter_file.stem}.mp3"
        if not audio_path.exists():
            continue
        video_path = video_dir / f"{audio_path.stem}.mp4"
        if video_path.exists():
            continue
        chapter_text = chapter_file.read_text(encoding="utf-8")
        if video_settings.paragraph_images.enabled:
            image_paths, durations = _generate_paragraph_images(
                client,
                chapter_text,
                audio_path,
                output_dir,
                video_settings,
                image_theme or "",
                verbose=verbose,
            )
            generated = synthesize_chapter_video_from_images(
                audio_path=audio_path,
                output_dir=video_dir,
                image_paths=image_paths,
                durations=durations,
                settings=video_settings,
                verbose=verbose,
            )
        else:
            generated = synthesize_chapter_video(
                audio_path=audio_path,
                output_dir=video_dir,
                settings=video_settings,
                verbose=verbose,
                text=chapter_text,
            )
        if generated:
            created.append(generated)
        elif video_path.exists():
            created.append(video_path)
    return created


def _chapter_files(output_dir: Path) -> List[Path]:
    return sorted(
        path
        for path in output_dir.iterdir()
        if path.suffix == ".md"
        and path.name not in {"book.md", "back-cover-synopsis.md", "nextsteps.md"}
    )


def _clear_chapter_files(output_dir: Path) -> None:
    if not output_dir.exists():
        return
    for chapter_path in _chapter_files(output_dir):
        chapter_path.unlink()


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


def _read_book_metadata(
    output_dir: Path, chapter_files: List[Path]
) -> tuple[ChapterContext, str]:
    book_md = output_dir / "book.md"
    if book_md.exists():
        content = book_md.read_text(encoding="utf-8")
        title = "Untitled"
        byline = "Marissa Bard"
        outline = ""
        for line in content.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        for line in content.splitlines():
            if line.startswith("### By "):
                byline = line[len("### By ") :].strip()
                break
        if "## Outline" in content:
            outline_section = content.split("## Outline", 1)[1]
            outline = outline_section.split("\\newpage", 1)[0].strip()
        return ChapterContext(title=title, content=outline), byline

    outline = _derive_outline_from_chapters(chapter_files)
    title = chapter_files[0].stem if chapter_files else output_dir.name
    for line in chapter_files[0].read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    return ChapterContext(title=title, content=outline), "Marissa Bard"


def _chapter_title_from_content(content: str, fallback: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            candidate = stripped.lstrip("#").strip()
            if candidate:
                return candidate
    return fallback


def _read_cover_synopsis(output_dir: Path) -> str:
    synopsis_path = output_dir / "back-cover-synopsis.md"
    if synopsis_path.exists():
        return synopsis_path.read_text(encoding="utf-8").strip()
    return ""


def _split_markdown_paragraphs(content: str) -> list[str]:
    paragraphs: list[str] = []
    for block in re.split(r"\n\s*\n", content.strip()):
        if not block.strip():
            continue
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        content_lines = [
            line for line in lines if not line.lstrip().startswith("#")
        ]
        if not content_lines:
            continue
        paragraph = " ".join(content_lines).strip()
        if paragraph:
            paragraphs.append(paragraph)
    return paragraphs


def _paragraph_word_count(paragraph: str) -> int:
    cleaned = sanitize_markdown_for_tts(paragraph)
    return len(re.findall(r"\S+", cleaned))


def _calculate_paragraph_durations(
    paragraphs: list[str], audio_duration: float
) -> list[float]:
    if audio_duration <= 0:
        raise ValueError("Audio duration must be greater than zero.")
    weights = [max(_paragraph_word_count(p), 1) for p in paragraphs]
    total_weight = sum(weights)
    if total_weight <= 0:
        raise ValueError("Unable to calculate paragraph weights.")
    durations = [
        audio_duration * weight / total_weight for weight in weights
    ]
    if durations:
        remaining = audio_duration - sum(durations[:-1])
        durations[-1] = max(remaining, 0.1)
    return durations


def _generate_image_theme(
    client: LMStudioClient,
    book_title: str,
    outline_text: str,
) -> str:
    prompt = (
        "Define a cohesive visual theme for imagery in a book video. "
        "Use 1-2 sentences describing art style, palette, lighting, era, and mood. "
        "Avoid summarizing plot details or listing multiple options.\n\n"
        f"Book title: {book_title}\n"
        f"Outline:\n{outline_text}".strip()
    )
    return client.generate(prompt).strip()


def _describe_paragraph_image(
    client: LMStudioClient,
    theme: str,
    paragraph: str,
    last_image: str | None,
) -> str:
    last_image_text = last_image or "None yet."
    prompt = (
        "You are describing a single image for a book video.\n"
        f"Imagery theme: {theme}\n"
        f"Previous image: {last_image_text}\n"
        f"Paragraph: {paragraph}\n\n"
        "Describe one image that represents the paragraph, stays consistent with the "
        "theme, and flows logically from the previous image. "
        "Return 1-2 sentences. Do not use bullet points, quotes, or mention text."
    )
    return client.generate(prompt).strip()


def _generate_paragraph_images(
    client: LMStudioClient,
    chapter_text: str,
    audio_path: Path,
    output_dir: Path,
    video_settings: VideoSettings,
    theme: str,
    verbose: bool = False,
) -> tuple[list[Path], list[float]]:
    paragraphs = _split_markdown_paragraphs(chapter_text)
    if not paragraphs:
        raise ValueError("No paragraphs found for image generation.")
    duration = _probe_audio_duration(audio_path)
    if duration is None:
        raise RuntimeError(
            "ffprobe is required to align paragraph images with audio timing."
        )
    durations = _calculate_paragraph_durations(paragraphs, duration)
    image_settings = video_settings.paragraph_images
    image_dir = (
        output_dir / image_settings.image_dirname / audio_path.stem
    )
    last_image_description: str | None = None
    image_paths: list[Path] = []
    for index, paragraph in enumerate(paragraphs, start=1):
        description = _describe_paragraph_image(
            client, theme, paragraph, last_image_description
        )
        prompt = f"{theme}\n{description}".strip()
        output_path = image_dir / f"{audio_path.stem}-{index:03d}.png"
        generated = generate_paragraph_image(
            prompt=prompt,
            output_path=output_path,
            settings=image_settings,
            verbose=verbose,
        )
        if generated is None:
            raise RuntimeError("Failed to generate a paragraph image.")
        image_paths.append(generated)
        last_image_description = description
    return image_paths, durations


def _summarize_cover_text(
    client: LMStudioClient, text: str, context_label: str
) -> str:
    if not text.strip():
        return ""
    prompt = (
        f"Summarize the following {context_label} into a concise visual description "
        "for cover art. Focus on vivid imagery, setting, characters, and mood. "
        "Keep it under 400 characters and limit to 2-3 sentences. "
        "Return plain text only.\n\n"
        f"{text}"
    )
    summary = client.generate(prompt).strip()
    return summary or text


def generate_book_cover_asset(
    output_dir: Path,
    cover_settings: CoverSettings,
    client: Optional[LMStudioClient] = None,
) -> Optional[Path]:
    if not cover_settings.enabled:
        return None
    chapter_files = _chapter_files(output_dir)
    if not chapter_files:
        raise ValueError(f"No chapter markdown files found in {output_dir}.")
    book_metadata, _ = _read_book_metadata(output_dir, chapter_files)
    synopsis = _read_cover_synopsis(output_dir)
    if client:
        synopsis = _summarize_cover_text(
            client, synopsis, "book synopsis"
        )
    cover_settings = replace(cover_settings, output_name="cover.png")
    return generate_book_cover(
        output_dir=output_dir,
        title=book_metadata.title,
        synopsis=synopsis,
        settings=cover_settings,
    )


def generate_chapter_cover_assets(
    output_dir: Path,
    cover_settings: CoverSettings,
    chapter_cover_dir: str = "chapter_covers",
    chapter_files: Optional[Iterable[Path]] = None,
    client: Optional[LMStudioClient] = None,
) -> List[Path]:
    if not cover_settings.enabled:
        return []
    all_chapter_files = _chapter_files(output_dir)
    if not all_chapter_files:
        raise ValueError(f"No chapter markdown files found in {output_dir}.")
    if chapter_files is None:
        selected_chapters = list(all_chapter_files)
    else:
        resolved_all = {path.resolve() for path in all_chapter_files}
        resolved_selected = {path.resolve() for path in chapter_files}
        missing = [path for path in resolved_selected if path not in resolved_all]
        if missing:
            missing_names = ", ".join(sorted(path.name for path in missing))
            raise ValueError(
                f"Cover selection did not match chapter files: {missing_names}"
            )
        selected_chapters = [
            path
            for path in all_chapter_files
            if path.resolve() in resolved_selected
        ]
        if not selected_chapters:
            raise ValueError("Cover selection did not match any chapter files.")

    book_metadata, _ = _read_book_metadata(output_dir, all_chapter_files)
    cover_output_dir = output_dir / chapter_cover_dir
    generated: List[Path] = []
    for chapter_file in selected_chapters:
        content = chapter_file.read_text(encoding="utf-8")
        chapter_title = _chapter_title_from_content(content, chapter_file.stem)
        if client:
            content = _summarize_cover_text(
                client, content, f"chapter {chapter_title}"
            )
        settings = replace(
            cover_settings, output_name=f"{chapter_file.stem}.png"
        )
        output_path = generate_chapter_cover(
            output_dir=cover_output_dir,
            book_title=book_metadata.title,
            chapter_title=chapter_title,
            chapter_content=content,
            settings=settings,
        )
        if output_path:
            generated.append(output_path)
    return generated


def expand_book(
    output_dir: Path,
    client: LMStudioClient,
    passes: int = 1,
    verbose: bool = False,
    tts_settings: Optional[TTSSettings] = None,
    video_settings: Optional[VideoSettings] = None,
    cover_settings: Optional[CoverSettings] = None,
    tone: Optional[str] = None,
    chapter_files: Optional[Iterable[Path]] = None,
) -> List[Path]:
    auto_tts = tts_settings is None
    tts_settings = tts_settings or TTSSettings()
    video_settings = video_settings or VideoSettings()
    if passes < 1:
        raise ValueError("Expansion passes must be at least 1.")
    cover_settings = cover_settings or CoverSettings()
    all_chapter_files = _chapter_files(output_dir)
    if not all_chapter_files:
        raise ValueError(f"No chapter markdown files found in {output_dir}.")
    if chapter_files is None:
        selected_chapters = list(all_chapter_files)
    else:
        resolved_all = {path.resolve() for path in all_chapter_files}
        resolved_selected = {path.resolve() for path in chapter_files}
        missing = [
            path for path in resolved_selected if path not in resolved_all
        ]
        if missing:
            missing_names = ", ".join(sorted(path.name for path in missing))
            raise ValueError(
                f"Expand-only selection did not match chapter files: {missing_names}"
            )
        selected_chapters = [
            path
            for path in all_chapter_files
            if path.resolve() in resolved_selected
        ]
        if not selected_chapters:
            raise ValueError("Expand-only selection did not match any chapter files.")

    if verbose:
        print(f"[expand] Expanding book in {output_dir} with {passes} pass(es).")
    image_theme: str | None = None
    if video_settings.enabled and video_settings.paragraph_images.enabled:
        book_metadata, _ = _read_book_metadata(output_dir, all_chapter_files)
        outline_text = book_metadata.content
        if not outline_text:
            outline_text = _derive_outline_from_chapters(all_chapter_files)
        image_theme = _generate_image_theme(
            client,
            book_metadata.title,
            outline_text,
        )
    nextsteps_sections: list[str] = []
    for _ in range(passes):
        if verbose:
            print(f"[expand] Starting pass {_ + 1}/{passes}.")
        for index, chapter_file in enumerate(selected_chapters, start=1):
            if verbose:
                print(
                    f"[expand] Step {index}/{len(selected_chapters)}: "
                    f"Expanding {chapter_file.name}."
                )
            content = chapter_file.read_text(encoding="utf-8")
            expanded_content = expand_chapter_content(content, client, tone=tone)
            cleaned_content, extracted_sections = _extract_implementation_sections(
                expanded_content
            )
            nextsteps_sections.extend(extracted_sections)
            chapter_file.write_text(cleaned_content.strip() + "\n", encoding="utf-8")
            audio_dir = chapter_file.parent / tts_settings.audio_dirname
            audio_path = audio_dir / f"{chapter_file.stem}.mp3"
            effective_tts_settings = tts_settings
            if auto_tts and not tts_settings.enabled and audio_path.exists():
                effective_tts_settings = TTSSettings(
                    enabled=True,
                    voice=tts_settings.voice,
                    rate=tts_settings.rate,
                    pitch=tts_settings.pitch,
                    audio_dirname=tts_settings.audio_dirname,
                    overwrite_audio=tts_settings.overwrite_audio,
                    keep_model_loaded=tts_settings.keep_model_loaded,
                )
            audio_path = synthesize_chapter_audio(
                chapter_path=chapter_file,
                output_dir=audio_dir,
                settings=effective_tts_settings,
                verbose=verbose,
            )
            audio_path = audio_path or audio_dir / f"{chapter_file.stem}.mp3"
            if audio_path.exists() and video_settings.enabled:
                chapter_text = chapter_file.read_text(encoding="utf-8")
                if video_settings.paragraph_images.enabled:
                    image_paths, durations = _generate_paragraph_images(
                        client,
                        chapter_text,
                        audio_path,
                        output_dir,
                        video_settings,
                        image_theme or "",
                        verbose=verbose,
                    )
                    synthesize_chapter_video_from_images(
                        audio_path=audio_path,
                        output_dir=chapter_file.parent
                        / video_settings.video_dirname,
                        image_paths=image_paths,
                        durations=durations,
                        settings=video_settings,
                        verbose=verbose,
                    )
                else:
                    synthesize_chapter_video(
                        audio_path=audio_path,
                        output_dir=chapter_file.parent
                        / video_settings.video_dirname,
                        settings=video_settings,
                        verbose=verbose,
                        text=chapter_text,
                    )

    book_metadata, byline = _read_book_metadata(output_dir, all_chapter_files)
    outline_text = book_metadata.content
    if not outline_text:
        outline_text = _derive_outline_from_chapters(all_chapter_files)

    generate_book_pdf(
        output_dir=output_dir,
        title=book_metadata.title,
        outline_text=outline_text,
        chapter_files=all_chapter_files,
        byline=byline,
    )
    if verbose:
        print("[expand] Generated book.pdf from expanded chapters.")
    audiobook_text = build_audiobook_text(
        book_metadata.title,
        byline,
        [path.read_text(encoding="utf-8") for path in all_chapter_files],
    )
    try:
        synthesize_text_audio(
            text=audiobook_text,
            output_path=output_dir / tts_settings.audio_dirname / "book.mp3",
            settings=tts_settings,
            verbose=verbose,
            raise_on_error=True,
        )
    except TTSSynthesisError as error:
        raise TTSSynthesisError(
            f"Failed to generate full audiobook audio: {error}"
        ) from error
    if verbose:
        print("[expand] Wrote book.mp3 for full audiobook.")
    _write_nextsteps(output_dir, nextsteps_sections)
    if verbose and nextsteps_sections:
        print("[expand] Wrote nextsteps.md from implementation details.")
    if cover_settings.enabled:
        generate_book_cover_asset(output_dir, cover_settings, client=client)
        if verbose:
            print("[expand] Generated cover image.")
    return selected_chapters


def write_book(
    items: List[OutlineItem],
    output_dir: Path,
    client: LMStudioClient,
    verbose: bool = False,
    tts_settings: Optional[TTSSettings] = None,
    video_settings: Optional[VideoSettings] = None,
    cover_settings: Optional[CoverSettings] = None,
    book_title: Optional[str] = None,
    byline: str = "Marissa Bard",
    tone: Optional[str] = None,
    resume: bool = False,
    log_prompts: bool = False,
    outline_hash: Optional[str] = None,
) -> List[Path]:
    tts_settings = tts_settings or TTSSettings()
    video_settings = video_settings or VideoSettings()
    cover_settings = cover_settings or CoverSettings()
    output_dir.mkdir(parents=True, exist_ok=True)
    written_files: List[Path] = []
    index = 0
    previous_chapter: Optional[ChapterContext] = None
    nextsteps_sections: list[str] = []
    generation_items = [item for item in items if item.source != "bullet"]
    total_steps = len(generation_items)
    progress = load_book_progress(output_dir) if resume else None
    if progress and progress.get("status") == "in_progress" and resume:
        if (
            outline_hash
            and progress.get("outline_hash")
            and progress.get("outline_hash") != outline_hash
        ):
            clear_book_progress(output_dir)
            progress = None
        elif outline_hash and "outline_hash" not in progress:
            clear_book_progress(output_dir)
            progress = None
        elif progress.get("total_steps") == total_steps:
            index = int(progress.get("completed_steps", 0))
            previous_data = progress.get("previous_chapter")
            if previous_data:
                previous_chapter = ChapterContext(
                    title=previous_data.get("title", ""),
                    content=previous_data.get("content", ""),
                )
            nextsteps_sections = progress.get("nextsteps_sections", [])
            if book_title is None:
                book_title = progress.get("book_title")
            written_files = _chapter_files(output_dir)
            if verbose and index < total_steps:
                print(
                    f"[write] Resuming from step {index + 1}/{total_steps} in "
                    f"{output_dir}."
                )
        else:
            clear_book_progress(output_dir)
            progress = None
    elif progress:
        clear_book_progress(output_dir)
        progress = None

    if progress is not None and outline_hash and "outline_hash" not in progress:
        progress["outline_hash"] = outline_hash

    if progress is None:
        _clear_chapter_files(output_dir)
        progress = {
            "status": "in_progress",
            "total_steps": total_steps,
            "completed_steps": index,
            "previous_chapter": None,
            "nextsteps_sections": [],
            "book_title": book_title or (items[0].title if items else "Untitled"),
            "byline": byline,
        }
        if outline_hash:
            progress["outline_hash"] = outline_hash
        save_book_progress(output_dir, progress)

    image_theme: str | None = None
    if video_settings.enabled and video_settings.paragraph_images.enabled:
        title_for_theme = book_title or (
            items[0].title if items else "Untitled"
        )
        image_theme = _generate_image_theme(
            client,
            title_for_theme,
            outline_to_text(items),
        )

    while index < len(generation_items):
        item = generation_items[index]
        if verbose:
            print(
                f"[write] Step {index + 1}/{len(generation_items)}: "
                f"Generating {item.type_label} '{item.title}'."
            )
        prompt = build_prompt(items, item, previous_chapter, tone=tone)
        if log_prompts:
            full_prompt = client.render_prompt(prompt)
            print(
                f"[prompt] {item.type_label.title()} {index + 1}/{len(generation_items)}: "
                f"{item.title}\n{full_prompt}\n"
            )
        content = client.generate(prompt)
        heading = f"{item.heading_prefix} {item.title}"
        if _is_implementation_details(item.title):
            section_text = heading
            content = content.strip()
            if content:
                section_text = f"{heading}\n\n{content}"
            nextsteps_sections.append(section_text)
            if verbose:
                print("[write] Captured implementation details for nextsteps.md.")
        else:
            cleaned_content, extracted_sections = _extract_implementation_sections(
                content
            )
            nextsteps_sections.extend(extracted_sections)
            file_name = f"{index + 1:03d}-{slugify(item.display_title)}.md"
            file_path = output_dir / file_name
            file_body = _strip_duplicate_heading(heading, cleaned_content).strip()
            if file_body:
                file_path.write_text(
                    f"{heading}\n\n{file_body}\n", encoding="utf-8"
                )
            else:
                file_path.write_text(f"{heading}\n", encoding="utf-8")
            written_files.append(file_path)
            audio_path = synthesize_chapter_audio(
                chapter_path=file_path,
                output_dir=file_path.parent / tts_settings.audio_dirname,
                settings=tts_settings,
                verbose=verbose,
            )
            audio_path = audio_path or file_path.parent / tts_settings.audio_dirname / (
                f"{file_path.stem}.mp3"
            )
            if audio_path.exists() and video_settings.enabled:
                chapter_text = file_path.read_text(encoding="utf-8")
                if video_settings.paragraph_images.enabled:
                    image_paths, durations = _generate_paragraph_images(
                        client,
                        chapter_text,
                        audio_path,
                        output_dir,
                        video_settings,
                        image_theme or "",
                        verbose=verbose,
                    )
                    synthesize_chapter_video_from_images(
                        audio_path=audio_path,
                        output_dir=file_path.parent
                        / video_settings.video_dirname,
                        image_paths=image_paths,
                        durations=durations,
                        settings=video_settings,
                        verbose=verbose,
                    )
                else:
                    synthesize_chapter_video(
                        audio_path=audio_path,
                        output_dir=file_path.parent
                        / video_settings.video_dirname,
                        settings=video_settings,
                        verbose=verbose,
                        text=chapter_text,
                    )
            if verbose:
                print(f"[write] Wrote {file_path.name}.")
            if item.level == 1:
                context_prompt = build_chapter_context_prompt(
                    item.title, file_body or content, tone=tone
                )
                if log_prompts:
                    full_prompt = client.render_prompt(context_prompt)
                    print(
                        "[prompt] Chapter context summary "
                        f"{index + 1}/{len(items)}: {item.title}\n"
                        f"{full_prompt}\n"
                    )
                context_summary = client.generate(context_prompt)
                previous_chapter = ChapterContext(
                    title=item.title, content=context_summary
                )
                if verbose:
                    print(f"[write] Generated context summary for {item.title}.")
        progress["completed_steps"] = index + 1
        progress["previous_chapter"] = (
            {
                "title": previous_chapter.title,
                "content": previous_chapter.content,
            }
            if previous_chapter
            else None
        )
        progress["nextsteps_sections"] = nextsteps_sections
        progress["status"] = "in_progress"
        save_book_progress(output_dir, progress)
        index += 1

    _write_nextsteps(output_dir, nextsteps_sections)
    if verbose and nextsteps_sections:
        print("[write] Wrote nextsteps.md from implementation details.")
    book_title = book_title or items[0].title
    outline_text = outline_to_text(items)
    generate_book_pdf(
        output_dir=output_dir,
        title=book_title,
        outline_text=outline_text,
        chapter_files=written_files,
        byline=byline,
    )
    if verbose:
        print("[write] Generated book.pdf from chapters.")
    audiobook_text = build_audiobook_text(
        book_title,
        byline,
        [path.read_text(encoding="utf-8") for path in written_files],
    )
    try:
        synthesize_text_audio(
            text=audiobook_text,
            output_path=output_dir / tts_settings.audio_dirname / "book.mp3",
            settings=tts_settings,
            verbose=verbose,
            raise_on_error=True,
        )
    except TTSSynthesisError as error:
        raise TTSSynthesisError(
            f"Failed to generate full audiobook audio: {error}"
        ) from error
    if verbose:
        print("[write] Wrote book.mp3 for full audiobook.")
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
    synthesize_text_audio(
        text=synopsis,
        output_path=output_dir / tts_settings.audio_dirname / "back-cover-synopsis.mp3",
        settings=tts_settings,
        verbose=verbose,
    )
    if verbose:
        print("[write] Wrote back-cover-synopsis.md.")
    try:
        genres = generate_book_genres(client, synopsis)
    except (HTTPError, OSError, ValueError):
        genres = []
    if genres:
        write_book_meta(output_dir, genres)
        if verbose:
            print("[write] Wrote meta.json with genres.")
    if cover_settings.enabled:
        cover_synopsis = _summarize_cover_text(
            client, synopsis, "book synopsis"
        )
        cover_settings = replace(cover_settings, output_name="cover.png")
        generate_book_cover(
            output_dir=output_dir,
            title=book_title,
            synopsis=cover_synopsis,
            settings=cover_settings,
        )
        if verbose:
            print("[write] Generated cover image.")

    progress["status"] = "completed"
    progress["completed_steps"] = total_steps
    save_book_progress(output_dir, progress)
    return written_files
