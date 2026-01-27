# Quilloquy architecture

This document summarizes the major components involved in generating books from Markdown outlines and how they connect.

## Architecture overview

![Quilloquy architecture overview](images/architecture-overview.svg)

## Core components

- **Outline sources**: Markdown files that define chapters and sections.
- **CLI / GUI**: Entry points that parse user inputs, validate options, and invoke generation flows.
- **Writer engine**: Core orchestration that expands outlines into chapters, handles tone/author prompts, and manages output paths.
- **Compilation**: Assembly layer that stitches chapter markdown into `book.md` and uses Pandoc for `book.pdf` output.
- **Media generation**: Optional TTS audio, video creation, and cover/illustration pipelines.
- **Book outputs**: The final book directory containing chapter markdown, PDFs, media, and metadata.

## Data and artifact flow

1. **Outline selection**: A Markdown outline is selected through the CLI or GUI.
2. **Chapter generation**: The writer engine uses LM Studio to generate chapter text for each outline heading.
3. **Compilation**: Generated chapters are stitched into `book.md`, then compiled into `book.pdf`.
4. **Optional media**: Audio, video, and cover assets are generated when enabled.
5. **Delivery**: The completed book folder is ready for review, expansion, or distribution.

## Supporting services

- **LM Studio**: Provides the OpenAI-compatible inference endpoint for chapter generation and summaries.
- **Pandoc / LaTeX**: Compiles `book.md` into a PDF.
- **Qwen3 TTS / FFmpeg**: Produces narrated audio and combines audio with video assets when requested.
- **Stable Diffusion (Core ML)**: Generates cover and paragraph imagery when enabled.
