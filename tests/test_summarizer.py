import unittest
from unittest.mock import patch

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


class ChunkTextTests(unittest.TestCase):
    def test_preserves_text_and_bounds_chunks(self):
        text = "First sentence. Second sentence is useful! Third one?"
        chunks = summarizer.chunk_text(text, chunk_size=100)
        self.assertEqual(" ".join(chunks), text)
        self.assertTrue(all(len(chunk) <= 100 for chunk in chunks))

    def test_splits_long_unpunctuated_text(self):
        chunks = summarizer.chunk_text("word " * 100, chunk_size=100)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 100 for chunk in chunks))


class ProcessVideoTests(unittest.TestCase):
    @patch("summarizer.generate_final_summary", return_value="Final")
    @patch("summarizer.summarize_chunk", side_effect=lambda value: f"Note: {value[:5]}")
    @patch("summarizer.get_transcript", return_value="One sentence. Another sentence.")
    def test_pipeline_response(self, _transcript, _chunk, _final):
        result = summarizer.process_video("https://youtu.be/dQw4w9WgXcQ")
        self.assertEqual(result["video_id"], "dQw4w9WgXcQ")
        self.assertEqual(result["final_summary"], "Final")
        self.assertTrue(result["bullet_notes"])


if __name__ == "__main__":
    unittest.main()
