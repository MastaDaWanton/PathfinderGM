"""The essence rule: which of the 18 essences an effect carries (alchemy plan §5.3).

One rule, shared by `tools/alchemy_data_pass.py` (which writes an `essence` on every
alchemist product trait and every hybrid herb effect) and `tools/alchemy_review.py` (which
lays the potions' essences beside their materials' for lane E). Lane E's derivation table
(a spell's essences, content/rules/alchemy-essences.json) is the game's own reader; this is
the data pass's, and the review page shows where the two must agree.
"""
from __future__ import annotations

# --- the essence of an effect -----------------------------------------------------------------
#
# One rule, so a herb's essence and a reagent's are read the same way and the owner reviews a
# table rather than 400 choices. Read off the structured effect, never its words (law 1).
# A trait may override it with an explicit `essence` where the rule reads the type and the
# thing is plainly something else (a fire beetle's glow is `light`, a size change `change`).

ENERGY = {"fire": "fire", "cold": "frost", "acid": "acid", "electricity": "storm",
          "sonic": "thunder", "negative": "decay", "poison": "decay", "positive": "light",
          "force": "might", "bludgeoning": "might", "piercing": "might", "slashing": "might",
          "untyped": "might"}
CONDITION = {"entangled": "binding", "staggered": "binding", "paralyzed": "binding",
             "grappled": "binding", "pinned": "binding", "prone": "binding",
             "helpless": "binding", "petrified": "change",
             "sickened": "decay", "nauseated": "decay", "fatigued": "decay",
             "exhausted": "decay", "bleed": "decay", "dying": "decay",
             "dazzled": "light", "blinded": "light", "deafened": "thunder",
             "stunned": "thunder", "invisible": "shadow",
             "shaken": "mind", "frightened": "mind", "panicked": "mind", "confused": "mind",
             "fascinated": "mind", "dazed": "mind", "unconscious": "mind",
             "cowering": "mind"}
ABILITY = {"str": "might", "con": "might", "dex": "grace", "int": "mind", "wis": "mind",
           "cha": "mind"}
SKILL = {"stealth": "shadow", "perception": "sight", "heal": "vigour",
         "acrobatics": "lightness", "climb": "lightness", "fly": "lightness",
         "swim": "lightness", "escape artist": "grace", "disguise": "change",
         "sleight of hand": "grace", "ride": "grace"}
PERMISSION = {"size_larger": "change", "size_smaller": "change", "gaseous_form": "change",
              "breathe_water": "change", "endure_elements": "ward",
              "comprehend_languages": "mind", "pass_without_trace": "shadow",
              "absorb_energy": "ward", "ward_mind_control": "ward",
              "ward_summoned_contact": "ward"}
_PURE_WORDS = ("poison", "disease", "venom", "toxin")


def essence_of(spec: dict) -> str:
    """The essence the rule reads off one effect (see the table above)."""
    if spec.get("essence"):
        return str(spec["essence"])
    t = str(spec.get("type") or "")
    target = str(spec.get("target") or "").lower()
    note = str(spec.get("note") or "").lower()
    if t in ("damage", "object_damage"):
        return ENERGY.get(str(spec.get("damage_type") or "untyped"), "might")
    if t == "burning":
        return ENERGY.get(str(spec.get("damage_type") or "fire"), "fire")
    if t in ("heal", "temp_hp", "fast_healing", "ability_restore"):
        return "vigour"
    if t in ("remove_condition", "suppress_condition", "immunity"):
        return "purity"
    if t == "apply_condition":
        return CONDITION.get(target, "binding")
    if t == "save_gate":
        for inner in spec.get("on_failure") or ():
            if isinstance(inner, dict):
                return essence_of(inner)
        return "decay"
    if t in ("ability_damage", "ability_drain", "bleed", "negative_level"):
        return "decay"
    if t == "ability_mod":
        return ABILITY.get(target, "might")
    if t == "skill_mod":
        return SKILL.get(target, "mind")
    if t == "save_mod":
        if any(w in note for w in _PURE_WORDS):
            return "purity"
        if target == "will" or "fear" in note:
            return "mind"
        return "ward"
    if t == "combat_mod":
        return "ward" if target in ("ac", "cmd", "touch_ac") else "might"
    if t in ("resistance", "damage_reduction", "spell_resistance", "fortification"):
        return "ward"
    if t == "vulnerability":
        return ENERGY.get(target, "decay")
    if t == "speed":
        return "grace" if target in ("", "land") else "lightness"
    if t == "sense":
        return "sight"
    if t == "light":
        return "light"
    if t == "concealment":
        return "shadow"
    if t == "manifest":
        return "shadow" if spec.get("terrain") == "obscuring" else "binding"
    if t == "permission":
        return PERMISSION.get(str(spec.get("tag") or ""), "change")
    if t == "strikes_as":
        if target in ("good", "lawful", "silver"):
            return "purity"
        if target == "ghost_touch":
            return "change"
        return "might"
    if t == "crit_range":
        return "might"
    if t == "choose_one":
        for inner in spec.get("options") or ():
            if isinstance(inner, dict):
                return essence_of(inner)
    if t == "spell_operation":
        return "purity" if spec.get("operation") in ("dispel", "suppress", "counter") \
            else "change"
    return "change"
