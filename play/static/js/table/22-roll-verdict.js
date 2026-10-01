// The play table, part 22 (the roll's verdict, shown). Classic script, sharing one global
// scope.
//
// The owner, 2026-10-01: "I would like to have a success or Failure animation play after
// rolling the D20 success with confetti maybe and something for failure." And, seeing the
// first pass: "make the success word big and bold and pop up over top of the die", "like a
// 3d object the success words should be".
//
// WHERE THE VERDICT COMES FROM. `/api/roll` answers with `verdict`: the engine's own
// judgement of the face the player sent (`Engine._judge`, play/views.py `roll`), as
// {verdict: "success"|"failure", natural}, or null for a die nobody calls a success
// (damage, initiative, a forage run). Nothing here compares a total with a number to beat,
// and nothing here reads `dc`: on an opposed check that number is the other side's secret
// die and is never sent to the popup (`dc_shown`). The page is told success or failure
// once the server has decided, and that is all it is told.
//
// HOW IT LOOKS. The word is the centrepiece: cast in the die's own brass, extruded like
// the die is (the lamp high and left, the depth falling down and right, as theme-v2.css's
// shadows do), popping up out of the mat over the die on a small perspective tilt as if
// it stood on the table. A failure is the same letter in the die's fumble red over soot,
// heavier, and it drops and lands rather than rising. Round the word, gilt foil and candle
// sparks thrown off the die's rim for a success: the die is cast brass on a leather mat,
// and rainbow party confetti on that table read as a sticker on a book. A failure is
// restrained: a few embers gutter and fall, the light round the die dims for a breath; a
// candle going low, not a sad trombone. A natural 20 earns the larger burst and a ring of
// light; a natural 1 adds a hairline crack across the die. The tiers follow Dice So Nice's
// three confetti strengths and its separate dark animation for a fumble; "Dramatic Rolls"
// keys the same effects to the degree of success rather than the face alone, which is why
// the verdict decides and the face only scales it.
//
// WHAT IT MAY NOT DO (the owner's standing rule: no motion that makes a menu harder to
// use). Nothing waits on it: `sendRoll` does not await it. It takes no clicks (word and
// canvas are `pointer-events: none`), moves nothing on the page (both are fixed), sits
// over the die and not over the mat's Close button, and is gone in at most 1.3s. BG3's
// players asked for a way to skip its success and failure animations, because there the
// next action waits; here it never does. Reduced motion: no particles and no pop; the
// word, still, for a moment.

const VERDICT_STILL = window.matchMedia
  ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
// The whole of each flourish, start to gone. All well under 1.5s.
const VERDICT_MS = { success: 1150, triumph: 1300, failure: 1050, calamity: 1200, still: 1200 };
// The sentence for the mat's own verdict line, which stays while the mat is open.
const VERDICT_WORDS = {
  success: "Success", triumph: "Success on a natural 20",
  failure: "Failure", calamity: "Failure on a natural 1",
};

// Which flourish a server verdict earns, or null for none. Pure, so node can hold it.
// `natural` only scales a verdict the engine already gave: a 20 on a skill check that
// still missed is a failure (1e excludes skill checks from the natural-20 rule), and it
// gets the failure flourish, not a triumph.
function verdictFlourish(v, still) {
  if (!v || typeof v !== "object") return null;
  if (v.verdict !== "success" && v.verdict !== "failure") return null;
  const good = v.verdict === "success";
  const kind = good ? (v.natural === 20 ? "triumph" : "success")
                    : (v.natural === 1 ? "calamity" : "failure");
  return { kind, good, text: VERDICT_WORDS[kind], still: !!still,
           word: good ? "Success" : "Failure",
           sub: kind === "triumph" ? "natural 20" : kind === "calamity" ? "natural 1" : "",
           ms: still ? VERDICT_MS.still : VERDICT_MS[kind] };
}

// Where the word stands when the mat no longer shows the die: over the book, where the
// reply is about to be read, else the window's middle. Not the Rolls panel: a word this
// size in the sidebar would sit over the panels' own controls.
function verdictOrigin() {
  const story = document.getElementById("story");
  if (story && story.getClientRects().length) {
    const r = story.getBoundingClientRect();
    if (r.width > 1 && r.bottom > 0 && r.top < innerHeight) {
      return { x: r.left + r.width / 2, y: r.top + Math.min(r.height / 2, 140) };
    }
  }
  return { x: innerWidth / 2, y: innerHeight * 0.42 };
}

// Play the verdict of the roll whose die is settling in `rest` (Dice3D.settled(), taken
// when that die was thrown). Returns what it chose, for probes; nobody awaits it.
async function showVerdict(v, rest) {
  const f = verdictFlourish(v, VERDICT_STILL && VERDICT_STILL.matches);
  if (!f) return null;
  // Never over a die still in the air: the verdict would spoil the landing it is about.
  let id = null;
  try { id = rest ? await rest : null; } catch { id = null; }
  const mat = id != null && window.Dice3D && typeof Dice3D.mark === "function"
    ? Dice3D.mark(id, f) : null;
  const at = mat ? { x: mat.left + mat.width / 2, y: mat.top + mat.height / 2 }
                 : verdictOrigin();
  verdictWord(f, at, mat ? mat.width : 0);
  if (!f.still) {
    VerdictSparks.burst(f.kind, at.x, at.y, f.ms,
                        mat ? Math.min(mat.width, mat.height) * 0.46 : 0);
  }
  return f;
}

// The word, as a cast object (table.html `.rv-word`). The letters are drawn twice from one
// string: the element's own text carries the extrusion as stacked shadows, and its
// `::after` lays the lit brass face over it with `background-clip: text`. One layer cannot
// do both, because a clipped background shows the text-shadow through the face.
function verdictWord(f, at, span) {
  document.querySelectorAll(".rv-word").forEach(el => el.remove());
  const el = document.createElement("div");
  el.className = "rv-word " + (f.good ? "is-good" : "is-bad") +
    (f.sub ? " is-strong" : "");
  el.setAttribute("role", "status");
  el.setAttribute("aria-label", f.text);
  const w = document.createElement("span");
  w.className = "rv-w";
  w.setAttribute("data-text", f.word);
  w.textContent = f.word;
  el.appendChild(w);
  if (f.sub) {
    const s = document.createElement("span");
    s.className = "rv-sub";
    s.textContent = f.sub;
    el.appendChild(s);
  }
  // Sized to the die it stands over when there is one, never past the window's edges.
  if (span) el.style.setProperty("--rv-size", Math.round(Math.max(40, Math.min(76, span * 0.3))) + "px");
  el.style.left = Math.round(Math.max(150, Math.min(innerWidth - 150, at.x))) + "px";
  el.style.top = Math.round(Math.max(50, Math.min(innerHeight - 50, at.y))) + "px";
  document.body.appendChild(el);
  if (f.still || typeof el.animate !== "function") {
    setTimeout(() => el.remove(), f.ms);
    return;
  }
  // Eased per keyframe, not over the whole: an easing on the animation itself warps the
  // offsets, and measured at 450ms of 1050 a word was already fading (opacity .44) inside
  // what was written as its hold.
  const P = "translate(-50%, -50%) perspective(640px)";
  const frames = f.good ? [
    // Up out of the mat, tipped back, overshooting, then standing a little reclined.
    { opacity: 0, transform: `${P} translateY(26px) rotateX(72deg) scale(.5)`,
      easing: "cubic-bezier(.2,.9,.3,1.2)" },
    { opacity: 1, transform: `${P} translateY(-10px) rotateX(-8deg) scale(1.1)`, offset: 0.2,
      easing: "ease-out" },
    { opacity: 1, transform: `${P} translateY(0) rotateX(12deg) scale(1)`, offset: 0.34 },
    { opacity: 1, transform: `${P} translateY(-4px) rotateX(12deg) scale(1)`, offset: 0.76,
      easing: "ease-in" },
    { opacity: 0, transform: `${P} translateY(-22px) rotateX(16deg) scale(1.03)` },
  ] : [
    // Dropped from above, heavy: it lands, sinks a hair, and settles.
    { opacity: 0, transform: `${P} translateY(-40px) rotateX(-34deg) scale(1.18)`,
      easing: "cubic-bezier(.55,0,.9,.5)" },
    { opacity: 1, transform: `${P} translateY(4px) rotateX(16deg) scale(.97)`, offset: 0.2,
      easing: "ease-out" },
    { opacity: 1, transform: `${P} translateY(0) rotateX(14deg) scale(1)`, offset: 0.3 },
    { opacity: 1, transform: `${P} translateY(0) rotateX(14deg) scale(1)`, offset: 0.76,
      easing: "ease-in" },
    { opacity: 0, transform: `${P} translateY(10px) rotateX(20deg) scale(.98)` },
  ];
  el.animate(frames, { duration: f.ms, fill: "forwards" })
    .finished.catch(() => {}).then(() => el.remove());
}

// The particles. One fixed canvas, made on first use, hidden whenever nothing is in the
// air; one requestAnimationFrame loop that stops itself when the last particle is gone,
// so an idle table costs nothing. At most ~130 particles, all plain 2D fills.
const VerdictSparks = (() => {
  // The die's landed brass, its bevel light, and the theme's candle cream.
  const GILT = ["#d8ae57", "#e3c485", "#c8a75f", "#bb9440", "#f0dcae", "#9d7c39"];
  const SPARK = ["#fff2c8", "#f0dcae", "#ffe3a3"];
  // The die's fumble ramp, then the ash an ember becomes.
  const EMBER = ["#e79a86", "#c46c58", "#d9776b"];
  let cv = null, cx = null, parts = [], marks = [], raf = 0, last = 0;

  function layer() {
    if (cv) return;
    cv = document.createElement("canvas");
    cv.id = "rv-layer";
    cv.setAttribute("aria-hidden", "true");
    document.body.appendChild(cv);
    cx = cv.getContext("2d");
  }

  function fit() {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = Math.round(innerWidth * dpr), h = Math.round(innerHeight * dpr);
    if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; }
    cx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  const rnd = (a, b) => a + Math.random() * (b - a);
  const pick = list => list[(Math.random() * list.length) | 0];

  // `r` is the die's own radius when the burst comes off the mat, so the flecks leave
  // from its rim: gilt drawn over the brass die itself vanished into it (measured on the
  // first screenshot, 2026-10-01: a 240ms frame showed the burst only as a smudge on
  // the die's face). Off the mat it is a small knot round a point.
  function burst(kind, x, y, ms, r) {
    layer();
    if (!cx) return;
    fit();
    cv.style.display = "block";
    const life = ms / 1000;
    const R = Math.max(10, r || 14);
    if (kind === "success" || kind === "triumph") {
      const big = kind === "triumph";
      const foil = big ? 96 : 44, sparks = big ? 36 : 16;
      for (let i = 0; i < foil; i++) {
        // Thrown up and out from the upper rim, wider for a triumph. Light gravity under
        // heavy drag: foil falls at about 140px/s at most (g / drag), so it hangs at the
        // top of its throw and drifts, rather than dropping like shot. With g 820 it fell
        // at 315px/s and was back on the die inside 400ms (measured, first pass).
        const a = -Math.PI / 2 + rnd(-1, 1) * (big ? 1.35 : 1.05);
        const v = rnd(380, big ? 940 : 760);
        parts.push({ k: "foil", x: x + Math.cos(a) * R * rnd(0.8, 1),
                     y: y + Math.sin(a) * R * rnd(0.8, 1),
                     vx: Math.cos(a) * v, vy: Math.sin(a) * v, g: 340, drag: 2.4,
                     w: rnd(4, 8), h: rnd(2, 4), rot: rnd(0, 6.28),
                     spin: rnd(-12, 12), flip: rnd(6, 16), c: pick(GILT),
                     t: 0, life: life * rnd(0.75, 1) });
      }
      for (let i = 0; i < sparks; i++) {
        const a = rnd(0, Math.PI * 2), v = rnd(90, big ? 420 : 300);
        parts.push({ k: "spark", x: x + Math.cos(a) * R, y: y + Math.sin(a) * R,
                     vx: Math.cos(a) * v, vy: Math.sin(a) * v - 80,
                     g: 160, drag: 3.2, r: rnd(1.2, 2.6), c: pick(SPARK),
                     t: 0, life: life * rnd(0.4, 0.7) });
      }
      if (big) marks.push({ k: "ring", x, y, r0: R, t: 0, life: Math.min(0.6, life * 0.5) });
    } else {
      const bad = kind === "calamity";
      marks.push({ k: "dim", x, y, r0: R, t: 0, life: life * 0.85 });
      // Across the die's lower half: through its middle it ran behind the word.
      if (bad) {
        marks.push({ k: "crack", x, y, t: 0, life, path: crackPath(x, y + R * 0.42, R * 0.8) });
      }
      const n = bad ? 22 : 12;
      for (let i = 0; i < n; i++) {
        // Off the lower half of the rim, falling: a wick's last sparks, not a spray.
        const a = rnd(0.15, Math.PI - 0.15);
        parts.push({ k: "ember", x: x + Math.cos(a) * R * rnd(0.6, 1),
                     y: y + Math.sin(a) * R * rnd(0.5, 0.95),
                     vx: rnd(-22, 22), vy: rnd(10, 60), g: 70, drag: 0.6,
                     r: rnd(1.4, 2.6), c: pick(EMBER), t: 0, life: life * rnd(0.6, 0.95) });
      }
    }
    if (!raf) { last = performance.now(); raf = requestAnimationFrame(frame); }
  }

  // A jagged hairline through the point, as the die's numbers are cut: a dark groove
  // with a lit edge.
  function crackPath(x, y, R) {
    // Inside the die's silhouette: drawn past it, onto the mat, it read as a scratch on
    // the screen rather than a crack in the die (first pass, R * 1.1).
    const pts = [], half = Math.max(40, R * 0.72), steps = 9;
    for (let i = 0; i <= steps; i++) {
      pts.push([x - half + (2 * half * i) / steps, y + rnd(-7, 7) + (i - steps / 2) * 1.4]);
    }
    return pts;
  }

  function frame(now) {
    // Age runs on the wall clock, so a flourish is gone on time however few frames the
    // machine manages (measured 9 a second in a throttled pane: a capped age had it
    // last twice as long). Only the motion is stepped in capped slices, so a long gap
    // cannot fling a flake off the screen in one step.
    const age = Math.max(0, (now - last) / 1000);
    const dt = Math.min(0.05, age);
    last = now;
    cx.clearRect(0, 0, innerWidth, innerHeight);

    marks = marks.filter(m => (m.t += age) < m.life);
    for (const m of marks) {
      const f = m.t / m.life;
      if (m.k === "dim") {
        // A breath of shadow round the die: in fast, out slow.
        const a = 0.34 * (f < 0.2 ? f / 0.2 : 1 - (f - 0.2) / 0.8);
        const reach = Math.max(150, m.r0 * 2.2);
        const g = cx.createRadialGradient(m.x, m.y, 0, m.x, m.y, reach);
        g.addColorStop(0, `rgba(12,7,3,${a})`);
        g.addColorStop(1, "rgba(12,7,3,0)");
        cx.fillStyle = g;
        cx.fillRect(m.x - reach, m.y - reach, reach * 2, reach * 2);
      } else if (m.k === "ring") {
        const r = m.r0 + 130 * (1 - Math.pow(1 - f, 3));
        cx.strokeStyle = `rgba(240,220,174,${0.55 * (1 - f)})`;
        cx.lineWidth = 2 * (1 - f) + 0.5;
        cx.beginPath(); cx.arc(m.x, m.y, r, 0, Math.PI * 2); cx.stroke();
      } else if (m.k === "crack") {
        // Drawn across in the first eighth, then fades.
        const shown = Math.min(1, f / 0.12);
        const a = f < 0.5 ? 1 : 1 - (f - 0.5) / 0.5;
        const upto = Math.max(1, Math.round(shown * (m.path.length - 1)));
        for (const [dx, dy, col, w] of [[1, 1, `rgba(20,8,4,${0.85 * a})`, 2.2],
                                        [0, 0, `rgba(231,154,134,${0.9 * a})`, 1.1]]) {
          cx.strokeStyle = col; cx.lineWidth = w;
          cx.beginPath();
          cx.moveTo(m.path[0][0] + dx, m.path[0][1] + dy);
          for (let i = 1; i <= upto; i++) cx.lineTo(m.path[i][0] + dx, m.path[i][1] + dy);
          cx.stroke();
        }
      }
    }

    parts = parts.filter(p => (p.t += age) < p.life);
    for (const p of parts) {
      const k = Math.exp(-p.drag * dt);
      p.vx *= k; p.vy = p.vy * k + p.g * dt;
      p.x += p.vx * dt; p.y += p.vy * dt;
      const f = p.t / p.life;
      if (p.k === "foil") {
        p.rot += p.spin * dt;
        // The flake's tumble: its face turns toward and away from the lamp, so it
        // flashes and narrows rather than sliding about as a flat chip.
        const tilt = Math.cos(p.t * p.flip);
        cx.globalAlpha = Math.min(1, (1 - f) * 1.6);
        cx.fillStyle = p.c;
        cx.save();
        cx.translate(p.x, p.y); cx.rotate(p.rot); cx.scale(1, Math.abs(tilt) + 0.15);
        cx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
        cx.restore();
      } else if (p.k === "spark") {
        cx.globalAlpha = 1 - f;
        cx.fillStyle = p.c;
        cx.beginPath(); cx.arc(p.x, p.y, p.r * (1 - f * 0.5), 0, Math.PI * 2); cx.fill();
      } else {
        // An ember: hot, then ash, then gone.
        cx.globalAlpha = (1 - f) * 0.9;
        cx.fillStyle = f < 0.45 ? p.c : "#5a4030";
        cx.beginPath(); cx.arc(p.x, p.y, p.r * (1 - f * 0.4), 0, Math.PI * 2); cx.fill();
      }
    }
    cx.globalAlpha = 1;

    if (parts.length || marks.length) {
      raf = requestAnimationFrame(frame);
    } else {
      raf = 0;
      cx.clearRect(0, 0, innerWidth, innerHeight);
      cv.style.display = "none";
    }
  }

  return { burst, busy: () => parts.length + marks.length };
})();
