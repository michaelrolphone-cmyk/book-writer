# Book Writer

Generate full-length books from Markdown outlines using LM Studio, and expand completed books with additional depth and detail. This repository provides a CLI interface for generating chapters, compiling PDFs, and expanding existing books.

## Requirements

- Python 3.12+
- [LM Studio](https://lmstudio.ai/) running a compatible model and exposing the OpenAI-compatible API (default: `http://localhost:1234`).
- [`pandoc`](https://pandoc.org/) for compiling PDFs (required for `book.pdf` generation). PDF output also requires a LaTeX engine such as `pdflatex`.

## Commands

### Generate a single book from an outline

```bash
python -m book_writer --outline OUTLINE.md --output-dir output
```

**Inputs**
- `OUTLINE.md`: Markdown headings describing chapters (`#`) and sections (`##`).
- `--base-url`: LM Studio API base URL (default `http://localhost:1234`).
- `--model`: LM Studio model name (default `local-model`).
- `--timeout`: Optional request timeout in seconds.
- `--tts`: Generate MP3 narration for each chapter using TTS.
- `--tts-voice`: Voice name for TTS narration (default `en-US-JennyNeural`).
- `--tts-rate`: Rate adjustment for TTS narration (e.g., `+5%`).
- `--tts-pitch`: Pitch adjustment for TTS narration (e.g., `+2Hz`).
- `--tts-audio-dir`: Directory name for storing chapter audio files (default `audio`).

**Outputs** (written under `output/`)
- Numbered chapter/section markdown files (e.g., `001-chapter-one.md`).
- `book.md`: Compiled markdown containing the title, outline, and chapters.
- `book.pdf`: Generated from `book.md` via pandoc.
- `back-cover-synopsis.md`: LM-generated synopsis.
- `audio/*.mp3`: Chapter narration files (when `--tts` is enabled).

### Generate multiple books from an outlines directory

```bash
python -m book_writer --outlines-dir outlines --books-dir books --completed-outlines-dir completed_outlines
```

**Inputs**
- `outlines/`: Directory containing one or more outline markdown files.

**Outputs**
- Each outline generates a subdirectory in `books/` containing chapter files, `book.md`, `book.pdf`, and `back-cover-synopsis.md`.
- Processed outline files are moved into `completed_outlines/`.
- Chapter audio files are stored under each book's `audio/` directory when `--tts` is enabled.

### Expand an existing completed book

```bash
python -m book_writer --expand-book books/my-book --expand-passes 2
```

**Inputs**
- `--expand-book`: Path to a completed book directory containing chapter markdown files.
- `--expand-passes`: Number of expansion passes to run across the entire book (default `1`).

**Behavior**
- Each paragraph/section in every chapter is expanded using the previous and next paragraph context.
- After expansion completes, `book.pdf` is regenerated from updated content.

**Outputs**
- Updated chapter markdown files written in-place.
- Updated `book.md` and regenerated `book.pdf`.
- Regenerated `audio/*.mp3` files when `--tts` is enabled.

## Outline format

Use Markdown headings to define chapters and sections. Examples:

```markdown
# Chapter One
## Section One
## Section Two
# Chapter Two
```

Headings starting with “Chapter” or “Section” at any heading level are also accepted.

## Notes

- `pandoc` and `pdflatex` must be available on your PATH for PDF generation. On macOS, you can install both with Homebrew: `brew install pandoc mactex`.
- Install the `edge-tts` package (`pip install edge-tts`) to enable MP3 narration with the default neural voice.
- The expansion flow reuses existing chapter files; no new files are created beyond updated output artifacts.
