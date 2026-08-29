import os
import sys
import time
import logging
import requests
from dotenv import load_dotenv

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
PROMPT_FILE = os.getenv("PROMPT_FILE", "video_prompt.txt")

KIE_API_KEY = os.getenv("KIE_API_KEY")
KIE_MODEL = os.getenv("KIE_MODEL", "grok-imagine/text-to-video")

KIE_INITIAL_WAIT = int(os.getenv("KIE_INITIAL_WAIT", "90"))
KIE_POLL_INTERVAL = int(os.getenv("KIE_POLL_INTERVAL", "10"))
KIE_MAX_WAIT = int(os.getenv("KIE_MAX_WAIT", "600"))

if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY is missing from .env")
    sys.exit(1)

if not KIE_API_KEY:
    print("ERROR: KIE_API_KEY is missing from .env")
    sys.exit(1)

if not os.path.isfile(PROMPT_FILE):
    print(f"ERROR: Prompt file not found: {PROMPT_FILE}")
    sys.exit(1)

with open(PROMPT_FILE, "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read().strip()

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/"
    f"v1beta/models/{GEMINI_MODEL}:generateContent"
)

KIE_CREATE_URL = "https://api.kie.ai/api/v1/jobs/createTask"
KIE_RECORD_URL = "https://api.kie.ai/api/v1/jobs/recordInfo"

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

log = logging.getLogger("content-engine")

# ─────────────────────────────────────────────
# GEMINI
# ─────────────────────────────────────────────

def ask_gemini(prompt, step_name):
    start = time.perf_counter()

    log.info("→ Gemini: %s", step_name)

    payload = {
        "system_instruction": {
            "parts": [
                {
                    "text": SYSTEM_PROMPT
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
        ]
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
    }

    try:
        response = requests.post(
            GEMINI_URL,
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
            log.error("Response: %s", response.text[:2000])
            response.raise_for_status()

        data = response.json()

        try:
            text = (
                data["candidates"][0]
                ["content"]["parts"][0]["text"]
                .strip()
            )
        except (KeyError, IndexError, TypeError):
            log.error("Unexpected Gemini response:")
            log.error("%s", data)
            raise RuntimeError(
                "Could not extract Gemini response text."
            )

        if not text:
            raise RuntimeError("Gemini returned empty text.")

        log.info(
            "✓ %s completed in %.2fs (%d chars)",
            step_name,
            elapsed,
            len(text),
        )

        return text

    except requests.RequestException as e:
        log.error("✗ Network/API error during %s", step_name)
        log.error("%s", e)
        raise

# ─────────────────────────────────────────────
# KIE — CREATE TASK
# ─────────────────────────────────────────────

def create_kie_task(video_prompt):
    start = time.perf_counter()

    log.info("→ Kie AI: Creating video generation task")

    payload = {
        "model": KIE_MODEL,
        "callBackUrl": "https://your-domain.com/api/callback",
        "input": {
            "prompt": video_prompt,
            "aspect_ratio": "2:3",
            "mode": "normal",
            "duration": "6",
            "resolution": "480p",
        },
    }

    headers = {
        "Authorization": f"Bearer {KIE_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            KIE_CREATE_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )

        elapsed = time.perf_counter() - start

        if not response.ok:
            log.error(
                "✗ Kie HTTP %s after %.2fs",
                response.status_code,
                elapsed,
            )
            log.error("Response: %s", response.text[:2000])
            response.raise_for_status()

        data = response.json()

        task_id = data.get("data", {}).get("taskId")

        if not task_id:
            log.error("Unexpected Kie response:")
            log.error("%s", data)
            raise RuntimeError("Kie did not return a taskId.")

        log.info(
            "✓ Kie task created in %.2fs",
            elapsed,
        )
        log.info("Task ID: %s", task_id)

        return task_id

    except requests.RequestException as e:
        log.error("✗ Kie task creation failed")
        log.error("%s", e)
        raise

# ─────────────────────────────────────────────
# KIE — CHECK TASK
# ─────────────────────────────────────────────

def check_kie_task(task_id):

    headers = {
        "Authorization": f"Bearer {KIE_API_KEY}",
    }

    response = requests.get(
        KIE_RECORD_URL,
        headers=headers,
        params={
            "taskId": task_id
        },
        timeout=60,
    )

    if not response.ok:
        log.error(
            "✗ Kie recordInfo HTTP %s",
            response.status_code,
        )
        log.error("Response: %s", response.text[:2000])
        response.raise_for_status()

    data = response.json()

    task_data = data.get("data", {})

    state = task_data.get("state", "unknown")

    log.info("Kie task state: %s", state)

    if state == "success":

        result_json = task_data.get("resultJson")

        if not result_json:
            raise RuntimeError(
                "Kie reported success but resultJson is missing."
            )

        try:
            result = (
                result_json
                if isinstance(result_json, dict)
                else __import__("json").loads(result_json)
            )
        except Exception:
            raise RuntimeError(
                "Could not parse Kie resultJson."
            )

        urls = result.get("resultUrls", [])

        if not urls:
            raise RuntimeError(
                "Kie reported success but no video URL was returned."
            )

        return {
            "state": "success",
            "video_url": urls[0],
            "raw": data,
        }

    if state in {
        "failed",
        "error",
        "cancelled",
        "canceled",
    }:
        return {
            "state": state,
            "video_url": None,
            "raw": data,
        }

    return {
        "state": state,
        "video_url": None,
        "raw": data,
    }

# ─────────────────────────────────────────────
# KIE — WAIT + POLL
# ─────────────────────────────────────────────

def wait_for_kie_video(task_id):

    log.info(
        "Waiting %d seconds before first Kie status check...",
        KIE_INITIAL_WAIT,
    )

    time.sleep(KIE_INITIAL_WAIT)

    total_wait = KIE_INITIAL_WAIT

    while total_wait <= KIE_MAX_WAIT:

        log.info(
            "→ Checking Kie task %s",
            task_id,
        )

        try:
            result = check_kie_task(task_id)

        except Exception as e:
            log.error(
                "✗ Status check failed: %s",
                e,
            )

            total_wait += KIE_POLL_INTERVAL

            if total_wait > KIE_MAX_WAIT:
                break

            log.info(
                "Retrying in %d seconds...",
                KIE_POLL_INTERVAL,
            )

            time.sleep(KIE_POLL_INTERVAL)
            continue

        state = result["state"]

        if state == "success":

            log.info("✓ Kie video generation SUCCESS")

            return result["video_url"]

        if state in {
            "failed",
            "error",
            "cancelled",
            "canceled",
        }:

            log.error(
                "✗ Kie video generation FAILED. State: %s",
                state,
            )

            log.error(
                "Kie response: %s",
                result["raw"],
            )

            raise RuntimeError(
                f"Kie video generation failed: {state}"
            )

        total_wait += KIE_POLL_INTERVAL

        if total_wait > KIE_MAX_WAIT:
            break

        log.info(
            "Still processing. Next check in %d seconds...",
            KIE_POLL_INTERVAL,
        )

        time.sleep(KIE_POLL_INTERVAL)

    raise TimeoutError(
        f"Kie task did not finish within "
        f"{KIE_MAX_WAIT} seconds."
    )

# ─────────────────────────────────────────────
# CONTENT PIPELINE
# ─────────────────────────────────────────────

def generate_content(video_idea):

    if not video_idea.strip():
        raise ValueError("Video idea cannot be empty.")

    log.info("════════════════════════════════════")
    log.info("STARTING CONTENT ENGINE")
    log.info("════════════════════════════════════")

    log.info("Input idea: %s", video_idea)

    # ─────────────────────────────────────────
    # STEP 1 — VIDEO PROMPT
    # ─────────────────────────────────────────

    video_prompt = ask_gemini(
        video_idea.strip(),
        "Video prompt generation",
    )

    if not 500 <= len(video_prompt) <= 2000:
        log.warning(
            "Video prompt is %d characters; expected 500–2000.",
            len(video_prompt),
        )

    # ─────────────────────────────────────────
    # STEP 2 — YOUTUBE TITLE
    # ─────────────────────────────────────────

    title_prompt = f"""
Based on this video prompt:

{video_prompt}

Give me a very short YouTube video title under 20 characters.

After the title, compulsory add:

#viralshort #shorts #Viral #short #indianviralshort

Including all the hashtags, do not let the complete output exceed
99 characters.

Return ONLY the title and hashtags.
No explanations.
No Markdown.
No quotes.
One line only.
""".strip()

    youtube_title = ask_gemini(
        title_prompt,
        "YouTube title generation",
    )

    if len(youtube_title) > 99:
        log.warning(
            "YouTube title is %d characters; expected <=99.",
            len(youtube_title),
        )

    return video_prompt, youtube_title

# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():

    print()
    print("╔════════════════════════════════════════════╗")
    print("║          AI VIRAL CONTENT ENGINE           ║")
    print("╚════════════════════════════════════════════╝")
    print()

    try:

        # ─────────────────────────────────────
        # INPUT
        # ─────────────────────────────────────

        idea = input(
            "Enter your video idea/fact: "
        ).strip()

        if not idea:
            log.error("No video idea provided.")
            sys.exit(1)

        # ─────────────────────────────────────
        # GEMINI
        # ─────────────────────────────────────

        video_prompt, youtube_title = generate_content(
            idea
        )

        # ─────────────────────────────────────
        # REVIEW
        # ─────────────────────────────────────

        print()
        print("════════════════ VIDEO PROMPT ════════════════")
        print(video_prompt)

        print()
        print("════════════════ YOUTUBE TITLE ══════════════")
        print(youtube_title)

        print()
        print("════════════════════════════════════════════")
        print("CONTENT READY FOR VIDEO GENERATION")
        print("════════════════════════════════════════════")
        print()

        # ─────────────────────────────────────
        # MANUAL CREDIT GATE
        # ─────────────────────────────────────

        confirmation = input(
            "Type YES to spend Kie credits and generate the video: "
        ).strip()

        if confirmation != "YES":

            log.info(
                "Video generation cancelled. "
                "No Kie task was created."
            )

            print()
            print("❌ Cancelled — no Kie credits were used.")
            print()

            return

        # ─────────────────────────────────────
        # KIE TASK CREATION
        # ─────────────────────────────────────

        log.info("User approved video generation.")

        task_id = create_kie_task(
            video_prompt
        )

        print()
        print("════════════════ KIE TASK ═══════════════════")
        print(f"Task ID: {task_id}")
        print("════════════════════════════════════════════")
        print()

        # ─────────────────────────────────────
        # WAIT + POLL
        # ─────────────────────────────────────

        video_url = wait_for_kie_video(
            task_id
        )

        # ─────────────────────────────────────
        # SUCCESS
        # ─────────────────────────────────────

        log.info("════════════════════════════════════")
        log.info("✓ VIDEO GENERATION COMPLETE")
        log.info("════════════════════════════════════")

        print()
        print("════════════════ VIDEO URL ══════════════════")
        print(video_url)
        print("════════════════════════════════════════════")
        print()

        print("✅ SUCCESS")
        print()

    except KeyboardInterrupt:

        log.warning(
            "Pipeline interrupted by user."
        )

        sys.exit(130)

    except Exception as e:

        log.error(
            "PIPELINE FAILED: %s",
            e,
        )

        sys.exit(1)


if __name__ == "__main__":
    main()