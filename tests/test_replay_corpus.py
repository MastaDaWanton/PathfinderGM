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
                        json.loads(call["raw"])
                    except ValueError:
                        bad_plan_json += 1
                    continue
                if call["role"] not in PROSE_ROLES:
                    continue
                text = _prose_of(call["raw"])
                if not text.strip():
                    continue
                drafts += 1
                alone = not [a for a in c.scene.actors.values() if not a.is_pc and a.hp > 0]
                review = narration.review(text, pc_name=pc.name if pc else "",
                                          known_names=known, alone=alone)
                faults.update(f.kind for f in review.findings)
                # Each state-writing detector on a fresh copy of the scene, so one's
                # booking cannot change what the next one sees.
                scene = _campaign(rec["save_before"], tmp_path).scene
                firings["note_cast booked"] += len(judgement.note_cast(scene, text, turn=n))
                firings["attacked_by named"] += sum(1 for r, _ in
                                                    judgement.attacked_by(c.scene, text) if r)
                firings["hailed_by"] += len(judgement.hailed_by(c.scene, text))
                firings["introductions"] += len(narration.introductions(text))
                firings["unname_strangers struck"] += len(
                    narration.unname_strangers(text, known)[1])
                here = agent._here_name()
                if here:
                    firings["stands_elsewhere"] += len(narration.stands_elsewhere(
                        text, here=here, places=agent._place_names()))
                firings["drafts with speech"] += int(speech.has_speech(text, 4))
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
