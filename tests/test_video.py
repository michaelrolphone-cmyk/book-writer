import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from book_writer.video import VideoSettings, synthesize_chapter_video


class TestVideo(unittest.TestCase):
    def test_synthesize_chapter_video_returns_none_when_disabled(self) -> None:
        with TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "chapter.mp3"
            audio_path.write_bytes(b"audio")
            output_dir = Path(tmpdir) / "video"
            settings = VideoSettings(enabled=False)

            result = synthesize_chapter_video(
                audio_path=audio_path,
                output_dir=output_dir,
                settings=settings,
            )

            self.assertIsNone(result)
            self.assertFalse(output_dir.exists())

    def test_synthesize_chapter_video_requires_background_video(self) -> None:
        with TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "chapter.mp3"
            audio_path.write_bytes(b"audio")
            output_dir = Path(tmpdir) / "video"
            settings = VideoSettings(enabled=True, background_video=None)

            with self.assertRaises(ValueError):
                synthesize_chapter_video(
                    audio_path=audio_path,
                    output_dir=output_dir,
                    settings=settings,
                )

    @patch("book_writer.video.subprocess.run")
    def test_synthesize_chapter_video_runs_ffmpeg(self, run_mock: Mock) -> None:
        with TemporaryDirectory() as tmpdir:
            background_video = Path(tmpdir) / "background.mp4"
            background_video.write_bytes(b"video")
            audio_path = Path(tmpdir) / "chapter.mp3"
            audio_path.write_bytes(b"audio")
            output_dir = Path(tmpdir) / "video"
            settings = VideoSettings(enabled=True, background_video=background_video)

            output_path = synthesize_chapter_video(
                audio_path=audio_path,
                output_dir=output_dir,
                settings=settings,
            )

            self.assertEqual(output_path, output_dir / "chapter.mp4")
            self.assertTrue(output_dir.exists())

        run_mock.assert_called_once()
        command = run_mock.call_args[0][0]
        self.assertIn("-nostdin", command)
        self.assertIn("-y", command)
        self.assertIn(str(background_video), command)
        self.assertIn(str(audio_path), command)

    @patch("book_writer.video.subprocess.run")
    def test_synthesize_chapter_video_handles_missing_ffmpeg(
        self, run_mock: Mock
    ) -> None:
        run_mock.side_effect = FileNotFoundError("ffmpeg")
        with TemporaryDirectory() as tmpdir:
            background_video = Path(tmpdir) / "background.mp4"
            background_video.write_bytes(b"video")
            audio_path = Path(tmpdir) / "chapter.mp3"
            audio_path.write_bytes(b"audio")
            output_dir = Path(tmpdir) / "video"
            settings = VideoSettings(enabled=True, background_video=background_video)

            with self.assertRaises(RuntimeError) as context:
                synthesize_chapter_video(
                    audio_path=audio_path,
                    output_dir=output_dir,
                    settings=settings,
                )

        self.assertIn("ffmpeg is required to generate chapter videos", str(context.exception))


if __name__ == "__main__":
    unittest.main()
