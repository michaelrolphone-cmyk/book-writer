from __future__ import annotations

import argparse
from pathlib import Path

from book_writer.outline import parse_outline
from book_writer.writer import LMStudioClient, expand_book, write_book


def _outline_files(outlines_dir: Path) -> list[Path]:
    if not outlines_dir.exists():
        return []
    return sorted(path for path in outlines_dir.iterdir() if path.suffix == ".md")


def write_books_from_outlines(
    outlines_dir: Path,
    books_dir: Path,
    completed_outlines_dir: Path,
    client: LMStudioClient,
) -> list[Path]:
    written_files: list[Path] = []
    outline_files = _outline_files(outlines_dir)
    if not outline_files:
        raise ValueError(f"No outline markdown files found in {outlines_dir}.")

    completed_outlines_dir.mkdir(parents=True, exist_ok=True)
    books_dir.mkdir(parents=True, exist_ok=True)

    for outline_path in outline_files:
        items = parse_outline(outline_path)
        if not items:
            raise ValueError(f"No outline items found in {outline_path}.")

        book_short_title = outline_path.stem
        book_output_dir = books_dir / book_short_title
        written_files.extend(
            write_book(items=items, output_dir=book_output_dir, client=client)
        )

        destination = completed_outlines_dir / outline_path.name
        outline_path.replace(destination)

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
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    client = LMStudioClient(base_url=args.base_url, model=args.model, timeout=args.timeout)
    if args.expand_book:
        expand_book(
            output_dir=args.expand_book,
            client=client,
            passes=args.expand_passes,
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
            )
        except ValueError as exc:
            parser.error(str(exc))
        return 0

    items = parse_outline(args.outline)
    if not items:
        parser.error("No outline items found in the outline file.")
    write_book(items=items, output_dir=args.output_dir, client=client)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
