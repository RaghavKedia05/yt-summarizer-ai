import math
import os
import re
from collections import Counter
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled, YouTubeTranscriptApi


MAX_TRANSCRIPT_CHARS = int(os.getenv("MAX_TRANSCRIPT_CHARS", "50000"))
CHUNK_SIZE = int(os.getenv("SUMMARY_CHUNK_SIZE", "1800"))
MAX_CHUNKS = int(os.getenv("MAX_SUMMARY_CHUNKS", "30"))
MAX_KEY_POINTS = int(os.getenv("MAX_KEY_POINTS", "8"))
SUMMARY_SENTENCES = int(os.getenv("SUMMARY_SENTENCES", "6"))

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
WORD_RE = re.compile(r"[^\W\d_](?:[^\W\d_]|['’-])*", re.UNICODE)
SENTENCE_RE = re.compile(r"(?<=[.!?।])\s+|\n+")

# Common words carry little meaning when ranking transcript sentences.
STOP_WORDS = {
    "a", "about", "after", "again", "all", "also", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "between", "both", "but",
    "by", "can", "could", "did", "do", "does", "doing", "down", "each", "even", "few",
    "for", "from", "further", "get", "going", "got", "had", "has", "have", "having", "he",
    "her", "here", "hers", "herself", "him", "himself", "his", "how", "i", "if", "in",
    "into", "is", "it", "its", "itself", "just", "know", "like", "me", "more", "most",
    "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once", "only", "or",
    "other", "our", "ours", "ourselves", "out", "over", "own", "really", "right", "said",
    "same", "she", "should", "so", "some", "such", "than", "that", "the", "their", "theirs",
    "them", "themselves", "then", "there", "these", "they", "think", "this", "those", "through",
    "to", "too", "under", "until", "up", "very", "was", "we", "well", "were", "what", "when",
    "where", "which", "while", "who", "whom", "why", "will", "with", "would", "you", "your",
    "yours", "yourself", "yourselves"
}


def extract_video_id(value: str) -> str | None:
    value = value.strip()
    if VIDEO_ID_RE.fullmatch(value):
        return value
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.hostname or "").lower()
    parts = [part for part in parsed.path.split("/") if part]
    candidate = None
    if host in YOUTUBE_HOSTS:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [None])[0]
        elif len(parts) >= 2 and parts[0] in {"embed", "shorts", "live"}:
            candidate = parts[1]
    elif host in {"youtu.be", "www.youtu.be"} and parts:
        candidate = parts[0]
    return candidate if candidate and VIDEO_ID_RE.fullmatch(candidate) else None


def get_transcript(video_id: str) -> str:
    try:
        transcripts = YouTubeTranscriptApi().list(video_id)
        available = list(transcripts)
        if not available:
            raise ValueError("This video does not provide captions in any language.")

        try:
            selected = transcripts.find_transcript(["en", "en-US", "en-GB", "en-IN"])
        except NoTranscriptFound:
            # Prefer a human-created track, then fall back to auto-generated captions.
            selected = next((item for item in available if not item.is_generated), available[0])
            if selected.is_translatable and selected.language_code != "en":
                try:
                    selected = selected.translate("en")
                except Exception:
                    # Translation is optional; the local ranker supports Unicode text.
                    pass

        transcript = selected.fetch()
        text = " ".join(item.text.strip() for item in transcript if item.text.strip())
        return re.sub(r"\s+", " ", text).strip()
    except TranscriptsDisabled as exc:
        raise ValueError("Transcripts are disabled for this video.") from exc
    except NoTranscriptFound as exc:
        raise ValueError("This video does not provide usable captions.") from exc
    except Exception as exc:
        raise ValueError("YouTube did not provide a transcript for this video.") from exc


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    if chunk_size < 100:
        raise ValueError("Chunk size must be at least 100 characters.")
    sentences = SENTENCE_RE.split(text.strip())
    chunks, current = [], ""
    for sentence in sentences:
        sentence = sentence.strip()
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


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\[(?:music|applause|laughter)\]", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    raw = SENTENCE_RE.split(text)
    sentences = []
    for sentence in raw:
        sentence = sentence.strip(" -")
        if len(sentence) >= 25 and len(WORD_RE.findall(sentence)) >= 5:
            sentences.append(sentence)
    return sentences


def _tokens(text: str) -> list[str]:
    return [word.lower().strip("'-") for word in WORD_RE.findall(text) if word.lower() not in STOP_WORDS]


def _similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def rank_sentences(text: str) -> list[tuple[int, str, float]]:
    sentences = split_sentences(text)
    if not sentences:
        return []
    token_sets = [set(_tokens(sentence)) for sentence in sentences]
    frequencies = Counter(token for sentence in sentences for token in _tokens(sentence))
    if not frequencies:
        return [(index, sentence, 1.0) for index, sentence in enumerate(sentences)]

    maximum = max(frequencies.values())
    weights = {word: 0.5 + 0.5 * (count / maximum) for word, count in frequencies.items()}
    ranked = []
    for index, (sentence, tokens) in enumerate(zip(sentences, token_sets)):
        words = _tokens(sentence)
        if not words:
            continue
        keyword_score = sum(weights[word] for word in words) / math.sqrt(len(words))
        # Openings often establish the subject; conclusions commonly appear near the end.
        position = index / max(1, len(sentences) - 1)
        position_bonus = 1.12 if index == 0 else 1.06 if position > 0.88 else 1.0
        length_bonus = 1.08 if 9 <= len(words) <= 32 else 0.92
        ranked.append((index, sentence, keyword_score * position_bonus * length_bonus))
    return sorted(ranked, key=lambda item: item[2], reverse=True)


def select_key_sentences(text: str, limit: int) -> list[str]:
    ranked = rank_sentences(text)
    if not ranked:
        cleaned = re.sub(r"\s+", " ", text).strip()
        return [cleaned] if cleaned else []

    selected: list[tuple[int, str, set[str]]] = []
    for index, sentence, _score in ranked:
        tokens = set(_tokens(sentence))
        if any(_similarity(tokens, existing) > 0.58 for _, _, existing in selected):
            continue
        selected.append((index, sentence, tokens))
        if len(selected) >= max(1, limit):
            break
    return [sentence for _, sentence, _ in sorted(selected, key=lambda item: item[0])]


def summarize_chunk(text_chunk: str) -> str:
    sentences = select_key_sentences(text_chunk, 1)
    return sentences[0] if sentences else text_chunk.strip()


def generate_final_summary(notes: list[str]) -> str:
    return " ".join(note.strip() for note in notes if note.strip())


def process_video(video_url: str) -> dict:
    video_id = extract_video_id(video_url)
    if not video_id:
        raise ValueError("Enter a valid YouTube video URL.")
    transcript = get_transcript(video_id)
    if not transcript:
        raise ValueError("The transcript is empty.")

    original_length = len(transcript)
    transcript = transcript[:MAX_TRANSCRIPT_CHARS]
    all_chunks = chunk_text(transcript)
    chunks = all_chunks[:MAX_CHUNKS]
    processed_text = " ".join(chunks)
    sentence_count = len(split_sentences(processed_text))
    summary_limit = min(SUMMARY_SENTENCES, max(2, round(sentence_count * 0.18)))
    notes_limit = min(MAX_KEY_POINTS, max(3, round(sentence_count * 0.25)))
    summary_sentences = select_key_sentences(processed_text, summary_limit)
    notes = select_key_sentences(processed_text, notes_limit)
    if not summary_sentences:
        raise ValueError("The transcript did not contain enough readable text to summarize.")

    return {
        "video_id": video_id,
        "bullet_notes": notes,
        "final_summary": generate_final_summary(summary_sentences),
        "chunk_count": len(chunks),
        "transcript_length": len(processed_text),
        "transcript_truncated": original_length > MAX_TRANSCRIPT_CHARS or len(all_chunks) > MAX_CHUNKS,
        "summary_method": "local-extractive",
    }
