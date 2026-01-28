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
_SIMPLE_GENRE_ORDER = [
    "Sci-Fi",
    "Fantasy",
    "Romance",
    "Drama",
    "Mystery",
    "Thriller",
    "Horror",
    "Historical",
    "Nonfiction",
    "Biography",
    "Adventure",
    "Young Adult",
    "Children",
    "Comedy",
]
_SIMPLE_GENRE_ALIASES = {
    "scifi": "Sci-Fi",
    "sciencefiction": "Sci-Fi",
    "fantasy": "Fantasy",
    "romance": "Romance",
    "drama": "Drama",
    "mystery": "Mystery",
    "thriller": "Thriller",
    "horror": "Horror",
    "historical": "Historical",
    "nonfiction": "Nonfiction",
    "biography": "Biography",
    "adventure": "Adventure",
    "youngadult": "Young Adult",
    "children": "Children",
    "comedy": "Comedy",
}
_SIMPLE_GENRE_KEYWORDS = {
    "Sci-Fi": {"scifi", "sciencefiction"},
    "Fantasy": {"fantasy"},
    "Romance": {"romance"},
    "Drama": {"drama"},
    "Mystery": {"mystery"},
    "Thriller": {"thriller"},
    "Horror": {"horror"},
    "Historical": {"historical", "history"},
    "Nonfiction": {"nonfiction"},
    "Biography": {"biography"},
    "Adventure": {"adventure"},
    "Young Adult": {"youngadult"},
    "Children": {"children"},
    "Comedy": {"comedy"},
}


def build_genre_prompt(synopsis: str) -> str:
    synopsis_text = synopsis.strip()
    return (
        "You are tagging book genres. Based on the synopsis below, return a JSON object "
        'with a key "genres" that contains an array of 1-3 genre strings. '
        "Use high-level categories like Thriller, Mystery, Sci-Fi, Romance, or Fantasy, "
        "not detailed subgenres. "
        "Return only JSON.\n\n"
        f"Synopsis:\n{synopsis_text}"
    )


def _meta_path(book_dir: Path) -> Path:
    return book_dir / META_FILENAME


def _normalize_genre(value: str) -> str:
    cleaned = re.sub(r"^[\s*\-•]+", "", value.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.rstrip(",.;")


def _genre_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


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


def _resolve_simple_genre(value: str) -> str | None:
    key = _genre_key(value)
    if not key:
        return None
    alias = _SIMPLE_GENRE_ALIASES.get(key)
    if alias:
        return alias
    for genre in _SIMPLE_GENRE_ORDER:
        keywords = _SIMPLE_GENRE_KEYWORDS.get(genre, {_genre_key(genre)})
        if any(keyword in key for keyword in keywords):
            return genre
    return None


def resolve_primary_genre(genres: Iterable[str]) -> str | None:
    normalized = _unique_preserve_order(genres)
    if not normalized:
        return None
    for genre in normalized:
        resolved = _resolve_simple_genre(genre)
        if resolved:
            return resolved
    return normalized[0]


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


def read_book_primary_genre(book_dir: Path) -> str | None:
    meta = read_book_meta(book_dir)
    primary = meta.get("primary_genre")
    if isinstance(primary, str):
        primary = _normalize_genre(primary)
        if primary:
            return primary
    genres = _coerce_genres(meta)
    return resolve_primary_genre(genres)


def read_book_language(book_dir: Path, default: str = "en") -> str:
    meta = read_book_meta(book_dir)
    language = meta.get("language") or meta.get("lang")
    if isinstance(language, str) and language.strip():
        return language.strip()
    return default


def write_book_meta(
    book_dir: Path,
    genres: Iterable[str],
    primary_genre: str | None = None,
) -> None:
    normalized = _unique_preserve_order(genres)[:GENRE_LIMIT]
    if not normalized:
        return
    meta = read_book_meta(book_dir)
    meta["genres"] = normalized
    resolved_primary = _normalize_genre(primary_genre) if primary_genre else None
    if resolved_primary:
        meta["primary_genre"] = resolved_primary
    else:
        resolved_primary = resolve_primary_genre(normalized)
        if resolved_primary:
            meta["primary_genre"] = resolved_primary
    meta_path = _meta_path(book_dir)
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ensure_book_identity(
    book_dir: Path, title: str | None = None, author: str | None = None
) -> bool:
    meta = read_book_meta(book_dir)
    updated = False
    if title and not meta.get("title"):
        meta["title"] = title
        updated = True
    if author and not meta.get("author"):
        meta["author"] = author
        updated = True
    if updated:
        meta_path = _meta_path(book_dir)
        meta_path.write_text(
            json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return updated


def ensure_book_chapters(
    book_dir: Path, chapters: Iterable[Mapping[str, object]]
) -> bool:
    normalized = [
        {
            "number": chapter.get("number"),
            "title": chapter.get("title"),
            "file": chapter.get("file"),
        }
        for chapter in chapters
        if chapter.get("number") and chapter.get("title")
    ]
    if not normalized:
        return False
    meta = read_book_meta(book_dir)
    if meta.get("chapters"):
        return False
    meta["chapters"] = normalized
    meta_path = _meta_path(book_dir)
    meta_path.write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return True


def ensure_primary_genre(book_dir: Path, genres: Iterable[str]) -> str | None:
    resolved = resolve_primary_genre(genres)
    if not resolved:
        return None
    meta = read_book_meta(book_dir)
    primary = meta.get("primary_genre")
    if isinstance(primary, str):
        primary = _normalize_genre(primary)
        if primary:
            return primary
    meta["primary_genre"] = resolved
    meta_path = _meta_path(book_dir)
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return resolved


def generate_book_genres(client: "LMStudioClient", synopsis: str) -> list[str]:
    if not synopsis.strip():
        return []
    prompt = build_genre_prompt(synopsis)
    response = client.generate(prompt)
    return parse_genres(response)
