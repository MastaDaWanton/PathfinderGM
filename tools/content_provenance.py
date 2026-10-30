"""Which shipped rules content still names Golarion, and which books those rows came from.

The follow-up measurement to docs/bestiary-licensing.md, read-only: it changes no content.
The owner chose option D for the bestiary on 2026-10-28 (ship the rulebook line, no
Product Identity). The spells, feats and the rest were imported from spreadsheets that span
the whole Pathfinder line, setting books and adventures included, and Paizo's declarations
make "proper names (characters, deities, etc.) ... locations" Product Identity whatever
book they sit in. So the question is not only "which rows come from setting books" but
"which rows name Golarion", and the two have to be counted separately.

    python tools/content_provenance.py              # the summary tables
    python tools/content_provenance.py --sample 40  # plus random hits with context, to hand-check
    python tools/content_provenance.py --rows       # every hit row, for a rewrite worklist

How it decides, and how far to trust it:

- **A Golarion name** is a match against the explicit deny-list below, case-sensitive, on
  word boundaries, possessive allowed. The list was built from docs/bestiary-licensing.md,
  the spreadsheets' own source titles, the spells' `deity` column, and a discovery pass
  over all shipped content (capitalised words that are never written lower-case anywhere,
  read by hand). A name not on the list is missed, so the counts are a floor; a listed
  name that is also an ordinary word is kept off the list rather than guessed at.
- **Classes of name.** `golarion` names are Paizo's own (Iomedae, Cheliax, Hellknight,
  Aram Zey). `myth` names are older than Paizo and were taken into Golarion as deities or
  planes (Asmodeus, Lamashtu, Hastur, Abaddon): the word is nobody's, the Golarion
  character built on it is Paizo's, so they are counted apart and the reader decides.
  `product` is a Paizo product title written into rules text ("detailed in Pathfinder
  Adventure Path #75") — a trademark citation, not setting lore.
- **Ids carry names too.** A spell's id is its slugged name (`abadar-s-truthtelling`), and
  the mechanics files are keyed by those ids, so a row is checked on its id as well.
- **Family** comes from the row's `source` by an explicit table; a source not in the table
  lands in `unclassified` rather than being guessed. Campaign Setting and Player Companion
  are one family here — both are Golarion setting lines, and nothing below turns on which.
  Files written in this project (rules documents, crafts, schemes) carry no book source;
  they are counted by file as `app-authored`.
"""
from __future__ import annotations

import collections
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --- the deny-list -----------------------------------------------------------------------------

# Paizo's Golarion: deities, demigods and their adjectives; places; peoples and languages;
# organisations; characters (iconics included); the calendar and the solar system. Kept to
# names that are never ordinary English, so a match means the name, not a word that
# happens to be capitalised at the start of a sentence.
GOLARION = {
    "deity": """
        Abadar Abadaran Calistria Calistrian Cayden Cailean Caydenite Caydenites Desna
        Desnan Erastil Erastilian Gorum Gorumite Gozreh Iomedae Iomedaean Irori Irorian
        Nethys Nethysian Norgorber Norgorberite Pharasma Pharasmin Rovagug Rovagugite
        Sarenrae Sarenite Shelyn Shelynite Torag Toragdan Urgathoa Urgathoan Zon-Kuthon
        Kuthite Aroden Arodenite Achaekek Alseta Arazni Besmara Brigh Groetus Hanspur
        Kurgess Milani Naderi Sivanah Ydersius Zyphus Ghlaunder Gyronna Nivi Rhombodazzle
        Tsukiyo Shizuru Daikitsu Fumeiyoshi Yamatsumi Kazutal Angazhan Lissala Zursvaater
        Dranngvit Bolka Kols Magrim Trudd Grundinnar Angradd Folgrit Deskari Kostchtchie
        Nocticula Szuriel Trelmarixian Kabriri Cyth-V'sug Areshkagal Mazmezz Socothbenoth
        Treerazer Xoveron Aldinach Gogunta Ragathiel Arshea Ashava Andoletta Dammerich
        Falayna Jaidi Pulura Sinashakti Tolc Vildeis Korada Eritrice Halcamora Lymnieris
        Valani Ylimancha Talmandor Mahathallah Xhamen-Dor Ragdya Lanishra Dretha Zagresh
        Hadregash Zarongel Venkelvore Chaldira Zuzaristan Findeladlara Ketephys Yuelral
        Ranalc Magdh Shyka Imbrex Ayrzul Hshurha Ranginori Kelizandri Ymeri Lysianassa
        Ceyannan Isph-Aun-Vuln Thuskchoon Yamasoth Chavazvug Oaur-Ooung Jezelda Sifkesh
        Andirifkhu Kerkamoth Ghorus Dawnflower Razmir Kalistrade
    """,
    "deity phrase": [
        "Hei Feng", "Lao Shu Po", "Qi Zhong", "Black Butterfly", "Lantern King",
        "Green Mother", "Lost Prince", "the Eldest", "Thamir Gixx", "Mother Vulture",
        "Ardad Lili",
    ],
    "place": """
        Golarion Avistan Garund Casmaron Azlant Thassilon Absalom Alkenstar Andoran Brevoy
        Belkzen Cheliax Galt Geb Irrisen Isger Jalmeray Kyonin Katapesh Lastwall Mendev
        Molthune Mwangi Nidal Nirmathas Numeria Osirion Qadira Rahadoum Razmiran Sargava
        Taldor Thuvia Ustalav Varisia Worldwound Hermea Korvosa Magnimar Riddleport
        Sandpoint Westcrown Egorian Oppara Katheer Sothis Caliphas Kenabres Ravounel Minkai
        Jinin Hongal Lingshen Quain Shokuro Kwanlai Valashmai Hwanggot Nar-Voth Sekamina
        Orv Kortos Sarkoris Highhelm Janderhoff Iobaria Vudra Holomog Nantambu Ilizmagorti
        Bloodcove Eleder Senghor Shory Jistka Lepidstadt Thrushmoor Mechitar Quantium
        Ecanus Nerosyan Whitethrone Restov Rostland Isarn Merab Lamasara Kelesh Iblydos
        Uskwood Viperwall Storval Basalfeyst Kitharodian Jandelay Jandelayan Starstone
        Earthfall Darklands Mushfens Fangwood Cinderlands Mierani Sarzari Witchwood Ird
        Castrovel Akiton Eox Triaxus Verces Aballon Apostae Liavara Bretheda Aucturn
    """,
    "place phrase": [
        "Tian Xia", "Inner Sea", "Lake Encarthan", "Mana Wastes", "River Kingdoms",
        "Five Kings Mountains", "Mammoth Lords", "Linnorm Kings", "Kaer Maga", "Nex",
        "Po Li", "Xa Hoi", "Dtang Ma", "Wall of Heaven", "New Stetven", "Isle of Terror",
        "Nemret Noktoria", "Darkmoon Vale", "Crimson Citadel", "Stolen Lands",
        "the Shackles", "Kho", "Gravelands", "Age of Lost Omens",
    ],
    "people": """
        Varisian Varisians Shoanti Chelaxian Chelaxians Chelish Kellid Kellids Garundi
        Keleshite Keleshites Kelish Ulfen Taldan Taldans Taldane Tian Vudrani Bekyar
        Bonuwat Mauxi Zenj Erutaki Jadwiga Nidalese Azlanti Thassilonian Osiriani Osirian
        Hallit Tien Varki Jistkan Andoren Andorens Irriseni Gebite Gebites Nexian Nexians
        Mendevian Molthuni Galtan Brevic Isgeri Thuvian Katapeshi Qadiran Rahadoumi
        Ustalavic Sarkorian Iobarian Sargavan Aldori Razmiri Numerian Jalmeri Absalomian
        Korvosan Magnimarian Shoki Novotnian Hermean Lissalan
    """,
    "organisation": """
        Hellknight Hellknights Aspis Sczarni Magaambya Arcanamirium Acadamae Riftwardens
        Cyphermage Cyphermages Arclord Arclords Swordlords Kalistrocrat Kalistrocrats
        Decemvirate Pathfinders Venture-Captain Bellflower Ozem Harrow
    """,
    "organisation phrase": [
        "Pathfinder Society", "Pathfinder Lodge", "Grand Lodge", "Aspis Consortium",
        "Red Mantis", "Eagle Knights", "Lion Blades", "Gray Maidens", "Twilight Talons",
        "Whispering Way", "Night Heralds", "Knights of Ozem", "Palatine Eye",
        "Free Captains", "Mendevian Crusade", "Blackfire Adepts", "Sleepless Detectives",
        "Glorious Reclamation", "Brotherhood of Silence", "Lantern Bearers", "Golden League",
        "Steel Falcons", "Dark Archive", "Scarab Sages", "Silver Crusade", "Sovereign Court",
        "Liberty's Edge", "Umbral Court", "Storm Kindlers", "Wardens of the Reborn Forge",
        "Shining Crusade", "Order of the Rack", "Order of the Nail", "Order of the Gate",
        "Order of the Scourge", "Order of the Pyre", "Order of the Chain",
        "Order of the Godclaw", "Order of the Torrent", "Order of the Glyph",
        "Sun Orchid", "Houses of Perfection", "Esoteric Order", "Technic League",
        "White Witches", "Golden Erinyes", "Bellf lower Network", "Ninth Battalion",
        "Pathf inder Society", "Risen Guard", "Bloodstone Swords", "Old Cults",
    ],
    "character": """
        Tar-Baphon Karzoug Runelord Runelords Sorshen Alaznist Krune Belimarius Zutha
        Kazavon Mengkare Ileosa Abrogail Thrune Elvanna Jatembe Khemet Janhelia
        Echean Deivon Kreighton Petresky Kortash Khain Artokus Kirran Ithuna Vardsdottir
        Petulengro Shaine Stigur Anelda Sonnorae Vyushbaro Zykomso Seelah Sajan Merisiel Valeros
        Kyra Harsk Lini Ezren Seoni Amiri Alahazra Damiel Feiya Imrijka Lirianne Seltyiel
        Jirelle Hayato Meligaster Reiko Rivani Zadim Oloch Balazar Shardra Enora Mavaro
    """,
    # "Choral the Conqueror", the dragon, and not the bare word: Bestiary 6's choral is a
    # kind of angel that sings in choirs, and was the one hit left when the bestiary was
    # first scanned (2026-10-30).
    "character phrase": [
        "Aram Zey", "Hao Jin", "Whispering Tyrant", "Old-Mage", "Urion", "Xin",
        "Lem", "Quinn", "Crowe", "Yoon", "Choral the Conqueror",
    ],
    "calendar": """
        Abadius Calistril Pharast Gozran Desnus Sarenith Erastus Arodus Rova Lamashan
        Neth Kuthona Toilday Wealday Oathday Fireday Starday
    """,
    # Golarion's coined metals: the skymetals of Numeria and the steel named for Nex. Both
    # cases, because a material's id and its prose are lower-case (renamed 2026-10-30).
    "material": """
        abysium Abysium djezet Djezet inubrix Inubrix noqual Noqual siccatite Siccatite
        horacalcum Horacalcum nexavaran Nexavaran
    """,
}

# Older than Paizo: real-world myth, demonology and the Mythos, taken into Golarion as its
# fiends, gods and planes. Counted apart (see the module docstring).
MYTH = {
    "myth": """
        Asmodeus Asmodean Lamashtu Lamashtan Baphomet Mammon Mephistopheles Dagon Pazuzu
        Moloch Belial Baalzebul Dispater Geryon Barbatos Abraxas Haagenti Shax Hastur
        Azathoth Cthulhu Nyarlathotep Yog-Sothoth Shub-Niggurath Erebus Abaddon Abaddonian
        Apollyon Charon Ahriman Cernunnos Apsu Dahak Leng Carcosa Styx
    """,
    "myth phrase": ["Baba Yaga", "Sun Wukong"],
}

# Paizo product titles quoted in rules text — a citation of a trademark, not lore.
PRODUCT = [
    r"Pathfinder (?:Adventure Path|Campaign Setting|Player Companion|Module|Society Scenario"
    r"|Chronicles|Roleplaying Game|RPG)",
    r"Inner Sea (?:World Guide|Gods|Magic|Races|Intrigue|Temples|Combat|Bestiary|Monster Codex)",
    # Where this project cites its own references: a website and a rules FAQ, not lore.
    r"Archives of Nethys", r"Pathfinder Society (?:FAQ|Roleplaying Guild)",
]

# The names Golarion gives its planes. Not Paizo's coinages: Elysium is Greek myth,
# Nirvana Buddhist, the Akashic Record Theosophy's, and the Boneyard, the Maelstrom, Axis,
# the First World and the Great Beyond are English words Golarion uses as plane names.
# Reported on their own line. The owner had them rewritten on 2026-10-30 for consistency,
# so the game names its planes one way, not because each is protected; do not extend
# this list on the premise that a plane's name is Paizo's.
# tests/test_no_golarion_names.py holds them at zero with the rest.
COSMOLOGY = ["Boneyard", "Maelstrom", "Great Beyond", "First World", "Akashic", "Elysium",
             "Elysian", "Nirvana", "Axis", "River of Souls"]


def _terms(table: dict) -> dict[str, str]:
    """name -> class, from the whitespace lists and the phrase lists."""
    out = {}
    for key, names in table.items():
        cls = key.split()[0]
        for name in (names.split() if isinstance(names, str) else names):
            out[name] = cls
    return out


TERMS = _terms(GOLARION)
TERMS.update({n: "myth" for n in _terms(MYTH)})
CLASS_OF = TERMS

# Names matched in any case. The list above is case-sensitive so an ordinary word
# capitalised at a sentence start is never a hit, and that let four kinds of name through
# (review, 2026-10-30): the Society as a bare "Pathfinder" ("invaluable to a Pathfinder
# who must make a snap decision", "an established Pathfinder lodge"); Thassilon's
# "runelords" written lower-case; a weapon named lower-case in the feats ("an earth breaker
# and klar") and the kasatha's spinal sword; and an old id quoted in this project's own
# notes ("come from last-azlanti-s-defending-sword"), which a hyphen hid from the word
# boundaries. So these match on letter boundaries alone, and a product title
# ("Pathfinder Roleplaying Game", "Pathfinder Society Scenario") still wins its words —
# that is a citation of the line, not the Society.
CASELESS = {
    "runelord": "character", "runelords": "character",
    "klar": "item", "kasatha": "people", "azlanti": "people", "shoanti": "people",
    "thassilonian": "people",
}
# The Society, by the shapes the Society takes: a person ("a Pathfinder who must", "fellow
# Pathfinders") or one of its things ("a Pathfinder lodge"). Not the bare word, which is
# the game itself in this project's own notes ("a 3.5 skill Pathfinder folded into
# Perception", "Pathfinder Unchained", "Original writing for Pathfinder GM") — a caseless
# bare "pathfinder" was tried first and flagged eighteen of those.
SOCIETY_RE = re.compile(
    r"(?<![A-Za-z])(?:(?:an?|the|fellow|every|each|any|young|veteran|seasoned)\s+"
    r"pathfinders?(?![A-Za-z:])|pathfinders(?![A-Za-z])|pathfinder(?:'s)?\s+(?:lodges?|society"
    r"|chronicles?|agents?|wayfinders?)(?![A-Za-z]))", re.IGNORECASE)
CASELESS_RE = re.compile(r"(?<![A-Za-z])(" + "|".join(sorted(CASELESS, key=len, reverse=True))
                         + r")(?![A-Za-z])", re.IGNORECASE)


def _pattern(names) -> re.Pattern:
    alts = sorted((re.escape(n) for n in names), key=len, reverse=True)
    return re.compile(r"(?<![\w'-])(" + "|".join(alts) + r")(?:'s|s')?(?![\w-])")


NAME_RE = _pattern(TERMS)
PRODUCT_RE = re.compile("|".join(PRODUCT))
COSMOLOGY_RE = _pattern(COSMOLOGY)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# Ids are slugs, so a name is looked for as a whole hyphen-bounded run. Only names of two
# or more letters that cannot be an English fragment once lower-cased are tried: "tian"
# or "geb" inside an id is the name; "lem" or "kho" could be anything, and is left out.
_ID_UNSAFE = {"lem", "kho", "xin", "nex", "geb", "orv", "eox", "tien", "tian", "rova",
              "neth", "galt", "harrow", "mantis", "choral", "quinn", "crowe", "yoon",
              "kyra", "lini", "brigh", "kols", "trudd", "leng", "shax", "charon", "arcadia",
              "the-eldest", "the-shackles", "urion", "starday", "fireday"}
ID_SLUGS = {s: n for n in TERMS for s in [_slug(n)] if len(s) > 2 and s not in _ID_UNSAFE}
# The caseless names in ids too ("kasatha-spinal-sword", "klar"), by their own spelling.
ID_SLUGS.update({s: s for s in CASELESS})
ID_RE = re.compile(r"(?:^|-)(" + "|".join(sorted(map(re.escape, ID_SLUGS), key=len,
                                                 reverse=True)) + r")(?:-s)?(?=-|$)")

# --- families ----------------------------------------------------------------------------------

# The Roleplaying Game line: Paizo's rulebooks, the PRD's own shape.
RULEBOOK = {
    "Core Rulebook", "PFRPG Core", "Advanced Player's Guide", "Ultimate Magic",
    "Ultimate Combat", "Ultimate Campaign", "Ultimate Intrigue", "Ultimate Wilderness",
    "Advanced Class Guide", "Advanced Race Guide", "Occult Adventures", "Horror Adventures",
    "Mythic Adventures", "Planar Adventures", "Villain Codex", "Monster Codex",
    "Adventurer's Guide", "Bestiary", "PFRPG Bestiary",
}
# Adventures: Adventure Paths and their appendices and player's guides, modules, Society.
ADVENTURE = {
    "Rise of the Runelords Anniversary Edition",
    "Rise of the Runelords Anniversary Edition Appendix",
    "Curse of the Crimson Throne Chapter Appendix", "Second Darkness Player's Guide",
    "Guardians of Dragonfall", "The Dragon's Demand", "Conquest of Bloodsworn Vale",
    "We Be Goblins Too", "Wardens Of The Reborn Forge",
}
ADVENTURE_RE = re.compile(r"^(AP \d+|PFS )")
# Neither a book line nor an adventure: web posts, comics, a card deck.
OTHER = {"Paizo Blog", "Pathfinder Comics #10", "Condition Cards"}
# Campaign Setting and Player Companion: Golarion's own lines. Explicit, so a new source
# has to be placed on purpose; title-case variants are the spreadsheets' own.
SETTING = {
    "Advanced Class Origins", "Adventurer's Armory 2", "Agents of Evil",
    "Andoran Spirit Of Liberty", "Animal Archive", "Aquatic Adventures", "Arcane Anthology",
    "Armor Master's Handbook", "Bastards Of Golarion", "Blood Of Angels", "Blood Of Fiends",
    "Blood Of The Moon", "Blood Of The Night", "Blood of Shadows", "Blood of the Ancients",
    "Blood of the Beast", "Blood of the Coven", "Blood of the Elements", "Blood of the Moon",
    "Blood of the Night", "Blood of the Sea", "Book of the Damned", "Champions Of Balance",
    "Champions Of Purity", "Champions of Balance", "Champions of Corruption",
    "Champions of Purity", "Cheliax Empire Of Devils", "Cheliax, Empire of Devils",
    "Chronicle Of The Righteous", "Chronicle of Legends", "Chronicle of the Righteous",
    "City Of Strangers", "Classic Treasures", "Cohorts & Companions",
    "Dark Markets: A Guide to Katapesh", "Demon Hunter's Handbook", "Demons Revisited",
    "Dirty Tactics Toolbox", "Disciple's Doctrine", "Distant Realms", "Divine Anthology",
    "Dragon Empires Primer", "Dragonslayer's Handbook", "Dungeon Denizens Revisited",
    "Dungeoneer's Handbook", "Dungeons of Golarion", "Dwarves Of Golarion",
    "Dwarves of Golarion", "Elemental Master's Handbook", "Faction Guide",
    "Faiths & Philosophies", "Faiths Of Balance", "Faiths Of Corruption", "Faiths Of Purity",
    "Faiths of Corruption", "Faiths of Purity", "Familiar Folio", "Giant Hunter's Handbook",
    "Gnomes Of Golarion", "Gnomes of Golarion", "Goblins Of Golarion", "Goblins of Golarion",
    "Gods and Magic", "Guide to the River Kingdoms", "Halflings Of Golarion",
    "Haunted Heroes Handbook", "Healer's Handbook", "Heroes from the Fringe",
    "Heroes of the Darklands", "Heroes of the High Court", "Heroes of the Streets",
    "Heroes of the Wild", "Horsemen of the Apocalypse", "Humans of Golarion",
    "Inner Sea Gods", "Inner Sea Intrigue", "Inner Sea Magic", "Inner Sea Monster Codex",
    "Inner Sea Races", "Inner Sea Temples", "Inner Sea World Guide",
    "Knights of the Inner Sea", "Kobolds Of Golarion", "Kobolds of Golarion",
    "Lands of the Linnorm Kings", "Legacy of Dragons", "Legacy of the First World",
    "Lords Of Chaos", "Lost Kingdoms", "Magic Tactics Toolbox", "Magical Marketplace",
    "Melee Tactics Toolbox", "Monster Hunter's Handbook", "Monster Summoner's Handbook",
    "Mythic Origins", "Occult Mysteries", "Occult Origins", "Occult Realms",
    "Orcs Of Golarion", "Orcs of Golarion", "Osirion, Legacy of Pharaohs",
    "Pathfinder Campaign Setting", "Pathfinder Society Field Guide",
    "Pathfinder Society Primer", "Paths of the Righteous", "People Of The North",
    "People Of The Sands", "People of the River", "People of the Sands", "People of the Stars",
    "People of the Wastes", "Pirates of the Inner Sea", "Plane-Hopper's Handbook",
    "Planes of Power", "Potions and Poisons", "Psychic Anthology", "Qadira",
    "Qadira, Jewel of the East", "Quests and Campaigns", "Ranged Tactics Toolbox",
    "Rival Guide", "Sargava", "Sargava, the Lost Colony", "Seekers of Secrets",
    "Spymaster's Handbook", "Taldor, Echoes of Glory", "Technology Guide",
    "The First World, Realm of the Fey", "The Harrow Handbook", "Undead Slayer's Handbook",
    "Varisia", "Wilderness Origins",
}
FAMILIES = ["rulebook", "setting", "adventure", "other", "unclassified", "derived",
            "app-authored"]


def family(source: str) -> str:
    if source in RULEBOOK:
        return "rulebook"
    if source in SETTING:
        return "setting"
    if source in ADVENTURE or ADVENTURE_RE.match(source):
        return "adventure"
    if source in OTHER:
        return "other"
    return "unclassified"


# Files whose rows each carry a book in `source`, and the key holding the rows. Every other
# content file is this project's own writing and is walked whole.
BOOK_FILES = {
    "content/spells/spells.json": "spells",
    "content/feats/feats.json": "feats",
    # The bestiary, scanned since 2026-10-30. It was skipped here ("measured on its own in
    # tools/bestiary_provenance.py"), which measured sources, not names — and so the
    # rebuild that grew core.json to 1,417 printed blocks brought back 100 rows naming
    # Golarion's gods and planes, 444 mentions, with this scan reporting zero.
    "content/bestiary/core.json": "creatures",
    "content/bestiary/creatures.json": "creatures",
    "content/bestiary/mounts.json": "creatures",
}
SKIP_DIRS: set[str] = set()
# `aliases.json` files are skipped: old id -> new id, kept so a save written before a
# rename still loads (tools/strip_golarion.py). They are the one sanctioned home of the
# old names; content/bestiary/aliases.json keeps its keys hashed, so not even there.
# This project's typed mechanics for the imported rows, keyed by the rows' ids and quoting
# their prose: not separate content, but a copy any rename or drop has to follow. The
# compiled bestiary is the printed blocks' attacks and gear, generated from them.
DERIVED = re.compile(r"^content/(spells/mechanics/|spells/spells-mechanics|feats/mechanics/"
                     r"|bestiary/compiled)")

# --- scanning ----------------------------------------------------------------------------------


Hit = collections.namedtuple("Hit", "file row_id field term cls context")


def _context(text: str, start: int, end: int, width: int = 60) -> str:
    left = max(0, start - width)
    return (("..." if left else "") + text[left:end + width] +
            ("..." if end + width < len(text) else "")).replace("\n", " ")


def scan_text(text: str):
    """(term, class, start, end) for every name, product and cosmology mention. A name
    inside a product title ("Inner Sea" in "Inner Sea Gods", "Nethys" in "Archives of
    Nethys") is the title, not a second mention."""
    titles = [(m.start(), m.end()) for m in PRODUCT_RE.finditer(text)]
    for a, b in titles:
        yield text[a:b], "product", a, b
    named = []
    for m in NAME_RE.finditer(text):
        if not any(a <= m.start() < b for a, b in titles):
            named.append((m.start(), m.end()))
            yield m.group(1), CLASS_OF[m.group(1)], m.start(), m.end()
    for m in CASELESS_RE.finditer(text):
        if not any(a <= m.start() < b for a, b in titles + named):
            yield m.group(1), CASELESS[m.group(1).lower()], m.start(), m.end()
    for m in SOCIETY_RE.finditer(text):
        # Overlap, not containment: "the Pathfinder Society FAQ" starts before its title.
        if not any(a < m.end() and m.start() < b for a, b in titles + named):
            yield "Pathfinder", "organisation", m.start(), m.end()
    for m in COSMOLOGY_RE.finditer(text):
        yield m.group(1), "cosmology", m.start(), m.end()


def scan_record(rel: str, row_id: str, record: dict):
    if row_id:
        for m in ID_RE.finditer(row_id):
            name = ID_SLUGS[m.group(1)]
            yield Hit(rel, row_id, "id", name, CLASS_OF[name], row_id)
    for field, value in record.items():
        if field in ("id", "source"):
            continue
        for text in _strings(value):
            for term, cls, a, b in scan_text(text):
                yield Hit(rel, row_id, field, term, cls, _context(text, a, b))


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def _records(data, inherited_id=""):
    """(row id, flat dict of this record's own scalar fields) for every record in a
    project-authored file, depth first: a record is a dict with an id or a name, and its
    dict-keyed children (mechanics files key spells by id) take that key as their id."""
    stack = [(data, inherited_id)]
    while stack:
        node, rid = stack.pop()
        if isinstance(node, dict):
            own = node.get("id") or node.get("name") or rid
            flat = {k: v for k, v in node.items() if not isinstance(v, (dict, list))
                    or (isinstance(v, list) and all(isinstance(x, str) for x in v))}
            if flat:
                yield str(own), flat
            for k, v in node.items():
                if isinstance(v, dict):
                    stack.append((v, k if re.fullmatch(r"[a-z0-9-]+", k) else own))
                elif isinstance(v, list) and not all(isinstance(x, str) for x in v):
                    stack.extend((x, own) for x in v)
        elif isinstance(node, list):
            stack.extend((x, rid) for x in node)


def measure():
    """rows: list of (file, row id, source, family, [hits]) for every row with a hit, and
    totals: file -> (family -> rows scanned)."""
    rows, totals = [], collections.defaultdict(collections.Counter)
    for path in sorted((ROOT / "content").rglob("*.json")):
        rel = path.relative_to(ROOT).as_posix()
        if SKIP_DIRS & set(path.relative_to(ROOT).parts) or path.name == "aliases.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if rel in BOOK_FILES:
            for rec in data[BOOK_FILES[rel]]:
                src = str(rec.get("source") or "")
                fam = family(src)
                totals[rel][fam] += 1
                hits = list(scan_record(rel, rec.get("id", ""), rec))
                if hits:
                    rows.append((rel, rec.get("id", ""), src, fam, hits))
            continue
        fam = "derived" if DERIVED.match(rel) else "app-authored"
        by_id = collections.defaultdict(list)
        for rid, flat in _records(data):
            by_id[rid].extend(scan_record(rel, rid, flat))
        totals[rel][fam] += len(by_id)
        for rid, hits in by_id.items():
            if hits:
                rows.append((rel, rid, "", fam, hits))
    return rows, totals


# --- report ------------------------------------------------------------------------------------

LORE = {"deity", "place", "people", "organisation", "character", "calendar", "material",
        "item"}

# Columns that are lists and gates rather than prose: the spells' "which god grants this"
# and "which bloodline gets it" columns, and the feats' prerequisites. A name only here
# can be dropped with the column entry; a name in the prose has to be rewritten.
METADATA = {"deity", "bloodline", "domain", "patron", "prerequisites_text",
            "unparsed_prerequisites", "prerequisites"}


def _verdict(hits) -> str:
    """The strongest thing a row carries: a Golarion name in its name or id, in its prose,
    only in a list column, a myth name, a product title, or only cosmology words."""
    lore = [h for h in hits if h.cls in LORE]
    if any(h.field in ("name", "id") for h in lore):
        return "golarion in name"
    if any(h.field not in METADATA for h in lore):
        return "golarion in prose"
    if lore:
        return "golarion in a column"
    if any(h.cls == "myth" for h in hits):
        return "myth only"
    if any(h.cls == "product" for h in hits):
        return "product title only"
    return "cosmology only"


VERDICTS = ["golarion in name", "golarion in prose", "golarion in a column", "myth only",
            "product title only", "cosmology only"]


def main() -> int:
    args = sys.argv[1:]
    sample = int(args[args.index("--sample") + 1]) if "--sample" in args else 0
    rows, totals = measure()

    print("Rows carrying a name, by file and family, against the rows scanned\n")
    print(f"  {'file':42} {'family':13} {'scanned':>7} " +
          " ".join(f"{v[:16]:>16}" for v in VERDICTS))
    per = collections.defaultdict(collections.Counter)
    for rel, _rid, _src, fam, hits in rows:
        per[(rel, fam)][_verdict(hits)] += 1
    for rel in sorted(totals):
        for fam in FAMILIES:
            n = totals[rel].get(fam, 0)
            if not n:
                continue
            c = per[(rel, fam)]
            if not sum(c.values()) and rel not in BOOK_FILES:
                continue
            print(f"  {rel:42} {fam:13} {n:7} " + " ".join(f"{c[v]:16}" for v in VERDICTS))

    print("\nTerms by class (rows that carry each, top ten per class)\n")
    by_class = collections.defaultdict(collections.Counter)
    for _rel, _rid, _src, _fam, hits in rows:
        for cls, term in {(h.cls, h.term.removesuffix("'s")) for h in hits}:
            by_class[cls][term] += 1
    for cls in ["deity", "place", "people", "organisation", "character", "calendar",
                "material", "item", "myth", "product", "cosmology"]:
        c = by_class.get(cls)
        if c:
            top = ", ".join(f"{t} {n}" for t, n in c.most_common(10))
            print(f"  {cls:13} {sum(c.values()):5} row-mentions, {len(c):3} names  {top}")

    print("\nBook-sourced rows with a Golarion name, by source (top 40)\n")
    src_tally = collections.Counter()
    for rel, _rid, src, fam, hits in rows:
        if rel in BOOK_FILES and _verdict(hits).startswith("golarion"):
            src_tally[(src, fam)] += 1
    for (src, fam), n in src_tally.most_common(40):
        print(f"  {n:5}  {src:50} {fam}")

    unclassified = sorted({src for rel in BOOK_FILES for src, fam in
                           ((r[2], r[3]) for r in rows if r[0] == rel) if fam == "unclassified"})
    if unclassified:
        print(f"\n  unclassified sources: {unclassified}")

    if "--rows" in args:
        print("\nEvery row\n")
        for rel, rid, src, fam, hits in rows:
            terms = sorted({f"{h.term}({h.cls},{h.field})" for h in hits})
            print(f"  {_verdict(hits):20} {rel}  {rid}  [{src or fam}]  {'; '.join(terms)}")

    if sample:
        rng = random.Random(20261029)
        flat = [(rel, rid, src, h) for rel, rid, src, _f, hits in rows for h in hits]
        print(f"\n{sample} random hits, to hand-check\n")
        for rel, rid, src, h in rng.sample(flat, min(sample, len(flat))):
            print(f"  [{h.cls}] {h.term!r} in {rel} {rid}.{h.field} ({src or 'app'})\n"
                  f"      {h.context}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
