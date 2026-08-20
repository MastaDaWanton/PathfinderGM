# Architecture

Settled with the user at the end of the World Bible session, before any code was written.
These are decisions, not suggestions — change them deliberately, not by drift.

## The shape

Not a storyteller with dice bolted on. **A rules engine with two agents attached.**

```
                    ┌──────────────────────────────┐
   you  ──────────► │  GM AGENT (user-facing)      │ ──► narration, NPC voice
        ◄────────── │  proposes, never resolves    │
                    └──────────┬───────────────────┘
                               │ structured intent
                               │ ("Reflex save DC 18", "orc attacks")
                    ┌──────────▼───────────────────┐
                    │  RULES ENGINE (code)         │
                    │  owns ALL state and rolls    │
                    └──────────┬───────────────────┘
                     player roll│      │NPC/hidden roll
                    ┌──────────▼──┐   └──► rolled here, result to the GM
                    │  DICE POPUP │
                    └─────────────┘
                               │ what happened
                    ┌──────────▼───────────────────┐
                    │  WORLD-STATE AGENT (cheap)   │ ──► compact state the GM reads
                    │  watches, predicts, hooks,   │
                    │  faction influence, standing │
                    └──────────────────────────────┘

   World Bible export (read-only)  +  campaign overlay (everything play changed)
```

## The decisions

**Combat: initiative and positions, no grid.** Turn order, ranges as zones
(engaged / near / far), full attack maths, conditions and buffs tracked with durations —
but no squares to count. Keeps nearly all of 1e's mechanical depth and all of the
bookkeeping worth offloading, and avoids needing maps, which the world export deliberately
does not provide (no coordinates, no distances).

**The GM proposes; the engine disposes.** The GM agent never states a mechanical outcome.
It declares intent — *this calls for a Reflex save*, *the orc attacks* — the engine
resolves it, and the GM narrates the result it is handed. This costs a structured call for
every mechanical intent, and it is the only arrangement in which the game cannot be talked
out of its own rules. A persuasive model narrating a hit that actually missed is the
failure mode this exists to make impossible.

**Rolls.** The engine listens for anything requiring one. **Player rolls surface on a dice
popup and the player rolls them.** Everything else — NPC attacks, saves, hidden checks —
the engine rolls and hands to the GM as a fact to narrate.

**One PC.** You play a single character; every ally, hireling and enemy belongs to the GM.
The dice popup only ever asks you for your own rolls.

**Full 1e character creation, guided.** Race, class, abilities, skills, feats, gear — the
real thing, with legality enforced and choices explained. A wrong sheet poisons every roll
that follows, and 1e's depth starts at creation.

**The world is read-only; the campaign is an overlay.** World Bible's files stay pristine
source of truth. Everything play changes — a burned bridge, a dead NPC, a faction's shifted
influence — lives in the campaign save, keyed by the export's durable entity ids. So the
same world can host several campaigns, and re-exporting a world never clobbers one.

**The world clock ticks on its own.** Factions pursue their aims between scenes whether the
player is involved or not; a rival advances while you were elsewhere. This is where hooks
come from for free. The background loop must be **legible and cancellable** — the player
should be able to see what moved and why, and stop it.

**Models are configured per role, each local or hosted.** A capable model narrating, a
cheap fast one watching. Each points independently at Ollama or an API, mirroring World
Bible's generator/proofreader settings, which already work. **Local is the default and must
always be sufficient; hosted is an option, never a requirement.**

**Stack: reuse World Bible's.** Python/Django + Electron, PyInstaller, electron-builder.
It already ships as a one-file `.exe` with auto-update, and every packaging trap in
`CLAUDE.md` has been paid for once already.

## What follows from all this

- **Rules resolution is code: instant, exact, free.** Anything the rules can decide must be
  decided by the rules, never generated. The model is for narration and voice only. This is
  the main lever against a local model's latency — most of a turn should involve no
  inference at all.
- **The GM's structured-intent protocol is the core interface** of the whole app, and the
  first thing worth designing carefully. Everything else hangs off it.
- **The world-state agent's output is a budget, not a dump.** It writes a compact state for
  the GM to read; that budget will be the thing that decides whether long campaigns stay
  coherent.
- **Two writers, one save.** The engine and the world-state agent both write the campaign
  overlay. Decide early who owns what, or they will race.

## Still open

- What the world-state agent's stored state actually looks like, and how much of it reaches
  the GM per turn.
- How much history the GM sees — full transcript, summarised, or retrieved.
- How a session starts: does the player pick a situation, or does the app propose scenarios
  from the world's own material (a faction's aim, a route's friction, an event's aftermath)?
- Whether NPC rolls are shown to the player or kept behind a screen.
- Encounter building against 1e CR maths for a **single** PC, which the published tables do
  not assume.
