"""Podcast assembler: combines audio segments into a final MP3 with transitions."""

import logging
from datetime import date
from pathlib import Path

from mutagen.id3 import TALB, TIT2, TPE1, ID3
from mutagen.mp3 import MP3
from pydub import AudioSegment
from pydub.effects import normalize

from .utils import get_output_dir, sanitize_filename

logger = logging.getLogger(__name__)

TRANSITION_SILENCE_MS = 1200
FADE_MS = 300


def _create_transition(duration_ms: int = TRANSITION_SILENCE_MS) -> AudioSegment:
    """Create a brief silence for transitions between segments."""
    return AudioSegment.silent(duration=duration_ms)


def assemble_podcast(
    audio_paths: list[Path],
    technology: str,
    day_number: int,
    config: dict,
) -> Path:
    """
    Combine individual segment audio files into a single podcast MP3.
    Adds transitions between segments and normalizes audio levels.
    """
    if not audio_paths:
        raise ValueError("No audio segments to assemble")

    logger.info(f"Assembling {len(audio_paths)} segments into final podcast...")

    combined = AudioSegment.empty()
    transition = _create_transition()

    for i, path in enumerate(audio_paths):
        segment = AudioSegment.from_mp3(str(path))

        segment = segment.fade_in(FADE_MS)
        segment = segment.fade_out(FADE_MS)

        combined += segment
        if i < len(audio_paths) - 1:
            combined += transition

    combined = normalize(combined)

    output_dir = get_output_dir()
    safe_name = sanitize_filename(technology)
    today = date.today().isoformat()
    output_filename = f"day-{day_number:03d}-{safe_name}-{today}.mp3"
    output_path = output_dir / output_filename

    combined.export(
        str(output_path),
        format="mp3",
        bitrate="128k",
        parameters=["-ac", "1"],  # mono for speech
    )

    _add_id3_tags(output_path, technology, day_number, config)

    duration_min = len(combined) / 1000 / 60
    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(
        f"Podcast assembled: {output_path.name} "
        f"({duration_min:.1f} min, {size_mb:.1f} MB)"
    )
    return output_path


def _add_id3_tags(path: Path, technology: str, day_number: int, config: dict):
    """Add ID3 metadata tags to the MP3 file."""
    try:
        audio = MP3(str(path))
        if audio.tags is None:
            audio.add_tags()
        tags = audio.tags

        show_name = config.get("podcast", {}).get("show_name", "Tech Deep Dive")
        tags.add(TIT2(encoding=3, text=f"Day {day_number}: {technology}"))
        tags.add(TPE1(encoding=3, text=show_name))
        tags.add(TALB(encoding=3, text=show_name))
        audio.save()
    except Exception as e:
        logger.warning(f"Could not add ID3 tags: {e}")
