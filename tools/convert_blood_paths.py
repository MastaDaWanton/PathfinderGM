"""Turn the Blood Bending path abilities into effects the engine can execute.

The same treatment consumables and creatures already had, and for the same reason:
prose is what the author wrote, and the engine cannot roll a paragraph. Every claim
here is anchored on a number, a save, a named condition or a named 1e mechanic —
because those are the parts an engine can act on — and anything a pattern cannot claim
is left as prose rather than guessed at. A paraphrase that quietly drops a clause is
worse than a paragraph.

Run after `import_blood_paths.py`, over the class file it wrote:

    python tools/convert_blood_paths.py

**What converts.** Damage reduction, temporary hit points, non-lethal costs paid by the
bender, healing, ability damage, flat modifiers, blood stacks, and the saving throws
that gate them. These are the regular sentences, and they are regular because the
author wrote the class in 1e's own vocabulary.

**What does not, and why it is not forced.** Three shapes recur that the engine has no
representation for, and writing them as though it did is the failure
`docs/homebrew-rules.md` §1 exists to prevent:

  * *Formulas against Control Blood level* — "Armor Bonus to AC equal to
    3+ControlBloodLevel". The engine's modifiers are numbers, not expressions of a
    track it does not model. The pools already use formula strings, so this is the
    natural place to grow next.
  * *Blood Pools as objects in the scene* — half of Blood Spike detonates, siphons or
    teleports between pools that would have to exist somewhere with a position. The
    grid can hold them; nothing creates them yet.
  * *Multipliers of the class's own Blood die* — "Blood DMG ×3" is a number the class
    table carries per level, and the effect spec has no way to say "three times that
    row's blood die".

Each is recorded per ability in `needs`, so the class tab can say which of the three is
missing rather than showing an ability that silently does nothing.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "content" / "classes" / "blood-bending.json"

DIE = r"\d+d\d+(?:\s*[+-]\s*\d+)?|\d+"
CONDITIONS = ("staggered", "stunned", "sickened", "nauseated", "shaken", "frightened",
              "prone", "entangled", "blinded", "dazed", "fatigued", "exhausted",
              "paralyzed", "grappled", "helpless")


def convert(name: str, text: str) -> tuple[list[dict], list[str]]:
    """Effects the engine can run, and the shapes it cannot."""
    out: list[dict] = []
    needs: list[str] = []
    low = text.lower()

    # Damage reduction. Iron Clot lists its whole ladder in one sentence — "DR 2/-
    # (Lvl 1), DR 5/- (Lvl 2), DR 8/- (Lvl 3), DR 12/- (Lvl 5)" — and emitting all four
    # gave the character DR 27. Several values is a rank that scales, which the engine
    # cannot express yet; one value is one DR.
    found_dr = re.findall(r"\bDR\s*(\d+)\s*/\s*([^\s,.;)]+)", text, re.I)
    if len(found_dr) == 1:
        amount, bypass = found_dr[0]
        out.append({"type": "damage_reduction", "amount": int(amount),
                    "bypass": "" if bypass in ("-", "—") else bypass})
    elif len(found_dr) > 1:
        needs.append("a value that scales with Control Blood level")

    # Temporary hit points. "+2 Temp HP per Hit Die" is per-HD and so is a formula, but
    # the amount is still a number the engine can be handed once HD are known.
    for m in re.finditer(rf"({DIE})\s*Temp(?:orary)?\s*HP", text, re.I):
        out.append({"type": "temp_hp", "dice": m.group(1).replace(" ", ""),
                    "source": name})
    if re.search(r"Temp HP\s*(?:per|/)\s*(?:Hit Die|HD)", text, re.I):
        needs.append("temporary hit points scaled per Hit Die")

    # What the bender pays. Blood Bending's whole economy is self-inflicted non-lethal
    # damage, and it is the one cost the engine already models exactly.
    for m in re.finditer(rf"(?:take|cost|spend|sacrifice)\s+({DIE})\s*"
                         rf"(?:points?\s+of\s+)?non-?lethal", text, re.I):
        out.append({"type": "damage", "dice": m.group(1).replace(" ", ""),
                    "damage_type": "untyped", "lethality": "nonlethal",
                    "note": f"the cost of {name}"})

    # Healing, including the non-lethal kind this class trades in.
    for m in re.finditer(rf"(?:regain|restore|recover|heal)\w*\s+({DIE})"
                         rf"(?:\s*\+\s*CON\w*)?\s*(non-?lethal|HP|hit points)?",
                         text, re.I):
        kind = (m.group(2) or "").lower()
        spec = {"type": "heal", "dice": m.group(1).replace(" ", "")}
        if kind.startswith("non"):
            spec["lethality"] = "nonlethal"
        out.append(spec)

    # Ability damage: "Deals 1d4 Constitution damage".
    for m in re.finditer(rf"({DIE})\s+(Str|Dex|Con|Int|Wis|Cha)\w*\s+damage", text, re.I):
        out.append({"type": "ability_damage", "target": m.group(2).lower()[:3],
                    "dice": m.group(1).replace(" ", "")})

    # Flat modifiers the sheet computes: "+2 melee attack/damage rolls", "-2 AC".
    for m in re.finditer(r"([+-]\d+)\s+(?:melee\s+)?attack/damage", text, re.I):
        for target in ("attack", "damage"):
            out.append({"type": "combat_mod", "amount": int(m.group(1)),
                        "target": target, "bonus_type": "untyped"})
    for m in re.finditer(r"([+-]\d+)\s+AC\b", text):
        out.append({"type": "combat_mod", "amount": int(m.group(1)), "target": "ac",
                    "bonus_type": "untyped"})

    # The gate. Every save in this class is written to one DC formula.
    for m in re.finditer(r"\b(Fort(?:itude)?|Ref(?:lex)?|Will)\s*(?:save\s*)?"
                         r"\(?\s*DC\s*([^)\s,.;]+)", text, re.I):
        save = {"fort": "fort", "fortitude": "fort", "ref": "ref",
                "reflex": "ref", "will": "will"}[m.group(1).lower()]
        raw = m.group(2)
        if raw.isdigit():
            out.append({"type": "save_gate", "target": save, "dc": int(raw)})
        else:
            # "10+12LVL+CONmod" is the class's own formula throughout — a real DC the
            # engine cannot yet compute, so it is recorded rather than rounded off.
            out.append({"type": "save_gate", "target": save,
                        "note": f"DC {raw} — the class's formula"})
            needs.append("a save DC computed from level and Constitution")

    # Conditions inflicted, only when a save or a "become" makes it an effect rather
    # than scenery.
    for cond in CONDITIONS:
        if re.search(rf"\bbecome\w*\s+{cond}\b|\bor\s+be\s+{cond}\b", low):
            out.append({"type": "apply_condition", "target": cond})

    # Blood stacks: a pool that lives on the creature it was applied to, which is
    # exactly what `resource` with target scope was built for.
    # And only when the sentence actually applies one. "Pull back blood stacks from all
    # surrounding enemies" was recorded as applying a stack — the opposite of what it
    # does, and the kind of confidently wrong conversion that is worse than none.
    m = re.search(r"(?:applies|applying|gains?|apply|adds?)\s+(\d+)\s+blood stacks?", low)
    takes_them = re.search(r"\b(?:pull|remove|consume|spend|strip)\w*\b[^.]{0,40}"
                           r"blood stacks?", low)
    if m and not takes_them:
        out.append({"type": "narrative",
                    "target": f"applies {m.group(1)} blood stack(s)",
                    "resource": "blood stack", "amount": int(m.group(1))})

    # And the three shapes that genuinely have nowhere to go.
    if re.search(r"control ?blood ?level|controlbloodlevel|\bCB ?L(?:vl|evel)\b", low):
        needs.append("a value that scales with Control Blood level")
    # Blood Pools are scene objects now, so the two things abilities do with them —
    # leave one behind, take some back off the ground — are ops rather than a missing
    # capability. What each ability then *does* with the blood stays its own effect.
    if re.search(r"\b(?:a |one )?blood pool appears|creat\w+ a blood pool|"
                 r"leaves? a blood pool|blood pool manifest", low):
        out.append({"type": "engine_op", "op": "blood_pool",
                    "note": "leaves blood on the ground"})
    m = re.search(r"(?:absorb|detonate|consume|siphon|convert)\w*\s+"
                  r"(any number of|all|\d+)?\s*(?:active\s+)?blood pools?", low)
    if m:
        count = (m.group(1) or "1").strip()
        out.append({"type": "engine_op", "op": "spend_pools",
                    "count": "all" if count in ("any number of", "all") else int(count),
                    "note": "takes blood back off the ground"})
    elif re.search(r"blood pool", low) and not any(
            e.get("op") == "blood_pool" for e in out):
        # Pools it reads or moves between rather than makes or spends — Pool Resonance
        # firing *from* one, Blood Teleportation trading places with one. The scene can
        # hold them now; targeting one still has nowhere to go.
        needs.append("targeting a particular Blood Pool on the map")
    if re.search(r"blood dmg\s*[×x]\s*\d", low):
        needs.append("a multiple of the class table's Blood die")
    return out, sorted(set(needs))


def main() -> int:
    data = json.loads(TARGET.read_text(encoding="utf-8"))
    total = converted = 0
    for path in data["paths"].values():
        specs, needs = {}, {}
        for name, text in path["abilities"].items():
            total += 1
            effects, missing = convert(name, text)
            if effects:
                specs[name] = effects
                converted += 1
            if missing:
                needs[name] = missing
        path["effects"] = specs
        path["needs"] = needs
        path["effects_converted"] = True
        print(f"{path['name']:16} {len(specs):2}/{len(path['abilities']):2} abilities "
              f"carry effects, {len(needs):2} name something the engine lacks")

    data["_effects_note"] = (
        "Path abilities carry effect specs converted by tools/convert_blood_paths.py "
        "from the author's own sentences. `needs` records, per ability, which of three "
        "missing engine capabilities it depends on — Control Blood scaling, Blood Pools "
        "as scene objects, or a multiple of the class table's Blood die. An ability with "
        "effects and no needs is one the engine can resolve today."
    )
    TARGET.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print(f"\n{converted} of {total} abilities carry at least one executable effect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
