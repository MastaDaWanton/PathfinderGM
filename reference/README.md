# Rules reference

Machine-readable Pathfinder 1e reference, extracted from the PDFs so that neither the app
nor anyone working on it has to open a 600-page book to answer a mechanical question.

Everything here is **generated**. Do not hand-edit it — change `build_reference.py` and
re-run:

```bash
python reference/build_reference.py --crb "H:/Pathfinder/Pathfinder_Core_Rulebook.pdf" --gmg "H:/Pathfinder/Pathfinder Roleplaying Game - GameMastery Guide.pdf"
```

The PDFs themselves are **not** in this repository and must not be added to it.

## What is here

| File | What it is |
|---|---|
| `index.json` | Every section and every numbered table in both books, with its PDF page. 1,609 sections and 125 tables from the Core Rulebook; 789 and 127 from the GameMastery Guide. |
| `INDEX.md` | The same index, readable. Start here when you need to find a rule. |
| `conditions.json` | All 34 conditions from Appendix 2, with their full text. |
| `encounter-design.json` | The encounter and XP budget material from *Designing Encounters*. |

Page numbers are **PDF page numbers, zero-based** — what a reader tool wants. They do not
match the printed numbers in the book's own footers, which run a few pages behind.

## What is deliberately not here

**The books.** Two reasons, and both matter.

The rules are Open Game Content under the OGL 1.0a, but the PDFs also contain Product
Identity — the setting, its deities, the iconic characters, the art and the trade dress —
which is *not* licensed and must not be redistributed. Extracting mechanics is fine;
extracting everything is not. See [`../OGL-NOTICE.md`](../OGL-NOTICE.md), and note that
the verbatim licence still has to be added before anything ships.

The second reason is practical: a 1,300-page prose dump is no more useful to an agent
than the books were. An index plus structured mechanics is what actually removes the need
to open a PDF.

## The typography problem

The books are typeset with ligatures and tight kerning, and the PDF text layer comes out
broken:

| In the PDF | What it means |
|---|---|
| `f lat-footed` | the `fl` ligature, extracted as a bare `f` |
| `inf lict` | the same ligature, mid-word |
| `s itu ation` | kerning, scattering a word into uneven pieces |
| `c re atures` | the same, three pieces |

`clean()` repairs these, and the repair is the fiddliest code in the file because every
naive version broke ordinary prose:

- welding short runs turned `who has not yet` into `whohasnotyet` and `with a dog` into
  `with adog`;
- joining anything ending in `f` turned `of light` into `oflight`;
- a dictionary of short words can never be complete, so `dog` looked like a fragment.

What works is testing the *shape* of the damage rather than guessing at words: a kerned
break leaves three or more consecutive pieces, at least one of which is a one- or
two-letter token that is not an English word. A list of one- and two-letter words **can**
be exhaustive, so that test does not degrade. `tests/test_reference.py` pins all of it,
including the prose that must be left alone — two-letter capitals like `AC`, `CR` and
`DC` are the sharp case, because they look exactly like fragments.

## What the reference is used for

Beyond lookup, `tests/test_reference.py` checks the engine against the book:

- every condition in `rules/tables.py` must exist in Appendix 2 — this caught one the
  engine had invented;
- the conditions the book defines that the engine does **not** implement are listed
  explicitly, so that ledger shrinks deliberately rather than by accident. It is down to
  five, each with the machinery it is waiting on.
