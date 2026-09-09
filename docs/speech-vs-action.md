# Speech versus action in typed player input

Research record, 2026-09-08. Written before any code changed, per the standing
instruction to search for how a problem was already solved before designing it.

Two measured playtest faults prompted this:

- **A fight opened on a self-description.** The player typed
  `I tell the clerk "I am a monk, I can handle myself in a fight or handle a bunch
  of others."` The battle gate fired, guards lunged, initiative rolled.
- **Speech falls through where action does not.** Lines the player wrote as speech
  came back as the holding line ("The moment holds — nothing new shows itself just
  yet") far more often than physical actions did.

Five traditions were swept in parallel, then a sixth pass fact-checked the
researchers against the primary sources. The critic found three overclaims, which
are corrected in place below; nothing here is repeated from a summary without the
correction attached.

---

## The finding, in one sentence

**Every tradition that has run this problem for more than a few years separates
speech from action at the door, not by classifying what was typed — and once a line
is known to be speech, its content is an opaque payload that is never scanned again
for action words.** No tradition sanctions our current shape, which is a single
free-text channel whose whole raw string, quoted speech included, is scanned for
violence verbs.

---

## What each tradition does

### Parser interactive fiction — a topic is a different kind of value

Inform 7 defines a small fixed family of speech actions — asking it about, telling
it about, answering it that, asking it for — and what follows `about` or `that` is
captured as a value of the kind `topic`, not resolved against anything in the world.
The manual is explicit, and this quote was verified directly:

> "Inform does not try to understand automatically what that text might mean, or to
> relate it to any items, places or values it knows about."
> — Writing with Inform §17.5, the text token

**Critic correction.** The stronger claim, that topic text is never re-matched
against action grammar, is a sound inference from how the parser consumes the line
but is **not stated in the source**. Cite the quote, not the inference.

TADS 3 adds the piece that speaks to our second fault: a `DefaultAskTellTopic`
matched at the lowest possible priority, so an unanticipated topic reaches a
designed in-character non-answer rather than nothing. Inform's side of the same idea
is an enumerated set of named parser errors, each with a guaranteed printed
response. Neither tradition has a path where input produces silence.

### Multiplayer text worlds — the split is the first thing the parser does

LambdaMOO rewrites the line before any verb lookup at all. Verified at the manual:

> "First, the server checks whether or not the first non-blank character in the
> command is one of the following: `"` `:` `;`. If so, that character is replaced by
> the corresponding command below, followed by a space: say emote eval."

Note `;` is eval in LambdaMOO, not semipose; the MUSH family uses it differently.
CircleMUD does the same thing one layer up, mapping `'` to the say handler and `:`
to emote in its command table, and printing `Huh?!?` when nothing matches. In every
system of this family the rest of the line after a speech verb is handed to a fixed
handler as a string and is never re-tokenised against the command table.

The critic verified the CircleMUD table but flagged that one automated read of the
source contradicted another, so treat that one as verified-with-a-caveat.

NPC reaction to player speech, where it exists at all, is substring matching on
keywords (Diku speech programs), with documented failure modes of its own including
mobs triggering each other into a recursion crash.

### Interactive drama research — a catch-all is itself an act

Façade mapped typed English onto discourse acts with roughly 800 authored templates
compiling to about 6,800 Jess rules, all firing inside 300 ms. Two things matter
for us.

First, the taxonomy contains an explicit catch-all: `DASystemCannotUnderstand`,
described as the catch-all for all utterances which trigger no other discourse acts.
Not understanding is a *typed result*, which the next stage can react to. Above that
sit global deflection and recovery handlers that work regardless of which dramatic
beat is running.

Second, the honest numbers. Façade's authors reported natural-language
understanding failing about 30% of the time in informal evaluation, and by their own
finer breakdown only about a quarter of turns reached a fully appropriate reaction.
That is the ceiling three person-years of hand-authoring bought.

**Critic corrections.** The taxonomy is **24 acts** in the 2004 paper's own table,
and the authors later describe about 30 parameterised acts. It is not 21. The
30%/70% sentences are correctly quoted; 30% is the failure rate.

Façade never had our first fault, because physical action was a separate input
channel and the language understanding only ever saw text.

### LIGHT (Facebook AI Research) — separate channels, not one classification

LIGHT models a turn as separate channels: a free-text dialogue utterance, a physical
action from a fixed verb set (get, drop, put, give, steal, wear, remove, eat, drink,
hug, hit) checked against explicit state-graph preconditions, and one of 22 fixed
emotes with no state effect. Actions are legal or not by world state, never by
surface wording.

**Critic correction.** The claim that every turn carries both a dialogue slot and an
action slot is **false**. The paper's own table gives 110,877 utterances against
37,865 actions and emotes combined, roughly a third of turns. The channels are
independent and either may be absent — which is the useful lesson, and a stronger
one than the overclaim.

### Shipped AI-narrated games — an explicit mode selector, every time

AI Dungeon has three input doors, verified from Latitude's own help pages. Say mode
"adds 'You say,' to the beginning of your input and wraps whatever you type in
quotation marks, unless you typed them yourself". Do mode prepends "You" and
converts first person to second person outside quotes. Story mode passes text
through unaltered. NovelAI's text adventure module ships the same three, with
punctuation inside Say choosing say, ask or yell.

Its history runs menu, then two explicit input types, then four. It never converged
on guessing. **Critic correction:** the claim that Latitude never *tried* automatic
detection could not be confirmed or refuted; absence of evidence only.

The one auto-heuristic found in the wild is a community client that routes input to
Say when the player typed quotation marks — an explicit lexical signal, not
semantic classification. The one project found that does classify free text with a
model is a solo experiment whose author documents the resulting drift himself.

### Conversation design and tabletop practice

Emily Short's taxonomy names the failure our second fault belongs to: the
guess-the-noun problem, where the player must hit keywords the author had in mind.
She also names the lawnmower effect for menus, a term she attributes to Duncan
Stevens. Chris Crawford's decade on a fully generalised verb simulation for dramatic
interaction is the tradition's clearest documented graveyard, in his own words:

> "abstracting dramatic interaction is immensely difficult"

No craft source treats "nothing happens" as acceptable. The documented alternatives
are a characterful in-fiction non-answer, an explicit acknowledgement that the
attempt was heard and does not apply, or redirection to what is possible.

Pathfinder 1e answers the mechanical question directly:

> "In general, speaking is a free action that you can perform even when it isn't
> your turn. Speaking more than a few sentences is generally beyond the limit of a
> free action."

And a *directed* social attempt is a timed action that can fail: Diplomacy to change
an attitude takes one minute, a request takes one or more rounds, in-combat feint
and demoralise are standard actions. **Critic correction:** the hurried Diplomacy
check as a full-round action at −10 is a Pathfinder Unchained skill unlock, not Core
Rulebook text.

Apocalypse World supplies the discipline our project already runs on, stated as a
rule: "to do it, do it" — the move triggers from the fiction, never from the player
naming the mechanic.

---

## What this diagnoses in our own code

Measured, not inferred. `gm/judgement.py` holds two violence regexes; `wants_a_fight`
runs the second over the player's **entire raw line**, quoted speech included. Its
`_player_is_the_one_swinging` test then asks who is named in front of the verb, and a
first-person pronoun *inside the quotation* satisfies it.

Nine lines through `wants_a_fight`, 2026-09-08:

| Result | Line |
|---|---|
| opens a fight | I tell the clerk "I am a monk, I can handle myself in a fight …" |
| opens a fight | I tell the clerk I am a monk and can handle myself in a fight |
| opens a fight | I tell the guard "put down your sword, I do not want to fight" |
| opens a fight | I warn the thug that I will hit him if he does not move |
| correct | I attack the guard / I punch the thug in the mouth |
| correct | I ask the woman if she wants to pay for my services |

Three false positives in nine, and the third is a line **refusing** a fight. The
guard that should have caught them, `_MUSING`, lists talk, speak and ask but not
tell, say, warn or promise — a verb blacklist doing a job the traditions do with a
quarantined payload.

The second fault has a simpler cause: of the 42 ops in `rules/intents.py` there is
**no speech op at all**. Speech has nowhere to land but `narrate_only`, and when the
prose call produces nothing the turn reaches the holding line in `play/views.py`.
Action verbs each have a door; speech has none.

---

## What the traditions imply for a fix

Recorded as design input, not as a decision. Aligned to the three laws.

1. **Quarantine before detection.** Any span the player quoted, and the complement of
   a speech verb (tell X that …, say to X …, ask X …), is a payload. Run no action
   detector over it. This is Inform's topic value and LambdaMOO's rewrite, and it is
   the smallest change that kills the measured false positives.
2. **Give speech its own door.** A `say` op, with the person addressed and the words
   as an opaque string, is a real op with a real tell. It costs nothing in 1e — the
   rules already call speech a free action — so it does not need a roll. This also
   answers the second fault by construction: speech never has to win a
   classification against action to be handled.
3. **A directed social attempt is a different thing from talking.** Persuade, deceive
   and threaten already exist in the engine as skill checks with the rules' own time
   costs. The line between free speech and a social action is drawn in the Core
   Rulebook, not by us.
4. **Never answer speech with silence.** TADS's lowest-priority catch-all and
   Façade's global deflection tier are the same idea: an unmatched utterance gets a
   designed in-character non-answer that acknowledges it was heard. Our holding line
   is the parser-error floor being used as a conversation response.
5. **Do not expect a classifier to be right.** The most authored system in this space
   shipped at a 30% misunderstanding rate. Graceful behaviour on the wrong 20% is
   what makes the design tolerable, not accuracy.

**Refused, with reasons.** A general verb ontology for social acts is Crawford's
documented decade-long failure. A larger discourse-act taxonomy is not free either:
the classification literature converges on 8 to 20 categories being what actually
ships, with the full ISO 24617-2 hierarchy needing heavy models to reach 66% exact
match and degrading badly across domains. A mode selector in the UI is genuinely the
industry answer, but it is a change to how the player types, and the quarantine plus
a `say` op gets most of the benefit without one.

---

## Asterisks for action, quotes for speech

Raised 2026-09-08 as a candidate convention, with different colours in the UI.
Researched, and the honest summary is that it is old, universal and undocumented.

The convention predates language models by decades. Its lineage runs through the
bounding asterisk of comics and early network chat, the MUSH pose and the IRC emote,
and it is named in the linguistics literature as autonomous stage direction (Yus,
*Cyberpragmatics*, discussed by Ben Zimmer at Language Log). Every roleplay tool in
the sweep uses it now. SillyTavern gives italic text and quoted text their own theme
colours as separate settings, and ships a markdown auto-repair for model output that
leaves an asterisk unclosed.

**What could not be sourced is any evidence that it makes the model behave better.**
No benchmark isolates the convention. Character.AI's own explainer describes some
emphasis marks as visual only, without interpretive meaning for the model. Treat it
as a readability and rendering choice, which is a real benefit on its own, and do not
claim a quality gain we cannot measure.

It does have one structural use worth noting: it gives the player a way to *mark*
their own intent, which is the cheap syntactic signal the community client used to
route quoted input to Say mode. A player who writes quotes has told us where the
speech is, and the quarantine in point 1 above can simply believe them.

## What could not be sourced

- Whether Latitude ever tried automatic mode detection for AI Dungeon. No evidence
  either way after searching help pages, changelogs and community wiki.
- Any documented case anywhere of our specific drift: several idle non-answers
  followed by the narration silently relocating the player to a new scene. The
  nearest documented cousins are about contradiction under load, not this shape. Our
  own playtest is the primary evidence for it.
- A primary source stating flatly that a parser must never do nothing. The practice
  is universal across Inform, TADS, LambdaMOO, LPMud and Diku; the maxim as a
  quotable sentence is not.
- Verbatim D&D 5e Dungeon Master's Guide text on resolving social interaction; only
  secondary paraphrase was reachable.
- A benchmark of action-versus-speech classification for a rules-aware language-model
  game master. LIGHT is the closest and is a text-adventure setting.

## Sources

Writing with Inform §7.6 and §17.5 (ganelson.github.io/inform-website); TADS 3 "The
Art of Conversation" (tads.org); LambdaMOO Programmer's Manual, command parsing
(tecfa.unige.ch mirror); CircleMUD `src/interpreter.c`; Mateas and Stern, "Natural
Language Understanding in Façade" (TIDSE 2004) and "Structuring Content in the
Façade Interactive Drama Architecture" (AIIDE 2005), eis.ucsc.edu; Urbanek et al.,
"Learning to Speak and Act in a Fantasy Text Adventure Game", arXiv:1903.03094;
AI Dungeon help centre, the-do-mode / the-say-mode / the-story-mode; NovelAI text
adventure documentation; Emily Short, "Conversation" (emshort.blog); Chris Crawford,
erasmatazz.com; Mauldin, "Chatterbots, TinyMUDs, and the Turing Test" (AAAI-94);
Pathfinder Core Rulebook speech and Diplomacy entries via Archives of Nethys and
d20pfsrd; Baker, Apocalypse World, quoted in thealexandrian.net.
