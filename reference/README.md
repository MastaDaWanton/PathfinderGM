# Rules reference

Machine-readable Pathfinder 1e reference, extracted from the PDFs so that neither the app
nor anyone working on it has to open a six-hundred-page book to answer a mechanical
question.

Everything here is **generated**. Do not hand-edit it — change the builder and re-run:

```bash
python reference/build_reference.py --library "H:/Pathfinder"
```

The PDFs themselves are **not** in this repository and must not be added to it.

## What is here

| File | What it is |
|---|---|
| `INDEX.md` | The catalogue: every book, with its section, table and entry counts. Start here. |
| `index.json` | The same catalogue as data, plus any PDFs the builder did not recognise. |
| `lookup.json` | **The fast path.** A lowercased name → every book and page it appears in. One file, one dictionary hit, and you know where to look. |
| `books/<slug>.json` | One book's full outline, its numbered tables, and — for bestiaries — its creatures with CR. |
| `conditions.json` | All 34 conditions from Core Rulebook Appendix 2, with their full text. |
| `encounter-design.json` | The encounter and XP budget material from *Designing Encounters*. |

Page numbers are **PDF page numbers, zero-based** — what a reader tool wants. They do not
match the printed numbers in the books' own footers, which run a few pages behind.

Adding a book to the library means adding it to `books.py` as well; `index.json` lists
anything unrecognised and a test fails on it, because a book that is present but
unindexed is silently absent from every lookup.

## What is deliberately not here

**The books.** Two reasons, and both matter.

The rules are Open Game Content under the OGL 1.0a, but the PDFs also contain Product
Identity — the setting, its deities, the iconic characters, the art and the trade dress —
which is *not* licensed and must not be redistributed. Extracting mechanics and an index
is fine; extracting everything is not. See [`../OGL-NOTICE.md`](../OGL-NOTICE.md), and
note that the verbatim licence still has to be added before anything ships.

The second reason is practical: a dump of eighteen books is no more useful to an agent
than the books were. An index plus structured mechanics is what actually removes the need
to open a PDF.

## Coverage, honestly

Creature extraction varies a lot by book, and the variation is not noise — it is whether
the book's own outline names its monsters:

| Book | Creatures found | Why |
|---|---:|---|
| Bestiary 1 | 224 | outline lists every monster |
| Bestiary 3 | 195 | as above |
| Bestiary 5 | 194 | as above |
| Bestiary 6 | 125 | as above |
| Bestiary 2 | 37 | outline is organised by *family* — "Aeon", "Agathion" are lore pages, and the individual creatures are never named in it |
| Bestiary 4 | 41 | as Bestiary 2 |
| Codex Monstrueux | — | not scanned; see below |

Spot-checked against the printed Bestiary 1: of twenty-five well-known monsters, twenty-four
came out with the right CR and one was absent. **None was wrong.** That is the trade the
extractor is tuned for, and the next improvement worth making is a text-derived table of
contents for the two family-organised bestiaries — not more heuristics.

The Codex Monstrueux is indexed but not creature-scanned: its outline is 26 entries for
258 pages, and at 131 MB its text layer is so slow to extract that a scan was still on
that one book after twenty minutes while every other bestiary finished in twenty seconds.

One more thing the library turned up: `pathfinder advanced race guide pdf.pdf` is **not**
the Advanced Race Guide. It is the four-page errata sheet for its first printing, so no
race option can be looked up from it. The book itself is not in the library.

## Creature CR, and why it was hard to get right

Encounter building for a *single* PC is an open question in `docs/architecture.md`, and it
cannot be attempted without knowing what each creature is worth. The outline gives every
monster's name and page; the CR exists only in the text, so bestiaries are the one place
the builder reads whole pages.

Two earlier versions produced **wrong** ratings, which is worse than missing ones — the
encounter builder would act on them without knowing to doubt them:

- taking the first CR on the page gave every creature sharing a page the first one's
  rating, so the dire bear inherited the grizzly's CR 4;
- falling back to the head of a comma-separated name matched "Barghest, Greater" against
  plain "Barghest" and gave it CR 4 instead of its own.

Header shapes vary even within one book — `Aboleth ABOLETh CR 7` where the running margin
repeats the name, `AChAIERAI CR 5` where it does not, `Illustration by Ben Wootten Aboleth
ABOLETh CR 7` where a caption runs into it. Every attempt to *detect which shape* a header
was made things worse: repairing the aboleth lost the ghoul, and repairing the ghoul lost
the aboleth.

What ended it was giving up on guessing. The builder now takes the trailing one, two,
three and four words before each `CR n` as candidates and **keeps only a candidate the
book's own outline names on that same page**. That is a fact about the book rather than an
inference about its typography, so it cannot mis-price anything: a wrong guess matches
nothing and is discarded. Coverage became a function of outline quality, which is the
right way round — a missing creature is a gap, a wrong CR is a lie the encounter builder
would act on.

`tests/test_reference.py` spot-checks fifteen creatures against the printed book.

## The typography problem

The books are typeset with ligatures and tight kerning, and the PDF text layer comes out
broken:

| In the PDF | What it means |
|---|---|
| `f lat-footed` | the `fl` ligature, extracted as a bare `f` |
| `inf lict` | the same ligature, mid-word |
| `s itu ation` | kerning, scattering a word into uneven pieces |
| `c re atures` | the same, three pieces |

`clean()` repairs these, and it is the fiddliest code in the builder because every naive
version broke ordinary prose:

- welding short runs turned `who has not yet` into `whohasnotyet` and `with a dog` into
  `with adog`;
- joining anything ending in `f` turned `of light` into `oflight`;
- a dictionary of short words can never be complete, so `dog` looked like a fragment.

What works is testing the *shape* of the damage rather than guessing at words: a kerned
break leaves three or more consecutive pieces, at least one of which is a one- or
two-letter token that is not an English word. A list of one- and two-letter words **can**
be exhaustive, so that test does not degrade. The tests pin all of it, including the
prose that must be left alone — two-letter capitals like `AC`, `CR` and `DC` are the
sharp case, because they look exactly like fragments.

## What the reference is used for

Beyond lookup, `tests/test_reference.py` checks the engine against the books:

- every condition in `rules/tables.py` must exist in Appendix 2 — this caught one the
  engine had invented and eighteen it was missing;
- the conditions the book defines that the engine does **not** implement are listed
  explicitly, so that ledger shrinks deliberately rather than by accident. It is down to
  five, each with the machinery it is waiting on.
