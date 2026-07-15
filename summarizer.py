import os
import re
import time
from urllib.parse import parse_qs, urlparse

import requests
from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled, YouTubeTranscriptApi


HF_API_TOKEN = os.getenv("HF_API_TOKEN", "").strip()
HF_MODEL = os.getenv("HF_MODEL", "google/flan-t5-base").strip()
HF_API_URL = os.getenv(
    "HF_API_URL", f"https://api-inference.huggingface.co/models/{HF_MODEL}"
).strip()
MAX_TRANSCRIPT_CHARS = int(os.getenv("MAX_TRANSCRIPT_CHARS", "24000"))
CHUNK_SIZE = int(os.getenv("SUMMARY_CHUNK_SIZE", "1800"))
MAX_CHUNKS = int(os.getenv("MAX_SUMMARY_CHUNKS", "12"))

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}


def _hf_summarize(prompt: str, retries: int = 3) -> str:
    if not HF_API_TOKEN:
        raise ValueError("AI summarization is not configured. Set the HF_API_TOKEN environment variable.")

    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 180, "num_beams": 4, "do_sample": False},
        "options": {"wait_for_model": True},
    }
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}

    for attempt in range(retries):
        try:
            response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=(10, 90))
        except requests.Timeout as exc:
            if attempt == retries - 1:
                raise ValueError("The AI service timed out. Please try again.") from exc
            time.sleep(2 ** attempt)
            continue
        except requests.RequestException as exc:
            raise ValueError("Could not reach the AI summarization service.") from exc

        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and result and isinstance(result[0], dict):
                summary = result[0].get("generated_text", "").strip()
                if summary:
                    return summary
            raise ValueError("The AI service returned an empty summary.")

        if response.status_code in {429, 503} and attempt < retries - 1:
            time.sleep(2 ** (attempt + 1))
            continue
        if response.status_code in {401, 403}:
            raise ValueError("The AI service credentials are invalid or lack permission.")
        raise ValueError(f"The AI service returned an error ({response.status_code}).")

    raise ValueError("The AI service is temporarily unavailable. Please try again.")


def extract_video_id(value: str) -> str | None:
    value = value.strip()
    if VIDEO_ID_RE.fullmatch(value):
        return value

    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.hostname or "").lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    candidate = None
    if host in YOUTUBE_HOSTS:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [None])[0]
        elif len(path_parts) >= 2 and path_parts[0] in {"embed", "shorts", "live"}:
            candidate = path_parts[1]
    elif host in {"youtu.be", "www.youtu.be"} and path_parts:
        candidate = path_parts[0]

    return candidate if candidate and VIDEO_ID_RE.fullmatch(candidate) else None


def get_transcript(video_id: str) -> str:
    try:
        transcript = YouTubeTranscriptApi().fetch(video_id, languages=["en"])
        text = " ".join(item.text.strip() for item in transcript if item.text.strip())
        return re.sub(r"\s+", " ", text).strip()
    except TranscriptsDisabled as exc:
        raise ValueError("Transcripts are disabled for this video.") from exc
    except NoTranscriptFound as exc:
        raise ValueError("No English transcript was found for this video.") from exc
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("YouTube did not provide a transcript for this video.") from exc


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    if chunk_size < 100:
        raise ValueError("Chunk size must be at least 100 characters.")
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        while len(sentence) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            split_at = sentence.rfind(" ", 0, chunk_size + 1)
            split_at = split_at if split_at > 0 else chunk_size
            chunks.append(sentence[:split_at].strip())
            sentence = sentence[split_at:].strip()

        proposed = f"{current} {sentence}".strip()
        if current and len(proposed) > chunk_size:
            chunks.append(current)
            current = sentence
        else:
            current = proposed

    if current:
        chunks.append(current)
    return chunks


def summarize_chunk(text_chunk: str) -> str:
    return _hf_summarize(
        "Summarize this YouTube transcript segment in 1-2 factual sentences. "
        f"Keep important names, claims, and conclusions:\n\n{text_chunk}"
    )


def generate_final_summary(notes: list[str]) -> str:
    combined = "\n".join(f"- {note}" for note in notes)
    return _hf_summarize(
        "Create a clear, cohesive summary from these notes. Avoid repetition and do not add facts.\n\n"
        f"{combined[:6000]}"
    )


def process_video(video_url: str) -> dict:
    video_id = extract_video_id(video_url)
    if not video_id:
        raise ValueError("Enter a valid YouTube video URL.")

    transcript = get_transcript(video_id)
    if not transcript:
        raise ValueError("The transcript is empty.")

    original_length = len(transcript)
    transcript = transcript[:MAX_TRANSCRIPT_CHARS]
    chunks = chunk_text(transcript)[:MAX_CHUNKS]
    notes = [summarize_chunk(chunk) for chunk in chunks]
    return {
        "video_id": video_id,
        "bullet_notes": notes,
        "final_summary": generate_final_summary(notes),
        "chunk_count": len(chunks),
        "transcript_length": len(transcript),
        "transcript_truncated": original_length > MAX_TRANSCRIPT_CHARS,
    }
