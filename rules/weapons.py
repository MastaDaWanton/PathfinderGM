"""Every weapon, shipped and authored.

`tables.WEAPONS` held eleven weapons as Python — enough for the pregenerated characters and
nothing else. A player who wanted a glaive got `KeyError: no such weapon 'glaive'`.

`content/weapons/weapons.json` holds 456, and the layering runs the *opposite* way to the
class overlay on purpose: the imported file provides the base and the eleven hand-written
entries merge on top of it. Those eleven are the curated ones — their `finessable` and
`hands` values are what several hundred tests are written against — and a bulk import
silently changing the rapier's crit range would be a real regression discovered in play.
Everything the file adds beyond them is new, so nothing it says can break anything.

Homebrew layers last, as it does everywhere else.

**One name, one row (2026-09-30).** There were two weapon tables and two answers to "is
this a weapon": `goods.kind_of` asked the curated twelve, the attack op and the shops asked
the 456. So the weaponsmith sold 356 weapons and `wear` refused 348 of them ("bo-staff is
not something that can be worn or wielded"), and the curated "shortsword" and "light
crossbow" were second rows beside the file's "short-sword" and "light-crossbow" — the same
sword at two keys, one with a price and one without. Now the curated entries merge INTO
the file's row (`ALIASES`), every name a player, a GM or a save can write resolves through
`key_for` to the one key, and `wieldable` is the one answer both the `wear` op and the
Equipment tab's button ask (docs/playtest-2026-09-30-findings.md item 2, E1).

`weapons_rules.json` beside the imported file carries what the import could not know —
which ammunition a launcher fires, the rows that are ammunition and not weapons, why a row
cannot be wielded — as a separate overlay, because `tools/build_weapons.py` rewrites
`weapons.json` from the workbook and an edit made there would be lost on the next import.
It sorts after `weapons.json`, so it layers on top.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .tables import WEAPONS as SHIPPED
from pathfindergm import files

_ALL: dict[str, dict] | None = None
_META: dict = {}
_INDEX: tuple[int, dict[str, str]] | None = None

# Curated keys whose row in the imported file has another id. The curated entry merges
# onto that row and its key answers as an alias, so the 3 tests and the fixture written
# against "shortsword" and "light crossbow" keep working and the shop sells one sword.
# The other ten curated keys already ARE the file's ids.
ALIASES: dict[str, str] = {
    "shortsword": "short-sword",
    "light crossbow": "light-crossbow",
    # Ammunition by its plain English name: "arrows", "a quiver of arrows", "bolts".
    "arrow": "arrows-20", "arrows": "arrows-20", "quiver of arrows": "arrows-20",
    "bolt": "crossbow-bolts-10", "bolts": "crossbow-bolts-10",
    "crossbow bolt": "crossbow-bolts-10", "crossbow bolts": "crossbow-bolts-10",
    "sling bullet": "sling-bullets-10", "sling bullets": "sling-bullets-10",
    "sling stones": "sling-bullets-10", "blowgun dart": "blowgun-darts-10",
    "blowgun darts": "blowgun-darts-10", "firearm bullets": "firearm-bullet-1",
    # The CRB monk's list says "crossbow (light or heavy)"; the bare word is the light one.
    "crossbow": "light-crossbow",
}

# Sections the weaponsmith does not stock (owner's ruling E5, 2026-09-30): engines of war
# are not shop goods, and the "(Modern)" rows are machine guns and grenades from another
# century. Still in the table — a world may write a cannon — just never on a shelf.
UNSOLD_SECTION = re.compile(r"siege|\(modern\)", re.I)
# The sections whose rows are ammunition rather than weapons in hand (E3).
AMMO_SECTIONS = ("Ammunition", "Firearm Ammunition / Gear", "Siege Weapon Ammunition",
                 "Siege Engines (Ammunition)")
_COUNT = re.compile(r"\s*\((\d+)(?:\s+[a-z]+)?\)\s*$")


def _shipped_folder() -> Path:
    from django.conf import settings

    return Path(settings.BASE_DIR) / "content" / "weapons"


def _homebrew_folders() -> list[Path]:
    """Where a table's own weapons live: `homebrew/weapons/`, which the weapon bench
    saves to, and `homebrew/items/`, which the bench saved to until 2026-10-01 and no
    code read — kept so an edit made before the move is not lost to it."""
    from django.conf import settings

    home = Path(settings.CAMPAIGN_DIR).parent / "homebrew"
    return [home / "items", home / "weapons"]


# What the old "Items, weapons & armour" bench could write that is not a weapon. Such a
# file in `homebrew/items/` has no table to reach (armour and shields are hand-written in
# `rules/tables.py` with no homebrew layer), and reading it as a weapon would be worse.
_NOT_WEAPONS = frozenset({"armour", "armor", "shield", "gear"})


def _read(folder: Path, *, homebrew: bool) -> list[dict]:
    if not folder.is_dir():
        return []
    out: list[dict] = []
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            files.unreadable(path, exc)
            continue
        entries = data.get("weapons") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            entries = [data] if isinstance(data, dict) and data.get("id") else []
        if isinstance(data, dict) and not homebrew:
            _META.update({k: v for k, v in data.items() if k != "weapons"})
        out += [e for e in entries if isinstance(e, dict)
                and not (homebrew and str(e.get("kind", "")).lower() in _NOT_WEAPONS)]
    return out


def all_weapons() -> dict[str, dict]:
    global _ALL, _META
    if _ALL is None:
        out: dict[str, dict] = {}

        def merge(entries: list[dict], *, homebrew: bool) -> None:
            for e in entries:
                key = str(e.get("id") or e.get("name", "")).strip().lower()
                if not key:
                    continue
                # A homebrew file keyed the curated way ("shortsword") corrects the one
                # row rather than standing beside it as a second sword.
                if homebrew:
                    key = ALIASES.get(key, key)
                    e = {**e, "id": key}
                # Merged, not replaced: a homebrew edit touching one field must not drop
                # the twenty it never mentioned.
                out.setdefault(key, {}).update(e)
                out[key].setdefault("name", e.get("name", key))

        merge(_read(_shipped_folder(), homebrew=False), homebrew=False)

        # The hand-written eleven win over the import. See the module docstring. A
        # curated key the file spells differently lands on the file's row (`ALIASES`),
        # never beside it.
        for key, entry in SHIPPED.items():
            row = ALIASES.get(key, key)
            out.setdefault(row, {}).update(entry)
            out[row].setdefault("id", row)

        # And homebrew over both, as the docstring always said. It ran before the eleven
        # until 2026-10-01, so a homebrew rapier with a 15-20 threat came back 18-20 —
        # an edit to any of the eleven silently overwritten
        # (tests/test_homebrew_weapons_reach_play.py).
        for folder in _homebrew_folders():
            merge(_read(folder, homebrew=True), homebrew=True)

        for entry in out.values():
            entry.setdefault("traits", [])
            entry.setdefault("category", "melee")
            entry.setdefault("hands", 1)
            entry.setdefault("prof", "martial")
            entry.setdefault("crit_range", 20)
            entry.setdefault("crit_mult", 2)
            entry.setdefault("type", "untyped")
            entry.setdefault("finessable", False)
        _ALL = out
    return _ALL


def forget() -> None:
    """Drop the table so the next read sees a file the weapon bench just saved."""
    global _ALL, _INDEX
    _ALL = None
    _INDEX = None


def meta() -> dict:
    all_weapons()
    return dict(_META)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")


def _index() -> dict[str, str]:
    """Every spelling that names a row -> the row's key. Built once per table."""
    global _INDEX
    table = all_weapons()
    if _INDEX is not None and _INDEX[0] == id(table):
        return _INDEX[1]
    idx: dict[str, str] = {}

    def add(spelling: str, key: str) -> None:
        for s in (" ".join(str(spelling).lower().split()), _slug(spelling)):
            if s and s not in idx:
                idx[s] = key

    for key in table:                      # the keys themselves first: they always win
        add(key, key)
    for key, row in table.items():         # then display names
        add(str(row.get("name") or ""), key)
    for key, row in table.items():         # then a bundle's name without its count
        name = str(row.get("name") or "")
        if _COUNT.search(name):
            add(_COUNT.sub("", name), key)
        bare = re.sub(r"-\d+$", "", key)
        if bare != key:
            add(bare, key)
    for alias, key in ALIASES.items():
        if key in table:
            add(alias, key)
    _INDEX = (id(table), idx)
    return idx


def key_for(text: str) -> str:
    """The one key a weapon or a round of ammunition is stored under, or "".

    Accepts whatever names it: the key ("bo-staff"), the display name ("Bo staff"), title
    case, a hyphen or a space ("short sword", "light-crossbow"), a bundle's count ("Arrows
    (20)", "arrows-20", "arrows"), and a curated alias ("shortsword"). A leading article
    or "my" goes first ("my longbow"), and a plural last ("longbows"). Never a guess past
    that: an unknown word is "", and the caller files it as gear rather than as the
    nearest weapon (CLAUDE.md, "ground every name").
    """
    raw = " ".join(str(text or "").lower().split())
    if not raw:
        return ""
    idx = _index()
    raw = re.sub(r"^(?:a|an|the|my|his|her|their|some)\s+", "", raw)
    for cand in (raw, _COUNT.sub("", raw), raw[:-1] if raw.endswith("s") else ""):
        if not cand:
            continue
        for s in (cand, _slug(cand)):
            if s in idx:
                return idx[s]
    return ""


def get(key: str) -> dict:
    found = all_weapons().get(key_for(key))
    if found is None:
        raise KeyError(f"no such weapon {key!r}")
    return found


def has(key: str) -> bool:
    return bool(key_for(key))


# --- what a row IS: a weapon to hold, ammunition to loose, or neither ------------------

def is_ammunition(key: str) -> bool:
    """A round to be loosed from a launcher, never held and never swung (E3).

    The CRB's Ammunition rows and the later books' firearm and siege ammunition, by the
    section the import filed them under — plus anything the overlay names a round of a
    family (`ammo_of`). The import gave all 72 of them `prof: exotic` and a sheet attack
    row, so a quiver of arrows was "+20 to hit, damage ''" on Sam's sheet."""
    k = key_for(key)
    if not k:
        return False
    row = all_weapons()[k]
    if row.get("not_ammo"):
        return False
    return bool(row.get("ammo_of")) or str(row.get("section") or "") in AMMO_SECTIONS


def ammo_families(key: str) -> list[str]:
    """What this launcher fires — `["arrows"]` for a bow — or [] for anything that is not
    a launcher. The overlay states it per row (`ammo`); see `weapons_rules.json`."""
    k = key_for(key)
    return [str(f) for f in (all_weapons()[k].get("ammo") or [])] if k else []


def family_of(key: str) -> str:
    """Which family a round belongs to ("arrows"), or ""."""
    k = key_for(key)
    return str(all_weapons()[k].get("ammo_of") or "") if k else ""


def rounds_per(key: str) -> int:
    """How many rounds one of this row is: "Arrows (20)" is twenty, a "Smoke arrow" one.

    The overlay may say (`per`), else the count printed in the name, else one."""
    k = key_for(key)
    if not k:
        return 1
    row = all_weapons()[k]
    if row.get("per"):
        return max(1, int(row["per"]))
    m = re.search(r"\((\d+)", str(row.get("name") or ""))
    return max(1, int(m.group(1))) if m else 1


def round_name(key: str, count: int = 1) -> str:
    """"arrows" / "arrow", "crossbow bolts", for a tell: the family, never "Arrows (20)"."""
    fam = family_of(key) or _COUNT.sub("", str(get(key)["name"])).lower()
    if count == 1 and fam.endswith("s") and not fam.endswith("ss"):
        return fam[:-1]
    return fam


def is_launcher(key: str) -> bool:
    return bool(ammo_families(key))


def wieldable(key: str) -> tuple[bool, str]:
    """Can this be put in hand by the `wear` op: (True, "") or (False, why, in words).

    The ONE answer, asked by `Engine._op_wear` and by the Equipment tab's row
    (`play/views.py:_carried`), so a Wield button appears exactly when the op would take
    it. Before 2026-09-30 the button asked `goods.kind_of` and the op asked it too, and
    both said no to 348 of the 356 weapons the smith sold — while the attack op, which
    asked `weapons.has`, would have swung any of them.
    """
    k = key_for(key)
    if not k:
        return False, "The rules have no weapon by that name."
    row = all_weapons()[k]
    if is_ammunition(k):
        what = family_of(k)
        return False, ("Ammunition" + (f" ({what})" if what else "") + ": loosed from a "
                       "launcher, never held. Wield the launcher and it shoots these.")
    if row.get("unwieldable"):
        return False, str(row["unwieldable"])
    return True, ""


def first_end_damage(dice: str) -> str:
    """A double weapon's damage as one die: "1d6/1d6" -> "1d6" (E2).

    The table prints both ends, and `Dice.roll` raised `BadDice` on the slash: 16 of the
    weapons the smith sold, the bo staff among them, could not deal a point. One end per
    swing is what 1e means — the other end is the off hand's, which is two-weapon
    fighting and a later batch (owner's ruling E6). The text stays "1d6/1d6" for the
    sheet to show."""
    text = str(dice or "").strip()
    return text.split("/")[0].strip() if "/" in text else text


def described(key: str) -> str:
    """What the thing in the hand IS, in the table's own words, for a prompt:
    "a light one-handed bludgeoning weapon: weighted head, wrapped grip".

    Built from the row, never hand-written per weapon. Measured live 2026-09-27: told
    "In hand: the sap", the local model wrote "the heavy vial of sap" and "the sticky
    liquid splashes wide" — a sap is a leather cosh, and the bare word reads as tree
    sap. Every weapon whose name is also an ordinary word (sap, flail, pick, star) is
    the same trap; the row already knows it has a weighted head. "" for anything the
    table does not hold.
    """
    if not has(key):
        return ""
    row = get(key)
    ranged = row.get("category") == "ranged"
    hands = int(row.get("hands") or 1)
    # The hand count only for melee: the table lists a longbow as one hand, which is
    # what it takes to carry, not to draw.
    grip = "" if ranged else ("two-handed" if hands >= 2 else "one-handed")
    words = " ".join(w for w in ("light" if row.get("light") else "", grip,
                                 str(row.get("type") or ""), "ranged" if ranged else "")
                     if w)
    parts = [str(v).lower() for v in (row.get("components") or {}).values() if v]
    return f"a {words} weapon" + (f": {', '.join(parts)}" if parts else "")


def has_trait(key: str, trait: str) -> bool:
    """Does this weapon carry that special quality — `reach`, `trip`, `brace`?

    Tolerant of a missing weapon rather than raising, because the callers are asking a
    question about geometry and "no weapon, so no reach" is the right answer for an
    unarmed creature.
    """
    try:
        weapon = get(key)
    except KeyError:
        return False
    return trait.strip().lower() in [t.lower() for t in weapon.get("traits", [])]


def lethality_of(weapon: dict) -> str:
    """What this weapon deals when nobody says otherwise: "lethal" or "nonlethal".

    Asked of the weapon record the sheet built, not of a key, because the record is
    what knows: a natural bite and a granted blood gauntlet are both built on the
    unarmed strike and say `nonlethal: False` for themselves, and a printed "(1d6+1
    nonlethal)" says True. An explicit flag wins; otherwise the weapon's special
    quality does — the content file writes the sap, whip, bolas and slaver's crossbow
    as `traits: ["nonlethal"]` and the slice table wrote a bool, and until this one
    reader existed neither was read by anything: a punch and a sap took hit points
    (measured 2026-09-27: a punch 13 -> 4 hp, a sap 9 -> 1, nonlethal 0 both times).
    """
    if "nonlethal" in weapon:
        return "nonlethal" if weapon.get("nonlethal") else "lethal"
    traits = [str(t).strip().lower() for t in weapon.get("traits") or ()]
    return "nonlethal" if "nonlethal" in traits else "lethal"


# --- size and groups: what a class feature asks of a weapon ------------------------------

# A Medium weapon's die at Small and Large size: Core Rulebook Table 6-5 ("Tiny and Large
# Weapon Damage"), the progression the monk's own table follows for his fists (CRB, Monk,
# "Table: Small or Large Monk Unarmed Damage": 1d6 -> 1d4 / 1d8 at 1st, 2d10 -> 2d8 / 4d8
# at 20th — checked row by row against AoN's monk table, 2026-10-05). Only the three sizes
# the monk table prints; any other size keeps the Medium die rather than inventing a step.
SIZE_DIE: dict[str, dict[str, str]] = {
    "1d2": {"small": "1", "large": "1d3"},
    "1d3": {"small": "1d2", "large": "1d4"},
    "1d4": {"small": "1d3", "large": "1d6"},
    "1d6": {"small": "1d4", "large": "1d8"},
    "1d8": {"small": "1d6", "large": "2d6"},
    "1d10": {"small": "1d8", "large": "2d8"},
    "1d12": {"small": "1d10", "large": "3d6"},
    "2d4": {"small": "1d6", "large": "2d6"},
    "2d6": {"small": "1d10", "large": "3d6"},
    "2d8": {"small": "2d6", "large": "3d8"},
    "2d10": {"small": "2d8", "large": "4d8"},
}


def size_die(medium: str, size: str) -> str:
    """A Medium die at this body's size: `size_die("1d8", "small")` is "1d6"."""
    die = " ".join(str(medium or "").split()).lower()
    return SIZE_DIE.get(die, {}).get(str(size or "medium").strip().lower(), die)


# The fighter's weapon groups (CRB, Fighter, "Weapon Training"; the consolidated list at
# aonprd.com/FighterWeapons.aspx, fetched 2026-10-05, which adds the later books' weapons
# to the Core groups). Written by NAME, the way the page writes them, and resolved through
# `key_for` when asked — a name the table does not carry (several later-book exotics) is
# skipped, never matched to the nearest weapon. "Firearms" is every row the import filed
# under a Firearms section; siege engines are not weapons in hand and are left out.
GROUPS: dict[str, tuple[str, ...]] = {
    "axes": ("bardiche", "battleaxe", "boarding axe", "butchering axe", "dwarven waraxe",
             "gandasa", "greataxe", "handaxe", "heavy pick", "hooked axe", "knuckle axe",
             "kumade", "light pick", "mattock", "orc double axe", "pata", "throwing axe",
             "tongi"),
    "heavy blades": ("aldori dueling sword", "ankus", "bastard sword", "chakram", "cutlass",
                     "double chicken saber", "double walking stick katana",
                     "elven curve blade", "estoc", "falcata", "falchion", "flambard",
                     "great terbutje", "greatsword", "katana", "khopesh", "klar",
                     "longsword", "nine-ring broadsword", "nodachi", "rhoka sword",
                     "sawtooth sabre", "scimitar", "scythe", "seven-branched sword",
                     "shotel", "sickle-sword", "split-blade sword", "switchscythe",
                     "temple sword", "terbutje", "two-bladed sword"),
    "light blades": ("bayonet", "broken-back seax", "butterfly knife", "butterfly sword",
                     "chakram", "dagger", "deer horn knife", "dogslicer", "dueling dagger",
                     "gladius", "hunga munga", "kama", "katar", "kerambit", "kukri",
                     "machete", "manople", "pata", "quadrens", "rapier", "sanpkhang",
                     "sawtooth sabre", "scizore", "short sword", "sica", "sickle",
                     "spiral rapier", "starknife", "sword cane", "swordbreaker dagger",
                     "wakizashi", "war razor"),
    "bows": ("composite longbow", "composite shortbow", "hornbow (orc)", "longbow",
             "shortbow"),
    "close": ("bayonet", "brass knuckles", "cestus", "dan bong", "emei piercer",
              "fighting fan", "gauntlet", "heavy shield", "iron brush", "katar",
              "katar (tri-bladed)",
              "klar", "light shield", "mere club", "punching dagger", "rope gauntlet",
              "sap", "scizore", "spiked armor", "spiked gauntlet", "spiked heavy shield",
              "spiked light shield", "tekko-kagi", "tonfa", "unarmed strike",
              "waveblade", "wooden stake", "wushu dart"),
    "crossbows": ("double crossbow", "hand crossbow", "heavy crossbow",
                  "launching crossbow", "light crossbow", "repeating hand crossbow",
                  "repeating heavy crossbow", "repeating light crossbow",
                  "tube arrow shooter", "underwater heavy crossbow",
                  "underwater light crossbow"),
    "double": ("bo staff", "boarding gaff", "chain spear", "chain-hammer", "dire flail",
               "double walking stick katana", "double-chained kama", "dwarven urgrosh",
               "gnome hooked hammer", "kusarigama", "monk's spade", "orc double axe",
               "quarterstaff", "taiaha", "two-bladed sword", "weighted spear"),
    "flails": ("battle poi", "bladed scarf", "cat-o'-nine-tails", "chain spear",
               "dire flail", "double-chained kama", "flying blade", "flying talon",
               "gnome pincher", "halfling rope-shot", "heavy flail", "kusarigama",
               "kyoketsu shoge", "light flail", "meteor hammer", "morningstar",
               "nine-section whip", "nunchaku", "sansetsukon", "scorpion whip",
               "spiked chain", "urumi", "whip"),
    "hammers": ("aklys", "battle aspergillum", "chain-hammer", "club", "earth breaker",
                "greatclub", "heavy mace", "lantern staff", "light hammer", "light mace",
                "mere club", "planson", "taiaha", "tetsubo", "wahaika", "warhammer"),
    "monk": ("bo staff", "brass knuckles", "butterfly sword", "cestus", "dan bong",
             "deer horn knife", "double chicken saber", "double-chained kama",
             "emei piercer", "fighting fan", "hanbo", "jutte", "kama", "kusarigama",
             "kyoketsu shoge", "lungchuan tamo", "monk's spade", "nine-ring broadsword",
             "nine-section whip", "nunchaku", "quarterstaff", "rope dart", "sai",
             "sanpkhang", "sansetsukon", "seven-branched sword", "shang gou", "shuriken",
             "siangham", "temple sword", "tiger fork", "tonfa", "traveling kettle",
             "tri-point double-edged sword", "unarmed strike", "urumi", "wushu dart"),
    "natural": ("unarmed strike",),
    "polearms": ("bardiche", "bec de corbin", "bill", "boarding gaff", "crook", "fauchard",
                 "glaive", "glaive-guisarme", "guisarme", "halberd", "hooked lance",
                 "horsechopper", "lucerne hammer", "mancatcher", "monk's spade",
                 "naginata", "nodachi", "ogre hook", "ranseur", "tiger fork"),
    "spears": ("amentum", "boar spear", "chain spear", "double spear",
               "elven branched spear", "harpoon", "javelin", "lance", "longspear",
               "orc skull ram", "pilum", "planson", "shortspear", "sibat", "spear",
               "stormshaft javelin", "tiger fork", "trident", "weighted spear"),
    "thrown": ("aklys", "amentum", "atlatl", "blowgun", "bolas", "boomerang",
               "chain-hammer", "chakram", "club", "dagger", "dart", "deer horn knife",
               "dueling dagger", "flask thrower", "halfling sling staff", "harpoon",
               "hunga munga", "javelin", "kestros", "lasso", "light hammer", "net",
               "pilum", "rope dart", "shoanti bolas", "shortspear", "shuriken", "sibat",
               "sling", "sling glove", "snag net", "spear", "starknife",
               "stormshaft javelin", "throwing axe", "throwing shield", "trident",
               "wushu dart"),
    "tribal": ("club", "dagger", "greatclub", "handaxe", "heavy shield", "light shield",
               "shortspear", "spear", "throwing axe", "unarmed strike"),
    "firearms": (),
}
_FIREARM_SECTION = re.compile(r"firearm", re.I)
_GROUP_INDEX: tuple[int, dict[str, frozenset]] | None = None


def groups_of(key: str) -> frozenset:
    """The fighter weapon groups this weapon is in: `groups_of("longsword")` is
    {"heavy blades"}. Built once per table, by name through `key_for`."""
    global _GROUP_INDEX
    table = all_weapons()
    if _GROUP_INDEX is None or _GROUP_INDEX[0] != id(table):
        idx: dict[str, set] = {}
        for group, names in GROUPS.items():
            for name in names:
                k = key_for(name)
                if k:
                    idx.setdefault(k, set()).add(group)
        for k, row in table.items():
            if _FIREARM_SECTION.search(str(row.get("section") or "")) \
                    and "siege" not in str(row.get("section") or "").lower() \
                    and not is_ammunition(k):
                idx.setdefault(k, set()).add("firearms")
        _GROUP_INDEX = (id(table), {k: frozenset(v) for k, v in idx.items()})
    return _GROUP_INDEX[1].get(key_for(key) or str(key or "").lower(), frozenset())


def search(text: str = "", prof: str = "", category: str = "", trait: str = "",
           limit: int = 60) -> list[dict]:
    needle = text.strip().lower()
    out = []
    for weapon in all_weapons().values():
        if prof and weapon.get("prof") != prof.strip().lower():
            continue
        if category and weapon.get("category") != category.strip().lower():
            continue
        if trait and trait.strip().lower() not in [t.lower()
                                                   for t in weapon.get("traits", [])]:
            continue
        if needle and needle not in str(weapon.get("name", "")).lower():
            continue
        out.append(weapon)

    def rank(w: dict) -> tuple:
        low = str(w.get("name", "")).lower()
        if not needle:
            return (0, low)
        return (0 if low == needle else 1 if low.startswith(needle) else 2, low)

    out.sort(key=rank)
    return out[:limit] if limit else out


__all__ = ["all_weapons", "get", "has", "has_trait", "key_for", "meta", "search",
           "wieldable", "is_ammunition", "ammo_families", "family_of", "rounds_per",
           "round_name", "is_launcher", "first_end_damage", "UNSOLD_SECTION",
           "AMMO_SECTIONS"]
