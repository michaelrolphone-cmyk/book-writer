import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, Mock, call, patch

from urllib.error import HTTPError

from book_writer.outline import OutlineItem
from book_writer.tts import TTSSynthesisError, TTSSettings
from book_writer.video import ParagraphImageSettings, VideoSettings
from book_writer.cover import CoverSettings
from book_writer.writer import (
    ChapterContext,
    ChapterLayout,
    LMStudioClient,
    build_audiobook_text,
    build_book_markdown,
    build_book_title_prompt,
    build_chapter_context_prompt,
    build_outline_prompt,
    build_outline_revision_prompt,
    build_expand_paragraph_prompt,
    build_prompt,
    build_synopsis_prompt,
    _base_prompt,
    _ensure_epub_css,
    _expand_prompt_text,
    _sanitize_markdown_for_latex,
    compile_book,
    expand_book,
    expand_chapter_content,
    generate_book_audio,
    generate_book_cover_asset,
    generate_book_title,
    generate_book_pdf,
    generate_book_videos,
    generate_chapter_cover_assets,
    generate_outline,
    save_book_progress,
    write_book,
    _summarize_cover_text,
    _truncate_cover_text,
)


class TestWriter(unittest.TestCase):
    def test_base_prompt_uses_author_persona(self) -> None:
        prompt = _base_prompt("curious-storyteller")

        self.assertIn("curious storyteller", prompt.casefold())

    def test_base_prompt_includes_continuity_guidance(self) -> None:
        prompt = _base_prompt()

        self.assertIn("continuity", prompt.casefold())
        self.assertIn("repetition", prompt.casefold())

    def test_expand_prompt_mentions_bridging_sentences(self) -> None:
        prompt = _expand_prompt_text()

        self.assertIn("bridging sentences", prompt.casefold())
        self.assertIn("continuity", prompt.casefold())

    def test_build_prompt_includes_outline_and_current_item(self) -> None:
        items = [
            OutlineItem(title="Chapter One", level=1),
            OutlineItem(title="Section A", level=2, parent_title="Chapter One"),
        ]

        prompt = build_prompt(items, items[1], None)

        self.assertIn("Outline:", prompt)
        self.assertIn("Current item: Section A", prompt)
        self.assertIn("chapter 'Chapter One'", prompt)
        self.assertIn("Section focus: Section A", prompt)

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

    def test_build_prompt_includes_outline_beats(self) -> None:
        items = [
            OutlineItem(title="Chapter One", level=1),
            OutlineItem(title="Section A", level=2, parent_title="Chapter One"),
            OutlineItem(title="Beat one", level=3, parent_title="Section A"),
            OutlineItem(title="Beat two", level=4, parent_title="Beat one"),
        ]

        prompt = build_prompt(items, items[0], None)

        self.assertIn("Outline beats to cover:", prompt)
        self.assertIn("- Section A", prompt)
        self.assertIn("  - Beat one", prompt)
        self.assertIn("    - Beat two", prompt)

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

    def test_generate_outline_applies_revision_prompts(self) -> None:
        client = MagicMock()
        client.generate.side_effect = [
            "# Title\n\n## Chapter One",
            "# Title\n\n## Chapter One\n\n## Chapter Two",
        ]

        result = generate_outline(
            "A story about growth.",
            client,
            revision_prompts=["Add a second chapter."],
        )

        self.assertIn("Chapter Two", result)
        self.assertEqual(
            client.generate.mock_calls,
            [
                call(build_outline_prompt("A story about growth.")),
                call(
                    build_outline_revision_prompt(
                        "# Title\n\n## Chapter One",
                        "Add a second chapter.",
                    )
                ),
            ],
        )

    def test_sanitize_markdown_for_latex_escapes_commands_outside_math(self) -> None:
        text = "We measure \\frac{d\\Psi}{dt} over time."
        cleaned = _sanitize_markdown_for_latex(text)
        self.assertIn(
            "\\textbackslash{}frac{d\\textbackslash{}Psi}{dt}",
            cleaned,
        )

    def test_sanitize_markdown_for_latex_preserves_math_blocks(self) -> None:
        text = "Energy $\\frac{d\\Psi}{dt}$ is steady."
        cleaned = _sanitize_markdown_for_latex(text)
        self.assertIn("$\\frac{d\\Psi}{dt}$", cleaned)

    def test_sanitize_markdown_for_latex_escapes_unbalanced_dollar(self) -> None:
        text = "The price is $5 for admission."
        cleaned = _sanitize_markdown_for_latex(text)
        self.assertIn("\\$5", cleaned)

    def test_sanitize_markdown_for_latex_escapes_windows_paths(self) -> None:
        text = "Saved to \\\\Server\\Office\\text."
        cleaned = _sanitize_markdown_for_latex(text)
        self.assertIn(
            "\\textbackslash{}\\textbackslash{}Server"
            "\\textbackslash{}Office\\textbackslash{}text.",
            cleaned,
        )

    def test_truncate_cover_text_returns_stripped_input(self) -> None:
        text = "  Short synopsis.  "

        result = _truncate_cover_text(text)

        self.assertEqual(result, "Short synopsis.")

    def test_truncate_cover_text_clips_long_input(self) -> None:
        text = "a" * 7001

        result = _truncate_cover_text(text)

        self.assertEqual(len(result), 6000)
        self.assertTrue(result.endswith("…"))

    def test_summarize_cover_text_uses_trimmed_input(self) -> None:
        long_text = "b" * 7001
        trimmed_text = _truncate_cover_text(long_text)
        client = MagicMock()
        client.generate.return_value = "summary"

        _summarize_cover_text(client, long_text, "book synopsis")

        called_prompt = client.generate.call_args[0][0]
        self.assertIn(trimmed_text, called_prompt)
        self.assertNotIn(long_text, called_prompt)

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
            "Mystery",
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
        self.assertEqual(run_mock.call_count, 2)
        epub_call = run_mock.call_args_list[1]
        self.assertNotIn("--epub-cover-image", epub_call.args[0])

    @patch("book_writer.writer.subprocess.run")
    def test_write_book_clears_existing_chapters(
        self, run_mock: Mock
    ) -> None:
        items = [OutlineItem(title="Chapter One", level=1)]
        client = MagicMock()
        client.generate.side_effect = [
            "Chapter content",
            "Chapter summary",
            "Synopsis text",
            "Mystery",
        ]

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            stale_path = output_dir / "001-old-chapter.md"
            stale_path.write_text("# Old Chapter\n\nOld content\n", encoding="utf-8")

            files = write_book(items, output_dir, client)

            self.assertEqual(len(files), 1)
            self.assertFalse(stale_path.exists())

        self.assertEqual(run_mock.call_count, 2)

    @patch("book_writer.writer.subprocess.run")
    def test_write_book_logs_verbose_steps(self, run_mock: Mock) -> None:
        items = [OutlineItem(title="Chapter One", level=1)]
        client = MagicMock()
        client.generate.side_effect = [
            "Chapter content",
            "Chapter summary",
            "Synopsis text",
            "Mystery",
        ]

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            with patch("builtins.print") as print_mock:
                write_book(items, output_dir, client, verbose=True)

        print_mock.assert_any_call(
            "[write] Step 1/1: Generating chapter 'Chapter One'."
        )
        print_mock.assert_any_call("[write] Generated book.pdf and book.epub from chapters.")
        self.assertEqual(run_mock.call_count, 2)

    @patch("book_writer.writer.subprocess.run")
    def test_write_book_skips_bullet_outline_items(
        self, run_mock: Mock
    ) -> None:
        items = [
            OutlineItem(title="Chapter One", level=1),
            OutlineItem(
                title="Beat one",
                level=2,
                parent_title="Chapter One",
                source="bullet",
            ),
        ]
        client = MagicMock()
        client.generate.side_effect = [
            "Chapter content",
            "Chapter summary",
            "Synopsis text",
            "Mystery",
        ]

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            files = write_book(items, output_dir, client)

            self.assertEqual(len(files), 1)
            self.assertTrue(files[0].name.startswith("001-"))

        self.assertEqual(run_mock.call_count, 2)

    @patch("book_writer.writer.subprocess.run")
    def test_write_book_logs_prompts_when_enabled(
        self, run_mock: Mock
    ) -> None:
        items = [OutlineItem(title="Chapter One", level=1)]

        class DummyClient:
            def __init__(self) -> None:
                self.base_prompt = "BASE PROMPT"
                self._responses = iter(
                    ["Chapter content", "Chapter summary", "Synopsis text", "Mystery"]
                )

            def render_prompt(self, prompt: str) -> str:
                return f"{self.base_prompt}\n\n{prompt}".strip()

            def generate(self, _prompt: str) -> str:
                return next(self._responses)

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            with patch("builtins.print") as print_mock:
                write_book(
                    items,
                    output_dir,
                    DummyClient(),
                    log_prompts=True,
                )

        self.assertTrue(
            any(
                "[prompt] Chapter 1/1: Chapter One" in call.args[0]
                for call in print_mock.mock_calls
                if call.args
            )
        )
        self.assertEqual(run_mock.call_count, 2)

    @patch("book_writer.writer.synthesize_text_audio")
    @patch("book_writer.writer.synthesize_chapter_video")
    @patch("book_writer.writer.synthesize_chapter_audio")
    @patch("book_writer.writer.subprocess.run")
    def test_write_book_generates_chapter_audio(
        self,
        run_mock: Mock,
        synthesize_chapter_mock: Mock,
        synthesize_video_mock: Mock,
        synthesize_text_mock: Mock,
    ) -> None:
        items = [OutlineItem(title="Chapter One", level=1)]
        client = MagicMock()
        client.generate.side_effect = [
            "Chapter content",
            "Chapter summary",
            "Synopsis text",
            "Mystery",
        ]
        tts_settings = TTSSettings(enabled=True)
        synthesize_chapter_mock.return_value = None

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            files = write_book(
                items, output_dir, client, tts_settings=tts_settings
            )
            audiobook_text = build_audiobook_text(
                "Chapter One",
                "Marissa Bard",
                [files[0].read_text(encoding="utf-8")],
            )

        synthesize_chapter_mock.assert_called_once_with(
            chapter_path=files[0],
            output_dir=files[0].parent / tts_settings.audio_dirname,
            settings=tts_settings,
            verbose=False,
        )
        synthesize_text_mock.assert_has_calls(
            [
                call(
                    text=audiobook_text,
                    output_path=output_dir
                    / tts_settings.audio_dirname
                    / "book.mp3",
                    settings=tts_settings,
                    verbose=False,
                    raise_on_error=True,
                ),
                call(
                    text="Synopsis text",
                    output_path=output_dir
                    / tts_settings.audio_dirname
                    / "back-cover-synopsis.mp3",
                    settings=tts_settings,
                    verbose=False,
                ),
            ]
        )

    @patch("book_writer.writer.synthesize_text_audio")
    @patch("book_writer.writer.synthesize_chapter_audio")
    def test_generate_book_audio_creates_missing_audio(
        self,
        synthesize_chapter_mock: Mock,
        synthesize_text_mock: Mock,
    ) -> None:
        tts_settings = TTSSettings(enabled=True)
        synthesize_chapter_mock.return_value = None
        synthesize_text_mock.side_effect = [
            Path("book.mp3"),
            Path("back-cover-synopsis.mp3"),
        ]
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            chapter_path = output_dir / "001-chapter-one.md"
            chapter_path.write_text("# Chapter One\n\nContent\n", encoding="utf-8")
            synopsis_path = output_dir / "back-cover-synopsis.md"
            synopsis_path.write_text("Synopsis", encoding="utf-8")
            audiobook_text = build_audiobook_text(
                "Chapter One",
                "Marissa Bard",
                [chapter_path.read_text(encoding="utf-8")],
            )

            generate_book_audio(output_dir, tts_settings)

        synthesize_chapter_mock.assert_called_once_with(
            chapter_path=chapter_path,
            output_dir=output_dir / tts_settings.audio_dirname,
            settings=tts_settings,
            verbose=False,
        )
        synthesize_text_mock.assert_has_calls(
            [
                call(
                    text=audiobook_text,
                    output_path=output_dir
                    / tts_settings.audio_dirname
                    / "book.mp3",
                    settings=tts_settings,
                    verbose=False,
                    raise_on_error=True,
                ),
                call(
                    text="Synopsis",
                    output_path=output_dir
                    / tts_settings.audio_dirname
                    / "back-cover-synopsis.mp3",
                    settings=tts_settings,
                    verbose=False,
                ),
            ]
        )

    @patch("book_writer.writer.generate_chapter_cover")
    def test_generate_chapter_cover_assets_creates_outputs(
        self, cover_mock: Mock
    ) -> None:
        settings = CoverSettings(enabled=True)
        cover_mock.side_effect = [
            Path("chapter_covers/001-chapter-one.png"),
            Path("chapter_covers/002-chapter-two.png"),
        ]

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            chapter_one = output_dir / "001-chapter-one.md"
            chapter_two = output_dir / "002-chapter-two.md"
            chapter_one.write_text("# Chapter One\n\nContent", encoding="utf-8")
            chapter_two.write_text("# Chapter Two\n\nContent", encoding="utf-8")

            generated = generate_chapter_cover_assets(
                output_dir=output_dir,
                cover_settings=settings,
                chapter_cover_dir="chapter_covers",
            )

        self.assertEqual(len(generated), 2)
        self.assertEqual(cover_mock.call_count, 2)
        first_call = cover_mock.call_args_list[0].kwargs
        self.assertEqual(first_call["book_title"], "Chapter One")
        self.assertEqual(first_call["chapter_title"], "Chapter One")

    @patch("book_writer.writer.generate_book_cover")
    def test_generate_book_cover_asset_summarizes_synopsis(
        self, cover_mock: Mock
    ) -> None:
        settings = CoverSettings(enabled=True)
        client = Mock(spec=LMStudioClient)
        client.generate.return_value = "Short summary."
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            chapter_path = output_dir / "001-chapter-one.md"
            chapter_path.write_text("# The Adventure\n\nContent", encoding="utf-8")
            synopsis_path = output_dir / "back-cover-synopsis.md"
            synopsis_path.write_text(
                "A long synopsis that needs to be shortened.", encoding="utf-8"
            )

            generate_book_cover_asset(output_dir, settings, client=client)

        cover_mock.assert_called_once()
        self.assertEqual(
            cover_mock.call_args.kwargs["synopsis"], "Short summary."
        )
        self.assertEqual(
            cover_mock.call_args.kwargs["settings"].output_name, "cover.png"
        )
        client.generate.assert_called_once()

    @patch("book_writer.writer.generate_chapter_cover")
    def test_generate_chapter_cover_assets_uses_summary(
        self, cover_mock: Mock
    ) -> None:
        settings = CoverSettings(enabled=True)
        client = Mock(spec=LMStudioClient)
        client.generate.return_value = "Condensed scene."
        cover_mock.return_value = Path("chapter_covers/001-chapter-one.png")

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            chapter_path = output_dir / "001-chapter-one.md"
            chapter_path.write_text("# Chapter One\n\nLong content", encoding="utf-8")

            generate_chapter_cover_assets(
                output_dir=output_dir,
                cover_settings=settings,
                client=client,
            )

        cover_mock.assert_called_once()
        self.assertEqual(
            cover_mock.call_args.kwargs["chapter_content"], "Condensed scene."
        )
        client.generate.assert_called_once()

    @patch("book_writer.writer.synthesize_text_audio")
    @patch("book_writer.writer.synthesize_chapter_audio")
    def test_generate_book_audio_overwrites_existing_audio(
        self,
        synthesize_chapter_mock: Mock,
        synthesize_text_mock: Mock,
    ) -> None:
        tts_settings = TTSSettings(enabled=True, overwrite_audio=True)
        synthesize_chapter_mock.return_value = Path("chapter.mp3")
        synthesize_text_mock.side_effect = [
            Path("book.mp3"),
            Path("back-cover-synopsis.mp3"),
        ]
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            chapter_path = output_dir / "001-chapter-one.md"
            chapter_path.write_text("# Chapter One\n\nContent\n", encoding="utf-8")
            synopsis_path = output_dir / "back-cover-synopsis.md"
            synopsis_path.write_text("Synopsis", encoding="utf-8")
            audio_dir = output_dir / tts_settings.audio_dirname
            audio_dir.mkdir()
            (audio_dir / "001-chapter-one.mp3").write_text(
                "existing", encoding="utf-8"
            )
            (audio_dir / "book.mp3").write_text("existing", encoding="utf-8")
            (audio_dir / "back-cover-synopsis.mp3").write_text(
                "existing", encoding="utf-8"
            )
            audiobook_text = build_audiobook_text(
                "Chapter One",
                "Marissa Bard",
                [chapter_path.read_text(encoding="utf-8")],
            )

            generate_book_audio(output_dir, tts_settings)

        synthesize_chapter_mock.assert_called_once_with(
            chapter_path=chapter_path,
            output_dir=audio_dir,
            settings=tts_settings,
            verbose=False,
        )
        synthesize_text_mock.assert_has_calls(
            [
                call(
                    text=audiobook_text,
                    output_path=audio_dir / "book.mp3",
                    settings=tts_settings,
                    verbose=False,
                    raise_on_error=True,
                ),
                call(
                    text="Synopsis",
                    output_path=audio_dir / "back-cover-synopsis.mp3",
                    settings=tts_settings,
                    verbose=False,
                ),
            ]
        )

    @patch("book_writer.writer.synthesize_text_audio")
    @patch("book_writer.writer.synthesize_chapter_audio")
    def test_generate_book_audio_book_only_skips_chapters_and_synopsis(
        self,
        synthesize_chapter_mock: Mock,
        synthesize_text_mock: Mock,
    ) -> None:
        tts_settings = TTSSettings(enabled=True, book_only=True)
        synthesize_text_mock.return_value = Path("book.mp3")

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            chapter_path = output_dir / "001-chapter-one.md"
            chapter_path.write_text("# Chapter One\n\nContent\n", encoding="utf-8")
            synopsis_path = output_dir / "back-cover-synopsis.md"
            synopsis_path.write_text("Synopsis", encoding="utf-8")
            audiobook_text = build_audiobook_text(
                "Chapter One",
                "Marissa Bard",
                [chapter_path.read_text(encoding="utf-8")],
            )

            generate_book_audio(output_dir, tts_settings)

        synthesize_chapter_mock.assert_not_called()
        synthesize_text_mock.assert_called_once_with(
            text=audiobook_text,
            output_path=output_dir / tts_settings.audio_dirname / "book.mp3",
            settings=tts_settings,
            verbose=False,
            raise_on_error=True,
        )

    @patch("book_writer.writer.synthesize_text_audio")
    @patch("book_writer.writer.synthesize_chapter_audio")
    def test_generate_book_audio_raises_when_book_audio_fails(
        self,
        synthesize_chapter_mock: Mock,
        synthesize_text_mock: Mock,
    ) -> None:
        tts_settings = TTSSettings(enabled=True)
        synthesize_chapter_mock.return_value = Path("audio/001-chapter-one.mp3")
        synthesize_text_mock.side_effect = TTSSynthesisError("no audio")

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            (output_dir / "book.md").write_text("# Title\n", encoding="utf-8")
            (output_dir / "001-chapter-one.md").write_text(
                "# Chapter One\n", encoding="utf-8"
            )

            with self.assertRaises(TTSSynthesisError) as context:
                generate_book_audio(output_dir, tts_settings)

            self.assertIn(
                "Failed to generate full audiobook audio",
                str(context.exception),
            )

    @patch("book_writer.writer.synthesize_chapter_video")
    def test_generate_book_videos_uses_existing_audio(
        self, synthesize_video_mock: Mock
    ) -> None:
        video_settings = VideoSettings(
            enabled=True,
            background_video=Path("background.mp4"),
        )
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            chapter_path = output_dir / "001-chapter-one.md"
            chapter_path.write_text("# Chapter One\n\nContent\n", encoding="utf-8")
            chapter_text = chapter_path.read_text(encoding="utf-8")
            audio_dir = output_dir / "audio"
            audio_dir.mkdir()
            audio_path = audio_dir / "001-chapter-one.mp3"
            audio_path.write_text("audio", encoding="utf-8")

            generate_book_videos(output_dir, video_settings, audio_dirname="audio")

        synthesize_video_mock.assert_called_once_with(
            audio_path=audio_path,
            output_dir=output_dir / video_settings.video_dirname,
            settings=video_settings,
            verbose=False,
            text=chapter_text,
        )

    @patch("book_writer.writer.generate_paragraph_image")
    @patch("book_writer.writer.synthesize_chapter_video_from_images")
    @patch("book_writer.writer._probe_audio_duration")
    def test_generate_book_videos_uses_paragraph_images(
        self,
        duration_mock: Mock,
        synthesize_video_mock: Mock,
        generate_image_mock: Mock,
    ) -> None:
        duration_mock.return_value = 10.0
        video_settings = VideoSettings(
            enabled=True,
            paragraph_images=ParagraphImageSettings(
                enabled=True,
                image_dirname="images",
            ),
        )
        generate_image_mock.side_effect = (
            lambda **kwargs: kwargs["output_path"]
        )
        client = MagicMock()
        client.generate.side_effect = [
            "Theme style",
            "First image description",
            "Second image description",
        ]
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            chapter_path = output_dir / "001-chapter-one.md"
            chapter_path.write_text(
                "# Chapter One\n\nFirst paragraph text.\n\nSecond paragraph text here.\n",
                encoding="utf-8",
            )
            audio_dir = output_dir / "audio"
            audio_dir.mkdir()
            audio_path = audio_dir / "001-chapter-one.mp3"
            audio_path.write_text("audio", encoding="utf-8")

            generate_book_videos(
                output_dir,
                video_settings,
                audio_dirname="audio",
                client=client,
            )

        self.assertEqual(client.generate.call_count, 3)
        prompts = [call.args[0] for call in client.generate.call_args_list]
        self.assertIn("Previous image: None yet.", prompts[1])
        self.assertIn("Previous image: First image description", prompts[2])
        self.assertEqual(generate_image_mock.call_count, 2)
        synthesize_video_mock.assert_called_once()
        durations = synthesize_video_mock.call_args.kwargs["durations"]
        self.assertEqual(len(durations), 2)
        self.assertAlmostEqual(sum(durations), 10.0, places=3)

    @patch("book_writer.writer.generate_book_pdf")
    def test_compile_book_uses_chapters(self, generate_pdf_mock: Mock) -> None:
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            chapter_path = output_dir / "001-chapter-one.md"
            chapter_path.write_text("# Chapter One\n\nContent\n", encoding="utf-8")

            compile_book(output_dir)

        generate_pdf_mock.assert_called_once()

    @patch("book_writer.writer.subprocess.run")
    def test_compile_book_skips_invalid_outline(
        self, run_mock: Mock
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()
            chapter_path = output_dir / "001-chapter-one.md"
            chapter_path.write_text("# Chapter One\n\nContent\n", encoding="utf-8")
            (output_dir / "book.md").write_text(
                "---\n"
                'title: "Draft Title"\n'
                'author: "Marissa Bard"\n'
                "---\n\n"
                "# Outline\n\n"
                "# Chapter One\n\n"
                "Content\n",
                encoding="utf-8",
            )

            compile_book(output_dir)

            compiled = (output_dir / "book.md").read_text(encoding="utf-8")
            outline_section = compiled.split("# Outline", 1)[1].split(
                "\\pagebreak", 1
            )[0]
            self.assertIn("- Chapter One", outline_section)
            self.assertNotIn("# Chapter One", outline_section)
            self.assertNotIn("Content", outline_section)

        self.assertEqual(run_mock.call_count, 2)

    @patch("book_writer.writer.synthesize_text_audio")
    @patch("book_writer.writer.synthesize_chapter_video")
    @patch("book_writer.writer.synthesize_chapter_audio")
    @patch("book_writer.writer.subprocess.run")
    def test_write_book_generates_audio_for_each_chapter(
        self,
        run_mock: Mock,
        synthesize_chapter_mock: Mock,
        synthesize_video_mock: Mock,
        synthesize_text_mock: Mock,
    ) -> None:
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
            "Mystery",
        ]
        tts_settings = TTSSettings(enabled=True)
        synthesize_chapter_mock.return_value = None

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            files = write_book(
                items, output_dir, client, tts_settings=tts_settings
            )
            audiobook_text = build_audiobook_text(
                "Chapter One",
                "Marissa Bard",
                [path.read_text(encoding="utf-8") for path in files],
            )

        synthesize_chapter_mock.assert_has_calls(
            [
                call(
                    chapter_path=files[0],
                    output_dir=files[0].parent / tts_settings.audio_dirname,
                    settings=tts_settings,
                    verbose=False,
                ),
                call(
                    chapter_path=files[1],
                    output_dir=files[1].parent / tts_settings.audio_dirname,
                    settings=tts_settings,
                    verbose=False,
                ),
            ]
        )
        self.assertEqual(synthesize_chapter_mock.call_count, 2)
        synthesize_text_mock.assert_has_calls(
            [
                call(
                    text=audiobook_text,
                    output_path=output_dir
                    / tts_settings.audio_dirname
                    / "book.mp3",
                    settings=tts_settings,
                    verbose=False,
                    raise_on_error=True,
                ),
                call(
                    text="Synopsis text",
                    output_path=output_dir
                    / tts_settings.audio_dirname
                    / "back-cover-synopsis.mp3",
                    settings=tts_settings,
                    verbose=False,
                ),
            ]
        )
        self.assertEqual(synthesize_text_mock.call_count, 2)
        synthesize_video_mock.assert_not_called()
        self.assertEqual(run_mock.call_count, 2)

    @patch("book_writer.writer.synthesize_text_audio")
    @patch("book_writer.writer.synthesize_chapter_video")
    @patch("book_writer.writer.synthesize_chapter_audio")
    @patch("book_writer.writer.subprocess.run")
    def test_write_book_generates_chapter_video_when_audio_exists(
        self,
        run_mock: Mock,
        synthesize_chapter_mock: Mock,
        synthesize_video_mock: Mock,
        synthesize_text_mock: Mock,
    ) -> None:
        items = [OutlineItem(title="Chapter One", level=1)]
        client = MagicMock()
        client.generate.side_effect = [
            "Chapter content",
            "Chapter summary",
            "Synopsis text",
            "Mystery",
        ]
        video_settings = VideoSettings(enabled=True, background_video=Path("bg.mp4"))

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"

            def _create_audio(*_args: object, **kwargs: object) -> Path:
                audio_dir = kwargs["output_dir"]
                audio_dir.mkdir(parents=True, exist_ok=True)
                audio_path = audio_dir / "001-chapter-one.mp3"
                audio_path.write_bytes(b"audio")
                return audio_path

            synthesize_chapter_mock.side_effect = _create_audio

            written_files = write_book(
                items,
                output_dir,
                client,
                tts_settings=TTSSettings(enabled=True),
                video_settings=video_settings,
            )

        synthesize_video_mock.assert_called_once()
        video_kwargs = synthesize_video_mock.call_args.kwargs
        self.assertIn("# Chapter One", video_kwargs["text"])
        self.assertEqual(video_kwargs["audio_path"].name, "001-chapter-one.mp3")
        self.assertEqual(
            video_kwargs["output_dir"], written_files[0].parent / "video"
        )
        self.assertEqual(run_mock.call_count, 2)

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
            "Mystery",
        ]

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            write_book(items, output_dir, client)

        second_prompt = client.generate.call_args_list[2][0][0]
        self.assertIn("Previous chapter context:", second_prompt)
        self.assertIn("Chapter one summary", second_prompt)
        self.assertEqual(run_mock.call_count, 2)

    @patch("book_writer.writer.subprocess.run")
    def test_write_book_resumes_from_progress(self, run_mock: Mock) -> None:
        items = [
            OutlineItem(title="Chapter One", level=1),
            OutlineItem(title="Chapter Two", level=1),
        ]
        client = MagicMock()
        client.generate.side_effect = [
            "Chapter two content",
            "Chapter two summary",
            "Synopsis text",
            "Mystery",
        ]

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "001-chapter-one.md").write_text(
                "# Chapter One\n\nSaved content.\n", encoding="utf-8"
            )
            save_book_progress(
                output_dir,
                {
                    "status": "in_progress",
                    "total_steps": 2,
                    "completed_steps": 1,
                    "previous_chapter": {
                        "title": "Chapter One",
                        "content": "Saved summary",
                    },
                    "nextsteps_sections": [],
                    "book_title": "My Book",
                    "byline": "Marissa Bard",
                },
            )

            write_book(
                items,
                output_dir,
                client,
                book_title="My Book",
                resume=True,
            )

            progress = json.loads(
                (output_dir / ".book_writer_progress.json").read_text(encoding="utf-8")
            )

        first_prompt = client.generate.call_args_list[0][0][0]
        self.assertIn("Previous chapter context:", first_prompt)
        self.assertIn("Saved summary", first_prompt)
        self.assertEqual(progress["status"], "completed")
        self.assertEqual(run_mock.call_count, 2)

    @patch("book_writer.writer.subprocess.run")
    def test_write_book_restarts_when_outline_hash_changes(
        self, run_mock: Mock
    ) -> None:
        items = [OutlineItem(title="Chapter One", level=1)]
        client = MagicMock()
        client.generate.side_effect = [
            "New chapter content",
            "New chapter summary",
            "Synopsis text",
            "Mystery",
        ]

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            stale_path = output_dir / "001-stale.md"
            stale_path.write_text("# Stale Chapter\n\nOld content.\n", encoding="utf-8")
            save_book_progress(
                output_dir,
                {
                    "status": "in_progress",
                    "total_steps": 1,
                    "completed_steps": 0,
                    "previous_chapter": None,
                    "nextsteps_sections": [],
                    "book_title": "Old Book",
                    "byline": "Marissa Bard",
                    "outline_hash": "old-hash",
                },
            )

            files = write_book(
                items,
                output_dir,
                client,
                book_title="New Book",
                resume=True,
                outline_hash="new-hash",
            )

            self.assertEqual(len(files), 1)
            self.assertFalse(stale_path.exists())
            self.assertIn("# Chapter One", files[0].read_text(encoding="utf-8"))

        self.assertEqual(run_mock.call_count, 2)

    @patch("book_writer.writer.subprocess.run")
    def test_write_book_restarts_when_outline_hash_missing(
        self, run_mock: Mock
    ) -> None:
        items = [OutlineItem(title="Chapter One", level=1)]
        client = MagicMock()
        client.generate.side_effect = [
            "New chapter content",
            "New chapter summary",
            "Synopsis text",
            "Mystery",
        ]

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            stale_path = output_dir / "001-stale.md"
            stale_path.write_text("# Stale Chapter\n\nOld content.\n", encoding="utf-8")
            save_book_progress(
                output_dir,
                {
                    "status": "in_progress",
                    "total_steps": 1,
                    "completed_steps": 0,
                    "previous_chapter": None,
                    "nextsteps_sections": [],
                    "book_title": "Old Book",
                    "byline": "Marissa Bard",
                },
            )

            files = write_book(
                items,
                output_dir,
                client,
                book_title="New Book",
                resume=True,
                outline_hash="new-hash",
            )

            self.assertEqual(len(files), 1)
            self.assertFalse(stale_path.exists())
            self.assertIn("# Chapter One", files[0].read_text(encoding="utf-8"))

        self.assertEqual(run_mock.call_count, 2)

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
            "Mystery",
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

        self.assertEqual(run_mock.call_count, 2)

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
            "Mystery",
        ]

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            write_book(items, output_dir, client)

        synopsis_prompt = client.generate.call_args_list[-2][0][0]
        self.assertIn("Outline:\n- Chapter One\n  - Section A", synopsis_prompt)
        self.assertEqual(run_mock.call_count, 2)

    def test_build_chapter_context_prompt_mentions_chapter(self) -> None:
        prompt = build_chapter_context_prompt("Chapter One", "Some chapter text.")

        self.assertIn("Chapter title: Chapter One", prompt)
        self.assertIn("Chapter content:", prompt)

    def test_build_chapter_context_prompt_includes_tone(self) -> None:
        prompt = build_chapter_context_prompt(
            "Chapter One", "Some chapter text.", tone="novel"
        )

        self.assertIn("novel", prompt)

    def test_build_synopsis_prompt_mentions_outline_and_content(self) -> None:
        prompt = build_synopsis_prompt(
            "Chapter One", "- Chapter One", "Full book content."
        )

        self.assertIn("Book title: Chapter One", prompt)
        self.assertIn("Outline:", prompt)
        self.assertIn("Book content:", prompt)

    def test_build_book_markdown_includes_title_outline_and_chapters(self) -> None:
        markdown = build_book_markdown(
            "Book Title",
            "- Chapter One",
            [ChapterLayout(title="Chapter One", content="# Chapter One\n\nText")],
            "Marissa Bard",
        )

        self.assertIn('lang: "en"', markdown)
        self.assertIn("# Book Title", markdown)
        self.assertIn("### By Marissa Bard", markdown)
        self.assertIn("# Outline", markdown)
        self.assertIn("# Chapter One", markdown)

    def test_build_audiobook_text_includes_title_byline_and_chapters(self) -> None:
        audiobook_text = build_audiobook_text(
            "Book Title",
            "Marissa Bard",
            ["# Chapter One\n\nText", "# Chapter Two\n\nMore text"],
        )

        self.assertIn("Book Title", audiobook_text)
        self.assertIn("By Marissa Bard", audiobook_text)
        self.assertIn("# Chapter One", audiobook_text)
        self.assertIn("# Chapter Two", audiobook_text)

    def test_build_book_markdown_strips_emoji_for_latex(self) -> None:
        markdown = build_book_markdown(
            "Book 🌙 Title",
            "- Chapter 🌙 One",
            [
                ChapterLayout(
                    title="Chapter One", content="# Chapter One\n\nSecret 🌙 emoji"
                )
            ],
            "Marissa 🌙 Bard",
        )

        self.assertIn('lang: "en"', markdown)
        self.assertNotIn("🌙", markdown)
        self.assertIn("Book  Title", markdown)
        self.assertIn("- Chapter  One", markdown)
        self.assertIn("Secret  emoji", markdown)

    def test_build_book_markdown_respects_language(self) -> None:
        markdown = build_book_markdown(
            "Book Title",
            "- Chapter One",
            [ChapterLayout(title="Chapter One", content="# Chapter One\n\nText")],
            "Marissa Bard",
            language="fr",
        )

        self.assertIn('lang: "fr"', markdown)

    def test_build_book_title_prompt_mentions_outline_and_first_chapter(self) -> None:
        prompt = build_book_title_prompt("- Chapter One", "Chapter One")

        self.assertIn("Outline:", prompt)
        self.assertIn("First chapter: Chapter One", prompt)

    def test_generate_book_title_avoids_first_chapter_name(self) -> None:
        items = [OutlineItem(title="Chapter One", level=1)]
        client = MagicMock()
        client.generate.side_effect = ["Chapter One", "Different Title"]

        title = generate_book_title(items, client)

        self.assertEqual(title, "Different Title")

    @patch("book_writer.writer.subprocess.run")
    def test_write_book_uses_provided_book_title(self, run_mock: Mock) -> None:
        items = [OutlineItem(title="Chapter One", level=1)]
        client = MagicMock()
        client.generate.side_effect = [
            "Chapter content",
            "Chapter summary",
            "Synopsis text",
            "Mystery",
        ]

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            write_book(
                items,
                output_dir,
                client,
                book_title="Custom Title",
                byline="Custom Byline",
            )

            book_md = (output_dir / "book.md").read_text(encoding="utf-8")

        self.assertIn("# Custom Title", book_md)
        self.assertIn("### By Custom Byline", book_md)
        self.assertEqual(run_mock.call_count, 2)

    @patch("book_writer.writer.subprocess.run")
    def test_write_book_strips_duplicate_heading(self, run_mock: Mock) -> None:
        items = [OutlineItem(title="Chapter One", level=1)]
        client = MagicMock()
        client.generate.side_effect = [
            "# Chapter One\n\nBody text.",
            "Chapter summary",
            "Synopsis text",
            "Mystery",
        ]

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            files = write_book(items, output_dir, client)

            chapter_text = files[0].read_text(encoding="utf-8").strip().splitlines()

        self.assertEqual(chapter_text[0], "# Chapter One")
        self.assertNotEqual(chapter_text[1].strip(), "# Chapter One")
        self.assertEqual(run_mock.call_count, 2)

    @patch("book_writer.writer.subprocess.run")
    def test_write_book_strips_duplicate_bold_heading(self, run_mock: Mock) -> None:
        items = [OutlineItem(title="Chapter One", level=1)]
        client = MagicMock()
        client.generate.side_effect = [
            "**Chapter One**\n\nBody text.",
            "Chapter summary",
            "Synopsis text",
            "Mystery",
        ]

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            files = write_book(items, output_dir, client)

            chapter_text = files[0].read_text(encoding="utf-8").strip().splitlines()

        self.assertEqual(chapter_text[0], "# Chapter One")
        self.assertEqual(chapter_text[1].strip(), "")
        self.assertNotEqual(chapter_text[2].strip(), "Chapter One")
        self.assertEqual(run_mock.call_count, 2)

    def test_build_expand_paragraph_prompt_includes_context(self) -> None:
        expand_prompt = (
            Path(__file__).resolve().parents[1] / "EXPAND_PROMPT.md"
        ).read_text(encoding="utf-8").strip()
        prompt = build_expand_paragraph_prompt(
            current="Current paragraph.",
            previous="Previous paragraph.",
            next_paragraph="Next paragraph.",
            section_heading="Section One",
            tone="instructive self help guide",
        )

        self.assertIn("Write in an instructive self help guide style.", prompt)
        self.assertIn(expand_prompt, prompt)
        self.assertIn("Section heading: Section One", prompt)
        self.assertIn("Previous section/paragraph:", prompt)
        self.assertIn("Next section/paragraph:", prompt)
        self.assertIn("Current paragraph/section:", prompt)

    def test_build_prompt_includes_tone_preface(self) -> None:
        items = [OutlineItem(title="Chapter One", level=1)]
        prompt = build_prompt(items, items[0], tone="instructive self help guide")

        self.assertTrue(
            prompt.startswith("Write in an instructive self help guide style.")
        )

    def test_build_prompt_raises_for_unknown_tone(self) -> None:
        items = [OutlineItem(title="Chapter One", level=1)]

        with self.assertRaises(ValueError):
            build_prompt(items, items[0], tone="unknown-tone")

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

        self.assertEqual(run_mock.call_count, 2)

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

        self.assertEqual(run_mock.call_count, 2)

    @patch("book_writer.writer.subprocess.run")
    def test_expand_book_limits_to_selected_chapters(
        self, run_mock: Mock
    ) -> None:
        client = MagicMock()
        client.generate.return_value = "Expanded paragraph."

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            chapter_one = output_dir / "001-chapter-one.md"
            chapter_two = output_dir / "002-chapter-two.md"
            chapter_one.write_text(
                "# Chapter One\n\nOriginal paragraph.", encoding="utf-8"
            )
            chapter_two.write_text(
                "# Chapter Two\n\nOriginal paragraph.", encoding="utf-8"
            )

            expanded_files = expand_book(
                output_dir, client, chapter_files=[chapter_one]
            )

            updated_one = chapter_one.read_text(encoding="utf-8")
            updated_two = chapter_two.read_text(encoding="utf-8")
            self.assertIn("Expanded paragraph.", updated_one)
            self.assertIn("Original paragraph.", updated_two)
            self.assertEqual(expanded_files, [chapter_one])

        self.assertEqual(run_mock.call_count, 2)

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
        self.assertEqual(run_mock.call_count, 2)

    @patch("book_writer.writer.synthesize_text_audio")
    @patch("book_writer.writer.synthesize_chapter_audio")
    @patch("book_writer.writer.subprocess.run")
    def test_expand_book_generates_chapter_audio(
        self,
        run_mock: Mock,
        synthesize_chapter_mock: Mock,
        synthesize_text_mock: Mock,
    ) -> None:
        client = MagicMock()
        client.generate.return_value = "Expanded paragraph."
        tts_settings = TTSSettings(enabled=True)

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            chapter_path = output_dir / "001-chapter-one.md"
            chapter_path.write_text(
                "# Chapter One\n\nOriginal paragraph.", encoding="utf-8"
            )

            expand_book(output_dir, client, tts_settings=tts_settings)
            audiobook_text = build_audiobook_text(
                "Chapter One",
                "Marissa Bard",
                [chapter_path.read_text(encoding="utf-8")],
            )

        synthesize_chapter_mock.assert_called_once_with(
            chapter_path=chapter_path,
            output_dir=chapter_path.parent / tts_settings.audio_dirname,
            settings=tts_settings,
            verbose=False,
        )
        synthesize_text_mock.assert_called_once_with(
            text=audiobook_text,
            output_path=output_dir / tts_settings.audio_dirname / "book.mp3",
            settings=tts_settings,
            verbose=False,
            raise_on_error=True,
        )
        self.assertEqual(run_mock.call_count, 2)

    @patch("book_writer.writer.synthesize_chapter_audio")
    @patch("book_writer.writer.subprocess.run")
    def test_expand_book_regenerates_audio_when_existing_audio_found(
        self, run_mock: Mock, synthesize_mock: Mock
    ) -> None:
        client = MagicMock()
        client.generate.return_value = "Expanded paragraph."

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            chapter_path = output_dir / "001-chapter-one.md"
            chapter_path.write_text(
                "# Chapter One\n\nOriginal paragraph.", encoding="utf-8"
            )
            audio_dir = output_dir / "audio"
            audio_dir.mkdir(parents=True, exist_ok=True)
            (audio_dir / "001-chapter-one.mp3").write_text("existing", encoding="utf-8")

            expand_book(output_dir, client)

        self.assertTrue(synthesize_mock.called)
        _, kwargs = synthesize_mock.call_args
        settings = kwargs["settings"]
        self.assertTrue(settings.enabled)
        self.assertEqual(run_mock.call_count, 2)

    @patch("book_writer.writer.subprocess.run")
    def test_generate_book_pdf_calls_pandoc(self, run_mock: Mock) -> None:
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            chapter_path = output_dir / "001-chapter-one.md"
            chapter_path.write_text("# Chapter One\n\nText", encoding="utf-8")
            (output_dir / "cover.png").write_text("cover", encoding="utf-8")
            chapter_cover_dir = output_dir / "chapter_covers"
            chapter_cover_dir.mkdir(parents=True, exist_ok=True)
            (chapter_cover_dir / "001-chapter-one.png").write_text(
                "chapter cover", encoding="utf-8"
            )
            (output_dir / "back-cover-synopsis.md").write_text(
                "A suspenseful synopsis.", encoding="utf-8"
            )

            pdf_path = generate_book_pdf(
                output_dir=output_dir,
                title="Chapter One",
                outline_text="- Chapter One",
                chapter_files=[chapter_path],
                byline="Marissa Bard",
            )

            book_md = (output_dir / "book.md").read_text(encoding="utf-8")
            self.assertIn("### By Marissa Bard", book_md)
            self.assertIn("![Cover image](cover.png){.cover-image}", book_md)
            self.assertIn(
                '<img src="chapter_covers/001-chapter-one.png" class="chapter-cover"',
                book_md,
            )
            self.assertIn("\\BgThispage", book_md)
            self.assertIn("# Back Cover", book_md)
            self.assertIn("A suspenseful synopsis.", book_md)
            self.assertEqual(pdf_path.name, "book.pdf")

        run_mock.assert_has_calls(
            [
                call(
                    [
                        "pandoc",
                        "book.md",
                        "--from",
                        "markdown+yaml_metadata_block+fenced_divs+link_attributes",
                        "--pdf-engine=xelatex",
                        "-o",
                        "book.pdf",
                    ],
                    check=True,
                    cwd=output_dir,
                ),
                call(
                    [
                        "pandoc",
                        "book.md",
                        "--from",
                        "markdown+yaml_metadata_block+fenced_divs+link_attributes",
                        "--toc",
                        "--css",
                        "epub.css",
                        "--epub-cover-image",
                        "cover.png",
                        "-o",
                        "book.epub",
                    ],
                    check=True,
                    cwd=output_dir,
                ),
            ]
        )

    @patch("book_writer.writer.subprocess.run")
    def test_generate_book_pdf_uses_non_png_chapter_cover(
        self, run_mock: Mock
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            chapter_path = output_dir / "001-chapter-one.md"
            chapter_path.write_text("# Chapter One\n\nText", encoding="utf-8")
            chapter_cover_dir = output_dir / "chapter_covers"
            chapter_cover_dir.mkdir(parents=True, exist_ok=True)
            (chapter_cover_dir / "001-chapter-one.JPG").write_text(
                "chapter cover", encoding="utf-8"
            )

            generate_book_pdf(
                output_dir=output_dir,
                title="Chapter One",
                outline_text="- Chapter One",
                chapter_files=[chapter_path],
                byline="Marissa Bard",
            )

            book_md = (output_dir / "book.md").read_text(encoding="utf-8")
            self.assertIn(
                '<img src="chapter_covers/001-chapter-one.JPG" class="chapter-cover"',
                book_md,
            )

        self.assertEqual(run_mock.call_count, 2)
        epub_call = run_mock.call_args_list[1]
        self.assertNotIn("--epub-cover-image", epub_call.args[0])

    def test_ensure_epub_css_styles_chapter_title_page(self) -> None:
        with TemporaryDirectory() as tmpdir:
            css_path = _ensure_epub_css(Path(tmpdir))

            css_text = css_path.read_text(encoding="utf-8")

        self.assertIn(".chapter-title-page", css_text)
        self.assertIn(".chapter-title-page .chapter-cover", css_text)

    @patch("book_writer.writer.subprocess.run")
    def test_generate_book_pdf_handles_missing_pandoc(self, run_mock: Mock) -> None:
        run_mock.side_effect = FileNotFoundError("pandoc")

        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            chapter_path = output_dir / "001-chapter-one.md"
            chapter_path.write_text("# Chapter One\n\nText", encoding="utf-8")

            with self.assertRaises(RuntimeError) as context:
                generate_book_pdf(
                    output_dir=output_dir,
                    title="Chapter One",
                    outline_text="- Chapter One",
                    chapter_files=[chapter_path],
                    byline="Marissa Bard",
                )

        self.assertIn(
            "pandoc is required to generate PDFs and EPUBs", str(context.exception)
        )

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
        request_obj, kwargs = urlopen_mock.call_args
        payload = json.loads(request_obj[0].data.decode("utf-8"))
        base_prompt = (Path(__file__).resolve().parents[1] / "PROMPT.md").read_text(
            encoding="utf-8"
        ).strip()
        self.assertTrue(
            payload["messages"][1]["content"].startswith(f"{base_prompt}\n\nPrompt")
        )
        self.assertNotIn("timeout", kwargs)

    def test_reset_context_uses_fallback_endpoint(self) -> None:
        response = Mock()
        response.read.return_value = b""
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        urlopen_mock = Mock(
            side_effect=[
                HTTPError(
                    "http://localhost:1234/v1/chat/reset",
                    404,
                    "Not Found",
                    None,
                    None,
                ),
                response,
            ]
        )

        with patch("book_writer.writer.request.urlopen", urlopen_mock):
            client = LMStudioClient(base_url="http://localhost:1234", model="demo-model")
            supported = client.reset_context()

        self.assertTrue(supported)
        self.assertEqual(urlopen_mock.call_count, 2)

    def test_reset_context_returns_false_when_unsupported(self) -> None:
        urlopen_mock = Mock(
            side_effect=[
                HTTPError(
                    "http://localhost:1234/v1/chat/reset",
                    404,
                    "Not Found",
                    None,
                    None,
                ),
                HTTPError(
                    "http://localhost:1234/v1/reset",
                    404,
                    "Not Found",
                    None,
                    None,
                ),
            ]
        )

        with patch("book_writer.writer.request.urlopen", urlopen_mock):
            client = LMStudioClient(base_url="http://localhost:1234", model="demo-model")
            supported = client.reset_context()

        self.assertFalse(supported)
        self.assertEqual(urlopen_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
