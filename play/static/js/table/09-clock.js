// The play table, part 09 of 10 (clock). Classic script, sharing one global scope with
// 01-08 and 10.
//
// Time passing, shown (playtest item 18; docs/design-f-ui.md §4.3; owner Q45): "a clock
// unmarked but by black strips, with the hour hand on the approximate before-action time
// and then the minute hand spinning vigorously while the hour hand moves to the current
// time… only for 1h+ time changes."
//
// - It fires only on the render that answers THIS page's own successful POST (02's
//   `post()` dispatches `table:posted` with the clock it held). Never on load, never on a
//   resync from the other device, never on a reconnect: none of those pass through
//   `post()`. So no server field is needed (the plan's `clock_minutes_before` was dropped).
// - Twelve identical black strips on a brass face, no numerals; the hour hand is capped at
//   two whole turns and the minute hand at fourteen (about six turns a second at the
//   peak, far below the thirty a 60Hz screen needs before a hand reads as turning
//   backwards: the wagon-wheel effect); both always go forward, never the short way back.
// - A fixed four seconds whatever the span, under WCAG 2.2.2's five; it never takes focus,
//   lets every click through but one on the face (which dismisses it, as Esc does), and
//   waits while a dice mat is open. At a day or more a caption says so in words.
// - Reduced motion: no spin and no scale; the end face with a gold arc on the bezel from
//   the old hour to the new, for 1.6s.

const CLOCK = { armed: null, timers: [], raf: 0, waiting: 0 };
const CLOCK_STILL = window.matchMedia
  ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
// Fade in, hold the old time, sweep, hold the new, fade out: 4.0s in all.
const CLOCK_MS = { fadeIn: 200, holdBefore: 300, sweep: 2200, holdAfter: 900, fadeOut: 400,
                   still: 1600 };

document.addEventListener("table:posted", e => {
  const before = e.detail ? e.detail.clockBefore : null;
  if (typeof before !== "number") return;
  CLOCK.armed = before;
  // The answer to a post is drawn in the same task (`render(await post(...))`); a timer
  // runs after it. So a post that is never drawn — the die's face — cannot leave the
  // clock armed for whatever renders next, which might be the other device's turn.
  setTimeout(() => { CLOCK.armed = null; }, 0);
});

// The hands' travel for a span of `delta` minutes, always forward (§4.3). Up to twelve
// hours the two are coupled exactly; past it the hour hand makes whole turns, at most
// two, then goes on to its true end, and the minute hand at most fourteen.
function clockTravel(before, delta) {
  const hour0 = (before % 720) / 2, minute0 = (before % 60) * 6;
  const hour = delta <= 720 ? delta / 2
    : Math.min(Math.floor(delta / 720), 2) * 360 + (delta % 720) / 2;
  const minute = delta <= 720 ? delta * 6
    : Math.min(Math.floor(delta / 60), 14) * 360 + (delta % 60) * 6;
  return { hour0, minute0, hour, minute };
}

const CLOCK_NUMBERS = ["", "one", "two", "three", "four", "five", "six", "seven", "eight",
  "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
  "seventeen", "eighteen", "nineteen", "twenty", "twenty-one", "twenty-two",
  "twenty-three"];

// Calendar days crossed, in words ("Two days later"), not elapsed hours: an evening to
// the next morning is "The next day" however few hours it took.
function clockCaption(before, after) {
  const days = Math.floor(after / 1440) - Math.floor(before / 1440);
  if (days <= 0) return "";
  if (days === 1) return "The next day";
  if (days <= 13) return `${capFirstWord(CLOCK_NUMBERS[days])} days later`;
  if (days <= 20) return "Two weeks later";
  if (days <= 27) return "Three weeks later";
  return "Some weeks later";   // the resurrect card's own words
}

function capFirstWord(t) { return t ? t[0].toUpperCase() + t.slice(1) : t; }

// One sentence for a screen reader: "Three hours pass. It is now evening."
function clockSentence(before, after, part) {
  const delta = after - before;
  const hours = Math.round(delta / 60);
  const lead = delta >= 1440 ? `${clockCaption(before, after)}.`
    : hours <= 1 ? "An hour passes."
    : `${capFirstWord(CLOCK_NUMBERS[Math.min(hours, 23)])} hours pass.`;
  return part ? `${lead} It is now ${part}.` : lead;
}

const clockEase = p => (p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
const clockEaseRate = p => (p < .5 ? 12 * p * p : 3 * Math.pow(-2 * p + 2, 2));

function clockPoint(r, deg) {
  const a = deg * Math.PI / 180;
  return [100 + r * Math.sin(a), 100 - r * Math.cos(a)];
}

function clockFaceSvg() {
  const strips = Array.from({ length: 12 }, (_, i) =>
    `<rect x="97" y="22" width="6" height="16" rx="1" fill="#0b0806"
       transform="rotate(${i * 30} 100 100)"/>`).join("");
  // The bezel wears the aside's own gold frame, stop for stop; the face is the brass of
  // the hit-point bar (--gold into #8a6f3e). No new colour.
  return `<svg viewBox="0 0 200 200" aria-hidden="true" focusable="false">
    <defs>
      <linearGradient id="clk-bezel" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#f0d9a0"/><stop offset=".16" stop-color="#b98f4e"/>
        <stop offset=".42" stop-color="#6b4f28"/><stop offset=".6" stop-color="#3a2c17"/>
        <stop offset=".86" stop-color="#c9a86a"/><stop offset="1" stop-color="#f4e3b2"/>
      </linearGradient>
      <radialGradient id="clk-face" cx=".42" cy=".36" r=".75">
        <stop offset="0" stop-color="#ddc48e"/><stop offset="1" stop-color="#8a6f3e"/>
      </radialGradient>
    </defs>
    <circle cx="100" cy="100" r="94" fill="url(#clk-bezel)"/>
    <circle cx="100" cy="100" r="86" fill="url(#clk-face)" stroke="#3a2c17" stroke-width="1.5"/>
    ${strips}
    <path class="clk-arc" d="" fill="none" stroke="#f0c070" stroke-width="4"
          stroke-linecap="round" opacity="0"/>
    <g class="clk-minute">
      <path class="clk-smear" d="M100 100 L100 32 A68 68 0 0 0 66 41.1 Z" fill="#0b0806"
            opacity="0"/>
      <path d="M98 110 L102 110 L101 34 L100 30 L99 34 Z" fill="#0b0806"
            stroke="#ddc48e" stroke-width="1"/>
    </g>
    <g class="clk-hour">
      <path d="M96.5 108 L103.5 108 L101.8 57 L100 53 L98.2 57 Z" fill="#0b0806"
            stroke="#ddc48e" stroke-width="1"/>
    </g>
    <circle cx="100" cy="100" r="5" fill="#0b0806" stroke="#ddc48e" stroke-width="1"/>
  </svg><div class="clockcap" hidden></div>`;
}

function clockStop() {
  CLOCK.timers.forEach(clearTimeout);
  CLOCK.timers = [];
  if (CLOCK.raf) cancelAnimationFrame(CLOCK.raf);
  CLOCK.raf = 0;
  if (CLOCK.waiting) clearInterval(CLOCK.waiting);
  CLOCK.waiting = 0;
}

function clockHide() {
  clockStop();
  const pop = document.getElementById("clockpop");
  if (!pop) return;
  pop.classList.remove("on", "going");
  pop.hidden = true;
}

function clockLater(ms, fn) { CLOCK.timers.push(setTimeout(fn, ms)); }

function clockShow(before, after, part) {
  const pop = document.getElementById("clockpop");
  if (!pop) return;
  clockStop();
  if (!pop.querySelector("svg")) pop.innerHTML = clockFaceSvg();
  const hourG = pop.querySelector(".clk-hour"), minuteG = pop.querySelector(".clk-minute");
  const smear = pop.querySelector(".clk-smear"), arc = pop.querySelector(".clk-arc");
  const cap = pop.querySelector(".clockcap");
  const delta = after - before;
  const t = clockTravel(before, delta);
  const set = (h, m) => {
    hourG.setAttribute("transform", `rotate(${h} 100 100)`);
    minuteG.setAttribute("transform", `rotate(${m} 100 100)`);
  };
  const caption = delta >= 1440 ? clockCaption(before, after) : "";
  cap.textContent = caption ? (part ? `${caption}, ${part}` : caption) : "";
  cap.hidden = !caption;
  const say = document.getElementById("clocksay");
  if (say) say.textContent = clockSentence(before, after, part);
  smear.setAttribute("opacity", "0");
  pop.classList.remove("going");
  pop.hidden = false;

  if (CLOCK_STILL && CLOCK_STILL.matches) {
    // Still: the end face, and the ground the hour hand covered drawn as an arc.
    set(t.hour0 + t.hour, t.minute0 + t.minute);
    const sweep = delta >= 720 ? 359.9 : t.hour;
    const [x0, y0] = clockPoint(90, t.hour0), [x1, y1] = clockPoint(90, t.hour0 + sweep);
    arc.setAttribute("d", `M${x0.toFixed(2)} ${y0.toFixed(2)} A90 90 0 ${
      sweep > 180 ? 1 : 0} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`);
    arc.setAttribute("opacity", "1");
    pop.classList.add("on");
    clockLater(CLOCK_MS.still, clockHide);
    return;
  }
  arc.setAttribute("opacity", "0");
  set(t.hour0, t.minute0);
  const hand = minuteG.lastElementChild;
  hand.setAttribute("opacity", "1");
  void pop.offsetWidth;               // so the fade starts from nothing
  pop.classList.add("on");
  clockLater(CLOCK_MS.fadeIn + CLOCK_MS.holdBefore, () => {
    const start = performance.now();
    let last = t.minute0;
    const frame = now => {
      const p = Math.min(1, (now - start) / CLOCK_MS.sweep);
      const e = clockEase(p);
      const minute = t.minute0 + t.minute * e;
      set(t.hour0 + t.hour * e, minute);
      // Above two turns a second a lone hand strobes; a faint wedge behind it reads as
      // motion instead. And on a machine slow enough that one frame carries the hand past
      // 150 degrees, the hand itself fades into the wedge: sampled that coarsely, a sharp
      // hand reads as turning backwards (the wagon-wheel effect). Headless Edge ran this at
      // about 20 frames a second and stepped 427 degrees in one.
      const revs = (t.minute / 360) * clockEaseRate(p) / (CLOCK_MS.sweep / 1000);
      smear.setAttribute("opacity", revs > 2 ? ".25" : "0");
      hand.setAttribute("opacity", minute - last > 150 ? ".35" : "1");
      last = minute;
      if (p < 1) { CLOCK.raf = requestAnimationFrame(frame); return; }
      CLOCK.raf = 0;
      smear.setAttribute("opacity", "0");
      hand.setAttribute("opacity", "1");
      clockLater(CLOCK_MS.holdAfter, () => {
        pop.classList.add("going");
        clockLater(CLOCK_MS.fadeOut, clockHide);
      });
    };
    CLOCK.raf = requestAnimationFrame(frame);
  });
}

// A die's mat is the player's to close; the clock waits its turn rather than landing on
// top of the number they are reading. A minute at most, then it is let go.
function clockWhenClear(before, after, part) {
  clockStop();
  const matOpen = () => !!document.querySelector("#d3d-mat.on");
  if (!matOpen()) { clockShow(before, after, part); return; }
  const since = Date.now();
  CLOCK.waiting = setInterval(() => {
    if (matOpen() && Date.now() - since < 60000) return;
    clearInterval(CLOCK.waiting);
    CLOCK.waiting = 0;
    if (!matOpen() && !document.hidden) clockShow(before, after, part);
  }, 200);
}

onRender(function clockFace(s, prev) {
  // Spent by whichever draw comes first after the post, so it can never carry over to a
  // later one; and the first draw (`prev === null`) is never a turn this page took.
  const before = CLOCK.armed;
  CLOCK.armed = null;
  if (!prev || before === null) return;
  const after = s && s.scene ? s.scene.clock_minutes : null;
  if (typeof after !== "number" || after - before < 60) return;
  // A page nobody is looking at does not play a four-second animation to nobody.
  if (document.hidden) return;
  clockWhenClear(before, after, (s.scene && s.scene.day_part) || "");
});

document.addEventListener("click", e => {
  if (e.target.closest && e.target.closest("#clockpop svg")) clockHide();
});
document.addEventListener("keydown", e => {
  const pop = document.getElementById("clockpop");
  if (e.key === "Escape" && pop && !pop.hidden) clockHide();
});
