"""Thin, provider-swappable LLM client for the AI layer.

Right now this is backed by Groq (serving Llama models) because Groq offers a
free tier, but the rest of the system only depends on the small ``chat()``
surface below — swapping to Anthropic, OpenAI, or a local model means editing
only this file.

Configuration comes from the environment (loaded from a gitignored ``.env`` if
python-dotenv is installed):
    GROQ_API_KEY   — required to make real calls.
    GROQ_MODEL     — optional; defaults to llama-3.3-70b-versatile.

The ``groq`` package is imported lazily inside :meth:`LLMClient.chat`, so code
that injects a fake client (e.g. the unit tests) never needs the SDK or a key.
"""

import os

# Load .env into os.environ if python-dotenv is available. Optional so the
# module still imports in a bare environment (e.g. CI without the package).
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - convenience only
    pass

DEFAULT_MODEL = "llama-3.3-70b-versatile"


class LLMError(RuntimeError):
    """Raised when the LLM cannot be configured or the call fails."""


class LLMClient:
    """Minimal chat wrapper around the Groq API.

    Args:
        model:       Groq model id; falls back to $GROQ_MODEL, then DEFAULT_MODEL.
        temperature: default sampling temperature (low = more deterministic).
        api_key:     overrides $GROQ_API_KEY (mainly for tests).
    """

    def __init__(
        self,
        model: "str | None" = None,
        temperature: float = 0.2,
        api_key: "str | None" = None,
    ):
        self.model = model or os.environ.get("GROQ_MODEL") or DEFAULT_MODEL
        self.temperature = temperature
        self._api_key = api_key or os.environ.get("GROQ_API_KEY")
        self._client = None  # created lazily on first call

    def _ensure_client(self):
        """Import the SDK and build the underlying client on first use."""
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise LLMError(
                "GROQ_API_KEY is not set. Copy .env.example to .env and add your "
                "key, or export GROQ_API_KEY in your shell."
            )
        try:
            from groq import Groq
        except ImportError as exc:  # pragma: no cover - environment issue
            raise LLMError(
                "The 'groq' package is not installed. Run: pip install groq"
            ) from exc
        self._client = Groq(api_key=self._api_key)
        return self._client

    def chat(
        self,
        system: str,
        user: str,
        *,
        temperature: "float | None" = None,
        max_tokens: int = 1200,
    ) -> str:
        """Send a system+user prompt and return the model's text reply.

        Raises LLMError on any configuration or API failure so callers can log
        the failure and fall back to the deterministic plan.
        """
        client = self._ensure_client()
        try:
            response = client.chat.completions.create(
                model=self.model,
                temperature=self.temperature if temperature is None else temperature,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            return response.choices[0].message.content or ""
        except LLMError:
            raise
        except Exception as exc:  # network, auth, rate limit, etc.
            raise LLMError(f"Groq call failed ({self.model}): {exc}") from exc
