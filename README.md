# Tech Deep Dive - Daily Podcast Agent

A self-running agent that generates a daily 1-hour podcast episode, each covering one open-source technology in depth. It discovers the best YouTube conference talks and tutorials, transcribes and summarizes them with AI, and produces a professional audio episode you can listen to on your phone.

## How It Works

1. **Picks today's topic** from a curated curriculum (Hadoop, Spark, Kafka, PostgreSQL, ClickHouse, etc.)
2. **Searches YouTube** for the best videos on that technology (conference talks, tutorials, deep dives - any date)
3. **Extracts transcripts** from the top videos
4. **Summarizes with AI** (Google Gemini) - extracting architecture details, use cases, and key insights
5. **Writes a podcast script** with segments: Intro → What & Why → Architecture → Use Cases → Comparisons → Outro
6. **Generates audio** using edge-tts (Microsoft Neural voices)
7. **Serves a web app** with a mobile-friendly podcast player (PWA - installable on your phone)

## Deploy Free (No Install on Your Computer)

You need two free API keys first (one-time, takes 2 minutes):

1. **YouTube Data API key**: [Google Cloud Console](https://console.cloud.google.com) → Create project → Enable "YouTube Data API v3" → Credentials → Create API Key
2. **Gemini API key**: [Google AI Studio](https://aistudio.google.com/apikey) → Create API Key

Then deploy to the cloud for free:

### Deploy to Render.com (Recommended)

1. Push this repo to GitHub (or fork it)
2. Go to [render.com](https://render.com) → Sign up free (no credit card)
3. Click **New** → **Web Service** → Connect your GitHub repo
4. Render auto-detects the Dockerfile. Set these:
   - **Name**: `tech-deep-dive`
   - **Plan**: Free
5. Add **Environment Variables**:
   - `YOUTUBE_API_KEY` = your key
   - `GEMINI_API_KEY` = your key
6. Click **Deploy**

You'll get a permanent URL like `https://tech-deep-dive.onrender.com`. Open it on your phone, tap Share → "Add to Home Screen" to install it as an app.

> Note: Render free tier sleeps after 15 min of inactivity. First visit after sleep takes ~30 seconds to wake up, then it's fast.

---

## Alternative: Run Locally

### 1. Prerequisites

- Python 3.11+
- ffmpeg: `brew install ffmpeg`

### 2. Install & Run

```bash
cd tech-podcast-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and paste your API keys

python run.py
```

Open the URL shown in the terminal on your phone (same WiFi). Tap Share → "Add to Home Screen" to install as an app.

## CLI Usage

```bash
# Show upcoming curriculum schedule
python -m src.main --schedule

# Generate episode for a specific technology
python -m src.main --topic "Apache Spark"

# Jump to day N of the curriculum
python -m src.main --day 5
```

## Curriculum

The agent covers 30+ technologies, one per day. Edit `curriculum.yaml` to customize:

| Day | Technology | Category |
|-----|-----------|----------|
| 1 | PostgreSQL | Databases |
| 2 | Apache Cassandra | Databases |
| 3 | MongoDB | Databases |
| 4 | Apache Hadoop | Big Data |
| 5 | Apache Spark | Big Data |
| 6 | Apache Flink | Stream Processing |
| 7 | Apache Kafka | Messaging |
| 8 | Elasticsearch | Search |
| 9 | OpenSearch | Search |
| 10 | ClickHouse | Analytics |
| 11 | DuckDB | Analytics |
| ... | ... | ... |

After completing all topics, the cycle repeats with fresh content.

## Episode Structure

Each ~60-minute episode follows this format:

- **Intro** (~3 min) - Welcome and topic introduction
- **What & Why** (~10 min) - Fundamentals, history, problem it solves
- **Architecture** (~20 min) - Deep dive into internals and design
- **Use Cases** (~15 min) - Real-world production deployments
- **Comparisons** (~7 min) - How it stacks up against alternatives
- **Outro** (~5 min) - Key takeaways and tomorrow's preview

## Configuration

Edit `config.yaml` to customize:

- TTS voice and speed
- Target podcast duration
- Web server port
- YouTube search parameters

Edit `curriculum.yaml` to:

- Add/remove/reorder technologies
- Customize search queries per technology

## Cost

**$0/month** - all services used are within free tier limits:

- YouTube Data API: 10,000 units/day (uses ~500)
- Gemini 1.5 Flash: 1,500 requests/day (uses ~15)
- edge-tts: unlimited, no API key needed
- Render.com hosting: free tier (no credit card)
- edge-tts: unlimited, no API key needed

## Project Structure

```
tech-podcast-agent/
├── run.py                 # Start the web app
├── config.yaml            # Settings
├── curriculum.yaml        # Technology learning schedule
├── requirements.txt       # Python dependencies
├── src/
│   ├── main.py            # Pipeline orchestrator
│   ├── web.py             # FastAPI web app
│   ├── curriculum.py      # Curriculum & progress tracking
│   ├── discovery.py       # YouTube content discovery
│   ├── transcriber.py     # Transcript extraction
│   ├── summarizer.py      # Gemini AI summarization
│   ├── script_writer.py   # Podcast script generation
│   ├── audio_generator.py # edge-tts audio generation
│   ├── podcast_assembler.py # Final MP3 assembly
│   └── utils.py           # Shared utilities
├── templates/
│   └── index.html         # Web app UI
├── static/                # CSS, JS, icons
├── output/                # Generated podcast MP3s
└── data/                  # Progress tracking
```
