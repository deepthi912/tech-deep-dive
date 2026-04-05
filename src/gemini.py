"""Shared Gemini API helper with retry logic and model fallback.

Tries models in order of preference. If one model's quota is exhausted,
automatically falls back to the next. Retries on rate limit errors.
"""

import logging
import os
import time

import google.generativeai as genai

logger = logging.getLogger(__name__)

MODEL_PRIORITY = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
]

MAX_RETRIES = 3
RETRY_BASE_DELAY = 15


def _configure():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    genai.configure(api_key=api_key)


def generate_content(prompt: str, max_output_tokens: int = 16000, temperature: float = 0.5) -> str:
    """
    Generate content using Gemini with automatic retry and model fallback.
    Returns the response text.
    """
    _configure()

    gen_config = genai.GenerationConfig(
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )

    last_error = None

    for model_name in MODEL_PRIORITY:
        for attempt in range(MAX_RETRIES):
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt, generation_config=gen_config)
                logger.info(f"Gemini response OK (model={model_name}, attempt={attempt + 1})")
                return response.text.strip()

            except Exception as e:
                last_error = e
                error_str = str(e)

                if "429" in error_str or "quota" in error_str.lower():
                    if "retry_delay" in error_str or attempt < MAX_RETRIES - 1:
                        delay = RETRY_BASE_DELAY * (attempt + 1)
                        logger.warning(
                            f"Rate limited on {model_name} (attempt {attempt + 1}), "
                            f"waiting {delay}s..."
                        )
                        time.sleep(delay)
                        continue
                    else:
                        logger.warning(f"Quota exhausted on {model_name}, trying next model...")
                        break

                elif "not found" in error_str.lower() or "404" in error_str:
                    logger.warning(f"Model {model_name} not available, trying next...")
                    break

                else:
                    logger.error(f"Gemini error on {model_name}: {e}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(5)
                        continue
                    break

    raise RuntimeError(
        f"All Gemini models failed. Last error: {last_error}. "
        f"Your daily quota may be exhausted -- try again tomorrow, "
        f"or check https://ai.dev/rate-limit"
    )
