import re
import torch
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

# ─── Device Setup ────────────────────────────────────────────────────────────
device = "cuda" if torch.cuda.is_available() else "cpu"

# ─── Model (loaded once at startup) ──────────────────────────────────────────
MODEL_NAME = "google/flan-t5-base"
print(f"[INFO] Loading model '{MODEL_NAME}' on {device}...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME).to(device)
print("[INFO] Model ready.")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def extract_video_id(url: str) -> str | None:
    """Extracts the 11-character YouTube video ID from any common URL format."""
    match = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([a-zA-Z0-9_-]{11})", url)
    return match.group(1) if match else None


def get_transcript(video_id: str) -> str:
    """Fetches and joins the transcript for a given video ID."""
    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id)
        return " ".join([t.text for t in transcript])
    except TranscriptsDisabled:
        raise ValueError("Transcripts are disabled for this video.")
    except NoTranscriptFound:
        raise ValueError("No transcript found for this video (it may not have captions).")
    except Exception as e:
        raise ValueError(f"Could not fetch transcript: {str(e)}")


def chunk_text(text: str, chunk_size: int = 1200) -> list[str]:
    """Splits long text into digestible chunks for the model."""
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
    """Summarizes a single text chunk using flan-t5."""
    prompt = f"Summarize the following text clearly and concisely:\n{text_chunk}"
    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=1024
    ).to(device)
    summary_ids = model.generate(
        **inputs,
        max_new_tokens=150,
        num_beams=4,
        length_penalty=1.2,
        early_stopping=True
    )
    return tokenizer.decode(summary_ids[0], skip_special_tokens=True)


def generate_final_summary(bullet_notes: list[str]) -> str:
    """Combines all bullet-point notes into one cohesive final summary."""
    combined = " ".join(bullet_notes)
    if len(combined) > 1200:
        combined = combined[:1200]
    prompt = f"Write a single cohesive paragraph summary of these notes:\n{combined}"
    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=1024
    ).to(device)
    ids = model.generate(**inputs, max_new_tokens=200, num_beams=4, early_stopping=True)
    return tokenizer.decode(ids[0], skip_special_tokens=True)


# ─── Main Pipeline ────────────────────────────────────────────────────────────

def process_video(video_url: str) -> dict:
    """
    Full pipeline: URL → transcript → chunks → notes → summary.
    Returns a dict with keys: video_id, bullet_notes, final_summary, chunk_count.
    Raises ValueError on any recoverable error.
    """
    video_id = extract_video_id(video_url)
    if not video_id:
        raise ValueError("Invalid YouTube URL. Please provide a valid link.")

    transcript = get_transcript(video_id)

    chunks = chunk_text(transcript)
    if not chunks:
        raise ValueError("Transcript was empty or too short to summarize.")

    bullet_notes = []
    for chunk in chunks:
        note = summarize_chunk(chunk)
        bullet_notes.append(note)

    final_summary = generate_final_summary(bullet_notes)

    return {
        "video_id": video_id,
        "bullet_notes": bullet_notes,
        "final_summary": final_summary,
        "chunk_count": len(chunks),
        "transcript_length": len(transcript),
    }
