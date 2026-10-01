"""The detectors, run over real model output, on every suite run and without a model.

Every prose test in this suite was written against hand-made sentences, and CLAUDE.md
records why that is not enough: "synthetic fixtures and regex metrics have repeatedly given
confident, wrong answers about quality." The corpus in tests/replay/ is fresh probe sessions
against the fixture worlds (never a player's saves — the repository is public), recorded by
`tools/narrator_audit.py --record`: for each turn, the save as it stood before the turn and
every model call's raw reply. Here each recorded prose draft is replayed against the scene
it was written for.

Two kinds of number, kept in tests/replay/baseline.json:

  * faults — what `narration.review` finds in the raw drafts. A ceiling: a change that makes
    the pipeline flag more of real prose fails here; fewer is reported so the ceiling can be
    lowered.
  * firings — how often each detector that WRITES state fires on real prose: people booked
    out of the page (`note_cast`), blows read at the player (`attacked_by`), hails, names
    given, places the page stands the party in, invented names struck. Exact: any change to
    a detector moves these, and the diff is the evidence of what the change did on real
    output — the before-and-after the narration redesign is measured by.

`REPLAY_UPDATE=1 python -m pytest tests/test_replay_corpus.py` rewrites the baseline; the
diff is then reviewed like any other change.
"""
from __future__ import annotations

import collections
import gzip
import json
import os
from pathlib import Path

import pytest
from django.test import override_settings

HERE = Path(__file__).resolve().parent / "replay"
BASELINE = HERE / "baseline.json"
PROSE_ROLES = ("narrate_turn", "narrate_outcome")


def _records():
    for f in sorted(HERE.glob("*.jsonl.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for n, line in enumerate(fh):
                yield f.name, n, json.loads(line)


def _prose_of(raw: str) -> str:
    try:
        d = json.loads(raw)
        return str(d.get("narration", "")) if isinstance(d, dict) else str(raw)
    except ValueError:
        return str(raw)


def _campaign(save: dict, tmp: Path):
    from play import campaign as cm

    p = tmp / f"{save['id']}.json"
    p.write_text(json.dumps(save), encoding="utf-8")
    return cm.Campaign.load(p)


def measure(tmp_path) -> dict:
    from gm import judgement, narration, speech
    from gm.agent import GMAgent

    faults: collections.Counter = collections.Counter()
    firings: collections.Counter = collections.Counter()
    drafts = plans = bad_plan_json = 0
    with override_settings(CAMPAIGN_DIR=str(tmp_path)):
        for name, n, rec in _records():
            c = _campaign(rec["save_before"], tmp_path)
            agent = GMAgent(c.world, c.engine())
            known = agent._known_names()
            pc = c.scene.pc()
            for call in rec["calls"]:
                if call["role"] == "plan_turn":
                    plans += 1
                    try:
                        plan = json.loads(call["raw"])
                    except ValueError:
                        bad_plan_json += 1
                        continue
                    # The user's ruling on places (2026-09-25): the mechanism is free, but
                    # places must keep being created — so the corpus counts the plans
                    # that found one (docs/declared-not-guessed.md, the places door).
                    firings["plans founding a place"] += int(any(
                        isinstance(i, dict) and i.get("op") == "found"
                        for i in (plan.get("intents") or []) if isinstance(plan, dict)))
                    continue
                if call["role"] not in PROSE_ROLES:
                    continue
                text = _prose_of(call["raw"])
                if not text.strip():
                    continue
                drafts += 1
                # Speaker tags come out first, through the game's own door, and what
                # they claimed is counted: every quoted line, how many a tag attributed
                # to somebody here, and tags naming nobody here (docs/declared-not-
                # guessed.md; nobody has published tag compliance for 8-12B models, so
                # this corpus is the measurement). Replayed against the scene BEFORE the
                # turn, so a tag naming somebody the turn's own plan spawned, or a place
                # the turn travelled to, counts as "nobody here" although the game —
                # which lifts after the engine resolved — attributed it: on the retag run
                # this counts 5 such misses where the game's own turn log counted 2. The
                # game's `speech-tags` row is the true rate; this is a floor.
                agent.last_said = []
                text = agent._lift(text)
                said = agent.last_said
                lines = speech.lines(text)
                firings["quoted lines"] += len(lines)
                firings["lines tagged"] += sum(
                    1 for ln in lines
                    if (speech.speaker(said, ln) or {}).get("who"))
                firings["tags naming nobody here"] += sum(1 for r in said if not r["who"])
                alone = not [a for a in c.scene.actors.values() if not a.is_pc and a.hp > 0]
                review = narration.review(text, pc_name=pc.name if pc else "",
                                          known_names=known, alone=alone)
                faults.update(f.kind for f in review.findings)
                # Each state-writing detector on a fresh copy of the scene, so one's
                # booking cannot change what the next one sees.
                scene = _campaign(rec["save_before"], tmp_path).scene
                booked = judgement.note_cast(scene, text, turn=n)
                firings["note_cast booked"] += len(booked)
                # Everyone booked goes into the population with a life rolled
                # (rules/population.py, 2026-09-25): how many, and how many rolls on a
                # real phrase had to fall back because every row was excluded. Through
                # the turn's own rule, which keeps crowds out.
                for person in judgement.record_people(scene, booked, turn=n):
                    firings["population noted"] += 1
                    firings["life rolls that fell back"] += int(bool(
                        person["life"]["fallbacks"]))
                firings["attacked_by named"] += sum(1 for r, _ in
                                                    judgement.attacked_by(c.scene, text) if r)
                firings["hailed_by"] += len(judgement.hailed_by(c.scene, text, said=said))
                firings["introductions"] += len(narration.introductions(text))
                firings["unname_strangers struck"] += len(
                    narration.unname_strangers(text, known)[1])
                here = agent._here_name()
                if here:
                    firings["stands_elsewhere"] += len(narration.stands_elsewhere(
                        text, here=here, places=agent._place_names(),
                        **narration.site_words(agent.engine)))
                firings["drafts with speech"] += int(speech.has_speech(text, 4))
                # What a hand holds and a body suffers, against the scene and the turn's
                # own effect records (gm/state_claims.py). 0 on this corpus when it
                # landed (2026-09-27): four false firings on the first draft — a smith's
                # quoted "when the hammer falls", "a stunned, heavy silence", a city's
                # "sprawl" twice — each narrowed out; any firing here is a sentence the
                # game would now rewrite or cut, so it is read before it is accepted.
                from gm.state_claims import state_claims

                changes = [e for t in (rec.get("added_turn_log") or [])
                           for o in (t.get("outcomes") or [])
                           for e in (o.get("effects") or []) if isinstance(e, dict)]
                second = narration.pc_to_second_person(text, pc.name)[0] if pc else text
                firings["state claims flagged"] += len(state_claims(second, c.scene,
                                                                    changes))
    return {"drafts": drafts, "plans": plans, "bad_plan_json": bad_plan_json,
            "faults": dict(sorted(faults.items())), "firings": dict(sorted(firings.items()))}


def test_the_corpus_is_there():
    assert list(HERE.glob("*.jsonl.gz")), "tests/replay/ has no recorded sessions"
    assert BASELINE.exists(), "run with REPLAY_UPDATE=1 to write the baseline"


def test_real_prose_through_the_detectors(tmp_path):
    got = measure(tmp_path)
    if os.environ.get("REPLAY_UPDATE"):
        BASELINE.write_text(json.dumps(got, indent=1) + "\n", encoding="utf-8")
        pytest.skip("baseline rewritten; review the diff")
    want = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert got["drafts"] == want["drafts"] and got["plans"] == want["plans"], (
        "the corpus changed; rewrite the baseline with REPLAY_UPDATE=1")
    worse = {k: (v, want["faults"].get(k, 0)) for k, v in got["faults"].items()
             if v > want["faults"].get(k, 0)}
    assert not worse, f"more faults found in real prose than the ceiling allows: {worse}"
    assert got["firings"] == want["firings"], (
        "a state-writing detector now fires differently on real prose — if intended, "
        f"rewrite the baseline with REPLAY_UPDATE=1 and review the diff.\n"
        f"now:  {got['firings']}\nwas:  {want['firings']}")
