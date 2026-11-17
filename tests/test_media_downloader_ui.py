from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class MediaDownloaderUITests(unittest.TestCase):
    def test_format_quality_download_and_stale_result(self):
        fake = SimpleNamespace(
            path=str(Path(__file__).resolve()), title="測試影片", extension="mp4", size=1024,
        )
        with (
            patch("modules.media_downloader.download_media", return_value=fake) as download,
            patch("modules.media_downloader.cleanup_media_download"),
        ):
            app = AppTest.from_file(
                str(Path(__file__).resolve().parents[1] / "youtube_toolbox.py"), default_timeout=30,
            ).run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.tabs[3].label, "📥 下載影片／音訊")
            app.text_input(key="media_url").set_value("https://youtu.be/dQw4w9WgXcQ").run()
            images = app.get("image")
            self.assertEqual(len(images), 1)
            self.assertIn("dQw4w9WgXcQ", images[0].proto.imgs[0].url)
            self.assertEqual(images[0].proto.imgs[0].caption, "")
            app.selectbox(key="media_quality_MP4").select("720p")
            app.button(key="media_prepare").click().run()
            self.assertEqual(len(app.exception), 0)
            download.assert_called_once()
            self.assertEqual(
                download.call_args.args[:3],
                ("https://youtu.be/dQw4w9WgXcQ", "MP4", "720p"),
            )
            self.assertEqual(len([button for button in app.get("download_button") if button.key == "media_save"]), 1)
            app.selectbox(key="media_quality_MP4").select("480p").run()
            self.assertEqual(len([button for button in app.get("download_button") if button.key == "media_save"]), 0)


if __name__ == "__main__":
    unittest.main()
