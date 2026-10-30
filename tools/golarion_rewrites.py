"""The world-agnostic rewrite of the imported spells, feats and weapons.

The owner's choice of 2026-10-29 (docs/bestiary-licensing.md §7): F3, falling back to F2.
Every row that names Golarion keeps its mechanics and loses the name — retitled from what
it does, the way d20pfsrd publishes "Aroden's spellbane" as "Spellbane" — and a row whose
setting *is* its mechanics (a feat gated on Pathfinder Society faction prestige, a bonus
"in relation to Osirion") is dropped instead.

Why a table and not a model pass: these are rules text, and the house rule is to detect
in code and repair with a targeted edit. `tools/content_provenance.py` found every row;
each edit below names the exact words it replaces, and `apply_*` refuses to run when an
edit no longer finds them — a stale table fails loudly instead of silently leaving the
name in. The same functions run from the importers (`build_spells.py`, `build_feats.py`,
`build_weapons.py`), so re-importing a spreadsheet cannot bring the names back; and
`tests/test_no_golarion_names.py` holds the shipped count at zero either way.

Deliberately untouched, for the owner's separate call (§7.4): names older than Paizo that
Golarion adopted (Asmodeus, Lamashtu, Hastur) and cosmology words (Boneyard, Elysium).

    python tools/strip_golarion.py      # applies this table to the shipped files
"""
from __future__ import annotations

import re

U = "’"   # the spreadsheets' curly apostrophe, so an edit matches the text as it is

# --- renames -----------------------------------------------------------------------------------
# old id -> (new id, new name). The name is chosen from the mechanics, never invented as a
# place or a person: a World Bible world has no "Shadowwood" for a rename to point at.

SPELL_RENAMES: dict[str, tuple[str, str]] = {
    "abadar-s-truthtelling": ("touch-of-truthtelling", "Touch of Truthtelling"),  # d20pfsrd's
    "alaznist-s-jinx": ("burning-jinx", "Burning Jinx"),
    "aldori-alacrity": ("duelist-s-alacrity", "Duelist's Alacrity"),
    "aram-zey-s-focus": ("trapfinder-s-focus", "Trapfinder's Focus"),
    "aram-zey-s-trap-ward": ("trap-ward", "Trap Ward"),
    "aroden-s-magic-army": ("magic-army", "Magic Army"),
    "aroden-s-spellbane": ("spellbane", "Spellbane"),                            # d20pfsrd's
    "aroden-s-spellsword": ("spellsword", "Spellsword"),
    "besmara-s-grasping-depths": ("grasping-depths", "Grasping Depths"),
    "calistria-s-guardian-wasps": ("guardian-wasps", "Guardian Wasps"),
    "deivon-s-parry": ("arcane-parry", "Arcane Parry"),
    "echean-s-excellent-enclosure": ("excellent-enclosure", "Excellent Enclosure"),
    "egorian-diplomacy": ("velvet-diplomacy", "Velvet Diplomacy"),
    "geb-s-hammer": ("corpse-hammer", "Corpse Hammer"),     # the text already calls it that
    "gorum-s-armor": ("quill-armor", "Quill Armor"),
    "gozreh-s-trident": ("storm-trident", "Storm Trident"),
    "hanspur-s-flotsam-vessel": ("flotsam-vessel", "Flotsam Vessel"),
    "irriseni-mirror-sight": ("mirror-sight", "Mirror Sight"),
    "jatembe-s-ire": ("wrathful-vines", "Wrathful Vines"),
    "khain-s-army": ("ghoul-army", "Ghoul Army"),
    "kreighton-s-perusal": ("rapid-perusal", "Rapid Perusal"),
    "last-azlanti-s-defending-sword": ("defending-sword", "Defending Sword"),
    "last-azlanti-s-defending-sword-mass": ("defending-sword-mass", "Defending Sword, Mass"),
    "light-of-iomedae": ("light-of-the-righteous", "Light of the Righteous"),
    "lissalan-snake-sigil": ("cursed-snake-sigil", "Cursed Snake Sigil"),
    "nex-s-secret-workshop": ("secret-workshop", "Secret Workshop"),
    "petulengro-s-validation": ("companion-s-validation", "Companion's Validation"),
    "rovagug-s-fury": ("quaking-fury", "Quaking Fury"),
    "rune-of-jandelay": ("rune-of-order", "Rune of Order"),
    "sarzari-shadow-memory": ("shadow-memory", "Shadow Memory"),
    "shield-of-the-dawnflower": ("shield-of-dawn", "Shield of Dawn"),
    "shield-of-the-dawnflower-greater": ("shield-of-dawn-greater", "Shield of Dawn, Greater"),
    "sign-of-the-dawnflower": ("sign-of-the-faithful", "Sign of the Faithful"),
    "song-of-kyonin": ("restorative-song", "Restorative Song"),
    "urgathoa-s-beacon": ("carrion-beacon", "Carrion Beacon"),
    "hermean-potential": ("perfected-potential", "Perfected Potential"),
}

FEAT_RENAMES: dict[str, tuple[str, str]] = {
    "aldori-dueling-mastery": ("dueling-sword-mastery", "Dueling Sword Mastery"),
    "andoren-falconry": ("falconer-s-art", "Falconer's Art"),
    "eye-of-the-arclord": ("eldritch-eye", "Eldritch Eye"),
    "hermean-blood": ("bred-for-perfection", "Bred for Perfection"),
    "lastwall-phalanx": ("shieldwall-phalanx", "Shieldwall Phalanx"),
    "legacy-of-ozem": ("legacy-of-the-crusade", "Legacy of the Crusade"),
    "shade-of-the-uskwood": ("shadow-effigy", "Shadow Effigy"),
    "taldan-duelist": ("buckler-duelist", "Buckler Duelist"),
    "talmandor-s-lifting": ("wings-of-grace", "Wings of Grace"),
    "thuvian-grenadier": ("careful-grenadier", "Careful Grenadier"),
    "varisian-tattoo": ("mystic-tattoo", "Mystic Tattoo"),
    "worldwound-walker": ("veiled-purity", "Veiled Purity"),
    # The importer broke a tie between two printings by appending the book's title to the
    # id; the feat's own name is clean. A shorter tie-breaker, same feat.
    "blood-vengeance-orcs-of-golarion": ("blood-vengeance-orcs", "Blood Vengeance"),
    "destroyer-s-blessing-orcs-of-golarion": ("destroyer-s-blessing-orcs", "Destroyer's Blessing"),
    "ferocious-tenacity-orcs-of-golarion": ("ferocious-tenacity-orcs", "Ferocious Tenacity"),
    "gore-fiend-orcs-of-golarion": ("gore-fiend-orcs", "Gore Fiend"),
    "sympathetic-rage-orcs-of-golarion": ("sympathetic-rage-orcs", "Sympathetic Rage"),
    "thrill-of-the-kill-orcs-of-golarion": ("thrill-of-the-kill-orcs", "Thrill of the Kill"),
    "learn-ranger-trap-kobolds-of-golarion": ("learn-ranger-trap-kobolds", "Learn Ranger Trap"),
}

# old id -> (new id, new name). The weapon's lookup keeps the old spellings as aliases
# (rules/weapons.py ALIASES), so a sword already in a pack is still found.
WEAPON_RENAMES: dict[str, tuple[str, str]] = {
    "aldori-dueling-sword": ("dueling-sword", "Dueling sword"),
    "shoanti-bolas": ("heavy-bolas", "Heavy bolas"),
}

# --- drops (the F2 fallback) -------------------------------------------------------------------
# old id -> the id a save holding it should now read, or None when there is no equivalent.

SPELL_DROPS: dict[str, str | None] = {
    # The Humans of Golarion printing of the Ultimate Intrigue spell, same mechanics with a
    # Taldan origin story bolted on. The rulebook printing ships.
    "cultural-adaptation-taldan": "cultural-adaptation",
    # Its effects are the AP 113 Great Old One's own abilities ("Xhamen-Dor's infected
    # dreams ability (see page 86)") — rules this app does not ship, from a book it does
    # not, around a name it cannot keep.
    "what-grows-within": None,
}

FEAT_DROPS: dict[str, str | None] = {
    # The Faction Guide's prestige feats: each requires "N TPA", Pathfinder Society
    # organised play's faction prestige. No character here can ever meet it, and the
    # organisations are the point of the feats.
    "advanced-defensive-combat-training": None, "bloodstone-manhunter": None,
    "calm-disposition": None, "death-s-suitor": None, "disassemble-magic-item": None,
    "fearsome-barricade": None, "grand-master-performer": None, "ki-diversity": None,
    "let-them-come": None, "master-performer": None, "nameless-servitor": None,
    "old-cults-awakener": None, "ominous-mien": None, "silent-performer": None,
    "touched-by-sacred-fire": None, "verbose-performer": None, "whispered-knowledge": None,
    # Organised play's Day Job checks, and two feats whose benefit is the setting itself:
    # the Eagle Knights' branches, and "+3 ... in relation to Osirion or its people".
    "improved-day-job": None, "eagle-knight-candidate": None, "osirionology": None,
    # An import duplicate of Lastwall Phalanx: identical but for the run-together name.
    "lastwallphalanx": "shieldwall-phalanx",
}

# --- text --------------------------------------------------------------------------------------

# Phrases rewritten wherever they stand, in spells and feats alike.
COMMON: list[tuple[str, str]] = [
    ("an Aldori dueling sword", "a dueling sword"),     # before the bare phrase: "an dueling"
    ("Aldori dueling sword", "dueling sword"),
    ("Shoanti bolas", "heavy bolas"),
]

# A deity gate in a feat's prerequisites keeps its gate and loses its god: the god's
# portfolio stands in, read against whatever belief system the world has. Unparsed today
# (rules/feats.py `meets` answers "cannot tell"), so a feat that could not be taken still
# cannot — a rewrite, not a rules change.
GODS = {
    "Abadar": "a god of commerce", "Calistria": "a god of revenge",
    "Gorum": "a god of battle", "Gozreh": "a god of sea and sky",
    "Irori": "a god of self-perfection", "Nethys": "a god of magic",
    "Norgorber": "a god of secrets", "Rovagug": "a god of destruction",
    "Urgathoa": "a god of undeath", "Zon-Kuthon": "a god of pain",
}
WORSHIPER_RE = re.compile(r"\b([Ww]orshiper of) (" + "|".join(map(re.escape, GODS)) + r")\b")

# Paizo's product-line prefixes on book citations: "(Pathfinder RPG Bestiary 245)" is
# "(Bestiary 245)". The book stays named; the trademark goes.
PRODUCT: list[tuple[re.Pattern, str]] = [
    (re.compile(r"Pathfinder Roleplaying Game: "), ""),
    (re.compile(r"Pathfinder RPG "), ""),
    (re.compile(r"Pathfinder Campaign Setting: "), ""),
    (re.compile(r"Pathfinder Adventure Path volume"), "Adventure Path volume"),
]

SPELL_EDITS: dict[str, list[tuple[str, str]]] = {
    "ablative-sphere": [("The Garundi tenaciously protect their homes",
                         "Desert peoples tenaciously protect their homes")],
    "abstemiousness": [("Sometimes Irori smiles on his worshipers",
                        "Sometimes a god of self-perfection smiles on its worshipers")],
    "aram-zey-s-focus": [("Aram Zey created this spell for use by his students",
                          "A master trapfinder created this spell for use by his students")],
    "aram-zey-s-trap-ward": [
        ("While he was researching the underlying causes of the resonance created by "
         "overlapping abjurations, Aram Zey discovered",
         "While researching the underlying causes of the resonance created by overlapping "
         "abjurations, a wizard discovered")],
    "arcane-reinforcement": [
        ("This spell originated among wizards of the Arcanamirium, though the Pathfinder "
         "Society also uses it.",
         "This spell originated among the wizards of an arcane academy, though adventuring "
         "societies also use it.")],
    "aroden-s-spellbane": [
        ("One of many spells originally created by the Last Azlanti before he became a god, "
         "Aroden's spellbane creates", "Spellbane creates")],
    "bind-sage": [("certain reclusive scholar communities in Kaer Maga may know titles",
                   "certain reclusive scholar communities may know titles")],
    "bladed-dash": [
        ("Both Quantium and Jalmeray claim that this spell was born in their arcane "
         "universities.", "Two rival schools of magic both claim that this spell was born "
                          "in their halls."),
        ("it quickly spread throughout the Inner Sea and beyond", "it quickly spread far and wide")],
    "blast-barrier": [("Originally used by the winter witches on the field of battle in the "
                       "early days of Irrisen,",
                       "Originally used by winter witches on the field of battle,")],
    "bloodstone-mirror": [("Developed due to Arazni's fear that her stolen organs might be used "
                           "to control her, this spell",
                           "Developed by a goddess who feared that her stolen organs might be "
                           "used to control her, this spell")],
    "bloodsworn-retribution": [("killed Stigur", "killed the caster"),
                               ("and Stigur wants", "and the caster wants"),
                               ("Stigur casts", "The caster casts"),
                               ("Thereafter Stigur gains", "Thereafter the caster gains")],
    "bone-flense": [("wielded by a member of the Red Mantis, a sawtooth sabre",
                     "wielded by a member of a mantis-masked order of assassins, a sawtooth "
                     "sabre")],
    "borrowed-time": [("A creation of the archmage Nex, this spell",
                       "A creation of an ancient archmage, this spell")],
    "brand-of-conformity": [("an elf raised among the Shoanti would lose Elven and Shoanti",
                             "an elf raised among a human tribe would lose Elven and the "
                             "tribe's tongue")],
    "brightest-light": [("This trademark spell of the Lantern Bearers functions",
                         "This trademark spell of an order of elven light-bearers functions")],
    "burning-arc": [("Keleshites brag that they stole this spell",
                     "The desert peoples brag that they stole this spell")],
    "call-weapon": [
        ("This spell first rose to prominence among the elves of Kyonin in the war to retake "
         "their ancestral land from the demon lord Treerazer and his minions.",
         "This spell first rose to prominence among elves in a war to retake their ancestral "
         "land from a demon lord and his minions."),
        ("this spell spread throughout the Inner Sea and beyond", "this spell spread far and wide")],
    "canopic-conversion": [
        ("The pharaohs of ancient Osirion sometimes", "Ancient pharaohs sometimes"),
        ("The Risen Guard does not use the spell (though they have access to it), preferring "
         "trustworthy living guardians for the Ruby Prince.",
         "Some royal guards do not use the spell (though they have access to it), preferring "
         "trustworthy living guardians for their ruler."),
        ("The Whispering Way may have copies of the spell.",
         "Cults of undeath may have copies of the spell.")],
    "chastise": [("This spell is primarily used by the Eagle Knights, though they did not "
                  "create it; Hellknights also use it extensively",
                  "This spell is primarily used by knightly orders, though they did not create "
                  "it; orders of lawful enforcers also use it extensively")],
    "contest-of-skill": [("certain duelists in the Aldori school",
                          "certain duelists of a famed swordfighting school")],
    "covetous-aura": [("invented thousands of years ago by Runelord Belimarius, who",
                       "invented thousands of years ago by an envious wizard-king, who")],
    "create-drug": [("a lawful evil worshiper of Mahathallah, the Dowager of Illusions, can "
                     "create", "a lawful evil worshiper of a goddess of illusions can create"),
                    ("A Mahathallah worshiper can create adyton",
                     "Such a worshiper can create adyton")],
    "create-variant-mummy": [("or Osirian tomb guardian", "or desert tomb guardian")],
    "crusader-s-edge": [("created by the paladins of the Mendevian Crusades",
                         "created by the paladins of a long crusade against demons")],
    "curse-item": [("If a cleric of Groetus is using", "If a cleric of a god of the end times "
                                                       "is using")],
    "deadeye-s-arrow": [("resembling Erastil's holy symbol",
                         "resembling the holy symbol of a god of the hunt")],
    "deivon-s-parry": [("Originally designed by an Aldori magus who had long admired",
                        "Originally designed by a dueling magus who had long admired")],
    "dirge-of-the-victorious-knights": [
        ("By performing part of the Chelish opera Victory of the Hellknights, you call forth "
         "spectral illusions of mounted Hellknights",
         "By performing part of a martial opera of a knightly order's victory, you call forth "
         "spectral illusions of mounted knights")],
    "drunkard-s-breath": [(f"Cayden Cailean{U}s church uses", "The church of a god of drink uses")],
    "eaglesoul": [
        ("As the Inner Sea's bravest men and women answered the call of what became the Second "
         "Mendevian Crusade, constructing the wardstones that eventually kept the brutal chaos "
         "of the Worldwound at bay,",
         "As the bravest men and women of many lands answered the call of a great crusade, "
         "constructing the wardstones that eventually kept the brutal chaos of a demon-blighted "
         "rift at bay,"),
        ("chiefly among those that patrol the borders of the Worldwound, other champions of "
         "good have carried it with them to all corners of the Inner Sea region.",
         "chiefly among those that patrol the borders of demon-blighted lands, other champions "
         "of good have carried it with them to all corners of the world.")],
    "early-judgment": [("passes under Pharasma's impartial gaze",
                        "passes under the impartial gaze of the god of death"),
                       ("its destined plane in the Great Beyond", "its destined plane in the "
                                                                  "afterlife")],
    "eldritch-conduit": [
        ("Originally created by a disciple of the archwizard Nex, this spell was used to turn "
         "enemy soldiers in Geb's undead armies into conduits capable of blasting spell energy "
         "back into the far reaches of the Gebite lines.",
         "Originally created by a disciple of an ancient archwizard, this spell was used to "
         "turn soldiers in a rival necromancer's undead armies into conduits capable of "
         "blasting spell energy back into the far reaches of the enemy lines.")],
    "eroding-ray": [("the tumultuous ecosystem of the Hao Jin Tapestry",
                     "the tumultuous ecosystem of a vast demiplane")],
    "fable-tapestry": [
        ("legendary characters from Varisian folktales",
         "legendary characters from a wandering people's folktales"),
        ("Anelda the beautiful (freelance thief)", "the beautiful thief (freelance thief)"),
        ("Sonnorae the storyteller (con artist)", "the storyteller (con artist)"),
        ("Vyushbaro the savior (carousing champion)", "the savior (carousing champion)"),
        ("Zykomso the slaver (bearded devil)", "the slaver (bearded devil)")],
    "fairness": [("The symbol of Abadar appears above",
                  "The symbol of a god of law and commerce appears above")],
    "fastidiousness": [("Members of the Prophet of Kalistrade prestige class",
                        "Members of an ascetic merchant-prophets' prestige class")],
    "foster-hatred": [("such as worshipers of Shelyn", "such as worshipers of a particular god")],
    "free-spirit": [("channel the essence of Cayden Cailean's philosophy",
                     "channel the essence of a god of freedom's philosophy")],
    "frigid-souls": [("You harness the Irriseni people's palpable fear of their frozen "
                      "environment and cruel Jadwiga overlords",
                      "You harness a northern people's palpable fear of their frozen "
                      "environment and cruel witch overlords")],
    "garrulous-grin": [("This Nidalese spell plants", "This spell plants")],
    "geb-s-hammer": [
        ("Centuries of war with Nex trained the necromancers of Geb to extract every last "
         "resource from the mindless undead that make up most of Geb's rank-and-file troops.",
         "Centuries of war trained the necromancers of an undead nation to extract every last "
         "resource from the mindless undead that make up most of their rank-and-file troops."),
        ("increase Geb's hammer's critical", "increase corpse hammer's critical")],
    "geniekind": [("Keleshite wizards and clerics have always",
                   "Wizards and clerics of the desert empires have always")],
    "gilded-whispers": [
        ("Developed by priests of Abadar to catch thieves and skimmers, gilded whispers later "
         "spread to other faiths and was adapted to the arcane arts through the combined "
         "efforts of Aram Zey and Kreighton Shaine.",
         "Developed by priests of a god of commerce to catch thieves and skimmers, gilded "
         "whispers later spread to other faiths and was adapted to the arcane arts by two "
         "scholars of an explorers' society."),
        ("Pathfinders most commonly use this spell", "Explorers most commonly use this spell"),
        ("the influence of Aspis Consortium agents", "the influence of a rival trading cartel")],
    "hallucinatory-decor": [("Members of the Prophet of Kalistrade prestige class",
                             "Members of an ascetic merchant-prophets' prestige class")],
    "harrowing": [
        ("You use a Harrow deck to tell a fortune", "You use a fortune-telling deck to tell a "
                                                    "fortune"),
        ("traveling to Viperwall to search for a magic sword",
         "traveling to a ruined castle to search for a magic sword"),
        ("If you have access to a Harrow deck,", "If you have access to a fortune-telling deck,"),
        ("If you do not have a Harrow deck,", "If you do not have a fortune-telling deck,")],
    "hidden-knowledge": [("Many Cyphermages commission", "Many rune-scholars commission")],
    "human-potential": [("The target shares in humanity's great potential as encouraged by "
                         "Aroden.", "The target shares in humanity's great potential.")],
    "ice-spears": [("Favored by the spellcasters of Irrisen, this potent spell",
                    "Favored by the spellcasters of the frozen north, this potent spell")],
    "infernal-challenger": [("the administering of a Hellknight test",
                             "the administering of a knightly order's test")],
    "insect-scouts": [("A favorite in the creaking courts of Ustalav,",
                       "A favorite in creaking, gothic courts,")],
    "invoke-primal-power": [("the savage, prehistoric creatures that dwell in the Realm of the "
                             "Mammoth Lords",
                             "the savage, prehistoric creatures that dwell in the frozen wilds")],
    "irriseni-mirror-sight": [
        ("For example, Urion Petresky knows that Queen Elvanna keeps a mirror in a hall near "
         "her throne room.",
         "For example, a spy knows that the queen keeps a mirror in a hall near her throne "
         "room."),
        ("If any of these conditions fails, Urion sees nothing",
         "If any of these conditions fails, the spy sees nothing")],
    "jatembe-s-ire": [("The scholars of the Magaambya claim that Old-Mage Jatembe developed "
                       "this spell to help eradicate the lost city of Ird, although such claims "
                       "have never been confirmed. ", "")],
    "judgment-undone": [
        ("undoes Pharasma's judgment", "undoes the judgment of the dead"),
        ("The servants of Pharasma vigilantly", "The servants of the god of death vigilantly"),
        ("a powerful agent of Pharasma", "a powerful agent of the god of death"),
        ("Worshipers of Pharasma who cast", "Worshipers of the god of death who cast"),
        ("grossly violated Pharasma's code of conduct", "grossly violated their god's code of "
                                                        "conduct")],
    "khain-s-army": [
        ("Originally created by the priest-king of Nemret Noktoria, the ghoul Kortash Khain, "
         "for use by his minions to bolster their forces in battles against their enemies, "
         "Khain's army has become a favorite of many necromancers throughout Osirion and "
         "beyond.",
         "Originally created by a ghoul priest-king to bolster his minions in battle against "
         "their enemies, ghoul army has become a favorite of many necromancers.")],
    "kreighton-s-perusal": [("(such as the bonuses gained from reading volumes of the "
                             "Pathfinder Chronicles; see pages 26-27)",
                             "(such as the bonuses some rare tomes grant their readers)")],
    "last-azlanti-s-defending-sword-mass": [("This spell functions as Aroden's defending sword,",
                                             "This spell functions as defending sword,")],
    "lissalan-snake-sigil": [("one for each of the Thassilonian schools of magic",
                              "one for each of the seven schools of sin magic")],
    "litany-of-the-red-crusader": [
        ("Followers of Arazni have made use of this litany since her days as a crusader and "
         "herald.", "Followers of a fallen crusader-goddess have made use of this litany since "
                    "her days as a mortal herald.")],
    "lover-s-vengeance": [("Worshipers of Calistria are fond",
                           "Worshipers of gods of revenge are fond")],
    "martyr-s-bargain": [
        ("whether they be the servants of Desna in Nidal, zealous followers of Milani "
         "struggling against Cheliax's government, paladins of Iomedae fighting against the "
         "horrors of the Worldwound, or simply those that fight evil the world over",
         "whether they be the hidden faithful under a tyrant's rule, zealous rebels against a "
         "devil-worshipping government, paladins fighting the horrors of a demon-blighted "
         "land, or simply those that fight evil the world over")],
    "mirror-mantis": [
        ("it sees a Red Mantis assassin (in full armor, face hidden by a mantis mask)",
         "it sees a mantis-masked assassin (in full armor, face hidden by the mask)"),
        ("The first time the target sees the Red Mantis reflection",
         "The first time the target sees the assassin's reflection"),
        ("it will still see the Red Mantis reflection until",
         "it will still see the assassin's reflection until")],
    "music-of-the-spheres": [("As any scholar of Desnan lore or astrologer can tell you",
                              "As any scholar of star lore or astrologer can tell you")],
    "nex-s-secret-workshop": [("Designed to protect a large number of items from rivals of the "
                               "Arclords of Nex,", "Designed to protect a large number of items "
                                                   "from a mage-council's rivals,")],
    "oath-of-justice": [("swear their oath in Kols's name",
                         "swear their oath in the name of a god of oaths")],
    "orchid-s-drop": [("to recreate Artokus Kirran's feat of genius that created the sun orchid "
                       "elixir", "to recreate the legendary feat of genius that created the sun "
                                 "orchid elixir")],
    "passing-fancy": [("Taldor's infamous Lion Blades imported this spell from the ninja clans "
                       "of Minkai, and both groups use it",
                       "An empire's infamous spymasters imported this spell from the ninja "
                       "clans of a distant land, and both groups use it")],
    "petulengro-s-validation": [("Venture-Captain Eliza Petulengro devised",
                                 "an adventuring captain devised")],
    "pinecone-bomb": [("Created by Ghorus when he was working to create the ghorans,",
                       "Created by the god who made the ghorans, while making them,")],
    "planar-inquiry": [
        ("Although he was hardly the first to turn to the Outer Planes for answers, Jatembe's "
         "dealings with outsiders in his pursuit of enlightenment are legendary, and the "
         "Magaambya credits the Old-Mage with the creation of this spell.",
         "Although he was hardly the first to turn to the Outer Planes for answers, a "
         "legendary old mage's dealings with outsiders in his pursuit of enlightenment are "
         "why his academy credits him with the creation of this spell.")],
    "planar-orientation": [("such as the Eldest of the First World or Heaven's various "
                            "Empyreal Lords and deities",
                            "such as the fey lords of the First World or Heaven's various "
                            "lords and deities")],
    "preserve-grace": [("The Lantern Bearers must often make difficult decisions",
                        "Elven light-bearers on crusade must often make difficult decisions")],
    "protection-from-spores": [("created by the seeded, by the spell what grows within, or by "
                                "Xhamen-Dor.", "created by the seeded or by the fungal powers "
                                               "they serve.")],
    "pugwampi-s-grace": [("Hated by adventurers throughout the Inner Sea region, the gremlins",
                          "Hated by adventurers everywhere, the gremlins")],
    "rune-of-jandelay": [
        ("When inscribed, the rune of Jandelay manifests as a shape that evokes the face of a "
         "monstrous elephantine creature-the legendary Oliphant of Jandelay itself.",
         "When inscribed, the rune of order manifests as a shape that evokes the face of a "
         "monstrous elephantine creature, a legendary guardian of law."),
        ("a potent ward against the primal chaos of the Great Beyond",
         "a potent ward against primal chaos")],
    "rune-of-rule": [
        ("Investigations into the ancient and mysterious traditions of the seven virtues of "
         "rule of the lost human empire of Azlant, which were later corrupted by the runelords "
         "into the more familiar seven deadly sins, inspired the Cyphermages to develop the "
         "runes of rule.",
         "Investigations into the ancient and mysterious traditions of the seven virtues of "
         "rule of a lost human empire, which were later corrupted into the more familiar seven "
         "deadly sins, inspired rune-scholars to develop the runes of rule.")],
    "runic-overload": [(" (Pathfinder Campaign Setting: Lost Cities of Golarion 60)", "")],
    "sarzari-shadow-memory": [
        ("beseech Achaekek to grant you access to the knowledge and lore contained within the "
         "innermost sanctum of the Crimson Citadel, the Sarzari Library.",
         "beseech a god of assassins to grant you access to the knowledge and lore kept in the "
         "innermost library of its order.")],
    "scribe-s-binding": [("Hermea's benevolent Council of Enlightenment uses this spell",
                          "A benevolent island council uses this spell")],
    "shadow-barbs": [("developed originally by priests of Zon-Kuthon in Nidal's early years",
                      "developed originally by priests of a god of pain")],
    "sharesister": [
        ("Ithuna Vardsdottir claims to have unearthed this ancient prayer in a ruined temple of "
         "Desna, though Pathfinders have reported the use of similar magic in Irrisen among "
         "the White Witches.",
         "An explorer claims to have unearthed this ancient prayer in a ruined temple of a "
         "goddess of travel, though others have reported the use of similar magic among a "
         "cabal of winter witches.")],
    "shield-of-the-dawnflower-greater": [("or shield of the Dawnflower (The Inner Sea World "
                                          "Guide 296)", "or shield of dawn")],
    "sign-of-the-dawnflower": [("that you are a worshiper of Sarenrae",
                                "that you are a worshiper of your god")],
    "snow-shape": [("Ulfen druids developed a variation", "northern druids developed a "
                                                          "variation")],
    "song-of-kyonin": [("Certain elven bards of Kyonin are known", "Certain elven bards are "
                                                                   "known")],
    "sotto-voce": [("originated among the followers of the Whispering Way, but necromancers "
                    "and other intimidating folk outside that group",
                    "originated among a secretive cult of necromancers, but necromancers and "
                    "other intimidating folk outside that cult")],
    "soul-vault": [("Any spellcaster that worships Abadar may learn",
                    "Any spellcaster that worships a god of wealth and law may learn")],
    "soulreaver": [("Favored by the necromancer Geb as a tool",
                    "Favored by an ancient necromancer-king as a tool")],
    "soulseeker": [("beneath the boughs of the Witchwood", "beneath the boughs of its great "
                                                           "forest")],
    "spawn-calling": [
        ("Having attained the highest and most profane form of magical achievement in the "
         "Great Destroyer's service, you are able to call forth his most dreaded creations: "
         "the Spawn of Rovagug.",
         "Having attained the highest and most profane form of magical achievement in the "
         "service of a god of destruction, you are able to call forth its most dreaded "
         "creations: the spawn of the destroyer."),
        ("a Spawn of Rovagug emerges", "a spawn of the destroyer emerges"),
        ("the called Spawn of Rovagug", "the called spawn of the destroyer"),
        ("Because the Spawn of Rovagug are", "Because the spawn of the destroyer are")],
    "speak-local-language": [
        ("a regional human language, such as Varisian or Common (Taldane in the Inner Sea "
         "region or Tien in Tian Xia)", "a regional human language, such as Common or a local "
                                        "trade tongue"),
        ("such as Ancient Osiriani or Jistka", "such as the tongue of a fallen empire")],
    "spellscar": [("the same sort of magical devastation that created the Mana Wastes so long "
                   "ago", "the same sort of magical devastation that created the great "
                          "magic-blasted wastelands long ago")],
    "spirit-share": [("but adventuring Caydenites have repurposed",
                      "but adventuring followers of a god of freedom have repurposed")],
    "stolen-light": [("Kreighton Shaine researched this spell from the fragmentary notes of a "
                      "Vudrani ascetic", "A scholar researched this spell from the fragmentary "
                                         "notes of a distant ascetic")],
    "strand-of-the-tangled-knot": [("You mimic tugging at the Green Mother's legendary Tangled "
                                    "Knot", "You mimic tugging at a fey goddess's legendary "
                                            "Tangled Knot")],
    "summon-barghest-i": [("from the Abyssal realm of Basalfeyst to serve",
                           "from its Abyssal realm to serve")],
    "summon-totem-creature": [
        ("The Shoanti revere more than the deities of distant planes",
         "Some tribes revere more than the deities of distant planes"),
        ("Shoanti spellcasters have learned ways to call upon the might of their quahs' totem "
         "creatures", "Their spellcasters have learned ways to call upon the might of their "
                      "clans' totem creatures"),
        ("A character must have been raised by the Shoanti and be considered part of a quah",
         "A character must have been raised by such a tribe and be considered part of one of "
         "its clans")],
    "suppress-primal-magic": [
        ("Nexian wizards first created this spell while researching the nature of the Mana "
         "Wastes,", "Wizards first created this spell while researching the nature of a "
                    "magic-blasted wasteland,"),
        ("The best the Nexians could manage", "The best they could manage")],
    "sustaining-legend": [("The rulers of Azlant are thought", "The rulers of a lost empire are "
                                                               "thought")],
    "tactical-adaptation": [("developed by an Aldori Academy student after several weeks of "
                             "observing (and occasionally joining) Restov barroom brawls",
                             "developed by a dueling-academy student after several weeks of "
                             "observing (and occasionally joining) barroom brawls")],
    "teleport-trap": [("The Pathfinders of the Grand Lodge make use of",
                       "A famous explorers' lodge makes use of"),
                      ("At least one crypt of the Whispering Tyrant makes use",
                       "At least one crypt of an ancient lich-tyrant makes use")],
    "tomb-legion": [("Though the spell has fallen out of favor among the Risen Guard because "
                     "the Ruby Prince frowns on the use of undead, this spell is popular among "
                     "followers of the Whispering Way.",
                     "Though the spell has fallen out of favor among royal guards whose ruler "
                     "frowns on the use of undead, it is popular among cults of undeath.")],
    "unflappable-mien": [("Members of the Prophet of Kalistrade prestige class",
                          "Members of an ascetic merchant-prophets' prestige class")],
    "unspoken-name": [("this spell is said to be used by Arazni to identify those followers "
                       "who dare refer to her as \"the Harlot Queen\" so she might summarily "
                       "dismiss them.",
                       "this spell is said to be used by a vengeful goddess to identify those "
                       "followers who dare speak a name she hates so she might summarily "
                       "dismiss them.")],
    "urgathoa-s-beacon": [("in Urgathoa's unclean influence", "in an unclean influence")],
    "vex-giant": [("The giants and their kin have long plagued the peoples of Varisia, "
                   "particularly the Shoanti of the Storval Plateau.",
                   "Giants and their kin have long plagued the peoples of the highlands."),
                  ("Among the various tactics and methods the Shoanti have developed",
                   "Among the various tactics and methods those peoples have developed")],
    "watchful-eye": [(f"Folgrit{U}s motherly protection", "a mother goddess's protection")],
    "woodland-rune": [("Created by Ghorus as a safety measure",
                       "Created by a druid-god as a safety measure")],
    "zone-of-foul-flames": [("The twisted druids of the Uskwood forsook fire in ages past for "
                             "the glory of Zon-Kuthon.",
                             "Twisted druids of a shadowed forest forsook fire in ages past for "
                             "the glory of a god of pain."),
                            ("these servants of Nidal know well", "these servants of darkness "
                                                                  "know well")],
}

FEAT_EDITS: dict[str, list[tuple[str, str]]] = {
    "aldori-dueling-mastery": [("You have mastered the grueling fighting style perfected by "
                                "the Aldori Swordlords.",
                                "You have mastered the grueling fighting style of the "
                                "dueling-sword masters.")],
    "andoren-falconry": [("You know the secret Andoren arts of falconry developed by the "
                          "Novotnian family of Darkmoon Vale.",
                          "You know the secret arts of falconry handed down by a noble family "
                          "of falconers.")],
    "arcane-vendetta": [("(such as Numeria's Technic League or the White Witches of Irrisen)",
                         "(such as a cabal of tyrant wizards or a ruling coven of witches)")],
    "careful-speaker": [("(such as Cheliax or Galt)",
                         "(such as a devil-ruled empire or a land in endless revolution)")],
    "cypher-magic": [("These unusual methods were initially devised by the Cyphermages of "
                      "Riddleport, but they have since spread far and wide through the Inner "
                      "Sea region.",
                      "These unusual methods were initially devised by a society of "
                      "rune-scholars in a pirate city, but they have since spread far and "
                      "wide.")],
    "cypher-script": [("Cypher Script was originally developed by the Cyphermages of "
                       "Riddleport, but has been spreading through the Inner Sea region "
                       "recently.",
                       "Cypher Script was originally developed by a society of rune-scholars, "
                       "but has been spreading far and wide recently.")],
    "deadly-dealer": [
        ("Harrow cards are treated as masterwork weapons", "Fortune-telling cards are treated "
                                                           "as masterwork weapons"),
        ("A harrow deck can no longer", "A fortune-telling deck can no longer"),
        # The import appended Thunder and Fang's whole entry to this feat's benefit — a
        # spreadsheet error, and the only Shoanti in the row. Thunder and Fang is its own row.
        (" You have mastered the ancient Shoanti Thunder and Fang fighting style, allowing you "
         "to fight with increased effectiveness when wielding an earth breaker and klar. "
         "Prerequisites: Str 15, Two-Weapon Fighting, Weapon Focus (earth breaker), Weapon "
         "Focus (klar) You can use an earth breaker as though it were a one-handed weapon. "
         "When using an earth breaker in one hand and a klar in your off hand, you retain the "
         "shield bonus your klar grants to your Armor Class even when you use it to attack. "
         "Treat your klar as a light weapon for the purposes of determining your two-weapon "
         "fighting penalty.", "")],
    "fortune-teller": [("a Harrow deck, or some such item", "a fortune-telling deck, or some "
                                                            "such item"),
                       ("(such as Varisia or Ustalav)",
                        "(such as a land of wandering fortune-tellers or haunted moors)")],
    "hamatulatsu": [("normally only taught to women of the Sisterhood of the Golden Erinyes.",
                     "normally only taught to the women of a secretive infernal sisterhood.")],
    "harrowed": [("Numerous Harrow readings early in your life",
                  "Numerous fortune-telling readings early in your life"),
                 ("draw a card from a Harrow deck you own",
                  "draw a card from a fortune-telling deck you own")],
    "eye-of-the-arclord": [("the esoteric teachings of the Arclords of Nex allows you",
                            "the esoteric teachings of an ancient mage-council allows you")],
    "hermean-blood": [("It's possible that Hermean agents may come looking for you",
                       "It's possible that the island's agents may come looking for you"),
                      ("You are the descendant of someone recruited to Hermea or the bastard "
                       "result of a Hermean's illicit pairing with someone foreign to that "
                       "land.",
                       "You are the descendant of someone recruited to an island bred for "
                       "perfection, or the bastard result of an islander's illicit pairing "
                       "with an outsider.")],
    "lastwall-phalanx": [("When battling the terrifying hordes of Belkzen,",
                          "When battling the terrifying orc hordes,")],
    "mounted-blade": [("Qadira affinity", "affinity with a desert nation of horsemen")],
    "scholar": [("scattered throughout the Inner Sea region", "scattered throughout the world")],
    "serpent-lash": [(" This feat originally appeared in Pathfinder Campaign Setting: Osirion, "
                      "Land of the Pharaohs.", "")],
    "shade-of-the-uskwood": [
        ("who dwell within the heart of the Uskwood", "who dwell within the heart of a "
                                                      "shadowed forest"),
        ("the deepening cold of the Midnight Lord's hallowed hunting grounds",
         "the deepening cold of a god of darkness's hallowed hunting grounds"),
        ("to the fell power of the Uskwood", "to the fell power of that forest"),
        ("the shadowy heart of the Uskwood is severed", "the shadowy heart of the forest is "
                                                        "severed"),
        ("This process requires a journey to the Uskwood and an atonement spell cast by a "
         "fellow worshiper of Zon-Kuthon.",
         "This process requires a journey to the forest and an atonement spell cast by a "
         "fellow worshiper of the god of pain."),
        ("patron deity Zon-Kuthon", "patron deity a god of pain and darkness")],
    "taldan-duelist": [("You trained at one of Taldor's elite fighting schools",
                        "You trained at one of an old empire's elite fighting schools")],
    "talmandor-s-lifting": [("You felt the powerful wings of Talmandor surround you when you "
                             "risked death from a fall, and somehow a tiny spark of his essence",
                             "You felt powerful angelic wings surround you when you risked "
                             "death from a fall, and somehow a tiny spark of their essence")],
    "tapestry-traveler": [("Your many visits to the Hao Jin Tapestry demiplane",
                           "Your many visits to a vast tapestry demiplane")],
    "thunder-and-fang": [("the ancient Shoanti Thunder and Fang fighting style",
                          "the ancient Thunder and Fang fighting style")],
    "totem-spirit": [
        ("depends on which Shoanti tribe you belong to: Lyrune-Quah (Moon Clan):",
         "depends on which clan of your tribe you belong to: Moon Clan:"),
        ("Shadde-Quah (Axe Clan):", "Axe Clan:"),
        ("Shriikirri-Quah (Hawk Clan):", "Hawk Clan:"),
        ("Shundar-Quah (Spire Clan):", "Spire Clan:"),
        ("Sklar-Quah (Sun Clan):", "Sun Clan:"),
        ("Skoan-Quah (Skull Clan):", "Skull Clan:"),
        ("Tamiir-Quah (Wind Clan):", "Wind Clan:"),
        ("Member of a Shoanti tribe", "Member of a clan-based tribe that honors totem spirits")],
    "tribal-scars": [("depending on which Mammoth Lords following you belong to",
                      "depending on which following of the mammoth-riding tribes you belong "
                      "to"),
                     ("Member of a Mammoth Lords tribe or following",
                      "Member of a mammoth-riding tribe or following")],
    "varisian-tattoo": [
        ("The spelllike ability gained (and its Varisian name) are as follows:",
         "The spell-like ability gained is as follows:"),
        ("Abjuration (avidais):", "Abjuration:"), ("Conjuration (idolis):", "Conjuration:"),
        ("Enchantment (carnasia):", "Enchantment:"), ("Evocation (ragario):", "Evocation:"),
        ("Illusion (vangloris):", "Illusion:"), ("Necromancy (voratalo):", "Necromancy:"),
        ("Transmutation (avaria):", "Transmutation:"),
        ("These tattoos mark you as a worker of the ancient traditions of Varisian magic.",
         "These tattoos mark you as a worker of an ancient tradition of tattoo magic."),
        ("A Varisian tattoo typically consists of a long string of complex characters from the "
         "Thassilonian alphabet.", "A mystic tattoo typically consists of a long string of "
                                   "complex characters from an ancient alphabet.")],
    "vengeful-banisher": [("such as the Worldwound or the Abyss",
                           "such as a demon-blighted rift or the Abyss")],
    "versatile-spontaneity": [("You made a good name for yourself in the Pathf inder Society",
                               "You made a good name for yourself among adventurers")],
    "wand-dancer": [("in a tradition of Garundi courtesans", "in a tradition of desert "
                                                             "courtesans")],
}


# --- applying ----------------------------------------------------------------------------------

class StaleEdit(ValueError):
    """An edit found neither the words it replaces nor the words it writes: the source text
    changed under the table, and the name it was written to remove may still be there."""


_KEEP = {"id", "source", "tags", "feat"}       # keys whose values are ids, not prose


def _map_strings(value, fn, key: str = ""):
    if key in _KEEP:
        return value
    if isinstance(value, str):
        return fn(value)
    if isinstance(value, list):
        return [_map_strings(v, fn) for v in value]
    if isinstance(value, dict):
        return {k: _map_strings(v, fn, k) for k, v in value.items()}
    return value


def _strings(value, key: str = ""):
    if key in _KEEP:
        return
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _strings(v, k)


def _edits_for(table: dict, row_id: str, renames: dict) -> list[tuple[str, str]]:
    """A row's edits, keyed by its original id and found again after the rename, so a
    second run re-checks them instead of skipping them."""
    original = next((old for old, (new, _n) in renames.items() if new == row_id), row_id)
    return table.get(original, [])


def _edit_row(row: dict, edits: list[tuple[str, str]]) -> dict:
    for old, new in edits:
        text = "\n".join(_strings(row))
        if old in text:
            row = _map_strings(row, lambda s, o=old, n=new: s.replace(o, n))
        elif not new or new in text:
            continue                        # already applied: the table is idempotent
        else:
            raise StaleEdit(f"{row.get('id')}: {old[:70]!r} not found")
    return row


def _renamer(renames: dict[str, str], lowercase: bool):
    """A function rewriting every old name to its new one in running text.

    Spell names are lower case in Paizo's prose ("functions as antimagic field") and feat
    names title case ("the Cypher Magic feat"); either way a name opening a sentence opens
    it capitalised."""
    if not renames:
        return lambda s: s
    olds = sorted(renames, key=len, reverse=True)
    pattern = re.compile(r"(?<![\w'])(" + "|".join(map(re.escape, olds)) + r")(?!\w)",
                         re.IGNORECASE)
    by_lower = {o.lower(): n for o, n in renames.items()}

    def swap(m: re.Match) -> str:
        new = by_lower[m.group(1).lower()]
        if lowercase:
            new = new.lower()
        before = m.string[:m.start()].rstrip()
        if not before or before[-1] in ".!?:\n\"(":
            new = new[0].upper() + new[1:]
        return new

    return lambda s: pattern.sub(swap, s)


def _common(s: str) -> str:
    for old, new in COMMON:
        s = s.replace(old, new)
    for pattern, new in PRODUCT:
        s = pattern.sub(new, s)
    return s


def _lore_names():
    """The deny-list's own matcher (tools/content_provenance.py), for the list columns."""
    import content_provenance as cp
    return cp.NAME_RE, cp.CLASS_OF, cp.LORE


def _clear_columns(row: dict) -> dict:
    """The `deity` and `bloodline` columns lose their Golarion entries. No code reads the
    deity column (the 2026-09-19 ruling keeps deity out of the engine), and the Harrowed
    bloodline is a setting bloodline this app does not offer."""
    name_re, class_of, lore = _lore_names()
    for col in ("deity", "bloodline"):
        value = row.get(col)
        if not isinstance(value, str) or not value:
            continue
        kept = [part.strip() for part in value.split(",")
                if not any(class_of.get(m.group(1)) in lore for m in name_re.finditer(part))]
        row[col] = ", ".join(p for p in kept if p)
    return row


def apply_spells(entries: list[dict]) -> tuple[list[dict], dict[str, str | None]]:
    """The shipped spells rewritten, and old id -> current id (None: dropped)."""
    aliases: dict[str, str | None] = dict(SPELL_DROPS)
    names = {}
    by_id = {e.get("id"): e for e in entries}
    for old, (new_id, new_name) in SPELL_RENAMES.items():
        aliases[old] = new_id
        row = by_id.get(old) or by_id.get(new_id)
        if row is None:
            raise StaleEdit(f"spell {old!r} is neither shipped nor already renamed")
        if row.get("id") == old:
            names[row["name"]] = new_name
    rename = _renamer(names, lowercase=True)
    out = []
    for e in entries:
        sid = e.get("id")
        if sid in SPELL_DROPS:
            continue
        e = _edit_row(dict(e), _edits_for(SPELL_EDITS, sid, SPELL_RENAMES))
        e = _rewrite_prose(e, lambda s: rename(_common(s)))
        e = _clear_columns(e)
        if sid in SPELL_RENAMES:
            e["id"], e["name"] = SPELL_RENAMES[sid]
        out.append(e)
    return out, aliases


def apply_feats(entries: list[dict]) -> tuple[list[dict], dict[str, str | None]]:
    """The shipped feats rewritten, and old id or old lower-case name -> current id."""
    aliases: dict[str, str | None] = dict(FEAT_DROPS)
    by_id = {e.get("id"): e for e in entries}
    names = {}
    for old, (new_id, new_name) in FEAT_RENAMES.items():
        aliases[old] = new_id
        row = by_id.get(old) or by_id.get(new_id)
        if row is None:
            raise StaleEdit(f"feat {old!r} is neither shipped nor already renamed")
        if row.get("id") == old and row["name"].lower() != new_name.lower():
            names[row["name"]] = new_name
            # Sheets store feats by lower-cased name ("weapon focus (rapier)").
            aliases[row["name"].strip().lower()] = new_id
    for old, target in FEAT_DROPS.items():
        row = by_id.get(old)
        if row is not None:
            aliases.setdefault(row["name"].strip().lower(), target)
    rename = _renamer(names, lowercase=False)

    def gods(s: str) -> str:
        return WORSHIPER_RE.sub(lambda m: f"{m.group(1)} {GODS[m.group(2)]}", s)

    out = []
    for e in entries:
        fid = e.get("id")
        if fid in FEAT_DROPS:
            continue
        e = _edit_row(dict(e), _edits_for(FEAT_EDITS, fid, FEAT_RENAMES))
        e = _rewrite_prose(e, lambda s: gods(rename(_common(s))))
        for cond in e.get("prerequisites") or []:
            if cond.get("kind") == "feat" and cond.get("feat") in FEAT_RENAMES:
                cond["feat"] = FEAT_RENAMES[cond["feat"]][0]
        if fid in FEAT_RENAMES:
            e["id"], e["name"] = FEAT_RENAMES[fid]
        out.append(e)
    return out, aliases


def apply_weapons(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        row = dict(row)
        if row.get("id") in WEAPON_RENAMES:
            row["id"], row["name"] = WEAPON_RENAMES[row["id"]]
        out.append(row)
    return out


def _rewrite_prose(row: dict, fn) -> dict:
    """Every string but the row's own title: a renamed row is titled from the table, and a
    title that merely contains an old name must not be lower-cased by the prose renamer."""
    title = row.get("name")
    row = _map_strings(row, fn)
    if title is not None:
        row["name"] = _common(title)
    return row


def spell_renamer(entries: list[dict]):
    """The prose rewrite for this project's own writing about spells (the mechanics files'
    `target` and `notes`), built from the shipped names before they change."""
    names = {e["name"]: SPELL_RENAMES[e["id"]][1] for e in entries
             if e.get("id") in SPELL_RENAMES}
    rename = _renamer(names, lowercase=True)
    return lambda s: rename(_common(s))
