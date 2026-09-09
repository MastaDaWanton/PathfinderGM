"""What one character of our own prompt actually costs in tokens.

The context budget in `gm/prompts.py` is enforced in characters, because counting
characters is free and shipping a tokeniser is not: the app is one .exe with two
dependencies, and a tokeniser for whichever model the user has chosen is neither
small nor knowable at build time.

So the budget converts with a constant, and a guessed constant is either wasteful or
dangerous. Too many characters per token and the prompt overflows the window, which
is the silent-truncation failure the budget exists to prevent. Too few and we throw
away context we had every right to use.

This measures the constant instead. It builds a real prompt out of the shipped world
and asks the configured model for exactly one token, then reads `prompt_eval_count`
off the reply, which is the model's own count of the prompt it just read, chat
template and all.

Run it after changing the model, the briefing or the worked examples:

    python tools/token_ratio.py

It loads the model, so it takes a cold load the first time (measured at 60 to 100
seconds on this machine) and does not need the app to be running.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pathfindergm.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402

from gm import prompts as P  # noqa: E402
from play import campaign as C  # noqa: E402
from play.views import _recent_events  # noqa: E402


def prompt_tokens(messages, model, host, timeout=600):
    """The model's own token count for these messages, via a one-token generation."""
    body = {
        "model": model,
        "messages": messages,
        "stream": False,
        # One token out. We are buying the count, not the answer.
        "options": {"num_predict": 1, "num_ctx": P.NUM_CTX, "temperature": 0},
        "keep_alive": "5m",
    }
    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8")).get("prompt_eval_count")


def main():
    cfg = settings.MODELS["narrator"]
    model, host = cfg["model"], cfg["host"]

    c = C.new_campaign("slice", seed=7)
    eng = c.engine()
    for i in range(8):
        eng.run(eng.validate([{
            "op": "spawn", "because": "a market",
            "params": {"template": "guildhand", "count": 1, "name": f"trader {i + 1}"}}]))
    brief = P.scene_brief(
        c.world, c.scene, c.location, _recent_events(c.world, c.location),
        here=eng.here(), known=eng.places(), recent=None, secret=True, turn=0)

    history = []
    for _ in range(10):
        history += [
            {"role": "user", "content": "I ask the trader about the export seals"},
            {"role": "assistant", "content":
                "The trader turns the bar over in his hands and holds it to the light. "
                "The stamp is there, shallow but there, and he grunts at it. Around you "
                "the market keeps moving, and the guards at the arch have not looked "
                "this way once since you came in. He waits for you to say something."}]

    cases = [
        ("briefing and brief only", [{"role": "system", "content": P.BRIEFING + "\n\n" + brief}]),
        ("a full turn, out of combat",
         P.call_one_messages(brief, history, "I ask him who checks the seals")),
        ("a full turn, in combat",
         P.call_one_messages(brief, history, "I strike the nearest guard", in_combat=True)),
    ]

    print(f"model: {model}\n")
    print(f"{'prompt':<28} {'chars':>8} {'tokens':>8} {'chars/token':>12}")
    worst = None
    for label, messages in cases:
        chars = sum(len(m.get("content") or "") for m in messages)
        tokens = prompt_tokens(messages, model, host)
        if not tokens:
            print(f"{label:<28} {chars:>8,}    no prompt_eval_count in the reply")
            continue
        ratio = chars / tokens
        worst = ratio if worst is None else min(worst, ratio)
        print(f"{label:<28} {chars:>8,} {tokens:>8,} {ratio:>12.2f}")

    if worst is not None:
        print(f"\nworst case: {worst:.2f} chars per token")
        print(f"CHARS_PER_TOKEN in gm/prompts.py is {P.CHARS_PER_TOKEN}, which is "
              f"{'safe' if P.CHARS_PER_TOKEN <= worst else 'TOO HIGH — the budget will overflow'}")


if __name__ == "__main__":
    main()
