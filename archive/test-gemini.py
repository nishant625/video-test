import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY missing from .env")

print("Key loaded:", api_key[:10] + "...")
print("Key length:", len(api_key))

client = genai.Client(api_key=api_key)

response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents="Say hello in one short sentence."
)

print("\nGEMINI RESPONSE:")
print(response.text)