import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from book_writer import metadata


class TestMetadata(unittest.TestCase):
    def test_parse_genres_from_json_object(self) -> None:
        response = '{"genres": ["Fantasy", "Adventure"]}'

        result = metadata.parse_genres(response)

        self.assertEqual(result, ["Fantasy", "Adventure"])

    def test_parse_genres_from_json_array(self) -> None:
        response = '["Mystery", "Thriller"]'

        result = metadata.parse_genres(response)

        self.assertEqual(result, ["Mystery", "Thriller"])

    def test_parse_genres_from_delimited_text(self) -> None:
        response = "Romance, Drama\nAdventure"

        result = metadata.parse_genres(response)

        self.assertEqual(result, ["Romance", "Drama", "Adventure"])

    def test_write_book_meta_persists_genres(self) -> None:
        with TemporaryDirectory() as tmpdir:
            book_dir = Path(tmpdir) / "book"
            book_dir.mkdir()

            metadata.write_book_meta(book_dir, ["Sci-Fi", "Space Opera"])

            meta_path = book_dir / metadata.META_FILENAME
            meta = json.loads(meta_path.read_text(encoding="utf-8"))

        self.assertEqual(meta["genres"], ["Sci-Fi", "Space Opera"])
        self.assertEqual(meta["primary_genre"], "Sci-Fi")

    def test_resolve_primary_genre_prefers_simple_genres(self) -> None:
        result = metadata.resolve_primary_genre(
            ["Space Opera", "Science Fiction", "Adventure"]
        )

        self.assertEqual(result, "Sci-Fi")

    def test_resolve_primary_genre_maps_subgenres(self) -> None:
        result = metadata.resolve_primary_genre(["Eco Thriller", "Crime Mystery"])

        self.assertEqual(result, "Thriller")
