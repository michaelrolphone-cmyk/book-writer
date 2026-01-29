import json
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

TAXONOMY_RESPONSE = json.dumps(
    {
        "title": "Sample Book",
        "taxonomy": {
            "people": [],
            "places": [],
            "events": [],
            "motivations": [],
            "loyalties": [],
            "personalities": [],
        },
    }
)
JOURNEY_RESPONSE = json.dumps({"title": "Sample Book", "journey": []})


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


class _CheckboxDefaultGuard:
    Choice = _FakeChoice

    def __init__(self, response: Any) -> None:
        self._response = response

    def checkbox(self, *args: Any, **kwargs: Any) -> _FakePrompt:
        if kwargs.get("default") == []:
            raise AssertionError("Checkbox default should not be an empty list.")
        response = self._response(**kwargs) if callable(self._response) else self._response
        return _FakePrompt(response)


class TestWriteBooksFromOutlines(unittest.TestCase):
    @patch("book_writer.writer.subprocess.run")
    def test_writes_books_and_moves_outlines(self, run_mock: MagicMock) -> None:
        client = MagicMock()
        client.generate.side_effect = [
            "Title for book one",
            "Content for book one",
            "Context for book one",
            "Synopsis for book one",
            '{"genres": ["Sci-Fi"]}',
            TAXONOMY_RESPONSE,
            JOURNEY_RESPONSE,
            "Title for book two",
            "Content for book two",
            "Context for book two",
            "Synopsis for book two",
            '{"genres": ["Fantasy"]}',
            TAXONOMY_RESPONSE,
            JOURNEY_RESPONSE,
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
            self.assertIn("Title for book one", alpha_book_md)
            self.assertIn("Title for book two", beta_book_md)
            self.assertIn("By Marissa Bard", alpha_book_md)
            self.assertIn("By Marissa Bard", beta_book_md)

            self.assertFalse((outlines_dir / "alpha.md").exists())
            self.assertFalse((outlines_dir / "beta.md").exists())
            self.assertTrue((completed_dir / "alpha.md").exists())
            self.assertTrue((completed_dir / "beta.md").exists())
            run_mock.assert_called()


class TestCliOutlineWizard(unittest.TestCase):
    @patch("book_writer.cli.generate_outline")
    def test_prompt_outline_wizard_writes_outline(self, generate_mock: MagicMock) -> None:
        generate_mock.return_value = "# Book One\n\n## Chapter One"
        with TemporaryDirectory() as tmpdir:
            outlines_dir = Path(tmpdir) / "outlines"
            questionary_stub = _QuestionaryStub(
                [
                    "outline",
                    "A fantasy epic.",
                    "fantasy.md",
                    str(outlines_dir),
                    None,
                    False,
                ]
            )
            with patch("book_writer.cli._questionary", return_value=questionary_stub):
                with patch("sys.argv", ["book-writer", "--prompt"]):
                    result = cli.main()

            outline_path = outlines_dir / "fantasy.md"
            self.assertEqual(result, 0)
            self.assertTrue(outline_path.exists())
            self.assertIn(
                "Chapter One", outline_path.read_text(encoding="utf-8")
            )


class TestCliExpandBook(unittest.TestCase):
    @patch("book_writer.cli.expand_book")
    def test_main_expands_completed_book(self, expand_mock: MagicMock) -> None:
        with TemporaryDirectory() as tmpdir:
            questionary_stub = _QuestionaryStub(
                [None, "instructive self help guide"]
            )
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
            questionary_stub = _QuestionaryStub(
                [None, "instructive self help guide"]
            )
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
            questionary_stub = _QuestionaryStub([None, "novel"])
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

    @patch("book_writer.cli.expand_book")
    def test_main_expands_only_selected_chapters(
        self, expand_mock: MagicMock
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            book_dir = Path(tmpdir)
            (book_dir / "001-chapter-one.md").write_text(
                "# Chapter One\n", encoding="utf-8"
            )
            (book_dir / "002-chapter-two.md").write_text(
                "# Chapter Two\n", encoding="utf-8"
            )
            questionary_stub = _QuestionaryStub(
                [None, "instructive self help guide"]
            )
            with patch("book_writer.cli._questionary", return_value=questionary_stub):
                with patch(
                    "sys.argv",
                    [
                        "book-writer",
                        "--expand-book",
                        tmpdir,
                        "--expand-only",
                        "2",
                    ],
                ):
                    result = cli.main()

        self.assertEqual(result, 0)
        expand_mock.assert_called_once()
        _, kwargs = expand_mock.call_args
        selected = kwargs["chapter_files"]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].name, "002-chapter-two.md")


class TestCliCoverGeneration(unittest.TestCase):
    @patch("book_writer.cli.generate_book_cover_asset")
    def test_main_generates_cover_for_existing_book(
        self, cover_mock: MagicMock
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            book_dir = Path(tmpdir)
            (book_dir / "001-chapter-one.md").write_text(
                "# Chapter One\n", encoding="utf-8"
            )
            with patch(
                "sys.argv",
                ["book-writer", "--cover-book", str(book_dir), "--cover-model-path", "/tmp/model"],
            ):
                result = cli.main()

        self.assertEqual(result, 0)
        cover_mock.assert_called_once()

    @patch("book_writer.cli.generate_chapter_cover_assets")
    def test_main_generates_chapter_covers_for_existing_book(
        self, cover_mock: MagicMock
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            book_dir = Path(tmpdir)
            (book_dir / "001-chapter-one.md").write_text(
                "# Chapter One\n", encoding="utf-8"
            )
            with patch(
                "sys.argv",
                [
                    "book-writer",
                    "--chapter-covers-book",
                    str(book_dir),
                    "--cover-model-path",
                    "/tmp/model",
                ],
            ):
                result = cli.main()

        self.assertEqual(result, 0)
        cover_mock.assert_called_once()


class TestCliExpandOnlyPrompt(unittest.TestCase):
    def test_prompt_for_expand_only_skips_empty_default(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            chapter_one = base_dir / "001-chapter-one.md"
            chapter_two = base_dir / "002-chapter-two.md"
            chapter_one.write_text("# Chapter One\n", encoding="utf-8")
            chapter_two.write_text("# Chapter Two\n", encoding="utf-8")
            chapter_files = [chapter_one, chapter_two]

            questionary_stub = _CheckboxDefaultGuard(
                lambda choices, **kwargs: [choices[0].value]
            )
            with patch("book_writer.cli._questionary", return_value=questionary_stub):
                selected = cli._prompt_for_expand_only(chapter_files, None)

        self.assertEqual(selected, [chapter_one])


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
    def test_main_passes_author_to_client(
        self, write_mock: MagicMock, _: MagicMock
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            outline_path = Path(tmpdir) / "OUTLINE.md"
            outline_path.write_text("# Chapter One\n", encoding="utf-8")
            current_dir = os.getcwd()
            os.chdir(tmpdir)
            try:
                with patch("book_writer.cli.LMStudioClient") as client_mock:
                    with patch(
                        "sys.argv",
                        [
                            "book-writer",
                            "--outline",
                            str(outline_path),
                            "--author",
                            "curious-storyteller",
                        ],
                    ):
                        cli.main()
            finally:
                os.chdir(current_dir)

        client_mock.assert_called_once()
        _, kwargs = client_mock.call_args
        self.assertEqual(kwargs["author"], "curious-storyteller")
        write_mock.assert_called_once()

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

    @patch("book_writer.cli.generate_book_title", return_value="Generated Title")
    @patch("book_writer.cli.write_book")
    def test_main_sets_tts_engine(
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
                        "--tts-engine",
                        "python",
                    ],
                ):
                    cli.main()
            finally:
                os.chdir(current_dir)

        _, kwargs = write_mock.call_args
        self.assertEqual(kwargs["tts_settings"].engine, "python")


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
    def test_prompt_selects_outlines_once_with_unchecked_defaults(self) -> None:
        outline_info = [
            cli.OutlineInfo(
                path=Path("alpha.md"),
                title="Alpha",
                items=[],
                preview_text="Preview A",
            ),
            cli.OutlineInfo(
                path=Path("beta.md"),
                title="Beta",
                items=[],
                preview_text="Preview B",
            ),
        ]

        def _select(**kwargs: Any) -> list[cli.OutlineInfo]:
            choices = kwargs["choices"]
            self.assertTrue(choices)
            self.assertTrue(all(not choice.checked for choice in choices))
            return [choices[0].value]

        questionary_stub = _QuestionaryStub([_select])
        with patch("book_writer.cli._questionary", return_value=questionary_stub):
            selected = cli._prompt_for_outline_selection(outline_info)

        self.assertEqual(selected, [outline_info[0]])

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
                    lambda choices: [choice.value for choice in choices],
                    "curious-storyteller",
                    "precise-historian",
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
        author_decider = kwargs["author_decider"]
        self.assertEqual(author_decider(outline_files[0]), "curious-storyteller")
        self.assertEqual(author_decider(outline_files[1]), "precise-historian")
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
            (book_dir / "002-chapter-two.md").write_text(
                "# Chapter Two\n", encoding="utf-8"
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
                    "qwen3",
                    "",
                    "",
                    "",
                    "",
                    "",
                    False,
                    False,
                    False,
                    "curious-storyteller",
                    "instructive self help guide",
                    lambda choices, **kwargs: [choices[1].value],
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
        self.assertEqual(len(expand_kwargs["chapter_files"]), 1)
        self.assertEqual(
            expand_kwargs["chapter_files"][0].name, "002-chapter-two.md"
        )
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
                    lambda choices: [choice.value for choice in choices],
                    "curious-storyteller",
                    "precise-historian",
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


class TestCliGuiLaunch(unittest.TestCase):
    @patch("book_writer.server.run_server")
    def test_main_starts_gui_server_with_flag(self, run_server_mock: MagicMock) -> None:
        with patch(
            "sys.argv",
            [
                "book-writer",
                "--gui",
                "--gui-host",
                "0.0.0.0",
                "--gui-port",
                "9090",
            ],
        ):
            result = cli.main()

        self.assertEqual(result, 0)
        run_server_mock.assert_called_once_with(host="0.0.0.0", port=9090)

    @patch("book_writer.server.run_server")
    def test_prompt_launches_gui_server(self, run_server_mock: MagicMock) -> None:
        questionary_stub = _QuestionaryStub(["gui"])
        with patch("book_writer.cli._questionary", return_value=questionary_stub):
            with patch("sys.argv", ["book-writer", "--prompt"]):
                result = cli.main()

        self.assertEqual(result, 0)
        run_server_mock.assert_called_once_with(host="127.0.0.1", port=8080)
