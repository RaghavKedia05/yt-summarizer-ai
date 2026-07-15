# NeuralClip

NeuralClip is a Flask website that turns a captioned YouTube video into concise segment notes and a cohesive AI-generated summary.

## Features

- Supports standard, shortened, Shorts, Live, and embed YouTube links
- Fetches English captions with `youtube-transcript-api`
- Splits long transcripts safely and summarizes them with Hugging Face Inference
- Responsive interface with loading, error, thumbnail, copy, and retry states
- Health endpoint, bounded requests, safe API errors, and configurable processing limits

## Local setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:HF_API_TOKEN = "your_hugging_face_token"
python app.py
```

Open `http://localhost:5000`. The token must have permission to call Hugging Face's inference service for the configured model.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `HF_API_TOKEN` | required | Hugging Face access token |
| `HF_MODEL` | `google/flan-t5-base` | Model name used to build the default endpoint |
| `HF_API_URL` | model inference URL | Override for a dedicated/custom inference endpoint |
| `MAX_TRANSCRIPT_CHARS` | `24000` | Maximum transcript text processed per request |
| `SUMMARY_CHUNK_SIZE` | `1800` | Approximate characters per transcript segment |
| `MAX_SUMMARY_CHUNKS` | `12` | Maximum AI calls for segment notes |
| `PORT` | `5000` | Local server port |

`GET /health` reports whether the web process is healthy and whether an AI token is configured. It never exposes the token.

## API

`POST /summarize` with JSON:

```json
{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
```

Successful responses include `video_id`, `bullet_notes`, `final_summary`, `chunk_count`, `transcript_length`, and `transcript_truncated`.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Tests mock YouTube and AI calls, so they do not require network access or credentials.

## Deployment

Use the included `Procfile` with a Python 3.11-compatible host and set `HF_API_TOKEN` as a secret environment variable. The production command is:

```text
gunicorn app:app --timeout 300 --workers 1
```

## Limitations

- A video must expose an English caption track.
- Private, restricted, or region-blocked videos may not provide transcripts.
- Only the configured transcript limit is processed; the response tells the UI when truncation occurred.
- Hugging Face availability, quotas, and model access affect summarization.
