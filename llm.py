"""Single, centralised language-model client — wording only.

The tool uses a language model ONLY to turn things into readable text:
asking the clarifying questions, listing resources from free text, and writing
plain-language explanations of results. It is NEVER used to decide a score;
FAIR (F-UJI), the FAIR-R2L checklist and licence analysis are all rule-based.

A European-developed model (Mistral) is preferred. If no key is configured the
client returns None so callers fall back to their rule-based text — the tool
must keep working without any LLM.
"""

import requests

import config

TIMEOUT = 30


def is_available():
    """True when a language model is configured and can be called."""
    return bool(config.MISTRAL_API_KEY)


def generate(prompt, system=None, max_tokens=300, temperature=0.2):
    """Return generated text, or None if unavailable / on any error.

    Callers must treat None as 'use the rule-based fallback wording'.
    """
    if not config.MISTRAL_API_KEY:
        return None

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        response = requests.post(
            config.MISTRAL_API_URL,
            headers={
                "Authorization": f"Bearer {config.MISTRAL_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": config.LLM_MODEL,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        # Wording is never load-bearing — fall back silently to rule-based text.
        return None
