"""The settlement's own fact fields, by key: "  Daily life: …".

Moved out of `prompts.scene_brief` unchanged (fix pass S2, docs/fix-interfaces.md §2.2),
then widened by Lane C (2026-09-28, §3.4):

- **The key lexicon.** R0 measured that the eight keys the loop lifted miss Landscape,
  Daily Life, Customs and Conflict, which other exports write instead (the synthetic
  world is keyed that way on purpose). They are read after the eight, so an export that
  writes the eight reads exactly as it did.
- **`display_key`.** "Urban Life" on a village is the world's scale-blind template one
  level up from "the city's"; the narrator is shown "Daily life".
- **`in_its_own_words`.** The same stock "the city's" the opening's material no longer
  hands the model (item 1: Vormoor, a village, written up as "a sprawling settlement … the
  city's bustling thoroughfares"), put back to the settlement's own stated size.
"""
from __future__ import annotations

ORDER = 40
SLOT = "place"
# Only the separator is fixed: the keys and their values are the world's own words.
SCAFFOLD = ()

KEYS = ("Urban Life", "Social Classes", "Architecture", "Governance",
        "Formal Power", "Shadow Power", "Tension", "Daily Norms")
# What other exports call the same things (R0, 2026-09-28), read after the eight.
MORE_KEYS = ("Daily Life", "Customs", "Conflict", "Landscape")


def section(ctx) -> tuple[str, dict]:
    from play.opening_prose import stated_scale
    from rules import geography

    location = ctx.location
    if not location:
        return "", {}
    scale = stated_scale(location)
    lines, printed = [], {}
    for key in KEYS + MORE_KEYS:
        if location.fact(key):
            said = geography.in_its_own_words(str(location.fact(key)), scale)
            shown = geography.display_key(key)
            lines.append(f"  {shown}: {said}")
            # Reported as printed: a check reading `brief_facts` must see what the model
            # was shown, not a second spelling of it.
            printed[shown] = said
    return "\n".join(lines), ({"facts": printed} if printed else {})
