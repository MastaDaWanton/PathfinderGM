"""The blacksmithing data pass (docs/blacksmithing-revamp-plan.md §5.8), as a record.

What it writes into `content/materials/blacksmith-materials.json`, entry by entry: the
pieces each material fills, its weapon and armour effects, its working traits, a
quenchant's mark, an ore's link to its metal, and a `text` rewritten to say what the
material does in the app. It also writes the "one material, many shelves" links into the
alchemist, enchanter and leatherworker files (`"material": "<parent>"`).

Two kinds of number, kept apart on purpose:

- **Book** effects, `B(...)`, transcribed by hand from docs/blacksmithing-prior-art.md
  §1.3, §1.4 and §5.2 (and the weapon blanch, Ultimate Equipment 103 / PFS Field Guide 48,
  checked on aonprd.com 2026-10-03 because the sweep missed it). No model authors these.
  tests/test_forge_materials.py states the same table independently and compares.
- **House** effects, everything else: drafted inside the validator's fences (types,
  targets, ±2 base, tier ceilings, a drawback in every list) for the owner to review as
  a table (docs/blacksmithing-review.md, written by tools/forge_review.py).

Every entry is run through `rules.materials.validate` before anything is written, and
the run refuses to write if any entry has a problem. Dry run by default.

    python tools/forge_data_pass.py            # validate and report
    python tools/forge_data_pass.py --apply    # validate, then write the files

Re-running is idempotent: the forge fields are replaced, never appended, and ids, names,
kinds and tiers are never touched (tests/test_blacksmith.py pins them).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

from rules import materials  # noqa: E402

MAT_DIR = ROOT / "content" / "materials"

# --- notation -------------------------------------------------------------------------------
#
# Short constructors so the table below reads as a table. Each returns a plain effect
# document in rules/effectspec.py vocabulary.


def _with(spec: dict, kw: dict) -> dict:
    for k, v in kw.items():
        if v is not None:
            spec[k] = v
    return spec


def cm(target, n, bonus="material", **kw):
    """A combat modifier: attack, damage, ac, cmb, cmd, initiative."""
    return _with({"type": "combat_mod", "target": target, "amount": n,
                  "bonus_type": bonus}, kw)


def sv(save, n, bonus="material", **kw):
    return _with({"type": "save_mod", "target": save, "amount": n, "bonus_type": bonus}, kw)


def sk(skill, n, bonus="material", **kw):
    return _with({"type": "skill_mod", "target": skill, "amount": n,
                  "bonus_type": bonus}, kw)


def gm(target, n, **kw):
    """The item's own number. Added to the armour table's value: acp is stored negative,
    so +3 is lighter and -2 heavier; asf is a percentage, so -10 is better."""
    return _with({"type": "gear_mod", "target": target, "amount": n}, kw)


def sa(target, **kw):
    return _with({"type": "strikes_as", "target": target}, kw)


def res(energy, n, **kw):
    return _with({"type": "resistance", "target": energy, "amount": n}, kw)


def dr(n, bypass="", **kw):
    return _with({"type": "damage_reduction", "amount": n, "bypass": bypass}, kw)


def B(spec: dict) -> dict:
    """A printed PF1e rule: applied from the main piece only and never scaled."""
    spec["book"] = True
    return spec


def wk(*traits) -> list[dict]:
    return [{"type": "working", "trait": t} for t in traits]


def vs(ctype) -> dict:
    """`when` the struck creature is of a type (contract §2's new clause)."""
    return {"target": {"type": ctype}}


def vs_sub(subtype) -> dict:
    return {"target": {"subtype": subtype}}


def by_weight(weight) -> dict:
    """`when` the base armour is of this weight class: adamantine's DR 1/2/3 and
    horacalcum's initiative +1/+2/+3 are printed per class, and the build knows the base."""
    return {"armour": {"weight": weight}}


PER_DAY = {"uses": "per_day", "uses_count": 1}
ALWAYS = {"unit": "permanent"}

# --- the table ------------------------------------------------------------------------------
#
# id -> fields. `text` is the rewritten description. `legacy` replaces the old flat
# `effects` list where it contradicted the book (rules/blacksmith.py still reads it).

W_HS = ["head", "fittings"]
A_BF = ["body", "fastenings"]

ENTRIES: dict[str, dict] = {}


def entry(mid: str, **fields) -> None:
    assert mid not in ENTRIES, mid
    ENTRIES[mid] = fields


# ---- ores: each smelts to its metal, and is assayed for it ----------------------------------

entry("iron-ore", material="iron", working=wk("forgiving"),
      text="Red-brown haematite, the commonest ore worth carting. It smelts to iron, and "
           "assaying a lump tells you what iron will do; the melt is wide and patient.")
entry("bog-iron", material="wrought-iron", working=wk("slaggy"),
      text="Lumps of ore raked out of marsh beds. Cheap and everywhere, and it smelts to "
           "soft wrought iron, but full of slag: work from it cannot reach its best until "
           "the melt is fluxed clean or the bar is folded.")
entry("copper-ore", material="copper", working=wk("easily_worked"),
      text="Green malachite and blue azurite, smelting quickly to copper, the first metal "
           "anyone ever worked. Soft alone; the better half of bronze.")
entry("tin-ore", material="tin", working=wk("easily_worked"),
      text="Heavy black cassiterite from stream gravels. It smelts fast to tin, worth more "
           "than its weight suggests: without tin there is no bronze.")
entry("lead-ore", material="lead", working=wk("easily_worked", "malleable"),
      text="Glittering cubic galena, so heavy a sack of it staggers a mule. Smelts low and "
           "easy to lead, and a botched melt costs nothing but the fire.")
entry("calamine", material="zinc", working=wk("narrow_window"),
      text="Dull zinc earth. It smelts to zinc only in a tight band of heat before the "
           "metal boils off; most smiths heap it in with copper and take brass instead.")
entry("cinnabar-ore", material="quicksilver", working=wk("reactive", "narrow_window"),
      text="Blood-red mercury ore. Roasting it drives off quicksilver as an invisible "
           "vapour, so assaying it is dangerous, and the roast must be caught in a narrow "
           "band or the metal is lost to the air.")
entry("silver-ore", material="silver", working=wk("slaggy"),
      text="Dark sulphide ore threaded with native wire silver. It smelts to silver "
           "carrying dross that a bone-ash cupel or a fold has to take out.")
entry("gold-ore", material="gold", working=wk("pure", "malleable"),
      text="Quartz veined with visible gold, or dust panned from river gravel. It smelts "
           "clean to gold, and a smelt of it is very hard to spoil.")
entry("nickel-ore", feeds=["alloy"], working=wk("slaggy", "narrow_window", "weld_aid"),
      text="Kupfernickel, 'devil's copper', named by miners it disappointed. It gives no "
           "metal a smith can forge alone; it feeds an alloy, where it makes a weld take "
           "more easily, after a dirty and finicky smelt.")
entry("cold-iron-ore", material="cold-iron", working=wk("narrow_window"),
      text="Iron mined deep underground, never touched by the sun. It smelts to cold iron "
           "only at a lower heat than common iron, in a narrow band that forgives no "
           "shortcuts.")
entry("platinum-ore", material="platinum", working=wk("narrow_window", "pure"),
      text="Grey grains heavier than gold that shrug off every acid in the alchemist's "
           "cabinet. It smelts to platinum only at furnace heat few smithies reach, and "
           "comes out pure when it does.")
entry("mithral-ore", material="mithral", working=wk("forgiving"),
      text="Silvery ore light enough to surprise the hand that lifts it. It smelts to "
           "mithral, and the book says it is worked like steel: the heat is forgiving.")
entry("adamantine-ore", material="adamantine", working=wk("narrow_window"),
      text="Night-black metal found only in the hearts of fallen stars and the deepest "
           "delvings. It smelts to adamantine in a narrow band of white heat that only a "
           "rare fuel reaches.")
entry("abysium-ore", material="abysium", working=wk("reactive"),
      text="A skymetal ore that glows blue-green in the dark and warms the hand that holds "
           "it. It smelts to abysium, and it sickens whoever carries it: assaying it is "
           "genuinely dangerous.")
entry("djezet-ore", material="djezet", working=wk("malleable"),
      text="Rust-red skymetal that is liquid at every temperature, collected drop by drop "
           "where it seeps from volcanic rock. Carried in wax-stoppered vials; nothing a "
           "smith does to it can ruin it.")
entry("inubrix-ore", material="inubrix", working=wk("malleable"),
      text="The ghost iron. Seams of it are found threaded through iron deposits they have "
           "visibly sunk through. It smelts to inubrix, only slightly less malleable than "
           "lead.")
entry("noqual-ore", material="noqual", working=wk("forgiving"),
      text="Pale green skymetal crystal, found in crater rims. Detect magic slides off a "
           "nugget of it as though there were nothing there. It smelts to noqual, which "
           "the book says is worked as iron.")
entry("siccatite-ore", material="siccatite", working=wk("reactive"),
      text="A skymetal that comes out of the ground either searing hot or freezing cold "
           "and never changes its mind. It smelts to siccatite, and assaying it burns.")
entry("horacalcum-ore", material="horacalcum", working=wk("narrow_window"),
      text="The rarest skymetal: a dull coppery ore around which time runs a half-step "
           "slow. It smelts to horacalcum in the narrowest band of any ore.")

# ---- metals ---------------------------------------------------------------------------------

entry("iron", pieces={"weapon": W_HS, "armour": A_BF},
      weapon=[cm("damage", 2), cm("attack", -2), gm("hardness", 2)],
      armour=[cm("ac", 2), gm("acp", -2), gm("hardness", 2)],
      working=wk("forgiving"),
      text="Bar iron, the smith's daily bread, and heavy with it. An iron head hits harder "
           "and swings slower, and iron plate turns more blows and stiffens the wearer; "
           "either way the piece is harder to break. Its heat band is wide and forgiving.")
entry("wrought-iron", pieces={"weapon": W_HS, "armour": A_BF},
      weapon=[gm("hp_per_inch", 2), cm("cmd", 2), cm("damage", -2)],
      armour=[gm("hp_per_inch", 2), gm("max_dex", 2), gm("hardness", -2)],
      working=wk("malleable", "forgiving"),
      text="Iron worked soft and fibrous, with the slag hammered into threads. It bends "
           "before it breaks: a wrought head is tough and hard to wrest away but cuts "
           "softly, and wrought mail moves with the wearer at the cost of hardness. Very "
           "hard to ruin at the anvil.")
entry("bismuth", feeds=["alloy"], working=wk("easily_worked", "brittle", "weld_aid"),
      text="A brittle white metal that cools into staircase crystals sheened like oil on "
           "water. Useless for an edge and fills no piece; alloyers melt it in for pours "
           "that must run thin, and it helps a weld take.")
entry("copper", pieces={"weapon": W_HS, "armour": A_BF},
      weapon=[cm("attack", 2), gm("hp_per_inch", 2), cm("damage", -2)],
      armour=[B(gm("hardness", -1, note="primitive bronze, copper or tin armour: hardness 9")),
              gm("max_dex", 2), gm("hp_per_inch", 2), cm("ac", -2)],
      working=wk("easily_worked"),
      text="Warm red metal that works cold and greens with age. A copper head swings true "
           "and will not shatter, but cuts softly; copper armour is supple and tough and "
           "turns fewer blows, with the book's hardness of 9. In the book a copper weapon "
           "is fragile, which this app does not yet model.")
entry("tin", pieces={"weapon": ["fittings"], "armour": ["fastenings"]},
      weapon=[gm("weight_pct", -20), cm("initiative", 2), gm("hardness", -2)],
      armour=[gm("acp", 2), gm("weight_pct", -20), gm("hp_per_inch", -2)],
      working=wk("easily_worked", "malleable"),
      text="Soft grey metal that cries when bent. As fittings and fastenings it lightens "
           "the piece and lets a hand or a body move quicker, and it is the first thing "
           "to give. One part in ten turns copper into bronze.")
entry("lead", pieces={"weapon": ["fittings"], "armour": ["lining"]},
      weapon=[cm("damage", 2), cm("attack", -2), gm("weight_pct", 20)],
      armour=[cm("ac", 2), gm("acp", -2), gm("weight_pct", 20)],
      working=wk("easily_worked", "malleable"),
      text="Dense, dull and obedient: it melts over a candle and holds any shape. A lead "
           "pommel or counterweight puts weight behind a blow and drags the swing; a lead "
           "lining deadens blows and the wearer pays for it in weight. The lining that "
           "stops scrying is its own treatment.")
entry("zinc", feeds=["alloy"], working=wk("narrow_window", "brittle", "easily_worked"),
      text="Bluish-white and brittle, boiling away out of any careless melt. It fills no "
           "piece; it is alloying stock, married to copper to make brass.")
entry("silver", pieces={"weapon": ["fittings"], "armour": ["fastenings"]},
      weapon=[cm("damage", 2, when=vs_sub("shapechanger")),
              cm("attack", 2, when=vs_sub("shapechanger")), gm("hardness", -2)],
      armour=[gm("max_dex", 2), gm("acp", 2), gm("hardness", -2)],
      working=wk("easily_worked"),
      text="The moon's metal, too soft to hold an edge alone. Silver fittings make a "
           "weapon bite harder and truer against shapechangers, and silver fastenings "
           "let armour move freely; both are softer than steel. A weapon that strikes as "
           "silver is the alchemical plating treatment.")
entry("gold", pieces={"weapon": W_HS, "armour": A_BF},
      weapon=[B(cm("damage", -2, bonus="untyped", note="solid gold weapon, minimum 1")),
              B(gm("hardness", -5, note="half the base hardness")),
              B(gm("weight_pct", 50, note="solid gold")),
              sk("diplomacy", 2)],
      armour=[B(cm("ac", -2, bonus="armour", note="solid gold armour")),
              B(gm("acp", -2, note="the book's +2 check penalty")),
              B(gm("hardness", -5, note="hardness 5")),
              B(gm("weight_pct", 50, note="solid gold")),
              sk("diplomacy", 2)],
      working=wk("malleable", "pure"),
      text="Heavy, incorruptible and useless in a fight, exactly as the book prints it: "
           "solid gold cuts softer, guards worse, weighs half again and breaks easily. "
           "What it does is announce the owner, and people listen. The kindest metal at "
           "the anvil.")
entry("platinum", pieces={"weapon": W_HS, "armour": A_BF},
      weapon=[cm("damage", 3), gm("hp_per_inch", 2), cm("attack", -2)],
      armour=[res("acid", 3), cm("ac", 2), gm("weight_pct", 30)],
      working=wk("narrow_window", "pure"),
      text="White metal that no acid touches and no common furnace melts. A platinum head "
           "is dense enough to hit very hard and drags the swing; platinum armour shrugs "
           "off acid and turns blows, and is very heavy.")
entry("cold-iron", pieces={"weapon": W_HS, "armour": A_BF},
      weapon=[B(sa("cold_iron")), cm("attack", 2, when=vs("fey")), gm("hardness", -2)],
      armour=[sv("will", 2), cm("ac", 2), gm("hardness", -2)],
      working=wk("narrow_window"),
      text="Iron mined deep and forged at low heat, never allowed to forget the dark it "
           "came from. A cold iron head strikes as cold iron, through the defences of "
           "demons and fey, and swings truer against the fey; cold iron armour steadies "
           "the wearer's will. Forged low, it is softer than common iron, and its heat "
           "window is narrow.")
entry("star-iron", pieces={"weapon": W_HS, "armour": A_BF},
      weapon=[sa("cold_iron"), cm("damage", 3), gm("hp_per_inch", -2)],
      armour=[cm("ac", 3), gm("hardness", 2), gm("acp", -2)],
      working=wk("easily_worked", "slaggy"),
      text="Meteoric iron, sky-fallen and already smelted by its landing, which makes it "
           "quick to work and full of stony inclusions. A star-iron head strikes as cold "
           "iron and hits hard but chips; star-iron plate is hard and stiff. A house "
           "metal with no book behind it.")
entry("viridium", pieces={"weapon": ["head"]},
      weapon=[B({"type": "save_gate", "target": "fort", "dc": 12, "trigger": "hit",
                 "on_failure": [{"type": "ability_damage", "target": "cha", "dice": "1d2"}],
                 "note": "leprosy: onset 2d4 weeks, 1/week, cured by 2 consecutive saves; "
                         "oozes, plants and outsiders are immune"}),
              B({"type": "save_gate", "target": "fort", "dc": 13, "trigger": "crit",
                 "on_failure": [{"type": "ability_damage", "target": "con", "dice": "1"}],
                 "note": "a fragment breaks off as greenblood oil: 1/round for 4 rounds"}),
              B({"type": "save_gate", "target": "fort", "dc": 12, "trigger": "carried",
                 "recipient": "self",
                 "on_failure": [{"type": "ability_damage", "target": "cha", "dice": "1d2"}],
                 "note": "leprosy, saved every 24 hours, unless kept extradimensional or "
                         "in a lead-lined scabbard"}),
              B(gm("hardness", -5, note="half hardness"))],
      working=wk("brittle", "narrow_window"),
      text="A dull green volcanic glass, knapped rather than forged, though smiths shelve "
           "it with the metals. Only a piercing or slashing head: every hit risks leprosy "
           "(Fortitude DC 12), a critical leaves a sliver of greenblood oil (DC 13), and "
           "whoever carries it saves against the leprosy each day unless the blade sleeps "
           "in lead. Half as hard as steel, and fragile in the book.",
      legacy=[{"type": "save_gate", "target": "fort", "dc": 12,
               "on_failure": [{"type": "ability_damage", "target": "cha", "dice": "1d2"}],
               "note": "leprosy, on any wound from a viridium edge"}])
entry("mithral", pieces={"weapon": W_HS, "armour": A_BF},
      weapon=[B(sa("silver")), B(gm("weight_pct", -50)), B(gm("hardness", 5)),
              cm("attack", 2), cm("damage", -2)],
      armour=[B(gm("acp", 3, note="armour check penalty 3 lighter, never above 0")),
              B(gm("max_dex", 2)), B(gm("asf", -10)), B(gm("weight_pct", -50)),
              B(gm("category", -1, note="for movement only, never for proficiency")),
              B(gm("hardness", 5)), gm("hp_per_inch", -2)],
      working=wk("forgiving"),
      text="Truesilver: harder than steel at half the weight. A mithral head strikes as "
           "silver and is quick in the hand but light behind the blow. Mithral armour is "
           "the book's: half weight, a lighter check penalty, two more points of "
           "Dexterity, less spell failure, and it moves one class lighter, for movement "
           "and never for proficiency. Its plates are thinner than steel's. Worked like "
           "steel, forgivingly.",
      legacy=[{"type": "narrative",
               "target": "Half weight; armour counts one category lighter for movement "
                         "(not for proficiency)"},
              {"type": "narrative",
               "target": "Armour: maximum Dexterity bonus +2, armour check penalty 3 "
                         "lighter, spell failure 10% lower; a weapon counts as silver"}])
entry("adamantine", pieces={"weapon": W_HS, "armour": A_BF},
      weapon=[B(sa("adamantine", note="ignores hardness below 20")),
              B(gm("hardness", 10)), B(gm("hp_per_inch", 10)),
              cm("damage", 2), gm("weight_pct", 20)],
      armour=[B(dr(1, when=by_weight("light"))), B(dr(2, when=by_weight("medium"))),
              B(dr(3, when=by_weight("heavy"))),
              B(gm("hardness", 10)), B(gm("hp_per_inch", 10)),
              cm("ac", 2), gm("acp", -2)],
      working=wk("narrow_window"),
      text="The unbreakable night-black metal of fallen stars, hardness 20. An adamantine "
           "head strikes as adamantine, through hardness below 20, and hits harder, though "
           "it is heavier than steel. Adamantine armour gives the book's damage reduction "
           "of 1, 2 or 3 by weight and turns blows, but it does not flex.")
entry("abysium", pieces={"weapon": W_HS, "armour": A_BF}, risky=True,
      weapon=[B({"type": "apply_condition", "target": "sickened", "trigger": "carried",
                 "note": "while carried and for 1d4 hours after; a poison effect, no save"}),
              cm("damage", 3), cm("attack", 2)],
      armour=[B({"type": "apply_condition", "target": "sickened", "trigger": "carried",
                 "note": "while carried and for 1d4 hours after; a poison effect, no save"}),
              cm("ac", 3), gm("hardness", 2)],
      working=wk("reactive", "narrow_window"),
      text="Feverstone: a skymetal that glows like a candle and works as steel. Its "
           "weapons bite and its armour turns blows better than steel, and it sickens "
           "whoever carries it, with no save, until 1d4 hours after it is put down. "
           "Assaying it is genuinely dangerous.",
      legacy=[{"type": "apply_condition", "target": "sickened",
               "note": "while carried and for 1d4 hours after; a poison effect, no save"},
              {"type": "narrative",
               "target": "Glows: sheds light as a candle, and cannot be hidden from "
                         "creatures that see it"}])
entry("djezet", feeds=["alloy"], working=wk("malleable", "pure", "weld_aid"),
      text="The quickmetal: rust-red and liquid at every temperature. It fills no piece; "
           "the book makes it useless for metal objects except alloys, and at the "
           "crucible it is the kindest of the skymetals. Its spell-quickening use is a "
           "spellcaster's, not a smith's.")
entry("inubrix", pieces={"weapon": ["head"]},
      weapon=[B(cm("attack", -2, bonus="untyped", note="always broken")),
              B(cm("damage", -2, bonus="untyped", note="always broken; and damage as one "
                                                       "size smaller")),
              B(gm("hardness", -5, note="hardness 5")),
              B(gm("hp_per_inch", -20, note="10 hit points per inch")),
              cm("attack", 3, when={"target": {"armour_metal": True}},
                 note="house approximation of the book's 'ignores armour and shield "
                      "bonuses from iron or steel'")],
      working=wk("malleable", "narrow_window"),
      text="Ghost iron, the softest of the skymetals. An inubrix head is always broken in "
           "the book, deals damage as a size smaller and cannot harm iron or steel, but "
           "passes through iron and steel armour as if it were not there; here it swings "
           "truer against a metal-armoured foe. Poor for armour, so it fills no armour "
           "piece.",
      legacy=[{"type": "narrative",
               "target": "Ignores armour and shield bonuses from iron or steel, but is "
                         "always broken, deals damage as one size smaller and cannot "
                         "damage iron or steel"}])
entry("noqual", pieces={"weapon": W_HS, "armour": A_BF}, enchant_surcharge_gp=5000,
      weapon=[B(gm("weight_pct", -50)),
              B(cm("damage", 1, bonus="enhancement", when=vs("construct"),
                   note="constructs made by feats or spells")),
              B(cm("damage", 1, bonus="enhancement", when=vs("undead"),
                   note="undead made by feats or spells")),
              gm("hp_per_inch", -2)],
      armour=[B(gm("asf", 20, note="for all spellcasting, not only arcane")),
              B(sv("fort", 2, bonus="resistance", when={"against": "spell"})),
              B(sv("ref", 2, bonus="resistance", when={"against": "spell"})),
              B(sv("will", 2, bonus="resistance", when={"against": "spell"})),
              B(gm("weight_pct", -50)), B(gm("category", -1)), B(gm("max_dex", 2)),
              B(gm("acp", 3))],
      working=wk("forgiving", "reactive"),
      text="Pale green and crystalline, and magic slides off it. Noqual is half weight; "
           "its weapons bite constructs and made undead harder, and its armour moves a "
           "class lighter and wards its wearer against spells, at a fifth more spell "
           "failure for any caster. Any magic item made with it costs 5,000 gp more to "
           "enchant. Worked as iron, but assaying it is dangerous.",
      legacy=[{"type": "narrative",
               "target": "Half weight; armour: +2 resistance on saves against spells, "
                         "+20% spell failure for all casting, one category lighter; any "
                         "magic item made with it costs 5,000 gp more"}])
entry("siccatite", pieces={"weapon": ["head"], "armour": ["body"]}, risky=True,
      weapon=[B({"type": "damage", "dice": "1", "damage_type": "fire",
                 "lethality": "lethal", "trigger": "hit",
                 "note": "hot siccatite; cold siccatite deals cold"}),
              B({"type": "damage", "dice": "1", "damage_type": "fire",
                 "lethality": "lethal", "recipient": "self", "trigger": "each_round",
                 "duration": ALWAYS, "note": "to the wielder, each round of combat"}),
              cm("damage", 2)],
      armour=[B({"type": "damage", "dice": "1", "damage_type": "fire",
                 "lethality": "lethal", "recipient": "self", "trigger": "each_round",
                 "duration": ALWAYS, "note": "to the wearer, each round"}),
              B({"type": "damage", "dice": "1", "damage_type": "fire",
                 "lethality": "lethal", "recipient": "attacker",
                 "trigger": "when_grappled", "duration": ALWAYS,
                 "note": "to whoever grapples the wearer, each round"}),
              B(res("cold", 5, note="hot siccatite armour; cold siccatite gives fire "
                                    "resistance 5 instead")),
              cm("ac", 2)],
      working=wk("reactive", "narrow_window"),
      text="The skymetal of extremes; this is the hot kind. A siccatite head brands what "
           "it hits for a point of fire and burns its wielder a point each round of "
           "combat. Siccatite armour burns its wearer and anyone who grapples them, and "
           "keeps the cold off. Assaying it burns.")
entry("horacalcum", pieces={"weapon": W_HS, "armour": A_BF},
      weapon=[B(cm("attack", 1, bonus="circumstance", note="not ammunition")),
              B(gm("hardness", 5)), cm("initiative", 4), cm("damage", -2)],
      armour=[B(cm("initiative", 1, bonus="untyped", when=by_weight("light"))),
              B(cm("initiative", 2, bonus="untyped", when=by_weight("medium"))),
              B(cm("initiative", 3, bonus="untyped", when=by_weight("heavy"))),
              B(gm("hardness", 5)), gm("acp", -2)],
      working=wk("narrow_window", "pure"),
      text="The rarest skymetal, a dull coppery gold around which time runs slow. A "
           "horacalcum blade gives the book's +1 on the attack and puts its bearer ahead "
           "in the fight, though it lands lightly. Horacalcum armour quickens the wearer "
           "by its weight, +1 to +3 initiative, and sits stiffly.",
      legacy=[{"type": "combat_mod", "amount": 1, "bonus_type": "circumstance",
               "target": "attack", "note": "a horacalcum weapon; armour instead gives "
                                           "+1/+2/+3 initiative by weight"}])

# ---- alloys ---------------------------------------------------------------------------------

entry("steel", pieces={"weapon": W_HS, "armour": A_BF},
      weapon=[cm("attack", 2), gm("hardness", 2), gm("hp_per_inch", -2)],
      armour=[cm("ac", 2), gm("hardness", 2), gm("max_dex", -2)],
      working=wk("forgiving"),
      text="Iron with carbon taken into itself in the fire. A steel head swings true and "
           "holds its hardness, and is less forgiving of a hard knock than iron; steel "
           "plate turns blows and is hard, and binds the wearer a little. The trade's "
           "whole ladder of quench, temper and hone exists because steel answers to it.")
entry("bronze", pieces={"weapon": W_HS, "armour": A_BF},
      weapon=[cm("attack", 2), gm("hp_per_inch", 2), gm("hardness", -2)],
      armour=[B(gm("hardness", -1, note="primitive bronze armour: hardness 9")),
              cm("ac", 2), gm("weight_pct", 20)],
      working=wk("forgiving", "easily_worked"),
      text="Copper and tin, the metal that named an age. A bronze head swings true and "
           "is tough but softer than steel; bronze armour turns blows, has the book's "
           "hardness of 9, and is heavy. Casts beautifully. In the book bronze weapons "
           "are fragile, which this app does not yet model.")
entry("brass", pieces={"weapon": ["fittings"], "armour": ["fastenings"]},
      weapon=[cm("cmd", 2), sk("diplomacy", 2), gm("hardness", -2)],
      armour=[gm("acp", 2), sk("diplomacy", 2), gm("hardness", -2)],
      working=wk("easily_worked"),
      text="Copper and zinc, gold's honest cousin. Brass fittings hold a blade in the "
           "hand and shine without a servant, and brass fastenings move easily; it is "
           "softer than steel. Easy to work and file.")
entry("pewter", pieces={"weapon": ["fittings"], "armour": ["fastenings"]},
      weapon=[gm("weight_pct", -20), gm("hardness", -2), gm("hp_per_inch", -2)],
      armour=[gm("weight_pct", -20), gm("acp", 2), gm("hardness", -2)],
      working=wk("easily_worked", "malleable"),
      text="Tin stiffened with a little copper and less honesty. Pewter buckles and "
           "fittings are light and cheap and the first thing to break.")
entry("electrum", pieces={"weapon": ["fittings"], "armour": ["fastenings"]},
      weapon=[sk("diplomacy", 2), cm("damage", 2, when=vs_sub("shapechanger")),
              gm("hardness", -2)],
      armour=[sk("diplomacy", 2), gm("max_dex", 2), gm("hardness", -2)],
      working=wk("pure", "malleable"),
      text="Gold and silver as nature sometimes pours them together, pale and moonish. "
           "Electrum fittings impress, and carry enough silver to bite a shapechanger "
           "harder; fastenings of it impress and flex. Soft, and a pleasure to work.")
entry("bell-bronze", pieces={"weapon": ["fittings"], "armour": ["fastenings"]},
      weapon=[sk("intimidate", 2), gm("hardness", 2), gm("hp_per_inch", -2)],
      armour=[sk("intimidate", 2), gm("hardness", 2), gm("hp_per_inch", -2)],
      working=wk("brittle", "easily_worked"),
      text="Bronze rich in tin, brittle as glass and voiced like an angel. Fittings of it "
           "ring on every blow, which unsettles whoever hears them; it is hard and it "
           "cracks. Casts easily.",
      legacy=[{"type": "narrative",
               "target": "Rings when struck: a signal audible far beyond shouting distance"}])
entry("high-carbon-steel", pieces={"weapon": ["head"], "armour": ["body"]},
      weapon=[cm("damage", 2), gm("hardness", 2), gm("hp_per_inch", -2)],
      armour=[cm("ac", 2), gm("hardness", 2), gm("hp_per_inch", -2)],
      working=wk("quench_sensitive", "narrow_window"),
      text="Steel fed carbon to the edge of temper's patience. A head of it cuts deeper "
           "and holds its hardness, and plate of it turns more blows, but both shatter "
           "sooner. The quench is narrow and brine cracks it on a miss.")
entry("pattern-steel", pieces={"weapon": ["head"], "armour": ["body"]},
      weapon=[cm("damage", 2), gm("hp_per_inch", 2), gm("hardness", -2)],
      armour=[cm("ac", 2), gm("hp_per_inch", 2), gm("hardness", -2)],
      working=wk("flawless", "narrow_window"),
      text="Billets of hard and soft steel folded and welded until the blade carries "
           "water-marks. Spring and edge in one bar: it cuts deep and survives what "
           "snaps a plain blade, and is a little softer for the spring. Masterwork costs "
           "it no extra difficulty, in a narrow heat window.")
entry("nexavaran-steel", pieces={"weapon": W_HS, "armour": A_BF},
      weapon=[B(sa("cold_iron")), cm("damage", 2), gm("hardness", -2)],
      armour=[sv("will", 2), gm("hardness", 2), gm("acp", -2)],
      working=wk("narrow_window", "forgiving"),
      text="Cold iron drawn out with a measure of common steel, the compromise metal of "
           "frontier fey-hunters. A head of it strikes as cold iron, as the book says, "
           "and cuts well but is softer; armour of it steadies the will and is stiff.",
      legacy=[{"type": "narrative",
               "target": "Counts as cold iron against damage reduction, at 1.5 times "
                         "common cost rather than double"}])
_EB_TYPES = ["magical beast", "monstrous humanoid"]
entry("elysian-bronze", pieces={"weapon": W_HS, "armour": A_BF},
      weapon=[B(cm("damage", 1, bonus="untyped", when={"target": {"type": _EB_TYPES}},
                   note="multiplied on a critical hit")),
              B(cm("attack", 1, bonus="untyped", trigger="hit", recipient="self",
                   duration={"amount": 24, "unit": "hour"},
                   when={"target": {"type": _EB_TYPES}},
                   note="after it damages one, against that kind of creature for 24 "
                        "hours")),
              gm("hardness", -2)],
      armour=[B(dr(1, when={**by_weight("light"), "attacker": {"type": _EB_TYPES}},
                   note="only against their natural weapons and unarmed strikes")),
              B(dr(2, when={**by_weight("medium"), "attacker": {"type": _EB_TYPES}},
                   note="only against their natural weapons and unarmed strikes")),
              B(dr(3, when={**by_weight("heavy"), "attacker": {"type": _EB_TYPES}},
                   note="only against their natural weapons and unarmed strikes")),
              gm("acp", -2)],
      working=wk("forgiving"),
      text="Bronze alloyed with traces of celestial metal, first beaten out for heroes "
           "who hunted monsters. Its weapons bite magical beasts and monstrous humanoids "
           "harder, and after drawing blood from one swing truer against that kind for a "
           "day. Its armour gives damage reduction, 1 to 3 by weight, against their claws "
           "and fists. Softer than steel, and stiff as armour.")
entry("living-steel", pieces={"weapon": W_HS, "armour": A_BF},
      weapon=[B(gm("hardness", 5)), B(gm("hp_per_inch", 5)), cm("cmd", 3),
              cm("attack", -2)],
      armour=[B(gm("hardness", 5)), B(gm("hp_per_inch", 5)), cm("ac", 2),
              gm("acp", -2)],
      working=wk("forgiving", "malleable"),
      text="Steel quickened by waters from trees that will not die: the book's hardness "
           "15 and 35 hit points an inch. A living-steel weapon is hard to wrest away "
           "and its grain fights the hand; its armour turns blows and is stiff. In the "
           "book it mends 2 hit points a day and can break a weapon that rolls a 1 "
           "against it; neither is modelled yet.",
      legacy=[{"type": "narrative",
               "target": "Repairs 2 hit points a day (1 if broken); a metal weapon that "
                         "rolls a natural 1 against its armour saves DC 20 Fortitude or "
                         "breaks"}])
entry("fire-forged-steel", pieces={"weapon": W_HS, "armour": A_BF},
      weapon=[cm("damage", 2, when=vs_sub("cold")), gm("hp_per_inch", 2),
              gm("hardness", -2)],
      armour=[B(res("fire", 2)), cm("ac", 2), gm("acp", -2)],
      working=wk("narrow_window"),
      text="Dwarven steel worked with channels that carry heat one way. Its armour gives "
           "the book's fire resistance 2, always, and turns blows but is stiff. Its "
           "weapons bite cold creatures harder and are tough but softer. The book's "
           "weapon rule, extra fire after it has sat in flame, is not modelled yet.",
      legacy=[{"type": "resistance", "target": "fire", "amount": 2,
               "note": "armour, always"}])
entry("frost-forged-steel", pieces={"weapon": W_HS, "armour": A_BF},
      weapon=[cm("damage", 2, when=vs_sub("fire")), gm("hp_per_inch", 2),
              gm("hardness", -2)],
      armour=[B(res("cold", 2)), cm("ac", 2), gm("max_dex", -2)],
      working=wk("narrow_window"),
      text="The winter twin of fire-forged steel. Its armour gives the book's cold "
           "resistance 2, always, and turns blows but binds the wearer. Its weapons bite "
           "fire creatures harder and are tough but softer. The book's weapon rule, extra "
           "cold after it has been chilled, is not modelled yet.",
      legacy=[{"type": "resistance", "target": "cold", "amount": 2,
               "note": "armour, always"}])
entry("singing-steel", pieces={"weapon": W_HS, "armour": A_BF},
      weapon=[B(sa("silver")),
              B(cm("damage", -1, bonus="untyped", when={"weapon": {"slashing_or_piercing": True}},
                   note="counts as alchemical silver: slashing or piercing only, "
                        "minimum 1")),
              B(gm("hp_per_inch", -10, note="20 hit points per inch")),
              sk("perform", 3)],
      armour=[B(gm("category", -1)), B(gm("asf", -5)), B(gm("max_dex", 1)),
              B(gm("acp", 1)), B(gm("hp_per_inch", -10, note="20 hit points per inch")),
              sk("perform", 3)],
      working=wk("pure", "narrow_window"),
      text="A pale gold and mithral alloy that chimes at a touch. Its weapons strike as "
           "alchemical silver, with silver's lighter cut; its armour moves a class "
           "lighter with a little less spell failure and check penalty. Both are less "
           "tough than steel, and both carry a performer's voice. In the book striking "
           "it speeds a bardic performance; here it lends Perform.",
      legacy=[{"type": "combat_mod", "amount": -1, "bonus_type": "untyped",
               "target": "damage",
               "note": "counts as alchemical silver: slashing or piercing only"}])
entry("wyrmsteel", pieces={"weapon": W_HS, "armour": A_BF},
      weapon=[sa("adamantine"), cm("damage", 4), gm("weight_pct", 30)],
      armour=[res("fire", 4), cm("ac", 3), gm("acp", -2)],
      working=wk("narrow_window", "flawless"),
      text="Adamantine folded over dragonfire coal and quenched in dragon's blood, an "
           "alloy more legend than recipe. Its weapons strike as adamantine and hit very "
           "hard, and are heavy; its armour keeps a dragon's indifference to flame and "
           "turns blows, and is stiff. A house metal with no book behind it.",
      legacy=[{"type": "resistance", "target": "fire", "amount": 4,
               "note": "the metal's own dragon-nature, carried by armour of it"}])

# ---- fuels: working traits only -------------------------------------------------------------

entry("peat", working=wk("forgiving", "sulfurous", "slaggy"),
      text="Cut from the bog and dried through a season. Burns low, slow and smoky: a "
           "forgiving fire for a field forge, but it runs sulfurous and leaves the work "
           "slaggy.")
entry("coal", working=wk("sulfurous", "hot_short", "easily_worked"),
      text="Black seam-rock that burns hotter and longer than wood, so work goes faster, "
           "but raw coal is sulfurous and a careless heat leaves the iron hot-short.")
entry("charcoal", working=wk("clean_heat", "forgiving", "pure"),
      text="Wood burned slow under turf until only the burning part is left. Clean, "
           "forgiving heat that adds nothing to the melt but temperature, which is "
           "exactly what a smith wants.")
entry("coke", working=wk("clean_heat", "easily_worked", "narrow_window"),
      text="Coal baked in an airless oven until its smoke and sulphur are driven off. "
           "Burns hotter and cleaner than coal, so the work goes quickly, in a tighter "
           "heat band.")
entry("bone-char", working=wk("flawless", "clean_heat", "narrow_window"),
      text="Charred bone, packed around iron to feed carbon into the surface. The fuel "
           "of case-hardening: a clean heat that lifts work to masterwork without extra "
           "difficulty, in a narrow band.")
entry("dwarven-hearthcoal", working=wk("clean_heat", "forgiving", "easily_worked"),
      text="Coal from seams the dwarves keep secret, dense as ore and slow as grudges. "
           "One scuttle burns a day and a night at forging heat: clean, steady and quick "
           "to work over.")
entry("dragonfire-coal", working=wk("easily_worked", "narrow_window", "sulfurous"),
      risky=True,
      text="Coal from seams a dragon once slept over. It burns white, hot enough to melt "
           "the skymetals, fast and in a narrow band, and sulfurous; it does not care "
           "whether the smith's beard is in the way.")
entry("salamander-cinder", working=wk("easily_worked", "malleable", "narrow_window"),
      text="Embers raked from a slain salamander's own hearth-flesh. They burn without "
           "fuel for a month, so the work is quick and a bad blow can be reheated and "
           "saved, in a narrow band.")
entry("efreet-brand", working=wk("forgiving", "pure", "malleable"),
      text="A brand from a bonfire on the Plane of Fire, carried home still burning. "
           "Forge-fire from it burns any colour the smith asks: the widest heat band "
           "there is, and very hard to spoil a piece over.")
entry("phoenix-ash-ember", working=wk("malleable", "pure", "flawless"),
      text="An ember from the pyre of a phoenix, which relights itself by morning however "
           "it is put out. Nothing forged over it is ruined by a bad blow, the check is "
           "rolled twice, and masterwork costs no extra difficulty.",
      legacy=[])

# ---- fluxes: working traits only ------------------------------------------------------------

entry("limestone", working=wk("cleans_slag", "easily_worked", "forgiving"),
      text="Crushed grey stone thrown into the melt, where it gathers the slag and floats "
           "it off the good metal. The cheapest honest flux: it cleans a smelt and makes "
           "it easier.")
entry("silica-sand", working=wk("weld_aid", "cleans_slag", "narrow_window"),
      text="Clean white sand for the forge-weld: it melts to glass and keeps the air off "
           "the joint. Helps folding and strengthening, cleans a little slag, and wants "
           "a precise heat.")
entry("potash", working=wk("weld_aid", "easily_worked", "malleable"),
      text="Wood ash leached and boiled down to a white salt. An old fireside flux for "
           "small work and soldering: welds come easier and a slip spoils nothing.")
entry("borax", working=wk("weld_aid", "forgiving", "flawless"),
      text="White crystal from dry lake beds, the wandering smith's flux: it melts low, "
           "widens the weld's heat band, and leaves a weld clean enough for masterwork "
           "at no extra difficulty.")
entry("bone-ash", working=wk("cleans_slag", "pure", "narrow_window"),
      text="Calcined bone, the assayer's flux. It soaks base metal away and leaves silver "
           "and gold sitting proud: it cleans a smelt and the check is rolled twice, in "
           "a narrow heat.")
entry("crushed-quartz", working=wk("narrow_window", "flawless", "weld_aid"),
      text="Clear crystal ground fine, for melts that must run glassy. Finicky, with a "
           "narrow heat, and worth it: fine work reaches masterwork at no extra "
           "difficulty and welds come easier.")
entry("consecrated-flux", working=wk("cleans_slag", "pure", "flawless"),
      text="Chalk blessed at a temple altar and ground with silver dust. In the melt it "
           "cleans thoroughly and steadies the smith's hand. A flux leaves no mark on "
           "the finished work; for a blessed edge, quench in holy water or anoint it.",
      legacy=[])
entry("abyssal-salt", working=wk("cleans_slag", "easily_worked", "reactive"), risky=True,
      text="Salt scraped from the shores of a lake in the Abyss. It strips a melt cleaner "
           "and faster than any earthly flux, and assaying it is dangerous: holy water "
           "hisses on it.",
      legacy=[])
entry("stardust-flux", working=wk("weld_aid", "pure", "flawless"),
      text="Glittering dust gathered where a star fell, sold by the pinch. It makes any "
           "weld take, steadies the check and costs masterwork nothing extra; the old "
           "smiths say it alone persuades the skymetals to mingle.",
      legacy=[])

# ---- quenchants: working traits plus one mark -----------------------------------------------

entry("water", working=wk("easily_worked", "narrow_window"),
      quench_mark=gm("hardness", 1),
      text="The oldest bath, always to hand. Quenches fast and hard, leaving the piece a "
           "point harder, in a narrow window that cracks a careless blade.")
entry("quenching-brine", working=wk("narrow_window", "brittle"),
      quench_mark=gm("hardness", 2),
      text="Salt water bites faster than sweet. It leaves the hardest skin of the common "
           "baths, and the narrowest window, and it can leave a careless blade brittle.")
entry("quenching-oil", working=wk("forgiving", "malleable"),
      quench_mark=gm("hp_per_inch", 2),
      text="Rendered fat or seed oil, the gentle bath. Slower than water and kinder: the "
           "piece comes out tougher rather than harder, and a bad quench ruins nothing.")
entry("whale-oil", working=wk("forgiving", "pure"),
      quench_mark=gm("hp_per_inch", 2),
      text="The finest quenching oil money buys, even-tempered from first plunge to "
           "last. Leaves the piece tougher, and the quench is forgiving and sure.")
entry("glacier-melt", working=wk("narrow_window", "pure"),
      quench_mark=res("cold", 1),
      text="Water from ice older than the kingdom. A blade quenched in it keeps a little "
           "winter: its bearer shrugs off a point of cold. A sharp, clean quench.")
entry("mercury-bath", material="quicksilver", working=wk("pure", "reactive"), risky=True,
      quench_mark=gm("hardness", 1),
      text="Quicksilver quenches with unearthly evenness, leaving the piece a point "
           "harder, and gives off a vapour that steals wits: assaying it is dangerous.")
entry("blessed-water", working=wk("pure", "forgiving"),
      quench_mark=cm("damage", 1, bonus="untyped", when=vs("undead")),
      text="Holy water enough to quench in, which is a conversation with the temple "
           "first. Steel quenched in it bites the undead a little harder. It does not "
           "make the blade good-aligned: in the book that needs magic, and a quench is "
           "not magic.",
      legacy=[{"type": "combat_mod", "amount": 1, "bonus_type": "untyped",
               "target": "damage", "note": "against undead"}])
entry("troll-blood", working=wk("malleable", "narrow_window"),
      quench_mark=_with({"type": "fast_healing", "amount": 1, "recipient": "self",
                         "trigger": "first_wound_daily",
                         "duration": {"amount": 1, "unit": "minute"}}, PER_DAY),
      text="Blood drawn from a troll and kept warm, because it does not accept being "
           "dead. What it hardens heals its bearer: fast healing 1 for a minute after "
           "the first wound each day.",
      legacy=[{"type": "fast_healing", "amount": 1,
               "duration": {"amount": 1, "unit": "minute"},
               "note": "once a day, after the first wound"}])
entry("wyvern-blood", working=wk("narrow_window", "reactive"),
      quench_mark={"type": "save_gate", "target": "fort", "dc": 17,
                   "trigger": "first_wound_daily",
                   "on_failure": [{"type": "ability_damage", "target": "con",
                                   "dice": "1d4"}],
                   "note": "wyvern venom, in the first wound the blade deals each day"},
      text="Envenomed blood from a wyvern's tail-stock. A blade quenched in it carries "
           "the sting into its first wound each day: Fortitude DC 17 or 1d4 Constitution. "
           "Assaying it is dangerous.")
entry("dragon-blood", working=wk("narrow_window", "pure"),
      quench_mark=res("fire", 2, note="a fire dragon's blood; other lineages lend their "
                                      "own element"),
      text="Blood of a true dragon, which quenches steel without ever quite going cold. "
           "The piece takes a shadow of the donor's element: its bearer resists 2 fire "
           "from a red dragon's blood.")
entry("styx-water", working=wk("narrow_window", "reactive"),
      quench_mark={"type": "bundle", "label": "Styx-quenched",
                   "effects": [cm("damage", 1, bonus="untyped", when=vs("outsider")),
                               sv("will", -1, bonus="untyped", recipient="self")]},
      text="Water from the river of forgetting, carried in horn. A blade quenched in it "
           "bites outsiders harder and dulls its bearer's will; the smith works fast and "
           "tries not to breathe the steam.",
      legacy=[{"type": "combat_mod", "amount": 1, "bonus_type": "untyped",
               "target": "damage", "note": "against outsiders; the bearer takes -1 on "
                                           "Will saves"}])

# ---- fittings -------------------------------------------------------------------------------
#
# The worked example (plan §6.4) reads three of these and must stay true to the integer:
# iron's head is +2 damage, -2 attack, +2 hardness; ash's haft +2 attack and nothing on
# damage or hardness; brass-guard's fittings +2 hardness and nothing on attack or damage.

entry("ash-haft", pieces={"weapon": ["haft"]},
      weapon=[cm("attack", 2), cm("cmd", 2), gm("hp_per_inch", -2)],
      working=wk("easily_worked"),
      text="Straight-grained ash, the spear-wood. Springy in the hand, so the weapon "
           "swings truer and is harder to wrest away, though wood is weaker than steel.")
entry("oak-haft", pieces={"weapon": ["haft"]},
      weapon=[cm("damage", 2), gm("hp_per_inch", 2), cm("attack", -2)],
      working=wk("forgiving"),
      text="Heavy, stiff and stubborn: the right wood under an axe or maul that leads "
           "with weight. It hits harder and lasts, and drags the swing.")
entry("bone-grip", pieces={"weapon": ["haft"]},
      weapon=[gm("hardness", 2), cm("cmd", 2), cm("attack", -2)],
      working=wk("easily_worked"),
      text="Scales of polished bone riveted to the tang. Hard-wearing and sure against a "
           "disarm, and slick in a sweating hand.")
entry("leather-grip", pieces={"weapon": ["haft"], "armour": ["lining"]},
      weapon=[cm("attack", 2), cm("cmd", 2), gm("hardness", -2)],
      armour=[cm("ac", 2), gm("acp", 2), gm("weight_pct", 20)],
      working=wk("forgiving"),
      text="Wet-wrapped leather that dries to the shape of the hand. As a grip it holds "
           "true and hard to wrest away; as a lining it pads blows and eases movement "
           "at the cost of weight.")
entry("cord-wrapped-grip", pieces={"weapon": ["haft"]},
      weapon=[cm("attack", 2), cm("cmb", 2), gm("hp_per_inch", -2)],
      working=wk("easily_worked"),
      text="Waxed cord laid in tight courses over the tang. Grips wet or dry, which helps "
           "both the swing and a trip or disarm, and wears through; a field repair needs "
           "only more cord.")
entry("brass-guard", pieces={"weapon": ["fittings"]},
      weapon=[gm("hardness", 2), cm("cmd", 2), gm("hp_per_inch", -2)],
      working=wk("easily_worked"),
      text="A cast brass crossguard or basket, bright and forgiving to file. It hardens "
           "the hilt and turns a disarming blade, and cast brass cracks before forged "
           "steel would.")
entry("steel-crossguard", pieces={"weapon": ["fittings"]},
      weapon=[cm("cmd", 2), gm("hp_per_inch", 2), gm("weight_pct", 20)],
      working=wk("forgiving"),
      text="Plain forged steel between hand and harm. It turns a disarm and outlasts the "
           "grip, and adds weight. Nothing about it is clever, which is why it works.")
entry("wire-wrapped-grip", pieces={"weapon": ["haft"]},
      weapon=[cm("cmd", 2, note="the duellist's grip, against being disarmed"),
              cm("attack", 2), gm("hardness", -2)],
      working=wk("narrow_window"),
      text="Twisted silver or steel wire laid over leather, the duellist's grip: it does "
           "not shift in the hand, so the blade swings true and is hard to take away. "
           "Fiddly to lay, and softer than a solid grip.",
      legacy=[{"type": "combat_mod", "amount": 2, "bonus_type": "untyped",
               "target": "cmd", "note": "against being disarmed of the fitted weapon"}])
entry("sharkskin-grip", pieces={"weapon": ["haft"]},
      weapon=[cm("attack", 2), cm("cmb", 2), gm("hardness", -2)],
      working=wk("forgiving"),
      text="Ray or shark hide, rough as a file in one direction. It never slips, wet, "
           "bloody or otherwise, so the swing and the grab are both surer; a hide grip "
           "is softer than bone.",
      legacy=[])
entry("mammoth-ivory-grip", pieces={"weapon": ["haft"]},
      weapon=[gm("hp_per_inch", 2), sk("diplomacy", 2), cm("attack", -2)],
      working=wk("easily_worked"),
      text="Ancient ivory dug from the tundra, dense and cool. It outlasts the blade and "
           "impresses anyone who sees it, and it is slick in the hand.")
entry("darkwood-haft", pieces={"weapon": ["haft"]},
      weapon=[B(gm("weight_pct", -50, note="only where the wood is the main piece: a "
                                           "wholly wooden weapon, as the book requires")),
              cm("attack", 2), cm("damage", -2)],
      working=wk("easily_worked"),
      text="Wood as dark as coffee and half the weight of oak. On a wholly wooden weapon "
           "the book halves its weight; as a haft under a metal head the book gives "
           "nothing, so here it is quick in the hand and light behind the blow.",
      legacy=[{"type": "narrative",
               "target": "Half weight on a wholly wooden weapon (the book gives a haft "
                         "alone no benefit)"}])
entry("ironwood-haft", pieces={"weapon": ["haft"]},
      weapon=[gm("hardness", 3), gm("hp_per_inch", 2), gm("weight_pct", 20)],
      working=wk("narrow_window"),
      text="Wood worked by druidic rite until it answers as steel: as hard and tough, and "
           "heavier than plain wood. It is still wood in the eyes of oath and spell, and "
           "rust never touches it.")
entry("wyroot-haft", pieces={"weapon": ["haft"]},
      weapon=[_with({"type": "temp_hp", "dice": "1", "recipient": "self",
                     "trigger": "crit", "duration": {"amount": 1, "unit": "day"},
                     "note": "house approximation of the book's stored life point; "
                             "gone at dusk"}, PER_DAY),
              cm("attack", 2), gm("hp_per_inch", -2)],
      working=wk("malleable"),
      text="Root-wood that refuses to finish dying. A confirmed critical through a wyroot "
           "haft gives its wielder a spark of life once a day, and the haft swings true "
           "but is weaker than ash. The book stores a point for ki or arcane pools, "
           "which the app does not have.",
      legacy=[])
entry("dragonhide-grip", pieces={"weapon": ["haft"]}, material="red-dragonhide",
      weapon=[res("fire", 3), cm("cmd", 2), cm("attack", -2)],
      working=wk("narrow_window"),
      text="Red dragonhide, supple where scale meets scale. The grip shrugs off flame, so "
           "its wielder does too, and it holds the weapon fast, but the scale is slick "
           "under a swing. The book's dragonhide is for armour and shields.",
      legacy=[{"type": "resistance", "target": "fire", "amount": 1,
               "note": "a red dragonhide grip, to its wielder"}])
entry("angelskin-binding", pieces={"armour": ["lining"]},
      armour=[sv("will", 3), cm("ac", 2), sk("diplomacy", -3)],
      working=wk("pure"),
      text="Pale leather from a celestial's remains. Bound inside armour it steadies the "
           "wearer's will and turns blows, and anyone who learns what it is trusts them "
           "less. The book's angelskin dims an evil aura, which the app does not model.",
      legacy=[])
entry("fiend-bone-core", pieces={"weapon": ["haft"]}, risky=True,
      weapon=[cm("initiative", 3), cm("attack", 2), sv("will", -3)],
      working=wk("reactive"),
      text="A rod of fiend's bone set down the spine of a haft. The weapon swings a "
           "half-thought ahead of its wielder, quick and true, and it whispers: the "
           "wielder's will weakens. Assaying it is dangerous.",
      legacy=[])

# ---- treatments: finishes laid over the item ------------------------------------------------

entry("bluing", finishes=["weapon", "armour"],
      weapon=[gm("hp_per_inch", 1, note="rust has nowhere to start")],
      armour=[gm("hp_per_inch", 1, note="rust has nowhere to start")],
      working=wk("easily_worked", "forgiving"),
      text="A controlled black-blue oxide raised over the steel. Rust has nowhere to "
           "start, so the piece lasts a little longer. Quick and forgiving to apply.",
      legacy=[])
entry("oil-blackening", finishes=["weapon", "armour"],
      weapon=[sk("stealth", 1, bonus="untyped", note="a blackened piece throws no glint")],
      armour=[sk("stealth", 1, bonus="untyped", note="a blackened piece throws no glint")],
      working=wk("easily_worked"),
      text="The piece is heated and plunged in oil until it carries a dead-black skin. "
           "It throws no glint, which is worth a point of Stealth.",
      legacy=[{"type": "skill_mod", "amount": 1, "bonus_type": "untyped",
               "target": "stealth", "note": "a blackened piece throws no glint"}])
entry("acid-etching", finishes=["weapon", "armour"],
      weapon=[sk("diplomacy", 1, bonus="untyped", note="a maker's mark and provenance")],
      armour=[sk("diplomacy", 1, bonus="untyped", note="a maker's mark and provenance")],
      working=wk("narrow_window"),
      text="Wax resist and aqua fortis, biting a design or a maker's mark into the "
           "steel. A marked piece carries its provenance, worth a point of Diplomacy. "
           "The acid bites fast.")
entry("cold-iron-blanching", finishes=["weapon"], price_gp=20,
      weapon=[B(sa("cold_iron", uses="once", uses_count=1,
                   note="weapon blanch: until the weapon next hits; one dose coats one "
                        "weapon or 10 pieces of ammunition"))],
      working=wk("easily_worked", "forgiving"),
      text="The book's weapon blanch: powdered cold iron melted over an edge in a round "
           "of flame. The weapon strikes as cold iron until it next hits, and then it is "
           "only steel again. One dose coats a weapon or ten arrows.",
      legacy=[{"type": "narrative",
               "target": "Strikes as cold iron until the weapon next hits"}])
entry("ghost-salt-blanching", finishes=["weapon"],
      weapon=[cm("damage", 2, bonus="untyped", when=vs("undead"), uses="once",
                 uses_count=1,
                 note="house stand-in: the book's full damage to incorporeal creatures "
                      "has no vocabulary yet")],
      working=wk("narrow_window", "pure"),
      text="A white alchemical crust worked over the striking surface. In the book it "
           "lets a weapon deal full damage to incorporeal creatures until it next hits; "
           "the app cannot yet say that, so here it bites the undead harder for one hit.",
      legacy=[{"type": "narrative",
               "target": "Deals full damage to incorporeal creatures until the weapon "
                         "next hits"}])
entry("alchemical-silver-plating", finishes=["weapon"],
      not_on=["adamantine", "cold-iron", "mithral"],
      weapon=[B(sa("silver")),
              B(cm("damage", -1, bonus="untyped", when={"weapon": {"slashing_or_piercing": True}},
                   note="slashing or piercing only, minimum 1"))],
      working=wk("narrow_window"),
      text="Silver alchemically bonded over a steel core. The weapon strikes as silver, "
           "through the defences of lycanthropes and devils, and a slashing or piercing "
           "edge loses a point of damage. The book forbids it on adamantine, cold iron "
           "and mithral.",
      legacy=[{"type": "combat_mod", "amount": -1, "bonus_type": "untyped",
               "target": "damage", "note": "slashing or piercing only, minimum 1"},
              {"type": "narrative",
               "target": "Strikes as silver; cannot be applied to adamantine, cold iron "
                         "or mithral"}])
entry("gold-gilding", finishes=["weapon", "armour"],
      weapon=[sk("diplomacy", 2, bonus="untyped")],
      armour=[sk("diplomacy", 2, bonus="untyped")],
      working=wk("easily_worked", "malleable"),
      text="Gold leaf burnished onto the finished piece. It stops no blow; it announces "
           "the owner across a room, which is worth two points of Diplomacy.")
entry("lead-lining", finishes=["armour"],
      armour=[sv("will", 1, bonus="untyped", note="against scrying and divination: a "
                                                  "house stand-in for the lead's block"),
              gm("weight_pct", 10)],
      working=wk("easily_worked", "malleable"),
      text="Sheet lead beaten into the inner faces of a helm or breastplate. Scrying stops "
           "at the lead: the wearer's will is a point harder to reach, and the armour a "
           "tenth heavier.",
      legacy=[])
entry("holy-anointing", finishes=["weapon"],
      weapon=[cm("damage", 2, bonus="untyped", when=vs("undead"), uses="once",
                 uses_count=1, note="its first battle after the rite")],
      working=wk("pure", "flawless"),
      text="The finished work is oiled, censed and blessed at an altar. For its first "
           "battle after the rite it bites the undead harder; the rites do not last.",
      legacy=[])
entry("adamantine-edging", finishes=["weapon"],
      weapon=[sa("adamantine", note="a house rule: the book gives a part-made edge no "
                                    "benefit"),
              gm("hp_per_inch", -2, note="the weld line")],
      working=wk("narrow_window", "weld_aid"),
      text="A ribbon of adamantine forge-welded along a lesser blade's edge. Here the "
           "weapon strikes as adamantine, a house rule, since the book gives a part-made "
           "edge nothing; the weld line is a weakness a hard parry finds.",
      legacy=[])

# ---- the other shelves: "one material, many shelves" ---------------------------------------

LINKS = {
    "alchemist-materials": {
        "iron-filings": "iron", "lead-dust": "lead", "cinnabar": "quicksilver",
        "powdered-silver": "silver", "mithral-dust": "mithral",
        "star-iron-dust": "star-iron", "adamantine-crucible": "adamantine",
        "iron-flask": "iron", "brass-casing": "brass",
    },
    "enchanter-materials": {
        "silver-ink": "silver", "quicksilver-ink": "quicksilver", "auric-ink": "gold",
        "true-silver-shavings": "mithral", "mithral-filings": "mithral",
        "adamantine-dust": "adamantine",
    },
    "leatherworker-materials": {
        "iron-buckle": "iron", "brass-buckle": "brass", "steel-studs": "steel",
        "bronze-rings": "bronze", "silver-clasps": "silver",
        "cold-iron-studs": "cold-iron", "mithral-fittings": "mithral",
        "adamantine-buckles": "adamantine",
    },
}

NOTE = ("Tier follows the worldclass ladder: common/uncommon/rare/exotic/legendary. The "
        "forge reads `pieces`, `weapon`, `armour`, `working` and `quench_mark` through "
        "rules/materials.py (docs/blacksmithing-contracts.md §3); effects marked "
        "\"book\": true are printed PF1e rules, applied from the main piece only and never "
        "scaled, and every other number is a house modifier for the owner's review "
        "(docs/blacksmithing-review.md). `effects` is the pre-revamp flat list that "
        "rules/blacksmith.py still reads until its bench moves to the new fields. "
        "`weight_factor` is the old weight multiplier the same reader uses. `source` is "
        "how a smith gets it: mined, bought, harvested or monster.")

FORGE_FIELDS = ("form", "material", "pieces", "weapon", "armour", "working", "quench_mark",
                "book", "feeds", "finishes", "not_on", "enchant_surcharge_gp")


def build(raw: dict) -> dict:
    """The entry with this pass's fields written over it; identity fields untouched."""
    spec = ENTRIES[raw["id"]]
    out = {k: v for k, v in raw.items() if k not in FORGE_FIELDS}
    out["text"] = spec["text"]
    if "legacy" in spec:
        out["effects"] = spec["legacy"]
    for k in ("risky", "price_gp"):
        if k in spec:
            out[k] = spec[k]
    if raw["kind"] == "ore":
        out["form"] = "ore"
    if spec.get("material"):
        out["material"] = spec["material"]
    if spec.get("pieces"):
        out["pieces"] = {g: list(p) for g, p in spec["pieces"].items()}
    for gear in ("weapon", "armour"):
        if spec.get(gear):
            out[gear] = spec[gear]
    out["working"] = spec["working"]
    if spec.get("quench_mark"):
        out["quench_mark"] = spec["quench_mark"]
    for k in ("feeds", "finishes", "not_on"):
        if spec.get(k):
            out[k] = list(spec[k])
    if spec.get("enchant_surcharge_gp"):
        out["enchant_surcharge_gp"] = spec["enchant_surcharge_gp"]
    has_book = any(e.get("book") for g in ("weapon", "armour") for e in spec.get(g) or [])
    out["book"] = has_book
    return out


def main() -> int:
    apply = "--apply" in sys.argv
    path = MAT_DIR / "blacksmith-materials.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    raws = data["materials"]
    ids = [r["id"] for r in raws]
    missing = [i for i in ids if i not in ENTRIES]
    extra = [i for i in ENTRIES if i not in ids]
    if missing or extra:
        print(f"table and file disagree: missing {missing}, unknown {extra}")
        return 1

    new = [build(r) for r in raws]
    for before, after in zip(raws, new):
        for k in ("id", "name", "kind", "tier"):
            assert before[k] == after[k], (before["id"], k)

    # Validate against the shelf as it will be, so links resolve to the new documents.
    others = {}
    for stem, links in LINKS.items():
        other = json.loads((MAT_DIR / f"{stem}.json").read_text(encoding="utf-8"))
        known = {m["id"] for m in other["materials"]}
        bad = [k for k in links if k not in known]
        if bad:
            print(f"{stem}: no such ids {bad}")
            return 1
        for m in other["materials"]:
            if m["id"] in links:
                m["material"] = links[m["id"]]
        others[stem] = other

    shelf = {d["id"]: materials.normalise(d, materials.FORGE_CATALOGUE) for d in new}
    for stem, other in others.items():
        for m in other["materials"]:
            shelf.setdefault(m["id"], materials.normalise(m, stem))
    problems = []
    for doc in new:
        problems.extend(materials.validate(shelf[doc["id"]], shelf=shelf))
    for stem, links in LINKS.items():
        for mid in links:
            problems.extend(materials.validate(shelf[mid], shelf=shelf))
    if problems:
        print(f"{len(problems)} problem(s); nothing written:")
        for p in problems:
            print("  " + p)
        return 1

    by_kind: dict[str, int] = {}
    effects = 0
    for doc in new:
        by_kind[doc["kind"]] = by_kind.get(doc["kind"], 0) + 1
        effects += len(doc.get("weapon") or []) + len(doc.get("armour") or [])
    print(f"{len(new)} materials valid; {effects} item effects; by kind {by_kind}")
    if not apply:
        print("dry run: pass --apply to write")
        return 0

    data["note"] = NOTE
    data["materials"] = new
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for stem, links in LINKS.items():
        # Inserted as one line after each linked entry's id, not re-dumped: the three
        # sibling files are formatted three different ways, and rewriting a file the
        # pass does not own to add nine fields would bury those nine in a whole-file diff.
        other = MAT_DIR / f"{stem}.json"
        text = other.read_text(encoding="utf-8")
        for mid, parent in links.items():
            text = _link(text, mid, parent)
        json.loads(text)                     # still JSON, or nothing is written
        other.write_text(text, encoding="utf-8")
    print("written")
    return 0


def _link(text: str, mid: str, parent: str) -> str:
    """`"material": parent` on the line after `"id": mid`, replacing any earlier link."""
    import re

    pattern = re.compile(r'^([ \t]*)"id": "' + re.escape(mid) + r'",\n'
                         r'(?:[ \t]*"material": "[^"]*",\n)?', re.M)
    found = pattern.search(text)
    if not found:
        raise SystemExit(f"cannot find {mid!r} to link")
    indent = found.group(1)
    line = f'{indent}"id": "{mid}",\n{indent}"material": "{parent}",\n'
    return text[:found.start()] + line + text[found.end():]


if __name__ == "__main__":
    raise SystemExit(main())
