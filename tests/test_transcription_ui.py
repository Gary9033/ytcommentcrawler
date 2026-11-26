"""Exercise the Streamlit flow without network calls or a second GPU model."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import streamlit as st
from streamlit.testing.v1 import AppTest
from streamlit.delta_generator import DeltaGenerator


class TranscriptionUITests(unittest.TestCase):
    def test_start_is_disabled_during_work_and_restored_after_success_or_error(self):
        original_button = DeltaGenerator.button
        rendered = []

        def button(container, label, *args, **kwargs):
            if kwargs.get("key") in ("whisper_start", "whisper_busy"):
                rendered.append((kwargs["key"], kwargs.get("disabled", False)))
            return original_button(container, label, *args, **kwargs)

        def check_busy(*args, **kwargs):
            self.assertEqual(rendered[-1], ("whisper_busy", True))
            self.assertTrue(st.session_state.whisper_running)

        def download(url):
            check_busy()
            return "test.webm", "測試影片"

        def transcribe(*args, **kwargs):
            check_busy()
            return [SimpleNamespace(start=0., end=1., text="測試")], SimpleNamespace(language="zh", duration=1.)

        st.cache_resource.clear()
        try:
            with (
                patch.object(DeltaGenerator, "button", button),
                patch("modules.subtitles.list_subtitles", return_value={
                    "title": "測試影片", "manual": {}, "automatic": {},
                }),
                patch("modules.download_audio", side_effect=download) as audio,
                patch("modules.cleanup_audio"),
                patch("modules.WhisperTranscriber") as factory,
            ):
                factory.return_value.transcribe.side_effect = transcribe
                app = AppTest.from_file(
                    str(Path(__file__).resolve().parents[1] / "youtube_toolbox.py"),
                    default_timeout=30,
                ).run()
                app.text_input(key="whisper").set_value("https://youtu.be/7-V-NWQpF7I").run()
                app.button(key="whisper_start").click().run()
                self.assertEqual(len(app.exception), 0)
                audio.assert_called_once()
                self.assertFalse(app.button(key="whisper_start").disabled)
                self.assertFalse(app.text_input(key="whisper").disabled)
                self.assertFalse(app.selectbox[0].disabled)
                self.assertFalse(app.selectbox[1].disabled)
                self.assertTrue(app.session_state.transcript_lines)
                app.run()
                audio.assert_called_once()  # An ordinary rerun must not restart work.
                app.text_input(key="whisper").set_value("https://youtu.be/Gpl7IZkmYbg").run()
                audio.side_effect = RuntimeError("下載失敗")
                app.button(key="whisper_start").click().run()
                self.assertEqual(len(app.exception), 0)
                self.assertFalse(app.session_state.whisper_running)
                self.assertFalse(app.button(key="whisper_start").disabled)
                self.assertFalse(app.text_input(key="whisper").disabled)
                self.assertFalse(app.selectbox[0].disabled)
                self.assertFalse(app.selectbox[1].disabled)
                self.assertTrue(any("下載失敗" in x.value for x in app.error))
        finally:
            st.cache_resource.clear()

    def test_start_uses_selected_cc_and_never_downloads_audio_even_on_cc_failure(self):
        catalog = {
            "title": "測試影片", "manual": {"zh-TW": [{"name": "繁體中文"}]},
            "automatic": {"en-orig": [{"name": "English"}]},
        }
        with (
            patch("modules.subtitles.list_subtitles", return_value=catalog),
            patch("modules.subtitles.download_subtitle", return_value=
                  "1\n00:00:00,000 --> 00:00:01,000\n平台字幕\n") as cc,
            patch("modules.download_audio") as audio,
            patch("modules.WhisperTranscriber") as whisper,
        ):
            app = AppTest.from_file(
                str(Path(__file__).resolve().parents[1] / "youtube_toolbox.py"),
                default_timeout=30,
            ).run()
            app.text_input(key="whisper").set_value("https://youtu.be/7-V-NWQpF7I").run()
            app.selectbox(key="whisper_cc_track").select(("automatic", "en-orig")).run()
            app.button(key="whisper_start").click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.session_state.transcript_cc["txt"], "平台字幕")
            self.assertFalse(app.text_input(key="whisper").disabled)
            self.assertFalse(app.button(key="whisper_start").disabled)
            cc.assert_called_once_with("https://youtu.be/7-V-NWQpF7I", "automatic", "en-orig", "SRT")
            app.button(key="whisper_start").click().run()
            cc.assert_called_once()  # Reuse already downloaded CC.
            app.session_state.whisper_cc_preview["result"] = None
            cc.side_effect = RuntimeError("字幕暫時無法下載")
            app.button(key="whisper_start").click().run()
            self.assertTrue(any("CC 字幕下載失敗" in x.value for x in app.error))
            self.assertFalse(app.session_state.whisper_running)
            self.assertFalse(app.text_input(key="whisper").disabled)
            self.assertIsNone(app.session_state.transcript_cc)
            self.assertEqual(len(app.exception), 0)
            audio.assert_not_called()
            whisper.assert_not_called()

    def test_incomplete_cc_session_is_reloaded_and_null_sources_are_safe(self):
        with patch("modules.subtitles.list_subtitles", return_value={
            "title": "無字幕", "manual": None, "automatic": None,
        }) as listing:
            app = AppTest.from_file(
                str(Path(__file__).resolve().parents[1] / "youtube_toolbox.py"),
                default_timeout=30,
            ).run()
            app.session_state.whisper_cc_preview = {
                "url": "https://youtu.be/7-V-NWQpF7I", "catalog": None,
                "error": None, "result": None,
            }
            app.text_input(key="whisper").set_value("https://youtu.be/7-V-NWQpF7I").run()
            self.assertEqual(len(app.exception), 0)
            listing.assert_called_once()
            self.assertTrue(any("沒有可用的 CC" in x.value for x in app.info))
            app.run()
            listing.assert_called_once()

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
                    "manual": {},
                    "automatic": {},
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
                app.text_input(key="whisper").set_value("https://youtu.be/7-V-NWQpF7I").run()
                app.button(key="whisper_start").click().run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.error), 0, [error.value for error in app.error])
                self.assertFalse(app.session_state.whisper_running)
                self.assertEqual(app.session_state.transcript_lines, [segment])
                self.assertIn("total", app.session_state.transcript_timings)
                self.assertTrue(any("完成" in item.value for item in app.success))
                self.assertEqual(transcriber.transcribe.call_args.kwargs["language"], "zh")
                self.assertEqual(transcriber.transcribe.call_args.kwargs["batch_size"], 4)
                self.assertIsNone(app.session_state.transcript_cc)
                cc_download.assert_not_called()

                # A new Streamlit run redefines get_transcriber; its cached resource
                # must remain the same instead of loading another GPU model.
                app.button(key="whisper_start").click().run()
                self.assertEqual(len(app.exception), 0)
                factory.assert_called_once_with("large-v3-turbo")
                self.assertEqual(download.call_count, 2)
                self.assertEqual(cleanup.call_count, 2)
                cc_download.assert_not_called()
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
            app.text_input(key="whisper").set_value("https://youtu.be/Gpl7IZkmYbg").run()
            self.assertFalse(any(x.key == "whisper_cc_text" for x in app.text_area))
            self.assertTrue(any("沒有可用的 CC" in x.value for x in app.info))
            app.text_input(key="whisper").set_value("https://youtu.be/abcdefghijk").run()
            self.assertTrue(any("無法確認 CC" in x.value for x in app.warning))
            self.assertEqual(len(app.exception), 0)


if __name__ == "__main__":
    unittest.main()
