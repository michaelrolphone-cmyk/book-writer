from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Mapping, TYPE_CHECKING

if TYPE_CHECKING:
    from book_writer.writer import LMStudioClient

META_FILENAME = "meta.json"
GENRE_LIMIT = 3
_JSON_BLOCK_RE = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)


def build_genre_prompt(synopsis: str) -> str:
    synopsis_text = synopsis.strip()
    return (
        "You are tagging book genres. Based on the synopsis below, return a JSON object "
        'with a key "genres" that contains an array of 1-3 genre strings. '
        "Return only JSON.\n\n"
        f"Synopsis:\n{synopsis_text}"
    )


def _meta_path(book_dir: Path) -> Path:
    return book_dir / META_FILENAME


def _normalize_genre(value: str) -> str:
    cleaned = re.sub(r"^[\s*\-•]+", "", value.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.rstrip(",.;")


def _unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = _normalize_genre(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _extract_json(text: str) -> object | None:
    if not text:
        return None
    trimmed = text.strip()
    for candidate in (trimmed,):
        if candidate.startswith("{") or candidate.startswith("["):
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
    match = _JSON_BLOCK_RE.search(trimmed)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def _coerce_genres(data: object) -> list[str]:
    if isinstance(data, list):
        return _unique_preserve_order([str(item) for item in data])
    if isinstance(data, Mapping):
        genres = data.get("genres")
        if isinstance(genres, list):
            return _unique_preserve_order([str(item) for item in genres])
        if isinstance(genres, str):
            return _unique_preserve_order(_split_genres(genres))
    if isinstance(data, str):
        return _unique_preserve_order(_split_genres(data))
    return []


def _split_genres(value: str) -> list[str]:
    if not value:
        return []
    separators = r"[,/;\n]"
    return [chunk.strip() for chunk in re.split(separators, value) if chunk.strip()]


def parse_genres(response: str) -> list[str]:
    parsed = _extract_json(response)
    if parsed is not None:
        genres = _coerce_genres(parsed)
        return genres[:GENRE_LIMIT]
    return _unique_preserve_order(_split_genres(response))[:GENRE_LIMIT]


def read_book_meta(book_dir: Path) -> dict[str, object]:
    meta_path = _meta_path(book_dir)
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def read_book_genres(book_dir: Path) -> list[str]:
    meta = read_book_meta(book_dir)
    genres = _coerce_genres(meta)
    return genres[:GENRE_LIMIT]


def write_book_meta(book_dir: Path, genres: Iterable[str]) -> None:
    normalized = _unique_preserve_order(genres)[:GENRE_LIMIT]
    if not normalized:
        return
    meta = read_book_meta(book_dir)
    meta["genres"] = normalized
    meta_path = _meta_path(book_dir)
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def generate_book_genres(client: "LMStudioClient", synopsis: str) -> list[str]:
    if not synopsis.strip():
        return []
    prompt = build_genre_prompt(synopsis)
    response = client.generate(prompt)
    return parse_genres(response)
