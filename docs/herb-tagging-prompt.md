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

Answer with JSON only, in exactly this shape, one object per ingredient you are
changing from the defaults. Omit any ingredient you are leaving alone:

{
  "adder-s-tongue": {
    "needs_extraction": false,
    "volatile": true,
    "can_grind": true,
    "mix_raw": false,
    "brew_raw": true,
    "animal": false,
    "why": {"volatile": "the sap blisters skin", "mix_raw": "inert until crushed"}
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
  "description": "Inhaling acacia smoke as incense adds +1 to any Will saves for 1 hour. Other uses include making dye/ink and its gummy sap can be used in many ointments and salves.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "aconite",
  "name": "Aconite",
  "kind": "herb",
  "tier": "common",
  "description": "Can be used to make antidote vs. animal poisons (+1 to Fort saves). Its special use is, if chewed or eaten within an hour of a lycanthrope's attack, you gain a DC 20 Fortitude save to shake off the effects of the lycanthrope curse. If boiled in hot water it can make a poison that can be infused into food or drink (DC 13 to avoid nausea for 1d4 rounds, then vomiting and 1d4 Str loss).",
  "harvesting": "",
  "effects": [
   "DC 20",
   "Causes nauseated for 1d4 rounds"
  ]
 },
 {
  "id": "adder-s-tongue",
  "name": "Adder's-Tongue",
  "kind": "herb",
  "tier": "common",
  "description": "Secondary treatment, helps the wounded regain strength. Leaves can be boiled as a tea. Recuperating wounded receive one extra hit point per day of rest, or 1-3 if convalescing with no activity. Used leaves can be combined with animal to make an ointment called \"green oil of charity\". The ointment cures 1-2 hit points immediately; only usable once per day.",
  "harvesting": "",
  "effects": [
   "Heals 1-2 hit points"
  ]
 },
 {
  "id": "aelfengrape",
  "name": "Aelfengrape",
  "kind": "herb",
  "tier": "uncommon",
  "description": "A grape plant modified by elven wizards, it provides mild illumination equal to a candle and produces fruit that is highly nutritious. A handful of grapes equals one meal. Can also be used to make wine, tea, and various crafts. DC: 15.",
  "harvesting": "",
  "effects": [
   "Acts as illuminates like a candle"
  ]
 },
 {
  "id": "allnight",
  "name": "Allnight",
  "kind": "herb",
  "tier": "common",
  "description": "This treated wafer dissolves into a chalky paste when placed under the tongue and then gives the imbiber a jolt of restless energy. It eliminates the effects of fatigue for the next 8 hours; when the drug’s effect ends, the user is exhausted. Allnight makes its users jittery and unable to focus; they suffer a –2 penalty on all skill checks until its effects wear off.",
  "harvesting": "",
  "effects": [
   "-2 skill checks until its effects wear off",
   "Ends fatigued",
   "Causes exhausted"
  ]
 },
 {
  "id": "althaea",
  "name": "Althaea",
  "kind": "herb",
  "tier": "common",
  "description": "Root pulverized into a poultice that heals wounds.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "amaranth",
  "name": "Amaranth",
  "kind": "herb",
  "tier": "common",
  "description": "Stops bleeding and hit point loss when applied to a wound as either a fresh poultice or dried and taken internally as a tea.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "angelica",
  "name": "Angelica",
  "kind": "herb",
  "tier": "common",
  "description": "Leaves brewed into a potion that wards off disease and magic, and cures disease.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "anise",
  "name": "Anise",
  "kind": "herb",
  "tier": "common",
  "description": "A combination oil used on the skin confers a +1 Fortitude save to resist skin diseases such as leprosy, grave rot, and swamp foot. Lasts two days. Can make a pill that boosts the immune system, giving a +2 Fortitude save against disease for 24 hours. Can be made into a soap that removes odors like skunk musk, or a powder that protects from odor type attacks like stinking cloud, giving a +1 save bonus for two days. An herbal tea relieves respiratory disorders, giving a +2 Heal skill bonus when dealing with breathing pain or congestion type problems.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "banshee-wail-essence",
  "name": "Banshee Wail Essence",
  "kind": "monster part",
  "tier": "exotic",
  "description": "When concentrated and inhaled, the essence amplifies the user’s voice, granting a +5 bonus to intimidate checks for 4 hours, but leaves them hoarse, imposing a –3 penalty to charisma-based checks afterward.",
  "harvesting": "The essence is captured in a sealed glass vial during the banshee’s wail, requiring quick reflexes to avoid its deafening effect.",
  "effects": [
   "+5 Intimidate for 4 hours"
  ]
 },
 {
  "id": "barbarian-chew",
  "name": "Barbarian Chew",
  "kind": "herb",
  "tier": "common",
  "description": "This bitter red chew comes from dried leaves of a stunted bush found in northern climates. It stains the teeth dark crimson but also increases the duration of barbarian rage entered into during the next hour by 1 round.",
  "harvesting": "",
  "effects": [
   "Causes stunned"
  ]
 },
 {
  "id": "barley",
  "name": "Barley",
  "kind": "herb",
  "tier": "common",
  "description": "Low grade cereal crop used to make bread or fermented in water to make beers and ales. Barley-laced water is often used as a medicinal by apothecaries and midwives (boil in water and drink to return 1 point of subdual damage).",
  "harvesting": "",
  "effects": [
   "Heals 1 non-lethal damage",
   "1 untyped non-lethal damage"
  ]
 },
 {
  "id": "basil",
  "name": "Basil",
  "kind": "herb",
  "tier": "common",
  "description": "Common herb, if 5 fresh leaves are stuffed into a poisoned wound, you gain an immediate Fort Save vs. poison.",
  "harvesting": "",
  "effects": [
   "Another Fortitude save against poison"
  ]
 },
 {
  "id": "basilisk-eye",
  "name": "Basilisk Eye",
  "kind": "monster part",
  "tier": "rare",
  "description": "When ground and mixed with holy water, the eye creates a paste that grants immunity to gaze attacks for 6 hours, but the user’s vision blurs, imposing a –4 penalty to perception checks.",
  "harvesting": "The eye must be removed with a precise incision using an obsidian knife within 1 hour of the basilisk’s death, avoiding direct eye contact to prevent petrification.",
  "effects": [
   "-4 Perception for 6 hours",
   "Immune to gaze attacks for 6 hours"
  ]
 },
 {
  "id": "behemoth-hide",
  "name": "Behemoth Hide",
  "kind": "monster part",
  "tier": "legendary",
  "description": "When tanned and worn as a patch, the hide grants a +3 natural armor bonus for 12 hours, but its weight reduces the user’s carrying capacity by 20% for the duration.",
  "harvesting": "The hide is stripped with a flensing knife after the behemoth is killed, requiring hours of labor due to its toughness.",
  "effects": []
 },
 {
  "id": "belladonna",
  "name": "Belladonna",
  "kind": "herb",
  "tier": "common",
  "description": "Sometimes used in dangerous religious ceremonies, it is mostly used to make poisons. One dose is DC 15/Nausea/1d8 hp damage. It can be prepared as a contact, injury, or ingestion poison. Like wolfsbane, if eaten within an hour of a lycanthrope attack you can roll a DC 20 Fort save to avoid the curse.",
  "harvesting": "",
  "effects": [
   "DC 15",
   "Causes nauseated"
  ]
 },
 {
  "id": "betony",
  "name": "Betony",
  "kind": "herb",
  "tier": "common",
  "description": "The flowers can be made into an analgesic and a curative for colds (use adds +1 Fort save vs. disease).",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "birthwort",
  "name": "Birthwort",
  "kind": "herb",
  "tier": "common",
  "description": "Curative. If leaves and stems are crushed, juice can immediately (within one round) be applied to poisonous bites or stings; provides +2 save against poison. Only works once per poison attack. A poultice can also be made to insure that wounds heal properly; adds and extra point of hit point recovery for first two days of rest; normal rest rate continues after two days.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "bitterroot",
  "name": "Bitterroot",
  "kind": "herb",
  "tier": "common",
  "description": "Can ferment into an extremely bitter brew that makes a person twice as drunk and for twice as long as normal if they don't make periodic Fortitude saves (DC 17). A special preparation can protect the user against being drunk for a number of hours equal to his Constitution modifier.",
  "harvesting": "",
  "effects": [
   "DC 17"
  ]
 },
 {
  "id": "blackthorn",
  "name": "Blackthorn",
  "kind": "herb",
  "tier": "common",
  "description": "This can be used against evil outsiders and demons in the same way garlic can be used to repel vampires. They can be grown as hedges or simply gathered and strewn about an area.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "bloodroot",
  "name": "Bloodroot",
  "kind": "herb",
  "tier": "common",
  "description": "A gnarled, red root that oozes a blood-like sap when cut, found beneath ancient battlegrounds. Drinking Bloodroot sap increases the user’s vitality, granting 10 temporary hit points for 8 hours. However, the sap clouds the mind, imposing a –4 penalty on intelligence-based checks during this time.",
  "harvesting": "",
  "effects": [
   "-4 Intelligence for 8 hours",
   "10 temporary hit points for 8 hours"
  ]
 },
 {
  "id": "blueweed",
  "name": "Blueweed",
  "kind": "herb",
  "tier": "common",
  "description": "Leaves powdered and sprinkled on something to ritually purify it.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "borage",
  "name": "Borage",
  "kind": "herb",
  "tier": "common",
  "description": "Pulping the leaves and flowers, then boiling, makes a medicine for breaking fevers and waking unconscious victims (gain a Fortitude save to fight off illness or poison effects early).",
  "harvesting": "",
  "effects": [
   "Another Fortitude save",
   "Causes unconscious"
  ]
 },
 {
  "id": "breeam",
  "name": "Breeam",
  "kind": "herb",
  "tier": "common",
  "description": "Tossing a handful of dried bark onto a fire emits a cloud of smoke that turns undead in a 10' diameter for 1d4 minutes as a 1st level cleric.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "bryony",
  "name": "Bryony",
  "kind": "herb",
  "tier": "common",
  "description": "All parts of this plant are poisonous (primary damage Nausea/ secondary damage 1d3 Str and 1d2 con). The various parts have different saves: stalks or root- DC 14, leaves and flowers- DC 16, berries- DC 17.",
  "harvesting": "",
  "effects": [
   "DC 14",
   "Causes nauseated"
  ]
 },
 {
  "id": "calendula",
  "name": "Calendula",
  "kind": "herb",
  "tier": "common",
  "description": "Flowers brewed into a potion that helps divine someone's future lover.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "caranator",
  "name": "Caranator",
  "kind": "herb",
  "tier": "common",
  "description": "Chew a piece of root to clear the mind (gain a Will save vs. any charms or enchantments immediately.)",
  "harvesting": "",
  "effects": [
   "Another Will save against charms or enchantments immediately"
  ]
 },
 {
  "id": "cave-star",
  "name": "Cave Star",
  "kind": "herb",
  "tier": "common",
  "description": "When prepared and stored in glass, it will give off light for four hours, with neither heat nor smoke. DC: 10.",
  "harvesting": "",
  "effects": [
   "DC 10"
  ]
 },
 {
  "id": "chasmyre-leaf",
  "name": "Chasmyre Leaf",
  "kind": "herb",
  "tier": "common",
  "description": "Chasmyre leaf is a sickly-looking brown-black leaf that grows on short shrubs in swampy environments. If crushed and applied to the eyelids, however, it grants the user Low Light Vision for an hour. Chasmyre leaf keeps for a few weeks.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "chimera-horn",
  "name": "Chimera Horn",
  "kind": "monster part",
  "tier": "exotic",
  "description": "When pulverized and inhaled as a powder, the horn grants a +3 bonus to saves against chaotic magic for 4 hours, but the user becomes prone to erratic behavior, taking a –3 penalty to wisdom-based checks.",
  "harvesting": "The horn must be sawed off with a diamond-edged blade after the chimera is incapacitated, as it resists lesser tools.",
  "effects": [
   "+3 saves against chaotic magic for 4 hours",
   "-3 Wisdom for 4 hours",
   "Causes prone for 4 hours"
  ]
 },
 {
  "id": "cloth-of-gold",
  "name": "Cloth of Gold",
  "kind": "herb",
  "tier": "common",
  "description": "Beyond its ordinary uses as a spell component, dye, or spice, you can chew on a flower or six leaves as a free action to gain a one-round speak with animals effect.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "cockatrice-beak",
  "name": "Cockatrice Beak",
  "kind": "monster part",
  "tier": "uncommon",
  "description": "When ground into a paste and applied to boots, the beak grants immunity to difficult terrain for 6 hours, but the user’s feet feel heavy, reducing movement speed by 5 feet.",
  "harvesting": "The beak must be broken off with a hammer and chisel after the cockatrice is killed, avoiding its petrifying gaze residue.",
  "effects": [
   "Immune to difficult terrain for 6 hours"
  ]
 },
 {
  "id": "coldwood",
  "name": "Coldwood",
  "kind": "herb",
  "tier": "uncommon",
  "description": "Grown by fey, this wood has the strength of iron while having none of iron's deleterious effects on fey. It can be used to craft both weapons and armor. Armor produced using coldwood can also be worn safely by druids. Objects created have the same hardness, strength, weight, and edge-holding properties as good-quality steel. The DC for crafting an item is always 8 higher than when crafting with actual steel.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "comfrey",
  "name": "Comfrey",
  "kind": "herb",
  "tier": "common",
  "description": "\"Wonder weed\" used in many ways. If root is applied immediately to a wound, roll 1-4 to see how many hit points \"were never done in the first place\" and subtract from damage taken. If used as a tea or mixed with wine during recuperation, has same qualities as adder's-tongue.",
  "harvesting": "",
  "effects": [
   "Heals 1-4 hit points"
  ]
 },
 {
  "id": "cotsbalm",
  "name": "Cotsbalm",
  "kind": "herb",
  "tier": "exotic",
  "description": "Sap is used as a base for a clear substance called purebalm. When poured on the skin of a someone poisoned by an injury or contact poison, it turns black as it draws it out of their system. If administered between the initial and secondary onset of a poison, it provides a +8 alchemical bonus to Fortitude save to resist the secondary effects. DC: 35.",
  "harvesting": "",
  "effects": [
   "+8 Fortitude to resist the secondary effects",
   "DC 35"
  ]
 },
 {
  "id": "cowslip",
  "name": "Cowslip",
  "kind": "herb",
  "tier": "common",
  "description": "Flowers brewed into a potion that cures paralysis and restores strength.",
  "harvesting": "",
  "effects": [
   "Ends paralyzed"
  ]
 },
 {
  "id": "damiana",
  "name": "Damiana",
  "kind": "herb",
  "tier": "common",
  "description": "The leaves and stalks can be harvested for use in incense. Anyone within the damiana incense vapors has their emotions and personality enhanced (+1 Charisma for one hour).",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "darkroot",
  "name": "Darkroot",
  "kind": "herb",
  "tier": "uncommon",
  "description": "Makes a strong glue called titan gum. Objects bonded with the glue require a DC 20 Strength check to separate. DC: 15.",
  "harvesting": "",
  "effects": [
   "DC 20"
  ]
 },
 {
  "id": "dawnpetal",
  "name": "Dawnpetal",
  "kind": "herb",
  "tier": "common",
  "description": "Bright yellow flowers with radiant, sunburst-shaped petals that grow in high mountain meadows. Chewing Dawnpetal grants a burst of energy, negating fatigue and granting a +2 bonus to strength for 2 hours. However, once the effect ends, the user becomes exhausted for twice the duration unless they rest for at least 1 hour.",
  "harvesting": "",
  "effects": [
   "+2 Strength for 2 hours",
   "Ends fatigued",
   "Causes exhausted"
  ]
 },
 {
  "id": "dire-boar-tusk",
  "name": "Dire Boar Tusk",
  "kind": "monster part",
  "tier": "uncommon",
  "description": "When carved into a powder and snorted, the tusk grants a +3 bonus to strength for 1 hour, but the user becomes aggressive, taking a –3 penalty to wisdom-based checks due to a reckless mindset.",
  "harvesting": "Tusks are sawed off with a steel saw after the boar is slain, requiring significant strength to cut through the dense bone.",
  "effects": [
   "+3 Strength for 1 hour, but the user becomes…"
  ]
 },
 {
  "id": "dittany",
  "name": "Dittany",
  "kind": "herb",
  "tier": "common",
  "description": "Can be heated in ale or wine to clear the head and help resist the lingering effects of poisons (regain 1d3 hp of subdual damage).",
  "harvesting": "",
  "effects": [
   "Heals 1d3 hit points"
  ]
 },
 {
  "id": "djinn-blossoms",
  "name": "Djinn Blossoms",
  "kind": "herb",
  "tier": "uncommon",
  "description": "Often grown by elves, but originating on the Elemental Plane of Air, the fern-like Blossoms maintains a link to its home plane, emitting a little breeze in all directions. Wearing a plucked djinn blossom provides a +2 bonus on all saves to resist inhaled poisons, gases, and spells that rely on gasses, clouds or fogs. It can also be made into a perfume using a DC 20 Craft (alchemy) check that gives a +2 bonus on Charisma skill checks. Both a worn blossom or a dose of perfume last for 24 hours. DC: 20.",
  "harvesting": "",
  "effects": [
   "+2 saves to resist inhaled poisons, gases, and spells for 24 hours",
   "+2 Charisma skill for 24 hours",
   "DC 20"
  ]
 },
 {
  "id": "dracolisk-scale",
  "name": "Dracolisk Scale",
  "kind": "monster part",
  "tier": "rare",
  "description": "When ground into a fine powder and sprinkled over armor, the scales grant resistance to petrification effects for 8 hours, but the user’s movement becomes sluggish, imposing a –2 penalty to dexterity-based checks.",
  "harvesting": "Scales must be carefully pried from the dracolisk’s hide using a non-metallic tool after it sheds naturally or is slain, as metal causes them to crumble.",
  "effects": [
   "-2 Dexterity for 8 hours"
  ]
 },
 {
  "id": "dragon-flower",
  "name": "Dragon Flower",
  "kind": "herb",
  "tier": "common",
  "description": "This plant produces an extremely foul odor; approaching within 60 requires a DC 20 Fortitude check. Saving results in a -2 penalty to all actions while in the area; failing means the creature is overcome with nausea and vomiting, being unable to take any action other than a single move or movement related action per turn. Lasts until you leave the area, plus 1d6 rounds. A preserved pod will keep its effects for 1d4 weeks, and can be used as a purgative. Sap from a pod has anti-toxic characteristics; if swallowed raw it gives a +5 bonus to save vs. poison for 10 rounds. Sap remains viable for 10 days and Herbalists can make it last much longer. Resin from the heart of the flower is an addictive, mind affecting toxin (Fortitude save DC 25 or suffer 12 hours euphoria and hallucinations, 1d6 Con damage and 1d6 days of cramps, vomiting and headaches).",
  "harvesting": "",
  "effects": [
   "-2 actions while in the area for 1d4 weeks",
   "+5 save vs poison for 10 rounds",
   "1d6 Constitution damage",
   "Fortitude DC 25",
   "Causes nauseated"
  ]
 },
 {
  "id": "dragon-s-blood",
  "name": "Dragon's Blood",
  "kind": "herb",
  "tier": "common",
  "description": "The resin of this palm tree can be used as a reagent for many other substances and it enhances many effects without making the concoctions unstable. Adding a pinch of resin to any herbal treatment that is eaten or imbibed has a 50% chance of of increasing its effectiveness by +1 per die of effect.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "dreamcap",
  "name": "Dreamcap",
  "kind": "fungus",
  "tier": "common",
  "description": "A luminescent, purple-capped mushroom that grows in enchanted groves and emits a faint hum. Consuming Dreamcap induces vivid, prophetic dreams for 6 hours, granting a +3 bonus to knowledge checks related to future events. However, the user is dazed for 1 minute upon waking as their mind adjusts to reality.",
  "harvesting": "",
  "effects": [
   "+3 knowledge checks related to future events for 6 hours",
   "Causes dazed for 1 minute"
  ]
 },
 {
  "id": "dreamer-s-star",
  "name": "Dreamer’s Star",
  "kind": "herb",
  "tier": "common",
  "description": "When the orange petals of this plant are cured and left to steep in hot water, the leaves make a mild, aromatic tea that facilitates restful sleep. When taken before sleeping, this tea grants the drinker the benefits of a full 8 hours of uninterrupted sleep in only 6 hours. One dose of Dreamer’s star makes enough tea to serve six.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "dryad-s-tears",
  "name": "Dryad's Tears",
  "kind": "herb",
  "tier": "common",
  "description": "While commoners use the berries from this climbing vine to make jam and wine, it has a special use: its odor repels lycanthropes in the same manner as blackthorn with outsiders and garlic with vampires.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "dwarven-oak",
  "name": "Dwarven Oak",
  "kind": "herb",
  "tier": "rare",
  "description": "The bark is used to create a liquid called oakdeath that increases toxicity when added to a poison. If added to a poison less than one hour before it is used, it increases the poison's DC by 2. DC: 25.",
  "harvesting": "",
  "effects": [
   "DC 25"
  ]
 },
 {
  "id": "elven-willow",
  "name": "Elven Willow",
  "kind": "herb",
  "tier": "common",
  "description": "The sap is the main component in a fluid called elf hazel. When applied over a week to an old wound, it makes the scar vanish completely. DC: 10.",
  "harvesting": "",
  "effects": [
   "DC 10"
  ]
 },
 {
  "id": "elysium",
  "name": "Elysium",
  "kind": "herb",
  "tier": "common",
  "description": "Strongly anti-magic. Any area where this grows is effectively covered with an Anti-magic field. This ability ends immediately once the plant is pulled up, but can continue for 2d4 weeks if pulled up with roots and attached earth. Eating it promotes efficient, healthier digestion; filling your stomach with the grass provides all the nutrition you need for two days. If enough grass is collected and drained, it can make a gel that, when rubbed onto the body, will give a +2 Hide check when in tall grass.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "euphorbia",
  "name": "Euphorbia",
  "kind": "herb",
  "tier": "common",
  "description": "The milkly juice of this plant is used as a purgative and a poison (DC 12; primary Nausea; secondary 1d3 Str). Rubbing the oily leaves on the skin will cause rashes and weeping blisters; doing this deliberately is an old beggar trick to make them appear more pitiable while they beg.",
  "harvesting": "",
  "effects": [
   "DC 12",
   "Causes nauseated"
  ]
 },
 {
  "id": "faerie-grass",
  "name": "Faerie Grass",
  "kind": "herb",
  "tier": "common",
  "description": "Stepping on a patch of this grass will disorient; make a DC 20 Will save or lose track of where you are going until you exit the grass. When eaten, the grass lowers blood sugar levels. Unless used to treat a diabetic, anyone eating must a DC 23 Fortitude save or lose 1d4 Constitution points as though starved for a week. A full day's worth of food must be consumed to return each Constitution point.",
  "harvesting": "",
  "effects": [
   "DC 20"
  ]
 },
 {
  "id": "fainne-mushroom",
  "name": "Fainne Mushroom",
  "kind": "fungus",
  "tier": "common",
  "description": "The base of the mushroom can be added to a potion to improve the duration by 25%; an Herbalist can increase this to 50%. The stem acts as an sexual stimulant, giving anyone attempting to seduce the user a Charisma bonus, +2 if they are attracted already, +1 if they are not. This effect lasts four hours.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "fey-cherry",
  "name": "Fey Cherry",
  "kind": "herb",
  "tier": "rare",
  "description": "The effects of weather and wind are reduced around these trees; within the canopy the temperature never drops below 50 degrees or rises above 80, wind is lessened by 20 mph. Once per decade it produces cherries that will give an protection from evil effect for 5 minutes when eaten. The magic lasts for one day after picking but gentle repose cast on the fruit will extend it for its duration. DC: 15.",
  "harvesting": "",
  "effects": [
   "DC 15"
  ]
 },
 {
  "id": "firesnap",
  "name": "Firesnap",
  "kind": "herb",
  "tier": "common",
  "description": "Notable only for its strong odor, dried sections of this are often kept to revive an unconscious person. Snap the root under a person's nose to give them a temporary hit point for 1 minute to move them out of danger.",
  "harvesting": "",
  "effects": [
   "Causes unconscious"
  ]
 },
 {
  "id": "flame-clove",
  "name": "Flame Clove",
  "kind": "herb",
  "tier": "uncommon",
  "description": "A garliclike herb imbued with elemental fire energy. When a clove is boiled in salt water and crushed and blended into food, it keeps the food hot for 1d4 days. Adding a sprig from the plant into alchemist's fire during crafting, it will double the fire damage and causes it to burn twice as long. DC: 15.",
  "harvesting": "",
  "effects": [
   "DC 15"
  ]
 },
 {
  "id": "flayleaf",
  "name": "Flayleaf",
  "kind": "herb",
  "tier": "common",
  "description": "These narrow, rust-colored leaves produce a mildly hallucinogenic smoke that also serves as powerful sedative. Users are immune to pain for 4 hours after smoking flayleaf, but during this time they take a –5 penalty on perception checks and saves against mind-altering effects.",
  "harvesting": "",
  "effects": [
   "-5 Perception and against mind altering… for 4 hours"
  ]
 },
 {
  "id": "fleshshiver",
  "name": "Fleshshiver",
  "kind": "herb",
  "tier": "uncommon",
  "description": "Mushroom used to combat fever in the tropics. Mix with cool mud and compress to head. Gives a +2 alchemical bonus to Fortitude saves made to resist non-magical diseases; lasts for one day. DC: 20.",
  "harvesting": "",
  "effects": [
   "+2 Fortitude made to resist non magical diseases",
   "DC 20"
  ]
 },
 {
  "id": "fool-s-weed",
  "name": "Fool's Weed",
  "kind": "herb",
  "tier": "common",
  "description": "Commoners often eat this as a leafy snack like lettuce or infuse it in a tea to help them sleep. Chewing 5 fresh leaves provides a calming effect and allows a Will save to help end any fear or rage effects, including barbarian rages.",
  "harvesting": "",
  "effects": [
   "Another Will save"
  ]
 },
 {
  "id": "frostbloom",
  "name": "Frostbloom",
  "kind": "herb",
  "tier": "common",
  "description": "Tiny, ice-blue flowers that sparkle like frost and thrive in snowy tundras. When ground into a paste and applied to the skin, Frostbloom grants resistance to fire damage for 4 hours, reducing fire damage taken by 10 points. However, the user’s body temperature drops, causing a –3 penalty to dexterity-based checks.",
  "harvesting": "",
  "effects": [
   "-3 Dexterity for 4 hours",
   "Resist fire for 4 hours"
  ]
 },
 {
  "id": "frostgiant-marrow",
  "name": "Frostgiant Marrow",
  "kind": "monster part",
  "tier": "exotic",
  "description": "When boiled into a broth and consumed, the marrow grants resistance to cold damage (10 points) for 12 hours, but the user’s body temperature drops, causing a –2 penalty to initiative rolls.",
  "harvesting": "The marrow is extracted by cracking the giant’s femur with a heavy hammer and scooping it out with a bone or wooden tool, as metal freezes to it.",
  "effects": [
   "-2 Initiative for 12 hours",
   "Resist cold 10 for 12 hours"
  ]
 },
 {
  "id": "garlic",
  "name": "Garlic",
  "kind": "herb",
  "tier": "common",
  "description": "Strong antiseptic, good for repelling insects (and vampires). Prevents infections when applied to wounds; wounded recover 2 hit points per day for the first three days of rest. Has a 50% chance of repelling attacking insects, giant or otherwise. Juice can restore one hit point per injury that was lost due to poisonous sting or bite.",
  "harvesting": "",
  "effects": [
   "Heals 2 hit points"
  ]
 },
 {
  "id": "gloomwraith-tendril",
  "name": "Gloomwraith Tendril",
  "kind": "monster part",
  "tier": "exotic",
  "description": "When boiled into a syrup and ingested, the tendrils grant the ability to see invisible creatures for 4 hours, but the user suffers a –3 penalty to saves against fear effects due to lingering dread.",
  "harvesting": "Tendrils must be severed with a silver blade during the gloomwraith’s brief materialization, requiring precise timing to avoid its chilling touch.",
  "effects": [
   "-3 saves against fear effects due to lingering dread for 4 hours"
  ]
 },
 {
  "id": "glowvine",
  "name": "Glowvine",
  "kind": "herb",
  "tier": "uncommon",
  "description": "The blossoms of this plant give off the same light as a torch during the night. Mages have cultivated varieties for many different climates. DC: 20.",
  "harvesting": "",
  "effects": [
   "DC 20"
  ]
 },
 {
  "id": "goblin-rouge",
  "name": "Goblin Rouge",
  "kind": "herb",
  "tier": "common",
  "description": "Juice of the berries can be used to make a waterproof ink that cannot be smeared or affected by the elements. DC 10.",
  "harvesting": "",
  "effects": [
   "DC 10"
  ]
 },
 {
  "id": "goblinvine",
  "name": "Goblinvine",
  "kind": "herb",
  "tier": "common",
  "description": "The leaves of this invasive creeper produce oil that irritates the skin, causing red, itchy splotches to cover the affected area.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "golden-embrace",
  "name": "Golden Embrace",
  "kind": "poison",
  "tier": "rare",
  "description": "(from the stem; Contact DC 22; primary damage 1 Con; secondary damage 1 Con per hour until death; cost 300 gp)",
  "harvesting": "",
  "effects": [
   "DC 22"
  ]
 },
 {
  "id": "golden-maple-leaves",
  "name": "Golden Maple Leaves",
  "kind": "herb",
  "tier": "uncommon",
  "description": "These potent additives can only be culled from a rare maple tree known to grow exclusively in urban areas. These small, elaborately twisting trees are extremely slow to grow and mature—the leaves reach maturity only once every 3 years—and they are almost always grown and cultivated by half-elves. Additionally, half-elves are keenly aware of the effort put into the leaves’ growth and normally only sell the products of their labors to others of their kind. When the golden maple’s delicate, five-pointed leaves finally take on their namesake’s color, they can be cut, dried, and then ground into a fine powder, a process that requires a DC 15 Knowledge (nature) or Profession (herbalist) check. When used in conjunction with the Craft (alchemy) skill to create special substances and items like alchemical grease or tanglefoot bags, golden maple leaves reduce the Craft DC by 5 and add +1 to the DC of any save required by the alchemical item. A single dose of golden maple leaf powder is sufficient to augment the crafting of three alchemical items.",
  "harvesting": "",
  "effects": [
   "DC 15"
  ]
 },
 {
  "id": "goldencup",
  "name": "Goldencup",
  "kind": "herb",
  "tier": "rare",
  "description": "Oily yellow moss that gives a euphoria that strengthens resolve, often used by natives before combat. When chewed for one minute it gives a +2 alchemical bonus on saves vs. fear and compulsion effects for 30 minutes. When in combat, the user must make a DC 10 Will save or suffer the confusion effect as the spell for the duration. DC: 25.",
  "harvesting": "",
  "effects": [
   "+2 saves vs fear and compulsion effects for 30 minutes",
   "DC 10",
   "Causes confused"
  ]
 },
 {
  "id": "goldenrod",
  "name": "Goldenrod",
  "kind": "herb",
  "tier": "common",
  "description": "Leaves mashed into a poultice to stop bleeding and cure poison.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "grave-mold",
  "name": "Grave Mold",
  "kind": "fungus",
  "tier": "uncommon",
  "description": "Small doses help fight disease and infection. Prepared by an herbalist, a consumed ounce of the mold will give a +3 Fortitude save bonus against all disease for 6 days. Grave mold growing on a corpse can produce a simulacrum due to its highly psionic nature; the simulacrum must stay within 120 feet of the generating corpse.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "griffon-talon",
  "name": "Griffon Talon",
  "kind": "monster part",
  "tier": "rare",
  "description": "When ground into a powder and mixed with oil, the talon creates a salve that grants a +2 bonus to attack rolls with melee weapons for 2 hours, but the user’s grip stiffens, imposing a –2 penalty to dexterity-based skill checks.",
  "harvesting": "Talons must be severed with a heavy chisel and hammer after the griffon is subdued, requiring strength to avoid damaging the talon’s core.",
  "effects": [
   "+2 Attack rolls with melee weapons for 2 hours"
  ]
 },
 {
  "id": "halfling-thistle",
  "name": "Halfling Thistle",
  "kind": "herb",
  "tier": "common",
  "description": "Used to make shinewater, a rust remover and polisher. One dose will de-rust a medium sized metal weapon. DC: 5.",
  "harvesting": "",
  "effects": [
   "DC 5"
  ]
 },
 {
  "id": "harpy-vocal-cord",
  "name": "Harpy Vocal Cord",
  "kind": "monster part",
  "tier": "uncommon",
  "description": "When boiled into a tea and consumed, the cord grants the ability to cast a charm person spell (DC 15) once within 4 hours, but the user’s voice cracks, imposing a –2 penalty to diplomacy checks for 24 hours.",
  "harvesting": "The cord is delicately cut with a sharp blade after the harpy’s death, requiring precision to avoid damaging its magical properties.",
  "effects": [
   "-2 Diplomacy for 24 hours",
   "DC 15"
  ]
 },
 {
  "id": "hawthorn",
  "name": "Hawthorn",
  "kind": "herb",
  "tier": "common",
  "description": "While lots of myths surround the use of the hawthorn tree's wood, there is one interesting use: sprinkling the pollen from its blossoms into the eyes allows anyone to see faeries and fey creatures, despite any invisibility on their part, for up to an hour.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "heart-fire",
  "name": "Heart Fire",
  "kind": "poison",
  "tier": "rare",
  "description": "(distilled from the seeds; Contact DC 20; primary damage 2d6 Con; secondary 1 permanent Con; cost 500 gp)",
  "harvesting": "",
  "effects": [
   "DC 20"
  ]
 },
 {
  "id": "hemlock",
  "name": "Hemlock",
  "kind": "herb",
  "tier": "common",
  "description": "The seeds can be made into a soporific tincture. If injected, the affected creature must make a Fortitude DC 15 or sleep for three hours. This can be made into a tea that makes the sleep last for five hours. Sometimes this is used as an anesthetic during primitive surgery. Can be used topically against inflammations; grants a +1 Heal skill bonus when used to treat skin-affecting diseases and infections. In small doses hemlock can relax muscles, in large enough doses complete paralysis can result, resulting in asphyxiation when the lungs stop working. Those eating raw hemlock must make a DC 15 Fortitude save or become paralyzed, subsequent damage is determined by suffocation rules until cured with spells or counteracted by a healer using a stimulant.",
  "harvesting": "",
  "effects": [
   "Fortitude DC 15",
   "Causes paralyzed"
  ]
 },
 {
  "id": "henbane",
  "name": "Henbane",
  "kind": "herb",
  "tier": "common",
  "description": "Potent painkiller. Poisonous if taken internally. Boil leaves, seeds or roots in water and apply as a poultice. Will restore 1-6 hit points to a wounded character in a manner similar to Aaron's rod, but only 1-4 of those will \"wear off\" two hours later when the pain returns. So effective as a painkiller, if you fight while under the effects of henbane you will fight as though moderately intoxicated due to numbing. Can be used daily when recovering from a fever, returning one point of strength and constitution per day. Treat as poison if eaten or drunk, when boiling there is a 40% chance that inhaling will cause hallucinations.",
  "harvesting": "",
  "effects": [
   "Heals 1-6 hit points"
  ]
 },
 {
  "id": "henna",
  "name": "Henna",
  "kind": "herb",
  "tier": "common",
  "description": "Mostly used to make a pigment used in tattoos, it is magically reactive and can be used to make several of the magic concoctions and verdexes mentioned in the book.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "herb-true-love",
  "name": "Herb True-Love",
  "kind": "herb",
  "tier": "common",
  "description": "Antidote for poisons and an antiseptic. Eating three berries or making a tea from the leaves will add +2 save vs. poison, +3 for halflings or dwarves, if taken within two rounds of the suspected poisoning. As a wound wash it can be used once per injury to restore a single hit point.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "horsetail",
  "name": "Horsetail",
  "kind": "herb",
  "tier": "common",
  "description": "Leaves powdered and sprinkled on something to ritually purify it.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "hrondis-tears",
  "name": "Hrondis' Tears",
  "kind": "herb",
  "tier": "common",
  "description": "These small blue bell-shaped flowers grow in open fields with plenty of sun. Their properties are known only to a few, due to the specificity of their use. If a strand of Hrondis' Tears are wrapped around the hilt of a weapon, that weapon can be used to strike incorporeal undead as if it were a magic weapon. Hrondis' Tears can last for up to a week and still confer this property.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "hydra-gall",
  "name": "Hydra Gall",
  "kind": "monster part",
  "tier": "exotic",
  "description": "When distilled and drunk, Hydra Gall allows the user to regrow minor wounds, healing 1d4 HP per round for 5 rounds, but causes nausea, imposing a –3 penalty to constitution-based checks for 1 hour.",
  "harvesting": "The gall bladder must be carefully excised with a silver scalpel after slaying the hydra, avoiding rupture to prevent acidic burns.",
  "effects": [
   "-3 Constitution for 1 hour",
   "Heals 1d4 hit points",
   "Causes nauseated"
  ]
 },
 {
  "id": "hypericum",
  "name": "Hypericum",
  "kind": "herb",
  "tier": "common",
  "description": "Leaves and flowers crushed and powdered, sprinkled on a place or person to help with exorcisms and summonings.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "ice-lotus",
  "name": "Ice Lotus",
  "kind": "herb",
  "tier": "exotic",
  "description": "Key ingredient in icewalker oil. The substance gives the equivalent to spider climb when walking on ice or snow. Lasts for 10 minutes. DC: 35.",
  "harvesting": "",
  "effects": [
   "DC 35"
  ]
 },
 {
  "id": "imperial-willow",
  "name": "Imperial Willow",
  "kind": "herb",
  "tier": "common",
  "description": "The bark is used to relieve pain. Can be brewed into a bland tea that cures 4 points of subdual damage. Can also be prepared to relieve infection; giving a +7 Fortitude save bonus against skin disease for a number of days equal to the imbiber's Constitution score. Imperial willow heartwood enhances certain magical effects, such as granting a dryad the ability to teleport without error when they step into the tree. A druid casting a spell within 30 feet can make a DC 20 Will save in order to have their spell augmented with the Enlarge Spell feat. A bard within 10 feet can bolster a song or chant by making a DC 25 Will save; success gains a +4 Perform skill bonus for the song's duration.",
  "harvesting": "",
  "effects": [
   "Heals 4 non-lethal damage",
   "DC 20"
  ]
 },
 {
  "id": "ironbark-moss",
  "name": "Ironbark Moss",
  "kind": "fungus",
  "tier": "common",
  "description": "A tough, gray-green moss that clings to ancient trees in primal forests, resembling cracked iron. When chewed, Ironbark Moss hardens the user’s skin, granting a +2 natural armor bonus for 2 hours. The stiffness of the effect reduces movement speed by 10 feet for the duration.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "juniper",
  "name": "Juniper",
  "kind": "herb",
  "tier": "common",
  "description": "Juniper berries are often prescribed as an immediate and sometimes helpful poison antidote (Fort save at +2 only against herbal poisons).",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "juniper-berry",
  "name": "Juniper Berry",
  "kind": "herb",
  "tier": "common",
  "description": "Less effective poison curative than herb true-love. Also a stimulant for the injured, as eating two berries helps fight off shock. If unconscious with zero or fewer hit points, the berries will add 1-4 hit points possibly restoring the character to consciousness. Character restored in this manner cannot fight or exert himself until he has rested to regain as many hit points as the herb artificially returned to him . If eaten to counter poison, add +1 to save if eaten with two rounds of poisoning.",
  "harvesting": "",
  "effects": [
   "Causes unconscious"
  ]
 },
 {
  "id": "kraken-ink",
  "name": "Kraken Ink",
  "kind": "monster part",
  "tier": "legendary",
  "description": "When concentrated and used to inscribe runes, the ink allows the user to breathe underwater for 8 hours, but their skin takes on a faint inky hue, imposing a –2 penalty to charisma-based checks.",
  "harvesting": "The sac must be carefully punctured and drained with a hollow needle after subduing the kraken, avoiding its acidic blood.",
  "effects": [
   "-2 Charisma for 8 hours"
  ]
 },
 {
  "id": "lakeleaf",
  "name": "Lakeleaf",
  "kind": "herb",
  "tier": "uncommon",
  "description": "This parsleylike herb originated along the banks of the River Oceanus. When rubbed into meat, it prevents the meat from ever drying out even when overcooked. Using a sprig from the plant when casting gentle repose doubles the spell's duration (does not stack with the Extend feat). DC: 15.",
  "harvesting": "",
  "effects": [
   "DC 15"
  ]
 },
 {
  "id": "leechwort",
  "name": "Leechwort",
  "kind": "herb",
  "tier": "common",
  "description": "When dried and ground into a powder, the mottled red and gray bark of this shrub is a boon to healers. When applied to a wound, leechwort grants a +1 alchemical bonus on all Heal checks and a +2 alchemical bonus on Heal checks to staunch bleeding. One pound of leechwort is enough for 10 uses.",
  "harvesting": "",
  "effects": [
   "+1 Heal",
   "+2 Heal to staunch bleeding"
  ]
 },
 {
  "id": "levisticum",
  "name": "Levisticum",
  "kind": "herb",
  "tier": "common",
  "description": "Leaves brewed into a \"love\" (lust) potion.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "lish-nut",
  "name": "Lish Nut",
  "kind": "herb",
  "tier": "common",
  "description": "Very nutritious, a handful can provide a day's sustenance. Vermin dislike the smell. For two hours after eating a nut (a full round action), the consumer emits the nut's odor, forcing attacking vermin to make a DC 11 Will save or become sickened for 2d4 round after touching the character. DC: 10.",
  "harvesting": "",
  "effects": [
   "DC 11",
   "Causes sickened"
  ]
 },
 {
  "id": "mad-cap",
  "name": "Mad Cap",
  "kind": "fungus",
  "tier": "common",
  "description": "These red mushrooms are less poisonous than the death cap but they also produce a strong psychoactive effect which can lead someone to fall into a berserk rage, lashing out at anyone nearby. After the rage subsides, the poisoned person collapses in exhaustion then slips into a coma. These mushrooms are an ingested poison, DC 18 the immediate effects are fall under the effects of a rage spell like effect for 1d10 rounds. Anyone failing the save by 5 or more also suffer from the effects of a confusion spell for the same duration of the rage effect. A secondary effect occurs after the spell like effects wear off, this is unconsciousness.",
  "harvesting": "",
  "effects": [
   "DC 18",
   "Causes exhausted",
   "Causes unconscious",
   "Causes confused"
  ]
 },
 {
  "id": "mallow",
  "name": "Mallow",
  "kind": "herb",
  "tier": "common",
  "description": "Shoots brewed into an anti-love/lust potion.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "mandrake",
  "name": "Mandrake",
  "kind": "herb",
  "tier": "common",
  "description": "Has pain relieving properties. The root, boiled in a tea or a small bit chewed, acts as an anesthetic and removes pain by sedating the imbiber (Fort Save or sleep for 1d4 hours). An apothecary should prepare it for use, otherwise the treatment acts as a poison (DC 17; primary Unconsciousness and Sleep 1d8 hours; secondary 1d2 Con).////when the leaves are chewed or rubbed on the skin it heals 2 points of subdual damage, usable once per 12 hours. A stronger version may be prepared that will heal 4 points per 6 hour period. Mandrake can have a soporific effect, chewing more ounces than half your Con score will require a DC 25 Fortitude save to avoid experiencing delirium lasting 2d4 hours. Another valuable trait of the plant is that a tea concoction can be made from it that will induce sleep for 2 hours. Country doctors will use this to anesthetize patients before rudimentary surgeries. Finally, the strongest chemical in mandrake is its toxin. Taking too much, or giving a large dose, requires a DC 25 Fortitude save or the character will enter a permanent coma, typically leading to death.",
  "harvesting": "",
  "effects": [
   "Heals 2 non-lethal damage",
   "DC 17",
   "Causes unconscious"
  ]
 },
 {
  "id": "manticore-spine",
  "name": "Manticore Spine",
  "kind": "monster part",
  "tier": "rare",
  "description": "When boiled into a tincture and applied to ammunition, the spines cause paralyzing pain, imposing a –4 penalty to attack rolls on struck targets for 1 minute, but the user risks a mild sting (DC 12 fortitude save) if mishandled, causing –2 dexterity for 1 hour.",
  "harvesting": "Spines must be carefully extracted with thick leather gloves and a steel forceps within minutes of the manticore’s death to avoid venom degradation.",
  "effects": [
   "-4 Attack rolls on struck targets for 1 minute",
   "DC 12"
  ]
 },
 {
  "id": "marsh-mallow",
  "name": "Marsh-Mallow",
  "kind": "herb",
  "tier": "common",
  "description": "Used to treat burns or help with recovery from blood loss. Root should be mashed, boiled in water, and bound to wound; this will give a character 2 hit points per day while recovering, for the first three days. Boiled remains of root can be drunk to counter the effects of blood loss; regaining 1-3 points per day instead of the usual one hit point.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "meadow-giant",
  "name": "Meadow Giant",
  "kind": "herb",
  "tier": "uncommon",
  "description": "Powered stem makes a substance called White Sanguine that prevents clotting; it is typically smeared along with a poison onto bladed weapons. If victim fails initial Fortitude save against the poison, the wound continues to bleed for one minute, inflicting 1 point of damage per round in blood loss. Bleeding can be stopped with a DC 15 Heal check. Can only be added to injury poisons. DC: 20.",
  "harvesting": "",
  "effects": [
   "DC 15"
  ]
 },
 {
  "id": "menhirite",
  "name": "Menhirite",
  "kind": "herb",
  "tier": "uncommon",
  "description": "Found naturally on the Elemental Plane of Earth, they can appear elsewhere in tall, rock-like rings where a king or queen has been interred in the ground. The plants are often guarded by a group of ghouls and wights; often they are non-aggressive, attacking only those who seek to harm the plants. Thought to be a gift from the gods, a menhirite ring is often considered holy ground by commoners, who will sometimes brave going near to place one of their dead within the ring. This is unpredictable, sometimes returning the person to life, sometimes raising them as an undead, but more commonly doing nothing (5% chance per month of resurrecting, after a year it rises as if create undead was cast on it.) Uses of the plant include promoting blood clotting, making wounds heal faster. An ounce of sap will instantly heal 6 hit points and stops bleeding as it closes the wound. Pieces of the plant, placed on a dead body, will slow the rate of decay by half.",
  "harvesting": "",
  "effects": [
   "Heals 6 hit points",
   "Causes dead"
  ]
 },
 {
  "id": "mind-hammer",
  "name": "Mind Hammer",
  "kind": "poison",
  "tier": "rare",
  "description": "(from the leaves; Contact DC 20; primary damage 1d4 permanent Int; secondary damage 1d4 permanent Con; cost 150 gp)",
  "harvesting": "",
  "effects": [
   "DC 20"
  ]
 },
 {
  "id": "mistletoe",
  "name": "Mistletoe",
  "kind": "herb",
  "tier": "common",
  "description": "A parasitic bush that grows on trees, it is most famous for being revered by druids, due to it appearing to grow out of nowhere and never touching the ground. The berries stimulate the immune system in response to cancers and wild growths. Drinking an extract grants a +3 bonus to all saves against any transformation process, whether natural like cancers, or supernatural like polymorph other. This can be used once per day. Unless this trait is separated by a herbalist, using mistletoe in this manner subjects the user to a more hazardous trait: it can cause agitation and contractions in the abdominal region, including the uterus in women. In pregnant women, this can be fatal for both fetus and mother. If a female eats more than a few berries they must make a DC 19 Fortitude save or take 1d4 Constitution damage and 1d8 damage from bleeding. A successful save results in half damage. In either case, any pregnancy is aborted. Men affected by the toxin must make a DC 12 Fortitude save to avoid 1 point of Con damage due to spasms; a critical failure adds 1d4 damage from internal bleeding.",
  "harvesting": "",
  "effects": [
   "+3 saves against any transformation process, whether…",
   "1d4 Constitution damage",
   "1 Constitution damage",
   "DC 19"
  ]
 },
 {
  "id": "mistveil-fern",
  "name": "Mistveil Fern",
  "kind": "herb",
  "tier": "common",
  "description": "This pale, translucent fern resembles wisps of fog and grows in damp, shadowy caves. Inhaling the spores of Mistveil Fern grants the ability to become partially incorporeal for 10 minutes, allowing the user to pass through thin barriers (up to 1 inch thick), but they take a –3 penalty to physical damage dealt due to their reduced solidity.",
  "harvesting": "",
  "effects": [
   "-3 physical damage dealt due to their reduced solidity for 10 minutes"
  ]
 },
 {
  "id": "monkshood",
  "name": "Monkshood",
  "kind": "herb",
  "tier": "common",
  "description": "Juice smeared on a weapon as a poison.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "musk-muddle",
  "name": "Musk Muddle",
  "kind": "herb",
  "tier": "common",
  "description": "Boiled leaves used to make a burn salve. Heals 1d6 points of fire damage if applied within two rounds of injury. DC: 10.",
  "harvesting": "",
  "effects": [
   "Heals 1d6 hit points",
   "DC 10"
  ]
 },
 {
  "id": "myrtle",
  "name": "Myrtle",
  "kind": "herb",
  "tier": "common",
  "description": "Leaves brewed into a love potion.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "nahre-lotus",
  "name": "Nahre Lotus",
  "kind": "herb",
  "tier": "common",
  "description": "These valuable lilies reach into the Elemental Plane of Water and draw fluid across the planes to flow out of their blossoms. Often grown in oases, a properly cultivated lotus can produce 50 gallons of pure, sweet water per day. A dead lotus kept in water can be used as a poisonous blight against other plants (used as a grenadelike weapon, contact; Fort DC 12; initial damage death, secondary 2d6 Con damage).",
  "harvesting": "",
  "effects": [
   "2d6 Constitution damage",
   "Fortitude DC 12",
   "Causes dead"
  ]
 },
 {
  "id": "nightshade",
  "name": "Nightshade",
  "kind": "herb",
  "tier": "common",
  "description": "The powerful nightshade is associated with witches, along with mandrake and hemlock. Extremely toxic, the lower parts of the plant are the most poisonous: the roots are strongest, the stem and leaves less powerful, and the berries are the most harmless. Except for small children, the fruit can be eaten in small amounts; gnomes are immune completely and often make the berries into jam. Small amounts relax muscles and increase blood flow which healers can use to treat such problems as muscle spasms, epilepsy and acute bouts of coughing (make a DC 18 Fort save or become lethargic, suffering a -2 circumstance penalty to all actions - any d20 roll- for 30 minutes). Used as a poison, swallowing more than an ounce requires a DC 18 Fort save to avoid taking 1d6 Con damage. The damage is accompanied by a delirium described as a \"sense of flying\". This is thought to be the origin of stories about witches being able to fly. A concoction can be made to use its ability to relax the nervous system; such an extract grants a +4 bonus to all Reflex saves for nine hours. More than one dose at a time requires a DC 18 Fort save to avoid becoming paralyzed completely (rules for slow suffocation apply after 10 minutes as the lungs stop working). Paralysis wears off in 60 minutes minus one minute per Constitution point. A trained Herbalist can make the poison deadly nightshade using extracts of the plant- Type: Ingested DC 25, Primary damage: 1d6 Con per round for 3 rounds; Secondary damage: 1d4 Wis per round for 3 rounds; cost: 2,940 gp.",
  "harvesting": "",
  "effects": [
   "-2 actions - any d20 roll- for 30 minutes",
   "+4 Reflex for nine hours",
   "1d6 Constitution damage",
   "DC 18",
   "Causes paralyzed"
  ]
 },
 {
  "id": "nura-stalk",
  "name": "Nura Stalk",
  "kind": "herb",
  "tier": "common",
  "description": "This plant is common in temperate forests. It has a thick stalk, nearly an inch in diameter. When this stalk is broken, the broken ends exude a white sap. This sap has the property that it stops bleeding when applied to open wounds. A little-known effect is that if used within a round of an attack that damages/drains Constitution via blood loss (dire weasels, vampires, etc), it can actually prevent one full point of Con loss from the attack. In other circumstances, it simply heals 1d4 points of damage (so long as that damage was caused by a wound and not e.g. negative energy, cold, etc). Nura sap loses its potency within a matter of hours once exposed to air, but the stalks can be kept for about a week if the bases are kept covered with wet cloth. The sap can be preserved by combining it with soft wax without allowing its temperature to exceed 110F at any point in the process.",
  "harvesting": "",
  "effects": [
   "Heals 1d4 hit points"
  ]
 },
 {
  "id": "oak",
  "name": "Oak",
  "kind": "herb",
  "tier": "common",
  "description": "An astringent oil can be made from the leaves that makes skin contract; used to seal wounds, it can heal 1 point of damage, but only once per wound. Bark can be processed by a Herbalist to make topical treatment used for preventing infections. Used as a poultice it gives a character with the Heal skill a bonus of +4 to his skill check when attempting to treat freshly inflicted wounds. Midwives will use this in childbirth to prevent infection.",
  "harvesting": "",
  "effects": [
   "Heals 1 hit points"
  ]
 },
 {
  "id": "old-man-s-friend",
  "name": "Old Man's Friend",
  "kind": "herb",
  "tier": "uncommon",
  "description": "Herb can be crushed and combined to make a thick paste called gash glue. Often carried by soldiers to seal a fallen companion's wounds, one application stabilizes a dying creature. DC: 20.",
  "harvesting": "",
  "effects": [
   "DC 20",
   "Causes dying"
  ]
 },
 {
  "id": "orevine",
  "name": "Orevine",
  "kind": "herb",
  "tier": "exotic",
  "description": "Modified from a version originating on the Elemental Plane of Earth, this plant sends roots through soil and stone to find specific metals. There are several varieties, each keyed to a different metal and having various ways of extracting the metal from the plant. Once per a month a DC 20 Knowledge (nature) check can be made to extract metal, and the plant will exhaust all traces within 100 foot of planting within 3d6 months. Plants keyed to copper or iron produce 400 gp worth of metal per month, silver or gold varieties produce 1,000 gp of metal a month, and one keyed to platinum, mithral or adamantium produce 2,000 gp of metal per month. Purchase price for a plant is roughly five times its per month value. DC: 30.",
  "harvesting": "",
  "effects": [
   "DC 20"
  ]
 },
 {
  "id": "orticusp",
  "name": "Orticusp",
  "kind": "herb",
  "tier": "exotic",
  "description": "Makes \"night venom\"; pulped and mixed with a poison, it adds an additional effect. If a victim fails the initial Fortitude save against an enhanced poison they must make another save at the same DC to avoid falling into a slumber until the poison's secondary effect sets in. Affected characters may be awoken normally. DC: 35.",
  "harvesting": "",
  "effects": [
   "DC 35"
  ]
 },
 {
  "id": "pennyroyal",
  "name": "Pennyroyal",
  "kind": "herb",
  "tier": "common",
  "description": "Leaves brewed into an abortificant.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "phoenix-feather",
  "name": "Phoenix Feather",
  "kind": "monster part",
  "tier": "legendary",
  "description": "When burned and inhaled as ash, the feather grants immunity to fire damage for 2 hours, but the user becomes feverish, taking a –3 penalty to concentration-based checks.",
  "harvesting": "Feathers must be collected from the phoenix’s nest during its fiery rebirth, using heat-resistant tongs to avoid burns.",
  "effects": [
   "-3 concentration-based checks for 2 hours",
   "Immune to fire damage for 2 hours"
  ]
 },
 {
  "id": "pomegranate",
  "name": "Pomegranate",
  "kind": "herb",
  "tier": "common",
  "description": "The leaves have antibacterial properties; when crushed and applied to wounds they give a +5 Heal skill bonus. It can be prepared by an herbalist into a form that gives a +10 bonus. The bark is a strong purgative, when consumed it forces a creature to vomit and evacuate its bowels in 1d10 rounds after consuming. There is no save for this. Healers sometimes use it this way to rid a patient of worms or other intestinal disorder. The juice from the pomegranate's fruit can treat such things as dysentery and fever as it reduces body temperature slightly. When drunk it provides a +2 bonus to Fortitude saves to resist extreme heat and hot conditions for one hour. When made into a concoction, it gives a +4 bonus for one day.",
  "harvesting": "",
  "effects": [
   "+2 Fortitude to resist extreme heat and hot…"
  ]
 },
 {
  "id": "poppy-log",
  "name": "Poppy Log",
  "kind": "consumable",
  "tier": "common",
  "description": "",
  "harvesting": "",
  "effects": [
   "+10 Strength (permanent)",
   "+10 Dexterity (permanent)",
   "Causes unconscious for 1d100 hours"
  ]
 },
 {
  "id": "poppy-tears",
  "name": "Poppy Tears",
  "kind": "herb",
  "tier": "common",
  "description": "The milk of this vibrant green cactus, when mixed with resins and other ingredients, congeals into sticky, black chunks with an exceedingly sour taste. Though poppy tears comes in several different varieties, it’s refined form is both the most potent and expensive type.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "prickly-tea",
  "name": "Prickly Tea",
  "kind": "herb",
  "tier": "rare",
  "description": "The regular version of prickly tea can be distilled into a substance called Senses. It sharpens the imbiber's eyes and ears for one hour, granting a +1 alchemical bonus to Spot and Listen checks. DC: 25.",
  "harvesting": "",
  "effects": [
   "+1 Spot and Listen checks",
   "DC 25"
  ]
 },
 {
  "id": "rowan",
  "name": "Rowan",
  "kind": "herb",
  "tier": "common",
  "description": "The wood of this small tree, while having no common uses, has a special one- it naturally protects against magic. Used in such items as staves and shields, rowan wood always gets a Fortitude saving throw against magic, even if not enchanted or treated, and has a 50% chance of naturally boosting an enchantment by +1 when created.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "rue",
  "name": "Rue",
  "kind": "herb",
  "tier": "common",
  "description": "Leaves brewed into a potion that grants second sight (ability to see spirits or magic).",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "salamander-ember-gland",
  "name": "Salamander Ember Gland",
  "kind": "monster part",
  "tier": "uncommon",
  "description": "When crushed and mixed with water, the gland creates a potion that allows the user to emit a burst of flame (1d6 fire damage, 10-ft. radius) once within 1 hour, but they take 1d4 fire damage from residual heat.",
  "harvesting": "The gland is removed with fire-resistant tongs after the salamander is incapacitated, requiring care to avoid burns.",
  "effects": [
   "1d6 fire damage",
   "1d4 fire damage"
  ]
 },
 {
  "id": "salamander-orchids",
  "name": "Salamander Orchids",
  "kind": "herb",
  "tier": "rare",
  "description": "These plants are seemingly made from brass and produce a smokeless flame drawn from the Elemental Plane of Fire. The light is equivalent to light and heat produced by a torch. Touching the plant without hand protection does 1d6 fire damage each round. When used in the crafting of a flaming or flame burst weapon, the cost is reduced by 500 gp and 100 XP. Cultivating the plant requires feeding it 25 gp of oil per month. DC:30.",
  "harvesting": "",
  "effects": [
   "1d6 fire damage",
   "DC 30"
  ]
 },
 {
  "id": "sand-vine",
  "name": "Sand Vine",
  "kind": "herb",
  "tier": "uncommon",
  "description": "Juice can be combined with common ingredients to make an anesthetic called vine oil. When spread on skin it numbs pain letting the user function when reduced below -5 hit points. This does not stop the normal loss of one hit point per round when a character is reduced to zero or less hit points. Last for hour after application, and can only be used once every 24 hours. DC: 15.",
  "harvesting": "",
  "effects": [
   "DC 15"
  ]
 },
 {
  "id": "scorpion",
  "name": "Scorpion",
  "kind": "herb",
  "tier": "common",
  "description": "Body powdered and brewed into a potion to ward against poison and cure poison.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "sealwort",
  "name": "Sealwort",
  "kind": "herb",
  "tier": "common",
  "description": "Roots prepared as a poultice to heal incapacitated limbs.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "selpeme-blossom",
  "name": "Selpeme Blossom",
  "kind": "herb",
  "tier": "common",
  "description": "This florid red/purple blossom is an orchid that grows on jungle vines. When the petals are rubbed on the skin, the user develops an odor that causes fear in animals. Any creature with the [Animal] type suffers a -4 to-hit penalty against the user. Selpeme's effects last for 8 hours. It is only good fresh and keeps for about two days after being harvested. However, if the blossom's fragrance is distilled into a tincture with the right solvents, it creates a perfume that can keep indefinitely though only providing a -2 to-hit.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "shadowvine",
  "name": "Shadowvine",
  "kind": "herb",
  "tier": "common",
  "description": "A creeping, black vine with small, heart-shaped leaves that seem to absorb light, found in cursed forests. When ingested, Shadowvine allows the user to blend into shadows, granting a +5 bonus to stealth checks for 3 hours. However, exposure to direct sunlight during this time causes 1d4 damage per round.",
  "harvesting": "",
  "effects": [
   "+5 Stealth for 3 hours"
  ]
 },
 {
  "id": "sherpa-s-friend",
  "name": "Sherpa's Friend",
  "kind": "herb",
  "tier": "common",
  "description": "This small green plant grows in temperate lowlands, which is somewhat ironic given its use. A dose of Sherpa's Friend makes one immune to altitude sickness for 4 hours. It can be dried, in which form it keeps for about a year",
  "harvesting": "",
  "effects": [
   "Ends sickened"
  ]
 },
 {
  "id": "skull-orchid",
  "name": "Skull Orchid",
  "kind": "herb",
  "tier": "common",
  "description": "Highly dangerous to even touch, the skull orchid produces three different poisons, each of which can be extracted by an herbalist from a different part of the plant. Toxin from the leaves targets the brain, causing a cerebral aneurysm. Touching a leaf requires making a DC 17 Fort save to avoid taking 1d4 temporary Intelligence damage and 1d4 temporary Constitution damage. On a critical save failure, the Int damage is permanent. Toxin from the stem shuts down the liver; touching it requires a DC 16 Fort save or the creature loses one Constitution point per hour until cured or dead. The third toxin, obtained from the seeds, targets the heart, forcing it to beat rapidly until it ruptures; touching them will cause 2d6 temporary Con damage and one point of permanent Con damage. Once picked the orchid quickly becomes safe to handle as the toxins are neutralized. If prepared quickly while fresh, several poisons can be made:",
  "harvesting": "",
  "effects": [
   "1d4 Intelligence damage",
   "1d4 Constitution damage",
   "2d6 Constitution damage",
   "DC 17",
   "Ends dead"
  ]
 },
 {
  "id": "sphagnum-moss",
  "name": "Sphagnum Moss",
  "kind": "fungus",
  "tier": "common",
  "description": "When sterilized, it makes an effective dressing for wounds. When cleaned and dried, can be bound to wounds; character will heal 25% more quickly (four hit points returned every three days of rest.) Moss must be replaced every three days of use.",
  "harvesting": "",
  "effects": [
   "Character will heal 25% more"
  ]
 },
 {
  "id": "sphinx-whisker",
  "name": "Sphinx Whisker",
  "kind": "monster part",
  "tier": "exotic",
  "description": "When burned and the smoke inhaled, the whisker grants a +4 bonus to intelligence-based checks for 3 hours, but the user becomes overly analytical, taking a –2 penalty to charisma-based interactions.",
  "harvesting": "Whiskers must be plucked with a silver tweezers during a sphinx’s slumber or after death, requiring stealth to avoid its riddling wrath.",
  "effects": [
   "+4 Intelligence for 3 hours"
  ]
 },
 {
  "id": "spriggan-tree",
  "name": "Spriggan Tree",
  "kind": "herb",
  "tier": "common",
  "description": "The spriggan tree gets its name from its unusual life cycle; for half its life it grows upwards as a normal tree, then mysteriously begins \"un-growing\", shrinking until it vanishes back into the ground. The acorns can be used to take advantage of the tree's natural magic to make cheap versions of potions of enlarging and growing equal to a caster level of 5. A trained Herbalist can make one for 22 gp. At the DM's discretion, the effects can be permanent until dispelled or an acorn of the opposite effect is eaten. The bark can be boiled into a tea that kills internal parasites such as tapeworm and blood flukes. Once the tea it taken, making a DC 15 Fort save will kill any in the body and flush them away.",
  "harvesting": "",
  "effects": [
   "DC 15"
  ]
 },
 {
  "id": "st-john-s-wort",
  "name": "St. John's-Wort",
  "kind": "herb",
  "tier": "common",
  "description": "Boil a dozen in wine to make a tincture for wound treatment; it helps close wounds and heal bruises. If immediately applied to a wound, return 1-4 points as having \"never been lost\". Powdered seeds drunk in a broth will add +1 to save vs. poison if taken within two rounds of poisoning.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "starbloom",
  "name": "Starbloom",
  "kind": "herb",
  "tier": "common",
  "description": "These delicate, star-shaped flowers glow faintly with a silver-blue hue, found only in moonlit glades. Their petals shimmer like liquid starlight. When brewed into a tea, Starbloom grants the drinker enhanced night vision for 6 hours, allowing them to see clearly in complete darkness, but they become hypersensitive to bright light, taking a –4 penalty on checks in bright environments.",
  "harvesting": "",
  "effects": [
   "-4 checks in bright environments for 6 hours"
  ]
 },
 {
  "id": "sukake",
  "name": "Sukake",
  "kind": "herb",
  "tier": "common",
  "description": "The lemon-like fruits produced from this tree can induce hallucinations or a dream-like sleep. If properly prepared priests and other spellcasters can eat a sukake fruit as a free action while casting a divination to make the spell act as if cast with a Maximize Spell feat. However, they also must endure its narcotic effects (as poison DC 13; primary damage 1 point Int and 1 point Wis; secondary damage Sleep 1d4 hours).",
  "harvesting": "",
  "effects": [
   "DC 13"
  ]
 },
 {
  "id": "sweetspire",
  "name": "Sweetspire",
  "kind": "herb",
  "tier": "common",
  "description": "This small tree has many uses. Its sap-filled leaves can be boiled down and fermented to make a sweet, white wine that travels well; its dried leaves and resin are highly flammable and make good torches or fire starters; its sap can be smeared onto skin as a guard against cold as it warms on contact. A little known use is to break open two or more leaves and smear the sap onto skin to provide an immediate Fortitude save against paralysis effects.",
  "harvesting": "",
  "effects": [
   "Causes paralyzed"
  ]
 },
 {
  "id": "tahtoalehti",
  "name": "Tahtoalehti",
  "kind": "herb",
  "tier": "legendary",
  "description": "Also known as Wishfern, this plant is considered the most valuable of all magical plants. It only blooms once every 1d100 years and always on the night of the winter solstice. On that night it produces a single, white, luminous flower. If properly harvested without bruising or damage, requiring a DC 40 Profession (gardener) check, it grants a single wish, equal to that cast as a level 20 sorcerer. Once day arrives, the blossom withers, leaving behind a single new seed. Extremely difficult to grow, it requires an absence of contact and must not be within 100 miles of any other wishfern. DC: 40 (if this check fails, the plant must make a DC Fort save or die, with a +0 bonus).",
  "harvesting": "",
  "effects": [
   "DC 40"
  ]
 },
 {
  "id": "tamarisk",
  "name": "Tamarisk",
  "kind": "herb",
  "tier": "common",
  "description": "Burning this plant produces an effect that is as offensive to any reptilian creature, from snakes to dragons, as garlic is to vampires.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "tereeka-root",
  "name": "Tereeka Root",
  "kind": "herb",
  "tier": "rare",
  "description": "Root removes pain and increases healing rate. Chewing it allows the user to remain conscious to -5 hit points and regain hit point damage while resting as though under the care of a trained healer (2 hit points per level). One dose takes a minute to chew and lasts 12 hours. DC: 30.",
  "harvesting": "",
  "effects": [
   "DC 30"
  ]
 },
 {
  "id": "tobacco",
  "name": "Tobacco",
  "kind": "herb",
  "tier": "common",
  "description": "These crushed and shredded leaves range in color from peppery red to black; users can either smoke or chew them. Tobacco users experience a certain level of calm and are more easily able to shrug off hunger pangs. Tobacco is addictive (Fort DC 10 to resist), and long-term users suffer Constitution damage.",
  "harvesting": "",
  "effects": [
   "Fortitude DC 10"
  ]
 },
 {
  "id": "trollheart-sap",
  "name": "Trollheart Sap",
  "kind": "monster part",
  "tier": "rare",
  "description": "When distilled into a tonic, Trollheart Sap grants fast healing 2 (regain 2 HP per round) for 10 minutes, but the user’s skin becomes coarse, reducing charisma by –2 for 24 hours.",
  "harvesting": "The heart must be cut from a freshly slain troll and drained within 10 minutes, as it hardens rapidly; a sharp blade and heat-resistant gloves are essential.",
  "effects": [
   "Heals 2 hit points",
   "Fast healing 2 for 10 minutes"
  ]
 },
 {
  "id": "tugwort",
  "name": "Tugwort",
  "kind": "herb",
  "tier": "common",
  "description": "This plant grows in alpine environments. It shows only a small stalk above-ground, but its roots go down 2-3 feet into the soil. An infusion of Tugwort causes the skin to toughen and mend with unusual speed, granting 3 points of resistance against slashing damage for 8 hours. Fresh Tugwort can keep for up to a week before losing its potency; when dried, it keeps for about a month.",
  "harvesting": "",
  "effects": [
   "Resist slashing 3 for 8 hours"
  ]
 },
 {
  "id": "twilight-dagger",
  "name": "Twilight Dagger",
  "kind": "herb",
  "tier": "common",
  "description": "Found most often in lands heavily modified by magic, this bulbous cactus is topped with twilight-blue flowers.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "tyrant-s-sword",
  "name": "Tyrant's Sword",
  "kind": "herb",
  "tier": "common",
  "description": "If silver colored parts of the plant are boiled they can be used to make a warm, mushy substance called frost lotion. Heals 1d6 points of cold damage if applied within two rounds of injury. DC: 10.",
  "harvesting": "",
  "effects": [
   "Heals 1d6 hit points",
   "DC 10"
  ]
 },
 {
  "id": "vervain",
  "name": "Vervain",
  "kind": "herb",
  "tier": "common",
  "description": "Dried and burned as an incense, it grants a +1 level bonus to any turning or rebuking undead or other spirits in the area, for one hour.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "visma-paste",
  "name": "Visma Paste",
  "kind": "herb",
  "tier": "uncommon",
  "description": "The boiled leaves are used to treat burns. One application heals 1d3 points nonlethal damage from heat exposure and a +2 alchemical bonus to the next save to resist further environmental heat damage. Lasts one hour. DC: 15.",
  "harvesting": "",
  "effects": [
   "+2 the next save to resist further environmental heat…",
   "DC 15"
  ]
 },
 {
  "id": "wendigo-antler",
  "name": "Wendigo Antler",
  "kind": "monster part",
  "tier": "exotic",
  "description": "When ground into a dust and scattered, the antler creates a chilling aura that repels undead within 30 feet for 1 hour, but the user suffers a –2 penalty to constitution due to the antler’s lingering curse.",
  "harvesting": "The antler must be broken off with a blessed weapon after the wendigo is banished or slain, as it resists mundane tools.",
  "effects": [
   "-2 Constitution due to the antler’s lingering curse for 1 hour"
  ]
 },
 {
  "id": "wild-fireclover",
  "name": "Wild Fireclover",
  "kind": "herb",
  "tier": "rare",
  "description": "Stems can make a mind-clouding poison additive called mindfire. When added to an ingested poison it adds the effect of a -2 alchemical penalty to Will saves if either of the poison saves are failed. In addition, spellcasters affected by it must make a Concentration check (DC 15 + spell level) to cast spells. Effects last one hour. DC: 30.",
  "harvesting": "",
  "effects": [
   "-2 Will if either of the poison are failed",
   "DC 15"
  ]
 },
 {
  "id": "winterbite",
  "name": "Winterbite",
  "kind": "herb",
  "tier": "common",
  "description": "Wolves are often found rubbing their noses in the white-tipped leaves of this wild mint. When held under the nose and crushed, winterbite releases a pungent, sharply sweet odor that clears the sinuses and sharpens the senses. For the next hour, a user of winterbite gains a +2 alchemical bonus on scent-based Perception checks.",
  "harvesting": "",
  "effects": [
   "+2 Perception scent"
  ]
 },
 {
  "id": "wispweed",
  "name": "Wispweed",
  "kind": "herb",
  "tier": "common",
  "description": "A slender, pale-green grass that sways as if alive, found in haunted marshes and glowing faintly at night. Burning Wispweed releases a smoke that allows entities within the smoke to communicate telepathically within 100 feet DC 15 + Wisdom is not an ally. smoke lasts 1 hour unless there are strong winds. The smoke irritates the lungs, causing a weakening effect that compounds every 5min causing a -1 to Constitution (DC15-Constitution Check)durring the same period.",
  "harvesting": "",
  "effects": [
   "DC 15"
  ]
 },
 {
  "id": "wittlewort",
  "name": "Wittlewort",
  "kind": "herb",
  "tier": "uncommon",
  "description": "Dried, treated and powdered, then made into a brew, its use immediately grants creatures under the effects of Enchantment effects another saving throw (unless the effect did not grant an initial save). DC: 15.",
  "harvesting": "",
  "effects": [
   "DC 15"
  ]
 },
 {
  "id": "woad",
  "name": "Woad",
  "kind": "herb",
  "tier": "common",
  "description": "Woad seed oil has an astringent quality that helps to clot blood and seal wounds. The oil must be spread onto the skin in advance of wounding, however. When an oil-covered area takes damage, 1 hit point heals automatically at the beginning of the following round. A coating of oil is effective for one hour and takes affect for each hit taken during that time. The leaves contain a chemical that reduces inflammation. When used in the raw state, the leaves heal 2 points of burn damage; a person may only benefit once per day. If made into a concoction, it provides a +2 Heal skill check bonus when working with burned tissue, in addition to healing 2 points of burn damage. The raw and prepared uses do not stack. The woad tree is most famous for a blue dye that can be made from its leaves; the pigment will stain skin and clothes for weeks and can be used to make permanent tattoos. Some barbarians know the secrets of enchanting such tattoos to increase their rage power.",
  "harvesting": "",
  "effects": [
   "Heals 2 hit points"
  ]
 },
 {
  "id": "wolfsbane",
  "name": "Wolfsbane",
  "kind": "herb",
  "tier": "common",
  "description": "The root of this tall plant with blue flowers is toxic, but herbalists use it in low doses to reduce pain and regulate the heart. Folklore says it can help a victim of lycanthropy throw off the curse.",
  "harvesting": "",
  "effects": []
 },
 {
  "id": "wolfweed",
  "name": "Wolfweed",
  "kind": "herb",
  "tier": "common",
  "description": "Used to make journeyman serum, which provides a +2 alchemical bonus to Constitution checks made to resist subdual damage from making a forced march. DC: 5.",
  "harvesting": "",
  "effects": [
   "+2 Constitution",
   "DC 5"
  ]
 },
 {
  "id": "wordwood",
  "name": "Wordwood",
  "kind": "herb",
  "tier": "common",
  "description": "Can make an infusion that helps expel internal parasites (as poison DC 11; primary Nausea; secondary 1d3 subdual)",
  "harvesting": "",
  "effects": [
   "DC 11",
   "Causes nauseated"
  ]
 },
 {
  "id": "woundwort",
  "name": "Woundwort",
  "kind": "herb",
  "tier": "common",
  "description": "Styptic, staunching blood and helping to coagulate. Good for all wounds, especially deep cuts. If applied within two rounds to an injury, woundwort will stop bleeding and prevent further weakness from blood loss. Bleeding damage is considered 20% less, reflecting damage that \"never took place\"",
  "harvesting": "",
  "effects": [
   "Bleeding damage 20% less"
  ]
 },
 {
  "id": "wyrmfang-venom",
  "name": "Wyrmfang Venom",
  "kind": "monster part",
  "tier": "rare",
  "description": "When concentrated and applied to a weapon, the venom causes an additional 1d8 poison damage for 1 hour, but the user risks poisoning themselves (DC 15 fortitude save) if mishandled during application.",
  "harvesting": "Venom is milked from the fangs of a sedated or dead wyrm using a glass syringe, requiring steady hands to avoid contact, as it burns skin.",
  "effects": [
   "1d8 poison damage",
   "DC 15"
  ]
 },
 {
  "id": "xian-tao",
  "name": "Xian Tao",
  "kind": "herb",
  "tier": "uncommon",
  "description": "Sometimes called the mythical \"Peach Tree of Immortality\", the xian tao is very difficult to find. The species is rare and tends to grow on remote mountaintops; it can grow in very cold and icy regions as the tree emits its own heat out to a 200 foot diameter. Once per lifetime a person may eat a fruit and gain its magical healing benefits. All damage is healed, including lost limbs, lost levels, and mental imbalances. The fruit must be eaten within three hours of being picked. If somehow preserved and brought to civilization, it can be sold for a fortune (up to 100,000 gp, assuming it isn't stolen once word of its existence gets out). If the alchemical and herbal secrets needed can be found, a fruit can be turned into the fabled elixir of immortality which, after a 9 month transformation stage where the user can do nothing, gets exactly what is implied: stops aging, immunity to poison and disease, large bonuses to saving throws (+10), damage resistance 20/+4 and spell resistance 15. The character also gains +4 to Wis and Int, but loses 5 levels due to the altering magic, though they may be regained. This makes the user virtually unkillable, though such a thing is still possible with great effort. The value of this elixir is 375,000 gp, and will certainly gain the creator the attention of everyone.",
  "harvesting": "",
  "effects": [
   "Immune to poison and disease, large bonuses to saving t"
  ]
 },
 {
  "id": "yarow",
  "name": "Yarow",
  "kind": "herb",
  "tier": "common",
  "description": "Leaves prepared in a poultice to heal wounds over several days. Leaves powdered and brewed into a potion to help with reading the future.",
  "harvesting": "",
  "effects": []
 }
]
```
