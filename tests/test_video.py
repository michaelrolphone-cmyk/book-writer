import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from book_writer.video import (
    ParagraphImageSettings,
    VideoSettings,
    _build_ffmpeg_command,
    _format_srt_timestamp,
    _write_word_captions,
    generate_paragraph_image,
    synthesize_chapter_video,
    synthesize_chapter_video_from_images,
)


class TestVideo(unittest.TestCase):
    def test_synthesize_chapter_video_returns_none_when_disabled(self) -> None:
        with TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "chapter.mp4"
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
            audio_path = Path(tmpdir) / "chapter.mp4"
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
            audio_path = Path(tmpdir) / "chapter.mp4"
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
            audio_path = Path(tmpdir) / "chapter.mp4"
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

    @patch("book_writer.video.subprocess.run")
    @patch("book_writer.video._probe_audio_duration")
    def test_synthesize_chapter_video_adds_word_captions(
        self, duration_mock: Mock, run_mock: Mock
    ) -> None:
        duration_mock.return_value = 3.0
        with patch("book_writer.video._ffmpeg_supports_filter", return_value=True):
            with TemporaryDirectory() as tmpdir:
                background_video = Path(tmpdir) / "background.mp4"
                background_video.write_bytes(b"video")
                audio_path = Path(tmpdir) / "chapter.mp4"
                audio_path.write_bytes(b"audio")
                output_dir = Path(tmpdir) / "video"
                settings = VideoSettings(enabled=True, background_video=background_video)

                synthesize_chapter_video(
                    audio_path=audio_path,
                    output_dir=output_dir,
                    settings=settings,
                    text="Hello world",
                )

        run_mock.assert_called_once()
        command = run_mock.call_args[0][0]
        command_text = " ".join(command)
        self.assertIn("-vf", command)
        self.assertIn("subtitles=", command_text)
        self.assertIn("captions.srt", command_text)
        self.assertIn(
            "force_style='Fontsize=48,Alignment=2,Outline=2,Shadow=1'",
            command_text,
        )

    @patch("book_writer.video.subprocess.run")
    @patch("book_writer.video._probe_audio_duration")
    def test_synthesize_chapter_video_skips_captions_when_filter_missing(
        self, duration_mock: Mock, run_mock: Mock
    ) -> None:
        duration_mock.return_value = 3.0
        with patch("book_writer.video._ffmpeg_supports_filter", return_value=False):
            with TemporaryDirectory() as tmpdir:
                background_video = Path(tmpdir) / "background.mp4"
                background_video.write_bytes(b"video")
                audio_path = Path(tmpdir) / "chapter.mp4"
                audio_path.write_bytes(b"audio")
                output_dir = Path(tmpdir) / "video"
                settings = VideoSettings(enabled=True, background_video=background_video)

                synthesize_chapter_video(
                    audio_path=audio_path,
                    output_dir=output_dir,
                    settings=settings,
                    text="Hello world",
                )

        run_mock.assert_called_once()
        command = run_mock.call_args[0][0]
        self.assertNotIn("-vf", command)

    def test_build_ffmpeg_command_quotes_subtitle_path(self) -> None:
        command = _build_ffmpeg_command(
            background_video=Path("background.mp4"),
            audio_path=Path("chapter.mp4"),
            output_path=Path("chapter.mp4"),
            subtitle_path=Path("chapter:1's.srt"),
        )

        filter_index = command.index("-vf") + 1
        self.assertEqual(
            command[filter_index],
            "subtitles=filename='chapter:1\\'s.srt':force_style="
            "'Fontsize=48,Alignment=2,Outline=2,Shadow=1'",
        )

    def test_write_word_captions_writes_srt_file(self) -> None:
        with TemporaryDirectory() as tmpdir:
            subtitle_path = Path(tmpdir) / "captions.srt"

            result = _write_word_captions(
                "Hello world", duration_seconds=2.0, output_path=subtitle_path
            )

            self.assertTrue(result)
            contents = subtitle_path.read_text(encoding="utf-8")
            self.assertIn("Hello", contents)
            self.assertIn("world", contents)
            self.assertIn("00:00:00,000 --> 00:00:01,000", contents)
            self.assertIn("00:00:01,000 --> 00:00:02,000", contents)

    def test_format_srt_timestamp_formats_milliseconds(self) -> None:
        self.assertEqual(_format_srt_timestamp(61.234), "00:01:01,234")

    @patch("book_writer.video.subprocess.run")
    def test_generate_paragraph_image_runs_command(
        self, run_mock: Mock
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "image.png"
            settings = ParagraphImageSettings(
                enabled=True,
                model_path=Path("model"),
            )

            def _run_side_effect(*_args: object, **_kwargs: object) -> None:
                output_path.write_bytes(b"image")

            run_mock.side_effect = _run_side_effect

            result = generate_paragraph_image(
                prompt="A vivid scene",
                output_path=output_path,
                settings=settings,
            )

            self.assertEqual(result, output_path)
            run_mock.assert_called_once()

    @patch("book_writer.video.subprocess.run")
    def test_synthesize_chapter_video_from_images_runs_ffmpeg(
        self, run_mock: Mock
    ) -> None:
        with TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "chapter.mp4"
            audio_path.write_bytes(b"audio")
            image_dir = Path(tmpdir) / "images"
            image_dir.mkdir()
            image_paths = [
                image_dir / "img-1.png",
                image_dir / "img-2.png",
            ]
            for path in image_paths:
                path.write_bytes(b"image")
            output_dir = Path(tmpdir) / "video"
            settings = VideoSettings(
                enabled=True,
                paragraph_images=ParagraphImageSettings(
                    enabled=True, width=640, height=360
                ),
            )

            output_path = synthesize_chapter_video_from_images(
                audio_path=audio_path,
                output_dir=output_dir,
                image_paths=image_paths,
                durations=[1.0, 2.0],
                settings=settings,
            )

            self.assertEqual(output_path, output_dir / "chapter.mp4")
            run_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
