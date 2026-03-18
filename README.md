# 🎬 NeuralClip — AI YouTube Video Summarizer

> Drop any YouTube link. Get AI-generated notes and a full summary instantly.

NeuralClip is a full-stack web application that fetches the transcript of any YouTube video and uses a local **Flan-T5** language model to produce structured key notes and a cohesive final summary — no external AI API keys required.

---

## ✨ Features

- 🔗 **Any YouTube URL format** — standard, short (`youtu.be`), Shorts, embedded
- 🧠 **Local AI inference** — runs `google/flan-t5-base` on your machine (CPU or GPU)
- 📝 **Structured output** — numbered key notes + a final narrative summary
- 🖼️ **Video thumbnail preview** — visual confirmation of the video being processed
- ⎘ **One-click copy** — copy the summary to clipboard instantly
- 🌑 **Cinematic dark UI** — responsive, animated, grain-textured interface
- 🚀 **Production-ready** — Gunicorn server, Procfile for Render/Railway/Heroku

---

## 🖥️ Screenshots

| Input | Results |
|-------|---------|
| Paste URL & click Analyze | AI notes + summary rendered below |

---

## 🚀 Quick Start (Local)

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/neuralclip.git
cd neuralclip
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** The first run will automatically download the `google/flan-t5-base` model (~300 MB). Subsequent runs use the cached version.

### 4. Run the app

```bash
python app.py
```

Open your browser at **http://localhost:5000**

---

## ☁️ Deploy to Render (Free Tier)

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → **New Web Service**
3. Connect your GitHub repo
4. Set:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --timeout 300 --workers 1`
   - **Environment:** Python 3.11
5. Click **Deploy**

> ⚠️ First request after deploy will be slow (~60s) while the model downloads and loads. Subsequent requests are faster.

---

## 📁 Project Structure

```
neuralclip/
├── app.py              # Flask web server & API routes
├── summarizer.py       # Core AI pipeline (transcript → summary)
├── requirements.txt    # Python dependencies
├── Procfile            # Gunicorn start command for deployment
├── runtime.txt         # Python version pin
├── .gitignore
├── README.md
└── templates/
    └── index.html      # Full frontend (HTML + CSS + JS)
```

---

## ⚙️ How It Works

```
YouTube URL
    │
    ▼
Extract Video ID (regex)
    │
    ▼
Fetch Transcript (youtube-transcript-api)
    │
    ▼
Split into ~1200-char Chunks
    │
    ▼
Flan-T5 summarizes each chunk → Bullet Notes
    │
    ▼
Flan-T5 combines notes → Final Summary
    │
    ▼
Render in UI
```

---

## 🤖 Model Details

| Property | Value |
|----------|-------|
| Model | `google/flan-t5-base` |
| Task | Seq2Seq text summarization |
| Size | ~250 MB |
| Inference | CPU (default) or CUDA GPU |
| Source | [Hugging Face](https://huggingface.co/google/flan-t5-base) |

---

## ⚠️ Limitations

- Videos **must have captions/subtitles** (auto-generated or manual)
- Private or age-restricted videos cannot be transcribed
- Very long videos (2h+) will take longer to process on CPU
- The free Render tier may time out for very long videos (increase `--timeout` in Procfile)

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 + Flask |
| AI Model | Google Flan-T5 Base (Transformers) |
| Transcripts | youtube-transcript-api |
| Server | Gunicorn |
| Frontend | Vanilla HTML/CSS/JS |
| Fonts | Bebas Neue, DM Sans, JetBrains Mono |

---

## 📄 License

MIT — free to use, modify, and deploy.

---

<p align="center">Built with ♥ using Flan-T5 and Flask</p>
