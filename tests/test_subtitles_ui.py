"""Verify subtitle selection, download, and stale-result handling offline."""

from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class SubtitleUITests(unittest.TestCase):
    def test_choose_source_language_and_format_and_invalidate_old_result(self):
        catalog = {
            "title": "測試影片",
            "manual": {"en": [{"name": "English"}]},
            "automatic": {"zh-TW": [{"name": "繁體中文"}]},
        }
        with (
            patch("modules.subtitles.list_subtitles", return_value=catalog),
            patch("modules.subtitles.download_subtitle", return_value="測試字幕") as download,
        ):
            app = AppTest.from_file(
                str(Path(__file__).resolve().parents[1] / "youtube_toolbox.py"),
                default_timeout=30,
            ).run()
            self.assertEqual(len(app.exception), 0)
            app.text_input(key="cc_url").set_value("https://youtu.be/test")
            app.button(key="cc_list").click().run()
            self.assertEqual(app.selectbox(key="cc_language_manual").value, "en")
            app.radio(key="cc_source").set_value("automatic").run()
            self.assertEqual(app.selectbox(key="cc_language_automatic").value, "zh-TW")
            app.selectbox(key="cc_format").select("TXT").run()
            app.button(key="cc_prepare").click().run()
            download.assert_called_once_with("https://youtu.be/test", "automatic", "zh-TW", "TXT")
            self.assertEqual(len(app.get("download_button")), 1)
            app.selectbox(key="cc_format").select("SRT").run()
            self.assertEqual(len(app.get("download_button")), 0)
            app.text_input(key="cc_url").set_value("https://youtu.be/other").run()
            self.assertEqual(len(app.get("download_button")), 0)
            self.assertEqual(len(app.exception), 0)


if __name__ == "__main__":
    unittest.main()
