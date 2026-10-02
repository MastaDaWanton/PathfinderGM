You are tagging a Pathfinder 1e herbalism corpus for a solo play app.

Each ingredient below needs six preparation flags. They govern what a player is allowed
to do with it at the crafting bench, so the answers have to follow from what the entry
actually says — not from what the herb is called, and not from real-world herbalism.

The flags, and what each one means mechanically:

  needs_extraction  The usable part is inside something: a shell, a husk, a pod, a
                    gland, a sac, bark that must be stripped, a stone in a fruit.
                    Nothing else can be done to it until it is out.

  volatile          It reacts badly to being worked: it ignites, burns, blisters,
                    fumes, explodes, corrodes, or is a contact poison in the raw. It
                    must be neutralised before it can be ground.

  can_grind         It can be reduced to powder at all. Say no for things that are wet,
                    fleshy, gelatinous, liquid, or that the text says must stay whole.

  mix_raw           It can go straight into a cold mixture. Say no if the text implies
                    the whole form is inert and it must be broken down first.

  brew_raw          It can go straight into the pot. Say no if it needs grinding first
                    to give anything up. This flag also decides whether the herb can be
                    infused into a finished tincture raw, so weigh it accordingly.

  animal            It came from a creature: gland, blood, scale, horn, ichor, carapace,
                    venom, organ, hide. These spoil in 48 hours rather than a week.

Rules for your answer:

* Default to the ordinary case. Most herbs are leaves and roots: they grind, they mix
  raw, they brew raw, they are not volatile, they need no extraction. Only depart from
  that when the entry gives you a reason.
* Quote your reason. For every flag you set away from the default, give the phrase from
  the entry that justifies it. If you cannot quote one, do not set the flag.
* Do not invent. If an entry is too thin to judge, leave it at defaults and say so.
* `kind` is a strong hint for `animal` — "monster part" is almost always yes — but read
  the text, because a few are plants growing on creatures.

Each ingredient also already carries the herbalism tags below, shown as its current
values. Check them against the text and propose a change only where the text disagrees.

  part         What of it is used. One of: leaf, flower, root, bark, berry, seed, sap,
               resin, fungus, gland, organ, bone, horn, feather, scale, eye, shell, oil,
               wax, mineral, liquid. Read it off the text ("the bark", "the sap", "the
               root"). If the text never says, leave the default: leaf for a herb,
               organ for a monster part, fungus for a fungus.

  route        On each effect: how that effect reaches the body. One of:
                 ingest    eaten, drunk, chewed, a tea, a pill
                 skin      rubbed on, a salve, a lotion, a worn patch
                 eyes      dropped in or smeared on the eyes or eyelids
                 wound     bound on, packed into or washed over a wound
                 inhale    smoked, snorted, breathed as incense or vapour
                 external  the effect reaches OUTSIDE the body or changes what
                           others perceive: invisibility, light, flight, charming
                           another, a cloud over an area, a coating on a blade or
                           arrow that acts on a target, incorporeality, a ward
                           on a place or an object
               An effect on or in the taker's own body is never external, even when it
               is magical: seeing the invisible through an eye salve is `eyes`, an
               immunity swallowed is `ingest`, fire resistance rubbed on is `skin`.

  hybrid       true when any effect is magical: planar flora, every monster part,
               anything supernatural. A hybrid appears on both the herbalist's and the
               alchemist's shelves. Every `external` effect should be on a hybrid,
               unless it is plainly not herbalism at all (a glue, an ink, a blade poison).

  base_for     ["salve"] for every bark, sap and resin: ground bark and tree sap
               thicken a salve. ["cream"] for a slippery, mucilaginous root, shoot
               or gel (marshmallow, mallow). Otherwise [].

  solvent, neutralizer   Leave these alone. Only the bench's reagents (oil, spirits,
               vinegar, lime, charcoal, clay) carry them, and those live on the
               materials shelf, not in this list.

Answer with JSON only, in exactly this shape, one object per ingredient you are
changing from the defaults or from its current tags. Omit any ingredient you are
leaving alone. Give `routes` as a full list, one per effect, in the order shown:

{
  "adder-s-tongue": {
    "needs_extraction": false,
    "volatile": true,
    "can_grind": true,
    "mix_raw": false,
    "brew_raw": true,
    "animal": false,
    "part": "leaf",
    "routes": ["wound"],
    "hybrid": false,
    "why": {"volatile": "the sap blisters skin", "mix_raw": "inert until crushed",
            "routes": "the ointment is laid on the wound"}
  }
}

The ingredients follow.

```json
[
 {
  "id": "acacia",
  "name": "Acacia",
  "kind": "herb",
  "tier": "common",
  "description": "Acacia's gummy resin burns as a sweet incense: breathing the smoke gives a +1 alchemical bonus on Will saves for an hour. Melted into an ointment, the gum soothes raw skin and heals 1d3 non-lethal damage, and dissolved in water it coats a sore throat, +1 on Fortitude saves against coughs and sore throats for an hour. Ground, it thickens a salve.",
  "harvesting": "",
  "effects": [
   {
    "line": "+1 Will for 1 hour",
    "route": "inhale"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "skin"
   },
   {
    "line": "+1 Fortitude against coughs and sore throats for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "resin",
  "hybrid": false,
  "base_for": [
   "salve"
  ]
 },
 {
  "id": "aconite",
  "name": "Aconite",
  "kind": "herb",
  "tier": "common",
  "description": "Wolfsbane's blue-hooded leaves, chewed within the hour of a beast's bite, steel the blood: a +2 alchemical bonus on Fortitude saves for an hour, against lycanthropy and animal venom alike. It is still a poison. Whoever swallows it must make a DC 13 Fortitude save or be nauseated for 1d4 rounds and take 1d4 Strength damage, unless the bench has neutralised it. Rubbed on aching joints as a weak liniment, it heals 1d3 non-lethal damage.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude against lycanthropy and animal venom for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Fortitude DC 13",
    "route": "ingest"
   },
   {
    "line": "Causes nauseated for 1d4 rounds",
    "route": "ingest"
   },
   {
    "line": "1d4 Strength damage",
    "route": "ingest"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "skin"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "adder-s-tongue",
  "name": "Adder's-Tongue",
  "kind": "herb",
  "tier": "common",
  "description": "The leaves, boiled down with animal fat, make the old ointment called green oil of charity: spread on a wound it closes 1d3 hit points. Boiled as a tea for the convalescent, they heal 1d3 non-lethal damage and give a +1 alchemical bonus on Fortitude saves against infection for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d3 hit points",
    "route": "wound"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "ingest"
   },
   {
    "line": "+1 Fortitude against infection for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "aelfengrape",
  "name": "Aelfengrape",
  "kind": "herb",
  "tier": "uncommon",
  "description": "A grape vine elven wizards bred to glow like a candle and to feed a traveller. A handful of the pale fruit is a meal's worth of strength: 1d6 temporary hit points and a +2 alchemical bonus on Fortitude saves against hunger, thirst and fatigue, for an hour. Wine pressed from them lends elven nerve too, +2 on Will saves against fear for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "1d6 temporary hit points for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+2 Fortitude against hunger, thirst and fatigue for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+2 Will against fear for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "berry",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "allnight",
  "name": "Allnight",
  "kind": "herb",
  "tier": "common",
  "description": "A treated wafer that dissolves into chalky paste under the tongue and jolts the imbiber awake, ending fatigue at once, then a +2 alchemical bonus on Fortitude saves against fatigue and sleep, and +1 on initiative, for 8 hours. The jitters cost focus, a -2 penalty on Perception checks for as long.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude against fatigue and sleep for 8 hours",
    "route": "ingest"
   },
   {
    "line": "-2 Perception for 8 hours",
    "route": "ingest"
   },
   {
    "line": "+1 Initiative for 8 hours",
    "route": "ingest"
   },
   {
    "line": "Ends fatigued",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "althaea",
  "name": "Althaea",
  "kind": "herb",
  "tier": "common",
  "description": "Marshmallow root. Pulverized and bound on a wound as a poultice, it heals 1d4 hit points; spread on a burn, 1d3; brewed as a slippery tea for a raw throat, it heals 1d3 non-lethal damage. Its mucilage also sets a cream: the ground root thickens a cream base the way wax thickens a salve.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d4 hit points",
    "route": "wound"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "ingest"
   },
   {
    "line": "Heals 1d3 hit points",
    "route": "skin"
   }
  ],
  "part": "root",
  "hybrid": false,
  "base_for": [
   "cream"
  ]
 },
 {
  "id": "amaranth",
  "name": "Amaranth",
  "kind": "herb",
  "tier": "common",
  "description": "Pressed fresh on a wound as a poultice, amaranth closes it: it heals 1d4 hit points. Dried and taken as a tea, it heals 1d3 and gives a +1 alchemical bonus on Fortitude saves against disease for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d4 hit points",
    "route": "wound"
   },
   {
    "line": "Heals 1d3 hit points",
    "route": "ingest"
   },
   {
    "line": "+1 Fortitude against disease for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "angelica",
  "name": "Angelica",
  "kind": "herb",
  "tier": "common",
  "description": "The leaves brew into a bitter, warming draught that guards body and spirit: a +2 alchemical bonus on Fortitude saves against disease, and +1 on Will saves against hostile magic, for an hour. Burned as incense, the root's smoke gives +1 on Will saves against fear for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude against disease for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+1 Will against hostile magic for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+1 Will against fear for 1 hour",
    "route": "inhale"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "anise",
  "name": "Anise",
  "kind": "herb",
  "tier": "common",
  "description": "A sweet seed of many uses. Pressed into an oil and rubbed on the skin it gives a +1 alchemical bonus on Fortitude saves against skin diseases for a day. As a pill it gives +2 on Fortitude saves against disease for an hour, and its steam, breathed, gives +1 against stench and nauseating vapours for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+1 Fortitude to resist skin diseases for 24 hours",
    "route": "skin"
   },
   {
    "line": "+2 Fortitude against disease for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+1 Fortitude against stench and nauseating vapours for 1 hour",
    "route": "inhale"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "banshee-wail-essence",
  "name": "Banshee Wail Essence",
  "kind": "monster part",
  "tier": "exotic",
  "description": "A banshee's wail, caught in a sealed vial. Breathe it in and your own voice carries her edge: a +4 alchemical bonus on Intimidate checks and +3 on Will saves against fear, for 4 hours. The throat pays for it, and the rasping voice takes a -2 penalty on Diplomacy checks for the same 4 hours.",
  "harvesting": "The essence is captured in a sealed glass vial during the banshee’s wail, requiring quick reflexes to avoid its deafening effect.",
  "effects": [
   {
    "line": "+4 Intimidate for 4 hours",
    "route": "inhale"
   },
   {
    "line": "-2 Diplomacy for 4 hours",
    "route": "inhale"
   },
   {
    "line": "+3 Will against fear for 4 hours",
    "route": "inhale"
   }
  ],
  "part": "liquid",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "barbarian-chew",
  "name": "Barbarian Chew",
  "kind": "herb",
  "tier": "common",
  "description": "Dried leaves of a stunted northern bush, chewed until the teeth stain crimson. The bitter juice stokes the blood: a +2 alchemical bonus to Constitution and +1 on damage rolls for 10 minutes, the long breath of a raging fighter. The red grin costs -1 on Diplomacy checks for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Constitution for 10 minutes",
    "route": "ingest"
   },
   {
    "line": "+1 Damage rolls for 10 minutes",
    "route": "ingest"
   },
   {
    "line": "-1 Diplomacy for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "barley",
  "name": "Barley",
  "kind": "herb",
  "tier": "common",
  "description": "A plain cereal, brewed into ale or boiled into barley water. Drunk as the midwife's medicinal, it heals 1d3 non-lethal damage and gives a +1 alchemical bonus on Fortitude saves against heat and fatigue for an hour. Mashed warm into a poultice for bruises and boils, it heals 1d3 non-lethal damage.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "ingest"
   },
   {
    "line": "+1 Fortitude against heat and fatigue for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "skin"
   }
  ],
  "part": "seed",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "basil",
  "name": "Basil",
  "kind": "herb",
  "tier": "common",
  "description": "Five fresh leaves stuffed into a poisoned wound draw the venom: a +2 alchemical bonus on Fortitude saves against poison for an hour. Eaten, the leaves settle the stomach, +1 on Fortitude saves against nausea for an hour, and their bruised scent clears the head, +1 on Will saves for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude against the poison in the wound for 1 hour",
    "route": "wound"
   },
   {
    "line": "+1 Fortitude against nausea and stomach upsets for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+1 Will to clear the head for 1 hour",
    "route": "inhale"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "basilisk-eye",
  "name": "Basilisk Eye",
  "kind": "monster part",
  "tier": "rare",
  "description": "Ground and worked into a paste with holy water, the eye is smeared on the lids: immunity to gaze attacks and a +3 alchemical bonus on Fortitude saves against petrification, for 6 hours. Vision blurs while it lasts, a -4 penalty on Perception checks.",
  "harvesting": "The eye must be removed with a precise incision using an obsidian knife within 1 hour of the basilisk’s death, avoiding direct eye contact to prevent petrification.",
  "effects": [
   {
    "line": "-4 Perception for 6 hours",
    "route": "eyes"
   },
   {
    "line": "Immune to gaze attacks for 6 hours",
    "route": "eyes"
   },
   {
    "line": "+3 Fortitude against petrification for 6 hours",
    "route": "eyes"
   }
  ],
  "part": "eye",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "behemoth-hide",
  "name": "Behemoth Hide",
  "kind": "monster part",
  "tier": "legendary",
  "description": "Tanned and worn against the skin as a patch, a piece of behemoth hide toughens the wearer's own: a +5 natural armour bonus to AC and DR 3/- for 12 hours. It is heavy, a -2 penalty on Acrobatics checks for as long.",
  "harvesting": "The hide is stripped with a flensing knife after the behemoth is killed, requiring hours of labor due to its toughness.",
  "effects": [
   {
    "line": "+5 Armour class for 12 hours",
    "route": "skin"
   },
   {
    "line": "-2 Acrobatics for 12 hours",
    "route": "skin"
   },
   {
    "line": "DR 3/— for 12 hours",
    "route": "skin"
   }
  ],
  "part": "organ",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "belladonna",
  "name": "Belladonna",
  "kind": "herb",
  "tier": "common",
  "description": "Deadly nightshade. A drop of the juice in the eyes widens the pupils: a +2 alchemical bonus on Perception checks in dim light for an hour. Eaten within the hour of a lycanthrope's bite it gives +2 on Fortitude saves against the curse, at a price: a DC 15 save or nausea for 3 rounds and 1d8 poison damage.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Perception in dim light for 1 hour",
    "route": "eyes"
   },
   {
    "line": "+2 Fortitude against lycanthropy for 1 hour",
    "route": "ingest"
   },
   {
    "line": "DC 15",
    "route": "ingest"
   },
   {
    "line": "Causes nauseated for 3 rounds",
    "route": "ingest"
   },
   {
    "line": "1d8 poison damage",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "betony",
  "name": "Betony",
  "kind": "herb",
  "tier": "common",
  "description": "The flowers make a mild analgesic tea, good against colds: it heals 1d3 non-lethal damage and gives a +1 alchemical bonus on Fortitude saves against disease, and +1 on Will saves against fear and bad dreams, for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+1 Fortitude against disease for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "ingest"
   },
   {
    "line": "+1 Will against fear and bad dreams for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "flower",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "birthwort",
  "name": "Birthwort",
  "kind": "herb",
  "tier": "common",
  "description": "Crushed leaves and stems, their juice laid on a poisonous bite or sting within a round, give a +2 alchemical bonus on Fortitude saves against the poison for an hour; bound as a poultice the same juice closes 1d2 hit points. Never drink it: swallowed, it is a slow poison, a DC 12 Fortitude save or 1 Constitution damage.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude against poison for 1 hour",
    "route": "wound"
   },
   {
    "line": "Heals 1d2 hit points",
    "route": "wound"
   },
   {
    "line": "Fortitude DC 12",
    "route": "ingest"
   },
   {
    "line": "1 Constitution damage",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "bitterroot",
  "name": "Bitterroot",
  "kind": "herb",
  "tier": "common",
  "description": "Fermented, the root makes a punishing brew, drunk only as a preparation against drink: a +2 alchemical bonus on Fortitude saves for an hour, against strong drink and any poison swallowed with it. The bitterness wakes the gut and heals 1d3 non-lethal damage, and turns it too: the drinker is sickened for a minute.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude against strong drink and swallowed poison for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "ingest"
   },
   {
    "line": "Causes sickened for 1 minute",
    "route": "ingest"
   }
  ],
  "part": "root",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "blackthorn",
  "name": "Blackthorn",
  "kind": "herb",
  "tier": "common",
  "description": "Strewn about a room or worn in a buttonhole, blackthorn holds evil outsiders and demons off the way garlic keeps off vampires (+2 on Will saves against their powers, alchemy's use). The sloes of the same hedge, eaten, give the eater a +1 alchemical bonus on those Will saves for an hour, and the astringent juice, laid on a cut, heals 1d3 hit points.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Will vs the powers of evil outsiders and demons, while strewn or worn for 1 hour",
    "route": "external"
   },
   {
    "line": "+1 Will against the powers of evil outsiders for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Heals 1d3 hit points",
    "route": "wound"
   }
  ],
  "part": "leaf",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "bloodroot",
  "name": "Bloodroot",
  "kind": "herb",
  "tier": "common",
  "description": "A gnarled red root that bleeds a blood-like sap where it is cut, found under old battlegrounds. Drinking the sap gives 1d6 temporary hit points and a +1 alchemical bonus on Fortitude saves against coughs and colds for an hour, and clouds the mind: a -2 penalty to Intelligence for the hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "1d6 temporary hit points for 1 hour",
    "route": "ingest"
   },
   {
    "line": "-2 Intelligence for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+1 Fortitude against coughs and colds for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "root",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "blueweed",
  "name": "Blueweed",
  "kind": "herb",
  "tier": "common",
  "description": "Viper's bugloss. Powdered and sprinkled on an object, the leaves ritually purify it (alchemy's use). Steeped as a wash and rubbed on the skin, they give a +1 alchemical bonus on Will saves against curses for an hour; brewed and drunk, +2 on Fortitude saves against snake venom for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+1 Will vs curses and evil magic, once the object is ritually purified for 1 hour",
    "route": "external"
   },
   {
    "line": "+1 Will against curses for 1 hour",
    "route": "skin"
   },
   {
    "line": "+2 Fortitude against snake venom for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "borage",
  "name": "Borage",
  "kind": "herb",
  "tier": "common",
  "description": "Leaves and flowers, pulped and boiled, make a draught for breaking fevers. It heals 1d3 non-lethal damage and gives a +2 alchemical bonus on Fortitude saves against illness and poison for an hour. Borage brings courage, the old saying goes: +1 on Will saves for the hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude against illness and poison for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "ingest"
   },
   {
    "line": "+1 Will for courage for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "breeam",
  "name": "Breeam",
  "kind": "herb",
  "tier": "common",
  "description": "Dried bark tossed on a fire throws a smoke that sears undead nearby, 1d6 positive energy damage, and steadies the living against them, +2 on Will saves against fear of undead for 10 minutes (alchemy's use). Breathed by whoever lit it, the smoke gives a +1 alchemical bonus on Will saves against fear for 10 minutes. Ground, the bark is a salve base.",
  "harvesting": "",
  "effects": [
   {
    "line": "1d6 positive damage",
    "route": "external"
   },
   {
    "line": "+2 Will vs fear caused by undead, within the smoke for 10 minutes",
    "route": "external"
   },
   {
    "line": "+1 Will against fear for 10 minutes",
    "route": "inhale"
   }
  ],
  "part": "bark",
  "hybrid": true,
  "base_for": [
   "salve"
  ]
 },
 {
  "id": "bryony",
  "name": "Bryony",
  "kind": "herb",
  "tier": "common",
  "description": "Every part of this vine is poison if swallowed: a DC 14 save or nausea for 3 rounds and 1d3 Strength damage. Bruised and rubbed on aching joints as a liniment, the root heals 1d3 non-lethal damage and warms the skin, resist cold 2 for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "skin"
   },
   {
    "line": "DC 14",
    "route": "ingest"
   },
   {
    "line": "Causes nauseated for 3 rounds",
    "route": "ingest"
   },
   {
    "line": "1d3 Strength damage",
    "route": "ingest"
   },
   {
    "line": "Resist cold 2 for 1 hour",
    "route": "skin"
   }
  ],
  "part": "root",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "calendula",
  "name": "Calendula",
  "kind": "herb",
  "tier": "common",
  "description": "Marigold. Brewed, the flowers make a love-diviner's tea, a +2 alchemical bonus on Sense Motive in matters of the heart for an hour. Bound on a wound as a poultice, they close 1d3 hit points, and a marigold salve gives +1 on Fortitude saves against skin infection for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Sense Motive in matters of the heart for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Heals 1d3 hit points",
    "route": "wound"
   },
   {
    "line": "+1 Fortitude against skin infection for 1 hour",
    "route": "skin"
   }
  ],
  "part": "flower",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "caranator",
  "name": "Caranator",
  "kind": "herb",
  "tier": "common",
  "description": "Chew a piece of the root to clear the mind: a +2 alchemical bonus on Will saves against charms and enchantments and +1 on Sense Motive checks, for an hour. It numbs the tongue, a -1 penalty on Diplomacy checks for as long.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Will against charms and enchantments for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+1 Sense Motive for 1 hour",
    "route": "ingest"
   },
   {
    "line": "-1 Diplomacy for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "root",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "cave-star",
  "name": "Cave Star",
  "kind": "herb",
  "tier": "common",
  "description": "Prepared and stored in glass, the leaf gives off a cold light for four hours with neither heat nor smoke (alchemy's use). Steeped and drunk, the light seems to settle in the chest, a +1 alchemical bonus on Will saves against fear in the dark for an hour; as an eyewash, +1 on Perception checks in darkness for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+1 Will against fear in the dark for 1 hour",
    "route": "ingest"
   },
   {
    "line": "A cold glass-held light, without heat or smoke for 4 hours",
    "route": "external"
   },
   {
    "line": "+1 Perception in darkness for 1 hour",
    "route": "eyes"
   }
  ],
  "part": "leaf",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "chasmyre-leaf",
  "name": "Chasmyre Leaf",
  "kind": "herb",
  "tier": "common",
  "description": "A sickly brown-black leaf of swamp shrubs. Crushed and smeared on the eyelids, it opens the eyes to the dark, a +2 alchemical bonus on Perception checks in dim light for an hour, though it stings: dazzled for the first minute. Chewed, it gives +1 on Fortitude saves against swamp fever for an hour. It keeps for a few weeks.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Perception in dim light for 1 hour",
    "route": "eyes"
   },
   {
    "line": "+1 Fortitude against swamp fever for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Causes dazzled for 1 minute",
    "route": "eyes"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "chimera-horn",
  "name": "Chimera Horn",
  "kind": "monster part",
  "tier": "exotic",
  "description": "Pulverized and snorted, the horn hardens body and will against chaos: a +3 alchemical bonus on Fortitude and Will saves for 4 hours. The user turns erratic and suspicious, a -3 penalty on Sense Motive checks for as long.",
  "harvesting": "The horn must be sawed off with a diamond-edged blade after the chimera is incapacitated, as it resists lesser tools.",
  "effects": [
   {
    "line": "+3 Will against chaotic magic for 4 hours",
    "route": "inhale"
   },
   {
    "line": "+3 Fortitude against chaotic magic for 4 hours",
    "route": "inhale"
   },
   {
    "line": "-3 Sense Motive for 4 hours",
    "route": "inhale"
   }
  ],
  "part": "horn",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "cloth-of-gold",
  "name": "Cloth of Gold",
  "kind": "herb",
  "tier": "common",
  "description": "A spell component, dye and spice. Chew a flower or six leaves and animals seem to make sense for a while: a +2 alchemical bonus on Handle Animal, Ride, and Knowledge (nature) checks about animals, for 10 minutes.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Handle Animal for 10 minutes",
    "route": "ingest"
   },
   {
    "line": "+2 Knowledge (Nature) about animals for 10 minutes",
    "route": "ingest"
   },
   {
    "line": "+2 Ride for 10 minutes",
    "route": "ingest"
   }
  ],
  "part": "flower",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "cockatrice-beak",
  "name": "Cockatrice Beak",
  "kind": "monster part",
  "tier": "uncommon",
  "description": "Ground into a paste and worked into boots, the beak carries its wearer over difficult terrain for 6 hours, though the feet feel heavy (-2 Acrobatics; alchemy's use). Taken in a tea, the powder gives a +2 alchemical bonus on Fortitude saves against petrification for an hour.",
  "harvesting": "The beak must be broken off with a hammer and chisel after the cockatrice is killed, avoiding its petrifying gaze residue.",
  "effects": [
   {
    "line": "Immune to difficult terrain for 6 hours",
    "route": "external"
   },
   {
    "line": "-2 Acrobatics for 6 hours",
    "route": "external"
   },
   {
    "line": "+2 Fortitude against petrification for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "horn",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "coldwood",
  "name": "Coldwood",
  "kind": "herb",
  "tier": "uncommon",
  "description": "Fey-grown wood as strong as iron with none of iron's harm to fey: weapons and armour are made of it. A coldwood weapon bites fey harder, +1 damage for a day of use, and worked coldwood guards its bearer against fey magic, +1 on Will saves (alchemy's and the smith's use). A tea of the bark gives a +2 alchemical bonus on Will saves against fey enchantment for an hour. Ground, the bark is a salve base.",
  "harvesting": "",
  "effects": [
   {
    "line": "+1 Damage rolls a coldwood weapon against fey for 1 day",
    "route": "external"
   },
   {
    "line": "+1 Will vs fey magic, carrying worked coldwood for 1 hour",
    "route": "external"
   },
   {
    "line": "+2 Will against fey enchantment for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "bark",
  "hybrid": true,
  "base_for": [
   "salve"
  ]
 },
 {
  "id": "comfrey",
  "name": "Comfrey",
  "kind": "herb",
  "tier": "common",
  "description": "Wonder weed, knitbone. The root, laid on a fresh wound at once, heals 1d4 hit points that were never quite done in the first place. As a tea or in wine during recovery it heals 1d3 non-lethal damage, and as a salve on bruises 1d3 more.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1-4 hit points",
    "route": "wound"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "ingest"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "skin"
   }
  ],
  "part": "root",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "cotsbalm",
  "name": "Cotsbalm",
  "kind": "herb",
  "tier": "exotic",
  "description": "The sap is the base of purebalm, a clear salve poured over the skin of someone poisoned by a wound or a touch. It turns black as it draws the poison out: a +4 alchemical bonus on Fortitude saves against poison for an hour, and it heals 2d4 hit points of the harm. Packed into a poisoned wound it gives +3 on those saves for an hour. The sap itself thickens any salve.",
  "harvesting": "",
  "effects": [
   {
    "line": "+4 Fortitude against poison for 1 hour",
    "route": "skin"
   },
   {
    "line": "Heals 2d4 hit points",
    "route": "skin"
   },
   {
    "line": "+3 Fortitude against poison in the wound for 1 hour",
    "route": "wound"
   }
  ],
  "part": "sap",
  "hybrid": false,
  "base_for": [
   "salve"
  ]
 },
 {
  "id": "cowslip",
  "name": "Cowslip",
  "kind": "herb",
  "tier": "common",
  "description": "The flowers brew into a draught against paralysis that restores strength: a +2 alchemical bonus on Fortitude saves against paralysis and +1 to Strength, for an hour. The same tea eases headache and heals 1d3 non-lethal damage, and given to someone paralyzed it ends the paralysis.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude against paralysis for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+1 Strength for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "ingest"
   },
   {
    "line": "Ends paralyzed",
    "route": "ingest"
   }
  ],
  "part": "flower",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "damiana",
  "name": "Damiana",
  "kind": "herb",
  "tier": "common",
  "description": "Leaves and stalks dried for incense. Anyone breathing the vapours feels bolder and warmer: a +1 alchemical bonus to Charisma for an hour, with feelings closer to the surface, -1 on Will saves against emotion effects. Drunk as a tea it gives +2 on Diplomacy checks for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+1 Charisma within the incense vapours for 1 hour",
    "route": "inhale"
   },
   {
    "line": "+2 Diplomacy for 1 hour",
    "route": "ingest"
   },
   {
    "line": "-1 Will against emotion effects for 1 hour",
    "route": "inhale"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "darkroot",
  "name": "Darkroot",
  "kind": "herb",
  "tier": "uncommon",
  "description": "The root boils down into titan gum, a glue that holds two objects until a DC 20 Strength check parts them; thrown, it entangles for 3 rounds (alchemy's use). Spread thin over a gash, the gum seals it and heals 1d6 hit points; painted over the skin it sets into a crust, DR 1/- for 10 minutes.",
  "harvesting": "",
  "effects": [
   {
    "line": "Causes entangled for 3 rounds",
    "route": "external"
   },
   {
    "line": "Heals 1d6 hit points",
    "route": "wound"
   },
   {
    "line": "DR 1/— for 10 minutes",
    "route": "skin"
   }
  ],
  "part": "root",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "dawnpetal",
  "name": "Dawnpetal",
  "kind": "herb",
  "tier": "common",
  "description": "Bright yellow sunburst flowers of high meadows. Chewing them is a burst of energy that ends fatigue at once, then a +2 alchemical bonus to Strength and on Fortitude saves against fatigue, for an hour. The restless mind takes a -1 penalty on Will saves for the hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Strength for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+2 Fortitude against fatigue for 1 hour",
    "route": "ingest"
   },
   {
    "line": "-1 Will for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Ends fatigued",
    "route": "ingest"
   }
  ],
  "part": "flower",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "dire-boar-tusk",
  "name": "Dire Boar Tusk",
  "kind": "monster part",
  "tier": "uncommon",
  "description": "Carved to powder and snorted, the tusk gives a +2 alchemical bonus to Strength and 1d6 temporary hit points for an hour, and the boar's temper with them: a -2 penalty to Wisdom for the hour.",
  "harvesting": "Tusks are sawed off with a steel saw after the boar is slain, requiring significant strength to cut through the dense bone.",
  "effects": [
   {
    "line": "+2 Strength for 1 hour",
    "route": "inhale"
   },
   {
    "line": "-2 Wisdom for 1 hour",
    "route": "inhale"
   },
   {
    "line": "1d6 temporary hit points for 1 hour",
    "route": "inhale"
   }
  ],
  "part": "bone",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "dittany",
  "name": "Dittany",
  "kind": "herb",
  "tier": "common",
  "description": "Heated in ale or wine, dittany clears the head: it heals 1d3 hit points and gives a +1 alchemical bonus on Fortitude saves against lingering poison for an hour. Pressed into a wound, the leaves draw out splinters and arrowheads and heal 1d4.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d3 hit points",
    "route": "ingest"
   },
   {
    "line": "+1 Fortitude against lingering poison for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Heals 1d4 hit points",
    "route": "wound"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "djinn-blossoms",
  "name": "Djinn Blossoms",
  "kind": "herb",
  "tier": "uncommon",
  "description": "Fern-like blossoms of the Elemental Plane of Air that stir a little breeze all round them. Worn, a plucked blossom guards against gases and clouds for a day (alchemy's use). Made into a perfume and worn on the skin, it gives a +2 alchemical bonus on Diplomacy checks for 8 hours, and its breath, drawn in, makes the body light, +2 on Acrobatics checks for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude against inhaled poisons, gases and clouds for 24 hours",
    "route": "external"
   },
   {
    "line": "+2 Diplomacy for 8 hours",
    "route": "skin"
   },
   {
    "line": "+2 Acrobatics light on the feet for 1 hour",
    "route": "inhale"
   }
  ],
  "part": "flower",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "dracolisk-scale",
  "name": "Dracolisk Scale",
  "kind": "monster part",
  "tier": "rare",
  "description": "Ground fine and sprinkled over armour, the scales guard against petrification for 8 hours, though the armour grows sluggish (-2 Dexterity; alchemy's use). Stirred into honey and swallowed, a pinch gives a +3 alchemical bonus on Fortitude saves against petrification for an hour.",
  "harvesting": "Scales must be carefully pried from the dracolisk’s hide using a non-metallic tool after it sheds naturally or is slain, as metal causes them to crumble.",
  "effects": [
   {
    "line": "+3 Fortitude against petrification for 8 hours",
    "route": "external"
   },
   {
    "line": "-2 Dexterity for 8 hours",
    "route": "external"
   },
   {
    "line": "+3 Fortitude against petrification for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "scale",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "dragon-flower",
  "name": "Dragon Flower",
  "kind": "herb",
  "tier": "common",
  "description": "A flower with a stench that fouls the air for sixty feet: anyone in it fights badly, -2 on attack rolls until 1d6 rounds after leaving (alchemy's use). Its sap, swallowed raw, gives a +2 alchemical bonus on Fortitude saves against poison for 10 rounds, and a preserved pod is a purgative, +1 on Fortitude saves against disease for an hour. The resin at its heart is poison: a DC 25 Fortitude save or 1d6 Constitution damage and nausea for 1d6 rounds.",
  "harvesting": "",
  "effects": [
   {
    "line": "-2 Attack rolls while in the stench for 1d6 rounds",
    "route": "external"
   },
   {
    "line": "+2 Fortitude against poison for 10 rounds",
    "route": "ingest"
   },
   {
    "line": "1d6 Constitution damage",
    "route": "ingest"
   },
   {
    "line": "Fortitude DC 25",
    "route": "ingest"
   },
   {
    "line": "Causes nauseated for 1d6 rounds",
    "route": "inhale"
   },
   {
    "line": "+1 Fortitude against disease for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "flower",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "dragon-s-blood",
  "name": "Dragon's Blood",
  "kind": "herb",
  "tier": "common",
  "description": "The red resin of a palm. A pinch steadies a brew, a +2 alchemical bonus on Craft checks for herbal preparations for an hour. Packed into a wound it closes 1d3 hit points, and in a salve it gives +1 on Fortitude saves against skin infection for an hour. Ground, it thickens a salve.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Craft brewing herbal preparations for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Heals 1d3 hit points",
    "route": "wound"
   },
   {
    "line": "+1 Fortitude against skin infection for 1 hour",
    "route": "skin"
   }
  ],
  "part": "resin",
  "hybrid": false,
  "base_for": [
   "salve"
  ]
 },
 {
  "id": "dreamcap",
  "name": "Dreamcap",
  "kind": "fungus",
  "tier": "common",
  "description": "A luminous purple mushroom of enchanted groves that hums faintly. Eaten, it brings vivid, prophetic visions: a +2 alchemical bonus on Sense Motive checks for 6 hours and +1 on Will saves against illusions for an hour. The mind is slow to come back, and the eater is dazed for a minute.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Sense Motive the dream's foresight for 6 hours",
    "route": "ingest"
   },
   {
    "line": "Causes dazed for 1 minute",
    "route": "ingest"
   },
   {
    "line": "+1 Will against illusions for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "fungus",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "dreamer-s-star",
  "name": "Dreamer’s Star",
  "kind": "herb",
  "tier": "common",
  "description": "Cured orange petals steeped in hot water make a mild, fragrant tea for deep sleep. A cup heals 1d4 non-lethal damage and gives a +1 alchemical bonus on Fortitude saves against fatigue for 8 hours, and leaves the drinker drowsy, -1 on Perception checks for an hour. One dose serves six.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d4 non-lethal damage",
    "route": "ingest"
   },
   {
    "line": "+1 Fortitude against fatigue for 8 hours",
    "route": "ingest"
   },
   {
    "line": "-1 Perception for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "flower",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "dryad-s-tears",
  "name": "Dryad's Tears",
  "kind": "herb",
  "tier": "common",
  "description": "Commoners make jam and wine of the berries, and a spoonful is 1d4 temporary hit points for an hour. The odour repels lycanthropes as blackthorn repels outsiders, +2 AC against them for an hour (alchemy's use), and the berries, eaten, give a +2 alchemical bonus on Fortitude saves against lycanthropy for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Armour class against lycanthropes for 1 hour",
    "route": "external"
   },
   {
    "line": "+2 Fortitude vs contracting lycanthropy for 1 hour",
    "route": "ingest"
   },
   {
    "line": "1d4 temporary hit points for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "berry",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "dwarven-oak",
  "name": "Dwarven Oak",
  "kind": "herb",
  "tier": "rare",
  "description": "The bark makes oakdeath, a liquid that makes a poison harder to throw off, -2 on the victim's Fortitude saves against it if added in the hour before it is used (alchemy's use). Ground and packed into a wound, the astringent bark heals 2d4 hit points and gives a +2 alchemical bonus on Heal checks treating it for an hour; it is also a salve base.",
  "harvesting": "",
  "effects": [
   {
    "line": "-2 Fortitude against a poison laced with oakdeath for 1 hour",
    "route": "external"
   },
   {
    "line": "Heals 2d4 hit points",
    "route": "wound"
   },
   {
    "line": "+2 Heal treating wounds for 1 hour",
    "route": "wound"
   }
  ],
  "part": "bark",
  "hybrid": false,
  "base_for": [
   "salve"
  ]
 },
 {
  "id": "elven-willow",
  "name": "Elven Willow",
  "kind": "herb",
  "tier": "common",
  "description": "The sap is the heart of elf hazel, a cool astringent wash. Rubbed on hurt skin it heals 1d4 hit points and gives a +1 alchemical bonus on Fortitude saves against skin infection for an hour; over a week it fades old scars. A willow tea heals 1d3 non-lethal damage. The sap thickens a salve.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d4 hit points",
    "route": "skin"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "ingest"
   },
   {
    "line": "+1 Fortitude against skin infection for 1 hour",
    "route": "skin"
   }
  ],
  "part": "sap",
  "hybrid": false,
  "base_for": [
   "salve"
  ]
 },
 {
  "id": "elysium",
  "name": "Elysium",
  "kind": "herb",
  "tier": "common",
  "description": "A strongly anti-magic grass: the ground it grows on holds magic off, as an antimagic field, until it is pulled up, and a fresh sprig carried gives +2 on Will saves against spells (alchemy's use). Eaten, it fills like a meal, 1d4 temporary hit points for an hour. Drained to a gel it sets a cream, and rubbed on the body the gel gives a +2 alchemical bonus on Stealth in tall grass for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "Hold it off while this lasts: magic on the ground where it grows",
    "route": "external"
   },
   {
    "line": "+2 Will vs spells while the fresh plant is carried for 1 hour",
    "route": "external"
   },
   {
    "line": "1d4 temporary hit points for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+2 Stealth in tall grass for 1 hour",
    "route": "skin"
   }
  ],
  "part": "leaf",
  "hybrid": true,
  "base_for": [
   "cream"
  ]
 },
 {
  "id": "euphorbia",
  "name": "Euphorbia",
  "kind": "herb",
  "tier": "common",
  "description": "The milky juice is a violent purgative. Drunk, it throws up whatever else was swallowed: a +2 alchemical bonus on Fortitude saves against ingested poison for an hour, and a DC 12 save or nausea for 3 rounds. Rubbed on skin the leaves raise weeping blisters, an old beggar's trick: +2 on Disguise checks to look pitiable for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude against swallowed poison for 1 hour",
    "route": "ingest"
   },
   {
    "line": "DC 12",
    "route": "ingest"
   },
   {
    "line": "Causes nauseated for 3 rounds",
    "route": "ingest"
   },
   {
    "line": "+2 Disguise as a pitiable beggar for 1 hour",
    "route": "skin"
   }
  ],
  "part": "sap",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "faerie-grass",
  "name": "Faerie Grass",
  "kind": "herb",
  "tier": "common",
  "description": "Step on a patch and the fey in it turn you round: a DC 20 Will save or confusion for 3 rounds (alchemy's use, thrown). Steeped as a careful tea, the grass grounds the mind instead, a +2 alchemical bonus on Will saves against confusion and enchantment for an hour, with a dreamy -1 on Perception checks for as long.",
  "harvesting": "",
  "effects": [
   {
    "line": "Will DC 20 · fail: Causes confused for 3 rounds",
    "route": "external"
   },
   {
    "line": "+2 Will against confusion and enchantment for 1 hour",
    "route": "ingest"
   },
   {
    "line": "-1 Perception for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "fainne-mushroom",
  "name": "Fainne Mushroom",
  "kind": "fungus",
  "tier": "common",
  "description": "The stem of this mushroom is a stimulant. Eaten, it gives a +1 alchemical bonus to Charisma and +2 on Diplomacy checks when seduction is the aim, for an hour, and lowers the eater's own guard: -1 on Will saves against charm for as long.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Diplomacy when seduction is the aim for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+1 Charisma for 1 hour",
    "route": "ingest"
   },
   {
    "line": "-1 Will against charm for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "fungus",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "fey-cherry",
  "name": "Fey Cherry",
  "kind": "herb",
  "tier": "rare",
  "description": "Within the canopy of these fey trees the weather softens. Once a decade they fruit, and a cherry eaten within a day of picking wards the eater as protection from evil for 5 minutes: a +2 deflection bonus to AC and a +2 resistance bonus on Fortitude and Will saves against evil creatures.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Armour class against evil creatures for 5 minutes",
    "route": "ingest"
   },
   {
    "line": "+2 Will against evil creatures for 5 minutes",
    "route": "ingest"
   },
   {
    "line": "+2 Fortitude against evil creatures for 5 minutes",
    "route": "ingest"
   }
  ],
  "part": "berry",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "firesnap",
  "name": "Firesnap",
  "kind": "herb",
  "tier": "common",
  "description": "Known only for its stink. Snap a dried section under someone's nose and the fumes shock them alert: 1d4 temporary hit points and a +2 alchemical bonus on Fortitude saves against being stunned or dazed, for a minute, long enough to get them out of danger. The reek leaves them sickened for a round.",
  "harvesting": "",
  "effects": [
   {
    "line": "1d4 temporary hit points for 1 minute",
    "route": "inhale"
   },
   {
    "line": "+2 Fortitude against being stunned or dazed for 1 minute",
    "route": "inhale"
   },
   {
    "line": "Causes sickened for 1 round",
    "route": "inhale"
   }
  ],
  "part": "root",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "flame-clove",
  "name": "Flame Clove",
  "kind": "herb",
  "tier": "uncommon",
  "description": "A garlic-like herb full of elemental fire. Boiled in salt water and crushed into food, it keeps the eater warm from inside, resist cold 5 for an hour, and like garlic it wards off sickness, a +2 alchemical bonus on Fortitude saves against disease for an hour. It scalds the mouth going down: 1 fire damage. A sprig worked into alchemist's fire adds 1d6 fire to its burn (alchemy's use).",
  "harvesting": "",
  "effects": [
   {
    "line": "1d6 fire damage",
    "route": "external"
   },
   {
    "line": "Resist cold 5 for 1 hour",
    "route": "ingest"
   },
   {
    "line": "1 fire damage",
    "route": "ingest"
   },
   {
    "line": "+2 Fortitude against disease for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "root",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "flayleaf",
  "name": "Flayleaf",
  "kind": "herb",
  "tier": "common",
  "description": "Narrow rust-coloured leaves smoked as a sedative. The smoker stops feeling pain, 1d4 temporary hit points for an hour, and drifts: a -2 penalty on Perception checks and on Will saves against mind-affecting effects for the hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "1d4 temporary hit points for 1 hour",
    "route": "inhale"
   },
   {
    "line": "-2 Perception for 1 hour",
    "route": "inhale"
   },
   {
    "line": "-2 Will against mind-affecting effects for 1 hour",
    "route": "inhale"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "fleshshiver",
  "name": "Fleshshiver",
  "kind": "herb",
  "tier": "uncommon",
  "description": "A tropical mushroom for fevers, mixed with cool mud and pressed to the head. The compress heals 1d4 non-lethal damage and gives a +2 alchemical bonus on Fortitude saves against non-magical disease for a day. Its chill makes the flesh shiver: -1 on initiative for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude to resist non-magical diseases for 24 hours",
    "route": "skin"
   },
   {
    "line": "Heals 1d4 non-lethal damage",
    "route": "skin"
   },
   {
    "line": "-1 Initiative for 1 hour",
    "route": "skin"
   }
  ],
  "part": "fungus",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "fool-s-weed",
  "name": "Fool's Weed",
  "kind": "herb",
  "tier": "common",
  "description": "Eaten like lettuce or brewed for sleep. Five fresh leaves, chewed, calm a frightened heart: a +2 alchemical bonus on Will saves against fear for an hour. The calm heals 1d3 non-lethal damage and dulls the senses, -1 on Perception checks for the hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Will against fear for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "ingest"
   },
   {
    "line": "-1 Perception for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "frostbloom",
  "name": "Frostbloom",
  "kind": "herb",
  "tier": "common",
  "description": "Tiny ice-blue flowers of the snowy tundra that sparkle like frost. Ground into a paste and rubbed on the skin, they give resist fire 10 for 4 hours and cool a burn, healing 1d3 non-lethal damage. The body chills: a -3 penalty to Dexterity for as long.",
  "harvesting": "",
  "effects": [
   {
    "line": "-3 Dexterity for 4 hours",
    "route": "skin"
   },
   {
    "line": "Resist fire 10 for 4 hours",
    "route": "skin"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "skin"
   }
  ],
  "part": "flower",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "frostgiant-marrow",
  "name": "Frostgiant Marrow",
  "kind": "monster part",
  "tier": "exotic",
  "description": "Cracked from a frost giant's femur and boiled into a broth. Drunk, it gives resist cold 10 for 12 hours and a giant's strength for one, a +3 alchemical bonus to Strength. The cold settles in the limbs: a -2 penalty on initiative for 12 hours.",
  "harvesting": "The marrow is extracted by cracking the giant’s femur with a heavy hammer and scooping it out with a bone or wooden tool, as metal freezes to it.",
  "effects": [
   {
    "line": "-2 Initiative for 12 hours",
    "route": "ingest"
   },
   {
    "line": "Resist cold 10 for 12 hours",
    "route": "ingest"
   },
   {
    "line": "+3 Strength for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "bone",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "garlic",
  "name": "Garlic",
  "kind": "herb",
  "tier": "common",
  "description": "A strong antiseptic. Crushed on a wound it keeps infection out and heals 2 hit points; eaten, it gives a +2 alchemical bonus on Fortitude saves against disease for an hour, and a breath that costs -1 on Diplomacy checks for as long. Insects (and vampires) dislike it.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 2 hit points",
    "route": "wound"
   },
   {
    "line": "+2 Fortitude against disease for 1 hour",
    "route": "ingest"
   },
   {
    "line": "-1 Diplomacy for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "root",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "gloomwraith-tendril",
  "name": "Gloomwraith Tendril",
  "kind": "monster part",
  "tier": "exotic",
  "description": "Severed with silver during a gloomwraith's brief solid moment and boiled into a syrup. Drunk, it opens the eyes to what hides: a +4 alchemical bonus on Perception checks against invisible or hidden creatures and +3 on Will saves against illusions, for 4 hours. A lingering dread comes with it, a -2 penalty on Will saves against fear.",
  "harvesting": "Tendrils must be severed with a silver blade during the gloomwraith’s brief materialization, requiring precise timing to avoid its chilling touch.",
  "effects": [
   {
    "line": "-2 Will against fear for 4 hours",
    "route": "ingest"
   },
   {
    "line": "+4 Perception against invisible or hidden creatures for 4 hours",
    "route": "ingest"
   },
   {
    "line": "+3 Will against illusions for 4 hours",
    "route": "ingest"
   }
  ],
  "part": "organ",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "glowvine",
  "name": "Glowvine",
  "kind": "herb",
  "tier": "uncommon",
  "description": "Mage-bred blossoms that shed torchlight through the night (alchemy's use). A wash of the petals over the eyes holds a little of that light, a +2 alchemical bonus on Perception checks in darkness for an hour, and a tea of them gives +2 on Will saves against fear for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "Torchlight shed by the blossoms through the night for 8 hours",
    "route": "external"
   },
   {
    "line": "+2 Perception in darkness for 1 hour",
    "route": "eyes"
   },
   {
    "line": "+2 Will against fear for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "flower",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "goblin-rouge",
  "name": "Goblin Rouge",
  "kind": "herb",
  "tier": "common",
  "description": "The berry juice makes a waterproof ink nothing can smear (DC 10 to make), +2 on Linguistics checks for a forger or scribe working in it (alchemy's use). Worked into a paste it is the rouge goblins are named for: painted on the face, a +2 alchemical bonus on Disguise checks, and +1 on Fortitude saves against sun and weather, for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Linguistics writing in waterproof ink for 1 hour",
    "route": "external"
   },
   {
    "line": "+2 Disguise as face paint for 1 hour",
    "route": "skin"
   },
   {
    "line": "+1 Fortitude against sun and weather for 1 hour",
    "route": "skin"
   }
  ],
  "part": "berry",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "goblinvine",
  "name": "Goblinvine",
  "kind": "herb",
  "tier": "common",
  "description": "The leaves of this creeper ooze an oil that raises red, itching splotches. Rubbed on deliberately, the sting keeps a sentry sharp, a +2 alchemical bonus on Perception checks for an hour, and nothing that bites wants the taste, +1 on Fortitude saves against vermin bites. The wearer is sickened for the first minute.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Perception while the itch lasts for 1 hour",
    "route": "skin"
   },
   {
    "line": "Causes sickened for 1 minute",
    "route": "skin"
   },
   {
    "line": "+1 Fortitude against vermin bites for 1 hour",
    "route": "skin"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "golden-embrace",
  "name": "Golden Embrace",
  "kind": "poison",
  "tier": "rare",
  "description": "A contact poison from the stem: on the skin, a DC 22 Fortitude save or 1 Constitution damage. In the smallest dose, on the tongue, it numbs all pain instead, 2d4 temporary hit points for an hour, and the judgement with it: a -2 penalty to Wisdom for the hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "2d4 temporary hit points for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Fortitude DC 22",
    "route": "skin"
   },
   {
    "line": "1 Constitution damage",
    "route": "skin"
   },
   {
    "line": "-2 Wisdom for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "golden-maple-leaves",
  "name": "Golden Maple Leaves",
  "kind": "herb",
  "tier": "uncommon",
  "description": "Leaves of a slow urban maple that half-elves grow and sell only to their own. Dried and ground (DC 15), the golden powder makes alchemical grease and tanglefoot bags easier to craft and harder to resist, -1 on saves against them (alchemy's use). Steeped and drunk, it sharpens the maker's hand and eye: a +2 alchemical bonus on Craft checks for alchemical work and on Appraise checks of alchemical goods, for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "-1 Reflex against an alchemical item made with it for 1 hour",
    "route": "external"
   },
   {
    "line": "+2 Craft for alchemical work for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+2 Appraise of alchemical goods for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "goldencup",
  "name": "Goldencup",
  "kind": "herb",
  "tier": "rare",
  "description": "Oily yellow moss chewed for a minute before battle. The euphoria strengthens resolve: a +3 alchemical bonus on Will saves against fear and compulsion and 2d4 temporary hit points, for 30 minutes. It can tip over: a DC 10 Will save or confusion for 3 rounds.",
  "harvesting": "",
  "effects": [
   {
    "line": "+3 Will against fear and compulsion for 30 minutes",
    "route": "ingest"
   },
   {
    "line": "Will DC 10",
    "route": "ingest"
   },
   {
    "line": "Causes confused for 3 rounds",
    "route": "ingest"
   },
   {
    "line": "2d4 temporary hit points for 30 minutes",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "goldenrod",
  "name": "Goldenrod",
  "kind": "herb",
  "tier": "common",
  "description": "Leaves mashed into a poultice and bound on a wound heal 1d4 hit points and give a +2 alchemical bonus on Fortitude saves against poison for an hour. A tea of the flowers gives +1 on Fortitude saves against disease for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d4 hit points",
    "route": "wound"
   },
   {
    "line": "+2 Fortitude vs poison for 1 hour",
    "route": "wound"
   },
   {
    "line": "+1 Fortitude against disease for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "grave-mold",
  "name": "Grave Mold",
  "kind": "fungus",
  "tier": "uncommon",
  "description": "Small doses fight disease and infection. An ounce of the mold, prepared and eaten, gives a +2 alchemical bonus on Fortitude saves against disease for a day, and turns the stomach: sickened for a minute. Dusted into a wound, it gives +2 on Fortitude saves against infection for an hour. Growing on a corpse it is psionic and can raise a simulacrum, no herbalist's business.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude against all disease for 24 hours",
    "route": "ingest"
   },
   {
    "line": "+2 Fortitude against infection in the wound for 1 hour",
    "route": "wound"
   },
   {
    "line": "Causes sickened for 1 minute",
    "route": "ingest"
   }
  ],
  "part": "fungus",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "griffon-talon",
  "name": "Griffon Talon",
  "kind": "monster part",
  "tier": "rare",
  "description": "Ground and mixed with oil into a salve for the hands: a +2 alchemical bonus on melee attack and damage rolls for 2 hours. The grip stiffens, a -2 penalty on Sleight of Hand checks for as long.",
  "harvesting": "Talons must be severed with a heavy chisel and hammer after the griffon is subdued, requiring strength to avoid damaging the talon’s core.",
  "effects": [
   {
    "line": "+2 Attack rolls with melee weapons for 2 hours",
    "route": "skin"
   },
   {
    "line": "-2 Sleight Of Hand for 2 hours",
    "route": "skin"
   },
   {
    "line": "+2 Damage rolls with melee weapons for 2 hours",
    "route": "skin"
   }
  ],
  "part": "horn",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "halfling-thistle",
  "name": "Halfling Thistle",
  "kind": "herb",
  "tier": "common",
  "description": "Makes shinewater, a rust remover and polish (DC 5); a dose cleans a medium weapon, +2 on Craft checks to keep metal arms in order (alchemy's use). A tea of the thistle settles the liver: it heals 1d3 non-lethal damage and gives a +2 alchemical bonus on Fortitude saves against poison for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Craft keeping metal arms clean for 1 hour",
    "route": "external"
   },
   {
    "line": "+2 Fortitude against poison for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "harpy-vocal-cord",
  "name": "Harpy Vocal Cord",
  "kind": "monster part",
  "tier": "uncommon",
  "description": "Boiled into a tea, the cord lends the harpy's lure: once within 4 hours a charm person (Will DC 15; alchemy's use). The drinker's own voice sings sweet, a +2 alchemical bonus on Perform checks, and their ear grows wary, +2 on Will saves against charms sung or spoken, for 4 hours. It cracks when it speaks: a -2 penalty on Diplomacy for as long.",
  "harvesting": "The cord is delicately cut with a sharp blade after the harpy’s death, requiring precision to avoid damaging its magical properties.",
  "effects": [
   {
    "line": "Will DC 15 · fail: Attitude towards the caster: friendly",
    "route": "external"
   },
   {
    "line": "+2 Perform for 4 hours",
    "route": "ingest"
   },
   {
    "line": "-2 Diplomacy for 4 hours",
    "route": "ingest"
   },
   {
    "line": "+2 Will against charms sung or spoken for 4 hours",
    "route": "ingest"
   }
  ],
  "part": "organ",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "hawthorn",
  "name": "Hawthorn",
  "kind": "herb",
  "tier": "common",
  "description": "Pollen from the blossoms, sprinkled in the eyes, lets anyone see faeries through their glamour: a +2 alchemical bonus on Perception checks to notice fey for an hour. A tea of the berries steadies the heart, 1d4 temporary hit points and +1 on Fortitude saves against fatigue for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Perception to notice fey for 1 hour",
    "route": "eyes"
   },
   {
    "line": "1d4 temporary hit points for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+1 Fortitude against fatigue for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "flower",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "heart-fire",
  "name": "Heart Fire",
  "kind": "poison",
  "tier": "rare",
  "description": "Distilled from the seeds, a contact poison: a DC 20 Fortitude save or 2d6 Constitution damage. A single drop on the tongue sets the heart racing instead, a +3 alchemical bonus on initiative for 10 minutes, and the head with it: a -2 penalty to Wisdom for as long.",
  "harvesting": "",
  "effects": [
   {
    "line": "+3 Initiative for 10 minutes",
    "route": "ingest"
   },
   {
    "line": "Fortitude DC 20",
    "route": "skin"
   },
   {
    "line": "2d6 Constitution damage",
    "route": "skin"
   },
   {
    "line": "-2 Wisdom for 10 minutes",
    "route": "ingest"
   }
  ],
  "part": "seed",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "hemlock",
  "name": "Hemlock",
  "kind": "herb",
  "tier": "common",
  "description": "The seeds make a soporific. Laid on the skin against inflammation, a hemlock poultice relaxes the muscle and heals 1d4 non-lethal damage, and gives a +1 alchemical bonus on Heal checks treating skin diseases for an hour. Eaten raw it is poison: a DC 15 Fortitude save or paralysis for 4 minutes.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d4 non-lethal damage",
    "route": "skin"
   },
   {
    "line": "Fortitude DC 15",
    "route": "ingest"
   },
   {
    "line": "Causes paralyzed for 4 minutes",
    "route": "ingest"
   },
   {
    "line": "+1 Heal treating skin diseases for 1 hour",
    "route": "wound"
   }
  ],
  "part": "seed",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "henbane",
  "name": "Henbane",
  "kind": "herb",
  "tier": "common",
  "description": "A potent painkiller. Boiled and laid on a wound as a poultice, it heals 1d2 hit points and numbs 1d4 more, temporary hit points that fade after 2 hours when the pain returns. Eaten or drunk it is poison: a DC 13 Fortitude save or nausea for 3 rounds.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d2 hit points",
    "route": "wound"
   },
   {
    "line": "1d4 temporary hit points for 2 hours",
    "route": "wound"
   },
   {
    "line": "Fortitude DC 13",
    "route": "ingest"
   },
   {
    "line": "Causes nauseated for 3 rounds",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "henna",
  "name": "Henna",
  "kind": "herb",
  "tier": "common",
  "description": "A pigment for tattoos, magically reactive and wanted for verdexes: a hand stained with it gives a +2 alchemical bonus on Craft checks for concoctions that call for it, for an hour. Spread as a cool paste on the skin, it gives +2 on Fortitude saves against heat and +1 against skin fungus for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Craft preparing magical concoctions that call for it for 1 hour",
    "route": "skin"
   },
   {
    "line": "+2 Fortitude against heat for 1 hour",
    "route": "skin"
   },
   {
    "line": "+1 Fortitude against skin fungus for 1 hour",
    "route": "skin"
   }
  ],
  "part": "leaf",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "herb-true-love",
  "name": "Herb True-Love",
  "kind": "herb",
  "tier": "common",
  "description": "An antidote and antiseptic. Three berries, or a tea of the leaves, taken within two rounds of a poisoning give a +2 alchemical bonus on Fortitude saves against poison for an hour. As a wound wash it heals 1 hit point and gives +1 on Fortitude saves against infection for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude against poison for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Heals 1 hit points",
    "route": "wound"
   },
   {
    "line": "+1 Fortitude against infection for 1 hour",
    "route": "wound"
   }
  ],
  "part": "berry",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "horsetail",
  "name": "Horsetail",
  "kind": "herb",
  "tier": "common",
  "description": "Powdered and sprinkled on an object, the leaves ritually purify it (alchemy's use). Packed into a cut, the same powder closes it, healing 1d3 hit points, and a tea of the stems gives a +1 alchemical bonus on Fortitude saves against wasting sickness for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+1 Will vs curses and evil magic, once the object is ritually purified for 1 hour",
    "route": "external"
   },
   {
    "line": "Heals 1d3 hit points",
    "route": "wound"
   },
   {
    "line": "+1 Fortitude against wasting sickness for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "hrondis-tears",
  "name": "Hrondis' Tears",
  "kind": "herb",
  "tier": "common",
  "description": "Small blue bells of sunny fields, known to few. A strand wrapped round a weapon's hilt lets it strike incorporeal undead, +1 damage against them, for a week, and observing its rite gives +1 on Will saves (alchemy's use). Brewed and drunk, the flowers give a +2 alchemical bonus on Fortitude saves against the chill of undead for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+1 Damage rolls against incorporeal undead for 7 days",
    "route": "external"
   },
   {
    "line": "+1 Will while its rite is observed for 1 hour",
    "route": "external"
   },
   {
    "line": "+2 Fortitude against the chill of undead for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "flower",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "hydra-gall",
  "name": "Hydra Gall",
  "kind": "monster part",
  "tier": "exotic",
  "description": "Excised whole with a silver scalpel and distilled. Drunk, the gall makes flesh regrow: it heals 4d4 hit points. The body revolts, nauseated for a round and a -3 penalty to Constitution for an hour.",
  "harvesting": "The gall bladder must be carefully excised with a silver scalpel after slaying the hydra, avoiding rupture to prevent acidic burns.",
  "effects": [
   {
    "line": "-3 Constitution for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Heals 4d4 hit points",
    "route": "ingest"
   },
   {
    "line": "Causes nauseated for 1 round",
    "route": "ingest"
   }
  ],
  "part": "organ",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "hypericum",
  "name": "Hypericum",
  "kind": "herb",
  "tier": "common",
  "description": "Leaves and flowers, crushed and powdered, are sprinkled on a place or a person in exorcisms and summonings (alchemy's use). Steeped and drunk, they give a +2 alchemical bonus on Will saves against possession for an hour; steeped in oil and laid on a wound, they heal 1d3 hit points.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Will vs possession and the influence of summoned spirits for 1 hour",
    "route": "external"
   },
   {
    "line": "+2 Will against possession for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Heals 1d3 hit points",
    "route": "wound"
   }
  ],
  "part": "leaf",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "ice-lotus",
  "name": "Ice Lotus",
  "kind": "herb",
  "tier": "exotic",
  "description": "The key to icewalker oil, which lets the wearer climb ice and snow like a spider, +4 on Climb checks there for 10 minutes (alchemy's use). Steeped and drunk, the petals carry the cold away, resist cold 10 for an hour; rubbed on the skin, they hold heat off instead, resist fire 10 for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+4 Climb on ice and snow for 10 minutes",
    "route": "external"
   },
   {
    "line": "Resist cold 10 for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Resist fire 10 for 1 hour",
    "route": "skin"
   }
  ],
  "part": "flower",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "imperial-willow",
  "name": "Imperial Willow",
  "kind": "herb",
  "tier": "common",
  "description": "The bark relieves pain: brewed into a bland tea it heals 4 non-lethal damage and gives a +2 alchemical bonus on Fortitude saves against infection for an hour. The heartwood strengthens nearby magic and song, +4 on Perform for a bard within reach of it (alchemy's use), and ground bark is a salve base.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 4 non-lethal damage",
    "route": "ingest"
   },
   {
    "line": "+2 Fortitude against infection for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+4 Perform a song near the heartwood for 1 hour",
    "route": "external"
   }
  ],
  "part": "bark",
  "hybrid": true,
  "base_for": [
   "salve"
  ]
 },
 {
  "id": "ironbark-moss",
  "name": "Ironbark Moss",
  "kind": "fungus",
  "tier": "common",
  "description": "Tough grey-green moss like cracked iron, clinging to ancient trees. Chewed, it hardens the skin: a +2 natural armour bonus to AC and resist bludgeoning 2 for an hour. The stiffness costs -1 on initiative for as long.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Armour class for 1 hour",
    "route": "ingest"
   },
   {
    "line": "-1 Initiative for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Resist bludgeoning 2 for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "fungus",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "juniper",
  "name": "Juniper",
  "kind": "herb",
  "tier": "common",
  "description": "Juniper berries are a quick, sometimes useful antidote: a +2 alchemical bonus on Fortitude saves against herbal poisons for an hour. Burned, the smoke cleans a sickroom, +1 on Fortitude saves against disease for an hour; the oil rubbed into stiff joints heals 1d3 non-lethal damage.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude against herbal poisons for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+1 Fortitude against disease for 1 hour",
    "route": "inhale"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "skin"
   }
  ],
  "part": "berry",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "juniper-berry",
  "name": "Juniper Berry",
  "kind": "herb",
  "tier": "common",
  "description": "A stimulant for the injured. Two berries help fight off shock: they heal 1d4 hit points and give a +1 alchemical bonus on Fortitude saves against poison for an hour. Someone brought round this way fights badly until rested, a -1 penalty on attack rolls for the hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d4 hit points",
    "route": "ingest"
   },
   {
    "line": "+1 Fortitude against poison for 1 hour",
    "route": "ingest"
   },
   {
    "line": "-1 Attack rolls for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "berry",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "kraken-ink",
  "name": "Kraken Ink",
  "kind": "monster part",
  "tier": "legendary",
  "description": "Concentrated and used to inscribe runes on the skin, the ink lets the bearer breathe water (immune to drowning) and gives a +6 alchemical bonus on Swim checks, for 8 hours. The skin takes on an inky hue, a -2 penalty to Charisma for as long.",
  "harvesting": "The sac must be carefully punctured and drained with a hollow needle after subduing the kraken, avoiding its acidic blood.",
  "effects": [
   {
    "line": "Immune to drowning for 8 hours",
    "route": "skin"
   },
   {
    "line": "+6 Swim for 8 hours",
    "route": "skin"
   },
   {
    "line": "-2 Charisma for 8 hours",
    "route": "skin"
   }
  ],
  "part": "gland",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "lakeleaf",
  "name": "Lakeleaf",
  "kind": "herb",
  "tier": "uncommon",
  "description": "A parsley-like herb from the banks of the River Oceanus that holds water like nothing else. Rubbed into meat it keeps it moist, and a sprig lengthens a gentle repose (alchemy's use). Chewed, it gives a +2 alchemical bonus on Fortitude saves against heat and thirst for an hour; laid on cracked, sun-burned skin, it heals 1d4 non-lethal damage.",
  "harvesting": "",
  "effects": [
   {
    "line": "Make it last longer: gentle repose",
    "route": "external"
   },
   {
    "line": "+2 Fortitude against heat and thirst for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Heals 1d4 non-lethal damage",
    "route": "skin"
   }
  ],
  "part": "leaf",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "leechwort",
  "name": "Leechwort",
  "kind": "herb",
  "tier": "common",
  "description": "Dried and ground, the mottled red and grey bark is a boon to healers. Applied to a wound, it gives a +1 alchemical bonus on Heal checks and +2 on Heal checks to staunch bleeding for an hour, and heals 1d2 hit points itself. One pound is ten uses, and the ground bark thickens a salve.",
  "harvesting": "",
  "effects": [
   {
    "line": "+1 Heal for 1 hour",
    "route": "wound"
   },
   {
    "line": "+2 Heal to staunch bleeding for 1 hour",
    "route": "wound"
   },
   {
    "line": "Heals 1d2 hit points",
    "route": "wound"
   }
  ],
  "part": "bark",
  "hybrid": false,
  "base_for": [
   "salve"
  ]
 },
 {
  "id": "levisticum",
  "name": "Levisticum",
  "kind": "herb",
  "tier": "common",
  "description": "Lovage leaves brewed into a love potion. The drinker warms to whoever served it, a +2 alchemical bonus on Diplomacy toward them for an hour, with their guard down, -1 on Will saves against charm. The brew also settles the stomach, +1 on Fortitude saves against stomach upsets for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Diplomacy toward the one who served the potion for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+1 Fortitude against stomach upsets for 1 hour",
    "route": "ingest"
   },
   {
    "line": "-1 Will against charm for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "lish-nut",
  "name": "Lish Nut",
  "kind": "herb",
  "tier": "common",
  "description": "Very nutritious: a handful is a day's food, 1d4 temporary hit points and a +1 alchemical bonus on Fortitude saves against hunger and fatigue for an hour. For two hours after eating one, the eater smells of it, and vermin that touch them must make a DC 11 Will save or be sickened for 2d4 rounds.",
  "harvesting": "",
  "effects": [
   {
    "line": "Will DC 11",
    "route": "external"
   },
   {
    "line": "Causes sickened for 2d4 rounds",
    "route": "external"
   },
   {
    "line": "1d4 temporary hit points for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+1 Fortitude against hunger and fatigue for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "seed",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "mad-cap",
  "name": "Mad Cap",
  "kind": "fungus",
  "tier": "common",
  "description": "Red mushrooms, less deadly than the death cap and wilder. A small piece brings on a fighting rage, a +2 morale bonus to Strength and 1d4 temporary hit points for a minute. It is a poison: a DC 18 save or collapse, exhausted and unconscious for 3 hours, and confused for 1d10 rounds.",
  "harvesting": "",
  "effects": [
   {
    "line": "DC 18",
    "route": "ingest"
   },
   {
    "line": "Causes exhausted for 3 hours",
    "route": "ingest"
   },
   {
    "line": "Causes unconscious for 3 hours",
    "route": "ingest"
   },
   {
    "line": "Causes confused for 1d10 rounds",
    "route": "ingest"
   },
   {
    "line": "+2 Strength for 1 minute",
    "route": "ingest"
   },
   {
    "line": "1d4 temporary hit points for 1 minute",
    "route": "ingest"
   }
  ],
  "part": "fungus",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "mallow",
  "name": "Mallow",
  "kind": "herb",
  "tier": "common",
  "description": "The shoots brew into an anti-love draught: a +2 alchemical bonus on Will saves against charm effects for an hour, and a coolness to everyone, -1 on Diplomacy checks for as long. Mashed, they soothe sore skin and heal 1d3 non-lethal damage, and their slippery sap thickens a cream base.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Will against charm effects for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "skin"
   },
   {
    "line": "-1 Diplomacy for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": [
   "cream"
  ]
 },
 {
  "id": "mandrake",
  "name": "Mandrake",
  "kind": "herb",
  "tier": "common",
  "description": "A pain-relieving root. A little chewed heals 1d4 non-lethal damage, and the leaves rubbed on the skin heal 1d3 more. It sedates as it soothes: a DC 17 Fortitude save or sleep for 1d4 hours, unless an apothecary has neutralised it.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d4 non-lethal damage",
    "route": "ingest"
   },
   {
    "line": "Fortitude DC 17",
    "route": "ingest"
   },
   {
    "line": "Causes unconscious for 1d4 hours",
    "route": "ingest"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "skin"
   }
  ],
  "part": "root",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "manticore-spine",
  "name": "Manticore Spine",
  "kind": "monster part",
  "tier": "rare",
  "description": "Boiled into a tincture for ammunition, the spines strike with paralyzing pain: a -4 penalty on attack rolls for a struck target for a minute (alchemy's use). Mishandled, a spine stings: a DC 12 Fortitude save or -2 Dexterity for an hour. Dilute, the same tincture laid on a wound numbs it, 2d4 temporary hit points for an hour.",
  "harvesting": "Spines must be carefully extracted with thick leather gloves and a steel forceps within minutes of the manticore’s death to avoid venom degradation.",
  "effects": [
   {
    "line": "-4 Attack rolls on struck targets for 1 minute",
    "route": "external"
   },
   {
    "line": "Fortitude DC 12 · fail: -2 Dexterity for 1 hour",
    "route": "skin"
   },
   {
    "line": "2d4 temporary hit points for 1 hour",
    "route": "wound"
   }
  ],
  "part": "bone",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "marsh-mallow",
  "name": "Marsh-Mallow",
  "kind": "herb",
  "tier": "common",
  "description": "A remedy for burns and blood loss. Mashed, boiled and bound to a wound, the root heals 2 hit points; spread on a burn, 1d3 non-lethal damage; the boiled remains, drunk, heal 1d3 hit points. Its mucilage thickens a cream base.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 2 hit points",
    "route": "wound"
   },
   {
    "line": "Heals 1d3 hit points",
    "route": "ingest"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "skin"
   }
  ],
  "part": "root",
  "hybrid": false,
  "base_for": [
   "cream"
  ]
 },
 {
  "id": "meadow-giant",
  "name": "Meadow Giant",
  "kind": "herb",
  "tier": "uncommon",
  "description": "The powdered stem makes white sanguine, smeared with an injury poison on a blade: a victim who fails the poison's save bleeds 1 hit point a round for a minute (alchemy's use). Rubbed on a bruise, the powder disperses it and heals 1d6 non-lethal damage. Swallowed, it thins the blood: -1 Constitution for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "Bleed 1 per round for 1 minute",
    "route": "external"
   },
   {
    "line": "Heals 1d6 non-lethal damage",
    "route": "skin"
   },
   {
    "line": "-1 Constitution for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "menhirite",
  "name": "Menhirite",
  "kind": "herb",
  "tier": "uncommon",
  "description": "A plant of the Elemental Plane of Earth that grows in rock-like rings over buried kings, held holy by commoners: standing in a ring gives +2 on Will saves (alchemy's use). An ounce of its sap, laid on a wound, closes it and heals 1d6 hit points; a drop on the tongue gives a +2 alchemical bonus on Fortitude saves against negative energy for an hour. The sap thickens a salve.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d6 hit points",
    "route": "wound"
   },
   {
    "line": "+2 Will on the holy ground of a menhirite ring for 1 hour",
    "route": "external"
   },
   {
    "line": "+2 Fortitude against negative energy for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "sap",
  "hybrid": true,
  "base_for": [
   "salve"
  ]
 },
 {
  "id": "mind-hammer",
  "name": "Mind Hammer",
  "kind": "poison",
  "tier": "rare",
  "description": "A contact poison from the leaves: on the skin, a DC 20 Fortitude save or 1d4 Intelligence drain. A single drop on the tongue drives every other influence out of the head, a +3 alchemical bonus on Will saves against confusion and charm for 10 minutes, and leaves the speaker blunt: -2 on Diplomacy checks for as long.",
  "harvesting": "",
  "effects": [
   {
    "line": "+3 Will against confusion and charm for 10 minutes",
    "route": "ingest"
   },
   {
    "line": "Fortitude DC 20",
    "route": "skin"
   },
   {
    "line": "1d4 Intelligence drain",
    "route": "skin"
   },
   {
    "line": "-2 Diplomacy for 10 minutes",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "mistletoe",
  "name": "Mistletoe",
  "kind": "herb",
  "tier": "common",
  "description": "The druids' plant. An extract of the berries gives a +2 alchemical bonus on Fortitude saves against any transformation, polymorph or wild growth, for an hour, and calms the blood to sluggishness, -1 on initiative. Unseparated, the berries cramp the gut: a DC 19 Fortitude save or 1d4 Constitution damage.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude against polymorph and transformation for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Fortitude DC 19",
    "route": "ingest"
   },
   {
    "line": "1d4 Constitution damage",
    "route": "ingest"
   },
   {
    "line": "-1 Initiative for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "berry",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "mistveil-fern",
  "name": "Mistveil Fern",
  "kind": "herb",
  "tier": "common",
  "description": "A pale, translucent fern of damp caves. A deep breath of its spores makes the user partly incorporeal for 10 minutes: +2 AC as blows pass part-way through, -3 on damage rolls as their own do too (alchemy's use). A shallow one only loosens the body: a +2 alchemical bonus on Escape Artist checks for 10 minutes.",
  "harvesting": "",
  "effects": [
   {
    "line": "-3 Damage rolls physical damage dealt while partly incorporeal for 10 minutes",
    "route": "external"
   },
   {
    "line": "+2 Armour class partially incorporeal; blows pass part-way through for 10 minutes",
    "route": "external"
   },
   {
    "line": "+2 Escape Artist for 10 minutes",
    "route": "inhale"
   }
  ],
  "part": "leaf",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "monkshood",
  "name": "Monkshood",
  "kind": "herb",
  "tier": "common",
  "description": "The juice is smeared on a weapon as a poison, 1d3 poison damage (alchemy's use). In a weak liniment rubbed on sore muscle it heals 1d3 non-lethal damage and numbs the fingers, -1 on Sleight of Hand checks for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "1d3 poison damage",
    "route": "external"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "skin"
   },
   {
    "line": "-1 Sleight Of Hand for 1 hour",
    "route": "skin"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "musk-muddle",
  "name": "Musk Muddle",
  "kind": "herb",
  "tier": "common",
  "description": "Boiled leaves make a burn salve (DC 10). Spread on a burn within two rounds it heals 1d4 hit points and gives resist fire 2 for 10 minutes. It reeks of musk: -2 on Stealth checks for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d4 hit points",
    "route": "skin"
   },
   {
    "line": "Resist fire 2 for 10 minutes",
    "route": "skin"
   },
   {
    "line": "-2 Stealth the musk carries for 1 hour",
    "route": "skin"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "myrtle",
  "name": "Myrtle",
  "kind": "herb",
  "tier": "common",
  "description": "Leaves brewed into a love potion. The drinker warms to whoever served it, a +2 alchemical bonus on Diplomacy toward them for an hour, with their guard down, -1 on Will saves against charm. Myrtle water splashed on the skin heals 1d3 non-lethal damage.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Diplomacy toward the one who served the potion for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "skin"
   },
   {
    "line": "-1 Will against charm for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "nahre-lotus",
  "name": "Nahre Lotus",
  "kind": "herb",
  "tier": "common",
  "description": "Lilies that reach into the Elemental Plane of Water and pour pure, sweet water from their blossoms, fifty gallons a day. A cup of that water heals 1d4 non-lethal damage and gives a +2 alchemical bonus on Fortitude saves against heat and thirst for an hour. A dead lotus kept in water is a blight, thrown like a grenade: a DC 12 Fortitude save or 2d6 Constitution damage (alchemy's use).",
  "harvesting": "",
  "effects": [
   {
    "line": "2d6 Constitution damage",
    "route": "external"
   },
   {
    "line": "Fortitude DC 12",
    "route": "external"
   },
   {
    "line": "Heals 1d4 non-lethal damage",
    "route": "ingest"
   },
   {
    "line": "+2 Fortitude against heat and thirst for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "flower",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "nightshade",
  "name": "Nightshade",
  "kind": "herb",
  "tier": "common",
  "description": "Witches' nightshade. In a careful extract it relaxes the nerves: a +2 alchemical bonus on Reflex saves for an hour, and a lethargy that costs -2 on initiative for 30 minutes. The plant is poison all the same: a DC 18 Fortitude save or 1d6 Constitution damage and paralysis for 4 minutes. Gnomes are immune and make jam of the berries.",
  "harvesting": "",
  "effects": [
   {
    "line": "-2 Initiative for 30 minutes",
    "route": "ingest"
   },
   {
    "line": "+2 Reflex for 1 hour",
    "route": "ingest"
   },
   {
    "line": "1d6 Constitution damage",
    "route": "ingest"
   },
   {
    "line": "Fortitude DC 18",
    "route": "ingest"
   },
   {
    "line": "Causes paralyzed for 4 minutes",
    "route": "ingest"
   }
  ],
  "part": "berry",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "nura-stalk",
  "name": "Nura Stalk",
  "kind": "herb",
  "tier": "common",
  "description": "A thick stalk of temperate forests that weeps white sap when broken. Laid on an open wound, the sap closes it, heals 1d4 hit points and gives a +1 alchemical bonus on Heal checks to staunch bleeding; spread on the skin, +1 on Fortitude saves against infection, each for an hour. It loses its strength within hours in the air; sealed in soft wax it keeps, and it thickens a salve.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d4 hit points",
    "route": "wound"
   },
   {
    "line": "+1 Heal to staunch bleeding for 1 hour",
    "route": "wound"
   },
   {
    "line": "+1 Fortitude against infection for 1 hour",
    "route": "skin"
   }
  ],
  "part": "sap",
  "hybrid": false,
  "base_for": [
   "salve"
  ]
 },
 {
  "id": "oak",
  "name": "Oak",
  "kind": "herb",
  "tier": "common",
  "description": "An astringent oil from the leaves seals a wound and heals 1d3 hit points. The bark, worked into a poultice against infection, gives a +2 alchemical bonus on Heal checks treating fresh wounds for an hour; a bark tea gives +1 on Fortitude saves against dysentery for an hour. Ground, the bark is a salve base.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d3 hit points",
    "route": "wound"
   },
   {
    "line": "+2 Heal treating fresh wounds for 1 hour",
    "route": "wound"
   },
   {
    "line": "+1 Fortitude against dysentery for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "bark",
  "hybrid": false,
  "base_for": [
   "salve"
  ]
 },
 {
  "id": "old-man-s-friend",
  "name": "Old Man's Friend",
  "kind": "herb",
  "tier": "uncommon",
  "description": "Crushed and worked into a thick paste called gash glue (DC 20), carried by soldiers to seal a fallen friend's wounds. One application heals 1d6 hit points, enough to bring most of the dying back, and gives a +2 alchemical bonus on Heal checks to stabilize the dying. The glued skin stiffens: -2 on Acrobatics checks for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d6 hit points",
    "route": "wound"
   },
   {
    "line": "+2 Heal to stabilize the dying for 1 hour",
    "route": "wound"
   },
   {
    "line": "-2 Acrobatics for 1 hour",
    "route": "wound"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "orevine",
  "name": "Orevine",
  "kind": "herb",
  "tier": "exotic",
  "description": "Bred from a plant of the Elemental Plane of Earth, orevine roots through stone after one metal and can be harvested for it monthly; its keepers gain +2 on Knowledge (dungeoneering) to find the ore (alchemy's use). A decoction of the metal-heavy root gives the skin a dull sheen, DR 3/- for an hour, and weighs the body down: -4 on Swim checks for as long.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Knowledge (Dungeoneering) finding metal near the vine for 1 hour",
    "route": "external"
   },
   {
    "line": "DR 3/— for 1 hour",
    "route": "ingest"
   },
   {
    "line": "-4 Swim for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "root",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "orticusp",
  "name": "Orticusp",
  "kind": "herb",
  "tier": "exotic",
  "description": "Pulped and mixed with a poison, orticusp makes night venom: a victim must also make a DC 15 Fortitude save or fall asleep for 3 hours (alchemy's use). In a cup by itself it is the deepest rest there is: it heals 2d6 non-lethal damage and gives a +3 alchemical bonus on Fortitude saves against fatigue and exhaustion for 8 hours.",
  "harvesting": "",
  "effects": [
   {
    "line": "Fortitude DC 15 · fail: Causes unconscious for 3 hours",
    "route": "external"
   },
   {
    "line": "Heals 2d6 non-lethal damage",
    "route": "ingest"
   },
   {
    "line": "+3 Fortitude against fatigue and exhaustion for 8 hours",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "pennyroyal",
  "name": "Pennyroyal",
  "kind": "herb",
  "tier": "common",
  "description": "A pungent mint. Brewed weak, the leaves settle the stomach: a +2 alchemical bonus on Fortitude saves against nausea and stomach poisons for an hour. Rubbed on the skin they keep vermin off, +1 on Fortitude saves against vermin and their bites for an hour. Brewed strong it is a poison, a DC 12 Fortitude save or 1 Constitution damage.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude against nausea and stomach poisons for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+1 Fortitude against vermin and their bites for 1 hour",
    "route": "skin"
   },
   {
    "line": "Fortitude DC 12",
    "route": "ingest"
   },
   {
    "line": "1 Constitution damage",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "phoenix-feather",
  "name": "Phoenix Feather",
  "kind": "monster part",
  "tier": "legendary",
  "description": "Gathered from a phoenix's nest during its rebirth and burned. Breathing the ash grants immunity to fire damage for 2 hours and burns the old hurt away, healing 4d8 hit points. The user runs a fever: a -3 penalty on caster level checks, concentration among them, for 2 hours.",
  "harvesting": "Feathers must be collected from the phoenix’s nest during its fiery rebirth, using heat-resistant tongs to avoid burns.",
  "effects": [
   {
    "line": "-3 Caster level checks for 2 hours",
    "route": "inhale"
   },
   {
    "line": "Immune to fire damage for 2 hours",
    "route": "inhale"
   },
   {
    "line": "Heals 4d8 hit points",
    "route": "inhale"
   }
  ],
  "part": "feather",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "pomegranate",
  "name": "Pomegranate",
  "kind": "herb",
  "tier": "common",
  "description": "The fruit's juice cools the body: drunk, a +2 alchemical bonus on Fortitude saves against extreme heat for an hour. Crushed leaves laid on a wound fight infection, a +2 alchemical bonus on Heal checks treating it. The bark is a purgative, and any brew with it in makes the drinker retch: nauseated for a round.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude to resist extreme heat for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+2 Heal treating wounds for 1 hour",
    "route": "wound"
   },
   {
    "line": "Causes nauseated for 1 round",
    "route": "ingest"
   }
  ],
  "part": "berry",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "poppy-tears",
  "name": "Poppy Tears",
  "kind": "herb",
  "tier": "common",
  "description": "The milk of a green cactus, congealed with resins into sticky black chunks with a sour taste. Eaten, it dulls pain: it heals 1d3 non-lethal damage and gives 1d4 temporary hit points for an hour, with a -2 penalty on Perception checks while the haze lasts.",
  "harvesting": "",
  "effects": [
   {
    "line": "1d4 temporary hit points for 1 hour",
    "route": "ingest"
   },
   {
    "line": "-2 Perception for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "ingest"
   }
  ],
  "part": "sap",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "prickly-tea",
  "name": "Prickly Tea",
  "kind": "herb",
  "tier": "rare",
  "description": "Distilled (DC 25) into a substance called Senses, which sharpens eyes and ears for an hour: a +3 alchemical bonus on Perception checks and +2 on initiative. Sleep comes hard after it, a -2 penalty on Fortitude saves against fatigue for the hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+3 Perception for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+2 Initiative for 1 hour",
    "route": "ingest"
   },
   {
    "line": "-2 Fortitude against fatigue for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "rowan",
  "name": "Rowan",
  "kind": "herb",
  "tier": "common",
  "description": "Rowan wood protects against magic: staves and shields of it save with +2 against magic aimed at them for a day of use, and worked rowan gives its wielder +2 on Will saves against spells (alchemy's and the woodworker's use). The berries, eaten, give a +1 alchemical bonus on Will saves against hostile spells for an hour, and the ground bark is a salve base.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude a rowan-wood item against magic for 1 day",
    "route": "external"
   },
   {
    "line": "+2 Will vs spells, wielding worked rowan for 1 hour",
    "route": "external"
   },
   {
    "line": "+1 Will against hostile spells for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "bark",
  "hybrid": true,
  "base_for": [
   "salve"
  ]
 },
 {
  "id": "rue",
  "name": "Rue",
  "kind": "herb",
  "tier": "common",
  "description": "Leaves brewed into a potion of second sight: a +2 alchemical bonus on Perception checks to notice spirits and magical auras for an hour. An eyewash of the leaves gives +1 on all Perception checks for an hour. Brewed too strong it turns the stomach: a DC 11 Fortitude save or nausea for 3 rounds.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Perception to notice spirits and magical auras for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+1 Perception for 1 hour",
    "route": "eyes"
   },
   {
    "line": "Fortitude DC 11",
    "route": "ingest"
   },
   {
    "line": "Causes nauseated for 3 rounds",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "salamander-ember-gland",
  "name": "Salamander Ember Gland",
  "kind": "monster part",
  "tier": "uncommon",
  "description": "Crushed and mixed with water, the gland lets the drinker breathe out one burst of flame within the hour, 1d6 fire in a 10-foot radius (alchemy's use). Its heat stays inside too: resist cold 5 and a +2 alchemical bonus on initiative for an hour, and 1d4 fire damage to the drinker as it goes down.",
  "harvesting": "The gland is removed with fire-resistant tongs after the salamander is incapacitated, requiring care to avoid burns.",
  "effects": [
   {
    "line": "1d6 fire damage",
    "route": "external"
   },
   {
    "line": "1d4 fire damage",
    "route": "ingest"
   },
   {
    "line": "Resist cold 5 for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+2 Initiative for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "gland",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "salamander-orchids",
  "name": "Salamander Orchids",
  "kind": "herb",
  "tier": "rare",
  "description": "Brass-looking orchids of the Elemental Plane of Fire that burn with a smokeless, torch-bright flame; bare hands take 1d6 fire damage. Worked into a weapon they make it flame, 1d6 fire on a hit (alchemy's use). A petal, eaten, lends its nature: resist fire 10 for 4 hours, and a +3 alchemical bonus on Fortitude saves against cold and exposure for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "1d6 fire damage",
    "route": "skin"
   },
   {
    "line": "1d6 fire damage",
    "route": "external"
   },
   {
    "line": "Resist fire 10 for 4 hours",
    "route": "ingest"
   },
   {
    "line": "+3 Fortitude against cold and exposure for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "flower",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "sand-vine",
  "name": "Sand Vine",
  "kind": "herb",
  "tier": "uncommon",
  "description": "The juice makes vine oil (DC 15), an anaesthetic spread on the skin. It numbs pain enough to fight through: 1d6 temporary hit points and a +2 alchemical bonus on Will saves against pain effects for an hour. The hands go numb too, -2 on Sleight of Hand checks for as long. The sap thickens a salve.",
  "harvesting": "",
  "effects": [
   {
    "line": "1d6 temporary hit points for 1 hour",
    "route": "skin"
   },
   {
    "line": "+2 Will against pain effects for 1 hour",
    "route": "skin"
   },
   {
    "line": "-2 Sleight Of Hand for 1 hour",
    "route": "skin"
   }
  ],
  "part": "sap",
  "hybrid": false,
  "base_for": [
   "salve"
  ]
 },
 {
  "id": "scorpion",
  "name": "Scorpion",
  "kind": "herb",
  "tier": "common",
  "description": "The body, powdered and brewed, makes a draught against venom: a +2 alchemical bonus on Fortitude saves against poison for an hour, and a sting of its own, 1 poison damage. Pressed into a fresh sting, the powder gives +2 on Fortitude saves against that venom for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude against poison for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+2 Fortitude against the venom in the sting for 1 hour",
    "route": "wound"
   },
   {
    "line": "1 poison damage",
    "route": "ingest"
   }
  ],
  "part": "shell",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "sealwort",
  "name": "Sealwort",
  "kind": "herb",
  "tier": "common",
  "description": "Solomon's seal. The roots, prepared as a poultice for injured limbs, heal 1d4 hit points bound on a wound, and 1d3 non-lethal damage rubbed on a bruise. A tea of the root gives a +1 alchemical bonus on Fortitude saves against fatigue for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d4 hit points",
    "route": "wound"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "skin"
   },
   {
    "line": "+1 Fortitude against fatigue for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "root",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "selpeme-blossom",
  "name": "Selpeme Blossom",
  "kind": "herb",
  "tier": "common",
  "description": "A florid red-purple jungle orchid. Rubbed on the skin, the petals make the wearer smell of fear to animals: for 8 hours an animal attacking them takes -4 on attack rolls, and the wearer gains +2 on Intimidate against animals for an hour (alchemy's use). The same oil keeps stinging things off: a +2 alchemical bonus on Fortitude saves against insect stings and vermin poison for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "-4 Attack rolls animals attacking the wearer for 8 hours",
    "route": "external"
   },
   {
    "line": "+2 Intimidate against animals, petals rubbed on the skin for 1 hour",
    "route": "external"
   },
   {
    "line": "+2 Fortitude against insect stings and vermin poison for 1 hour",
    "route": "skin"
   }
  ],
  "part": "flower",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "shadowvine",
  "name": "Shadowvine",
  "kind": "herb",
  "tier": "common",
  "description": "A creeping black vine of cursed forests whose heart-shaped leaves drink the light. Swallowed, it lets the user blend into shadow, +2 Stealth for 3 hours (alchemy's use). The herbalist's dose keeps only the dark's endurance, a +2 alchemical bonus on Fortitude saves against negative energy for an hour, and the dark's eyes: -2 on Perception checks in bright light.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Stealth for 3 hours",
    "route": "external"
   },
   {
    "line": "+2 Fortitude against negative energy for 1 hour",
    "route": "ingest"
   },
   {
    "line": "-2 Perception in bright light for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "sherpa-s-friend",
  "name": "Sherpa's Friend",
  "kind": "herb",
  "tier": "common",
  "description": "A small green plant of temperate lowlands. A dose gives a +2 alchemical bonus on Fortitude saves against altitude sickness for 4 hours and +1 against cold for an hour, and leaves the head light: -1 on Perception checks for the hour. Dried, it keeps for a year.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude against altitude sickness for 4 hours",
    "route": "ingest"
   },
   {
    "line": "+1 Fortitude against cold for 1 hour",
    "route": "ingest"
   },
   {
    "line": "-1 Perception for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "skull-orchid",
  "name": "Skull Orchid",
  "kind": "herb",
  "tier": "common",
  "description": "Dangerous to touch: each part of the orchid carries its own contact poison, a DC 17 save or 1d4 Intelligence and 1d4 Constitution damage from the leaves, and 2d6 Constitution damage from the seeds. Picked and handled fast, it becomes safe, and a measured taste of the neutral flesh hardens the body against toxins, a +2 alchemical bonus on Fortitude saves against poison for an hour, at a cost of -1 Intelligence for the hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "1d4 Intelligence damage",
    "route": "skin"
   },
   {
    "line": "1d4 Constitution damage",
    "route": "skin"
   },
   {
    "line": "2d6 Constitution damage",
    "route": "skin"
   },
   {
    "line": "DC 17",
    "route": "skin"
   },
   {
    "line": "+2 Fortitude against poison for 1 hour",
    "route": "ingest"
   },
   {
    "line": "-1 Intelligence for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "sphagnum-moss",
  "name": "Sphagnum Moss",
  "kind": "fungus",
  "tier": "common",
  "description": "Sterilized and dried, the moss makes a clean dressing. Bound on a wound it heals 1d4 hit points and gives a +1 alchemical bonus on Heal checks dressing it; laid on broken skin, +1 on Fortitude saves against infection, each for an hour. It must be changed every three days.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d4 hit points",
    "route": "wound"
   },
   {
    "line": "+1 Fortitude against infection for 1 hour",
    "route": "skin"
   },
   {
    "line": "+1 Heal dressing a wound for 1 hour",
    "route": "wound"
   }
  ],
  "part": "fungus",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "sphinx-whisker",
  "name": "Sphinx Whisker",
  "kind": "monster part",
  "tier": "exotic",
  "description": "Plucked with silver tweezers while a sphinx sleeps, or after it dies, and burned. Breathing the smoke gives a +4 alchemical bonus to Intelligence and +3 on Will saves against illusions for 3 hours. The user grows over-analytical, a -2 penalty on Diplomacy checks for as long.",
  "harvesting": "Whiskers must be plucked with a silver tweezers during a sphinx’s slumber or after death, requiring stealth to avoid its riddling wrath.",
  "effects": [
   {
    "line": "+4 Intelligence for 3 hours",
    "route": "inhale"
   },
   {
    "line": "-2 Diplomacy for 3 hours",
    "route": "inhale"
   },
   {
    "line": "+3 Will against illusions for 3 hours",
    "route": "inhale"
   }
  ],
  "part": "feather",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "spriggan-tree",
  "name": "Spriggan Tree",
  "kind": "herb",
  "tier": "common",
  "description": "A tree that grows up for half its life and then shrinks back into the ground. Its acorns make cheap potions of enlarging, +2 size bonus to Strength for 5 minutes (alchemy's use). The bark, boiled into a tea, purges parasites: a +2 alchemical bonus on Fortitude saves against parasites and disease for an hour, and a round of nausea as it works. Ground, the bark is a salve base.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Strength enlarged by an acorn for 5 minutes",
    "route": "external"
   },
   {
    "line": "+2 Fortitude against parasites and disease for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Causes nauseated for 1 round",
    "route": "ingest"
   }
  ],
  "part": "bark",
  "hybrid": true,
  "base_for": [
   "salve"
  ]
 },
 {
  "id": "st-john-s-wort",
  "name": "St. John's-Wort",
  "kind": "herb",
  "tier": "common",
  "description": "Boiled in wine, a dozen sprigs make a tincture that closes wounds: applied at once, it heals 1d4 hit points. The powdered seeds in a broth give a +1 alchemical bonus on Fortitude saves against poison, and the flowering tops +1 on Will saves against despair and fear, each for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d4 hit points",
    "route": "wound"
   },
   {
    "line": "+1 Fortitude against poison for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+1 Will against despair and fear for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "starbloom",
  "name": "Starbloom",
  "kind": "herb",
  "tier": "common",
  "description": "Delicate star-shaped flowers of moonlit glades that glow silver-blue. Brewed into a tea, they sharpen night sight and nerve: a +2 alchemical bonus on Perception checks in darkness and on Will saves against fear in the dark, for an hour. Bright light stings the drinker's eyes, a -2 penalty on checks made in it for the hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "-2 Perception in bright light for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+2 Perception in darkness for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+2 Will against fear in the dark for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "flower",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "sukake",
  "name": "Sukake",
  "kind": "herb",
  "tier": "common",
  "description": "Lemon-like fruit that brings hallucinations and dreaming sleep. Eaten while casting a divination it strengthens the spell, +1 caster level (alchemy's use). Eaten alone it opens the mind's eye, a +2 alchemical bonus on Spellcraft checks for divinations for an hour, and it is a narcotic: a DC 13 save or 1 Intelligence and 1 Wisdom damage.",
  "harvesting": "",
  "effects": [
   {
    "line": "+1 Caster level checks casting a divination for 1 hour",
    "route": "external"
   },
   {
    "line": "+2 Spellcraft for divinations for 1 hour",
    "route": "ingest"
   },
   {
    "line": "DC 13",
    "route": "ingest"
   },
   {
    "line": "1 Intelligence damage",
    "route": "ingest"
   },
   {
    "line": "1 Wisdom damage",
    "route": "ingest"
   }
  ],
  "part": "berry",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "sweetspire",
  "name": "Sweetspire",
  "kind": "herb",
  "tier": "common",
  "description": "A small tree of many uses: torches from the resin, and a sweet white wine from the leaves that heals 1d3 non-lethal damage. Smeared on the skin the sap warms on contact, resist cold 2 for an hour, and gives a +2 alchemical bonus on Fortitude saves against paralysis for as long. The sap thickens a salve.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude against paralysis for 1 hour",
    "route": "skin"
   },
   {
    "line": "Resist cold 2 for 1 hour",
    "route": "skin"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "ingest"
   }
  ],
  "part": "sap",
  "hybrid": false,
  "base_for": [
   "salve"
  ]
 },
 {
  "id": "tahtoalehti",
  "name": "Tahtoalehti",
  "kind": "herb",
  "tier": "legendary",
  "description": "Wishfern, the most valuable of magical plants. It blooms once every 1d100 years, on the winter solstice, and the single luminous flower, harvested unbruised (DC 40), grants a wish (alchemy's use; the app keeps it as a permanent +1 inherent bonus to Constitution). Before day withers it, the blossom eaten is a lesser miracle: it heals 6d6 hit points and gives a +4 alchemical bonus on all saves for a day.",
  "harvesting": "",
  "effects": [
   {
    "line": "+1 Constitution a wish granted (permanent)",
    "route": "external"
   },
   {
    "line": "Heals 6d6 hit points",
    "route": "ingest"
   },
   {
    "line": "+4 Fortitude for 1 day",
    "route": "ingest"
   },
   {
    "line": "+4 Reflex for 1 day",
    "route": "ingest"
   },
   {
    "line": "+4 Will for 1 day",
    "route": "ingest"
   }
  ],
  "part": "flower",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "tamarisk",
  "name": "Tamarisk",
  "kind": "herb",
  "tier": "common",
  "description": "Burning tamarisk offends every reptile from snake to dragon, as garlic offends vampires: in the smoke, +2 AC and +2 on Will saves against reptilian creatures for 10 minutes (alchemy's use). Its sweet manna, eaten, gives a +2 alchemical bonus on Fortitude saves against snake and reptile venom for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Armour class against reptilian creatures for 10 minutes",
    "route": "external"
   },
   {
    "line": "+2 Will vs the abilities of reptilian creatures, in the smoke for 10 minutes",
    "route": "external"
   },
   {
    "line": "+2 Fortitude against snake and reptile venom for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "tereeka-root",
  "name": "Tereeka Root",
  "kind": "herb",
  "tier": "rare",
  "description": "Chewed for a minute (DC 30 to prepare), the root takes pain away and speeds healing: it heals 1d8 hit points and gives 2d4 temporary hit points for an hour. The numbness reaches the senses, -2 on Perception checks for the hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d8 hit points",
    "route": "ingest"
   },
   {
    "line": "2d4 temporary hit points for 1 hour",
    "route": "ingest"
   },
   {
    "line": "-2 Perception for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "root",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "tobacco",
  "name": "Tobacco",
  "kind": "herb",
  "tier": "common",
  "description": "Crushed red-to-black leaves, smoked or chewed. Smoked, the calm gives a +1 alchemical bonus on Will saves against fear, and costs the lungs, -1 Constitution, for an hour. Chewed, it dulls hunger: +1 on Fortitude saves against hunger for an hour. It is habit-forming.",
  "harvesting": "",
  "effects": [
   {
    "line": "+1 Will against fear for 1 hour",
    "route": "inhale"
   },
   {
    "line": "+1 Fortitude against hunger for 1 hour",
    "route": "ingest"
   },
   {
    "line": "-1 Constitution for 1 hour",
    "route": "inhale"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "trollheart-sap",
  "name": "Trollheart Sap",
  "kind": "monster part",
  "tier": "rare",
  "description": "Cut from a freshly slain troll's heart and drained within ten minutes. Distilled into a tonic, it makes flesh knit at once: it heals 2d4 hit points and gives a +3 alchemical bonus on Fortitude saves against disease and infection for an hour. The skin coarsens, a -2 penalty to Charisma for a day.",
  "harvesting": "The heart must be cut from a freshly slain troll and drained within 10 minutes, as it hardens rapidly; a sharp blade and heat-resistant gloves are essential.",
  "effects": [
   {
    "line": "Heals 2d4 hit points",
    "route": "ingest"
   },
   {
    "line": "-2 Charisma for 24 hours",
    "route": "ingest"
   },
   {
    "line": "+3 Fortitude against disease and infection for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "organ",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "tugwort",
  "name": "Tugwort",
  "kind": "herb",
  "tier": "common",
  "description": "An alpine plant with a little stalk and roots three feet deep. An infusion toughens the skin: resist slashing 3 and piercing 2 for 8 hours, and a -1 penalty to Dexterity for as long as the skin stays stiff. Fresh it keeps a week, dried a month.",
  "harvesting": "",
  "effects": [
   {
    "line": "Resist slashing 3 for 8 hours",
    "route": "ingest"
   },
   {
    "line": "Resist piercing 2 for 8 hours",
    "route": "ingest"
   },
   {
    "line": "-1 Dexterity for 8 hours",
    "route": "ingest"
   }
  ],
  "part": "root",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "twilight-dagger",
  "name": "Twilight Dagger",
  "kind": "herb",
  "tier": "common",
  "description": "A bulbous cactus of magic-soaked lands, crowned with twilight-blue flowers. Its sap carries a faint charge: drunk, it gives 1d4 temporary hit points and a +1 alchemical bonus on initiative for an hour; smeared on the skin, resist electricity 2 for an hour. It thickens a salve.",
  "harvesting": "",
  "effects": [
   {
    "line": "1d4 temporary hit points for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+1 Initiative for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Resist electricity 2 for 1 hour",
    "route": "skin"
   }
  ],
  "part": "sap",
  "hybrid": true,
  "base_for": [
   "salve"
  ]
 },
 {
  "id": "tyrant-s-sword",
  "name": "Tyrant's Sword",
  "kind": "herb",
  "tier": "common",
  "description": "The silver parts of the plant boil down into frost lotion (DC 10). Spread on frostbite within two rounds, it heals 1d4 hit points and gives resist cold 2 for 10 minutes, and numbs the limb, -1 Dexterity for as long.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d4 hit points",
    "route": "skin"
   },
   {
    "line": "Resist cold 2 for 10 minutes",
    "route": "skin"
   },
   {
    "line": "-1 Dexterity for 10 minutes",
    "route": "skin"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "vervain",
  "name": "Vervain",
  "kind": "herb",
  "tier": "common",
  "description": "Dried and burned as incense, vervain strengthens anyone turning or rebuking undead nearby, +1 on the caster level check, and gives +1 on Will saves against undead, for an hour (alchemy's use). A tea of the leaves eases headache and sleeplessness, healing 1d3 non-lethal damage.",
  "harvesting": "",
  "effects": [
   {
    "line": "+1 Caster level checks turning or rebuking undead for 1 hour",
    "route": "external"
   },
   {
    "line": "+1 Will vs the abilities of undead, within the incense for 1 hour",
    "route": "external"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "visma-paste",
  "name": "Visma Paste",
  "kind": "herb",
  "tier": "uncommon",
  "description": "Boiled leaves (DC 15) worked into a paste for burns. One application heals 1d6 non-lethal damage from heat, gives a +2 alchemical bonus on Fortitude saves against heat and resist fire 2, for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d6 non-lethal damage",
    "route": "skin"
   },
   {
    "line": "+2 Fortitude against environmental heat for 1 hour",
    "route": "skin"
   },
   {
    "line": "Resist fire 2 for 1 hour",
    "route": "skin"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "wendigo-antler",
  "name": "Wendigo Antler",
  "kind": "monster part",
  "tier": "exotic",
  "description": "Broken off with a blessed weapon. Ground and scattered, the dust makes a chilling aura that holds undead off, +2 AC against them for an hour, and curses whoever scattered it (-2 Constitution; alchemy's use). A pinch in a broth makes the wendigo's cold the drinker's own: resist cold 10 for 4 hours.",
  "harvesting": "The antler must be broken off with a blessed weapon after the wendigo is banished or slain, as it resists mundane tools.",
  "effects": [
   {
    "line": "+2 Armour class against undead for 1 hour",
    "route": "external"
   },
   {
    "line": "-2 Constitution due to the antler's lingering curse for 1 hour",
    "route": "external"
   },
   {
    "line": "Resist cold 10 for 4 hours",
    "route": "ingest"
   }
  ],
  "part": "horn",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "wild-fireclover",
  "name": "Wild Fireclover",
  "kind": "herb",
  "tier": "rare",
  "description": "The stems make mindfire, an additive that adds a -2 penalty on Will saves to an ingested poison (alchemy's use). A tea of the flowers works the other way: a +3 alchemical bonus on Will saves against mind-clouding poisons and confusion, and +2 on Fortitude saves against ingested poison, for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "-2 Will if either of the poison's saves is failed for 1 hour",
    "route": "external"
   },
   {
    "line": "+3 Will against mind-clouding poisons and confusion for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+2 Fortitude against ingested poison for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "winterbite",
  "name": "Winterbite",
  "kind": "herb",
  "tier": "common",
  "description": "A wild mint with white-tipped leaves that wolves rub their noses in. Crushed under the nose, it clears the sinuses: a +2 alchemical bonus on scent-based Perception checks and +1 on Fortitude saves against colds and stench for an hour. The sharp sweet smell carries, -1 on Stealth checks for as long.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Perception scent for 1 hour",
    "route": "inhale"
   },
   {
    "line": "+1 Fortitude against colds and stench for 1 hour",
    "route": "inhale"
   },
   {
    "line": "-1 Stealth the sharp scent carries for 1 hour",
    "route": "inhale"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "wispweed",
  "name": "Wispweed",
  "kind": "herb",
  "tier": "common",
  "description": "A pale-green marsh grass that sways as if alive. Burned, its smoke lets those inside it speak mind to mind, +2 on Diplomacy among them for an hour (alchemy's use). Breathed, it gives a +2 alchemical bonus on Sense Motive checks for an hour, and irritates the lungs, -1 Constitution for as long.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Diplomacy speaking mind to mind in the smoke for 1 hour",
    "route": "external"
   },
   {
    "line": "+2 Sense Motive for 1 hour",
    "route": "inhale"
   },
   {
    "line": "-1 Constitution for 1 hour",
    "route": "inhale"
   }
  ],
  "part": "leaf",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "wittlewort",
  "name": "Wittlewort",
  "kind": "herb",
  "tier": "uncommon",
  "description": "Dried, treated and powdered (DC 15), then brewed. The brew gives a +2 alchemical bonus on Will saves against enchantments and on Sense Motive checks to spot one, for an hour, and turns the drinker inward: -1 on Perception checks for as long.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Will against enchantments for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+2 Sense Motive to spot enchantment for 1 hour",
    "route": "ingest"
   },
   {
    "line": "-1 Perception for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "woad",
  "name": "Woad",
  "kind": "herb",
  "tier": "common",
  "description": "The leaves cool a burn, healing 2 hit points. Woad seed oil, spread on the skin before a fight, seals each cut as it opens: DR 1/- for an hour. Painted on in the old blue patterns, the dye gives a +2 alchemical bonus on Intimidate checks for an hour, and stains for weeks.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 2 hit points",
    "route": "skin"
   },
   {
    "line": "DR 1/— for 1 hour",
    "route": "skin"
   },
   {
    "line": "+2 Intimidate painted blue for 1 hour",
    "route": "skin"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "wolfsbane",
  "name": "Wolfsbane",
  "kind": "herb",
  "tier": "common",
  "description": "The root is toxic, but in low doses dulls pain and steadies the heart: it heals 1d3 non-lethal damage and gives a +2 alchemical bonus on Fortitude saves against lycanthropy for an hour. The dose is never quite safe: a DC 13 Fortitude save or 1 Strength damage.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude against lycanthropy for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "ingest"
   },
   {
    "line": "Fortitude DC 13",
    "route": "ingest"
   },
   {
    "line": "1 Strength damage",
    "route": "ingest"
   }
  ],
  "part": "root",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "wolfweed",
  "name": "Wolfweed",
  "kind": "herb",
  "tier": "common",
  "description": "Makes journeyman serum (DC 5), drunk on the road: a +2 alchemical bonus on Fortitude saves against the fatigue of a forced march for 8 hours, and 1d4 temporary hit points for one. The road-numbness dulls the mind, -1 Wisdom for the hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude against a forced march for 8 hours",
    "route": "ingest"
   },
   {
    "line": "1d4 temporary hit points for 1 hour",
    "route": "ingest"
   },
   {
    "line": "-1 Wisdom for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "wordwood",
  "name": "Wordwood",
  "kind": "herb",
  "tier": "common",
  "description": "An infusion that drives out internal parasites: a +2 alchemical bonus on Fortitude saves against parasites and disease for an hour, and a DC 11 Fortitude save or nausea for 3 rounds as it works. Once it has, the body mends, healing 1d3 non-lethal damage.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Fortitude against parasites and disease for 1 hour",
    "route": "ingest"
   },
   {
    "line": "Fortitude DC 11",
    "route": "ingest"
   },
   {
    "line": "Causes nauseated for 3 rounds",
    "route": "ingest"
   },
   {
    "line": "Heals 1d3 non-lethal damage",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "woundwort",
  "name": "Woundwort",
  "kind": "herb",
  "tier": "common",
  "description": "A styptic for deep cuts. Laid on an injury within two rounds, it heals 1d4 hit points and gives a +2 alchemical bonus on Heal checks to staunch the bleeding for an hour. A tea of the leaves gives +1 on Fortitude saves against infection for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "+2 Heal to staunch bleeding for 1 hour",
    "route": "wound"
   },
   {
    "line": "Heals 1d4 hit points",
    "route": "wound"
   },
   {
    "line": "+1 Fortitude against infection for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 },
 {
  "id": "wyrmfang-venom",
  "name": "Wyrmfang Venom",
  "kind": "monster part",
  "tier": "rare",
  "description": "Milked from a wyrm's fangs. Concentrated and applied to a weapon, it adds 1d8 poison damage for an hour (alchemy's use); spilled on the skin it burns, a DC 15 Fortitude save or 1d4 poison damage. A trace swallowed hardens the body against venom: a +3 alchemical bonus on Fortitude saves against poison for an hour.",
  "harvesting": "Venom is milked from the fangs of a sedated or dead wyrm using a glass syringe, requiring steady hands to avoid contact, as it burns skin.",
  "effects": [
   {
    "line": "1d8 poison damage",
    "route": "external"
   },
   {
    "line": "Fortitude DC 15 · fail: 1d4 poison damage",
    "route": "skin"
   },
   {
    "line": "+3 Fortitude against poison for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "gland",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "xian-tao",
  "name": "Xian Tao",
  "kind": "herb",
  "tier": "uncommon",
  "description": "The mythical peach tree of immortality, found on remote, icy mountaintops it warms with its own heat. A fruit eaten within three hours of picking heals 2d6 hit points, makes the eater immune to poison for a day and gives a +2 alchemical bonus on Fortitude saves against disease for as long.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 2d6 hit points",
    "route": "ingest"
   },
   {
    "line": "Immune to poison for 24 hours",
    "route": "ingest"
   },
   {
    "line": "+2 Fortitude against disease for 24 hours",
    "route": "ingest"
   }
  ],
  "part": "berry",
  "hybrid": true,
  "base_for": []
 },
 {
  "id": "yarow",
  "name": "Yarow",
  "kind": "herb",
  "tier": "common",
  "description": "Yarrow. Leaves prepared in a poultice and bound on a wound heal 1d4 hit points. Powdered and brewed, they break a fever, a +1 alchemical bonus on Fortitude saves against fever, and help with reading what is to come, +1 on Sense Motive checks, each for an hour.",
  "harvesting": "",
  "effects": [
   {
    "line": "Heals 1d4 hit points",
    "route": "wound"
   },
   {
    "line": "+1 Fortitude against fever for 1 hour",
    "route": "ingest"
   },
   {
    "line": "+1 Sense Motive for 1 hour",
    "route": "ingest"
   }
  ],
  "part": "leaf",
  "hybrid": false,
  "base_for": []
 }
]
```
