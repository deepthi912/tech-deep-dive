"""FastAPI web application with URL queue and podcast player."""

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .curriculum import get_schedule
from .main import generate_from_urls, get_all_episodes, get_episode_for_today
from .queue import add_urls, get_all_queue, remove_video
from .utils import get_output_dir, get_project_root, load_config

logger = logging.getLogger(__name__)

_generating = False
_generation_error: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
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


# --- URL Queue endpoints ---

@app.get("/api/queue")
async def api_get_queue():
    return {"videos": get_all_queue()}


@app.post("/api/queue/add")
async def api_add_to_queue(request: Request):
    body = await request.json()
    urls = body.get("urls", [])
    if isinstance(urls, str):
        urls = [u.strip() for u in urls.split("\n") if u.strip()]
    added = add_urls(urls)
    return {"added": len(added), "videos": get_all_queue()}


@app.delete("/api/queue/{video_id}")
async def api_remove_from_queue(video_id: str):
    remove_video(video_id)
    return {"status": "removed", "videos": get_all_queue()}


@app.post("/api/generate")
async def api_generate(request: Request):
    global _generating, _generation_error
    if _generating:
        return {"status": "already_generating"}

    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    title = body.get("title", "Tech Deep Dive Episode")
    urls = body.get("urls")

    def _run():
        global _generating, _generation_error
        _generating = True
        _generation_error = None
        try:
            generate_from_urls(video_urls=urls, episode_title=title)
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
