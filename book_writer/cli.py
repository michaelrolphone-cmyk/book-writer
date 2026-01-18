from __future__ import annotations

import argparse
from typing import Optional
from pathlib import Path

from book_writer.outline import parse_outline, parse_outline_with_title
from book_writer.tts import TTSSettings
from book_writer.writer import (
    LMStudioClient,
    expand_book,
    generate_book_title,
    write_book,
)


def _outline_files(outlines_dir: Path) -> list[Path]:
    if not outlines_dir.exists():
        return []
    return sorted(path for path in outlines_dir.iterdir() if path.suffix == ".md")


def write_books_from_outlines(
    outlines_dir: Path,
    books_dir: Path,
    completed_outlines_dir: Path,
    client: LMStudioClient,
    verbose: bool = False,
    tts_settings: Optional[TTSSettings] = None,
    byline: str = "Marissa Bard",
) -> list[Path]:
    tts_settings = tts_settings or TTSSettings()
    written_files: list[Path] = []
    outline_files = _outline_files(outlines_dir)
    if not outline_files:
        raise ValueError(f"No outline markdown files found in {outlines_dir}.")

    completed_outlines_dir.mkdir(parents=True, exist_ok=True)
    books_dir.mkdir(parents=True, exist_ok=True)

    for index, outline_path in enumerate(outline_files, start=1):
        if verbose:
            print(
                f"[batch] Step {index}/{len(outline_files)}: "
                f"Writing book for {outline_path.name}."
            )
        outline_title, items = parse_outline_with_title(outline_path)
        if not items:
            raise ValueError(f"No outline items found in {outline_path}.")
        book_title = outline_title or generate_book_title(items, client)

        book_short_title = outline_path.stem
        book_output_dir = books_dir / book_short_title
        written_files.extend(
            write_book(
                items=items,
                output_dir=book_output_dir,
                client=client,
                verbose=verbose,
                tts_settings=tts_settings,
                book_title=book_title,
                byline=byline,
            )
        )

        destination = completed_outlines_dir / outline_path.name
        outline_path.replace(destination)
        if verbose:
            print(f"[batch] Archived outline to {destination}.")

    return written_files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate book chapters from OUTLINE.md.")
    parser.add_argument(
        "--outline",
        type=Path,
        default=Path("OUTLINE.md"),
        help="Path to the outline markdown file.",
    )
    parser.add_argument(
        "--outlines-dir",
        type=Path,
        default=Path("outlines"),
        help="Directory containing multiple outline markdown files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory to write generated markdown files.",
    )
    parser.add_argument(
        "--expand-book",
        type=Path,
        default=None,
        help="Path to a completed book directory to expand.",
    )
    parser.add_argument(
        "--expand-passes",
        type=int,
        default=1,
        help="Number of expansion passes to run when expanding a completed book.",
    )
    parser.add_argument(
        "--books-dir",
        type=Path,
        default=Path("books"),
        help="Directory to write book subfolders when using batch outlines.",
    )
    parser.add_argument(
        "--completed-outlines-dir",
        type=Path,
        default=Path("completed_outlines"),
        help="Directory to move completed outline markdown files.",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:1234",
        help="Base URL for the LM Studio API.",
    )
    parser.add_argument(
        "--model",
        default="local-model",
        help="Model name exposed by LM Studio.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Timeout in seconds for the API call. Omit for no timeout.",
    )
    parser.add_argument(
        "--tts",
        action="store_true",
        help="Generate MP3 narration for each chapter using TTS.",
    )
    parser.add_argument(
        "--tts-voice",
        default="en-US-JennyNeural",
        help="Voice name for TTS narration (default: en-US-JennyNeural).",
    )
    parser.add_argument(
        "--tts-rate",
        default="+0%",
        help="Rate adjustment for TTS narration (e.g., '+5%').",
    )
    parser.add_argument(
        "--tts-pitch",
        default="+0Hz",
        help="Pitch adjustment for TTS narration (e.g., '+2Hz').",
    )
    parser.add_argument(
        "--tts-audio-dir",
        default="audio",
        help="Directory name for storing chapter audio files.",
    )
    parser.add_argument(
        "--byline",
        default="Marissa Bard",
        help="Byline shown on the book title page.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    client = LMStudioClient(base_url=args.base_url, model=args.model, timeout=args.timeout)
    tts_settings = TTSSettings(
        enabled=args.tts,
        voice=args.tts_voice,
        rate=args.tts_rate,
        pitch=args.tts_pitch,
        audio_dirname=args.tts_audio_dir,
    )
    if args.expand_book:
        expand_book(
            output_dir=args.expand_book,
            client=client,
            passes=args.expand_passes,
            verbose=True,
            tts_settings=tts_settings,
        )
        return 0
    outline_files = _outline_files(args.outlines_dir)
    if outline_files:
        try:
            write_books_from_outlines(
                outlines_dir=args.outlines_dir,
                books_dir=args.books_dir,
                completed_outlines_dir=args.completed_outlines_dir,
                client=client,
                verbose=True,
                tts_settings=tts_settings,
                byline=args.byline,
            )
        except ValueError as exc:
            parser.error(str(exc))
        return 0

    outline_title, items = parse_outline_with_title(args.outline)
    if not items:
        parser.error("No outline items found in the outline file.")
    book_title = outline_title or generate_book_title(items, client)
    write_book(
        items=items,
        output_dir=args.output_dir,
        client=client,
        verbose=True,
        tts_settings=tts_settings,
        book_title=book_title,
        byline=args.byline,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
