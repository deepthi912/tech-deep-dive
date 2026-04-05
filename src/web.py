"""FastAPI web application with URL queue, summaries, and podcast player."""

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import unquote

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from .main import generate_from_urls, get_all_episodes
from .queue import add_urls, get_all_queue, remove_url
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


@app.get("/api/status")
async def api_status():
    return {
        "generating": _generating,
        "generation_error": _generation_error,
    }


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


@app.delete("/api/queue/{url:path}")
async def api_remove_from_queue(url: str):
    remove_url(unquote(url))
    return {"status": "removed", "videos": get_all_queue()}


@app.post("/api/generate")
async def api_generate(request: Request):
    global _generating, _generation_error
    if _generating:
        return {"status": "already_generating"}

    body = {}
    if request.headers.get("content-type", "").startswith("application/json"):
        body = await request.json()
    title = body.get("title", "Tech Deep Dive Episode")
    urls = body.get("urls")

    def _run():
        global _generating, _generation_error
        _generating = True
        _generation_error = None
        try:
            generate_from_urls(urls=urls, episode_title=title)
        except Exception as e:
            _generation_error = str(e)
            logger.error(f"Generation failed: {e}", exc_info=True)
        finally:
            _generating = False

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "started"}


@app.get("/audio/{filename}")
async def serve_audio(filename: str, request: Request):
    audio_path = get_output_dir() / filename
    if not audio_path.exists():
        return Response(content='{"error":"not found"}', status_code=404,
                        media_type="application/json")

    file_size = audio_path.stat().st_size
    range_header = request.headers.get("range")

    if range_header:
        range_spec = range_header.replace("bytes=", "")
        parts = range_spec.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else file_size - 1
        end = min(end, file_size - 1)
        length = end - start + 1

        with open(audio_path, "rb") as f:
            f.seek(start)
            data = f.read(length)

        return Response(
            content=data,
            status_code=206,
            media_type="audio/mpeg",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
                "Cache-Control": "public, max-age=86400",
            },
        )

    return FileResponse(
        str(audio_path),
        media_type="audio/mpeg",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Cache-Control": "public, max-age=86400",
        },
    )


@app.get("/download/{filename}")
async def download_audio(filename: str):
    audio_path = get_output_dir() / filename
    if not audio_path.exists():
        return Response(content='{"error":"not found"}', status_code=404,
                        media_type="application/json")
    return FileResponse(
        str(audio_path),
        media_type="audio/mpeg",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
        "description": "AI podcast from blogs and docs",
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
