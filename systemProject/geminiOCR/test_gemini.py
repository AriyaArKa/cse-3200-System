import sys, os

sys.path.insert(0, ".")
from dotenv import load_dotenv

load_dotenv()

import google.generativeai as genai

key = os.getenv("GEMINI_API_KEY", "").strip()
print("Key present:", bool(key), "| Length:", len(key))

genai.configure(api_key=key)
model = genai.GenerativeModel("gemini-2.0-flash")

# --- 1. plain text test ---
try:
    resp = model.generate_content("Say hello in one word.")
    print("TEXT TEST OK:", resp.text)
except Exception as e:
    print("TEXT TEST ERROR:", type(e).__name__, "|", e)

# --- 2. image test ---
from PIL import Image
import io

# create a 100x100 white image
img = Image.new("RGB", (100, 100), color=(255, 255, 255))

try:
    resp2 = model.generate_content(["Describe this image in one sentence.", img])
    print("IMAGE TEST OK:", resp2.text)
except Exception as e:
    print("IMAGE TEST ERROR:", type(e).__name__, "|", e)

# --- 3. list available models ---
print("\nAvailable models:")
for m in genai.list_models():
    if "generateContent" in m.supported_generation_methods:
        print(" -", m.name)
