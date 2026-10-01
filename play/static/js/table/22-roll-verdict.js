// The play table, part 22 (the roll's verdict, shown). Classic script, sharing one global
// scope.
//
// The owner, 2026-10-01: "I would like to have a success or Failure animation play after
// rolling the D20 success with confetti maybe and something for failure."
//
// WHERE THE VERDICT COMES FROM. `/api/roll` answers with `verdict`: the engine's own
// judgement of the face the player sent (`Engine._judge`, play/views.py `roll`), as
// {verdict: "success"|"failure", natural}, or null for a die nobody calls a success
// (damage, initiative, a forage run). Nothing here compares a total with a number to beat,
// and nothing here reads `dc`: on an opposed check that number is the other side's secret
// die and is never sent to the popup (`dc_shown`). The page is told success or failure
// once the server has decided, and that is all it is told.
//
// HOW IT LOOKS. Gilt foil and candle sparks for a success, thrown up off the die the way
// a struck brass coin throws light: the die is cast brass on a leather mat, and rainbow
// party confetti on that table read as a sticker on a book. The colours are the die's own
// brass ramp (dice3d.js `.f.land`) and the theme's candle cream, so the burst looks like
// it came off the die. A failure is restrained: a few embers gutter and fall, the light
// round the die dims for a breath; it is a candle going low, not a sad trombone. A natural
// 20 earns the larger burst and a ring of light; a natural 1 adds a hairline crack. The
// tiers follow Dice So Nice's three confetti strengths and its separate dark animation for
// a fumble; "Dramatic Rolls" keys the same effects to the degree of success rather than
// the face alone, which is why the verdict decides and the face only scales it.
//
// WHAT IT MAY NOT DO (the owner's standing rule: no motion that makes a menu harder to
// use). Nothing waits on it: `sendRoll` does not await it. It takes no clicks (the layer
// is `pointer-events: none`), moves nothing on the page (a fixed canvas and a fixed
// word), and is over in at most 1.3s. BG3's players asked for a way to skip its success
// and failure animations, because there the next action waits; here it never does.
// Reduced motion: no particles, no movement; the word, still, for a moment.

const VERDICT_STILL = window.matchMedia
  ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
// The whole of each flourish, start to gone. All well under 1.5s.
const VERDICT_MS = { success: 1050, triumph: 1300, failure: 900, calamity: 1100, still: 1200 };
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
           ms: still ? VERDICT_MS.still : VERDICT_MS[kind] };
}

// Where the flourish starts when the mat no longer shows the die: the newest line of the
// Rolls panel if it is on screen, else the middle of the book, else the window's middle.
function verdictOrigin() {
  const onScreen = el => {
    if (!el || !el.getClientRects().length) return null;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.bottom < 0 || r.top > innerHeight) return null;
    return r;
  };
  const r = onScreen(document.querySelector("#rolls > .who")) ||
            onScreen(document.getElementById("story"));
  if (r) return { x: r.left + r.width / 2, y: r.top + Math.min(r.height / 2, 120) };
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
  // On the mat the word goes in the mat's own verdict line and stays while it is open;
  // off it, a small plaque says it near where the eye already is.
  const at = mat ? { x: mat.left + mat.width / 2, y: mat.top + mat.height / 2 }
                 : verdictOrigin();
  if (!mat) verdictSeal(f, at);
  if (!f.still) VerdictSparks.burst(f.kind, at.x, at.y, f.ms);
  return f;
}

// The word, off the mat. Fixed and pointer-events none (table.html `.rv-seal`), so it
// covers nothing a click needs and shifts nothing.
function verdictSeal(f, at) {
  document.querySelectorAll(".rv-seal").forEach(el => el.remove());
  const el = document.createElement("div");
  el.className = "rv-seal " + (f.good ? "is-good" : "is-bad");
  el.setAttribute("role", "status");
  el.textContent = f.text;
  el.style.left = Math.round(Math.max(90, Math.min(innerWidth - 90, at.x))) + "px";
  el.style.top = Math.round(Math.max(30, Math.min(innerHeight - 30, at.y))) + "px";
  document.body.appendChild(el);
  if (f.still || typeof el.animate !== "function") {
    setTimeout(() => el.remove(), f.ms);
    return;
  }
  const lift = f.good ? -14 : 8;
  el.animate([
    { opacity: 0, transform: "translate(-50%, -50%) scale(.92)" },
    { opacity: 1, transform: "translate(-50%, -50%) scale(1)", offset: 0.14 },
    { opacity: 1, transform: "translate(-50%, -50%) scale(1)", offset: 0.7 },
    { opacity: 0, transform: `translate(-50%, calc(-50% + ${lift}px)) scale(1)` },
  ], { duration: f.ms, easing: "cubic-bezier(.2,.7,.3,1)", fill: "forwards" })
    .finished.catch(() => {}).then(() => el.remove());
}

// The particles. One fixed canvas, made on first use, hidden whenever nothing is in the
// air; one requestAnimationFrame loop that stops itself when the last particle is gone,
// so an idle table costs nothing. At most ~120 particles, all plain 2D fills.
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

  function burst(kind, x, y, ms) {
    layer();
    if (!cx) return;
    fit();
    cv.style.display = "block";
    const life = ms / 1000;
    if (kind === "success" || kind === "triumph") {
      const big = kind === "triumph";
      const foil = big ? 78 : 34, sparks = big ? 34 : 14;
      for (let i = 0; i < foil; i++) {
        // A fan thrown upward, wider for a triumph.
        const a = -Math.PI / 2 + rnd(-1, 1) * (big ? 1.25 : 0.95);
        const v = rnd(240, big ? 680 : 520);
        parts.push({ k: "foil", x: x + rnd(-10, 10), y: y + rnd(-6, 6),
                     vx: Math.cos(a) * v, vy: Math.sin(a) * v, g: 980, drag: 1.6,
                     w: rnd(3, 6.5), h: rnd(1.6, 3.2), rot: rnd(0, 6.28),
                     spin: rnd(-12, 12), flip: rnd(6, 16), c: pick(GILT),
                     t: 0, life: life * rnd(0.75, 1) });
      }
      for (let i = 0; i < sparks; i++) {
        const a = rnd(0, Math.PI * 2), v = rnd(60, big ? 380 : 260);
        parts.push({ k: "spark", x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 80,
                     g: 160, drag: 3.2, r: rnd(0.9, 2.2), c: pick(SPARK),
                     t: 0, life: life * rnd(0.4, 0.7) });
      }
      if (big) marks.push({ k: "ring", x, y, t: 0, life: Math.min(0.6, life * 0.5) });
    } else {
      const bad = kind === "calamity";
      marks.push({ k: "dim", x, y, t: 0, life: life * 0.85 });
      if (bad) marks.push({ k: "crack", x, y, t: 0, life, path: crackPath(x, y) });
      const n = bad ? 22 : 12;
      for (let i = 0; i < n; i++) {
        parts.push({ k: "ember", x: x + rnd(-28, 28), y: y + rnd(-16, 8),
                     vx: rnd(-22, 22), vy: rnd(10, 60), g: 70, drag: 0.6,
                     r: rnd(1.2, 2.4), c: pick(EMBER), t: 0, life: life * rnd(0.6, 0.95) });
      }
    }
    if (!raf) { last = performance.now(); raf = requestAnimationFrame(frame); }
  }

  // A jagged hairline through the point, as the die's numbers are cut: a dark groove
  // with a lit edge.
  function crackPath(x, y) {
    const pts = [], half = 70, steps = 9;
    for (let i = 0; i <= steps; i++) {
      pts.push([x - half + (2 * half * i) / steps, y + rnd(-7, 7) + (i - steps / 2) * 1.4]);
    }
    return pts;
  }

  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    cx.clearRect(0, 0, innerWidth, innerHeight);

    marks = marks.filter(m => (m.t += dt) < m.life);
    for (const m of marks) {
      const f = m.t / m.life;
      if (m.k === "dim") {
        // A breath of shadow round the die: in fast, out slow.
        const a = 0.34 * (f < 0.2 ? f / 0.2 : 1 - (f - 0.2) / 0.8);
        const g = cx.createRadialGradient(m.x, m.y, 0, m.x, m.y, 150);
        g.addColorStop(0, `rgba(12,7,3,${a})`);
        g.addColorStop(1, "rgba(12,7,3,0)");
        cx.fillStyle = g;
        cx.fillRect(m.x - 150, m.y - 150, 300, 300);
      } else if (m.k === "ring") {
        const r = 18 + 130 * (1 - Math.pow(1 - f, 3));
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

    parts = parts.filter(p => (p.t += dt) < p.life);
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
