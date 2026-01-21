from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable, Optional


def _default_module_path() -> Path:
    project_root = Path(__file__).resolve().parents[1]
    return (project_root / ".." / "ml-stable-diffusion").resolve()


@dataclass(frozen=True)
class CoverSettings:
    enabled: bool = False
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    model_path: Optional[Path] = None
    module_path: Optional[Path] = field(default_factory=_default_module_path)
    steps: int = 30
    guidance_scale: float = 7.5
    seed: Optional[int] = None
    width: int = 768
    height: int = 1024
    output_name: str = "cover.png"
    overwrite: bool = False
    command: Optional[list[str]] = None


DEFAULT_COVER_COMMAND = [
    "swift",
    "run",
    "StableDiffusionSample",
    "{prompt}",
    "{negative_prompt_flag}",
    "{negative_prompt}",
    "--resource-path",
    "{model_path}",
    "{seed_flag}",
    "{seed}",
    "--output-path",
    "{output_dir}",
]

DEFAULT_NEGATIVE_PROMPT = (
    "text, letters, typography, watermark, logo, signature"
)
DEFAULT_COVER_GUIDANCE = (
    "Cinematic scene illustration. "
    "No text, no typography, no letters, no watermark, no logo."
)


def build_cover_prompt(title: str, synopsis: str) -> str:
    synopsis_text = _truncate_prompt_text(synopsis)
    prompt = (
        "Illustrate a cinematic scene. "
        f"Visualize: {synopsis_text} "
        "Moody lighting, highly detailed."
    ).strip()
    return _ensure_cover_prompt(prompt)


def build_chapter_cover_prompt(
    book_title: str, chapter_title: str, chapter_content: str
) -> str:
    lines = [
        line.strip()
        for line in chapter_content.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    summary = " ".join(lines) or chapter_title
    summary_text = _truncate_prompt_text(summary)
    prompt = (
        "Illustrate a cinematic scene inspired by the chapter. "
        f"Visualize: {summary_text} "
        "Moody lighting, highly detailed."
    ).strip()
    return _ensure_cover_prompt(prompt)


def _render_command(
    template: Iterable[str],
    *,
    prompt: str,
    negative_prompt: Optional[str],
    model_path: Optional[Path],
    seed: Optional[int],
    steps: int,
    guidance_scale: float,
    width: int,
    height: int,
    output_path: Path,
    output_dir: Path,
) -> list[str]:
    values = {
        "prompt": prompt,
        "negative_prompt": negative_prompt or "",
        "negative_prompt_flag": "--negative-prompt" if negative_prompt else "",
        "model_path": str(model_path) if model_path else "",
        "model_path_flag": "--model-path" if model_path else "",
        "seed": str(seed) if seed is not None else "",
        "seed_flag": "--seed" if seed is not None else "",
        "steps": str(steps),
        "guidance_scale": str(guidance_scale),
        "width": str(width),
        "height": str(height),
        "output_path": str(output_path),
        "output_dir": str(output_dir),
    }
    rendered: list[str] = []
    for token in template:
        formatted = token.format(**values)
        if not formatted:
            continue
        rendered.append(formatted)
    return rendered


def _resolve_command(
    settings: CoverSettings,
    prompt: str,
    output_path: Path,
    output_dir: Path,
    *,
    model_path: Optional[Path] = None,
) -> list[str]:
    template = settings.command or DEFAULT_COVER_COMMAND
    return _render_command(
        template,
        prompt=prompt,
        negative_prompt=settings.negative_prompt,
        model_path=model_path if model_path is not None else settings.model_path,
        seed=settings.seed,
        steps=settings.steps,
        guidance_scale=settings.guidance_scale,
        width=settings.width,
        height=settings.height,
        output_path=output_path,
        output_dir=output_dir,
    )


def _build_cover_env(module_path: Optional[Path]) -> dict[str, str]:
    env = os.environ.copy()
    if module_path:
        module_value = str(module_path)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{module_value}{os.pathsep}{existing}"
            if existing
            else module_value
        )
    return env


def parse_cover_command(command: Optional[str]) -> Optional[list[str]]:
    if not command:
        return None
    return shlex.split(command)


def _infer_default_model_path(module_path: Optional[Path]) -> Optional[Path]:
    if not module_path:
        return None
    candidate = (
        module_path
        / ".."
        / "coreml-stable-diffusion-v1-4"
        / "original"
        / "compiled"
    ).resolve()
    if candidate.exists():
        return candidate
    return None


def generate_book_cover(
    output_dir: Path,
    title: str,
    synopsis: str,
    settings: CoverSettings,
) -> Optional[Path]:
    if not settings.enabled:
        return None
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / settings.output_name
    if output_path.exists() and not settings.overwrite:
        return output_path
    if settings.overwrite and output_path.exists():
        output_path.unlink()
    existing_paths = {path.resolve() for path in output_dir.rglob("*.png")}
    if settings.command is None and not settings.model_path:
        inferred_path = _infer_default_model_path(settings.module_path)
        if inferred_path:
            settings = replace(settings, model_path=inferred_path)
        else:
            raise ValueError(
                "Cover generation requires a --cover-model-path when using the "
                "default swift command. Place the Core ML resources at "
                "../coreml-stable-diffusion-v1-4/original/compiled or pass "
                "--cover-model-path explicitly."
            )
    prompt = _ensure_cover_prompt(settings.prompt or build_cover_prompt(title, synopsis))
    negative_prompt = _merge_negative_prompt(settings.negative_prompt)
    command = _resolve_command(
        replace(settings, negative_prompt=negative_prompt),
        prompt,
        output_path,
        output_dir,
    )
    try:
        subprocess.run(
            command,
            check=True,
            env=_build_cover_env(settings.module_path),
            cwd=str(settings.module_path) if settings.module_path else None,
        )
    except FileNotFoundError as exc:
        message = (
            "Cover generation command not found. "
            "Ensure it is installed and available in your PATH or set --cover-command."
        )
        raise RuntimeError(message) from exc
    if output_path.exists():
        return output_path
    candidates = [
        path
        for path in output_dir.rglob("*.png")
        if path.resolve() not in existing_paths
    ]
    if not candidates:
        candidates = list(output_dir.rglob("*.png"))
    candidates = sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)
    if candidates:
        candidates[0].replace(output_path)
    return output_path


def generate_chapter_cover(
    output_dir: Path,
    book_title: str,
    chapter_title: str,
    chapter_content: str,
    settings: CoverSettings,
) -> Optional[Path]:
    if not settings.enabled:
        return None
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / settings.output_name
    if output_path.exists() and not settings.overwrite:
        return output_path
    if settings.overwrite and output_path.exists():
        output_path.unlink()
    existing_paths = {path.resolve() for path in output_dir.rglob("*.png")}
    if settings.command is None and not settings.model_path:
        inferred_path = _infer_default_model_path(settings.module_path)
        if inferred_path:
            settings = replace(settings, model_path=inferred_path)
        else:
            raise ValueError(
                "Cover generation requires a --cover-model-path when using the "
                "default swift command. Place the Core ML resources at "
                "../coreml-stable-diffusion-v1-4/original/compiled or pass "
                "--cover-model-path explicitly."
            )
    prompt = _ensure_cover_prompt(
        settings.prompt
        or build_chapter_cover_prompt(book_title, chapter_title, chapter_content)
    )
    negative_prompt = _merge_negative_prompt(settings.negative_prompt)
    command = _resolve_command(
        replace(settings, negative_prompt=negative_prompt),
        prompt,
        output_path,
        output_dir,
    )
    try:
        subprocess.run(
            command,
            check=True,
            env=_build_cover_env(settings.module_path),
            cwd=str(settings.module_path) if settings.module_path else None,
        )
    except FileNotFoundError as exc:
        message = (
            "Cover generation command not found. "
            "Ensure it is installed and available in your PATH or set --cover-command."
        )
        raise RuntimeError(message) from exc
    if output_path.exists():
        return output_path
    candidates = [
        path
        for path in output_dir.rglob("*.png")
        if path.resolve() not in existing_paths
    ]
    if not candidates:
        candidates = list(output_dir.rglob("*.png"))
    candidates = sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)
    if candidates:
        candidates[0].replace(output_path)
    return output_path


def _truncate_prompt_text(text: str) -> str:
    text_value = " ".join(text.split())
    if len(text_value) > 600:
        return text_value[:597].rstrip() + "..."
    return text_value


def _ensure_cover_prompt(prompt: str) -> str:
    prompt_value = prompt.strip()
    prompt_lower = prompt_value.lower()
    if "no text" in prompt_lower and (
        "no typography" in prompt_lower or "no letters" in prompt_lower
    ):
        return prompt_value
    return f"{prompt_value} {DEFAULT_COVER_GUIDANCE}".strip()


def _merge_negative_prompt(negative_prompt: Optional[str]) -> str:
    if negative_prompt:
        negative_value = negative_prompt.strip()
        if DEFAULT_NEGATIVE_PROMPT.lower() in negative_value.lower():
            return negative_value
        return f"{negative_value}, {DEFAULT_NEGATIVE_PROMPT}"
    return DEFAULT_NEGATIVE_PROMPT
