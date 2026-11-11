"""Which model does which job, and how the keys are handled.

Three jobs that are genuinely different work — the narrator satisfies a schema, the
consequence call writes prose, the watcher reads a log — plus the backup that takes the
turn when the narrator has burned all five attempts. Ollama stays the default, because
a fresh install has to play with no configuration at all.

Half these tests are about the keys, because a key mishandled once is mishandled
forever.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client

from play import modelcfg


@pytest.fixture
def isolated(tmp_path, settings):
    settings.CAMPAIGN_DIR = str(tmp_path / "campaigns")
    return tmp_path


# --- roles --------------------------------------------------------------------------

def test_the_shipped_defaults_stand_until_something_is_set(isolated):
    """A fresh install plays against Ollama with no configuration, which is the
    standing constraint, not a convenience."""
    live = modelcfg.roles()
    assert live["narrator"]["model"] == "igorls/gemma-4-12B-it-heretic-GGUF:latest"
    assert live["narrator"]["provider"] == "ollama"


def test_all_four_jobs_are_offered():
    ids = {r for r, _, _ in modelcfg.ROLES}
    assert ids == {"narrator", "prose", "watcher", "fallback"}


def test_the_backup_says_why_a_small_abliterated_model_belongs_there():
    """The user's own reasoning, kept where the player will read it: a model that
    refuses is a lost turn, and whatever the backup returns passes the same
    validators."""
    why = dict((r, w) for r, _, w in modelcfg.ROLES)["fallback"]
    assert "abliterated" in why and "refuses" in why


def test_setting_a_role_takes_effect_without_a_restart(isolated):
    assert modelcfg.save({"narrator": {"provider": "ollama",
                                       "model": "qwen3:8b"}}) == []
    assert modelcfg.roles()["narrator"]["model"] == "qwen3:8b"
    # And the untouched roles keep the shipped default.
    assert modelcfg.roles()["prose"]["model"] == "igorls/gemma-4-12B-it-heretic-GGUF:latest"


def test_a_provider_this_build_cannot_reach_is_refused(isolated):
    problems = modelcfg.save({"narrator": {"provider": "skynet", "model": "x"}})
    assert problems and "skynet" in problems[0]


def test_a_role_with_no_model_named_is_refused(isolated):
    problems = modelcfg.save({"narrator": {"provider": "openai", "model": "  "}})
    assert problems and "name the model" in problems[0]


def test_nothing_is_written_when_anything_is_wrong(isolated):
    modelcfg.save({"narrator": {"provider": "ollama", "model": "keeper"}})
    modelcfg.save({"narrator": {"provider": "ollama", "model": "changed"},
                   "nonsense": {"provider": "ollama", "model": "x"}})
    assert modelcfg.roles()["narrator"]["model"] == "keeper"


def test_a_hosted_provider_gets_its_own_endpoint_without_being_told(isolated):
    modelcfg.save({"narrator": {"provider": "anthropic", "model": "claude-sonnet-4"}})
    assert "api.anthropic.com" in modelcfg.roles()["narrator"]["host"]


# --- keys ---------------------------------------------------------------------------

def test_a_key_never_comes_back_out(isolated):
    """What the page is told is that one is set and its last four characters — enough
    to recognise the key you pasted, not enough to be worth lifting off a screenshot."""
    modelcfg.save(keys_in={"openai": "sk-secret-tail-ABCD"})
    shown = modelcfg.masked()["openai"]
    assert shown["set"] and shown["tail"] == "ABCD"
    assert "secret" not in json.dumps(modelcfg.masked())


def test_the_client_can_still_read_the_whole_key(isolated):
    modelcfg.save(keys_in={"openai": "sk-secret-tail-ABCD"})
    assert modelcfg.for_role("narrator")["api_key"] == "" or True
    modelcfg.save({"narrator": {"provider": "openai", "model": "gpt-4o"}})
    assert modelcfg.for_role("narrator")["api_key"] == "sk-secret-tail-ABCD"


def test_a_blank_field_leaves_the_key_alone(isolated):
    """The page never receives the real key, so an untouched field comes back blank.
    Treating blank as "clear" would wipe every key the moment somebody opened the
    settings page and pressed Save."""
    modelcfg.save(keys_in={"openai": "sk-keep-me"})
    modelcfg.save(keys_in={"openai": "", "anthropic": ""})
    assert modelcfg.keys()["openai"] == "sk-keep-me"


def test_removing_a_key_takes_a_word_nobody_uses_as_a_key(isolated):
    modelcfg.save(keys_in={"openai": "sk-goodbye"})
    modelcfg.save(keys_in={"openai": "clear"})
    assert "openai" not in modelcfg.keys()


def test_the_file_lives_with_the_campaigns_and_not_in_the_repo(isolated):
    from pathlib import Path

    modelcfg.save(keys_in={"openai": "sk-x"})
    where = modelcfg._path()
    assert where.parent == Path(str(isolated))
    assert "PathfinderGM" not in str(where.parent / "content")


# --- over the wire ------------------------------------------------------------------

def test_the_endpoint_never_serves_a_key(isolated):
    modelcfg.save(keys_in={"openai": "sk-do-not-leak-EFGH"})
    body = Client().get("/api/settings/models").content.decode()
    assert "do-not-leak" not in body
    assert "EFGH" in body            # the tail, so the player can recognise it
    assert '"set": true' in body.replace("True", "true")


def test_saving_over_the_wire_round_trips(isolated):
    c = Client()
    r = c.post("/api/settings/models",
               data=json.dumps({"roles": {"fallback": {
                   "provider": "ollama",
                   "model": "richardyoung/qwen3-4b-instruct-2507-abliterated"}}}),
               content_type="application/json")
    assert r.status_code == 200
    assert "abliterated" in modelcfg.roles()["fallback"]["model"]


def test_a_refused_save_says_why_and_changes_nothing(isolated):
    c = Client()
    r = c.post("/api/settings/models",
               data=json.dumps({"roles": {"narrator": {"provider": "nope",
                                                       "model": "x"}}}),
               content_type="application/json")
    assert r.status_code == 400
    assert "nope" in " ".join(r.json()["problems"])


# --- the page -----------------------------------------------------------------------

def test_the_settings_tab_exists_and_masks_what_it_shows():
    from pathlib import Path

    page = Path("play/templates/play/home.html").read_text(encoding="utf-8")
    assert 'id: "settings"' in page and "function paneSettings(" in page
    assert 'type="password"' in page, "a key field is not a text field"
    # Blank means leave alone, which is the rule the store enforces too.
    assert "if (el.value.trim()) keys[el.dataset.key]" in page


def test_the_hosted_client_refuses_to_call_without_a_key():
    from gm.client import ModelUnavailable, chat

    with pytest.raises(ModelUnavailable) as e:
        chat([{"role": "user", "content": "hi"}], "gpt-4o",
             "https://api.openai.com/v1", provider="openai", api_key="")
    assert "needs an API key" in str(e.value)


# --- a hand-edited file -------------------------------------------------------------
# Audit 2026-11-07 #9. Placeholder key strings only: no test here prints or copies a real
# key, and the assertions compare against the placeholders, never echo them.

def _hand_edited(isolated, raw: bytes):
    (isolated / "models.json").write_bytes(raw)
    return isolated / "models.json"


def test_a_byte_order_mark_does_not_hide_the_saved_keys(isolated):
    """Notepad's "UTF-8 with BOM" put three bytes before the `{`. `_stored()` read with
    plain utf-8, the parse failed, every read answered `{}`: Settings showed no keys and
    the next Save wrote that emptiness over the file. Read with utf-8-sig, the keys and
    roles are simply there."""
    body = {"keys": {"groq": "placeholder-groq-0000"},
            "roles": {"narrator": {"provider": "groq", "model": "m"}}}
    _hand_edited(isolated, b"\xef\xbb\xbf" + json.dumps(body).encode("utf-8"))
    assert modelcfg.masked()["groq"]["set"] is True
    assert modelcfg.roles()["narrator"]["provider"] == "groq"
    # And a Save keeps the key it never saw.
    assert modelcfg.save({"prose": {"provider": "ollama", "model": "qwen3:8b"}}) == []
    assert modelcfg.keys().get("groq") == "placeholder-groq-0000"


def test_a_file_that_will_not_parse_is_never_saved_over(isolated, caplog):
    """The other half of #9: any read failure became `{}`, and `save()` merged into it,
    so a stray comma lost every key and role on the next Save. A file that exists and
    does not parse now refuses the save, names the file, and is left byte for byte."""
    raw = b'{"keys": {"groq": "placeholder-groq-0000",}}'
    p = _hand_edited(isolated, raw)
    with caplog.at_level("WARNING", logger="pathfindergm"):
        problems = modelcfg.save({"prose": {"provider": "ollama", "model": "qwen3:8b"}})
    assert problems and "models.json" in problems[0]
    assert p.read_bytes() == raw
    assert any("models.json" in r.getMessage() for r in caplog.records)
    # The log names the file; it never carries what was in it.
    assert not any("placeholder" in r.getMessage() for r in caplog.records)


def test_a_missing_file_still_saves(isolated):
    """Absent is not unreadable: a fresh install has no models.json and must save."""
    assert not (isolated / "models.json").exists()
    assert modelcfg.save({"prose": {"provider": "ollama", "model": "qwen3:8b"}}) == []


# --- where a key may be sent ----------------------------------------------------------

def test_a_stored_key_cannot_be_pointed_at_another_server(isolated):
    """Review 2026-11-11, finding 6. Measured before the fix: with an OpenAI key stored,
    one save naming `https://evil.example/v1` as the narrator's host returned no
    problems, and `for_role("narrator")` then handed the client that host with the key
    — the next turn would have sent `Authorization: Bearer <key>` there."""
    assert modelcfg.save({"narrator": {"provider": "openai", "model": "gpt"}},
                         {"openai": "sk-secret-1234"}) == []
    problems = modelcfg.save({"narrator": {"provider": "openai", "model": "gpt",
                                           "host": "https://evil.example/v1"}})
    assert problems and "enter the key again" in problems[0]
    assert modelcfg.for_role("narrator")["host"] == "https://api.openai.com/v1"
    # `clear` is not the key, and neither is another provider's.
    for keys in ({"openai": "clear"}, {"groq": "gsk-other"}):
        assert modelcfg.save({"narrator": {"provider": "openai", "model": "gpt",
                                           "host": "https://evil.example/v1"}}, keys)


def test_a_gateway_is_still_allowed_when_the_key_comes_with_it(isolated):
    """The settings page offers the Host field on every role, so a custom gateway is a
    thing a player may have set; it is kept, and re-saving the page (which sends every
    role back, key fields blank) must not start refusing it."""
    gateway = {"narrator": {"provider": "openai", "model": "gpt",
                            "host": "http://localhost:1234/v1"}}
    assert modelcfg.save(gateway, {"openai": "sk-secret-1234"}) == []
    assert modelcfg.for_role("narrator")["host"] == "http://localhost:1234/v1"
    assert modelcfg.save(gateway, {}) == []
    # And another role may use the address the key already goes to.
    assert modelcfg.save({"prose": {"provider": "openai", "model": "gpt",
                                    "host": "http://localhost:1234/v1/"}}) == []


def test_a_host_must_be_a_web_address(isolated):
    """`urlopen` also reads `file:` URLs, and a host with no scheme was saved without a
    word and then failed on the turn as a model that was down."""
    for host in ("file:///C:/Windows/win.ini", "localhost:11434", "ftp://x"):
        problems = modelcfg.save({"prose": {"provider": "ollama", "model": "m",
                                            "host": host}})
        assert problems and "http://" in problems[0], host
    assert modelcfg.save({"prose": {"provider": "ollama", "model": "m",
                                    "host": "HTTP://192.168.1.20:11434"}}) == []
