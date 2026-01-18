from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List
from urllib import request

from book_writer.outline import OutlineItem, outline_to_text, slugify


class LMStudioClient:
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful writing assistant who writes in markdown.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
        }
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with request.urlopen(req, timeout=60) as response:
            body = response.read().decode("utf-8")
        parsed = json.loads(body)
        return parsed["choices"][0]["message"]["content"].strip()


def build_prompt(items: Iterable[OutlineItem], current: OutlineItem) -> str:
    outline_text = outline_to_text(items)
    context = ""
    if current.parent_title:
        context = f"The current section belongs to the chapter '{current.parent_title}'."
    return (
        "Write the next part of the book based on the outline. "
        "Return only markdown content for the requested item.\n\n"
        f"Outline:\n{outline_text}\n\n"
        f"Current item: {current.title} ({current.type_label}).\n"
        f"{context}".strip()
    )


def write_book(
    items: List[OutlineItem],
    output_dir: Path,
    client: LMStudioClient,
) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written_files: List[Path] = []
    index = 0

    while index < len(items):
        item = items[index]
        prompt = build_prompt(items, item)
        content = client.generate(prompt)
        heading = f"{item.heading_prefix} {item.title}"
        file_name = f"{index + 1:03d}-{slugify(item.display_title)}.md"
        file_path = output_dir / file_name
        file_path.write_text(f"{heading}\n\n{content}\n", encoding="utf-8")
        written_files.append(file_path)
        index += 1

    return written_files
