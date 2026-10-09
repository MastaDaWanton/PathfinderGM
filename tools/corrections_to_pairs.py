"""Turn the "That's wrong" log into fine-tuning sets for the narrator.

The table logs every beat the player marked wrong to `<data>/training/corrections.jsonl`
(play/corrections.py): one record per episode, with the prompt that wrote the beat and
every version that followed, each with a verdict. This writes three files beside it, in
the conversational formats TRL's trainers read (huggingface.co/docs/trl/dataset_formats):

  * `pairs.dpo.jsonl` — `{prompt, chosen, rejected}` for DPOTrainer (or ORPO/CPO). The
    chosen is the version that stood: the player's own words, a remake they kept, or a
    remake they moved on from (`implicit`). The rejected is each version they marked
    wrong or put back. An episode with nothing chosen gives no pair.
  * `examples.kto.jsonl` — `{prompt, completion, label}` for KTOTrainer: every judged
    version, label true for kept and false for wrong or reverted — including the episodes
    that never got a good version, which is why the log keeps them. KTO is built for
    exactly this: unpaired, and more bad examples than good (Ethayarajh et al., 2024).
  * `repair.kto.jsonl` — the same for the REPAIR call, from each remake's own prompt: a
    remake the player rejected is a failure of the call that wrote it.

`prompt` is the narrator's own messages as they were sent (system, examples, the turn), so
the model is trained on the exact context it failed in. Completions are written as the
reply the call is asked for — `{"narration": "…"}` as a JSON string — because that is the
shape the prose schema makes it answer in; `--plain` writes the bare prose instead.

The page text is not quite the narrator's own: the pipeline appends sentences of its own
(a death line, a face) and `model_text` has those taken out, as `narration.own_prose` takes
them out of what the narrator is shown. That is the text used here.

How it would be used, roughly (on a machine with a GPU; nothing here trains anything):

    python tools/corrections_to_pairs.py                    # the app's data folder
    python tools/corrections_to_pairs.py path/to/corrections.jsonl --out some/folder

    from datasets import load_dataset
    from trl import DPOConfig, DPOTrainer
    pairs = load_dataset("json", data_files="pairs.dpo.jsonl")["train"]
    DPOTrainer(model=..., args=DPOConfig(...), train_dataset=pairs,
               processing_class=tokenizer).train()

with a LoRA on the narrator's base weights, and the result converted to GGUF for Ollama.
`--explicit-only` drops the implicit keeps (the player moving on rather than pressing
Keep), which are weaker evidence; by default they are in, and each row's `meta` says
which it was so a trainer can weigh them (strip `meta` if a trainer refuses extra keys).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _default_log() -> Path:
    from pathfindergm.paths import user_data_root

    return user_data_root() / "training" / "corrections.jsonl"


def _read(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _completion(text: str, plain: bool) -> list[dict]:
    content = text if plain else json.dumps({"narration": text}, ensure_ascii=False)
    return [{"role": "assistant", "content": content}]


def _text(v: dict) -> str:
    return str(v.get("model_text") or v.get("text") or "").strip()


def _good(v: dict, explicit_only: bool) -> bool:
    return v.get("verdict") == "kept" and not (explicit_only and v.get("implicit"))


def _bad(v: dict) -> bool:
    return v.get("verdict") in ("wrong", "reverted")


def convert(records: list[dict], *, plain: bool = False,
            explicit_only: bool = False) -> dict[str, list[dict]]:
    """The three sets from the log's records. Pure: no files, so the suite can hold it to
    the record shape `play/corrections.py` writes."""
    dpo, kto, repair = [], [], []
    for rec in records:
        prompt = (rec.get("input") or {}).get("messages")
        versions = [v for v in rec.get("versions") or [] if _text(v)]
        meta_base = {"episode": rec.get("id"), "outcome": rec.get("outcome"),
                     "narrator_model": rec.get("narrator_model"),
                     "app_version": rec.get("app_version")}
        if prompt:
            chosen = [v for v in versions if _good(v, explicit_only)]
            rejected = [v for v in versions if _bad(v)]
            for good in chosen:
                for bad in rejected:
                    if _text(bad) == _text(good):
                        continue
                    dpo.append({"prompt": prompt,
                                "chosen": _completion(_text(good), plain),
                                "rejected": _completion(_text(bad), plain),
                                "meta": {**meta_base, "chosen_by": good.get("by"),
                                         "rejected_by": bad.get("by"),
                                         "implicit": bool(good.get("implicit")),
                                         "flagged": bad.get("flagged_sentences") or [],
                                         "note": bad.get("note") or ""}})
            for v in versions:
                if _good(v, explicit_only) or _bad(v):
                    kto.append({"prompt": prompt,
                                "completion": _completion(_text(v), plain),
                                "label": _good(v, explicit_only),
                                "meta": {**meta_base, "by": v.get("by"),
                                         "verdict": v.get("verdict"),
                                         "implicit": bool(v.get("implicit"))}})
        for v in versions:
            if v.get("by") == "remake" and v.get("repair_messages") and (
                    _good(v, explicit_only) or _bad(v)):
                repair.append({"prompt": v["repair_messages"],
                               "completion": _completion(str(v.get("text") or ""), False),
                               "label": _good(v, explicit_only),
                               "meta": {**meta_base, "verdict": v.get("verdict"),
                                        "model": v.get("model")}})
    return {"pairs.dpo.jsonl": dpo, "examples.kto.jsonl": kto, "repair.kto.jsonl": repair}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("log", nargs="?", help="corrections.jsonl (default: the app's data "
                                           "folder, or PATHFINDER_GM_DATA's)")
    ap.add_argument("--out", help="folder to write into (default: beside the log)")
    ap.add_argument("--plain", action="store_true",
                    help="completions as bare prose instead of the {\"narration\"} reply")
    ap.add_argument("--explicit-only", action="store_true",
                    help="leave out the versions kept only by the player moving on")
    args = ap.parse_args(argv)
    log = Path(args.log) if args.log else _default_log()
    if not log.is_file():
        print(f"No log at {log}. Mark a beat wrong in the game first.", file=sys.stderr)
        return 1
    records = _read(log)
    out = Path(args.out) if args.out else log.parent
    out.mkdir(parents=True, exist_ok=True)
    sets = convert(records, plain=args.plain, explicit_only=args.explicit_only)
    for name, rows in sets.items():
        (out / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                                        for r in rows), encoding="utf-8")
    uncaptured = sum(1 for r in records if not (r.get("input") or {}).get("messages"))
    print(f"{len(records)} episodes: {len(sets['pairs.dpo.jsonl'])} DPO pairs, "
          f"{len(sets['examples.kto.jsonl'])} KTO examples, "
          f"{len(sets['repair.kto.jsonl'])} repair examples, into {out}"
          + (f" ({uncaptured} episodes had no prompt kept and gave the narrator sets "
             f"nothing)" if uncaptured else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
