import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from book_writer.cover import (
    CoverSettings,
    build_cover_prompt,
    generate_book_cover,
    parse_cover_command,
)
from book_writer.writer import generate_book_cover_asset


class TestCover(unittest.TestCase):
    def test_build_cover_prompt_includes_title_and_synopsis(self) -> None:
        synopsis = "A sweeping tale of discovery and resilience."

        prompt = build_cover_prompt("Starbound", synopsis)

        self.assertIn("Starbound", prompt)
        self.assertIn("discovery and resilience", prompt)
        self.assertIn("No text", prompt)

    def test_build_cover_prompt_truncates_long_synopsis(self) -> None:
        synopsis = " ".join(["word"] * 400)

        prompt = build_cover_prompt("Long Tale", synopsis)

        self.assertLessEqual(len(prompt), 800)
        self.assertIn("...", prompt)

    def test_parse_cover_command_splits_tokens(self) -> None:
        command = "python -m tool --prompt \"{prompt}\" --output {output_path}"

        parsed = parse_cover_command(command)

        self.assertEqual(parsed[0], "python")
        self.assertIn("--prompt", parsed)

    @patch("book_writer.cover.subprocess.run")
    def test_generate_book_cover_runs_command(self, run_mock: Mock) -> None:
        settings = CoverSettings(enabled=True, module_path=Path("/tmp/coreml"))
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = generate_book_cover(
                output_dir=output_dir,
                title="My Book",
                synopsis="Synopsis text",
                settings=settings,
            )

        run_mock.assert_called_once()
        called_args = run_mock.call_args.args[0]
        called_kwargs = run_mock.call_args.kwargs
        self.assertIn("--output-path", called_args)
        self.assertIn(str(output_dir / settings.output_name), called_args)
        self.assertEqual(result, output_dir / settings.output_name)
        self.assertIn("env", called_kwargs)
        pythonpath = called_kwargs["env"]["PYTHONPATH"]
        self.assertEqual(str(settings.module_path), pythonpath.split(os.pathsep)[0])

    @patch("book_writer.writer.generate_book_cover")
    def test_generate_book_cover_asset_uses_synopsis_file(
        self, generate_mock: Mock
    ) -> None:
        settings = CoverSettings(enabled=True, output_name="cover.png")
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            chapter_path = output_dir / "001-chapter.md"
            chapter_path.write_text("# The Adventure\n\nContent", encoding="utf-8")
            synopsis_path = output_dir / "back-cover-synopsis.md"
            synopsis_path.write_text("A daring quest unfolds.", encoding="utf-8")

            generate_book_cover_asset(output_dir, settings)

        generate_mock.assert_called_once_with(
            output_dir=output_dir,
            title="The Adventure",
            synopsis="A daring quest unfolds.",
            settings=settings,
        )
