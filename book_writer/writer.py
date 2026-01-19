from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional
from urllib import request
from urllib.error import HTTPError

from book_writer.outline import OutlineItem, outline_to_text, slugify
from book_writer.tts import TTSSettings, synthesize_chapter_audio, synthesize_text_audio
from book_writer.video import VideoSettings, synthesize_chapter_video


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
        prompt = f"{_base_prompt()}\n\n{prompt}".strip()
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


def _base_prompt() -> str:
    prompt_path = Path(__file__).resolve().parents[1] / "PROMPT.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Base prompt file not found at {prompt_path}.")
    return prompt_path.read_text(encoding="utf-8").strip()


def build_prompt(
    items: Iterable[OutlineItem],
    current: OutlineItem,
    previous_chapter: Optional[ChapterContext] = None,
    tone: Optional[str] = None,
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
        f"{_tone_preface(tone)}"
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


def build_book_title_prompt(outline_text: str, first_chapter_title: str) -> str:
    return (
        "Generate a compelling book title based on the outline. "
        "Do not reuse the first chapter name as the title. "
        "Return only the title text.\n\n"
        f"First chapter: {first_chapter_title}\n\n"
        f"Outline:\n{outline_text}"
    )


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


def _strip_duplicate_heading(heading: str, content: str) -> str:
    lines = content.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and lines[0].strip() == heading.strip():
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
    return "".join(
        ch
        for ch in text
        if unicodedata.category(ch) not in {"So", "Cs"} and ord(ch) <= 0xFFFF
    )


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


def _chapter_files(output_dir: Path) -> List[Path]:
    return sorted(
        path
        for path in output_dir.iterdir()
        if path.suffix == ".md"
        and path.name not in {"book.md", "back-cover-synopsis.md", "nextsteps.md"}
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


def expand_book(
    output_dir: Path,
    client: LMStudioClient,
    passes: int = 1,
    verbose: bool = False,
    tts_settings: Optional[TTSSettings] = None,
    video_settings: Optional[VideoSettings] = None,
    tone: Optional[str] = None,
) -> List[Path]:
    auto_tts = tts_settings is None
    tts_settings = tts_settings or TTSSettings()
    video_settings = video_settings or VideoSettings()
    if passes < 1:
        raise ValueError("Expansion passes must be at least 1.")
    chapter_files = _chapter_files(output_dir)
    if not chapter_files:
        raise ValueError(f"No chapter markdown files found in {output_dir}.")

    if verbose:
        print(f"[expand] Expanding book in {output_dir} with {passes} pass(es).")
    nextsteps_sections: list[str] = []
    for _ in range(passes):
        if verbose:
            print(f"[expand] Starting pass {_ + 1}/{passes}.")
        for index, chapter_file in enumerate(chapter_files, start=1):
            if verbose:
                print(
                    f"[expand] Step {index}/{len(chapter_files)}: "
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
                )
            audio_path = synthesize_chapter_audio(
                chapter_path=chapter_file,
                output_dir=audio_dir,
                settings=effective_tts_settings,
                verbose=verbose,
            )
            audio_path = audio_path or audio_dir / f"{chapter_file.stem}.mp3"
            if audio_path.exists():
                synthesize_chapter_video(
                    audio_path=audio_path,
                    output_dir=chapter_file.parent / video_settings.video_dirname,
                    settings=video_settings,
                    verbose=verbose,
                )

    book_metadata, byline = _read_book_metadata(output_dir, chapter_files)
    outline_text = book_metadata.content
    if not outline_text:
        outline_text = _derive_outline_from_chapters(chapter_files)

    generate_book_pdf(
        output_dir=output_dir,
        title=book_metadata.title,
        outline_text=outline_text,
        chapter_files=chapter_files,
        byline=byline,
    )
    if verbose:
        print("[expand] Generated book.pdf from expanded chapters.")
    audiobook_text = build_audiobook_text(
        book_metadata.title,
        byline,
        [path.read_text(encoding="utf-8") for path in chapter_files],
    )
    synthesize_text_audio(
        text=audiobook_text,
        output_path=output_dir / tts_settings.audio_dirname / "book.mp3",
        settings=tts_settings,
        verbose=verbose,
    )
    if verbose:
        print("[expand] Wrote book.mp3 for full audiobook.")
    _write_nextsteps(output_dir, nextsteps_sections)
    if verbose and nextsteps_sections:
        print("[expand] Wrote nextsteps.md from implementation details.")
    return chapter_files


def write_book(
    items: List[OutlineItem],
    output_dir: Path,
    client: LMStudioClient,
    verbose: bool = False,
    tts_settings: Optional[TTSSettings] = None,
    video_settings: Optional[VideoSettings] = None,
    book_title: Optional[str] = None,
    byline: str = "Marissa Bard",
    tone: Optional[str] = None,
) -> List[Path]:
    tts_settings = tts_settings or TTSSettings()
    video_settings = video_settings or VideoSettings()
    output_dir.mkdir(parents=True, exist_ok=True)
    written_files: List[Path] = []
    index = 0
    previous_chapter: Optional[ChapterContext] = None
    nextsteps_sections: list[str] = []

    while index < len(items):
        item = items[index]
        if verbose:
            print(
                f"[write] Step {index + 1}/{len(items)}: "
                f"Generating {item.type_label} '{item.title}'."
            )
        prompt = build_prompt(items, item, previous_chapter, tone=tone)
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
            if audio_path.exists():
                synthesize_chapter_video(
                    audio_path=audio_path,
                    output_dir=file_path.parent / video_settings.video_dirname,
                    settings=video_settings,
                    verbose=verbose,
                )
            if verbose:
                print(f"[write] Wrote {file_path.name}.")
            if item.level == 1:
                context_prompt = build_chapter_context_prompt(
                    item.title, file_body or content
                )
                context_summary = client.generate(context_prompt)
                previous_chapter = ChapterContext(
                    title=item.title, content=context_summary
                )
                if verbose:
                    print(f"[write] Generated context summary for {item.title}.")
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
    synthesize_text_audio(
        text=audiobook_text,
        output_path=output_dir / tts_settings.audio_dirname / "book.mp3",
        settings=tts_settings,
        verbose=verbose,
    )
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

    return written_files
