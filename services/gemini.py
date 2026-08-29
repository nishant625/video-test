
import os
import time
import requests

from services.logger import log


PROMPT_FILE = (
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "prompts",
        "content_prompt.txt",
    )
)


with open(
    PROMPT_FILE,
    "r",
    encoding="utf-8",
) as file:

    SYSTEM_PROMPT = file.read().strip()


def ask_gemini(
    prompt,
    system_prompt,
    step_name,
):

    api_key = os.getenv("GEMINI_API_KEY")

    model = os.getenv(
        "GEMINI_MODEL",
        "gemini-3-flash-preview",
    )

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing from .env"
        )

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{model}:generateContent"
    )

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    payload = {

        "system_instruction": {
            "parts": [
                {
                    "text": system_prompt
                }
            ]
        },

        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
    }

    start = time.perf_counter()

    log.info(
        "→ Gemini: %s",
        step_name,
    )

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=120,
    )

    elapsed = time.perf_counter() - start

    if not response.ok:

        log.error(
            "✗ Gemini HTTP %s after %.2fs",
            response.status_code,
            elapsed,
        )

        log.error(
            "Response: %s",
            response.text[:1000],
        )

        response.raise_for_status()

    data = response.json()

    try:

        text = (
            data["candidates"][0]
            ["content"]["parts"][0]
            ["text"]
            .strip()
        )

    except (
        KeyError,
        IndexError,
        TypeError,
    ):

        raise RuntimeError(
            f"Unexpected Gemini response: {data}"
        )

    if not text:
        raise RuntimeError(
            "Gemini returned empty text."
        )

    log.info(
        "✓ %s completed in %.2fs (%d chars)",
        step_name,
        elapsed,
        len(text),
    )

    return text


def generate_content(idea):

    video_prompt = ask_gemini(
        idea,
        SYSTEM_PROMPT,
        "Video prompt generation",
    )

    title_prompt = f"""
Based on this video prompt:

{video_prompt}

Generate a very short YouTube title under 20 characters.

After the title, compulsory add:

#viralshort #shorts #Viral #short #indianviralshort

Including all hashtags, keep the complete output under 99 characters.

Return ONLY the title and hashtags.
No explanation.
No Markdown.
No quotes.
One line only.
""".strip()

    youtube_title = ask_gemini(
        title_prompt,
        "You generate concise YouTube titles. Return only the requested title.",
        "YouTube title generation",
    )

    return video_prompt, youtube_title

