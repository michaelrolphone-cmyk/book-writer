import runpy
import unittest
from unittest.mock import patch


class TestMain(unittest.TestCase):
    def test_module_entrypoint_calls_cli_main(self) -> None:
        with patch("book_writer.cli.main", return_value=0) as mocked_main:
            with self.assertRaises(SystemExit) as context:
                runpy.run_module("book_writer", run_name="__main__")

        mocked_main.assert_called_once()
        self.assertEqual(context.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
