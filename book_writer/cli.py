from __future__ import annotations

import argparse
from pathlib import Path

from book_writer.outline import parse_outline
from book_writer.writer import LMStudioClient, write_book


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate book chapters from OUTLINE.md.")
    parser.add_argument(
        "--outline",
        type=Path,
        default=Path("OUTLINE.md"),
        help="Path to the outline markdown file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory to write generated markdown files.",
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

    items = parse_outline(args.outline)
    if not items:
        parser.error("No outline items found in the outline file.")

    client = LMStudioClient(base_url=args.base_url, model=args.model, timeout=args.timeout)
    write_book(items=items, output_dir=args.output_dir, client=client)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
