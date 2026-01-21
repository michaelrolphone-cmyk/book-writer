import unittest

from book_writer import gui


class TestGui(unittest.TestCase):
    def test_get_gui_html_contains_key_sections(self) -> None:
        html = gui.get_gui_html()

        self.assertIn("Book Writer Studio", html)
        self.assertIn("id=\"outlineShelf\"", html)
        self.assertIn("id=\"completedOutlineShelf\"", html)
        self.assertIn("id=\"bookShelf\"", html)
        self.assertIn("id=\"outlineSelect\"", html)
        self.assertIn("id=\"bookSelect\"", html)
        self.assertIn("id=\"chapterSelect\"", html)
        self.assertIn("id=\"homeView\"", html)
        self.assertIn("id=\"detailView\"", html)
        self.assertIn("id=\"detailBack\"", html)
        self.assertIn("id=\"workspacePanel\"", html)
        self.assertIn("id=\"outlineWorkspace\"", html)
        self.assertIn("id=\"bookWorkspace\"", html)
        self.assertIn("id=\"chapterShelf\"", html)
        self.assertIn("id=\"readerPanel\"", html)
        self.assertIn("id=\"outlineWorkspaceSummary\"", html)
        self.assertIn("id=\"chapterAudio\"", html)
        self.assertIn("id=\"chapterVideo\"", html)
        self.assertIn("id=\"bookAudio\"", html)
        self.assertIn("id=\"chapterView\"", html)
        self.assertIn("id=\"chapterBack\"", html)
        self.assertIn("id=\"chapterReaderBody\"", html)
        self.assertIn("id=\"chapterViewAudio\"", html)
        self.assertIn("id=\"chapterViewVideo\"", html)
        self.assertIn("Select a book before generating audio.", html)
        self.assertIn(
            "loadWorkspaceChapterContent(bookSelect.value, chapterSelect.value);",
            html,
        )
        self.assertIn("handoffChapterAudioToDetail", html)
        self.assertIn("No preview available.", html)
        self.assertIn(".workspace-actions {", html)
        self.assertIn("display: flex;", html)
        self.assertIn("width: auto;", html)
        book_shelf_index = html.index("id=\"bookShelf\"")
        outline_shelf_index = html.index("id=\"outlineShelf\"")
        self.assertLess(book_shelf_index, outline_shelf_index)
        reader_panel_index = html.index("id=\"readerPanel\"")
        media_panel_index = html.index("id=\"mediaPanel\"", reader_panel_index)
        reader_body_index = html.index("id=\"readerBody\"", reader_panel_index)
        self.assertLess(media_panel_index, reader_body_index)
        chapter_panel_index = html.index("id=\"chapterReaderPanel\"")
        chapter_media_index = html.index("id=\"chapterMediaPanel\"", chapter_panel_index)
        chapter_body_index = html.index("id=\"chapterReaderBody\"", chapter_panel_index)
        self.assertLess(chapter_media_index, chapter_body_index)
        self.assertIn("Neumorphic", gui.__doc__ or "")

    def test_save_gui_html_writes_file(self) -> None:
        with self.subTest("write and read back"):
            from tempfile import TemporaryDirectory
            from pathlib import Path

            with TemporaryDirectory() as tmpdir:
                path = gui.save_gui_html(Path(tmpdir) / "gui.html")
                self.assertTrue(path.exists())
                self.assertIn(gui.GUI_TITLE, path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
