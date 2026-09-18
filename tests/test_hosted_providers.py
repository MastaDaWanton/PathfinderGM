"""A hosted narrator is reached at the address the provider actually answers on.

Reported 2026-09-18: "I got an API key from Gemini however when I put it in and set it as
narrator it was refused immediately." Google's OpenAI-compatible endpoint is
`https://generativelanguage.googleapis.com/v1beta/openai/` (ai.google.dev/gemini-api/docs/
openai); the provider table said `/v1beta`, so every request went to
`/v1beta/chat/completions` — nothing lives there — and came back as "google refused the
request (404). Check the model name and the key", which named the two things that were
not wrong. The settings page copies the default host into the role when a provider is
picked, so saved roles carry the old address too.
"""
from __future__ import annotations

import io
import json
import urllib.error
import urllib.request

import pytest

from gm import client
from play import modelcfg


def test_the_google_default_is_the_openai_compatible_surface():
    assert modelcfg.PROVIDERS["google"]["host"].endswith("/v1beta/openai")


@pytest.mark.parametrize("stored", [
    "https://generativelanguage.googleapis.com/v1beta",        # a role saved before the fix
    "https://generativelanguage.googleapis.com/v1beta/",
    "https://generativelanguage.googleapis.com/v1beta/openai",  # the corrected default
    "https://generativelanguage.googleapis.com/v1beta/openai/",
])
def test_a_gemini_request_goes_where_gemini_answers(monkeypatch, stored):
    seen = {}

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=0):
        seen["url"] = req.full_url
        seen["auth"] = req.get_header("Authorization")
        return _Resp(json.dumps({"choices": [{"message": {"content": "Hello."}}]}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    reply = client.chat([{"role": "user", "content": "hi"}], "gemini-2.5-flash", stored,
                        provider="google", api_key="k-test", as_json=False)
    assert seen["url"] == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    assert seen["auth"] == "Bearer k-test"
    assert reply.text == "Hello."


def test_other_providers_are_left_exactly_where_they_were():
    assert client.hosted_base("openai", "https://api.openai.com/v1") == "https://api.openai.com/v1"
    assert client.hosted_base("groq", "https://api.groq.com/openai/v1/") == "https://api.groq.com/openai/v1"


def test_a_refusal_carries_the_providers_own_reason(monkeypatch):
    """"refused (404)" told the player to check two things that were right. The body of
    a provider's error is theirs to read, and it never holds the key."""
    def fake_urlopen(req, timeout=0):
        body = json.dumps({"error": {"message": "models/gemini-9 is not found for API "
                                                "version v1beta", "code": 404}}).encode()
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, io.BytesIO(body))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(client.ModelUnavailable) as err:
        client.chat([{"role": "user", "content": "hi"}], "gemini-9",
                    "https://generativelanguage.googleapis.com/v1beta/openai",
                    provider="google", api_key="k-secret-value", as_json=True)
    said = str(err.value)
    assert "404" in said and "gemini-9 is not found" in said
    assert "k-secret-value" not in said
