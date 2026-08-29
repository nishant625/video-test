
import os
import time
import json
import requests

from services.logger import log


CREATE_URL = (
    "https://api.kie.ai/api/v1/jobs/createTask"
)

STATUS_URL = (
    "https://api.kie.ai/api/v1/jobs/recordInfo"
)


def get_headers():

    api_key = os.getenv("KIE_API_KEY")

    if not api_key:
        raise RuntimeError(
            "KIE_API_KEY is missing from .env"
        )

    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def create_video(prompt):

    payload = {

        "model": os.getenv(
            "KIE_MODEL",
            "grok-imagine/text-to-video",
        ),

        "callBackUrl": os.getenv(
            "KIE_CALLBACK_URL",
            "https://your-domain.com/api/callback",
        ),

        "input": {

            "prompt": prompt,

            "aspect_ratio": os.getenv(
                "KIE_ASPECT_RATIO",
                "2:3",
            ),

            "mode": "normal",

            "duration": os.getenv(
                "KIE_DURATION",
                "6",
            ),

            "resolution": os.getenv(
                "KIE_RESOLUTION",
                "480p",
            ),
        },
    }

    log.info(
        "→ Kie: creating video task"
    )

    response = requests.post(
        CREATE_URL,
        headers=get_headers(),
        json=payload,
        timeout=60,
    )

    if not response.ok:

        log.error(
            "✗ Kie createTask HTTP %s",
            response.status_code,
        )

        log.error(
            "%s",
            response.text[:1000],
        )

        response.raise_for_status()

    data = response.json()

    task_id = (
        data.get("data", {})
        .get("taskId")
    )

    if not task_id:
        raise RuntimeError(
            f"Kie did not return taskId: {data}"
        )

    log.info(
        "✓ Kie task created: %s",
        task_id,
    )

    return task_id


def wait_for_video(task_id):

    initial_wait = int(
        os.getenv(
            "KIE_INITIAL_WAIT",
            "90",
        )
    )

    retry_interval = int(
        os.getenv(
            "KIE_RETRY_INTERVAL",
            "10",
        )
    )

    log.info(
        "Waiting %d seconds before first Kie status check...",
        initial_wait,
    )

    time.sleep(initial_wait)

    while True:

        log.info(
            "→ Checking Kie task %s",
            task_id,
        )

        response = requests.get(
            STATUS_URL,
            params={
                "taskId": task_id
            },
            headers=get_headers(),
            timeout=60,
        )

        if not response.ok:

            log.error(
                "✗ Kie status HTTP %s",
                response.status_code,
            )

            log.error(
                "%s",
                response.text[:1000],
            )

            response.raise_for_status()

        data = response.json()

        state = (
            data.get("data", {})
            .get("state")
        )

        log.info(
            "Kie task state: %s",
            state,
        )

        if state == "success":

            result_json = (
                data["data"]
                .get("resultJson")
            )

            if not result_json:
                raise RuntimeError(
                    "Kie succeeded but resultJson is missing."
                )

            result = json.loads(
                result_json
            )

            urls = result.get(
                "resultUrls",
                [],
            )

            if not urls:
                raise RuntimeError(
                    "Kie succeeded but returned no video URL."
                )

            log.info(
                "✓ Kie video generation SUCCESS"
            )

            return urls[0]

        if state in {
            "failed",
            "error",
            "cancelled",
        }:

            raise RuntimeError(
                f"Kie task failed with state: {state}"
            )

        log.info(
            "Kie still processing. "
            "Retrying in %d seconds...",
            retry_interval,
        )

        time.sleep(
            retry_interval
        )

