import os
from dataclasses import dataclass


@dataclass
class ProviderResponse:
    response_text: str
    stop_reason: str
    tool_calls: list[dict] | None
    input_tokens: int | None
    output_tokens: int | None
    model: str


def _call_anthropic(prompt: str) -> ProviderResponse:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in."
        )

    model = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    text_parts = []
    tool_calls: list[dict] = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            tool_calls.append({"id": block.id, "name": block.name, "input": block.input})

    return ProviderResponse(
        response_text="".join(text_parts),
        stop_reason=response.stop_reason,
        tool_calls=tool_calls or None,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        model=response.model,
    )


def _call_openai_compatible(
    prompt: str, *, base_url: str, api_key: str, model: str
) -> ProviderResponse:
    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )

    choice = response.choices[0]
    message = choice.message

    tool_calls: list[dict] | None = None
    if message.tool_calls:
        tool_calls = [
            {"id": tc.id, "name": tc.function.name, "input": tc.function.arguments}
            for tc in message.tool_calls
        ]

    usage = response.usage

    return ProviderResponse(
        response_text=message.content or "",
        stop_reason=choice.finish_reason,
        tool_calls=tool_calls,
        input_tokens=usage.prompt_tokens if usage else None,
        output_tokens=usage.completion_tokens if usage else None,
        model=response.model,
    )


def _call_ollama(prompt: str) -> ProviderResponse:
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    api_key = os.environ.get("OLLAMA_API_KEY", "ollama")
    model = os.environ.get("OLLAMA_MODEL")
    if not model:
        raise RuntimeError(
            "OLLAMA_MODEL is not set. Copy .env.example to .env and fill it in."
        )

    return _call_openai_compatible(prompt, base_url=base_url, api_key=api_key, model=model)


def _call_openai(prompt: str) -> ProviderResponse:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in."
        )

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    return _call_openai_compatible(
        prompt, base_url="https://api.openai.com/v1", api_key=api_key, model=model
    )


PROVIDERS = {
    "anthropic": _call_anthropic,
    "claude": _call_anthropic,
    "openai": _call_openai,
    "ollama": _call_ollama,
}


def resolve_model(provider: str) -> str:
    """What model a provider would use, without making a call. Mirrors the
    env-var + default logic embedded in each _call_* function -- kept here
    as the single source of truth so callers that need the model up front
    (e.g. coverage_probe's cache keys) don't duplicate that logic."""
    if provider in ("anthropic", "claude"):
        return os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")
    if provider == "openai":
        return os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    if provider == "ollama":
        model = os.environ.get("OLLAMA_MODEL")
        if not model:
            raise RuntimeError(
                "OLLAMA_MODEL is not set. Copy .env.example to .env and fill it in."
            )
        return model
    raise ValueError(
        f"Unknown provider {provider!r}. Choose from: {', '.join(sorted(set(PROVIDERS)))}"
    )


def call_provider(provider: str, prompt: str) -> ProviderResponse:
    try:
        fn = PROVIDERS[provider]
    except KeyError:
        raise ValueError(
            f"Unknown provider {provider!r}. Choose from: {', '.join(sorted(set(PROVIDERS)))}"
        ) from None

    return fn(prompt)
