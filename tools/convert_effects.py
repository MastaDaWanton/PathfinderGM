"""Bake the extracted effects into the shipped ingredient data as authored specs.

Until now the mechanics were derived at read time by `rules/effects.py`. Deriving is fine
while the parse is the only source of truth, and wrong the moment a person is allowed to
correct one: an edit would be overwritten by the next parse.

So the specs are written into the file, and the parse becomes the *starting point* rather
than the answer. `converted` marks the ones the parse produced, so a later pass can tell
what a human has since touched from what nobody has looked at yet.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

from rules import effects, effectspec as es  # noqa: E402

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))

stats = {"entries": 0, "with_effects": 0, "effects": 0, "invalid": 0, "silent": 0}
by_type = {}

for ing in data["ingredients"]:
    stats["entries"] += 1
    found = effects.extract(ing.get("text", ""))
    specs = []
    for e in found:
        if not e.spec:
            continue
        problems = es.validate(e.spec)
        if problems:
            stats["invalid"] += 1
            # Kept as narrative rather than dropped: a claim the schema cannot hold is
            # still a claim the source made, and losing it silently is the one outcome
            # worse than holding it loosely.
            specs.append({"type": "narrative", "target": e.text,
                          "note": f"needs review: {problems[0]}"})
            continue
        specs.append(e.spec)
        by_type[e.spec["type"]] = by_type.get(e.spec["type"], 0) + 1

    ing["effects"] = specs
    # True while nobody has corrected them. The editor clears it on save, so the two
    # states are distinguishable: parsed and unreviewed, or looked at by a person.
    ing["effects_converted"] = True
    if specs:
        stats["with_effects"] += 1
        stats["effects"] += len(specs)
    else:
        stats["silent"] += 1

data["effects_note"] = (
    "Effects were converted from each entry's description by rules/effects.py and are "
    "stored here rather than re-derived, so an edit is not overwritten by the next parse. "
    "`effects_converted` is true until a person has reviewed them."
)
path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")

print(f"entries        {stats['entries']}")
print(f"  with effects {stats['with_effects']}")
print(f"  no mechanics {stats['silent']}  (description only)")
print(f"effects        {stats['effects']}")
print(f"  needs review {stats['invalid']}")
print()
for t, n in sorted(by_type.items(), key=lambda kv: -kv[1]):
    print(f"  {t:20} {n}")
