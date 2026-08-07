"""Scaffold-only smoke test for the Ollama (OpenAI-compatible) path.

Not the real wrapper -- just confirms the base URL/model are set and
prints the raw response object so its shape is visible before the real
extraction logic gets built.
"""

import os
import sys

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()

    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    api_key = os.environ.get("OLLAMA_API_KEY", "ollama")
    model = os.environ.get("OLLAMA_MODEL")
    if not model:
        print("OLLAMA_MODEL is not set. Copy .env.example to .env and fill it in.")
        sys.exit(1)

    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Say hello in one short sentence."}],
    )

    print(response)


if __name__ == "__main__":
    main()
