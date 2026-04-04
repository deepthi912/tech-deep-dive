"""Entry point: start the Tech Deep Dive web app."""
import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def print_banner(port: int):
    is_cloud = os.environ.get("RENDER") or os.environ.get("IS_CLOUD")
    if is_cloud:
        print(f"\n  Tech Deep Dive starting on port {port} (cloud mode)\n")
        return

    local_ip = get_local_ip()
    print()
    print("=" * 56)
    print("  Tech Deep Dive - Podcast Agent")
    print("=" * 56)
    print()
    print("  Open on your phone (same WiFi):")
    print(f"    http://{local_ip}:{port}")
    print()
    print("  Install on iPhone/Android:")
    print("    1. Open the URL above in Safari or Chrome")
    print("    2. Tap Share > 'Add to Home Screen'")
    print()
    print("-" * 56)
    print()


if __name__ == "__main__":
    from src.utils import load_config
    config = load_config()

    # Render.com sets PORT env var; fall back to config
    port = int(os.environ.get("PORT", config.get("web", {}).get("port", 8555)))

    print_banner(port)

    from src.web import run_server
    run_server(port_override=port)
