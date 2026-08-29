import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ZERNIO_API_KEY")

if not API_KEY:
    print("❌ ZERNIO_API_KEY is missing from .env")
    sys.exit(1)

URL = "https://zernio.com/api/v1/accounts"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

print()
print("╔════════════════════════════════════════════╗")
print("║          ZERNIO CONNECTION TEST            ║")
print("╚════════════════════════════════════════════╝")
print()

print("→ Fetching connected accounts...")

try:
    response = requests.get(
        URL,
        headers=headers,
        timeout=30,
    )

    print(f"HTTP Status: {response.status_code}")
    print()

    if not response.ok:
        print("❌ Zernio request failed")
        print(response.text)
        sys.exit(1)

    data = response.json()

    print("✅ Zernio authentication successful")
    print()
    print("════════════ CONNECTED ACCOUNTS ════════════")

    # Print the raw response first so we can see the
    # exact structure returned by your Zernio account.
    print(data)

    print("════════════════════════════════════════════")
    print()

except requests.RequestException as e:
    print("❌ Network error:")
    print(e)
    sys.exit(1)

except Exception as e:
    print("❌ Unexpected error:")
    print(e)
    sys.exit(1)