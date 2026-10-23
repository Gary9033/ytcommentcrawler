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
            ):
                app = AppTest.from_file(str(app_path), default_timeout=30).run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(app.selectbox[1].value, 4)
                app.selectbox[0].select("中文")
                app.text_input(key="whisper").set_value("https://youtu.be/test").run()
                app.button[1].click().run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.error), 0, [error.value for error in app.error])
                self.assertFalse(app.session_state.whisper_running)
                self.assertEqual(app.session_state.transcript_lines, [segment])
                self.assertIn("total", app.session_state.transcript_timings)
                self.assertEqual(app.get("progress")[0].value, 100)
                self.assertEqual(transcriber.transcribe.call_args.kwargs["language"], "zh")
                self.assertEqual(transcriber.transcribe.call_args.kwargs["batch_size"], 4)

                # A new Streamlit run redefines get_transcriber; its cached resource
                # must remain the same instead of loading another GPU model.
                app.button[1].click().run()
                self.assertEqual(len(app.exception), 0)
                factory.assert_called_once_with("large-v3-turbo")
                self.assertEqual(download.call_count, 2)
                self.assertEqual(cleanup.call_count, 2)
        finally:
            st.cache_resource.clear()


if __name__ == "__main__":
    unittest.main()
