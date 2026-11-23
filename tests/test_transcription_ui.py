"""Exercise the Streamlit flow without network calls or a second GPU model."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import streamlit as st
from streamlit.testing.v1 import AppTest


class TranscriptionUITests(unittest.TestCase):
    def test_settings_progress_timings_and_model_cache_survive_reruns(self):
        st.cache_resource.clear()
        transcriber = Mock()
        segment = SimpleNamespace(start=0.0, end=30.0, text="測試", no_speech_prob=0.01)
        info = SimpleNamespace(language="zh", duration=30.0)

        def transcribe(path, language, batch_size, progress_callback):
            progress_callback(0.0, "前處理中")
            progress_callback(0.5, "辨識中")
            progress_callback(1.0, "完成")
            return [segment], info

        transcriber.transcribe.side_effect = transcribe
        app_path = Path(__file__).resolve().parents[1] / "youtube_toolbox.py"
        try:
            with (
                patch("modules.WhisperTranscriber", return_value=transcriber) as factory,
                patch("modules.download_audio", return_value=("test.webm", "測試影片")) as download,
                patch("modules.cleanup_audio") as cleanup,
                patch("modules.subtitles.list_subtitles", return_value={
                    "title": "測試影片",
                    "manual": {"zh-TW": [{"name": "繁體中文"}]},
                    "automatic": {"en-orig": [{"name": "English"}]},
                }),
                patch(
                    "modules.subtitles.download_subtitle",
                    return_value="1\n00:00:00,000 --> 00:00:01,000\n平台字幕\n",
                ) as cc_download,
            ):
                app = AppTest.from_file(str(app_path), default_timeout=30).run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(app.selectbox[1].value, 4)
                app.selectbox[0].select("中文")
                app.text_input(key="whisper").set_value("https://youtu.be/test").run()
                app.button(key="whisper_start").click().run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.error), 0, [error.value for error in app.error])
                self.assertFalse(app.session_state.whisper_running)
                self.assertEqual(app.session_state.transcript_lines, [segment])
                self.assertIn("total", app.session_state.transcript_timings)
                self.assertEqual(app.get("progress")[0].value, 100)
                self.assertEqual(transcriber.transcribe.call_args.kwargs["language"], "zh")
                self.assertEqual(transcriber.transcribe.call_args.kwargs["batch_size"], 4)
                self.assertEqual(app.session_state.transcript_cc["language"], "zh-TW")
                cc_download.assert_called_once_with(
                    "https://youtu.be/test", "manual", "zh-TW", "SRT"
                )
                download_labels = [button.label for button in app.get("download_button")]
                self.assertIn("📥 平台 CC SRT", download_labels)
                self.assertIn("📥 平台 CC TXT", download_labels)

                # A new Streamlit run redefines get_transcriber; its cached resource
                # must remain the same instead of loading another GPU model.
                app.button(key="whisper_start").click().run()
                self.assertEqual(len(app.exception), 0)
                factory.assert_called_once_with("large-v3-turbo")
                self.assertEqual(download.call_count, 2)
                self.assertEqual(cleanup.call_count, 2)
                self.assertEqual(cc_download.call_count, 2)
        finally:
            st.cache_resource.clear()

    def test_cc_preview_avoids_whisper_and_clears_when_url_changes(self):
        catalog = {
            "title": "測試影片", "manual": {"zh-TW": [{"name": "繁體中文"}]},
            "automatic": {},
        }
        with (
            patch("modules.subtitles.list_subtitles", side_effect=[
                catalog, {"title": "無字幕", "manual": {}, "automatic": {}},
                RuntimeError("連線失敗"),
            ]) as listing,
            patch("modules.subtitles.download_subtitle", return_value=
                  "1\n00:00:00,000 --> 00:00:01,000\n平台字幕\n") as cc_download,
            patch("modules.download_audio") as audio,
            patch("modules.WhisperTranscriber") as whisper,
        ):
            app = AppTest.from_file(
                str(Path(__file__).resolve().parents[1] / "youtube_toolbox.py"),
                default_timeout=30,
            ).run()
            app.text_input(key="whisper").set_value("https://youtu.be/dQw4w9WgXcQ").run()
            self.assertTrue(any("不必自行語音轉錄" in x.value for x in app.success))
            self.assertGreater(len(app.get("image")), 0)
            app.button(key="whisper_cc_prepare").click().run()
            self.assertEqual(app.text_area(key="whisper_cc_text").value, "平台字幕")
            cc_download.assert_called_once_with("https://youtu.be/dQw4w9WgXcQ", "manual", "zh-TW", "SRT")
            listing.assert_called_once()
            audio.assert_not_called()
            whisper.assert_not_called()
            app.text_input(key="whisper").set_value("https://youtu.be/other").run()
            self.assertFalse(any(x.key == "whisper_cc_text" for x in app.text_area))
            self.assertTrue(any("沒有可用的 CC" in x.value for x in app.info))
            app.text_input(key="whisper").set_value("https://youtu.be/error").run()
            self.assertTrue(any("無法確認 CC" in x.value for x in app.warning))
            self.assertEqual(len(app.exception), 0)


if __name__ == "__main__":
    unittest.main()
