"""Text-to-Speech audio generation using edge-tts (Microsoft Neural voices)."""

import asyncio
import logging
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
    word_count = len(segment.text.split())
    logger.info(
        f"Generating audio: {segment.name} ({word_count} words, "
        f"~{word_count // 150} min)..."
    )
    try:
        communicate = edge_tts.Communicate(
            text=segment.text,
            voice=voice,
            rate=rate,
            volume=volume,
        )
        await communicate.save(str(output_path))

        size_kb = output_path.stat().st_size / 1024
        logger.info(f"Audio done: {segment.name} -> {output_path.name} ({size_kb:.0f} KB)")
        return output_path
    except Exception as e:
        logger.error(f"Audio generation FAILED for {segment.name}: {e}")
        raise


async def generate_all_audio(
    segments: list[PodcastSegment],
    work_dir: Path,
    config: dict,
) -> list[Path]:
    tts_config = config.get("tts", {})
    voice = tts_config.get("voice", DEFAULT_VOICE)
    rate = tts_config.get("rate", DEFAULT_RATE)
    volume = tts_config.get("volume", DEFAULT_VOLUME)

    work_dir.mkdir(parents=True, exist_ok=True)
    audio_paths = []

    total_words = sum(len(s.text.split()) for s in segments)
    logger.info(f"Starting TTS for {len(segments)} segments ({total_words} words total)")

    for i, segment in enumerate(segments):
        filename = f"{i:02d}_{segment.name.lower()}.mp3"
        output_path = work_dir / filename
        await _generate_segment_audio(segment, output_path, voice, rate, volume)
        audio_paths.append(output_path)

    logger.info(f"All {len(audio_paths)} audio segments generated")
    return audio_paths


def generate_audio(
    segments: list[PodcastSegment],
    work_dir: Path,
    config: dict,
) -> list[Path]:
    return asyncio.run(generate_all_audio(segments, work_dir, config))
