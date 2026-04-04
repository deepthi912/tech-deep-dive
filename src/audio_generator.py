"""Text-to-Speech audio generation using edge-tts (Microsoft Neural voices)."""

import asyncio
import logging
import tempfile
from pathlib import Path

import edge_tts

from .script_writer import PodcastSegment

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "en-US-GuyNeural"
DEFAULT_RATE = "+5%"
DEFAULT_VOLUME = "+0%"


async def _generate_segment_audio(
    segment: PodcastSegment,
    output_path: Path,
    voice: str,
    rate: str,
    volume: str,
) -> Path:
    """Generate audio for a single podcast segment."""
    communicate = edge_tts.Communicate(
        text=segment.text,
        voice=voice,
        rate=rate,
        volume=volume,
    )
    await communicate.save(str(output_path))
    logger.info(f"Audio generated: {segment.name} -> {output_path.name}")
    return output_path


async def generate_all_audio(
    segments: list[PodcastSegment],
    work_dir: Path,
    config: dict,
) -> list[Path]:
    """Generate audio files for all podcast segments."""
    tts_config = config.get("tts", {})
    voice = tts_config.get("voice", DEFAULT_VOICE)
    rate = tts_config.get("rate", DEFAULT_RATE)
    volume = tts_config.get("volume", DEFAULT_VOLUME)

    work_dir.mkdir(parents=True, exist_ok=True)
    audio_paths = []

    for i, segment in enumerate(segments):
        filename = f"{i:02d}_{segment.name.lower()}.mp3"
        output_path = work_dir / filename
        await _generate_segment_audio(segment, output_path, voice, rate, volume)
        audio_paths.append(output_path)

    logger.info(f"Generated {len(audio_paths)} audio segments in {work_dir}")
    return audio_paths


def generate_audio(
    segments: list[PodcastSegment],
    work_dir: Path,
    config: dict,
) -> list[Path]:
    """Synchronous wrapper for audio generation."""
    return asyncio.run(generate_all_audio(segments, work_dir, config))
