import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch


spec = importlib.util.spec_from_file_location(
    "media_downloader_test_module",
    Path(__file__).resolve().parents[1] / "modules" / "media_downloader.py",
)
downloader = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = downloader
spec.loader.exec_module(downloader)


class MediaDownloaderTests(unittest.TestCase):
    def test_thumbnail_url_supports_common_youtube_urls(self):
        expected = "https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg"
        self.assertEqual(
            downloader.youtube_thumbnail_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10"),
            expected,
        )
        self.assertEqual(
            downloader.youtube_thumbnail_url("https://youtu.be/dQw4w9WgXcQ"), expected,
        )
        self.assertEqual(
            downloader.youtube_thumbnail_url("https://www.youtube.com/shorts/dQw4w9WgXcQ"), expected,
        )

    def test_thumbnail_url_ignores_incomplete_or_non_youtube_urls(self):
        self.assertIsNone(downloader.youtube_thumbnail_url("https://youtu.be/test"))
        self.assertIsNone(downloader.youtube_thumbnail_url("https://example.com/dQw4w9WgXcQ"))

    @patch.object(downloader.shutil, "which", return_value="ffmpeg")
    @patch.object(downloader.yt_dlp, "YoutubeDL")
    def test_mp4_uses_height_ceiling_and_returns_file(self, factory, which):
        def make_manager(options):
            manager = MagicMock()

            def extract(url, download):
                path = Path(options["outtmpl"]).parent / "video.mp4"
                path.write_bytes(b"video")
                return {"title": "測試影片", "id": "abc"}

            manager.__enter__.return_value.extract_info.side_effect = extract
            return manager

        factory.side_effect = make_manager
        result = downloader.download_media("https://youtu.be/abc", "MP4", "1080p")
        try:
            self.assertEqual(result.title, "測試影片")
            self.assertEqual(result.extension, "mp4")
            self.assertIn("height<=1080", factory.call_args.args[0]["format"])
            self.assertEqual(factory.call_args.args[0]["merge_output_format"], "mp4")
        finally:
            downloader.cleanup_media_download(result.path)

    @patch.object(downloader.shutil, "which", return_value="ffmpeg")
    @patch.object(downloader.yt_dlp, "YoutubeDL")
    def test_mp3_uses_requested_bitrate(self, factory, which):
        def make_manager(options):
            manager = MagicMock()

            def extract(url, download):
                (Path(options["outtmpl"]).parent / "audio.mp3").write_bytes(b"audio")
                return {"title": "Audio", "id": "abc"}

            manager.__enter__.return_value.extract_info.side_effect = extract
            return manager

        factory.side_effect = make_manager
        result = downloader.download_media("https://youtu.be/abc", "MP3", "192 kbps")
        try:
            processor = factory.call_args.args[0]["postprocessors"][0]
            self.assertEqual(processor["preferredquality"], "192")
            self.assertEqual(processor["preferredcodec"], "mp3")
        finally:
            downloader.cleanup_media_download(result.path)

    @patch.object(downloader.shutil, "which", return_value=None)
    def test_missing_ffmpeg_is_actionable(self, which):
        with self.assertRaisesRegex(ValueError, "FFmpeg"):
            downloader.download_media("url", "MP3", "最高品質")


if __name__ == "__main__":
    unittest.main()
