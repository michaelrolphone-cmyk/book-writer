import unittest
from urllib.parse import quote
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from book_writer import server


def _write_book_summary(book_dir: Path, text: str = "Summary") -> None:
    summary_dir = book_dir / "summaries"
    summary_dir.mkdir(parents=True, exist_ok=True)
    (summary_dir / "book-summary.md").write_text(text, encoding="utf-8")


def _write_chapter_summary(book_dir: Path, stem: str, text: str = "Summary") -> None:
    summary_dir = book_dir / "summaries" / "chapters"
    summary_dir.mkdir(parents=True, exist_ok=True)
    (summary_dir / f"{stem}.md").write_text(text, encoding="utf-8")


class TestServerHelpers(unittest.TestCase):
    def test_parse_tts_settings_defaults(self) -> None:
        settings = server._parse_tts_settings({})

        self.assertTrue(settings.enabled)
        self.assertEqual(settings.voice, "en-US-JennyNeural")
        self.assertEqual(settings.audio_dirname, "audio")
        self.assertFalse(settings.overwrite_audio)
        self.assertFalse(settings.book_only)

    def test_parse_video_settings_defaults(self) -> None:
        settings = server._parse_video_settings({})

        self.assertFalse(settings.enabled)
        self.assertEqual(settings.video_dirname, "video")
        self.assertIsNone(settings.background_video)
        self.assertFalse(settings.paragraph_images.enabled)
        self.assertEqual(settings.paragraph_images.image_dirname, "video_images")


class TestServerApi(unittest.TestCase):
    def test_send_file_handles_client_disconnect(self) -> None:
        with TemporaryDirectory() as tmpdir:
            media_path = Path(tmpdir) / "audio.mp3"
            media_path.write_text("audio", encoding="utf-8")

            class DummyWfile:
                def write(self, _body: bytes) -> None:
                    raise BrokenPipeError("client disconnected")

            class DummyHandler:
                def __init__(self) -> None:
                    self.wfile = DummyWfile()

                def send_response(self, _status: int) -> None:
                    return None

                def send_header(self, _key: str, _value: str) -> None:
                    return None

                def end_headers(self) -> None:
                    return None

            server._send_file(DummyHandler(), media_path)

    def test_list_outlines_returns_preview(self) -> None:
        with TemporaryDirectory() as tmpdir:
            outlines_dir = Path(tmpdir) / "outlines"
            outlines_dir.mkdir()
            outline_path = outlines_dir / "story.md"
            outline_path.write_text("# Book One\n\n## Chapter One\n", encoding="utf-8")

            result = server.list_outlines({"outlines_dir": str(outlines_dir)})

        self.assertEqual(len(result["outlines"]), 1)
        self.assertIn("Chapter One", result["outlines"][0]["preview"])
        self.assertEqual(result["outlines"][0]["item_count"], 1)

    def test_list_authors_returns_markdown_stems(self) -> None:
        with TemporaryDirectory() as tmpdir:
            authors_dir = Path(tmpdir) / "authors"
            authors_dir.mkdir()
            (authors_dir / "curious.md").write_text("persona", encoding="utf-8")
            (authors_dir / "ignore.txt").write_text("skip", encoding="utf-8")

            result = server.list_authors({"authors_dir": str(authors_dir)})

        self.assertEqual(result["authors"], ["curious"])

    def test_list_tones_returns_markdown_stems(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tones_dir = Path(tmpdir) / "tones"
            tones_dir.mkdir()
            (tones_dir / "warm.md").write_text("tone", encoding="utf-8")
            (tones_dir / "note.txt").write_text("skip", encoding="utf-8")

            result = server.list_tones({"tones_dir": str(tones_dir)})

        self.assertEqual(result["tones"], ["warm"])

    def test_list_outlines_skips_unreadable_files(self) -> None:
        with TemporaryDirectory() as tmpdir:
            outlines_dir = Path(tmpdir) / "outlines"
            outlines_dir.mkdir()
            good_outline = outlines_dir / "good.md"
            bad_outline = outlines_dir / "bad.md"
            good_outline.write_text("# Book One\n\n## Chapter One\n", encoding="utf-8")
            bad_outline.write_bytes(b"\xff\xfe\xfd")

            result = server.list_outlines({"outlines_dir": str(outlines_dir)})

        self.assertEqual(len(result["outlines"]), 1)
        self.assertEqual(result["outlines"][0]["path"], str(good_outline))

    def test_list_completed_outlines_returns_preview(self) -> None:
        with TemporaryDirectory() as tmpdir:
            outlines_dir = Path(tmpdir) / "completed_outlines"
            outlines_dir.mkdir()
            outline_path = outlines_dir / "archived.md"
            outline_path.write_text("# Book Two\n\n## Chapter Two\n", encoding="utf-8")

            result = server.list_completed_outlines(
                {"completed_outlines_dir": str(outlines_dir)}
            )

        self.assertEqual(len(result["outlines"]), 1)
        self.assertIn("Chapter Two", result["outlines"][0]["preview"])
        self.assertEqual(result["outlines"][0]["item_count"], 1)

    def test_list_books_returns_status(self) -> None:
        with TemporaryDirectory() as tmpdir:
            books_dir = Path(tmpdir) / "books"
            book_dir = books_dir / "sample"
            book_dir.mkdir(parents=True)
            first_content = "# Chapter One\n\n" + ("word " * 250)
            second_content = "# Chapter Two\n\n" + ("word " * 350)
            (book_dir / "001-chapter-one.md").write_text(
                first_content, encoding="utf-8"
            )
            (book_dir / "002-chapter-two.md").write_text(
                second_content, encoding="utf-8"
            )
            _write_book_summary(book_dir, "Saved summary")

            result = server.list_books({"books_dir": str(books_dir)})

        self.assertEqual(len(result["books"]), 1)
        self.assertTrue(result["books"][0]["has_text"])
        self.assertEqual(result["books"][0]["chapter_count"], 2)
        self.assertIsNone(result["books"][0]["book_audio_url"])
        self.assertFalse(result["books"][0]["has_cover"])
        expected_pages = server._estimate_page_count(
            first_content
        ) + server._estimate_page_count(second_content)
        self.assertEqual(result["books"][0]["page_count"], expected_pages)

    def test_list_books_handles_unreadable_chapters(self) -> None:
        with TemporaryDirectory() as tmpdir:
            books_dir = Path(tmpdir) / "books"
            good_dir = books_dir / "good"
            bad_dir = books_dir / "bad"
            good_dir.mkdir(parents=True)
            bad_dir.mkdir(parents=True)
            (good_dir / "001-chapter-one.md").write_text(
                "# Chapter One\n\nContent", encoding="utf-8"
            )
            (bad_dir / "001-chapter-one.md").write_bytes(b"\xff\xfe\xfd")
            _write_book_summary(good_dir, "Saved summary")

            result = server.list_books({"books_dir": str(books_dir)})

        book_paths = {entry["path"] for entry in result["books"]}
        self.assertEqual(book_paths, {str(good_dir), str(bad_dir)})
        titles = {entry["path"]: entry["title"] for entry in result["books"]}
        self.assertEqual(titles[str(bad_dir)], bad_dir.name)

    def test_list_books_includes_book_audio_url(self) -> None:
        with TemporaryDirectory() as tmpdir:
            books_dir = Path(tmpdir) / "books"
            book_dir = books_dir / "sample"
            audio_dir = book_dir / "audio"
            audio_dir.mkdir(parents=True)
            (book_dir / "001-chapter-one.md").write_text("# Chapter One", encoding="utf-8")
            (audio_dir / "book.mp3").write_text("audio", encoding="utf-8")
            _write_book_summary(book_dir, "Saved summary")

            result = server.list_books(
                {"books_dir": str(books_dir), "tts_audio_dir": "audio"}
            )

        expected_base = f"/media?book_dir={quote(str(book_dir))}"
        self.assertTrue(result["books"][0]["book_audio_url"].startswith(expected_base))

    def test_list_chapters_returns_titles(self) -> None:
        with TemporaryDirectory() as tmpdir:
            book_dir = Path(tmpdir) / "book"
            book_dir.mkdir()
            first = book_dir / "001-chapter-one.md"
            second = book_dir / "002-chapter-two.md"
            first_content = "# Chapter One\n\nContent " + ("word " * 300)
            second_content = "# Chapter Two\n\nContent " + ("word " * 10)
            first.write_text(first_content, encoding="utf-8")
            second.write_text(second_content, encoding="utf-8")
            _write_chapter_summary(book_dir, "001-chapter-one", "Saved summary")
            _write_chapter_summary(book_dir, "002-chapter-two", "Saved summary")

            result = server.list_chapters({"book_dir": str(book_dir)})

        self.assertEqual(len(result["chapters"]), 2)
        self.assertEqual(result["chapters"][0]["title"], "Chapter One")
        self.assertEqual(result["chapters"][1]["title"], "Chapter Two")
        self.assertIsNone(result["chapters"][0]["audio_url"])
        self.assertEqual(
            result["chapters"][0]["page_count"],
            server._estimate_page_count(first_content),
        )
        self.assertEqual(
            result["chapters"][1]["page_count"],
            server._estimate_page_count(second_content),
        )

    def test_list_chapters_includes_media_urls(self) -> None:
        with TemporaryDirectory() as tmpdir:
            book_dir = Path(tmpdir) / "book"
            audio_dir = book_dir / "audio"
            video_dir = book_dir / "video"
            cover_dir = book_dir / "chapter_covers"
            audio_dir.mkdir(parents=True)
            video_dir.mkdir()
            cover_dir.mkdir()
            first = book_dir / "001-chapter-one.md"
            first.write_text("# Chapter One\n\nContent", encoding="utf-8")
            (audio_dir / "001-chapter-one.mp3").write_text("audio", encoding="utf-8")
            (video_dir / "001-chapter-one.mp4").write_text("video", encoding="utf-8")
            (cover_dir / "001-chapter-one.png").write_text("cover", encoding="utf-8")
            _write_chapter_summary(book_dir, "001-chapter-one", "Saved summary")

            result = server.list_chapters(
                {
                    "book_dir": str(book_dir),
                    "audio_dirname": "audio",
                    "video_dirname": "video",
                    "chapter_cover_dir": "chapter_covers",
                }
            )

        expected_base = f"/media?book_dir={quote(str(book_dir))}"
        self.assertTrue(result["chapters"][0]["audio_url"].startswith(expected_base))
        self.assertTrue(result["chapters"][0]["video_url"].startswith(expected_base))
        self.assertTrue(result["chapters"][0]["cover_url"].startswith(expected_base))

    def test_get_chapter_content_returns_markdown(self) -> None:
        with TemporaryDirectory() as tmpdir:
            book_dir = Path(tmpdir) / "book"
            book_dir.mkdir()
            chapter = book_dir / "001-chapter-one.md"
            content = "# Chapter One\n\nContent " + ("word " * 100)
            chapter.write_text(content, encoding="utf-8")
            _write_chapter_summary(book_dir, "001-chapter-one", "Saved summary")

            result = server.get_chapter_content(
                {"book_dir": str(book_dir), "chapter": "001-chapter-one.md"}
            )

        self.assertEqual(result["title"], "Chapter One")
        self.assertIn("Content", result["content"])
        self.assertEqual(result["page_count"], server._estimate_page_count(content))

    def test_get_outline_content_returns_content(self) -> None:
        with TemporaryDirectory() as tmpdir:
            outline_path = Path(tmpdir) / "outline.md"
            outline_path.write_text("# Book One\n\n## Chapter One\n", encoding="utf-8")

            result = server.get_outline_content({"outline_path": str(outline_path)})

        self.assertEqual(result["title"], "Book One")
        self.assertIn("Chapter One", result["content"])
        self.assertEqual(result["item_count"], 1)

    @patch("book_writer.server.generate_outline")
    def test_generate_outline_api_writes_file(self, generate_mock: MagicMock) -> None:
        generate_mock.return_value = "# Book One\n\n## Chapter One\n"
        with TemporaryDirectory() as tmpdir:
            outlines_dir = Path(tmpdir) / "outlines"
            payload = {
                "prompt": "Write a sci-fi outline.",
                "outlines_dir": str(outlines_dir),
                "outline_name": "sci-fi.md",
            }
            result = server.generate_outline_api(payload)

            outline_path = Path(result["outline_path"])
            self.assertTrue(outline_path.exists())
            self.assertIn("Chapter One", outline_path.read_text(encoding="utf-8"))
            self.assertEqual(result["item_count"], 1)

    def test_save_outline_api_writes_content(self) -> None:
        with TemporaryDirectory() as tmpdir:
            outlines_dir = Path(tmpdir) / "outlines"
            payload = {
                "outline_path": "saved.md",
                "outlines_dir": str(outlines_dir),
                "content": "# Book One\n\n## Chapter One\n",
            }
            result = server.save_outline_api(payload)

            outline_path = Path(result["outline_path"])
            self.assertTrue(outline_path.exists())
            self.assertIn("Chapter One", outline_path.read_text(encoding="utf-8"))
            self.assertEqual(result["item_count"], 1)

    def test_get_chapter_content_includes_media_urls(self) -> None:
        with TemporaryDirectory() as tmpdir:
            book_dir = Path(tmpdir) / "book"
            audio_dir = book_dir / "audio"
            video_dir = book_dir / "video"
            cover_dir = book_dir / "chapter_covers"
            audio_dir.mkdir(parents=True)
            video_dir.mkdir()
            cover_dir.mkdir()
            chapter = book_dir / "001-chapter-one.md"
            chapter.write_text("# Chapter One\n\nContent", encoding="utf-8")
            (audio_dir / "001-chapter-one.mp3").write_text("audio", encoding="utf-8")
            (video_dir / "001-chapter-one.mp4").write_text("video", encoding="utf-8")
            (cover_dir / "001-chapter-one.png").write_text("cover", encoding="utf-8")
            _write_chapter_summary(book_dir, "001-chapter-one", "Saved summary")

            result = server.get_chapter_content(
                {
                    "book_dir": str(book_dir),
                    "chapter": "001-chapter-one.md",
                    "audio_dirname": "audio",
                    "video_dirname": "video",
                    "chapter_cover_dir": "chapter_covers",
                }
            )

        expected_base = f"/media?book_dir={quote(str(book_dir))}"
        self.assertTrue(result["audio_url"].startswith(expected_base))
        self.assertTrue(result["video_url"].startswith(expected_base))
        self.assertTrue(result["cover_url"].startswith(expected_base))

    def test_get_book_content_returns_synopsis(self) -> None:
        with TemporaryDirectory() as tmpdir:
            book_dir = Path(tmpdir) / "book"
            book_dir.mkdir()
            (book_dir / "001-chapter-one.md").write_text(
                "# Chapter One\n\nContent", encoding="utf-8"
            )
            (book_dir / "back-cover-synopsis.md").write_text(
                "Synopsis text.", encoding="utf-8"
            )
            _write_book_summary(book_dir, "Saved summary")

            result = server.get_book_content({"book_dir": str(book_dir)})

        self.assertEqual(result["synopsis"], "Synopsis text.")

    def test_list_books_schedules_summary_generation_when_missing(self) -> None:
        started: list[object] = []

        class DummyThread:
            def __init__(self, target: object, daemon: bool) -> None:
                self.target = target
                self.daemon = daemon

            def start(self) -> None:
                started.append(self)

        with TemporaryDirectory() as tmpdir:
            books_dir = Path(tmpdir) / "books"
            book_dir = books_dir / "sample"
            book_dir.mkdir(parents=True)
            (book_dir / "001-chapter-one.md").write_text(
                "# Chapter One\n\nContent", encoding="utf-8"
            )
            summary_path = book_dir / "summaries" / "book-summary.md"

            with patch("book_writer.server.threading.Thread", DummyThread):
                try:
                    result = server.list_books({"books_dir": str(books_dir)})
                finally:
                    server._SUMMARY_TASKS.clear()

            self.assertEqual(result["books"][0]["summary"], "")
            self.assertEqual(len(started), 1)
            self.assertFalse(summary_path.exists())

    def test_list_chapters_schedules_summary_generation_when_missing(self) -> None:
        started: list[object] = []

        class DummyThread:
            def __init__(self, target: object, daemon: bool) -> None:
                self.target = target
                self.daemon = daemon

            def start(self) -> None:
                started.append(self)

        with TemporaryDirectory() as tmpdir:
            book_dir = Path(tmpdir) / "book"
            book_dir.mkdir()
            chapter = book_dir / "001-chapter-one.md"
            chapter.write_text("# Chapter One\n\nContent", encoding="utf-8")
            summary_path = book_dir / "summaries" / "chapters" / "001-chapter-one.md"

            with patch("book_writer.server.threading.Thread", DummyThread):
                try:
                    result = server.list_chapters({"book_dir": str(book_dir)})
                finally:
                    server._SUMMARY_TASKS.clear()

            self.assertEqual(result["chapters"][0]["summary"], "")
            self.assertEqual(len(started), 1)
            self.assertFalse(summary_path.exists())

    def test_summary_generation_dedupes_background_tasks(self) -> None:
        started: list[object] = []

        class DummyThread:
            def __init__(self, target: object, daemon: bool) -> None:
                self.target = target
                self.daemon = daemon

            def start(self) -> None:
                started.append(self)

        with TemporaryDirectory() as tmpdir:
            books_dir = Path(tmpdir) / "books"
            book_dir = books_dir / "sample"
            book_dir.mkdir(parents=True)
            (book_dir / "001-chapter-one.md").write_text(
                "# Chapter One\n\nContent", encoding="utf-8"
            )

            with patch("book_writer.server.threading.Thread", DummyThread):
                try:
                    server.list_books({"books_dir": str(books_dir)})
                    server.list_books({"books_dir": str(books_dir)})
                finally:
                    server._SUMMARY_TASKS.clear()

            self.assertEqual(len(started), 1)

    def test_resolve_media_path_blocks_escape(self) -> None:
        with TemporaryDirectory() as tmpdir:
            book_dir = Path(tmpdir) / "book"
            book_dir.mkdir()
            media_path = book_dir / "audio" / "chapter.mp3"
            media_path.parent.mkdir()
            media_path.write_text("audio", encoding="utf-8")

            resolved = server._resolve_media_path(book_dir, "audio/chapter.mp3")

            self.assertEqual(resolved, media_path.resolve())
            with self.assertRaises(server.ApiError):
                server._resolve_media_path(book_dir, "../outside.mp3")

    def test_generate_book_calls_writer(self) -> None:
        with TemporaryDirectory() as tmpdir:
            outline_path = Path(tmpdir) / "outline.md"
            outline_path.write_text("# Book One\n\n## Chapter One\n", encoding="utf-8")
            output_dir = Path(tmpdir) / "output"

            with patch("book_writer.server.write_book") as write_book:
                write_book.return_value = [Path(tmpdir) / "001.md"]
                response = server.generate_book(
                    {
                        "outline_path": str(outline_path),
                        "output_dir": str(output_dir),
                    }
                )

                self.assertEqual(response["written_files"], [str(Path(tmpdir) / "001.md")])
                self.assertTrue(output_dir.exists())
                write_book.assert_called_once()

    def test_expand_book_supports_expand_only(self) -> None:
        with TemporaryDirectory() as tmpdir:
            book_dir = Path(tmpdir) / "book"
            book_dir.mkdir()
            first = book_dir / "001-chapter-one.md"
            second = book_dir / "002-chapter-two.md"
            first.write_text("# Chapter One", encoding="utf-8")
            second.write_text("# Chapter Two", encoding="utf-8")

            with patch("book_writer.server.expand_book") as expand_book:
                server.expand_book_api(
                    {
                        "expand_book": str(book_dir),
                        "expand_only": "2",
                    }
                )

        expand_book.assert_called_once()
        chapter_files = expand_book.call_args.kwargs["chapter_files"]
        self.assertEqual(chapter_files, [second])

    def test_generate_cover_api_invokes_cover_generation(self) -> None:
        with TemporaryDirectory() as tmpdir:
            book_dir = Path(tmpdir) / "book"
            book_dir.mkdir()
            (book_dir / "001-chapter-one.md").write_text(
                "# Chapter One\n", encoding="utf-8"
            )
            with patch("book_writer.server.generate_book_cover_asset") as cover_mock:
                response = server.generate_cover_api(
                    {
                        "book_dir": str(book_dir),
                        "cover_settings": {"model_path": "/tmp/resource"},
                    }
                )

        cover_mock.assert_called_once()
        self.assertIsNotNone(cover_mock.call_args.kwargs["client"])
        self.assertEqual(response["status"], "cover_generated")

    def test_generate_chapter_covers_api_invokes_generation(self) -> None:
        with TemporaryDirectory() as tmpdir:
            book_dir = Path(tmpdir) / "book"
            book_dir.mkdir()
            (book_dir / "001-chapter-one.md").write_text(
                "# Chapter One\n", encoding="utf-8"
            )
            with patch(
                "book_writer.server.generate_chapter_cover_assets"
            ) as cover_mock:
                cover_mock.return_value = [book_dir / "chapter_covers/001.png"]
                response = server.generate_chapter_covers_api(
                    {
                        "book_dir": str(book_dir),
                        "chapter": "1",
                        "chapter_cover_dir": "chapter_covers",
                        "cover_settings": {"model_path": "/tmp/resource"},
                    }
                )

        cover_mock.assert_called_once()
        self.assertIsNotNone(cover_mock.call_args.kwargs["client"])
        self.assertEqual(response["status"], "chapter_covers_generated")


if __name__ == "__main__":
    unittest.main()
