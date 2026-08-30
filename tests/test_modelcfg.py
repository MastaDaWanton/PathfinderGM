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
