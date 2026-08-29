
import os
import requests

from services.logger import log


BASE_URL = "https://zernio.com/api/v1"


def get_headers():

    api_key = os.getenv(
        "ZERNIO_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "ZERNIO_API_KEY is missing from .env"
        )

    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def get_accounts():

    log.info(
        "→ Zernio: fetching connected accounts"
    )

    response = requests.get(
        f"{BASE_URL}/accounts",
        headers=get_headers(),
        timeout=30,
    )

    if not response.ok:

        log.error(
            "✗ Zernio accounts HTTP %s",
            response.status_code,
        )

        log.error(
            "%s",
            response.text[:1000],
        )

        response.raise_for_status()

    data = response.json()

    accounts = data.get(
        "accounts",
        [],
    )

    log.info(
        "✓ Zernio returned %d connected account(s)",
        len(accounts),
    )

    return accounts


def get_youtube_accounts():

    accounts = get_accounts()

    youtube = [

        account

        for account in accounts

        if account.get("platform") == "youtube"

        and account.get("isActive") is True

        and account.get("enabled") is True
    ]

    log.info(
        "✓ Found %d active YouTube account(s)",
        len(youtube),
    )

    return youtube


def create_post(
    content,
    video_url,
    account_id,
):

    payload = {

        "content": content,

        "mediaItems": [

            {
                "type": "video",
                "url": video_url,
                "filename": "video.mp4",
            }

        ],

        "platforms": [

            {
                "platform": "youtube",
                "accountId": account_id,
            }

        ],

        "publishNow": True,
    }

    log.info(
        "→ Zernio: creating YouTube post"
    )

    response = requests.post(
        f"{BASE_URL}/posts",
        headers=get_headers(),
        json=payload,
        timeout=60,
    )

    if not response.ok:

        log.error(
            "✗ Zernio post HTTP %s",
            response.status_code,
        )

        log.error(
            "%s",
            response.text[:1000],
        )

        response.raise_for_status()

    data = response.json()

    log.info(
        "✓ Zernio post created successfully"
    )

    return data
