"""The conversation log's one writer: `play/aftermath/conversation_log.py` (Lane F, item 7.1).

"It should pop out with a log of what has been said… just the dialogue and vocalizations
such as grunting or laughing" (owner, playtest 2026-09-28). Every spoken line was already
tagged and lifted into who/to/line records — kept per beat, then never indexed per person,
so the log the owner asked for could not be read back. These tests hold the index:

  * the NPC lines kept on each beat, both ways, with the player's own QUOTED words (Q43)
    and the sounds `speech.vocalisations` finds — no scenery, no reported speech (Q44);
  * Continue records nothing of the player's; a line nobody tagged books nobody;
  * a name is snapshotted, so a person deleted from the scene keeps it in the log;
  * each person keeps their newest 300 (Q6), and old saves start empty (no backfill).

Measured over the owner's thirteen beats through the real `_finish`: 27 entries — 20 lines
from the watchman (10), the man in the jerkin (8) and Drenn (2), the player's 3 quoted
lines, and 4 sounds — every line a quotation of its beat or the player's words, every sound
outside every quotation. Before this step the same beats wrote nothing a log could read.
"""
from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings

import replays
from gm import speech
from play import aftermath
from play.aftermath import conversation_log


class _Reply:
    def __init__(self, text):
        self.text, self.seconds, self.model = text, 0.0, "stub"
        self.prompt_tokens = self.reply_tokens = 0
        self.done_reason = "stop"

    def json(self):
        return json.loads(self.text)


@pytest.fixture
def small(tmp_path):
    """A campaign with Drenn and the watchman standing by, and a way to log one beat."""
    from play import campaign as cm
    from rules.bestiary import instantiate
    from rules.sheet import load_pc

    with override_settings(CAMPAIGN_DIR=str(tmp_path / "campaigns")):
        cm._LIVE.clear()
        c = cm.begin_with(load_pc("fixtures/pc-kesst.json"))
        # Since 2026-09-30 (item 1) the opening's own lines are logged — the start's lead
        # speaks in it — so these tests start the log from their own beats.
        c.scene.conversation_log, c.scene.conversation_seq = [], 0
        drenn = c.scene.add(instantiate("guildhand", scene=c.scene, name="Drenn Ironvale"))
        watch = c.scene.add(instantiate("guildhand", scene=c.scene,
                                        name="the watchman waving traffic through"))

        def beat(text, said=(), player="", door="turn"):
            if player:
                c.transcript.append({"who": "player", "text": player})
            c.transcript.append({"who": "gm", "text": text, "kind": "setup",
                                 **({"said": list(said)} if said else {})})
            ctx = aftermath.context("beat", door, c, text=text, said=list(said),
                                    player_text=player if door == "turn" else "",
                                    beat_index=len(c.transcript) - 1)
            return aftermath.run("beat", ctx)

        yield {"c": c, "drenn": drenn.ref, "watch": watch.ref, "beat": beat}
        cm._LIVE.clear()


def test_lines_both_ways_and_a_grunt_are_logged_in_page_order(small):
    c, d, beat = small["c"], small["drenn"], small["beat"]
    small["c"].engine().join_talk(c.scene.actors[d])
    said = [{"who": d, "to": "you", "line": "Seen it? No,"},
            {"who": d, "to": "you", "line": "But I know who has."}]
    rows = beat("Drenn studies you. 'Seen it? No,' he says. 'But I know who has.' Drenn "
                "lets out a low, dry grunt.", said, player='I ask "Have you seen the leaf?"')
    # The stage runs every member, and since Lane D merged (2026-09-28) its pronoun step
    # rightly books "he says" for Drenn; what this test forbids is the log's own failures.
    assert not [r for r in rows if r.get("kind") in ("vocal-miss", "aftermath-error")]
    log = c.scene.conversation_log
    assert [(e["who"], e["kind"], e["text"]) for e in log] == [
        ("you", "line", "Have you seen the leaf?"),
        (d, "line", "Seen it? No,"),
        (d, "line", "But I know who has."),
        (d, "vocal", "lets out a low, dry grunt"),
    ]
    assert [e["n"] for e in log] == [1, 2, 3, 4] and c.scene.conversation_seq == 4
    you = log[0]
    assert you["to"] == d and you["among"] == [d] and you["src"] == "player"
    assert you["beat"] == len(c.transcript) - 2          # the player's own beat
    assert log[1]["beat"] == len(c.transcript) - 1 and log[1]["name"] == "Drenn Ironvale"
    assert log[3]["src"] == "named"


def test_the_players_unquoted_words_are_an_action_not_a_line(small):
    """Owner, Q43: quoted words only. "I ask him about the girl" is what the player did."""
    small["beat"]("The watchman shrugs.", player="I ask him about the girl in the market.")
    assert small["c"].scene.conversation_log == []


def test_continue_records_nothing_of_the_players(small):
    d = small["drenn"]
    said = [{"who": d, "to": "you", "line": "Well?"}]
    small["beat"]("'Well?' Drenn asks.", said, player='"Hm."', door="carry_on")
    assert [e["who"] for e in small["c"].scene.conversation_log] == [d]


def test_a_line_nobody_tagged_books_nobody_and_reported_speech_is_narration(small):
    """Only what the prose call tagged, and `_finish` kept, is a line: a groomer's cut line
    is never in `said`, so it is never logged. "Drenn asks where you are headed" is
    narration (owner, Q44)."""
    small["beat"]("'Nice day,' someone says. Drenn asks where you are headed.")
    assert small["c"].scene.conversation_log == []


def test_a_sound_nobody_can_be_found_for_is_a_miss_row_not_an_entry(small):
    rows = small["beat"]("Drenn and the watchman trade a look. He laughs.")
    assert rows == [{"kind": "vocal-miss", "phrase": "laughs", "why": "ambiguous"}]
    assert small["c"].scene.conversation_log == []


def test_a_deleted_person_keeps_their_name_in_the_log(small):
    c, w = small["c"], small["watch"]
    small["beat"]("'Move along,' the watchman says.",
                  [{"who": w, "to": "you", "line": "Move along,"}])
    c.scene.remove(w)
    assert w not in c.scene.people
    (entry,) = c.scene.conversation_log
    assert entry["name"] == "the watchman waving traffic through"
    page = Client().get(f"/api/conversation?with={w}").json()
    assert [e["name"] for e in page["entries"]] == ["the watchman waving traffic through"]


def test_the_log_survives_a_save_and_an_old_save_starts_empty(small, tmp_path):
    from play import campaign as cm

    c, d = small["c"], small["drenn"]
    small["beat"]("'Two days,' Drenn says.", [{"who": d, "to": "you", "line": "Two days,"}])
    path = c.save()
    back = cm.Campaign.load(path)
    assert back.scene.conversation_log == c.scene.conversation_log
    assert back.scene.conversation_seq == 1
    # An old save — beats with `said` on them and no log — loads with an empty log: the
    # lines already on its beats are not replayed into it (Q6, no backfill).
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["scene"].pop("conversation_log", None)
    raw["scene"].pop("conversation_seq", None)
    path.write_text(json.dumps(raw), encoding="utf-8")
    old = cm.Campaign.load(path)
    assert any(b.get("said") for b in old.transcript)
    assert old.scene.conversation_log == [] and old.scene.conversation_seq == 0


def test_each_person_keeps_their_newest_three_hundred():
    """Q6's cap, per person: a companion's 400 lines cannot push a stranger's three out."""
    chatty = [{"n": i, "who": "c1", "to": "you", "among": []} for i in range(1, 401)]
    quiet = [{"n": 401 + i, "who": "c2", "to": "you", "among": []} for i in range(3)]
    log = [quiet[0]] + chatty + quiet[1:]
    kept = conversation_log.capped(log)
    assert sum(e["who"] == "c1" for e in kept) == 300
    assert [e["n"] for e in kept if e["who"] == "c2"] == [401, 402, 403]
    assert [e["n"] for e in kept if e["who"] == "c1"][0] == 101
    # The player's words to a crowd count for everyone in it, and go with the last of them.
    both = [{"n": i, "who": "you", "to": "", "among": ["c1", "c2"]} for i in range(1, 302)]
    assert len(conversation_log.capped(both)) == 300


def test_the_opening_companions_first_lines_are_logged(small):
    """Owner, Q48: through `aftermath.after_opening`, which Lane C calls."""
    c, d = small["c"], small["drenn"]
    c.transcript.append({"who": "gm", "kind": "setup",
                         "text": "Drenn waves you over. 'You made it,' he says.",
                         "said": [{"who": d, "to": "you", "line": "You made it,"}]})
    aftermath.after_opening(c)
    (entry,) = c.scene.conversation_log
    assert (entry["who"], entry["text"], entry["beat"]) == (d, "You made it,",
                                                             len(c.transcript) - 1)


# --- the owner's thirteen beats, through the real `_finish` -----------------------------------

def _bobby_campaign(tmp_path, monkeypatch):
    """Each of the 13 beats through `views._finish`, the prose call standing in with the beat
    the player saw and the lines tagged on it (the S3 harness, keeping the campaign)."""
    from gm import client as gm_client
    from gm import watcher
    from gm.agent import GMAgent
    from play import campaign as cm
    from play import views
    from rules import population
    from rules.bestiary import instantiate
    from rules.engine import Resolution, Scene, _rehydrate
    from rules.sheet import load_pc
    from world.loader import load_cached

    wait = json.dumps({"narration": "You wait. What do you do?",
                       "intents": [{"op": "narrate_only", "because": "waits"}]})
    monkeypatch.setattr(watcher, "kick", lambda c: None)
    monkeypatch.setattr(gm_client, "chat", lambda *a, **k: _Reply(wait))
    with override_settings(CAMPAIGN_DIR=str(tmp_path / "bobby-campaigns")):
        world = load_cached("fixtures/aurvantis-campaign.json")
        s = Scene(location_id=world.by_name("Vormoor", kind="CITY").id)
        s.add(load_pc("fixtures/pc-kesst.json"))
        for p in replays.save("bobby.json")["people"]:
            if p["kind"] != "pc":
                s.add(instantiate(p.get("from_template") or "guildhand", scene=s,
                                  name=p["name"]))
        c = cm.Campaign(id="bobby-f", world_source="fixtures/aurvantis-campaign.json",
                        scene=s, seed=7)
        c.engine().place_party()
        cm._LIVE.clear()
        cm._LIVE["bobby-f"] = c
        cm.set_active("bobby-f")
        for t in replays.turns():
            beat = t["beats"][0]

            def narrate(self, *a, _b=beat, **k):
                self.last_said = [dict(r) for r in (_b.get("said") or [])]
                return _b["text"], [], []

            monkeypatch.setattr(GMAgent, "narrate_turn", narrate)
            agent = GMAgent(c.world, c.engine())
            views._arm_cards(agent, c)
            agent.intents_first = True
            outcomes = [_rehydrate(o) for o in
                        ((t.get("resolution") or {}).get("outcomes")
                         or (t.get("plan") or {}).get("outcomes") or [])]
            c.transcript.append({"who": "player", "text": t["player"]})
            population.drain_misses()
            views._finish(c, agent, Resolution(outcomes=outcomes), "", t["player"], None)
        cm._LIVE.clear()
    return c


@pytest.mark.skipif(not replays.available(), reason="the Bobby corpus is not on this disk")
def test_the_bobby_beats_log_only_what_was_said_and_the_sounds(tmp_path, monkeypatch):
    """The no-scenery invariant over real content: every `line` entry is a quotation of its
    beat (or of the player's words), and every `vocal` entry lies outside every quotation
    of its beat."""
    c = _bobby_campaign(tmp_path, monkeypatch)
    log = c.scene.conversation_log
    assert log, "nothing was logged over thirteen beats of talk"
    assert [e["n"] for e in log] == list(range(1, len(log) + 1))
    for e in log:
        beat = c.transcript[e["beat"]]["text"]
        if e["kind"] == "line":
            said = [ln.strip() for ln in speech.lines(beat)]
            assert any(e["text"] in ln or ln in e["text"] for ln in said if ln), e
        else:
            at = speech.blanked(beat).find(e["text"].split()[0])
            assert at >= 0 and not speech.inside(beat, at), e
    players = [e["text"] for e in log if e["who"] == "you"]
    assert players == [
        "actually, Im looking for coin and adventure led by my curiosity and the need for "
        "soft bed.",
        "lost implies I had a particular destination in mind, I in fact do not. I can to "
        "explore these woods.",
        "I can fly so i doubt I'll get lost."]
    sounds = [(e["who"], e["text"]) for e in log if e["kind"] == "vocal"]
    assert sounds == [("c1", "lets out a short, dry bark of a laugh"),
                      ("c1", "lets out a low, dry grunt"),
                      ("c8", "gives a short, dry laugh"),
                      ("c8", "lets out a short, barking laugh")]
    # Every line the page kept on a beat is in the log once, booked to whom the page booked
    # it, and nothing else is.
    kept = [(r["who"], r["line"]) for b in c.transcript if b.get("who") == "gm"
            for r in (b.get("said") or [])]
    assert [(e["who"], e["text"]) for e in log
            if e["kind"] == "line" and e["who"] != "you"] == kept
