# Quilloquy

Generate full-length books from Markdown outlines using LM Studio, and expand completed books with additional depth and detail. Quilloquy provides a CLI interface for generating chapters, compiling PDFs/EPUBs, and expanding existing books.

## Requirements

- Python 3.12+
- [LM Studio](https://lmstudio.ai/) running a compatible model and exposing the OpenAI-compatible API (default: `http://localhost:1234`).
- [`pandoc`](https://pandoc.org/) for compiling PDFs/EPUBs (required for `book.pdf` and `book.epub` generation). PDF output also requires a LaTeX engine such as `pdflatex`.
- Optional LaTeX `background.sty` (from the `background` package) to render chapter cover backgrounds; if unavailable, PDF compilation skips background artwork.
- [`ffmpeg`](https://ffmpeg.org/) for converting Qwen3 TTS audio to MP3 and for generating chapter MP4 videos when `--video` is enabled.
- [`qwen_tts`](https://github.com/QwenLM/Qwen3-TTS) with compatible model weights, plus `torch` and `soundfile`, for local Qwen3 narration.
- [`questionary`](https://github.com/tmbo/questionary) for the interactive `--prompt` experience (install with `pip install questionary`).
- [`python_coreml_stable_diffusion`](https://github.com/apple/ml-stable-diffusion) for generating book covers when `--cover` is enabled.

## Documentation

- Architecture and component responsibilities: [`documentation/architecture.md`](documentation/architecture.md)
- Generation workflows and sequence diagrams: [`documentation/workflows.md`](documentation/workflows.md)

## Commands

The CLI commands and GUI API endpoints are summarized in the quick reference below for fast lookup.

### CLI & API quick reference

**CLI commands**
- `python -m book_writer --gui --gui-host 127.0.0.1 --gui-port 8080` (launch GUI server)
- `python -m book_writer --outline OUTLINE.md --output-dir output` (generate a single book)
- `python -m book_writer --outlines-dir outlines --books-dir books --completed-outlines-dir completed_outlines` (batch generate)
- `python -m book_writer --expand-book books/my-book --expand-passes 2 --expand-only 1,3-4` (expand a finished book)
- `python -m book_writer --cover-book books/my-book --cover` (generate a new cover)
- `python -m book_writer --chapter-covers-book books/my-book --chapter-cover-dir chapter_covers` (generate chapter covers)
- `python -m book_writer --prompt` (interactive outline and book workflow, including **Modify existing books → Generate compiled book.pdf and book.epub**)
- `python -m book_writer --help` (full CLI option list)

**GUI API endpoints**
- `GET /` (GUI HTML)
- `GET /api/books` (book catalog, including `genres`, `primary_genre`, `folder_created` timestamps for newest sorting, overall `progress` completion totals, and `book_pdf_url`/`book_epub_url` for the GUI Open PDF/EPUB actions; titles prefer `meta.json` when available)
- `GET /api/outlines`, `GET /api/completed-outlines` (catalogs)
- `GET /api/authors`, `GET /api/tones` (author and tone options)
- `GET /api/chapters?book_dir=books/my-book` (chapter list for a book)
- `GET /api/book-content?book_dir=books/my-book` (book markdown content)
- `GET /api/chapter-content?book_dir=books/my-book&chapter=1&audio_dirname=audio&video_dirname=video&chapter_cover_dir=chapter_covers` (chapter markdown + media URLs)
- `GET /api/outline-content?outline_path=outlines/my-outline.md` (outline markdown)
- `GET /api/book-progress?book_dir=books/my-book&audio_dirname=audio&video_dirname=video&chapter_cover_dir=chapter_covers`
- `POST /api/generate-book`, `POST /api/expand-book`, `POST /api/compile-book`
- `POST /api/generate-audio`, `POST /api/generate-videos`
- `POST /api/generate-cover`, `POST /api/generate-chapter-covers`
- `POST /api/generate-outline`, `POST /api/save-outline`
- `POST /api/rename-book-title`, `POST /api/rename-chapter-title` (update book or chapter titles used in the GUI)
- `POST /api/git-pull-restart` (pull latest code and restart GUI server)
- `GET /media` (chapter audio/video/cover assets, plus compiled `book.pdf`/`book.epub` files when requested by `path=book.pdf` or `path=book.epub`)

**GUI API example commands**
- Compile a book: `curl -X POST http://127.0.0.1:8080/api/compile-book -H "Content-Type: application/json" -d '{"book_dir":"books/my-book"}'`
  - The compiler builds the PDF/EPUB table of contents from chapter files, inserts a copyright page before the TOC, and omits outline sections in `book.md`.
- Expand a book: `curl -X POST http://127.0.0.1:8080/api/expand-book -H "Content-Type: application/json" -d '{"book_dir":"books/my-book","expand_passes":1}'`
- Generate a book cover: `curl -X POST http://127.0.0.1:8080/api/generate-cover -H "Content-Type: application/json" -d '{"book_dir":"books/my-book"}'`
- Generate chapter covers: `curl -X POST http://127.0.0.1:8080/api/generate-chapter-covers -H "Content-Type: application/json" -d '{"book_dir":"books/my-book","chapter_cover_dir":"chapter_covers"}'`
### CLI quick reference

- Launch GUI: `python -m book_writer --gui --gui-host 127.0.0.1 --gui-port 8080`
- Generate from one outline: `python -m book_writer --outline OUTLINE.md --output-dir output`
- Batch-generate from outlines: `python -m book_writer --outlines-dir outlines --books-dir books`
- Expand a completed book: `python -m book_writer --expand-book books/my-book --expand-passes 2`
- Generate cover assets: `python -m book_writer --cover-book books/my-book --cover`
- Compile an existing book: `python -m book_writer --prompt` (choose **Modify existing books** → **Generate compiled book.pdf and book.epub**)
  - Compilation builds the PDF/EPUB table of contents from chapter files, inserts a copyright page before the TOC, and omits outline sections in `book.md`.

### Launch the GUI server

```bash
python -m book_writer --gui --gui-host 127.0.0.1 --gui-port 8080
```

Open `http://127.0.0.1:8080` in your browser after the server starts. You can also launch the GUI from the interactive CLI by running `python -m book_writer --prompt` and choosing **Launch GUI server** from the first menu.
Run `python -m book_writer --help` for the full CLI command reference.

### CLI commands

Use these common CLI entry points to run the workflow without the interactive prompt.

```bash
# Generate a new book from an outline
python -m book_writer --outline OUTLINE.md --output-dir output

# Expand an existing book in place
python -m book_writer --expand-book output/My_Book --expand-passes 2

# Compile a finished book (PDF/EPUB depending on your setup)
python -m book_writer --compile-book output/My_Book

# Generate audio narration for an existing book
python -m book_writer --generate-audio output/My_Book --tts-overwrite
```

### Generate a single book from an outline

```bash
python -m book_writer --outline OUTLINE.md --output-dir output
```

**Inputs**
- `OUTLINE.md`: Markdown headings describing chapters (`#`) and sections (`##`).
- `--base-url`: LM Studio API base URL (default `http://localhost:1234`).
- `--model`: LM Studio model name (default `local-model`).
- `--timeout`: Optional request timeout in seconds.
- `--no-tts`: Disable MP3 narration (TTS is enabled by default).
- `--tts-voice`: Qwen3 speaker name for narration (default `Ryan`).
- `--tts-language`: Qwen3 language label (default `English`).
- `--tts-instruct`: Optional Qwen3 instruction prompt (for example: `Very happy.`).
- `--tts-model-path`: Path to the Qwen3 TTS model directory (default `../audio/models/Qwen3-TTS-12Hz-1.7B-CustomVoice`).
- `--tts-device-map`: Qwen3 device map (e.g., `auto`, `mps`, `cuda`).
- `--tts-dtype`: Torch dtype for Qwen3 (default `float16`; e.g., `float32`, `float16`).
- `--tts-attn-implementation`: Attention implementation for Qwen3 (default `sdpa`).
- `--tts-rate`: Rate adjustment for legacy TTS (unused by Qwen3).
- `--tts-pitch`: Pitch adjustment for legacy TTS (unused by Qwen3).
- `--tts-audio-dir`: Directory name for storing chapter audio files (default `audio`).
- `--tts-max-text-tokens`: Maximum text tokens per Qwen3 TTS chunk (default `384`).
- `--tts-max-new-tokens`: Maximum generated tokens per Qwen3 TTS chunk (default `2048`).
- `--tts-do-sample`: Enable sampling for Qwen3 TTS generation (default deterministic).
- `--tts-overwrite`: Overwrite existing audio files.
- `--tts-book-only`: Only generate a full-book MP3 (`book.mp3`).
- `--tts-unload-model`: Unload the Qwen3 model between chapters to reduce memory usage.
- Narration input is sanitized to remove Markdown/HTML formatting (code blocks, tables, images, etc.) before Qwen3 TTS to reduce malformed audio.
- Qwen3 tokenizer loading enables the Mistral regex fix when supported to prevent incorrect tokenization.
- `--video`: Generate MP4 chapter videos by looping a background MP4 with the chapter MP3 narration.
- `--background-video`: Path to a local MP4 file used as the looping video background.
- `--video-dir`: Directory name for storing chapter video files (default `video`).
- `--video-paragraph-images`: Generate MP4 chapter videos from per-paragraph images aligned to audio timing.
- `--video-image-dir`: Directory name for storing per-paragraph images (default `video_images`).
- `--video-image-model-path`: Path to the Core ML resources for paragraph image generation.
- `--video-image-module-path`: Path to the `python_coreml_stable_diffusion` module (default: `../ml-stable-diffusion`).
- `--video-image-negative-prompt`: Negative prompt for paragraph image generation.
- `--video-image-steps`: Inference steps for paragraph image generation (default `30`).
- `--video-image-guidance-scale`: Guidance scale for paragraph image generation (default `7.5`).
- `--video-image-seed`: Seed for paragraph image generation.
- `--video-image-width`: Width for paragraph image generation (default `1280`).
- `--video-image-height`: Height for paragraph image generation (default `720`).
- `--video-image-overwrite`: Overwrite existing paragraph images.
- `--video-image-command`: Custom command template for paragraph image generation.
- `--cover`: Generate a book cover image using `python_coreml_stable_diffusion`.
- `--cover-prompt`: Override the generated cover prompt.
- `--cover-negative-prompt`: Negative prompt to avoid unwanted elements.
- `--cover-model-path`: Path to the compiled Core ML resource folder for cover generation.
- `--cover-module-path`: Path to the `python_coreml_stable_diffusion` module (default: `../ml-stable-diffusion`).
- `--cover-steps`: Inference steps for cover generation (default `30`).
- `--cover-guidance-scale`: Guidance scale (CFG) for cover generation (default `7.5`).
- `--cover-seed`: Random seed for cover generation.
- `--cover-width`: Output width for the cover image (default `2560`).
- `--cover-height`: Output height for the cover image (default `1600`).
- `--cover-output-name`: Output filename for the cover image (default `cover.png`).
- `--cover-overwrite`: Overwrite any existing cover image.
- `--cover-command`: Custom command template for cover generation (uses placeholders like `{prompt}` and `{output_path}`).
- `--byline`: Byline shown on the book title page (default `Marissa Bard`).
- `--tone`: Tone for chapter generation and expansion (default `instructive self help guide`).
- `--author`: Author persona to load from the `authors/` folder (omit to use `PROMPT.md`).
- `--prompt`: Launch the interactive prompt flow for selecting outlines, tones, and tasks.

**Outputs** (written under `output/`)
- Numbered chapter/section markdown files (e.g., `001-chapter-one.md`).
- `book.md`: Compiled markdown containing cover/title pages (when no cover image is present), a copyright page, table of contents, chapter title pages, and chapters. Front matter uses raw HTML/LaTeX blocks for cover/title/copyright sections so EPUB readers don't display stray fenced div delimiters, while still emitting the correct HTML/CSS and LaTeX layout for pandoc. The front matter uses `title-meta`/`author-meta` for metadata while keeping `title`/`author` empty so pandoc does not inject an extra title page during PDF/EPUB compilation.
- Chapter YAML metadata blocks at the start of chapter files are stripped during compilation so pandoc YAML parsing is limited to the book-level front matter (avoiding invalid alias errors like `*Style`).
- Thematic breaks written as a standalone `---` line inside chapters are rewritten to `* * *` in `book.md` to avoid pandoc misinterpreting mid-book metadata blocks.
- Book, chapter, and byline text is sanitized for LaTeX output (escaping characters like `&`, `%`, and `_`) to prevent pandoc/LaTeX compilation errors.
- `book.pdf`: Generated from `book.md` via pandoc, incorporating cover art, chapter cover pages, and a table of contents plus back-cover synopsis when available.
- `book.epub`: Generated from `book.md` via pandoc for ebook readers (includes EPUB metadata, a navigable NCX table of contents, and default CSS with relative margins). The EPUB cover image is set from `cover.png` so reader apps display the cover consistently.
- `epub.css`: Default stylesheet applied to EPUB output to keep typography and margins compliant with ebook readers, including full-page chapter cover styling and explicit page breaks.
- `back-cover-synopsis.md`: LM-generated synopsis.
- `meta.json`: LM-generated metadata (including `title`, `author`, `chapters` with numbers/titles/filenames, `genres`, `primary_genre`, and an optional `language` field used for EPUB metadata).
- `cover.png`: Generated cover image (when `--cover` is enabled).
- `chapter_covers/*.png`: Per-chapter cover images (when chapter covers are generated).
- `audio/*.mp3`: Chapter narration files (when `--tts` is enabled).
- `video/*.mp4`: Chapter video files (when `--video` is enabled).
- `video_images/*/*.png`: Generated paragraph images (when `--video-paragraph-images` is enabled).
- When `meta.json` chapter titles are edited, chapter markdown and related assets (audio/video/cover/summary/video_images) are renamed on the next metadata read using chapter numbers as the stable identifier.

### Generate multiple books from an outlines directory

```bash
python -m book_writer --outlines-dir outlines --books-dir books --completed-outlines-dir completed_outlines
```

**Inputs**
- `outlines/`: Directory containing one or more outline markdown files.

**Outputs**
- Each outline generates a subdirectory in `books/` containing chapter files, `book.md`, `book.pdf`, `book.epub`, `back-cover-synopsis.md`, `cover.png`, and `chapter_covers/` when enabled.
- Processed outline files are moved into `completed_outlines/`.
- Chapter audio files are stored under each book's `audio/` directory when `--tts` is enabled.

### Run the interactive prompt flow

```bash
python -m book_writer --prompt
```

**Behavior**
- Choose whether to create new books or manage existing ones.
- When generating new books, select the outlines to generate once from the checklist prompt.

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
- After expansion completes, `book.pdf` and `book.epub` are regenerated from updated content.

**Outputs**
- Updated chapter markdown files written in-place.
- Updated `book.md` and regenerated `book.pdf`/`book.epub`.
- Regenerated `audio/*.mp3` files when `--tts` is enabled.
- Regenerated `video/*.mp4` files when `--video` is enabled.
- Updated `cover.png` and `chapter_covers/` when cover generation is enabled.

### Generate cover assets for an existing book

```bash
python -m book_writer --cover-book books/my-book --cover --cover-prompt "A modern sci-fi panorama"
```

```bash
python -m book_writer --chapter-covers-book books/my-book --chapter-cover-dir chapter_covers
```

**Inputs**
- `--cover-book`: Path to a completed book directory to generate a new `cover.png`.
- `--chapter-covers-book`: Path to a completed book directory to generate per-chapter covers.
- `--chapter-cover-dir`: Directory name for chapter cover output (default `chapter_covers`).
- All cover-related settings listed in **Generate a single book from an outline** also apply.

**PDF compilation**
- `book.pdf` and `book.epub` use `cover.png` as the front cover, with EPUB compilation referencing the same image for cover metadata to satisfy common reader requirements. Chapter cover images from `chapter_covers/` (matching chapter file stems with `.png`, `.jpg`, `.jpeg`, or `.webp` extensions) power full-bleed chapter title pages with overlaid titles, and `back-cover-synopsis.md` is used for the back cover when those assets are present.

**Note**
- Cover synopsis and chapter content are truncated to 6,000 characters before summarization to avoid exceeding model context limits during cover prompt generation.
- Cover images are generated at 2560×1600 (1.6:1) by default to satisfy minimum 300 PPI EPUB cover standards; override dimensions only if you maintain the same aspect ratio and minimum size.

### CLI option reference

These options are available across the CLI flows:

- Outline selection: `--outline`, `--outlines-dir`, `--output-dir`, `--books-dir`, `--completed-outlines-dir`
- Expansion: `--expand-book`, `--expand-passes`, `--expand-only`
- LM Studio: `--base-url`, `--model`, `--timeout`, `--author`
- Tone and byline: `--tone`, `--byline`
- TTS: `--no-tts`, `--tts-voice`, `--tts-language`, `--tts-instruct`, `--tts-model-path`, `--tts-device-map`, `--tts-dtype`, `--tts-attn-implementation`, `--tts-rate`, `--tts-pitch`, `--tts-audio-dir`, `--tts-max-text-tokens`, `--tts-max-new-tokens`, `--tts-do-sample`, `--tts-overwrite`, `--tts-book-only`, `--tts-unload-model`
- Video: `--video`, `--background-video`, `--video-dir`, `--video-paragraph-images`, `--video-image-dir`, `--video-image-negative-prompt`, `--video-image-model-path`, `--video-image-module-path`, `--video-image-steps`, `--video-image-guidance-scale`, `--video-image-seed`, `--video-image-width`, `--video-image-height`, `--video-image-overwrite`, `--video-image-command`
- Cover: `--cover`, `--cover-prompt`, `--cover-negative-prompt`, `--cover-model-path`, `--cover-module-path`, `--cover-steps`, `--cover-guidance-scale`, `--cover-seed`, `--cover-width`, `--cover-height`, `--cover-output-name`, `--cover-overwrite`, `--cover-command`, `--cover-book`, `--chapter-covers-book`, `--chapter-cover-dir`
- Interactive and GUI: `--prompt`, `--gui`, `--gui-host`, `--gui-port`

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
- `pandoc` and `pdflatex` must be available on your PATH for PDF generation. EPUB output only needs pandoc. On macOS, you can install both with Homebrew: `brew install pandoc mactex`.
- Install the Qwen3 dependencies (`qwen_tts`, `torch`, and `soundfile`) and download the Qwen3 model weights to enable local MP3 narration.
- The expansion flow reuses existing chapter files; no new files are created beyond updated output artifacts.

## GUI API

The GUI talks to a built-in HTTP server launched with `--gui`. All endpoints live under the same host/port used to serve the HTML. Responses are JSON unless noted.

### Endpoint reference

**GET**
- `/api/books`
- `/api/outlines`
- `/api/completed-outlines`
- `/api/authors`
- `/api/tones`
- `/api/chapters`
- `/api/outline-content`
- `/api/chapter-content`
- `/api/book-content`
- `/api/book-progress`
- `/media`

**POST**
- `/api/generate-book`
- `/api/expand-book`
- `/api/compile-book`
- `/api/generate-audio`
- `/api/generate-videos`
- `/api/generate-cover`
- `/api/generate-chapter-covers`
- `/api/generate-outline`
- `/api/save-outline`

### Shared request settings

Most POST endpoints accept these optional fields to align with CLI behavior:

- `base_url`, `model`, `timeout`, `author`: LM Studio configuration (same defaults as the CLI).
- `tone`, `byline`, `resume`, `verbose`: Generation controls.
- `tts_settings` object:
  - `enabled`, `voice`, `language`, `instruct`, `model_path`, `device_map`, `dtype`, `attn_implementation`, `rate`, `pitch`, `audio_dirname`, `max_text_tokens`, `max_new_tokens`, `do_sample`, `overwrite_audio`, `book_only`, `keep_model_loaded`
- `video_settings` object:
  - `enabled`, `background_video`, `video_dirname`
  - `paragraph_images` object: `enabled`, `image_dirname`, `negative_prompt`, `model_path`, `module_path`, `steps`, `guidance_scale`, `seed`, `width`, `height`, `overwrite`, `command`
- `cover_settings` object:
  - `enabled`, `prompt`, `negative_prompt`, `model_path`, `module_path`, `steps`, `guidance_scale`, `seed`, `width`, `height`, `output_name`, `overwrite`, `command`

### API endpoints

The GUI server exposes JSON endpoints under the same host/port used for the GUI (for example `http://127.0.0.1:8080`).

### GET endpoints

- `GET /`
  - Returns the GUI HTML page.
- `GET /api/outlines?outlines_dir=outlines`
  - Returns `{ outlines: [{ path, title, preview, item_count }] }`.
- `GET /api/completed-outlines?completed_outlines_dir=completed_outlines`
  - Returns `{ outlines: [...] }` for archived outlines.
- `GET /api/books?books_dir=books&tts_audio_dir=audio&video_dir=video`
  - Returns `{ books: [{ path, title, has_text, has_audio, has_video, has_compilation, has_cover, chapter_count, page_count, summary, genres, folder_created, cover_url, book_audio_url }] }`.
  - `genres` are populated from each book's `meta.json`. If the file is missing, the server will generate it in the background using the synopsis so the GUI can group books by genre.
  - `folder_created` is the book directory creation timestamp (seconds since epoch) used for latest-book sorting in the GUI.
- `GET /api/authors?authors_dir=authors`
  - Returns `{ authors: ["persona-name", ...] }`.
- `GET /api/tones?tones_dir=book_writer/tones`
  - Returns `{ tones: ["tone-name", ...] }`.
- `GET /api/chapters?book_dir=/path/to/book&audio_dirname=audio&video_dirname=video&chapter_cover_dir=chapter_covers`
  - Returns `{ chapters: [{ index, name, stem, title, page_count, summary, cover_url, audio_url, video_url }] }`.
- `GET /api/outline-content?outline_path=/path/to/outline.md`
  - Returns `{ outline_path, title, content, item_count }`.
- `GET /api/chapter-content?book_dir=/path/to/book&chapter=1&audio_dirname=audio&video_dirname=video&chapter_cover_dir=chapter_covers`
  - Returns `{ chapter, title, content, page_count, summary, cover_url, audio_url, video_url }`.
- `GET /api/book-content?book_dir=/path/to/book`
  - Returns `{ book_dir, title, summary, synopsis }`.
- `GET /api/book-progress?book_dir=/path/to/book&audio_dirname=audio&video_dirname=video&chapter_cover_dir=chapter_covers`
  - Returns `{ book_dir, title, completion, book, chapters, totals }` for images/summaries/audio/video completion by book and chapter, including an overall percent.
- `GET /media?book_dir=/path/to/book&path=audio/book.mp3`
  - Streams static assets (audio/video/images) referenced by `*_url` fields.

### POST endpoints

- `POST /api/generate-book`
  - Body: `{ outline_path, output_dir, book_title?, byline?, tone?, resume?, verbose?, ...shared settings }`.
  - Returns `{ written_files, output_dir }`.
- `POST /api/expand-book`
  - Body: `{ expand_book, expand_passes?, expand_only?, tone?, ...shared settings }`.
  - Returns `{ status: "expanded", book_dir }`.
- `POST /api/compile-book`
  - Body: `{ book_dir }`.
  - Returns `{ status: "compiled", book_dir }`.
- `POST /api/generate-audio`
  - Body: `{ book_dir, ...shared settings }` (uses `tts_settings`).
  - Returns `{ status: "audio_generated", book_dir }`.
- `POST /api/generate-videos`
  - Body: `{ book_dir, audio_dirname?, ...shared settings }` (uses `video_settings`).
  - Returns `{ status: "videos_generated", book_dir }`.
- `POST /api/generate-cover`
  - Body: `{ book_dir, ...shared settings }` (uses `cover_settings`).
  - Returns `{ status: "cover_generated", book_dir }`.
- `POST /api/generate-chapter-covers`
  - Body: `{ book_dir, chapter?, chapter_cover_dir?, ...shared settings }`.
  - Returns `{ status: "chapter_covers_generated", book_dir, generated }`.
- `POST /api/generate-outline`
  - Body: `{ prompt, outlines_dir?, outline_path?, outline_name?, revision_prompts?, ...shared settings }`.
  - Returns `{ outline_path, title, content, item_count }`.
- `POST /api/save-outline`
  - Body: `{ outline_path, outlines_dir?, content }`.
  - Returns `{ outline_path, title, content, item_count }`.

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
