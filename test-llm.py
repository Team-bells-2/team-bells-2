import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError


def main() -> int:
    load_dotenv(Path(__file__).resolve().with_name(".env"), override=True)

    api_key = os.getenv("LLM_API_KEY", "").strip()
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    missing = [
        name
        for name, value in (
            ("LLM_API_KEY", api_key),
            ("LLM_BASE_URL", base_url),
            ("LLM_MODEL", model),
        )
        if not value
    ]
    if missing:
        print(
            f"Missing required .env setting(s): {', '.join(missing)}", file=sys.stderr
        )
        return 1

    if (urlsplit(base_url).hostname or "").lower() == "openrouter.ai" and not api_key.startswith(
        "sk-or-v1-"
    ):
        print(
            "Warning: LLM_BASE_URL is OpenRouter, but LLM_API_KEY does not match "
            "OpenRouter's usual key format. Check that this is an OpenRouter API key.",
            file=sys.stderr,
        )

    client = OpenAI(api_key=api_key, base_url=base_url)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": 'Reply with exactly: "LLM credentials are working."',
                }
            ],
            max_tokens=256,
        )
    except OpenAIError as error:
        status = f" (HTTP {error.status_code})" if error.status_code else ""
        print(f"LLM request failed{status}: {error}", file=sys.stderr)
        if error.status_code == 401:
            print(
                "The OpenAI SDK sends an Authorization: Bearer header automatically. "
                "Check that LLM_API_KEY is a valid key for the provider at LLM_BASE_URL "
                "and does not include a 'Bearer ' prefix.",
                file=sys.stderr,
            )
        return 1

    choice = response.choices[0] if response.choices else None
    answer = choice.message.content if choice else None
    if answer:
        print(answer)
        return 0

    print(
        "The request succeeded but returned no text. "
        f"model={response.model}, "
        f"finish_reason={choice.finish_reason if choice else 'no choices'}, "
        f"usage={response.usage.model_dump() if response.usage else None}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
