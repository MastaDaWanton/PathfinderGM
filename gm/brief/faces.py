"""ALREADY DESCRIBED: how the page first showed each person here (item 16.7).

Measured on the Bobby playtest, 2026-09-28: the watchman was described on the page — an
Orc, hair like wet rope, blue ink dots on the knuckles — and two beats later the gate had
"an older man with a face like cracked leather … a broadsword". The brief did carry his
face, labelled "use it when they are first described", which licensed a fresh invention
every beat after the first.

So everyone present whom the page has described is listed here with the page's own
sentence (`Actor.described_as`, kept by `judgement.settle_descriptions`) and the held
face, as a fact to keep to. The sentence is shown rather than a rule about it because a
demonstration outweighs an instruction (CLAUDE.md). The check under it is
`gm/checks/face_kept.py`.
"""
from __future__ import annotations

ORDER = 20
SLOT = "people"
SCAFFOLD = (
    "ALREADY DESCRIBED — keep to it (every later description of them agrees with this):",
    "the page said:",
)


def section(ctx) -> tuple[str, dict]:
    scene = ctx.scene
    rows, refs = [], []
    for ref, actor in (getattr(scene, "actors", {}) or {}).items():
        if getattr(actor, "is_pc", False) or not getattr(actor, "described", False):
            continue
        if actor.has_state("state.hidden"):
            continue
        said = [" ".join(str(s).split()) for s in (getattr(actor, "described_as", None)
                                                   or []) if str(s).strip()]
        face = " ".join(str(getattr(actor, "appearance", "") or "").split())
        if not said and not face:
            continue
        bits = []
        if said:
            bits.append("the page said: " + " ".join(said))
        if face:
            bits.append(face)
        rows.append(f"  {ref} — {actor.name}: " + " | ".join(bits))
        refs.append(ref)
    if not rows:
        return "", {}
    text = ("\nALREADY DESCRIBED — keep to it (every later description of them agrees "
            "with this):\n" + "\n".join(rows))
    return text, {"refs": refs}
