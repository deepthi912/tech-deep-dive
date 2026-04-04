"""FastAPI web application: serves a mobile-friendly podcast player with PWA support."""

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .curriculum import get_schedule
from .main import generate_episode, get_all_episodes, get_episode_for_today
from .utils import get_output_dir, get_project_root, load_config

logger = logging.getLogger(__name__)

_generating = False
_generation_error: str | None = None


def _auto_generate():
    """Background thread: generate today's episode if it doesn't exist."""
    global _generating, _generation_error
    _generating = True
    _generation_error = None
    try:
        existing = get_episode_for_today()
        if existing:
            logger.info(f"Today's episode already exists: {existing['filename']}")
            return

        logger.info("Auto-generating today's episode...")
        generate_episode()
        logger.info("Auto-generation complete!")
    except Exception as e:
        _generation_error = str(e)
        logger.error(f"Auto-generation failed: {e}")
    finally:
        _generating = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    thread = threading.Thread(target=_auto_generate, daemon=True)
    thread.start()
    yield


app = FastAPI(title="Tech Deep Dive", lifespan=lifespan)

static_dir = get_project_root() / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = get_project_root() / "templates" / "index.html"
    return HTMLResponse(content=html_path.read_text())


@app.get("/api/episodes")
async def api_episodes():
    episodes = get_all_episodes()
    episodes.reverse()
    return {
        "episodes": episodes,
        "generating": _generating,
        "generation_error": _generation_error,
    }


@app.get("/api/schedule")
async def api_schedule():
    return {"schedule": get_schedule(count=20)}


@app.get("/api/status")
async def api_status():
    return {
        "generating": _generating,
        "generation_error": _generation_error,
        "todays_episode": get_episode_for_today(),
    }


@app.post("/api/generate")
async def api_generate(topic: str | None = None, day: int | None = None):
    global _generating, _generation_error
    if _generating:
        return {"status": "already_generating"}

    def _run():
        global _generating, _generation_error
        _generating = True
        _generation_error = None
        try:
            generate_episode(override_topic=topic, override_day=day)
        except Exception as e:
            _generation_error = str(e)
            logger.error(f"Generation failed: {e}")
        finally:
            _generating = False

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "started"}


@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    audio_path = get_output_dir() / filename
    if not audio_path.exists():
        return {"error": "Episode not found"}, 404
    return FileResponse(
        str(audio_path),
        media_type="audio/mpeg",
        headers={"Accept-Ranges": "bytes"},
    )


@app.get("/manifest.json")
async def manifest():
    return {
        "name": "Tech Deep Dive",
        "short_name": "TechPod",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0f172a",
        "theme_color": "#3b82f6",
        "description": "Daily deep-dive podcast on open source technologies",
        "icons": [
            {"src": "/static/icons/icon-192.svg", "sizes": "any", "type": "image/svg+xml"},
        ],
    }


@app.get("/sw.js")
async def service_worker():
    sw_path = get_project_root() / "static" / "js" / "sw.js"
    return FileResponse(str(sw_path), media_type="application/javascript")


def run_server(port_override: int | None = None):
    import uvicorn
    config = load_config()
    web_config = config.get("web", {})
    host = web_config.get("host", "0.0.0.0")
    port = port_override or web_config.get("port", 8555)
    uvicorn.run(app, host=host, port=port, log_level="warning")
