import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

from yt_dlp.utils import DownloadError


# Keep subtitle tests independent of Whisper/GPU imports in modules.__init__.
spec = importlib.util.spec_from_file_location(
    "subtitles", Path(__file__).resolve().parents[1] / "modules" / "subtitles.py"
)
subtitles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subtitles)


class SubtitleTests(unittest.TestCase):
    def test_choose_track_prefers_matching_manual_then_matching_automatic(self):
        catalog = {
            "manual": {"en": [{"url": "manual"}]},
            "automatic": {"zh-TW": [{"url": "automatic"}]},
        }
        self.assertEqual(
            subtitles.choose_subtitle_track(catalog, "zh"), ("automatic", "zh-TW")
        )
        catalog["manual"]["zh-Hant"] = [{"url": "manual-zh"}]
        self.assertEqual(
            subtitles.choose_subtitle_track(catalog, "zh"), ("manual", "zh-Hant")
        )

    def test_choose_track_falls_back_to_any_manual_track(self):
        catalog = {
            "manual": {"ja": [{"url": "manual"}]},
            "automatic": {"en-orig": [{"url": "automatic"}]},
        }
        self.assertEqual(
            subtitles.choose_subtitle_track(catalog, "ko"), ("manual", "ja")
        )

    def test_txt_removes_timestamps_and_markup(self):
        self.assertEqual(subtitles.srt_to_text(
            '1\r\n00:00:01,000 --> 00:00:02,000\r\n<b>你好</b> &amp; hello\r\n\r\n'
            '2\r\n00:00:02,000 --> 00:00:03,000\r\n第二行\r\n'
        ), '你好 & hello\n第二行')

    @patch.object(subtitles.yt_dlp, "YoutubeDL")
    def test_catalog_keeps_sources_separate(self, factory):
        factory.return_value.__enter__.return_value.extract_info.return_value = {
            "title": "影片", "subtitles": {"en": [{"url": "manual"}]},
            "automatic_captions": {
                "en-orig": [{"url": "https://example.test/captions?lang=en"}],
                "en": [{"url": "https://example.test/captions?lang=en"}],
                "zh-Hant": [{"url": "https://example.test/captions?lang=en&tlang=zh-Hant"}],
            },
        }
        result = subtitles.list_subtitles("https://example.com/video")
        self.assertEqual(list(result["manual"]), ["en"])
        self.assertEqual(list(result["automatic"]), ["en-orig"])

    @patch.object(subtitles.shutil, "which", return_value="ffmpeg")
    @patch.object(subtitles.yt_dlp, "YoutubeDL")
    def test_download_selects_only_requested_source_and_language(self, factory, which):
        def create_download(options):
            manager = MagicMock()
            def extract(*args, **kwargs):
                path = Path(options["outtmpl"]).parent / "subtitle.en.srt"
                path.write_text('1\n00:00:00,000 --> 00:00:01,000\nHello\n', encoding="utf-8")
            manager.__enter__.return_value.extract_info.side_effect = extract
            return manager
        factory.side_effect = create_download
        self.assertEqual(subtitles.download_subtitle("url", "automatic", "en.*", "TXT"), "Hello")
        options = factory.call_args.args[0]
        self.assertFalse(options["writesubtitles"])
        self.assertTrue(options["writeautomaticsub"])
        self.assertEqual(options["subtitleslangs"], [r"en\.\*"])
        self.assertFalse(Path(options["outtmpl"]).parent.exists())

    @patch.object(subtitles.yt_dlp, "YoutubeDL")
    def test_chat_replay_is_not_a_caption(self, factory):
        info = {"subtitles": {"live_chat": [{"ext": "json"}]},
                "automatic_captions": {"live_chat": [{"ext": "json"}]}}
        factory.return_value.__enter__.return_value.extract_info.return_value = info
        catalog = subtitles.list_subtitles("https://example.com/video")
        self.assertEqual(catalog["manual"], {})
        self.assertEqual(catalog["automatic"], {})
        self.assertIsNone(subtitles.choose_subtitle_track(catalog))
        info["subtitles"]["zh-TW"] = [{"ext": "vtt"}]
        catalog = subtitles.list_subtitles("https://example.com/video")
        self.assertEqual(list(catalog["manual"]), ["zh-TW"])

    @patch.object(subtitles.shutil, "which", return_value=None)
    def test_missing_ffmpeg_is_actionable(self, which):
        with self.assertRaisesRegex(ValueError, "FFmpeg"):
            subtitles.download_subtitle("url", "manual", "en", "SRT")

    @patch.object(subtitles.time, "sleep")
    @patch.object(subtitles.shutil, "which", return_value="ffmpeg")
    @patch.object(subtitles.yt_dlp, "YoutubeDL")
    def test_429_retries_then_shows_actionable_message(self, factory, which, sleep):
        manager = MagicMock()
        manager.__enter__.return_value.extract_info.side_effect = DownloadError(
            "\x1b[0;31mERROR:\x1b[0m HTTP Error 429: Too Many Requests"
        )
        factory.return_value = manager
        with self.assertRaisesRegex(subtitles.SubtitleRateLimitError, "10～30 分鐘"):
            subtitles.download_subtitle("url", "automatic", "zh-Hant", "SRT")
        self.assertEqual(factory.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [2, 5])


if __name__ == "__main__":
    unittest.main()
