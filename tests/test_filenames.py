import unittest

from book_writer.filenames import book_audio_filename, epub_filename, title_to_filename


class TestFilenames(unittest.TestCase):
    def test_title_to_filename_joins_title_words(self) -> None:
        self.assertEqual(title_to_filename("the quiet moon"), "TheQuietMoon")

    def test_title_to_filename_strips_punctuation(self) -> None:
        self.assertEqual(title_to_filename("Rise! @ the sun?"), "RiseTheSun")

    def test_title_to_filename_falls_back_when_empty(self) -> None:
        self.assertEqual(title_to_filename(""), "Untitled")

    def test_epub_filename_appends_extension(self) -> None:
        self.assertEqual(epub_filename("My Book"), "MyBook.epub")

    def test_book_audio_filename_appends_extension(self) -> None:
        self.assertEqual(book_audio_filename("My Book"), "MyBook.mp3")
