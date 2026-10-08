"""The leatherworking data pass (docs/leatherworking-revamp-plan.md §14, §15), as a record.

What it writes into `content/materials/leatherworker-materials.json`, entry by entry: the
pieces each hide fills, its armour effects (and weapon effects, for a hide that can be a
grip), its working traits, surface and colour, the book's flags (always masterwork, a druid
may wear it, the suits it may be made into), a tannin's tannage, the form a counter sells a
hide in, and a `text` rewritten where the old one claimed what the app does not do. It adds
the materials the book has and the shelf did not (plan §14.5): eel hide's real rule,
angelskin, darkleaf cloth, griffon mane, bone studs, sharkskin and ray skin for grips,
cowhide for plain leather, and lane C's six generic hides. And it writes, into
`content/materials/blacksmith-materials.json`, the forge's four leather pieces as forms of
their leather parents (plan §4.4) and `ferrous` on iron and its alloys (contracts §6.2).

Two kinds of number, kept apart on purpose, as the forge's pass did:

- **Book** effects, `B(...)`, transcribed by hand from docs/leatherworking-prior-art.md §1.3
  (Core and Ultimate Equipment special materials, confirmed against the primary text in its
  critic pass, §7.1). No model authors these. tests/test_leather_materials.py states the
  same table independently and compares.
- **House** effects, everything else: drafted inside the validator's fences (the leather
  vocabulary, ±2 base, the tier ceilings, a drawback in every list) for the owner to review
  as a table (docs/leatherworking-review.md, written by tools/leather_review.py).

**Marks are on hold** (the owner, 2026-10-08). The proposed marks (plan §14.6) are kept in
`MARKS_ON_HOLD` below and written to the catalogue's top-level `marks_on_hold` block, which
nothing reads. Enabling them is one decision: set `ENABLE_MARKS` here and
`materials.MARKS_HELD` to False; deleting them is deleting that dict.

Every entry is run through `rules.materials.validate` before anything is written, and the
run refuses to write if any entry has a problem. Dry run by default.

    python tools/leather_data_pass.py            # validate and report
    python tools/leather_data_pass.py --apply    # validate, then write the files

Re-running is idempotent: the pass's fields are replaced, never appended, and existing ids
and names are never touched (the old bench and saved stock key on them).
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

from rules import materials  # noqa: E402

MAT_DIR = ROOT / "content" / "materials"
LEATHER_FILE = MAT_DIR / "leatherworker-materials.json"
FORGE_FILE = MAT_DIR / "blacksmith-materials.json"

ENABLE_MARKS = False

# --- notation (the forge pass's, so the two tables read alike) ------------------------------


def _with(spec: dict, kw: dict) -> dict:
    for k, v in kw.items():
        if v is not None:
            spec[k] = v
    return spec


def cm(target, n, bonus="material", **kw):
    """A combat modifier: ac, attack, damage, cmb, cmd, initiative."""
    return _with({"type": "combat_mod", "target": target, "amount": n,
                  "bonus_type": bonus}, kw)


def sv(save, n, bonus="material", **kw):
    return _with({"type": "save_mod", "target": save, "amount": n, "bonus_type": bonus}, kw)


def sk(skill, n, bonus="material", **kw):
    return _with({"type": "skill_mod", "target": skill, "amount": n,
                  "bonus_type": bonus}, kw)


def gm(target, n, **kw):
    """The item's own number, added to the armour table's value: acp is stored negative,
    so +2 is lighter and -2 heavier; asf is a percentage, so -10 is better."""
    return _with({"type": "gear_mod", "target": target, "amount": n}, kw)


def res(energy, n, **kw):
    return _with({"type": "resistance", "target": energy, "amount": n}, kw)


def dr(n, bypass="", **kw):
    """Damage reduction in the owner's reduced shape (2026-10-08): the creature's DR N/x
    gives a hide max(1, N/5)/x, rare and up, counted as a house modifier."""
    return _with({"type": "damage_reduction", "amount": n, "bypass": bypass}, kw)


def oi(energy):
    """The item itself is immune (dragonhide's book power), never the wearer."""
    return {"type": "object_immunity", "target": energy}


def B(spec: dict) -> dict:
    """A printed PF1e rule: applied from the main piece only and never scaled."""
    spec["book"] = True
    return spec


def wk(*traits) -> list[dict]:
    return [{"type": "working", "trait": t} for t in traits]


# --- pieces ---------------------------------------------------------------------------------
#
# A supple hide is a suit's body, its lacing or its lining, a shield's facing, and a worn
# good's body or lining. A rigid plate or shell is a body only (it cannot be laced or worn
# against the skin). Bat-wing leather "tears like paper under a blade" and is a lining and
# worn goods only. A grip-capable hide adds the forge's haft (plan §14.3).

SUPPLE = {"armour": ["body", "fastenings", "lining"], "shield": ["body"],
          "worn": ["body", "lining"]}
RIGID = {"armour": ["body"], "shield": ["body"]}
FINE = {"armour": ["lining"], "worn": ["body", "lining"]}


def grip(pieces: dict) -> dict:
    out = copy.deepcopy(pieces)
    out["weapon"] = ["haft"]
    return out


# A grip's three: about hold (plan §14.3: "attack +2 (sure grip), CMD vs disarm +2, with a
# negative (damage -2 for a slick wrap, hardness -2)"). Varied by hide so no two grips of one
# tier are the same thing.
GRIP_SURE = [cm("attack", 2), cm("cmd", 2), gm("hardness", -2)]
GRIP_SLICK = [cm("attack", 2), cm("cmd", 2), cm("damage", -2)]
GRIP_SCALE = [cm("attack", 2), cm("cmd", 2), gm("weight_pct", 20)]

# --- the hides ------------------------------------------------------------------------------
#
# id -> fields. Ids, names, tiers, sizes, `obtain` and `from_creatures` of the shipped hides
# are not touched. `price` is the counter's price for the hide as it is sold (`sold_as`,
# tanned): the Core Rulebook's leather armour is 10 gp and a Craft's raw materials are a
# third of the price, so the two hide units of a Medium suit are about 3.3 gp — 2 gp a
# Medium hide (one unit), 1 gp a Small, 4 gp a Large (plan §5.5's units). Each sits on or
# above `pricing.MATERIAL_FLOOR_GP` (1 gp common, 5 gp uncommon).

HIDES: dict[str, dict] = {}


def hide(mid: str, **fields) -> None:
    assert mid not in HIDES, mid
    HIDES[mid] = fields


# ---- common ----------------------------------------------------------------------------------
hide("deer-hide", surface="smooth", color="#b08a5e", pieces=SUPPLE, price=2,
     # Plan §13.3's worked example names deer's list exactly: "ACP +2, max Dex +2,
     # hardness -2". "Never reduces maximum Dexterity" was narrative; this is it, typed.
     armour=[gm("acp", 2), gm("max_dex", 2), gm("hardness", -2)],
     working=wk("forgiving", "fast_tan"))
hide("boar-hide", surface="fur", color="#6b4a32", pieces=SUPPLE, price=2,
     # "Stiff: the armour check penalty of a piece made from it is one worse" (narrative),
     # typed as -2 because house numbers start at ±2.
     armour=[cm("ac", 2), gm("hardness", 2), gm("acp", -2)],
     working=wk("thick", "slow_tan"))
hide("wolf-pelt", surface="fur", color="#8a8478", pieces=SUPPLE, price=2,
     armour=[sk("survival", 2), sv("fort", 2), gm("weight_pct", 20)],
     working=wk("forgiving"))
hide("dog-hide", surface="fur", color="#9a7b5a", pieces=SUPPLE, price=1,
     # "Takes every method without complaint; apprentice work of it sells as journeyman."
     armour=[gm("acp", 2), sk("handle animal", 2), gm("hardness", -2)],
     working=wk("forgiving", "flawless"))
hide("cat-pelt", surface="fur", color="#c2a272", pieces=SUPPLE, price=1,
     armour=[sk("stealth", 2), sk("acrobatics", 2), gm("hp_per_inch", -2)],
     working=wk("fast_tan"))
hide("horse-hide", surface="smooth", color="#5a3a26", pieces=SUPPLE, price=4,
     armour=[gm("hp_per_inch", 2), sk("ride", 2), gm("weight_pct", 20)],
     working=wk("forgiving"))
hide("goat-hide", surface="smooth", color="#c8ae86", pieces=SUPPLE, price=1,
     # "Takes dye truer than any other common hide": the tans-white trait.
     armour=[gm("max_dex", 2), sk("climb", 2), gm("hardness", -2)],
     working=wk("tans_white", "fast_tan"))
hide("viper-skin", surface="scale", color="#6f7a3a", pieces=grip(SUPPLE), price=1,
     armour=[sk("escape artist", 2), gm("acp", 2), gm("hp_per_inch", -2)],
     weapon=GRIP_SURE, working=wk("fast_tan"))
hide("crocodile-hide", surface="scale", color="#4f5a38", pieces=grip(SUPPLE), price=4,
     armour=[cm("ac", 2), sk("swim", 2), gm("acp", -2)],
     weapon=[cm("attack", 2), cm("cmb", 2), gm("weight_pct", 20)],
     working=wk("thick", "slow_tan"))
hide("monitor-lizard-hide", surface="scale", color="#7a6a4a", pieces=grip(SUPPLE), price=2,
     # "Keeps its suppleness: armour of it never reduces maximum Dexterity bonus."
     armour=[gm("max_dex", 2), sk("acrobatics", 2), gm("hardness", -2)],
     weapon=GRIP_SLICK, working=wk("forgiving"))
hide("toad-hide", surface="smooth", color="#7d7a4e", pieces=SUPPLE, price=1,
     armour=[sk("swim", 2), sk("stealth", 2), gm("hardness", -2)],
     working=wk("fast_tan"))
hide("bat-wing-leather", surface="smooth", color="#3e3436", pieces=FINE, price=1,
     # "Takes the finest tooling; useless for armour — it tears like paper under a blade."
     armour=[gm("weight_pct", -20), sk("perception", 2), gm("hp_per_inch", -2)],
     working=wk("flawless", "fast_tan"))
hide("weasel-pelt", surface="fur", color="#8c6a44", pieces=SUPPLE, price=1,
     armour=[cm("initiative", 2), sk("sleight of hand", 2), gm("hp_per_inch", -2)],
     working=wk("fast_tan"))
hide("elk-hide", surface="smooth", color="#9a7048", pieces=SUPPLE, price=4,
     # Plan §13.3's worked example: "Elk's armour list (proposed): AC +2, ACP -2, Survival
     # +2". Lane E's test computes the example to the integer from these.
     armour=[cm("ac", 2), gm("acp", -2), sk("survival", 2)],
     working=wk("thick", "slow_tan"))

# ---- uncommon --------------------------------------------------------------------------------
hide("dire-boar-hide", surface="fur", color="#4a3424", pieces=SUPPLE,
     # The old DR 1/slashing is gone: a dire boar has no damage reduction in the book, so
     # the owner's reduced-DR rule (2026-10-08) gives its hide none.
     armour=[cm("ac", 2), sv("fort", 2), gm("acp", -2)],
     working=wk("thick", "slow_tan"))
hide("winter-wolf-pelt", surface="fur", color="#d8dde2", pieces=SUPPLE,
     # Immune to cold: an immunity is the tier's ceiling (plan §5.4's rule, which the
     # named hides follow by hand), and uncommon's is 2. Plan §14.2's example document.
     armour=[res("cold", 2), sk("survival", 2), gm("acp", -2)],
     working=wk("forgiving"))
hide("boreal-wolf-pelt", surface="fur", color="#b9b4a8", pieces=SUPPLE,
     armour=[res("cold", 2), sk("survival", 2), gm("weight_pct", 20)],
     working=wk("forgiving"))
hide("black-bear-hide", surface="fur", color="#2e2622", pieces=SUPPLE,
     armour=[sv("fort", 2), gm("hp_per_inch", 2), gm("weight_pct", 20)],
     working=wk("thick", "slow_tan"))
hide("grizzly-hide", surface="fur", color="#5a4030", pieces=SUPPLE,
     armour=[sk("intimidate", 2), cm("ac", 2), gm("acp", -2)],
     working=wk("thick", "slow_tan"))
hide("polar-bear-hide", surface="fur", color="#e8e2d4", pieces=SUPPLE,
     armour=[res("cold", 2), sk("swim", 2), gm("weight_pct", 20)],
     working=wk("thick", "slow_tan"))
hide("frostfallen-bison-hide", surface="fur", color="#6e5844", pieces=SUPPLE,
     armour=[res("cold", 2), gm("hp_per_inch", 2), gm("acp", -2)],
     working=wk("thick", "slow_tan"))
hide("glowlizard-hide", surface="scale", color="#9ad0a0", pieces=SUPPLE,
     # It glows: the light is not modelled (no light vocabulary on an item), the cost to
     # hiding is.
     armour=[gm("max_dex", 2), sk("perception", 2), sk("stealth", -2)],
     working=wk("fast_tan"))
hide("frilled-lizard-hide", surface="scale", color="#8a6a3a", pieces=grip(SUPPLE),
     armour=[sk("intimidate", 2), gm("max_dex", 2), gm("hardness", -2)],
     weapon=GRIP_SLICK, working=wk("forgiving"))
hide("electric-eel-skin", surface="smooth", color="#4a5a6a", pieces=SUPPLE,
     # Eel hide (Ultimate Equipment, prior art §1.3, confirmed §7.1): ACP 1 better (to 0),
     # max Dex +1, electricity resistance 2 for the wearer — the one special leather whose
     # resistance IS the wearer's — always masterwork, leather, hide or studded leather
     # only. House top-up to reach a drawback: a thin skin is softer.
     armour=[B(gm("acp", 1)), B(gm("max_dex", 1)), B(res("electricity", 2)),
             gm("hardness", -2)],
     always_masterwork=True, allowed_bases=["leather", "hide armour", "studded leather"],
     working=wk("fast_tan"),
     text="Eel hide: hagfish-thin strips sewn edge to edge into a sheet that flexes like "
          "skin. By the book a suit of it is always masterwork, lighter on the limbs (check "
          "penalty one better, Dexterity one higher) and turns 2 points of every "
          "lightning strike; it makes only leather, hide or studded leather.")
hide("ankheg-shell-leather", surface="chitin", color="#8a7a4a", pieces=RIGID,
     armour=[cm("ac", 2), res("acid", 2), gm("acp", -2)],
     working=wk("thick"))
hide("snow-leopard-pelt", surface="fur", color="#d6d0c4", pieces=SUPPLE,
     armour=[sk("stealth", 2), sk("climb", 2), gm("hp_per_inch", -2)],
     working=wk("forgiving"))
hide("dire-wolverine-hide", surface="fur", color="#3a2a20", pieces=SUPPLE,
     armour=[sv("will", 2), cm("cmd", 2), gm("weight_pct", 20)],
     working=wk("slow_tan"))
hide("owlbear-hide", surface="fur", color="#6a5038", pieces=SUPPLE,
     armour=[sv("fort", 2), cm("cmb", 2), gm("acp", -2)],
     working=wk("slow_tan"))
hide("griffon-hide", surface="feather", color="#b08a4a", pieces=SUPPLE,
     armour=[sk("handle animal", 2), sk("perception", 2), gm("weight_pct", 20)],
     working=wk("forgiving"))

# ---- rare ------------------------------------------------------------------------------------
hide("shadow-mastiff-hide", surface="fur", color="#1e1c22", pieces=SUPPLE,
     armour=[sk("stealth", 3), sk("perception", 2), sk("diplomacy", -2)],
     working=wk("forgiving"))
hide("salamander-hide", surface="scale", color="#c0502a", pieces=SUPPLE,
     # Immune to fire (rare ceiling 3); DR 10/magic gives DR 2/magic by the owner's rule.
     armour=[res("fire", 3), dr(2, "magic"), gm("acp", -2)],
     working=wk("slow_tan"))
hide("hell-hound-hide", surface="fur", color="#5a2a20", pieces=SUPPLE,
     armour=[res("fire", 3), sk("intimidate", 2), sk("stealth", -2)],
     working=wk("forgiving"))
hide("cave-bear-hide", surface="fur", color="#4a3a2e", pieces=SUPPLE,
     # The old DR 1/— is gone (a cave bear has none in the book).
     armour=[cm("ac", 3), sv("fort", 2), gm("acp", -2)],
     working=wk("thick", "slow_tan"))
hide("sabre-tooth-hide", surface="fur", color="#b08040", pieces=SUPPLE,
     armour=[sk("intimidate", 3), cm("initiative", 2), gm("hp_per_inch", -2)],
     working=wk("forgiving"))
hide("basilisk-hide", surface="scale", color="#6a7058", pieces=grip(SUPPLE),
     armour=[cm("ac", 3), gm("hardness", 2), gm("weight_pct", 30)],
     weapon=GRIP_SCALE, working=wk("slow_tan"))
hide("bulette-plate", surface="shell", color="#7a6a5a", pieces=RIGID,
     # Bulette leather "has the same statistics as studded leather" (Dungeon Denizens
     # Revisited, prior art §1.3): `as_base`, with no metal in it. The old +3 armour-typed
     # AC was invented and is gone. The source's 65 lb bulette PLATE mail (max Dex +2,
     # hardness 12) is not modelled: this is the leather.
     armour=[B({"type": "as_base", "target": "studded leather"}), gm("hardness", 2),
             cm("cmd", 2), gm("acp", -2)],
     working=wk("thick", "slow_tan"),
     text="The bulette's back plates, boiled and laced into a coat. By its source a suit of "
          "bulette leather has the same numbers as studded leather with no metal in it, so "
          "a druid may wear what a smith would otherwise have to stud.")
hide("manticore-hide", surface="smooth", color="#8a5a3a", pieces=SUPPLE,
     armour=[cm("ac", 2), sv("ref", 2), gm("acp", -2)],
     working=wk("flawless"))
hide("chimera-hide", surface="fur", color="#8a6040", pieces=SUPPLE,
     armour=[res("fire", 2), sv("will", 2), gm("weight_pct", 20)],
     working=wk("forgiving"))
hide("remorhaz-hide", surface="chitin", color="#c86a3a", pieces=SUPPLE,
     # Immune to fire; the old cold resistance had no source and is gone.
     armour=[res("fire", 3), cm("ac", 2), gm("acp", -2)],
     working=wk("slow_tan"))
hide("gorgon-hide", surface="scale", color="#6a7a7a", pieces=SUPPLE,
     # "Rings when struck": a noisy hide.
     armour=[cm("ac", 3), sv("fort", 2), sk("stealth", -3)],
     working=wk("slow_tan"))
hide("shadow-girallon-pelt", surface="fur", color="#2a2a30", pieces=SUPPLE,
     armour=[sk("stealth", 3), sk("climb", 2), gm("hp_per_inch", -2)],
     working=wk("forgiving"))
hide("nightmare-hide", surface="smooth", color="#1a1414", pieces=SUPPLE,
     armour=[res("fire", 2), sk("intimidate", 2), sk("diplomacy", -2)],
     working=wk("slow_tan"))

# ---- exotic ----------------------------------------------------------------------------------
hide("wyvern-hide", surface="scale", color="#5a6a4a", pieces=grip(SUPPLE),
     armour=[cm("ac", 3), sv("fort", 2), gm("acp", -2)],
     weapon=GRIP_SCALE, working=wk("slow_tan"))
hide("behir-hide", surface="scale", color="#3a5a8a", pieces=grip(SUPPLE),
     armour=[res("electricity", 3), sk("climb", 2), gm("acp", -2)],
     weapon=[cm("attack", 2), cm("cmb", 2), gm("hardness", -2)], working=wk("forgiving"))
hide("purple-worm-plate", surface="chitin", color="#5a3a6a", pieces=RIGID,
     # The old DR 2 had no source (a purple worm has no DR in the book) and is gone.
     armour=[cm("ac", 3), gm("hardness", 3), gm("acp", -3)],
     working=wk("thick", "slow_tan"))
hide("dragon-turtle-shell", surface="shell", color="#3a5a4a", pieces=RIGID,
     armour=[res("fire", 3), cm("ac", 3), gm("weight_pct", 30)],
     working=wk("thick", "slow_tan"))
hide("couatl-feather-hide", surface="feather", color="#4ab0a0", pieces=SUPPLE,
     # "Cannot be dyed, disguised or mistaken."
     armour=[sv("will", 3), sk("diplomacy", 2), sk("disguise", -3)],
     working=wk("flawless"))
hide("hydra-hide", surface="scale", color="#4a6a3a", pieces=SUPPLE,
     armour=[sv("fort", 3), sk("swim", 2), gm("acp", -2)],
     working=wk("forgiving"))
hide("noble-salamander-hide", surface="scale", color="#d0402a", pieces=SUPPLE,
     # Immune to fire (exotic ceiling 3); DR 15/magic gives DR 3/magic.
     armour=[res("fire", 3), dr(3, "magic"), gm("acp", -3)],
     working=wk("slow_tan"))
hide("phoenix-feather-hide", surface="feather", color="#f08a2a", pieces=SUPPLE,
     # Immune to fire; DR 15/evil gives DR 3/evil. "The feathers ember": it glows.
     armour=[res("fire", 3), dr(3, "evil"), sk("stealth", -3)],
     working=wk("flawless"))
hide("unicorn-hide", surface="fur", color="#f2f0ea", pieces=SUPPLE,
     armour=[sk("heal", 3), sv("fort", 2), sk("diplomacy", -3)],
     working=wk("flawless"))
hide("dragonne-hide", surface="fur", color="#c8a050", pieces=SUPPLE,
     armour=[sk("intimidate", 3), cm("initiative", 2), gm("weight_pct", 20)],
     working=wk("forgiving"))

# ---- legendary -------------------------------------------------------------------------------
hide("tarrasque-plate", surface="shell", color="#5a4a3a", pieces=RIGID,
     # DR 15/epic gives DR 3/epic by the owner's rule; the old DR 3/— is that, typed.
     armour=[cm("ac", 4), dr(3, "epic"), gm("acp", -4)],
     working=wk("thick", "slow_tan"))
hide("kraken-hide", surface="smooth", color="#3a2a4a", pieces=SUPPLE,
     # Immune to cold: legendary's ceiling.
     armour=[res("cold", 4), sk("swim", 3), gm("acp", -2)],
     working=wk("forgiving"))

# ---- the dragonhides (plan §15) --------------------------------------------------------------
#
# Book (Core, Ultimate Equipment; prior art §1.3, the wearer line confirmed verbatim): the
# ARMOUR is immune to the dragon's energy, "although this does not confer any protection to
# the wearer"; energy-resistance enchantments on it cost 25% less; always masterwork; a druid
# may wear it; hardness 10 and 10 hp per inch (leather is 2 and 5, so +8 and +5). House
# top-up, held to the legendary ceiling: resistance 2 for the wearer (PF2e's precedent,
# prior art §1.7), a drawback (the scales' weight), and one positive by colour. Before this
# the 11 entries gave the wearer resistance 5 as if it were the book's rule.

DRAGONS = {
    # colour: (energy, colour hex, the colour's own positive, why)
    "red": ("fire", "#a8281e", sk("intimidate", 3), "the tyrant's scale"),
    "gold": ("fire", "#d4a838", sv("will", 2), "a gift, not a kill"),
    "brass": ("fire", "#c89a48", sk("diplomacy", 3), "the talkative desert dragon"),
    "white": ("cold", "#e4ecf0", sk("survival", 3), "the ice-hunter"),
    "silver": ("cold", "#c8ccd4", sk("sense motive", 3), "the cloud-bright judge"),
    "blue": ("electricity", "#2a58a8", sk("perception", 3), "the desert-storm watcher"),
    "bronze": ("electricity", "#8a6a2a", sk("swim", 3), "the sea-cliff dragon"),
    "black": ("acid", "#1a1a1e", sk("escape artist", 3), "the swamp ambusher"),
    "copper": ("acid", "#b0683a", sk("climb", 3), "the cliff-climbing trickster"),
    "green": ("acid", "#3a6a3a", sk("bluff", 3), "the forest liar"),
    # The umbral dragon is immune to cold (its stat block; the old entry said negative
    # energy, which an object cannot be immune to in the book's list). Its name waits on
    # the bestiary licensing decision (plan §22); its numbers do not.
    "umbral": ("cold", "#2a2433", sk("stealth", 3), "the shadow dragon"),
}

DRAGON_GRIP = [cm("cmd", 2), cm("attack", 2), gm("weight_pct", 20)]


def _dragon(colour: str) -> None:
    energy, hexc, own, why = DRAGONS[colour]
    mid = f"{colour}-dragonhide"
    pieces = grip(SUPPLE)
    doc = {
        "surface": "scale", "color": hexc, "pieces": pieces,
        "armour": [B(oi(energy)),
                   B(gm("enchant_cost_pct", -25, applies_to="energy_resistance")),
                   B(gm("hardness", 8)), B(gm("hp_per_inch", 5)),
                   res(energy, 2), own, gm("weight_pct", 20)],
        "weapon": DRAGON_GRIP,
        "working": wk("thick", "slow_tan"),
        "always_masterwork": True, "druid_permitted": True,
        # The book's "best scales" ladder (banded mail to full plate for smaller wearers)
        # is the forge's, from this hide's scales (plan §15, harvest.scales).
        "forms": None,
        "text": (f"{colour.capitalize()} dragonhide, {why}. By the book the armour itself "
                 f"is immune to {energy} and the wearer is not; energy resistance laid on it "
                 f"later costs a quarter less, it is always masterwork, a druid may wear it, "
                 f"and it is hardness 10. It usually makes hide armour for a wearer one size "
                 f"smaller than the dragon, and its best scales go to the forge."),
    }
    HIDES[mid] = doc


for _c in DRAGONS:
    _dragon(_c)

# ---- new materials (plan §14.3, §14.5, §5.4, §4.4) --------------------------------------------
#
# Full raw entries: these ids are new, so the pass writes every field.

NEW: dict[str, dict] = {}


def new(mid: str, name: str, kind: str, tier: str, **fields) -> None:
    assert mid not in NEW, mid
    NEW[mid] = {"id": mid, "name": name, "kind": kind, "tier": tier, **fields}


new("cowhide", "Cowhide", "hide", "common",
    obtain="bought", price_gp=4, size="large", fresh_hours=48, from_creatures=[],
    text="Plain leather off the farm and the butcher's yard, the tannery's daily bread and "
         "every town's. Firm, even and dull, it takes any method and makes anything, and "
         "it is what a grip is wrapped in when nobody asks for better.")
HIDES["cowhide"] = dict(
    surface="smooth", color="#8b5a3c", pieces=grip(SUPPLE),
    # The forge's leather-grip carried these numbers before the pass (forge plan's house
    # draft); plan §4.4 makes that grip a form of plain leather, so they are plain
    # leather's now, and the grip copies them.
    armour=[cm("ac", 2), gm("acp", 2), gm("weight_pct", 20)],
    weapon=[cm("attack", 2), cm("cmd", 2), gm("hardness", -2)],
    working=wk("forgiving"))

new("sharkskin", "Sharkskin", "hide", "uncommon",
    obtain="harvested", size="medium", fresh_hours=48, from_creatures=["shark"],
    text="Shark hide, rough as a file in one direction and smooth in the other. Untanned "
         "and dried it is shagreen, the grip that never slips wet or bloody; tanned it "
         "makes a hard, abrasive coat that swims well.")
HIDES["sharkskin"] = dict(
    surface="smooth", color="#7a8a8e", pieces=grip(SUPPLE),
    armour=[sk("swim", 2), cm("cmd", 2), gm("acp", -2)],
    # The forge's sharkskin-grip's numbers before the pass, now the hide's.
    weapon=[cm("attack", 2), cm("cmb", 2), gm("hardness", -2)],
    working=wk("forgiving"))

new("ray-skin", "Ray Skin", "hide", "uncommon",
    # No ray in the shipped bestiary, so it comes by trade until a world's coast has one.
    obtain="bought", price_gp=10, size="small", fresh_hours=48, from_creatures=[],
    text="Shagreen proper: a ray's skin, its denticles ground smooth into a pebbled "
         "surface hard as horn. Prized for grips and scabbards, and too stiff for much "
         "else.")
HIDES["ray-skin"] = dict(
    surface="smooth", color="#c9c2b0", pieces=grip(SUPPLE),
    armour=[gm("hardness", 2), sk("swim", 2), gm("max_dex", -2)],
    weapon=[cm("cmd", 2), gm("hardness", 2), cm("damage", -2)],
    working=wk("flawless"))

new("griffon-mane", "Griffon Mane", "hide", "uncommon",
    obtain="harvested", size="large", fresh_hours=48, from_creatures=["griffon"],
    not_yet=["Flight powers added to it later cost 10% less (Ultimate Equipment): no "
             "enchanting cost family for flight exists yet "
             "(effectspec.ENCHANT_COST_FAMILIES)."],
    text="The feathered ruff of a griffon, woven into padded cloth. By the book it gives "
         "its wearer +2 on Fly checks, and it makes only cloaks, robes, padded or quilted "
         "armour; the house adds that the stiff quills turn a blow, at a little weight.")
HIDES["griffon-mane"] = dict(
    surface="feather", color="#c8a060",
    pieces={"armour": ["body", "lining"], "worn": ["body", "lining"]},
    # Book (Ultimate Equipment, prior art §1.3): +2 competence on Fly. House: plan
    # §14.5's "AC +2 on padded, a negative weight +10%", the weight at the floor of 2
    # points (+20%: weight moves in tenths, POINT).
    armour=[B(sk("fly", 2, bonus="competence")), cm("ac", 2), gm("weight_pct", 20)],
    allowed_bases=["padded", "quilted cloth"], working=wk("fast_tan"))

new("angelskin", "Angelskin", "hide", "exotic",
    obtain="harvested", size="medium", fresh_hours=48, from_creatures=["angel"],
    not_yet=["A moderate good aura; the wearer's evil aura counts as 10 Hit Dice weaker; a "
             "20% chance that an effect aimed at evil treats an evil wearer as neutral "
             "(Ultimate Equipment). No alignment-targeted effect exists in the app yet."],
    text="The skin of a celestial, pale and faintly luminous. By the book a suit of it is "
         "always masterwork, hardness 5, makes only leather, hide or studded leather, and "
         "hides its wearer's evil from those who look for it; that last the app does not "
         "yet model. Taking it is a deed the world remembers.")
HIDES["angelskin"] = dict(
    surface="smooth", color="#f4ecdc", pieces=SUPPLE,
    # The forge's angelskin-binding had Will +3, AC +2, Diplomacy -3 presented as the
    # book's; they were invented (questions doc, contradiction 3). Book: hardness 5 (+3 on
    # leather's 2). House: a steadying Will and a calm voice, and it shines.
    armour=[B(gm("hardness", 3)), sv("will", 2), sk("diplomacy", 2), sk("stealth", -2)],
    always_masterwork=True, allowed_bases=["leather", "hide armour", "studded leather"],
    working=wk("flawless"))

new("darkleaf-cloth", "Darkleaf Cloth", "hide", "rare",
    # Not a skin: leaves woven and hardened into cloth (Ultimate Equipment). Filed with the
    # hides because it is the body of a suit and nothing else; it is never green, so it has
    # no freshness window and is sold as the finished sheet.
    obtain="bought", price_gp=375, size="medium", from_creatures=[],
    text="Leaves of the darkleaf tree, pressed and woven into a cloth as tough as hide. By "
         "the book a suit of it is always masterwork, half the weight, lighter on the limbs "
         "(spell failure 10% lower, check penalty 3 better, Dexterity 2 higher) and "
         "hardness 10; it makes padded, leather, studded leather or hide armour. It "
         "crackles faintly when it moves.")
HIDES["darkleaf-cloth"] = dict(
    surface="smooth", color="#2e4a2a", pieces=SUPPLE,
    forms=["leather", "panel", "plate", "lacing", "scrap"],
    # Book (prior art §1.3): ASF -10% (min 5%), max Dex +2, ACP 3 better (min 0), half
    # weight, hardness 10 (+8), 20 hp per inch (+15). Every printed effect is a benefit, so
    # the house drawback the validator asks for: dry leaves crackle.
    armour=[B(gm("asf", -10)), B(gm("max_dex", 2)), B(gm("acp", 3)),
            B(gm("weight_pct", -50)), B(gm("hardness", 8)), B(gm("hp_per_inch", 15)),
            sk("stealth", -2)],
    always_masterwork=True,
    allowed_bases=["padded", "leather", "studded leather", "hide armour"],
    working=wk("forgiving"))

# Lane C's generic hides (plan §5.4): one document per surface, each with its own house
# modifiers. What makes a beast's generic hide its own (its energy resistance, its reduced
# DR, its tier from CR, `thick` from natural armour +5) is read from the stat block at
# harvest by lane C and never stored here as a number (the brief, 2026-10-08).
GENERIC = {
    "fur": ("generic-fur-hide", "Fur Hide", "#8a7458", SUPPLE,
            [sv("fort", 2), sk("survival", 2), gm("weight_pct", 20)], wk("forgiving")),
    "scale": ("generic-scale-hide", "Scaled Hide", "#6a7050", SUPPLE,
              [cm("ac", 2), gm("hardness", 2), gm("max_dex", -2)], wk("slow_tan")),
    "smooth": ("generic-smooth-hide", "Smooth Hide", "#a07a52", SUPPLE,
               [gm("acp", 2), gm("hp_per_inch", 2), gm("hardness", -2)], wk("forgiving")),
    "feather": ("generic-feather-hide", "Feathered Hide", "#b0a080", SUPPLE,
                [gm("weight_pct", -20), sk("acrobatics", 2), gm("hp_per_inch", -2)],
                wk("fast_tan")),
    "chitin": ("generic-chitin", "Chitin Plates", "#5a4a2a", RIGID,
               [cm("ac", 2), gm("weight_pct", -20), gm("acp", -2)], wk("slow_tan")),
    "shell": ("generic-shell", "Shell Plates", "#7a6a50", RIGID,
              [cm("ac", 2), gm("hardness", 2), gm("weight_pct", 20)], wk("slow_tan")),
}
for _surface, (_gid, _gname, _hex, _pieces, _armour, _working) in GENERIC.items():
    new(_gid, _gname, "hide", "common", obtain="harvested", size="medium", fresh_hours=48,
        from_creatures=[],
        text=f"A {_gname.lower()} off a beast the catalogue has no name for. What the "
             f"creature was decides the rest: its tier from how dangerous it was, and any "
             f"resistance or damage reduction it had, read from it when it is skinned.")
    HIDES[_gid] = dict(surface=_surface, color=_hex, pieces=_pieces, armour=_armour,
                       working=_working)

new("bone-studs", "Bone Studs", "fitting", "common",
    obtain="bought", price_gp=5,
    text="Studs of boiled and shaped bone, the book's primitive material. On studded "
         "leather they give 1 less AC than metal and 1 less check penalty, and there is no "
         "metal in them, so a druid may wear the suit.")
FITTINGS_NEW = {
    "bone-studs": dict(
        surface="smooth", color="#e8dcc0",
        pieces={"armour": ["fastenings"], "shield": ["fastenings"]},
        # Book (Ultimate Equipment, primitive bone, prior art §1.3): armour bonus -1; on
        # studded leather ACP 1 better (to 0); hardness 5 (+3 on leather's 2). The build
        # reads book effects from the main piece only (forge_items.build), and studs are
        # fastenings: lane B or H must apply these for a studded suit whose studs are bone
        # (docs/leatherworking-review.md, "asks of other lanes").
        armour=[B(cm("ac", -1)), B(gm("acp", 1)), B(gm("hardness", 3))],
        working=wk("forgiving")),
}

# --- the shipped fittings: forms of the forge's metals ------------------------------------------
#
# Eight leatherworker fittings already link to a forge metal (forge pass LINKS). A form
# carries what it is made of: its armour list is its parent's, copied at run time from the
# forge file so the two cannot drift, and the validator refuses a difference.

FITTING_COLOURS = {
    "iron-buckle": "#5a5a5e", "brass-buckle": "#c8a040", "steel-studs": "#9aa0a8",
    "bronze-rings": "#a8743a", "silver-clasps": "#d0d4d8", "cold-iron-studs": "#4a4e58",
    "mithral-fittings": "#e0e8f0", "adamantine-buckles": "#2a2a30",
}
FITTING_PIECES = {"armour": ["fastenings"], "shield": ["fastenings"]}

# --- the consumables -----------------------------------------------------------------------------
#
# Working traits only (the owner, Q3.2, with marks held). Each trait is one the leather
# vocabulary means (effectspec.LEATHER_TRAITS); none is given that is not true of the thing,
# so a dye is fast or fugitive and usually nothing else (materials.CONSUMABLE_PROPERTIES).
# `price` is set where a counter sells it and the shelf had none; every price sits on or above
# `pricing.MATERIAL_FLOOR_GP`.

CONSUMABLES: dict[str, dict] = {}


def con(mid: str, color: str, *traits, **fields) -> None:
    assert mid not in CONSUMABLES, mid
    CONSUMABLES[mid] = dict(color=color, working=wk(*traits), **fields)


# Tannins (plan §8.1): the tannage decides the wait and whether the leather hardens.
con("oak-bark", "#7a4a26", "forgiving", "slow_tan", "ceiling_up", tannage="bark")
con("sumac-leaf", "#a83a2a", "tans_white", "fast_tan", "flawless", tannage="bark")
con("hemlock-bark", "#8a3a22", "fast_tan", "ceiling_down", "forgiving", tannage="bark")
con("willow-bark", "#9a8a5a", "ceiling_down", "slow_tan", "tans_white", tannage="bark")
con("tara-pod", "#c8a86a", "ceiling_up", "tans_white", "fast_tan", tannage="bark")
con("bog-liquor", "#3a2a1a", "slow_tan", "salt_proof", "forgiving", tannage="bark",
    price=5)
con("mangrove-bark", "#6a2a1a", "salt_proof", "fast_tan", "ceiling_down", tannage="bark",
    price=5)
con("ironbark-tannin", "#4a3a2a", "ceiling_up", "slow_tan", "flawless", tannage="bark")
con("wyrm-gall", "#6a7a2a", "fast_tan", "ceiling_up", "forgiving", tannage="planar")
con("salamander-ash-lye", "#8a8a8a", "fast_tan", "salt_proof", "flawless",
    tannage="mineral")
con("styx-mordant", "#1a2a3a", "slow_tan", "ceiling_up", "salt_proof", tannage="planar")
con("dragonblood-tannin", "#7a1a1a", "ceiling_up", "flawless", "slow_tan",
    tannage="planar")
# The field tans, filed as treatments before the pass. Plan §8.1 names them as the brain and
# alum tannins; their kind follows, so the tannage field (tannins only) can say so.
con("brain-paste", "#d8c8b0", "tans_white", "forgiving", "fast_tan", tannage="brain",
    kind="tannin")
con("tawing-alum", "#f0f0ec", "tans_white", "ceiling_down", "forgiving", tannage="alum",
    kind="tannin")
# Oils.
con("neatsfoot-oil", "#d8b860", "supple", "forgiving")
con("currier-tallow", "#e8dcb0", "rancid", "forgiving")
con("fish-oil", "#b8a060", "supple", "rancid")
con("mink-oil", "#c8a870", "supple", "flawless", price=5)
con("troll-fat", "#6a7a4a", "rancid")
con("salamander-oil", "#c86a2a", "supple")
con("wyvern-fat", "#a89a6a", "supple", "flawless")
con("umbral-oil", "#1a1820", "supple")
# Waxes.
con("thread-wax", "#e0c880", "strong_seam", "weatherproof", "forgiving")
con("seam-pitch", "#2a2018", "weatherproof", "strong_seam")
con("hardening-wax", "#d8c070", "fills_tooling", "forgiving")
con("fireproof-wax", "#b8b0a0", "fills_tooling")
con("ghost-wax", "#e8eef0", "fills_tooling", "flawless")
# Threads.
con("linen-thread", "#e8e0c8", "forgiving", "fine_pitch")
con("sinew-thread", "#c8b890", "weatherproof", "strong_seam")
con("gut-cord", "#d8c8a0", "forgiving")
con("horsehair-cord", "#3a3028", "strong_seam")
con("waxed-flax", "#d8c890", "weatherproof", "strong_seam", "forgiving")
con("silk-thread", "#f4f0e8", "fine_pitch", "flawless")
con("spider-silk-cord", "#e8e8e8", "strong_seam", "fine_pitch")
con("wire-silk", "#b8bcc0", "strong_seam", "flawless")
con("shadow-silk", "#2a2830", "fine_pitch")
con("wyvern-sinew", "#a89a70", "strong_seam", "weatherproof")
con("dragon-sinew", "#8a3a2a", "strong_seam", "weatherproof", "flawless")
# Dyes. Substantive (vat, tannin and iron) dyes are fast without a mordant; adjective ones
# (madder, weld) need one or they run.
con("madder-red", "#a82a2a", "fugitive", price=1)
con("weld-yellow", "#d8c040", "fugitive", price=1)
con("woad-blue", "#2a4a8a", "fast_colour", price=1)
con("walnut-brown", "#5a3a20", "fast_colour", "forgiving", price=1)
con("iron-gall-black", "#1a1a20", "fast_colour", price=1)
con("murex-purple", "#6a1a5a", "fast_colour", "flawless")
con("vermilion", "#d83a2a", "fugitive")
con("glowcap-green", "#6ad08a", "fugitive")
con("shadow-black", "#0e0e12", "fast_colour")
con("dragons-blood-crimson", "#8a1a1a", "fugitive")
con("moonlight-silver", "#c8d0e0", "fast_colour")
con("void-dye", "#050508", "fast_colour")
# Treatments.
con("curing-salt", "#f0ece4", "forgiving", salt=True)
con("liming-quicklime", "#e8e8e0", "forgiving")
# Dye sets a fast colour with the mordant (plan §7), so the counter sells it.
con("mordant-salts", "#d8d0e0", "fast_colour", price=5)
con("planar-quench", "#6a5a8a", "forgiving")

# --- the marks the owner holds (plan §14.6; not read by anything) ------------------------------
#
# Each is the old typed effect the consumable carried in `effects` (which the old chain bench
# laid on every finished item, plan §14.1's measured leak) or the plan's proposal. Kept whole
# so the owner's ruling can enable or delete them in one place.

MARKS_ON_HOLD: dict[str, dict] = {
    "salamander-oil": res("fire", 1),
    "fireproof-wax": res("fire", 1),
    "troll-fat": gm("hardness", 1),
    "spider-silk-cord": gm("hardness", 1),
    "shadow-silk": sk("stealth", 1, bonus="circumstance"),
    "shadow-black": sk("stealth", 1, bonus="circumstance"),
    "void-dye": sk("stealth", 2, bonus="circumstance"),
    "umbral-oil": sk("stealth", 1, bonus="circumstance"),
    "styx-mordant": cm("damage", 1, when={"target": {"type": "outsider"}}),
}

# --- the forge's four leather pieces (plan §4.4) -----------------------------------------------
#
# Forms of leatherworker materials now (one material, many shelves): each carries its
# parent's list for the gear it fills, so a grip wrapped from sharkskin is sharkskin. Their
# forge working traits stay (the forge's Assemble fits them), as do their ids, names, kinds,
# tiers and legacy `effects`.

FORGE_FORMS = {
    "leather-grip": dict(
        material="cowhide", lists=("weapon", "armour"),
        text="Wet-wrapped cowhide that dries to the shape of the hand: plain leather, cut "
             "as a grip or a lining. As a grip it holds true and hard to wrest away; as a "
             "lining it turns blows and eases movement at the cost of weight."),
    "sharkskin-grip": dict(
        material="sharkskin", lists=("weapon",),
        text="Sharkskin cut and wrapped over the tang. It never slips, wet, bloody or "
             "otherwise, so the swing and the grab are both surer; a hide grip is softer "
             "than bone."),
    "dragonhide-grip": dict(
        material="red-dragonhide", lists=("weapon",),
        text="Red dragonhide, supple where scale meets scale, wrapped as a grip. It holds "
             "the weapon fast and true and weighs a little. The book's dragonhide powers "
             "are for armour and shields; on a hilt it is a fine grip and nothing more."),
    "angelskin-binding": dict(
        material="angelskin", lists=("armour",),
        text="Angelskin cut as a lining. It steadies the wearer and calms their voice, and "
             "it shines. The book's angelskin is the suit itself, always masterwork, and "
             "dims an evil aura, which the app does not yet model; as a lining it carries "
             "only the house numbers."),
}

# Iron and its alloys: what rusting grasp eats (contracts §6.2, plan §18.5). Read from the
# shelf's own texts: iron, wrought and cold iron, meteoric star-iron, and every steel. Not
# inubrix ("ghost iron" is a skymetal that cannot damage iron), not abysium (it "works as
# steel" and is not), not wyrmsteel (adamantine folded with dragonfire).
FERROUS = ("iron", "wrought-iron", "cold-iron", "star-iron", "steel", "high-carbon-steel",
           "pattern-steel", "nexavaran-steel", "living-steel", "fire-forged-steel",
           "frost-forged-steel")

NOTE = ("Tier follows the worldclass ladder (a deer is common work, a dragon legendary). "
        "The leather bench reads `pieces`, `armour`, `weapon` (grip-capable hides only), "
        "`working`, `surface`, `color`, `allowed_bases`, `always_masterwork`, "
        "`druid_permitted`, `tannage`, `salt` and `sold_as` through rules/materials.py "
        "(docs/leatherworking-contracts.md §3); effects marked \"book\": true are printed "
        "PF1e rules, applied from the main piece only and never scaled, and every other "
        "number is a house modifier for the owner's review (docs/leatherworking-review.md, "
        "written by tools/leather_review.py from this file). `price_gp` on a hide is the "
        "price of the form it is sold in (`sold_as`). `effects` is the pre-revamp flat list "
        "the old chain bench still reads until its replacement lands: its narrative lines "
        "are gone and a consumable's is empty. `from_creatures` is the old name-fragment "
        "join, superseded by harvest tags on the creature (leather lane C). "
        "`marks_on_hold` is the consumables' proposed marks, held by the owner's ruling of "
        "2026-10-08 and read by nothing.")

# The fields this pass owns on a leather entry; everything else is passed through.
LEATHER_FIELDS = ("pieces", "armour", "weapon", "shield", "working", "surface", "color",
                  "allowed_bases", "always_masterwork", "druid_permitted", "book", "tannage",
                  "salt", "sold_as", "forms", "not_yet", "mark")


def _legacy(raw: dict, mid: str) -> list[dict]:
    """The old flat `effects` the chain bench reads, cleaned: no narrative anywhere (the
    measured 96 of 171), nothing at all on a consumable (its prose was laid on every finished
    item, plan §14.1), the dragonhides' wearer resistance cut to the house 2, and bulette's
    invented armour bonus gone."""
    kind = (CONSUMABLES.get(mid) or {}).get("kind") or raw.get("kind")
    if kind in materials.LEATHER_CONSUMABLES:
        return []
    if mid == "bulette-plate":
        return []
    if mid.endswith("-dragonhide"):
        energy = DRAGONS[mid.removesuffix("-dragonhide")][0]
        return [{"type": "resistance", "target": energy, "amount": 2}]
    return [dict(e) for e in raw.get("effects") or [] if e.get("type") != "narrative"]


def _hide_fields(mid: str, spec: dict) -> dict:
    out: dict = {}
    out["pieces"] = copy.deepcopy(spec["pieces"])
    out["armour"] = copy.deepcopy(spec["armour"])
    if spec.get("weapon"):
        out["weapon"] = copy.deepcopy(spec["weapon"])
    out["working"] = copy.deepcopy(spec["working"])
    out["surface"] = spec["surface"]
    out["color"] = spec["color"]
    for k in ("allowed_bases", "always_masterwork", "druid_permitted", "not_yet"):
        value = spec.get(k) or (NEW.get(mid) or {}).get(k)
        if value:
            out[k] = copy.deepcopy(value)
    book = any(e.get("book") for g in ("armour", "weapon") for e in out.get(g) or [])
    if book:
        out["book"] = True
    probe = materials.normalise({"id": mid, "kind": "hide", **out},
                                materials.LEATHER_CATALOGUE)
    if mid.endswith("-dragonhide"):
        out["forms"] = materials.hide_forms(probe) + ["scales"]
    elif spec.get("forms"):
        out["forms"] = list(spec["forms"])
    out["sold_as"] = "fur" if spec["surface"] in ("fur", "feather") else "leather"
    if mid.endswith("-dragonhide"):
        out["sold_as"] = "leather"
    return out


def build_leather(raw: dict, forge_by_id: dict[str, dict]) -> dict:
    """One leather entry with this pass's fields written over it; identity untouched."""
    mid = raw["id"]
    out = {k: v for k, v in raw.items() if k not in LEATHER_FIELDS}
    out["effects"] = _legacy(raw, mid)
    if mid in HIDES:
        spec = HIDES[mid]
        out.update(_hide_fields(mid, spec))
        if spec.get("text"):
            out["text"] = spec["text"]
        if spec.get("price") is not None:
            out["price_gp"] = spec["price"]
    elif mid in CONSUMABLES:
        spec = CONSUMABLES[mid]
        if spec.get("kind"):
            out["kind"] = spec["kind"]
        out["working"] = copy.deepcopy(spec["working"])
        out["color"] = spec["color"]
        if spec.get("tannage"):
            out["tannage"] = spec["tannage"]
        if spec.get("salt"):
            out["salt"] = True
        if spec.get("price") is not None:
            out["price_gp"] = spec["price"]
        if ENABLE_MARKS and mid in MARKS_ON_HOLD:
            out["mark"] = copy.deepcopy(MARKS_ON_HOLD[mid])
    elif mid in FITTINGS_NEW:
        spec = FITTINGS_NEW[mid]
        out.update({k: copy.deepcopy(v) for k, v in spec.items()})
        if any(e.get("book") for e in spec["armour"]):
            out["book"] = True
    elif raw.get("kind") == "fitting" and raw.get("material") in forge_by_id:
        parent = forge_by_id[raw["material"]]
        out["pieces"] = copy.deepcopy(FITTING_PIECES)
        out["armour"] = copy.deepcopy(parent.get("armour") or [])
        out["surface"] = "smooth"
        out["color"] = FITTING_COLOURS[mid]
        if any(e.get("book") for e in out["armour"]):
            out["book"] = True
    else:
        raise SystemExit(f"{mid}: no row in the pass")
    return _ordered(out)


# Field order in the written file: identity first, the pass's fields next, the old fields
# last, so a reader of the JSON sees what a material is before what it was.
_ORDER = ("id", "name", "kind", "tier", "material", "text", "surface", "color", "pieces",
          "armour", "weapon", "shield", "working", "book", "always_masterwork",
          "druid_permitted", "allowed_bases", "not_yet", "tannage", "salt", "mark",
          "sold_as", "forms", "price_gp", "obtain", "biomes", "size", "fresh_hours",
          "from_creatures", "craft_dc", "risky", "forageable", "source", "effects",
          "effects_converted")


def _ordered(entry: dict) -> dict:
    out = {k: entry[k] for k in _ORDER if k in entry}
    out.update({k: v for k, v in entry.items() if k not in out})
    return out


def build_new(mid: str) -> dict:
    raw = dict(NEW[mid])
    raw.setdefault("craft_dc", None)
    raw.setdefault("risky", False)
    raw.setdefault("forageable", False)
    raw.setdefault("source", {"bought": "bought", "harvested": "skinned"}
                   .get(raw.get("obtain"), raw.get("obtain")))
    raw.setdefault("effects", [])
    return raw


def forge_form(mid: str, leather_by_id: dict[str, dict]) -> dict:
    """The fields of one of the forge's four leather pieces: its parent link and the
    parent's list for each gear it fills. Called by this pass, and by tools/forge_data_pass.py
    so a re-run of the forge's pass writes the same thing rather than reverting it."""
    spec = FORGE_FORMS[mid]
    parent = leather_by_id[spec["material"]]
    out = {"material": spec["material"], "text": spec["text"]}
    for gear in spec["lists"]:
        out[gear] = copy.deepcopy(parent.get(gear) or [])
    return out


def leather_parents() -> dict[str, dict]:
    """The leather documents the forge's forms copy, as this pass writes them (so the forge
    pass gets the same lists whether or not this pass has been applied yet)."""
    out = {}
    for spec in FORGE_FORMS.values():
        mid = spec["material"]
        base = {"id": mid, "kind": "hide"}
        out[mid] = {**base, **_hide_fields(mid, HIDES[mid])}
    return out


def main() -> int:
    apply = "--apply" in sys.argv
    data = json.loads(LEATHER_FILE.read_text(encoding="utf-8"))
    forge = json.loads(FORGE_FILE.read_text(encoding="utf-8"))
    forge_by_id = {m["id"]: m for m in forge["materials"]}

    raws = data["materials"]
    ids = [r["id"] for r in raws]
    known = set(HIDES) | set(CONSUMABLES) | set(FITTINGS_NEW) | {
        r["id"] for r in raws if r.get("kind") == "fitting" and r.get("material")}
    missing = [i for i in ids if i not in known]
    if missing:
        print(f"no row in the pass for {missing}")
        return 1
    for mid in NEW:
        if mid in ids:
            continue
    new_ids = [m for m in NEW if m not in ids]

    out = [build_leather(r, forge_by_id) for r in raws]
    for mid in new_ids:
        out.append(build_leather(build_new(mid), forge_by_id))
    for before, after in zip(raws, out):
        for k in ("id", "name", "tier"):
            assert before[k] == after[k], (before["id"], k)

    # The forge's side: its four leather pieces and ferrous.
    parents = {d["id"]: d for d in out}
    forge_new = []
    for m in forge["materials"]:
        m = dict(m)
        if m["id"] in FORGE_FORMS:
            # Replaced in place (dict order kept), so the diff is the numbers that changed;
            # a new link goes after the id, where the forge pass writes links.
            new_link = "material" not in m
            m.update(forge_form(m["id"], parents))
            m["book"] = any(e.get("book") for g in ("weapon", "armour")
                            for e in m.get(g) or [])
            if new_link:
                _forge_order(m)
        if m["id"] in FERROUS:
            m["ferrous"] = True
        else:
            m.pop("ferrous", None)
        forge_new.append(m)

    # Validate against the shelf as it will be.
    shelf = {d["id"]: materials.normalise(d, materials.LEATHER_CATALOGUE) for d in out}
    for m in forge_new:
        shelf[m["id"]] = materials.normalise(m, materials.FORGE_CATALOGUE)
    for stem in ("alchemist-materials", "enchanter-materials"):
        other = json.loads((MAT_DIR / f"{stem}.json").read_text(encoding="utf-8"))
        for m in other["materials"]:
            shelf.setdefault(m["id"], materials.normalise(m, stem))
    problems = []
    for d in out:
        problems.extend(materials.validate(shelf[d["id"]], shelf=shelf))
    for m in forge_new:
        problems.extend(materials.validate(shelf[m["id"]], shelf=shelf))
    from rules import effectspec, pricing

    for mid, mark in MARKS_ON_HOLD.items():
        if mid not in shelf:
            problems.append(f"marks_on_hold: {mid} is no material")
        problems.extend(effectspec.leather_effect_problems(mark, f"marks_on_hold {mid}"))
    problems.extend(pricing.material_price_problems(out, "leatherworker-materials.json"))
    problems.extend(pricing.material_price_problems(forge_new, "blacksmith-materials.json"))
    if problems:
        print(f"{len(problems)} problem(s); nothing written:")
        for p in problems:
            print("  " + p)
        return 1

    by_kind: dict[str, int] = {}
    for d in out:
        by_kind[d["kind"]] = by_kind.get(d["kind"], 0) + 1
    print(f"{len(out)} leather materials valid ({len(new_ids)} new); by kind {by_kind}")
    if not apply:
        print("dry run: pass --apply to write")
        return 0

    data["note"] = NOTE
    data["materials"] = out
    data["marks_on_hold"] = {
        "_note": ("The owner's ruling of 2026-10-08 holds marks until explained: each row is "
                  "the one small effect plan §14.6 proposes the consumable leaves on a "
                  "finished item. Nothing reads this block. To enable: set ENABLE_MARKS in "
                  "tools/leather_data_pass.py and materials.MARKS_HELD to False, and re-run "
                  "the pass. To delete: remove MARKS_ON_HOLD there and re-run."),
        **{k: v for k, v in MARKS_ON_HOLD.items()},
    }
    LEATHER_FILE.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n",
                            encoding="utf-8")
    forge["materials"] = forge_new
    FORGE_FILE.write_text(json.dumps(forge, indent=1, ensure_ascii=False) + "\n",
                          encoding="utf-8")
    print("written")
    return 0


def _forge_order(m: dict) -> None:
    """Keep a forge entry's keys in the forge pass's order after the update (material after
    id), so the diff is the fields that changed."""
    keys = list(m)
    if "material" in keys:
        keys.remove("material")
        keys.insert(keys.index("id") + 1, "material")
    snapshot = dict(m)
    m.clear()
    for k in keys:
        m[k] = snapshot[k]


if __name__ == "__main__":
    raise SystemExit(main())
