import unittest
from unittest.mock import patch

from app import create_app


class AppTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def test_index_and_health(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn('id="summary-form"', page)
        self.assertIn("fetch('/summarize'", page)
        self.assertIn('id="results"', page)
        response.close()
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json()["summarizer"], "local-extractive")
        health.close()

    def test_rejects_bad_json(self):
        response = self.client.post("/summarize", json={})
        self.assertEqual(response.status_code, 400)

    @patch("app.process_video", return_value={"video_id": "dQw4w9WgXcQ"})
    def test_summarize(self, process_video):
        response = self.client.post(
            "/summarize", json={"url": "https://youtu.be/dQw4w9WgXcQ"}
        )
        self.assertEqual(response.status_code, 200)
        process_video.assert_called_once()


if __name__ == "__main__":
    unittest.main()
