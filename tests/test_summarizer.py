import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import summarizer


class ExtractVideoIdTests(unittest.TestCase):
    def test_supported_urls(self):
        video_id = "dQw4w9WgXcQ"
        urls = [
            f"https://www.youtube.com/watch?v={video_id}&t=10",
            f"https://youtu.be/{video_id}?si=abc",
            f"https://youtube.com/shorts/{video_id}",
            f"https://youtube.com/live/{video_id}",
            f"https://www.youtube.com/embed/{video_id}",
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(summarizer.extract_video_id(url), video_id)

    def test_rejects_lookalike_hosts_and_bad_ids(self):
        self.assertIsNone(summarizer.extract_video_id("https://evil.example/watch?v=dQw4w9WgXcQ"))
        self.assertIsNone(summarizer.extract_video_id("https://youtube.com/watch?v=short"))


class TranscriptTests(unittest.TestCase):
    @staticmethod
    def item(text):
        return SimpleNamespace(text=text)

    @patch("summarizer.YouTubeTranscriptApi")
    def test_uses_available_english_transcript(self, api_class):
        english = MagicMock(language_code="en", is_generated=False)
        english.fetch.return_value = [self.item("Useful English captions."), self.item("Second line.")]
        listing = MagicMock()
        listing.__iter__.return_value = iter([english])
        listing.find_transcript.return_value = english
        api_class.return_value.list.return_value = listing
        self.assertEqual(summarizer.get_transcript("dQw4w9WgXcQ"), "Useful English captions. Second line.")

    @patch("summarizer.YouTubeTranscriptApi")
    def test_translates_non_english_transcript_when_possible(self, api_class):
        source = MagicMock(language_code="es", is_generated=True, is_translatable=True)
        translated = MagicMock()
        translated.fetch.return_value = [self.item("Translated caption text.")]
        source.translate.return_value = translated
        listing = MagicMock()
        listing.__iter__.return_value = iter([source])
        listing.find_transcript.side_effect = summarizer.NoTranscriptFound("video", ["en"], listing)
        api_class.return_value.list.return_value = listing
        self.assertEqual(summarizer.get_transcript("dQw4w9WgXcQ"), "Translated caption text.")
        source.translate.assert_called_once_with("en")

    @patch("summarizer.YouTubeTranscriptApi")
    def test_uses_original_language_when_translation_is_unavailable(self, api_class):
        source = MagicMock(language_code="hi", is_generated=True, is_translatable=False)
        source.fetch.return_value = [self.item("सौर ऊर्जा स्वच्छ बिजली प्रदान करती है।")]
        listing = MagicMock()
        listing.__iter__.return_value = iter([source])
        listing.find_transcript.side_effect = summarizer.NoTranscriptFound("video", ["en"], listing)
        api_class.return_value.list.return_value = listing
        self.assertIn("सौर ऊर्जा", summarizer.get_transcript("dQw4w9WgXcQ"))


class ChunkTextTests(unittest.TestCase):
    def test_preserves_text_and_bounds_chunks(self):
        text = "First sentence. Second sentence is useful! Third one?"
        chunks = summarizer.chunk_text(text, chunk_size=100)
        self.assertEqual(" ".join(chunks), text)
        self.assertTrue(all(len(chunk) <= 100 for chunk in chunks))


class LocalSummarizerTests(unittest.TestCase):
    def setUp(self):
        self.transcript = (
            "Solar panels convert sunlight into electricity through photovoltaic cells. "
            "Modern solar installations can supply clean energy to homes and businesses. "
            "Battery storage keeps excess solar electricity for use after sunset. "
            "The cost of solar technology has fallen significantly during the last decade. "
            "Weather and roof orientation affect the amount of electricity a system produces. "
            "Homeowners should compare installation costs, warranties, and expected energy savings. "
            "Combining efficient panels with battery storage can reduce dependence on the power grid."
        )

    def test_selects_original_sentences_in_source_order(self):
        selected = summarizer.select_key_sentences(self.transcript, 3)
        self.assertEqual(len(selected), 3)
        positions = [self.transcript.index(sentence) for sentence in selected]
        self.assertEqual(positions, sorted(positions))

    def test_summary_uses_only_transcript_sentences(self):
        selected = summarizer.select_key_sentences(self.transcript, 4)
        summary = summarizer.generate_final_summary(selected)
        self.assertTrue(summary)
        self.assertTrue(all(sentence in self.transcript for sentence in selected))

    def test_removes_near_duplicate_sentences(self):
        text = (
            "Solar batteries store extra renewable electricity for later use. "
            "Solar batteries store additional renewable electricity for use later. "
            "Installation prices have decreased substantially over the past decade."
        )
        selected = summarizer.select_key_sentences(text, 3)
        self.assertLessEqual(len(selected), 2)

    def test_splits_long_unpunctuated_text(self):
        chunks = summarizer.chunk_text("word " * 100, chunk_size=100)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 100 for chunk in chunks))


class ProcessVideoTests(unittest.TestCase):
    @patch("summarizer.get_transcript", return_value=(
        "The course explains how Python functions organize reusable program logic. "
        "Parameters allow functions to receive values from other parts of a program. "
        "Return statements send calculated results back to the calling code. "
        "Small focused functions make software easier to test and maintain."
    ))
    def test_pipeline_response(self, _transcript):
        result = summarizer.process_video("https://youtu.be/dQw4w9WgXcQ")
        self.assertEqual(result["video_id"], "dQw4w9WgXcQ")
        self.assertEqual(result["summary_method"], "local-extractive")
        self.assertTrue(result["final_summary"])
        self.assertTrue(result["bullet_notes"])


if __name__ == "__main__":
    unittest.main()
