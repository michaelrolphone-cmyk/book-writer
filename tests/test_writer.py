import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, Mock, patch

from book_writer.outline import OutlineItem
from book_writer.writer import (
    ChapterContext,
    LMStudioClient,
    build_book_markdown,
    build_chapter_context_prompt,
    build_expand_paragraph_prompt,
    build_prompt,
    build_synopsis_prompt,
    expand_book,
    expand_chapter_content,
    generate_book_pdf,
    write_book,
)


class TestWriter(unittest.TestCase):
    def test_build_prompt_includes_outline_and_current_item(self) -> None:
        items = [
            OutlineItem(title="Chapter One", level=1),
            OutlineItem(title="Section A", level=2, parent_title="Chapter One"),
        ]

        prompt = build_prompt(items, items[1], None)

        self.assertIn("Outline:", prompt)
        self.assertIn("Current item: Section A", prompt)
        self.assertIn("chapter 'Chapter One'", prompt)

    def test_build_prompt_includes_previous_chapter_for_next_chapter(self) -> None:
        items = [
            OutlineItem(title="Chapter One", level=1),
            OutlineItem(title="Chapter Two", level=1),
        ]
        previous_chapter = ChapterContext(
            title="Chapter One", content="Protagonist meets the guide."
        )

        prompt = build_prompt(items, items[1], previous_chapter)

        self.assertIn("Previous chapter context:", prompt)
        self.assertIn("Title: Chapter One", prompt)
        self.assertIn("Protagonist meets the guide.", prompt)

    def test_build_prompt_labels_epilogue(self) -> None:
        items = [
            OutlineItem(title="Chapter One", level=1),
            OutlineItem(title="Epilogue", level=1),
        ]
        previous_chapter = ChapterContext(
            title="Chapter One", content="Protagonist meets the guide."
        )

        prompt = build_prompt(items, items[1], previous_chapter)

        self.assertIn("Current item: Epilogue (epilogue).", prompt)
        self.assertIn("Previous chapter context:", prompt)

    @patch("book_writer.writer.subprocess.run")
    def test_write_book_creates_numbered_files(self, run_mock: Mock) -> None:
        items = [
            OutlineItem(title="Chapter One", level=1),
            OutlineItem(title="Section A", level=2, parent_title="Chapter One"),
        ]
        client = MagicMock()
        client.generate.side_effect = [
            "Chapter content",
            "Chapter context summary",
            "Section content",
            "Synopsis text",
        ]

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            files = write_book(items, output_dir, client)

            self.assertEqual(len(files), 2)
            self.assertTrue(files[0].name.startswith("001-"))
            self.assertTrue(files[1].name.startswith("002-"))
            first_content = files[0].read_text(encoding="utf-8")
            second_content = files[1].read_text(encoding="utf-8")
            synopsis_path = output_dir / "back-cover-synopsis.md"
            self.assertTrue(synopsis_path.exists())
            self.assertIn("Synopsis text", synopsis_path.read_text(encoding="utf-8"))

        self.assertIn("# Chapter One", first_content)
        self.assertIn("Chapter content", first_content)
        self.assertIn("## Section A", second_content)
        self.assertIn("Section content", second_content)
        run_mock.assert_called_once()

    @patch("book_writer.writer.subprocess.run")
    def test_write_book_logs_verbose_steps(self, run_mock: Mock) -> None:
        items = [OutlineItem(title="Chapter One", level=1)]
        client = MagicMock()
        client.generate.side_effect = [
            "Chapter content",
            "Chapter summary",
            "Synopsis text",
        ]

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            with patch("builtins.print") as print_mock:
                write_book(items, output_dir, client, verbose=True)

        print_mock.assert_any_call(
            "[write] Step 1/1: Generating chapter 'Chapter One'."
        )
        print_mock.assert_any_call("[write] Generated book.pdf from chapters.")
        run_mock.assert_called_once()

    @patch("book_writer.writer.subprocess.run")
    def test_write_book_includes_previous_chapter_in_next_prompt(
        self, run_mock: Mock
    ) -> None:
        items = [
            OutlineItem(title="Chapter One", level=1),
            OutlineItem(title="Chapter Two", level=1),
        ]
        client = MagicMock()
        client.generate.side_effect = [
            "Chapter one content",
            "Chapter one summary",
            "Chapter two content",
            "Chapter two summary",
            "Synopsis text",
        ]

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            write_book(items, output_dir, client)

        second_prompt = client.generate.call_args_list[2][0][0]
        self.assertIn("Previous chapter context:", second_prompt)
        self.assertIn("Chapter one summary", second_prompt)
        run_mock.assert_called_once()

    @patch("book_writer.writer.subprocess.run")
    def test_write_book_saves_implementation_details(
        self, run_mock: Mock
    ) -> None:
        items = [OutlineItem(title="Chapter One", level=1)]
        client = MagicMock()
        client.generate.side_effect = [
            "Intro paragraph.\n\n## Implementation Details\n\nUse a cache.\n\n## Wrap-up\n\nDone.",
            "Chapter summary",
            "Synopsis text",
        ]

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            files = write_book(items, output_dir, client)

            nextsteps_path = output_dir / "nextsteps.md"
            self.assertTrue(nextsteps_path.exists())
            nextsteps_text = nextsteps_path.read_text(encoding="utf-8")
            self.assertIn("## Implementation Details", nextsteps_text)
            self.assertIn("Use a cache.", nextsteps_text)

            chapter_text = files[0].read_text(encoding="utf-8")
            self.assertNotIn("Implementation Details", chapter_text)

        run_mock.assert_called_once()

    @patch("book_writer.writer.subprocess.run")
    def test_write_book_synopsis_includes_outline(self, run_mock: Mock) -> None:
        items = [
            OutlineItem(title="Chapter One", level=1),
            OutlineItem(title="Section A", level=2, parent_title="Chapter One"),
        ]
        client = MagicMock()
        client.generate.side_effect = [
            "Chapter content",
            "Chapter summary",
            "Section content",
            "Synopsis text",
        ]

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            write_book(items, output_dir, client)

        synopsis_prompt = client.generate.call_args_list[-1][0][0]
        self.assertIn("Outline:\n- Chapter One\n  - Section A", synopsis_prompt)
        run_mock.assert_called_once()

    def test_build_chapter_context_prompt_mentions_chapter(self) -> None:
        prompt = build_chapter_context_prompt("Chapter One", "Some chapter text.")

        self.assertIn("Chapter title: Chapter One", prompt)
        self.assertIn("Chapter content:", prompt)

    def test_build_synopsis_prompt_mentions_outline_and_content(self) -> None:
        prompt = build_synopsis_prompt(
            "Chapter One", "- Chapter One", "Full book content."
        )

        self.assertIn("Book title: Chapter One", prompt)
        self.assertIn("Outline:", prompt)
        self.assertIn("Book content:", prompt)

    def test_build_book_markdown_includes_title_outline_and_chapters(self) -> None:
        markdown = build_book_markdown(
            "Book Title", "- Chapter One", ["# Chapter One\n\nText"]
        )

        self.assertIn("# Book Title", markdown)
        self.assertIn("## Outline", markdown)
        self.assertIn("# Chapter One", markdown)

    def test_build_expand_paragraph_prompt_includes_context(self) -> None:
        prompt = build_expand_paragraph_prompt(
            current="Current paragraph.",
            previous="Previous paragraph.",
            next_paragraph="Next paragraph.",
            section_heading="Section One",
        )

        self.assertIn("Section heading: Section One", prompt)
        self.assertIn("Previous section/paragraph:", prompt)
        self.assertIn("Next section/paragraph:", prompt)
        self.assertIn("Current paragraph/section:", prompt)

    def test_expand_chapter_content_uses_neighboring_context(self) -> None:
        content = "# Chapter One\n\nFirst paragraph.\n\nSecond paragraph."
        client = MagicMock()
        client.generate.side_effect = ["Expanded first.", "Expanded second."]

        expanded = expand_chapter_content(content, client)

        self.assertIn("Expanded first.", expanded)
        self.assertIn("Expanded second.", expanded)
        first_prompt = client.generate.call_args_list[0][0][0]
        second_prompt = client.generate.call_args_list[1][0][0]
        self.assertIn("Next section/paragraph:", first_prompt)
        self.assertIn("Second paragraph.", first_prompt)
        self.assertIn("Previous section/paragraph:", second_prompt)
        self.assertIn("First paragraph.", second_prompt)

    @patch("book_writer.writer.subprocess.run")
    def test_expand_book_updates_chapters_and_regenerates_pdf(
        self, run_mock: Mock
    ) -> None:
        client = MagicMock()
        client.generate.return_value = "Expanded paragraph."

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            chapter_path = output_dir / "001-chapter-one.md"
            chapter_path.write_text(
                "# Chapter One\n\nOriginal paragraph.", encoding="utf-8"
            )
            (output_dir / "book.md").write_text(
                "# Book Title\n\n"
                "\\newpage\n\n"
                "## Outline\n"
                "- Chapter One\n\n"
                "\\newpage\n\n"
                "# Chapter One\n\n"
                "Original paragraph.\n",
                encoding="utf-8",
            )

            expanded_files = expand_book(output_dir, client)

            updated_content = chapter_path.read_text(encoding="utf-8")
            self.assertIn("Expanded paragraph.", updated_content)
            self.assertEqual(expanded_files, [chapter_path])

        run_mock.assert_called_once()

    @patch("book_writer.writer.subprocess.run")
    def test_expand_book_runs_multiple_passes(self, run_mock: Mock) -> None:
        client = MagicMock()
        client.generate.side_effect = ["Expanded once.", "Expanded twice."]

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            chapter_path = output_dir / "001-chapter-one.md"
            chapter_path.write_text(
                "# Chapter One\n\nOriginal paragraph.", encoding="utf-8"
            )

            expanded_files = expand_book(output_dir, client, passes=2)

            updated_content = chapter_path.read_text(encoding="utf-8")
            self.assertIn("Expanded twice.", updated_content)
            self.assertEqual(expanded_files, [chapter_path])

        run_mock.assert_called_once()

    @patch("book_writer.writer.subprocess.run")
    def test_expand_book_logs_verbose_steps(self, run_mock: Mock) -> None:
        client = MagicMock()
        client.generate.return_value = "Expanded paragraph."

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            chapter_path = output_dir / "001-chapter-one.md"
            chapter_path.write_text(
                "# Chapter One\n\nOriginal paragraph.", encoding="utf-8"
            )

            with patch("builtins.print") as print_mock:
                expand_book(output_dir, client, verbose=True)

        print_mock.assert_any_call(
            f"[expand] Expanding book in {output_dir} with 1 pass(es)."
        )
        print_mock.assert_any_call(
            "[expand] Step 1/1: Expanding 001-chapter-one.md."
        )
        run_mock.assert_called_once()

    @patch("book_writer.writer.subprocess.run")
    def test_generate_book_pdf_calls_pandoc(self, run_mock: Mock) -> None:
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            chapter_path = output_dir / "001-chapter-one.md"
            chapter_path.write_text("# Chapter One\n\nText", encoding="utf-8")

            pdf_path = generate_book_pdf(
                output_dir=output_dir,
                title="Chapter One",
                outline_text="- Chapter One",
                chapter_files=[chapter_path],
            )

            self.assertTrue((output_dir / "book.md").exists())
            self.assertEqual(pdf_path.name, "book.pdf")

        run_mock.assert_called_once()

    def test_generate_without_timeout_omits_timeout_param(self) -> None:
        response = Mock()
        response.read.return_value = json.dumps(
            {"choices": [{"message": {"content": "Draft content"}}]}
        ).encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        urlopen_mock = Mock(return_value=response)

        with patch("book_writer.writer.request.urlopen", urlopen_mock):
            client = LMStudioClient(base_url="http://localhost:1234", model="demo-model")
            result = client.generate("Prompt")

        self.assertEqual(result, "Draft content")
        urlopen_mock.assert_called_once()
        _, kwargs = urlopen_mock.call_args
        self.assertNotIn("timeout", kwargs)


if __name__ == "__main__":
    unittest.main()
