import os
import unittest
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import MagicMock, patch

from book_writer import cli
from book_writer.cli import write_books_from_outlines
from book_writer.writer import save_book_progress


@dataclass
class _FakeChoice:
    title: str
    value: Any
    checked: bool = False


class _FakePrompt:
    def __init__(self, value: Any) -> None:
        self._value = value

    def ask(self) -> Any:
        return self._value


class _QuestionaryStub:
    Choice = _FakeChoice

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)

    def _next(self) -> Any:
        if not self._responses:
            raise AssertionError("No more prompt responses configured.")
        return self._responses.pop(0)

    def _resolve(self, response: Any, **kwargs: Any) -> Any:
        if callable(response):
            return response(**kwargs)
        return response

    def confirm(self, *args: Any, **kwargs: Any) -> _FakePrompt:
        return _FakePrompt(self._next())

    def text(self, *args: Any, **kwargs: Any) -> _FakePrompt:
        return _FakePrompt(self._next())

    def select(self, *args: Any, **kwargs: Any) -> _FakePrompt:
        return _FakePrompt(self._resolve(self._next(), **kwargs))

    def checkbox(self, *args: Any, **kwargs: Any) -> _FakePrompt:
        return _FakePrompt(self._resolve(self._next(), **kwargs))


class TestWriteBooksFromOutlines(unittest.TestCase):
    @patch("book_writer.writer.subprocess.run")
    def test_writes_books_and_moves_outlines(self, run_mock: MagicMock) -> None:
        client = MagicMock()
        client.generate.side_effect = [
            "Title for book one",
            "Content for book one",
            "Context for book one",
            "Synopsis for book one",
            "Title for book two",
            "Content for book two",
            "Context for book two",
            "Synopsis for book two",
        ]

        with TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            outlines_dir = base_dir / "outlines"
            books_dir = base_dir / "books"
            completed_dir = base_dir / "completed_outlines"
            outlines_dir.mkdir()

            (outlines_dir / "alpha.md").write_text("# Chapter Alpha\n", encoding="utf-8")
            (outlines_dir / "beta.md").write_text("# Chapter Beta\n", encoding="utf-8")

            written_files = write_books_from_outlines(
                outlines_dir=outlines_dir,
                books_dir=books_dir,
                completed_outlines_dir=completed_dir,
                client=client,
            )

            self.assertEqual(len(written_files), 2)
            alpha_output = books_dir / "alpha"
            beta_output = books_dir / "beta"
            self.assertTrue(alpha_output.is_dir())
            self.assertTrue(beta_output.is_dir())
            self.assertTrue((alpha_output / written_files[0].name).exists())
            self.assertTrue((beta_output / written_files[1].name).exists())

            alpha_book_md = (alpha_output / "book.md").read_text(encoding="utf-8")
            beta_book_md = (beta_output / "book.md").read_text(encoding="utf-8")
            self.assertIn("# Title for book one", alpha_book_md)
            self.assertIn("# Title for book two", beta_book_md)
            self.assertIn("### By Marissa Bard", alpha_book_md)
            self.assertIn("### By Marissa Bard", beta_book_md)

            self.assertFalse((outlines_dir / "alpha.md").exists())
            self.assertFalse((outlines_dir / "beta.md").exists())
            self.assertTrue((completed_dir / "alpha.md").exists())
            self.assertTrue((completed_dir / "beta.md").exists())
            run_mock.assert_called()


class TestCliExpandBook(unittest.TestCase):
    @patch("book_writer.cli.expand_book")
    def test_main_expands_completed_book(self, expand_mock: MagicMock) -> None:
        with TemporaryDirectory() as tmpdir:
            questionary_stub = _QuestionaryStub(["instructive self help guide"])
            with patch("book_writer.cli._questionary", return_value=questionary_stub):
                with patch("sys.argv", ["book-writer", "--expand-book", tmpdir]):
                    result = cli.main()

        self.assertEqual(result, 0)
        expand_mock.assert_called_once()
        _, kwargs = expand_mock.call_args
        self.assertTrue(kwargs["verbose"])

    @patch("book_writer.cli.expand_book")
    def test_main_expands_completed_book_with_passes(
        self, expand_mock: MagicMock
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            questionary_stub = _QuestionaryStub(["instructive self help guide"])
            with patch("book_writer.cli._questionary", return_value=questionary_stub):
                with patch(
                    "sys.argv",
                    ["book-writer", "--expand-book", tmpdir, "--expand-passes", "3"],
                ):
                    result = cli.main()

        self.assertEqual(result, 0)
        expand_mock.assert_called_once()
        _, kwargs = expand_mock.call_args
        self.assertEqual(kwargs["passes"], 3)
        self.assertTrue(kwargs["verbose"])

    @patch("book_writer.cli.expand_book")
    def test_main_expands_completed_book_with_tone(
        self, expand_mock: MagicMock
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            questionary_stub = _QuestionaryStub(["novel"])
            with patch("book_writer.cli._questionary", return_value=questionary_stub):
                with patch(
                    "sys.argv",
                    ["book-writer", "--expand-book", tmpdir, "--tone", "novel"],
                ):
                    result = cli.main()

        self.assertEqual(result, 0)
        expand_mock.assert_called_once()
        _, kwargs = expand_mock.call_args
        self.assertEqual(kwargs["tone"], "novel")


class TestCliTtsDefaults(unittest.TestCase):
    @patch("book_writer.cli.generate_book_title", return_value="Generated Title")
    @patch("book_writer.cli.write_book")
    def test_main_enables_tts_by_default(
        self, write_mock: MagicMock, _: MagicMock
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            outline_path = Path(tmpdir) / "OUTLINE.md"
            outline_path.write_text("# Chapter One\n", encoding="utf-8")
            current_dir = os.getcwd()
            os.chdir(tmpdir)
            try:
                with patch(
                    "sys.argv", ["book-writer", "--outline", str(outline_path)]
                ):
                    cli.main()
            finally:
                os.chdir(current_dir)

        _, kwargs = write_mock.call_args
        self.assertTrue(kwargs["tts_settings"].enabled)

    @patch("book_writer.cli.generate_book_title", return_value="Generated Title")
    @patch("book_writer.cli.write_book")
    def test_main_passes_tone_to_write_book(
        self, write_mock: MagicMock, _: MagicMock
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            outline_path = Path(tmpdir) / "OUTLINE.md"
            outline_path.write_text("# Chapter One\n", encoding="utf-8")
            current_dir = os.getcwd()
            os.chdir(tmpdir)
            try:
                with patch(
                    "sys.argv",
                    [
                        "book-writer",
                        "--outline",
                        str(outline_path),
                        "--tone",
                        "play write",
                    ],
                ):
                    cli.main()
            finally:
                os.chdir(current_dir)

        _, kwargs = write_mock.call_args
        self.assertEqual(kwargs["tone"], "play write")

    @patch("book_writer.cli.generate_book_title", return_value="Generated Title")
    @patch("book_writer.cli.write_book")
    def test_main_disables_tts_with_flag(
        self, write_mock: MagicMock, _: MagicMock
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            outline_path = Path(tmpdir) / "OUTLINE.md"
            outline_path.write_text("# Chapter One\n", encoding="utf-8")
            current_dir = os.getcwd()
            os.chdir(tmpdir)
            try:
                with patch(
                    "sys.argv",
                    ["book-writer", "--outline", str(outline_path), "--no-tts"],
                ):
                    cli.main()
            finally:
                os.chdir(current_dir)

        _, kwargs = write_mock.call_args
        self.assertFalse(kwargs["tts_settings"].enabled)


class TestCliResumeFlow(unittest.TestCase):
    @patch("book_writer.cli.generate_book_title", return_value="Generated Title")
    @patch("book_writer.cli.write_book")
    def test_main_prompts_to_resume_in_progress(
        self, write_mock: MagicMock, _: MagicMock
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            outline_path = Path(tmpdir) / "OUTLINE.md"
            outline_path.write_text("# Chapter One\n", encoding="utf-8")
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            save_book_progress(
                output_dir,
                {
                    "status": "in_progress",
                    "total_steps": 1,
                    "completed_steps": 0,
                    "previous_chapter": None,
                    "nextsteps_sections": [],
                    "book_title": "Generated Title",
                    "byline": "Marissa Bard",
                },
            )
            current_dir = os.getcwd()
            os.chdir(tmpdir)
            try:
                questionary_stub = _QuestionaryStub([True])
                with patch("book_writer.cli._questionary", return_value=questionary_stub):
                    with patch(
                        "sys.argv",
                        ["book-writer", "--outline", str(outline_path)],
                    ):
                        cli.main()
            finally:
                os.chdir(current_dir)

        _, kwargs = write_mock.call_args
        self.assertTrue(kwargs["resume"])


class TestCliPromptFlow(unittest.TestCase):
    @patch("book_writer.cli.write_books_from_outlines")
    def test_prompt_selects_outlines_tones_and_tasks(
        self, write_mock: MagicMock
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            outlines_dir = base_dir / "outlines"
            outlines_dir.mkdir()
            (outlines_dir / "alpha.md").write_text("# Chapter Alpha\n", encoding="utf-8")
            (outlines_dir / "beta.md").write_text("# Chapter Beta\n", encoding="utf-8")

            questionary_stub = _QuestionaryStub(
                [
                    "create",
                    [],
                    lambda choices: [choice.value for choice in choices],
                    "childrensbook",
                    "novel",
                    ["text"],
                    "",
                ]
            )
            with patch("book_writer.cli._questionary", return_value=questionary_stub):
                with patch(
                    "sys.argv",
                    [
                        "book-writer",
                        "--prompt",
                        "--outlines-dir",
                        str(outlines_dir),
                    ],
                ):
                    cli.main()

        _, kwargs = write_mock.call_args
        outline_files = kwargs["outline_files"]
        self.assertEqual([path.name for path in outline_files], ["alpha.md", "beta.md"])
        tone_decider = kwargs["tone_decider"]
        self.assertEqual(tone_decider(outline_files[0]), "childrensbook")
        self.assertEqual(tone_decider(outline_files[1]), "novel")


class TestCliBookManagementPrompt(unittest.TestCase):
    @patch("book_writer.cli.generate_book_videos")
    @patch("book_writer.cli.generate_book_audio")
    @patch("book_writer.cli.compile_book")
    @patch("book_writer.cli.expand_book")
    def test_prompt_manages_existing_books(
        self,
        expand_mock: MagicMock,
        compile_mock: MagicMock,
        audio_mock: MagicMock,
        video_mock: MagicMock,
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            books_dir = base_dir / "books"
            book_dir = books_dir / "alpha"
            book_dir.mkdir(parents=True)
            (book_dir / "001-chapter-one.md").write_text(
                "# Chapter One\n", encoding="utf-8"
            )

            questionary_stub = _QuestionaryStub(
                [
                    "modify",
                    lambda choices: [choices[0].value],
                    lambda choices: [
                        choice.value
                        for choice in choices
                        if choice.value in {"expand", "compile", "audio"}
                    ],
                    "2",
                    "instructive self help guide",
                    "",
                    "",
                    "",
                    "",
                ]
            )
            with patch("book_writer.cli._questionary", return_value=questionary_stub):
                with patch(
                    "sys.argv",
                    [
                        "book-writer",
                        "--prompt",
                        "--books-dir",
                        str(books_dir),
                    ],
                ):
                    result = cli.main()

        self.assertEqual(result, 0)
        expand_mock.assert_called_once()
        _, expand_kwargs = expand_mock.call_args
        self.assertEqual(expand_kwargs["passes"], 2)
        compile_mock.assert_called_once_with(book_dir)
        audio_mock.assert_called_once()
        video_mock.assert_not_called()


class TestCliPromptCombinedFlows(unittest.TestCase):
    @patch("book_writer.cli.write_books_from_outlines")
    @patch("book_writer.cli.expand_book")
    def test_prompt_create_path_skips_book_management(
        self, expand_mock: MagicMock, write_mock: MagicMock
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            books_dir = base_dir / "books"
            book_dir = books_dir / "alpha"
            book_dir.mkdir(parents=True)
            (book_dir / "001-chapter-one.md").write_text(
                "# Chapter One\n", encoding="utf-8"
            )
            outlines_dir = base_dir / "outlines"
            outlines_dir.mkdir()
            (outlines_dir / "alpha.md").write_text("# Chapter Alpha\n", encoding="utf-8")
            (outlines_dir / "beta.md").write_text("# Chapter Beta\n", encoding="utf-8")

            questionary_stub = _QuestionaryStub(
                [
                    "create",
                    [],
                    lambda choices: [choice.value for choice in choices],
                    "instructive self help guide",
                    "instructive self help guide",
                    ["text"],
                    "",
                ]
            )
            with patch("book_writer.cli._questionary", return_value=questionary_stub):
                with patch(
                    "sys.argv",
                    [
                        "book-writer",
                        "--prompt",
                        "--books-dir",
                        str(books_dir),
                        "--outlines-dir",
                        str(outlines_dir),
                    ],
                ):
                    result = cli.main()

        self.assertEqual(result, 0)
        expand_mock.assert_not_called()
        write_mock.assert_called_once()
        _, write_kwargs = write_mock.call_args
        outline_files = write_kwargs["outline_files"]
        self.assertEqual([path.name for path in outline_files], ["alpha.md", "beta.md"])
