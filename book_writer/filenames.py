from __future__ import annotations

import re


_TITLE_WORD_RE = re.compile(r"[A-Za-z0-9]+")


def title_to_filename(title: str, fallback: str = "Untitled") -> str:
    words = _TITLE_WORD_RE.findall(title or "")
    if not words:
        return fallback
    return "".join(word.capitalize() for word in words) or fallback


def epub_filename(title: str, fallback: str = "Untitled") -> str:
    return f"{title_to_filename(title, fallback)}.epub"


def book_audio_filename(title: str, fallback: str = "Untitled") -> str:
    return f"{title_to_filename(title, fallback)}.mp3"
