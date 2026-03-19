import re
import os
import time
import requests
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

# ─── HuggingFace Inference API ────────────────────────────────────────────────
HF_API_TOKEN = os.environ.get("HF_API_TOKEN", "")
HF_API_URL   = "https://api-inference.huggingface.co/models/google/flan-t5-base"
HEADERS      = {"Authorization": f"Bearer {HF_API_TOKEN}"} if HF_API_TOKEN else {}


def _hf_summarize(prompt: str, retries: int = 4) -> str:
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 150,
            "num_beams": 4,
            "length_penalty": 1.2,
            "early_stopping": True,
        },
        "options": {"wait_for_model": True},
    }

    for attempt in range(retries):
        try:
            resp = requests.post(HF_API_URL, headers=HEADERS, json=payload, timeout=60)
            if resp.status_code == 200:
                result = resp.json()
                if isinstance(result, list) and result:
                    return result[0].get("generated_text", "").strip()
                return str(result).strip()
            elif resp.status_code == 503:
                time.sleep(10 * (attempt + 1))
                continue
            else:
                raise ValueError(f"HuggingFace API error {resp.status_code}: {resp.text[:200]}")
        except requests.exceptions.Timeout:
            if attempt < retries - 1:
                time.sleep(5)
                continue
            raise ValueError("HuggingFace API timed out. Please try again.")

    raise ValueError("HuggingFace model is still loading. Please try again in a minute.")


def extract_video_id(url: str):
    match = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([a-zA-Z0-9_-]{11})", url)
    return match.group(1) if match else None


def get_transcript(video_id: str) -> str:
    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id)
        return " ".join([t.text for t in transcript])
    except TranscriptsDisabled:
        raise ValueError("Transcripts are disabled for this video.")
    except NoTranscriptFound:
        raise ValueError("No transcript found — the video may not have captions.")
    except Exception as e:
        raise ValueError(f"Could not fetch transcript: {str(e)}")


def chunk_text(text: str, chunk_size: int = 1000) -> list:
    sentences = text.split(". ")
    chunks, current = [], ""
    for sentence in sentences:
        if len(current) + len(sentence) < chunk_size:
            current += sentence + ". "
        else:
            if current.strip():
                chunks.append(current.strip())
            current = sentence + ". "
    if current.strip():
        chunks.append(current.strip())
    return chunks


def summarize_chunk(text_chunk: str) -> str:
    prompt = f"Summarize the following text clearly and concisely:\n{text_chunk}"
    return _hf_summarize(prompt)


def generate_final_summary(bullet_notes: list) -> str:
    combined = " ".join(bullet_notes)[:1200]
    prompt = f"Write a single cohesive paragraph summary of these notes:\n{combined}"
    return _hf_summarize(prompt)


def process_video(video_url: str) -> dict:
    video_id = extract_video_id(video_url)
    if not video_id:
        raise ValueError("Invalid YouTube URL. Please provide a valid link.")

    transcript = get_transcript(video_id)
    chunks = chunk_text(transcript)
    if not chunks:
        raise ValueError("Transcript was empty or too short to summarize.")

    chunks = chunks[:12]  # cap to stay within free API rate limits
    bullet_notes = [summarize_chunk(chunk) for chunk in chunks]
    final_summary = generate_final_summary(bullet_notes)

    return {
        "video_id":          video_id,
        "bullet_notes":      bullet_notes,
        "final_summary":     final_summary,
        "chunk_count":       len(chunks),
        "transcript_length": len(transcript),
    }
