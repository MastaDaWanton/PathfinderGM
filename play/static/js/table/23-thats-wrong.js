/* "That's wrong": the player's correction of a narrated beat (play/corrections.py).

   Under each of the narrator's own beats (02-state.js leaves a `.beatfix` slot after
   every who:"gm" kind:"setup" beat) a quiet line: "That's wrong". Pressed, the beat's
   own sentences become pickable in place and a slip opens under it with an optional
   one-line note. "Fix it" asks the server to remake the beat against the engine's facts;
   the remade beat carries the same line again, with "Keep this one", "Put the first one
   back" and "Write it myself". After three remakes the player also rejected the slip
   says so in words and offers only writing it, putting the first back, or leaving it.

   Only the latest turn's beats can be remade (later beats are built on the older ones);
   an older beat can be marked wrong, which logs it for training and leaves the page as
   it is. What may be offered on each beat is the server's to say (`s.corrections`), so
   the page never offers what the server would refuse.

   The open slip is held here (`FIX`), not in the DOM: render() rebuilds the whole story
   on every state, and the slip is put back by the render hook below.

   Below the narration's half, the same slip lists what the ENGINE did that turn
   (play/engine_corrections.py, the owner, 2026-11-15): the reading of the player's line,
   each outcome in the engine's own words with the rolls the Rolls panel shows, and what
   the plan did nothing for. A line is picked as a sentence is (the same red ink), given a
   kind from the owner's fixed list and an optional note, and "Log the engine's mistake"
   writes them to the training log. Nothing is undone: pinpoint and log only. The lines
   come from the server already filtered (no hidden creature, no hidden roll). */
(function () {
  const FIX = { beat: -1, mode: "", picked: [], note: "", text: "", busy: false, error: "",
                engine: null };

  function reset() {
    FIX.beat = -1; FIX.mode = ""; FIX.picked = []; FIX.note = ""; FIX.text = "";
    FIX.busy = false; FIX.error = ""; FIX.engine = null;
  }

  // The engine's half: {beat, loading, lines, kinds, max_note, recorded, marks: {id:
  // {kind, note}}, busy, error, logged}. Fetched when the slip opens, never in the state,
  // so a long campaign's state carries no turn records.
  async function loadEngine(i) {
    FIX.engine = { beat: i, loading: true, lines: [], kinds: {}, marks: {}, max_note: 400 };
    try {
      const r = await fetch(`/api/beat/engine?beat=${encodeURIComponent(i)}`);
      const d = await readJSON(r);
      if (!r.ok) throw new Error(d.error || ("HTTP " + r.status));
      if (!FIX.engine || FIX.engine.beat !== i) return;
      Object.assign(FIX.engine, d, { loading: false });
    } catch (err) {
      if (!FIX.engine || FIX.engine.beat !== i) return;
      FIX.engine.loading = false;
      FIX.engine.error = (err && err.message) || String(err);
    }
    paint(STATE);
  }

  const MISSING = "missing";

  function kindPicker(id, mark, kinds, off) {
    const opts = Object.entries(kinds).filter(([k]) => k !== MISSING)
      .map(([k, label]) => `<option value="${esc(k)}"${mark.kind === k ? " selected" : ""}>${
        esc(label)}</option>`).join("");
    const pick = id === MISSING ? "" : `<select class="v2-well" data-enkind="${esc(id)}"
        aria-label="What kind of mistake"${off}><option value="">What kind of mistake?</option>${
        opts}</select>`;
    return `<div class="enmark">${pick}
      <input class="v2-well" type="text" data-ennote="${esc(id)}" maxlength="${
        esc(FIX.engine.max_note)}" value="${esc(mark.note || "")}"
        aria-label="A short note (optional)" placeholder="A short note (optional)"${off}></div>`;
  }

  function engineBox() {
    const E = FIX.engine;
    if (!E) return "";
    const head = `<label class="enhead">What the engine did this turn</label>`;
    if (E.loading) return `${head}<p class="fixhint">Reading the turn’s record…</p>`;
    if (E.error && !E.lines.length) {
      return `${head}<p class="fixerr" role="alert">${esc(E.error)}</p>`;
    }
    const off = E.busy ? " disabled" : "";
    const rows = (E.lines || []).map(ln => {
      const mark = E.marks[ln.id];
      const rolls = (ln.rolls || []).map(r => `<span class="enroll">${esc(r)}</span>`).join("");
      return `<li class="enline">
        <span class="sent" role="button" tabindex="0" data-enline="${esc(ln.id)}"
          aria-pressed="${mark ? "true" : "false"}">${esc(ln.text)}</span>${rolls}
        ${mark ? kindPicker(ln.id, mark, E.kinds, off) : ""}</li>`;
    }).join("");
    const miss = E.marks[MISSING];
    const list = E.lines.length ? `<ul class="enlines">${rows}</ul>`
      : `<p class="fixhint">${E.recorded ? "The engine resolved nothing you can be shown this turn."
          : "No engine record was kept for this turn."}</p>`;
    const n = Object.keys(E.marks).length;
    const ready = n > 0 && Object.entries(E.marks).every(([id, m]) => id === MISSING || m.kind);
    const done = E.logged ? `<p class="fixhint" role="status">Logged ${esc(E.logged)} mark${
      E.logged === 1 ? "" : "s"} on the engine.</p>` : "";
    return `${head}
      <p class="fixhint">Click a line the engine got wrong, then say how. Nothing is undone:
        it is logged so the rules can be fixed.</p>
      ${list}
      <div class="enmiss">
        ${btn("fixlink", "enmissing", miss ? "Nothing is missing after all" : "Something’s missing", off)}
        ${miss ? kindPicker(MISSING, miss, E.kinds, off) : ""}</div>
      ${E.error ? `<p class="fixerr" role="alert">${esc(E.error)}</p>` : ""}
      ${done}
      <div class="fixgo">${btn("v2-btn is-small is-quiet", "enlog",
        E.busy ? "Logging…" : "Log the engine’s mistake", ready && !E.busy ? "" : " disabled")}</div>`;
  }

  async function sendEngine(i) {
    const E = FIX.engine;
    if (!E) return;
    E.busy = true; E.error = ""; E.logged = 0;
    paint(STATE);
    const marks = Object.entries(E.marks).map(([line, m]) =>
      ({ line, kind: line === MISSING ? MISSING : m.kind, note: m.note || "" }));
    try {
      const d = await post("/api/beat/engine", { beat: i, marks });
      if (FIX.engine !== E) return;
      Object.assign(E, { lines: d.lines || E.lines, marks: {}, busy: false,
                         logged: d.marks || marks.length });
    } catch (err) {
      if (FIX.engine !== E) return;
      E.busy = false;
      E.error = (err && err.message) || String(err);
    }
    paint(STATE);
  }

  function toggleLine(id) {
    const E = FIX.engine;
    if (!E || E.busy) return;
    if (E.marks[id]) delete E.marks[id]; else E.marks[id] = { kind: "", note: "" };
    E.logged = 0;
    paint(STATE);
    const back = id === MISSING
      ? document.querySelector(`#story .fixpanel [data-fix="enmissing"]`)
      : document.querySelector(`#story .fixpanel [data-enline="${CSS.escape(id)}"]`);
    if (back) back.focus({ preventScroll: true });
  }

  function offers(s, i) {
    const beats = (s && s.corrections && s.corrections.beats) || {};
    // A beat the server says nothing about is an older narrated beat: it can be marked.
    return beats[String(i)] || { flaggable: true, current: false };
  }

  function maxRemakes(s) {
    return (s && s.corrections && s.corrections.max_remakes) || 3;
  }

  // The same sentence shape the server reads (gm/narration.py `_SENTENCE`): a run up to
  // the closing stop and any closing quote, with titles like "Mr." not ending one.
  const SENTENCE = /(?:\b(?:Mr|Mrs|Ms|Dr|St|Mt|Capt|Sgt|Lt|Col|Prof)\.|[^.!?])+(?:[.!?]+["'”’]?)?/g;

  // The beat's text as sentence spans, with everything between them (the spaces and the
  // paragraph breaks the page keeps, `white-space: pre-wrap`) left exactly where it was.
  function pickable(text, picked) {
    let html = "", at = 0, n = 0, m;
    SENTENCE.lastIndex = 0;
    while ((m = SENTENCE.exec(text)) !== null) {
      if (!m[0].length) { SENTENCE.lastIndex++; continue; }
      const raw = m[0], lead = raw.length - raw.trimStart().length;
      const body = raw.trim();
      html += esc(text.slice(at, m.index + lead));
      if (body) {
        const on = picked.includes(body);
        html += `<span class="sent" role="button" tabindex="0" data-sent="${n}"
          aria-pressed="${on}">${esc(body)}</span>`;
        n++;
      }
      at = m.index + lead + body.length;
    }
    return html + esc(text.slice(at));
  }

  function sentencesOf(text) {
    return (String(text || "").match(SENTENCE) || []).map(x => x.trim()).filter(Boolean);
  }

  function btn(cls, act, label, extra) {
    return `<button type="button" class="${cls}" data-fix="${act}"${extra || ""}>${label}</button>`;
  }

  // The resting line under a beat: the quiet link, and what was done to it.
  function row(s, i) {
    const o = offers(s, i);
    if (!o.flaggable && !o.current) {
      // Settled: say what happened, quietly, and offer nothing.
      const said = { "left wrong": "Marked wrong", "remake kept": "Remade",
                     "player wrote": "Your version", "put back": "Put back" }[o.outcome];
      return said ? `<span class="fixtag">${said}</span>` : "";
    }
    const bits = [];
    if (o.by === "remake") {
      bits.push(`<span class="fixtag">Remake ${esc(o.remakes)} of ${esc(maxRemakes(s))}${
        o.kept ? ", kept" : ""}</span>`);
    } else if (o.by === "player") {
      bits.push(`<span class="fixtag">Your version</span>`);
    }
    if (o.flaggable) bits.push(btn("fixlink", "open", "That’s wrong"));
    if (o.keep) bits.push(btn("fixlink", "keep", "Keep this one"));
    if (o.put_back) bits.push(btn("fixlink", "put_back", "Put the first one back"));
    if (o.write && o.by && o.by !== "narrator") {
      bits.push(btn("fixlink", "write", o.by === "player" ? "Write it again" : "Write it myself"));
    }
    return bits.join("");
  }

  function pickHint(o) {
    const n = FIX.picked.length;
    return (n ? `${n} sentence${n === 1 ? "" : "s"} marked.` : "Nothing marked: the whole beat.")
      + (o.remake ? ` ${esc(o.remakes_left)} remake${o.remakes_left === 1 ? "" : "s"} left.` : "");
  }

  function slip(s, i) {
    const o = offers(s, i);
    const beat = (s.transcript || [])[i] || {};
    const off = FIX.busy ? " disabled" : "";
    const err = FIX.error ? `<p class="fixerr" role="alert">${esc(FIX.error)}</p>` : "";
    if (FIX.mode === "write") {
      return `<div class="fixpanel" role="group" aria-label="Write this beat yourself">
        <label for="fixtext">Your version of the beat</label>
        <textarea id="fixtext" class="v2-well" rows="8"${off}>${esc(FIX.text)}</textarea>
        <p class="fixhint">What you save becomes the beat, and the narrator reads it as
          its own from the next turn.</p>
        ${err}
        <div class="fixgo">
          ${btn("v2-btn is-small is-go", "save", FIX.busy ? "Saving…" : "Save my version", off)}
          ${btn("v2-btn is-small is-flat", "cancel", "Cancel", off)}
        </div></div>`;
    }
    const cut = o.current && !o.remake && o.remakes >= maxRemakes(s);
    let lead;
    if (!o.current) {
      lead = "Later beats are built on this one, so it stays as it is. Marking it wrong " +
             "saves it for training the narrator.";
    } else if (cut) {
      lead = `It has been remade ${esc(o.remakes)} times. Write it yourself, put the first ` +
             "one back, or leave it as it is.";
    } else if (!o.remake) {
      lead = "The narrator’s notes for this beat were not kept, so it cannot be " +
             "remade. Write it yourself, or leave it marked wrong.";
    } else {
      lead = "Click the sentences that are wrong in the beat above. Pick none if all " +
             "of it is.";
    }
    const go = [];
    if (o.current && o.remake) {
      go.push(btn("v2-btn is-small is-go", "fix", FIX.busy ? "Remaking…" : "Fix it", off));
    }
    if (o.current && o.write) go.push(btn("v2-btn is-small is-quiet", "write", "Write it myself", off));
    if (cut && o.put_back) go.push(btn("v2-btn is-small is-quiet", "put_back", "Put the first one back", off));
    if (!o.current) go.push(btn("v2-btn is-small is-go", "mark", "Mark it wrong", off));
    else if (!o.remake) go.push(btn("v2-btn is-small is-quiet", "mark", "Leave it", off));
    go.push(btn("v2-btn is-small is-flat", "cancel", "Cancel", off));
    return `<div class="fixpanel" role="group" aria-label="What is wrong with this beat">
      <p>${lead}</p>
      <p class="fixhint" id="fixcount" aria-live="polite">${pickHint(o)}</p>
      <label for="fixnote">What’s wrong? <span class="fixopt">(optional)</span></label>
      <input id="fixnote" class="v2-well" type="text" maxlength="400" value="${esc(FIX.note)}"${off}>
      ${FIX.busy && FIX.mode === "fix" ? `<p class="fixhint">The narrator is writing it
        again. On a model on this machine that can take a minute.</p>` : ""}
      ${err}
      <div class="fixgo">${go.join("")}</div>
      ${engineBox()}</div>`;
  }

  function paint(s) {
    if (!s || !s.transcript) return;
    if (FIX.beat >= 0) {
      const b = s.transcript[FIX.beat];
      // The beat moved on under us (another device's turn, a reload): close the slip.
      if (!b || b.who !== "gm" || b.kind !== "setup") reset();
    }
    document.querySelectorAll("#story .beatfix").forEach(slot => {
      const i = Number(slot.dataset.beat);
      const open = i === FIX.beat;
      slot.classList.toggle("open", open);
      slot.innerHTML = open ? slip(s, i) : row(s, i);
      const p = slot.previousElementSibling;
      if (p && p.classList.contains("beat")) {
        const picking = open && FIX.mode === "pick";
        p.classList.toggle("picking", picking);
        if (picking) p.innerHTML = pickable(String(s.transcript[i].text || ""), FIX.picked);
      }
    });
  }

  async function send(body) {
    FIX.busy = true; FIX.error = "";
    paint(STATE);
    // A remake holds the game while the narrator writes (the server's lock): the desk
    // says so and offers no turn meanwhile, as it does while a turn resolves (busy()).
    if (typeof busy === "function") busy(true);
    try {
      const s = await post("/api/beat/correct", body);
      if (typeof busy === "function") busy(false);
      reset();
      render(s);
    } catch (err) {
      if (typeof busy === "function") busy(false);
      FIX.busy = false;
      FIX.error = (err && err.message) || String(err);
      paint(STATE);
    }
  }

  function toggleSentence(span) {
    const beat = STATE.transcript[FIX.beat] || {};
    const body = sentencesOf(beat.text)[Number(span.dataset.sent)];
    if (!body) return;
    const at = FIX.picked.indexOf(body);
    if (at >= 0) FIX.picked.splice(at, 1); else FIX.picked.push(body);
    span.setAttribute("aria-pressed", at >= 0 ? "false" : "true");
    // Only the count changes: a repaint would rebuild the beat and lose the focus.
    const count = document.getElementById("fixcount");
    if (count) count.textContent = pickHint(offers(STATE, FIX.beat));
  }

  document.addEventListener("click", e => {
    const span = e.target.closest("#story .beat.picking .sent");
    if (span) { toggleSentence(span); return; }
    const line = e.target.closest("#story .fixpanel [data-enline]");
    if (line) { toggleLine(line.dataset.enline); return; }
    const b = e.target.closest("#story .beatfix [data-fix]");
    if (!b || b.disabled) return;
    const i = Number(b.closest(".beatfix").dataset.beat);
    const act = b.dataset.fix;
    const beat = (STATE.transcript || [])[i] || {};
    if (act === "enmissing") {
      toggleLine(MISSING);
    } else if (act === "enlog") {
      sendEngine(i);
    } else if (act === "open") {
      reset(); FIX.beat = i; FIX.mode = "pick"; loadEngine(i); paint(STATE);
      const first = document.querySelector("#story .beat.picking .sent");
      if (first) first.focus({ preventScroll: true });
      // The slip opens under the beat, often below the fold of a short page.
      const slot = document.querySelector(`#story .beatfix[data-beat="${i}"]`);
      if (slot) slot.scrollIntoView({ block: "nearest" });
    } else if (act === "cancel") {
      reset(); paint(STATE);
    } else if (act === "write") {
      const keep = { picked: FIX.beat === i ? FIX.picked.slice() : [], note: FIX.note };
      reset(); FIX.beat = i; FIX.mode = "write"; FIX.text = String(beat.text || "");
      FIX.picked = keep.picked; FIX.note = keep.note; paint(STATE);
      const t = document.getElementById("fixtext");
      if (t) t.focus({ preventScroll: true });
    } else if (act === "fix") {
      FIX.mode = "fix";
      send({ beat: i, do: "fix", sentences: FIX.picked, note: FIX.note });
    } else if (act === "mark") {
      send({ beat: i, do: "mark", sentences: FIX.picked, note: FIX.note });
    } else if (act === "save") {
      send({ beat: i, do: "write", text: FIX.text, sentences: FIX.picked, note: FIX.note });
    } else if (act === "put_back" || act === "keep") {
      FIX.beat = i;
      send({ beat: i, do: act });
    }
  });

  // A sentence is a button to the keyboard too.
  document.addEventListener("keydown", e => {
    const span = e.target.closest && e.target.closest("#story .beat.picking .sent");
    if (span && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); toggleSentence(span); }
    const line = e.target.closest && e.target.closest("#story .fixpanel [data-enline]");
    if (line && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault(); toggleLine(line.dataset.enline);
    }
    if (e.key === "Escape" && FIX.beat >= 0 && !FIX.busy
        && e.target.closest && e.target.closest("#story")) { reset(); paint(STATE); }
  });

  // What is typed is held here, so a redraw of the story never loses it.
  document.addEventListener("input", e => {
    if (e.target.id === "fixnote") FIX.note = e.target.value;
    if (e.target.id === "fixtext") FIX.text = e.target.value;
    const E = FIX.engine, id = e.target.dataset && e.target.dataset.ennote;
    if (E && id && E.marks[id]) E.marks[id].note = e.target.value;
  });

  // A kind picked: the Log button may wake, so the slip is drawn again.
  document.addEventListener("change", e => {
    const E = FIX.engine, id = e.target.dataset && e.target.dataset.enkind;
    if (!E || !id || !E.marks[id]) return;
    E.marks[id].kind = e.target.value;
    paint(STATE);
    const back = document.querySelector(`#story .fixpanel [data-enkind="${CSS.escape(id)}"]`);
    if (back) back.focus({ preventScroll: true });
  });

  onRender(s => paint(s));
})();
