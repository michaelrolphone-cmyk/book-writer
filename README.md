# Book Writer

Generate full-length books from Markdown outlines using LM Studio, and expand completed books with additional depth and detail. This repository provides a CLI interface for generating chapters, compiling PDFs, and expanding existing books.

## Requirements

- Python 3.12+
- [LM Studio](https://lmstudio.ai/) running a compatible model and exposing the OpenAI-compatible API (default: `http://localhost:1234`).
- [`pandoc`](https://pandoc.org/) for compiling PDFs (required for `book.pdf` generation). PDF output also requires a LaTeX engine such as `pdflatex`.
- [`ffmpeg`](https://ffmpeg.org/) for generating chapter MP4 videos when `--video` is enabled.
- [`questionary`](https://github.com/tmbo/questionary) for the interactive `--prompt` experience (install with `pip install questionary`).
- [`python_coreml_stable_diffusion`](https://github.com/apple/ml-stable-diffusion) for generating book covers when `--cover` is enabled.

## Commands

### Launch the GUI server

```bash
python -m book_writer --gui --gui-host 127.0.0.1 --gui-port 8080
```

Open `http://127.0.0.1:8080` in your browser after the server starts. You can also launch the GUI from the interactive CLI by running `python -m book_writer --prompt` and choosing **Launch GUI server** from the first menu.

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
- `--video`: Generate MP4 chapter videos by looping a background MP4 with the chapter MP3 narration.
- `--background-video`: Path to a local MP4 file used as the looping video background.
- `--video-dir`: Directory name for storing chapter video files (default `video`).
- `--video-paragraph-images`: Generate MP4 chapter videos from per-paragraph images aligned to audio timing.
- `--video-image-dir`: Directory name for storing per-paragraph images (default `video_images`).
- `--video-image-model-path`: Path to the Core ML resources for paragraph image generation.
- `--video-image-module-path`: Path to the `python_coreml_stable_diffusion` module (default: `../ml-stable-diffusion`).
- `--video-image-negative-prompt`: Negative prompt for paragraph image generation.
- `--video-image-steps`: Inference steps for paragraph image generation.
- `--video-image-guidance-scale`: Guidance scale for paragraph image generation.
- `--video-image-seed`: Seed for paragraph image generation.
- `--video-image-width`: Width for paragraph image generation.
- `--video-image-height`: Height for paragraph image generation.
- `--video-image-overwrite`: Overwrite existing paragraph images.
- `--video-image-command`: Custom command template for paragraph image generation.
- `--cover`: Generate a book cover image using `python_coreml_stable_diffusion`.
- `--cover-model-path`: Path to the compiled Core ML resource folder for cover generation.
- `--cover-module-path`: Path to the `python_coreml_stable_diffusion` module (default: `../ml-stable-diffusion`).
- `--cover-prompt`: Override the generated cover prompt.
- `--cover-negative-prompt`: Negative prompt to avoid unwanted elements.
- `--cover-command`: Custom command template for cover generation (uses placeholders like `{prompt}` and `{output_path}`).
- `--byline`: Byline shown on the book title page (default `Marissa Bard`).
- `--author`: Author persona to load from the `authors/` folder (omit to use `PROMPT.md`).

**Outputs** (written under `output/`)
- Numbered chapter/section markdown files (e.g., `001-chapter-one.md`).
- `book.md`: Compiled markdown containing the title, outline, and chapters.
- `book.pdf`: Generated from `book.md` via pandoc.
- `back-cover-synopsis.md`: LM-generated synopsis.
- `cover.png`: Generated cover image (when `--cover` is enabled).
- `audio/*.mp3`: Chapter narration files (when `--tts` is enabled).
- `video/*.mp4`: Chapter video files (when `--video` is enabled).
- `video_images/*/*.png`: Generated paragraph images (when `--video-paragraph-images` is enabled).

### Generate multiple books from an outlines directory

```bash
python -m book_writer --outlines-dir outlines --books-dir books --completed-outlines-dir completed_outlines
```

**Inputs**
- `outlines/`: Directory containing one or more outline markdown files.

**Outputs**
- Each outline generates a subdirectory in `books/` containing chapter files, `book.md`, `book.pdf`, `back-cover-synopsis.md`, and `cover.png` when enabled.
- Processed outline files are moved into `completed_outlines/`.
- Chapter audio files are stored under each book's `audio/` directory when `--tts` is enabled.

### Expand an existing completed book

```bash
python -m book_writer --expand-book books/my-book --expand-passes 2
```

**Inputs**
- `--expand-book`: Path to a completed book directory containing chapter markdown files.
- `--expand-passes`: Number of expansion passes to run across the entire book (default `1`).
- `--expand-only`: Comma-separated list of chapter numbers, ranges, or filenames to expand (for example: `1,3-4,002-chapter-two.md`).

**Behavior**
- Each paragraph/section in every chapter is expanded using the previous and next paragraph context.
- After expansion completes, `book.pdf` is regenerated from updated content.

**Outputs**
- Updated chapter markdown files written in-place.
- Updated `book.md` and regenerated `book.pdf`.
- Regenerated `audio/*.mp3` files when `--tts` is enabled.
- Regenerated `video/*.mp4` files when `--video` is enabled.
- Updated `cover.png` when `--cover` is enabled.

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

- Author personas live in `authors/` as markdown files (for example, `authors/curious-storyteller.md`). Provide the filename stem with `--author` to select a persona.
- `pandoc` and `pdflatex` must be available on your PATH for PDF generation. On macOS, you can install both with Homebrew: `brew install pandoc mactex`.
- Install the `edge-tts` package (`pip install edge-tts`) to enable MP3 narration with the default neural voice.
- The expansion flow reuses existing chapter files; no new files are created beyond updated output artifacts.

## Future ideas

- Add a project config file for storing defaults like model settings, TTS options, and output paths.
- Introduce resume/retry checkpoints for long-running generation tasks.
- Build an outline linter to validate headings and chapter structure before generation.
- Support per-chapter metadata (tone, length targets, keywords) in outlines.
- Add more output formats (EPUB, DOCX) alongside PDF.
- Create a prompt template library with versioning for author personas.
- Track per-chapter generation metrics like token usage and timing.
- Allow expand-only subsets of chapters for targeted revisions.
- Add an interactive outline builder for non-technical authors.
- Expand audio/video controls with presets and normalization options.
