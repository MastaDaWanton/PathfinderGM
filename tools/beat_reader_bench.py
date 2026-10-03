"""Measure the beat reader against the hand-labelled beats (docs/beat-reader.md).

Not a pytest: it needs a live Ollama and takes minutes. The integrity of the labels is
tests/test_beat_reader_gold.py.

    python tools/beat_reader_bench.py                 # the beat reader
    python tools/beat_reader_bench.py --before        # the regex harvesters it replaced
    python tools/beat_reader_bench.py --json out.json --runs 2

`--before` runs the harvesters as `views._finish` ran them on 2026-10-03 — the old
labeller (`mentions.attribute`), `doubt_tags`, `note_cast` + `record_people` (seen or
heard: `seen_in_beat`, `only_a_predicate`), `speaker_real`, `embody_seen`,
`heard_places.heard_in`, `mentioned_elsewhere.phrases_at` and `pronouns_adopted` — over the
same beats and the same scenes. Those functions were retired by the beat reader in the
commit after fceeb44; to run `--before` again, check out fceeb44 (its result is recorded
in docs/beat-reader.md).
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

from tests.beat_reader.gold import CASES  # noqa: E402
from tests.beat_reader.score import align_lines, align_mentions, score, strict  # noqa: E402

ZHILVARNIA = "6953424c8a82"     # the Pangrella fixture's town, the owner's saves
VORMOOR = "bde94b038cba"        # the Aurvantis fixture's, the Bobby corpus
# The player corpora live only in the main checkout (owner's ruling, 2026-09-28: kept out
# of the repository), so a worktree looks there too.
BOBBY_DIR = Path(os.environ.get("BOBBY_CORPUS", "")) if os.environ.get("BOBBY_CORPUS") else \
    next((p for p in (ROOT / "tests" / "replays",
                      ROOT.parents[2] / "tests" / "replays" if len(ROOT.parents) > 2 else ROOT)
          if (p / "bobby-2026-09-28" / "turns.json").is_file()), ROOT / "tests" / "replays")


class _Place:
    def __init__(self, pid: str, name: str):
        self.id, self.name, self.kind = pid, name, ""


class TownEngine:
    """The engine's place questions, answered from the case's own list of the town's
    places, so the reader and the harvesters are shown exactly the same town."""

    def __init__(self, names: list[str], here: str):
        self._places = [_Place(f"town:{n.removeprefix('the ').replace(' ', '-')}", n)
                        for n in names]
        if not any(p.name == here for p in self._places):
            self._places.append(_Place(f"town:{here.removeprefix('the ')}", here))
        self._here = next(p for p in self._places if p.name == here)

    def places(self):
        return tuple(self._places)

    def open_ground(self):
        return ()

    def here(self):
        return self._here


def _world(case):
    from world.loader import load_cached

    if case["id"].startswith("bobby"):
        return load_cached("fixtures/aurvantis-campaign.json"), VORMOOR
    return load_cached("fixtures/pangrella-campaign.json"), ZHILVARNIA


def _scene(case):
    """A real Scene with the case's cast, the PC first, every NPC a guildhand renamed."""
    from rules.bestiary import instantiate
    from rules.dice import Dice
    from rules.engine import Engine, Scene
    from rules.sheet import load_pc

    world, loc = _world(case)
    scene = Scene(location_id=loc)
    pc = load_pc("fixtures/pc-kesst.json")
    for ref, name, what in case["cast"]:
        if what == "pc":
            pc.name = name
            if name == "Bobby":
                pc.pronouns, pc.gender = "he/him", "man"
            scene.add(pc)
            break
    engine = Engine(scene, Dice(seed=1), world=world)
    engine.place_party()
    for ref, name, what in case["cast"]:
        if what == "pc":
            continue
        a = instantiate("guildhand")
        a.ref, a.name = ref, name
        a.true_name = name if name[:1].isupper() and not name.lower().startswith("the ") else ""
        if ref in case.get("vague") or []:
            a.pronouns, a.gender = "they/them", ""
        else:
            a.pronouns, a.gender = "he/him", "man"
        a.described = True
        scene.add(a)
    # People the engine holds elsewhere in the town: the merchant left at the docks, the
    # clerk behind the shut door. Stood at another of the town's places.
    other = next((p.id for p in engine.places() if p.id != scene.at), "")
    for ref, name, what in case.get("away") or []:
        a = instantiate("guildhand")
        a.ref, a.name = ref, name
        a.true_name = ""
        a.pronouns, a.gender = "he/him", "man"
        scene.arrive(a, place_id=other)
    return scene, engine, world


def _town(case, engine) -> list[str]:
    if case.get("town"):
        return list(case["town"])
    return [p.name for p in list(engine.places()) + list(engine.open_ground())]


def _text_and_said(case):
    """The beat and the prose call's own tags: from the case, or from the Bobby corpus."""
    from gm import speech

    if case.get("corpus"):
        name, n, i = case["corpus"]
        path = BOBBY_DIR / name / "turns.json"
        if not path.is_file():
            return None, None
        turns = json.loads(path.read_text(encoding="utf-8"))["turns"]
        beat = next(t for t in turns if t["n"] == n)["beats"][i]
        return beat["text"], [dict(r) for r in beat.get("said") or [] if r.get("who")]
    text = case["text"]
    said = []
    for ref, prefix in case.get("said") or []:
        line = next((ln for ln in speech.lines(text)
                     if " ".join(ln.split()).lower().startswith(prefix.lower())), None)
        if line:
            said.append({"who": ref, "to": "you", "line": line.strip()})
    return text, said


def _chatml(chat):
    """For a model Ollama serves with a bare `{{ .Prompt }}` template (Osmosis-Structure-
    0.6B, measured 2026-10-03: `api/show` gives exactly that and the capability
    "completion" only): Ollama would drop the system message and the demonstration, so
    the messages are rendered here in Qwen3's ChatML and sent as one prompt; and `think`
    is not sent, since a model without the capability refuses the key."""
    def call(messages, model, host, **kw):
        parts = [f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>" for m in messages]
        prompt = "\n".join(parts) + "\n<|im_start|>assistant\n"
        kw["think"] = None
        return chat([{"role": "user", "content": prompt}], model, host, **kw)
    return call


# --- the reader ----------------------------------------------------------------------------

def run_reader(case, cfg) -> tuple[dict, dict]:
    from gm import beat_reader

    text, said = _text_and_said(case)
    if text is None:
        return {}, {"skipped": "corpus not on this disk"}
    scene, engine, world = _scene(case)
    town = TownEngine(_town(case, engine), case["here"])
    from gm import client

    chat = _chatml(client.chat) if cfg.get("chatml") else client.chat
    started = time.monotonic()
    r = beat_reader.read(text, scene, engine=town, said=said, model=cfg["model"],
                         host=cfg["host"], provider=cfg.get("provider", "ollama"),
                         api_key=cfg.get("api_key", ""), chat=chat)
    seconds = round(time.monotonic() - started, 2)
    keys = align_mentions(case, r.mentions)
    key_of = {id(m): k for k, m in keys.items()}
    root_key = {}
    for n in r.newcomers:
        m = r.mention(n.root)
        root_key[n.root] = key_of.get(id(m)) if m is not None else None
    mentions_ans, groups = {}, {}
    for k, m in keys.items():
        person = r.person_of(m)
        if person in r.refs or person in r.away:
            mentions_ans[k] = person
        elif person:
            mentions_ans[k] = "new"
            groups[k] = person
        else:
            mentions_ans[k] = "nobody" if m.model else "unread"
    lines = align_lines(case, r.lines)
    line_ans, to_ans = {}, {}
    for k, ln in lines.items():
        who = ln.speaker(r)
        if who and who not in r.refs and who != "you":
            who = f"new:{root_key.get(who) or who}"
        line_ans[k] = who or ("nobody" if ln.by else "")
        to = str(ln.to or "")
        m = r.mention(to)
        to_ans[k] = r.person_of(m) if m is not None else to
    here_id = town.here().id
    names = {p.id: p.name for p in town.places()}
    ans = {
        "mentions": mentions_ans, "groups": groups,
        "newcomers": [{"words": n.words, "where": n.where, "key": root_key.get(n.root)}
                      for n in r.newcomers],
        "lines": line_ans, "to": to_ans,
        "places": [{"words": p.words, "kind": p.kind,
                    "near": ("here" if p.landmark == here_id else names.get(p.landmark, "none"))}
                   for p in r.places],
        "placed": [{"words": p.words, "at": names.get(p.at, p.at)} for p in r.placed],
        "pronouns": dict(r.pronouns),
        "arrived": list(r.arrived),
        # The names that would be TAKEN: the reader's, through the engine's checks.
        "names": [{"who": (n["who"] if n["who"] in r.refs
                           else f"new:{root_key.get(n['who']) or n['who']}"),
                   "name": n["name"]} for n in r.names
                  if n["who"] not in r.refs
                  or not beat_reader.name_refusal(scene, world, n["who"], n["name"])],
    }
    meta = {"seconds": seconds, "timings": r.timings, "error": r.error, "read": r.read,
            "dropped": r.dropped, "raw": r.raw[:600]}
    return ans, meta


# --- the regex harvesters, as they ran on 2026-10-03 ------------------------------------

def run_before(case, cfg) -> tuple[dict, dict]:
    from gm import judgement, mentions, speech
    from play.aftermath import mentioned_elsewhere, pronouns_adopted, speaker_real
    from rules import heard_places

    text, said = _text_and_said(case)
    if text is None:
        return {}, {"skipped": "corpus not on this disk"}
    scene, engine, world = _scene(case)
    town = TownEngine(_town(case, engine), case["here"])
    before_refs = set(scene.actors)
    mentions.ENABLED = True
    # The finder as it was: its own word list only (the beat reader widened it).
    mentions._VOCAB[:] = [frozenset()]
    started = time.monotonic()
    att = mentions.attribute(text, scene, model=cfg["model"], host=cfg["host"],
                             provider=cfg.get("provider", "ollama"),
                             api_key=cfg.get("api_key", ""))
    seconds = round(time.monotonic() - started, 2)
    turn = 40
    live = [dict(r) for r in said]
    judgement.doubt_tags(scene, text, live, attribution=att)
    renamed = judgement.apply_introductions(scene, text, "", said=live, whose=att.who,
                                            world=world)
    introduced = judgement.note_cast(scene, text, turn=turn)
    judgement.record_people(scene, introduced, turn=turn, world=world, beat=text)
    ctx = SimpleNamespace(scene=scene, text=text, said=live, world=world, attribution=att,
                          turn=turn, door="turn", player_text="", campaign=None)
    speaker_real.step(ctx)
    judgement.embody_seen(scene, turn=turn, world=world, beat=text, engine=engine)
    made = {r: a for r, a in scene.actors.items() if r not in before_refs}
    heard = [rec for rec in (scene.population or {}).values()
             if rec.get("seen") is False and not rec.get("ref")]

    keys = align_mentions(case, att.mentions)
    mentions_ans = {k: (m.ref or "nobody") for k, m in keys.items()}
    # A body the harvesters made, tied to the gold phrase whose head its name holds.
    def _key_for(name: str):
        from gm.checks._people import head_of

        head = head_of(name).lower().split()[-1] if head_of(name) else ""
        for k, g in (case.get("people") or {}).items():
            if "new:" in g and head and head in k.lower():
                return k
        return None

    newcomers = [{"words": a.name, "where": "here", "key": _key_for(a.name)}
                 for a in made.values()]
    newcomers += [{"words": rec["phrase"], "where": "elsewhere", "key": _key_for(rec["phrase"])}
                  for rec in heard]
    from gm.beat_reader import lines_of

    lines = align_lines(case, lines_of(text))
    line_ans = {}
    for k, ln in lines.items():
        rec = speech.speaker(live, ln.words)
        who = str((rec or {}).get("who") or "")
        if who in made:
            who = f"new:{_key_for(made[who].name) or who}"
        if not who and "you" in (case["lines"].get(k) or "").split("|"):
            who = "you"          # not booked to anybody: the old door's right answer for "you"
        line_ans[k] = who
    here_id = town.here().id
    names = {p.id: p.name for p in town.places()}
    places, placed = [], []
    words = mentioned_elsewhere._person_words()
    for rec in live:
        who = str(rec.get("who") or "")
        if not who or who not in scene.actors or scene.actors[who].is_pc:
            continue
        for found in heard_places.heard_in(rec["line"], town.places(), here_id):
            places.append({"words": found["name"], "kind": found["kind"],
                           "near": ("here" if found["landmark"] == here_id
                                    else names.get(found["landmark"], "none"))})
        for phrase, place in mentioned_elsewhere.phrases_at(rec["line"], town.places(), words):
            if place.id != here_id:
                placed.append({"words": phrase, "at": place.name})
    vague = list(case.get("vague") or [])
    pronouns_adopted.step(ctx)
    pronouns = {ref: ("he" if scene.actors[ref].pronouns.startswith("he") else "she")
                for ref in vague if ref in scene.actors
                and scene.actors[ref].pronouns != "they/them"}
    ans = {"mentions": mentions_ans, "newcomers": newcomers, "lines": line_ans,
           "places": places, "placed": placed, "pronouns": pronouns,
           "names": [{"who": ref, "name": name} for ref, name in renamed]}
    return ans, {"seconds": seconds, "error": att.error}


# --- the report ------------------------------------------------------------------------------

def summarise(results: list[dict]) -> dict:
    tot: dict = {}
    for r in results:
        for q, t in r["score"].items():
            s = tot.setdefault(q, {})
            for k, v in t.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    s[k] = s.get(k, 0) + v
                elif isinstance(v, list):
                    s[k] = s.get(k, 0) + len(v)
    scored = [r for r in results if r["score"]]
    out = {"beats": len(scored), "strict": sum(1 for r in scored if strict(r["score"])),
           "questions": tot}
    secs = [r["meta"]["seconds"] for r in scored if r["meta"].get("seconds") is not None]
    if secs:
        out["seconds_median"] = round(statistics.median(secs), 2)
        out["seconds_max"] = max(secs)
    out["failed_calls"] = sum(1 for r in scored if r["meta"].get("error"))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", action="store_true")
    ap.add_argument("--json", default="")
    ap.add_argument("--only", default="", help="run the cases whose id holds this")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--model", default="")
    ap.add_argument("--places-new-only", action="store_true",
                    help="the places call lists only places the town lacks "
                         "(beat_reader.LIST_TOWN_PLACES off)")
    args = ap.parse_args()
    if args.places_new_only:
        from gm import beat_reader

        beat_reader.LIST_TOWN_PLACES = False

    from play import modelcfg

    cfg = dict(modelcfg.for_role("narrator"))
    if args.model:
        cfg["model"] = args.model
        cfg["chatml"] = "osmosis" in args.model.lower()
    results = []
    for run in range(args.runs):
        for case in CASES:
            if args.only and args.only not in case["id"]:
                continue
            fn = run_before if args.before else run_reader
            ans, meta = fn(case, cfg)
            if not ans:
                print(f"{case['id']}: {meta}")
                continue
            sc = score(case, ans)
            results.append({"id": case["id"], "run": run, "score": sc, "meta": meta,
                            "answers": ans})
            flag = "ok " if strict(sc) else "MISS"
            print(f"{flag} {case['id']} {meta.get('seconds')}s "
                  + " ".join(f"{q}={t.get('right', t.get('found'))}/{t.get('of', t.get('want'))}"
                             for q, t in sc.items()), flush=True)
            for q, t in sc.items():
                for k in ("misses", "wrong"):
                    if t.get(k):
                        print(f"      {q}.{k}: {t[k]}")
    summary = summarise(results)
    print(json.dumps(summary, indent=1))
    if args.json:
        Path(args.json).write_text(json.dumps({"summary": summary, "results": results},
                                              indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
