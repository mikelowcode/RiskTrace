"""Scaffold-only smoke test for the Anthropic SDK path.

Not the real wrapper -- just confirms the API key is set and prints the
raw response object so its shape is visible before the real extraction
logic gets built.
"""

import os
import sys

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in.")
        sys.exit(1)

    model = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": "Say hello in one short sentence."}],
    )

    print(response)


if __name__ == "__main__":
    main()
