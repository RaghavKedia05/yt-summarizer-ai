# Recap — Local YouTube Summarizer

Recap is a Flask website that turns a captioned YouTube video into a concise overview and structured key points. Its summarizer runs locally with a frequency-and-position ranking algorithm—no AI account, API token, model download, or paid service is required.

## How the local summarizer works

1. Fetches the best available caption track, preferring English.
2. Translates non-English captions to English when YouTube supports it.
3. Removes caption markers and normalizes the transcript.
4. Splits the transcript into readable sentences, including Unicode scripts.
5. Removes common low-information words.
6. Scores sentences by important-word frequency, length, and position.
7. Filters near-duplicate sentences.
8. Restores selected sentences to their original order for readability.

This is an **extractive** summarizer: it selects the strongest original sentences instead of generating new claims. That keeps it fast, private, deterministic, and less prone to invented facts.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open [http://localhost:5000](http://localhost:5000). No environment variable is required.

## Configuration

| Variable | Default | Purpose |
|---|---:|---|
| `MAX_TRANSCRIPT_CHARS` | `50000` | Maximum caption text read per request |
| `SUMMARY_CHUNK_SIZE` | `1800` | Characters per processing chunk |
| `MAX_SUMMARY_CHUNKS` | `30` | Maximum chunks processed |
| `MAX_KEY_POINTS` | `8` | Maximum key points returned |
| `SUMMARY_SENTENCES` | `6` | Maximum overview sentences |
| `PORT` | `5000` | Flask server port |

## API

Send `POST /summarize` with JSON:

```json
{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
```

The response contains `video_id`, `bullet_notes`, `final_summary`, processing metadata, and `summary_method: "local-extractive"`.

`GET /health` returns the service status and summarizer method.

## Tests

```powershell
python -m unittest discover -s tests -v
```

The tests run without network access or credentials.

## Limitations

- The video must expose at least one manual or auto-generated caption track. A video with captions disabled has no transcript for the summarizer to read.
- Private, restricted, or region-blocked videos may not provide captions.
- Extractive summaries preserve original wording and will be less conversational than generative AI summaries.
- Caption quality directly affects summary quality.
