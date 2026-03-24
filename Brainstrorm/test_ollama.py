import requests
import json


def test_mistral():
    """Test Mistral model with the provided text"""

    # The text to summarize
    text = "আমি আজ office এ গিয়েছিলাম। The meeting was about project deadline."

    # Prepare the request
    url = "http://localhost:11434/api/generate"

    payload = {
        "model": "mistral",
        "prompt": f"Summarize this text in simple language:\n{text}",
        "stream": False,
    }

    print("Testing Mistral model...")
    print(f"Input text: {text}\n")
    print("Sending request to Ollama...\n")

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()

        result = response.json()
        summary = result.get("response", "")

        print("=" * 60)
        print("SUMMARY:")
        print("=" * 60)
        print(summary)
        print("=" * 60)
        print("\n✓ Mistral model is working!")

    except requests.exceptions.ConnectionError:
        print("❌ Error: Cannot connect to Ollama. Make sure Ollama is running.")
        print("   Try running: ollama serve")
    except Exception as e:
        print(f"❌ Error: {e}")


def test_nomic_embed():
    """Test nomic-embed-text model"""

    url = "http://localhost:11434/api/embeddings"

    payload = {
        "model": "nomic-embed-text",
        "prompt": "This is a test sentence for embeddings.",
    }

    print("\n\nTesting nomic-embed-text model...")

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()

        result = response.json()
        embedding = result.get("embedding", [])

        print(f"✓ Generated embedding with {len(embedding)} dimensions")
        print(f"  First 5 values: {embedding[:5]}")
        print("✓ nomic-embed-text model is working!")

    except requests.exceptions.ConnectionError:
        print("❌ Error: Cannot connect to Ollama. Make sure Ollama is running.")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    test_mistral()
    test_nomic_embed()
