import json
import os
import re
from pathlib import Path

import yaml


def get_project_root() -> Path:
    return Path(__file__).parent.parent


def load_config() -> dict:
    with open(get_project_root() / "config.yaml") as f:
        return yaml.safe_load(f)


def load_curriculum() -> list[dict]:
    with open(get_project_root() / "curriculum.yaml") as f:
        data = yaml.safe_load(f)
    return data.get("curriculum", [])


def get_data_dir() -> Path:
    d = get_project_root() / "data"
    d.mkdir(exist_ok=True)
    return d


def get_output_dir() -> Path:
    config = load_config()
    d = Path(config["podcast"]["output_dir"])
    if not d.is_absolute():
        d = get_project_root() / d
    d.mkdir(exist_ok=True)
    return d


def load_json(path: Path, default=None):
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return default if default is not None else {}


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "-").lower()


def truncate_text(text: str, max_chars: int = 30000) -> str:
    """Truncate text to fit within API limits while keeping coherent boundaries."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    last_period = cut.rfind(".")
    if last_period > max_chars * 0.8:
        return cut[: last_period + 1]
    return cut
