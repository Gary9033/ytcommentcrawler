"""Regression checks for lazy inference, GPU retries and original audio downloads."""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from modules import transcription


class TranscriptionTests(unittest.TestCase):
    def setUp(self):
        self.transcriber = transcription.WhisperTranscriber()
        self.transcriber.model = Mock()
        self.info = SimpleNamespace(language="zh", duration=60.0)
        self.segment = SimpleNamespace(start=0.0, end=30.0, text="測試")

    def test_completion_is_reported_only_after_lazy_inference(self):
        reports = []

        def segments():
            self.assertFalse(any(fraction == 1 for fraction, _ in reports))
            yield self.segment

        self.transcriber.model.transcribe.return_value = (segments(), self.info)
        with self.assertLogs(transcription.logger, level="INFO") as logs:
            result, info = self.transcriber.transcribe(
                "audio.webm", batch_size=1,
                progress_callback=lambda fraction, message: reports.append((fraction, message)),
            )
        self.assertEqual(result, [self.segment])
        self.assertIs(info, self.info)
        self.assertEqual(reports[-1][0], 1.0)
        self.assertIn("1 段", logs.output[-1])
        self.assertNotIn("batch_size", self.transcriber.model.transcribe.call_args.kwargs)

    def test_late_gpu_oom_restarts_with_smaller_batches_without_duplicate_segments(self):
        batch_four, batch_two = Mock(), Mock()

        def failing_segments():
            yield self.segment
            raise RuntimeError("CUDA failed with error out of memory")

        batch_four.transcribe.return_value = (failing_segments(), self.info)
        batch_two.transcribe.return_value = (iter([self.segment]), self.info)
        with patch.object(transcription, "BatchedInferencePipeline", side_effect=[batch_four, batch_two]):
            result, _ = self.transcriber.transcribe("audio.webm", language="zh", batch_size=4)
        self.assertEqual(result, [self.segment])
        self.assertEqual(batch_four.transcribe.call_args.kwargs["batch_size"], 4)
        self.assertEqual(batch_two.transcribe.call_args.kwargs["batch_size"], 2)
        self.assertEqual(batch_two.transcribe.call_args.kwargs["language"], "zh")
        self.assertFalse(batch_two.transcribe.call_args.kwargs["without_timestamps"])

    def test_batch_oom_can_fall_back_to_original_sequential_mode(self):
        pipeline = Mock()
        pipeline.transcribe.side_effect = RuntimeError("CUDA_ERROR_OUT_OF_MEMORY")
        self.transcriber.model.transcribe.return_value = (iter([self.segment]), self.info)
        with patch.object(transcription, "BatchedInferencePipeline", return_value=pipeline):
            result, _ = self.transcriber.transcribe("audio.webm", batch_size=2)
        self.assertEqual(result, [self.segment])
        self.assertNotIn("batch_size", self.transcriber.model.transcribe.call_args.kwargs)

    def test_non_memory_errors_are_not_retried_or_reported_complete(self):
        reports = []

        def failing_segments():
            yield self.segment
            raise RuntimeError("Invalid audio")

        self.transcriber.model.transcribe.return_value = (failing_segments(), self.info)
        with self.assertRaises(transcription.TranscriptionError):
            self.transcriber.transcribe(
                "audio.webm", batch_size=1,
                progress_callback=lambda fraction, message: reports.append((fraction, message)),
            )
        self.assertFalse(any(fraction == 1 for fraction, _ in reports))
        self.assertEqual(self.transcriber.model.transcribe.call_count, 1)

    def test_sequential_oom_terminates(self):
        self.transcriber.model.transcribe.side_effect = RuntimeError("out of memory")
        with self.assertRaises(transcription.TranscriptionError):
            self.transcriber.transcribe("audio.webm", batch_size=1)
        self.assertEqual(self.transcriber.model.transcribe.call_count, 1)

    def test_loaded_model_is_reused(self):
        self.transcriber.model = None
        with patch.object(transcription, "WhisperModel") as model:
            self.transcriber.load_model()
            self.transcriber.load_model()
        model.assert_called_once_with("large-v3-turbo", device="cuda", compute_type="float16")

    def test_empty_audio_reaches_completion(self):
        self.transcriber.model.transcribe.return_value = (iter([]), self.info)
        result, _ = self.transcriber.transcribe("silence.webm", batch_size=1)
        self.assertEqual(result, [])


class DownloadTests(unittest.TestCase):
    def test_download_returns_original_compressed_audio_and_cleanup_removes_it(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "audio"
            audio = base.with_suffix(".webm")
            audio.write_bytes(b"test")
            with patch.object(transcription.yt_dlp, "YoutubeDL") as downloader:
                instance = downloader.return_value.__enter__.return_value
                instance.extract_info.return_value = {"title": "影片", "ext": "webm"}
                instance.prepare_filename.return_value = str(audio)
                path, title = transcription.download_audio("https://youtu.be/test", base)
            self.assertEqual(path, str(audio))
            self.assertEqual(title, "影片")
            options = downloader.call_args.args[0]
            self.assertNotIn("postprocessors", options)
            self.assertTrue(options["noplaylist"])
            self.assertEqual(options["outtmpl"], str(base) + ".%(ext)s")
            transcription.cleanup_audio(path)
            self.assertFalse(audio.exists())

    def test_default_paths_do_not_collide_between_requests(self):
        with patch.object(transcription.yt_dlp, "YoutubeDL") as downloader:
            instance = downloader.return_value.__enter__.return_value
            instance.extract_info.return_value = {"ext": "webm"}
            instance.prepare_filename.return_value = "audio.webm"
            with patch.object(os.path, "isfile", return_value=True):
                transcription.download_audio("https://youtu.be/test")
                transcription.download_audio("https://youtu.be/test")
        first, second = [call.args[0]["outtmpl"] for call in downloader.call_args_list]
        self.assertNotEqual(first, second)

    def test_missing_output_is_an_error(self):
        with patch.object(transcription.yt_dlp, "YoutubeDL") as downloader:
            instance = downloader.return_value.__enter__.return_value
            instance.extract_info.return_value = {"ext": "webm"}
            instance.prepare_filename.return_value = "missing-audio.webm"
            with self.assertRaises(transcription.AudioDownloadError):
                transcription.download_audio("https://youtu.be/test")


if __name__ == "__main__":
    unittest.main()
