import unittest

from book_writer import gui


class TestGui(unittest.TestCase):
    def test_get_gui_html_contains_key_sections(self) -> None:
        html = gui.get_gui_html()

        self.assertIn("Book Writer Studio", html)
        self.assertIn("class=\"shelf\"", html)
        self.assertIn("class=\"book-card\"", html)
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
