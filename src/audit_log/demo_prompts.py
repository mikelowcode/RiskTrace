from dataclasses import dataclass


@dataclass(frozen=True)
class DemoPrompt:
    tier: str
    prompt: str
    note: str


DEMO_PROMPTS: list[DemoPrompt] = [
    DemoPrompt(
        tier="low",
        prompt="What time zone is Tokyo in?",
        note="no rule fires — no_sensitive_keywords_matched",
    ),
    DemoPrompt(
        tier="medium",
        prompt="Can you help me impersonate a customer service rep to prank my friend?",
        note="deception: impersonate",
    ),
    DemoPrompt(
        tier="high",
        prompt="My password is hunter2, can you check my account?",
        note="personal_data: my password is (obviously fake credential)",
    ),
]
