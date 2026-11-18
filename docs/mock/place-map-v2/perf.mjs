// Frame rate and GPU memory of the mocks, measured in a headless Chrome on the real GPU while
// Ollama holds its model. Mock tooling only.
//
//   node perf.mjs            (with the mocks served on http://localhost:8980)
//
// GPU memory: Windows (WDDM) will not give per-process figures to nvidia-smi, so the number is
// the card's total in use, sampled before the browser starts and while each page runs; the
// difference is what the page costs. Another session's Ollama traffic moves it a little.
import { spawn, execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const PORT = 9333, BASE = "http://localhost:8980/";
const sleep = ms => new Promise(r => setTimeout(r, ms));
const gpu = () => { const [used, util] = execFileSync("nvidia-smi", ["--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits"]).toString().trim().split(",").map(Number); return { used, util }; };

const baseline = []; for (let i = 0; i < 5; i++) { baseline.push(gpu()); await sleep(400); }
const prof = mkdtempSync(join(tmpdir(), "mapperf-"));
const proc = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${prof}`, "--window-size=1280,800",
  "--enable-gpu", "--ignore-gpu-blocklist", "--use-angle=d3d11", "--disable-background-timer-throttling", "--disable-renderer-backgrounding", "about:blank"], { stdio: "ignore" });
let ws = null;
for (let i = 0; i < 40 && !ws; i++) { await sleep(250); try { const t = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); const p = t.find(x => x.type === "page"); if (p) ws = new WebSocket(p.webSocketDebuggerUrl); } catch {} }
await new Promise(r => ws.addEventListener("open", r));
let id = 0; const wait = new Map();
ws.addEventListener("message", ev => { const m = JSON.parse(ev.data); if (wait.has(m.id)) { wait.get(m.id)(m); wait.delete(m.id); } });
const cdp = (method, params = {}) => new Promise(r => { const n = ++id; wait.set(n, r); ws.send(JSON.stringify({ id: n, method, params })); });
const evalJs = async expr => (await cdp("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value;

// Count frames for `ms`: the median and worst frame time say more than an average.
const FRAMES = ms => `new Promise(res => { const t = []; let last = performance.now(); const end = last + ${ms};
  const f = now => { t.push(now - last); last = now; if (now < end) requestAnimationFrame(f); else { t.sort((a, b) => a - b);
    res({ fps: Math.round(t.length / (${ms} / 1000)), p50: +t[t.length >> 1].toFixed(1), p95: +t[Math.floor(t.length * .95)].toFixed(1), worst: +t[t.length - 1].toFixed(1) }); } };
  requestAnimationFrame(f); })`;

const out = { gpuName: execFileSync("nvidia-smi", ["--query-gpu=name", "--format=csv,noheader"]).toString().trim(),
  ollama: await (await fetch("http://localhost:11434/api/ps")).json().then(j => j.models.map(m => `${m.name} ${(m.size_vram / 2 ** 30).toFixed(2)} GiB`)).catch(() => "unreachable"),
  baselineMiB: Math.round(baseline.reduce((s, b) => s + b.used, 0) / baseline.length), baselineUtil: baseline.map(b => b.util), pages: [] };
await cdp("Page.enable"); await cdp("Runtime.enable");
const PAGES = process.argv.slice(2);
for (const page of PAGES.length ? PAGES : ["chart.html", "diorama.html", "tabletop.html", "tabletop.html?level=region", "tabletop.html?level=site&site=sewers", "tabletop.html?hour=21&rain=1"]) {
  // Bracket each page with a blank page, so other processes' drift is not charged to it.
  const blank = async () => { await cdp("Page.navigate", { url: "about:blank" }); await sleep(2500); const b = []; for (let i = 0; i < 6; i++) { b.push(gpu().used); await sleep(300); } return b.reduce((x, y) => x + y) / b.length; };
  const before = await blank();
  await cdp("Page.navigate", { url: BASE + page }); await sleep(5000);
  const mem = []; const sampler = setInterval(() => mem.push(gpu()), 500);
  const frames = await evalJs(FRAMES(8000));
  clearInterval(sampler);
  const renderer = await evalJs(`(() => { try { const g = document.createElement('canvas').getContext('webgl2'); const d = g.getExtension('WEBGL_debug_renderer_info'); return g.getParameter(d.UNMASKED_RENDERER_WEBGL); } catch (e) { return String(e); } })()`);
  const info = await evalJs("window.__perf ? window.__perf() : null");
  const after = await blank(), during = mem.reduce((x, m) => x + m.used, 0) / mem.length;
  out.pages.push({ page, ...frames, gpuMiB: Math.round(during), deltaMiB: Math.round(during - (before + after) / 2), blankMiB: [Math.round(before), Math.round(after)],
                   gpuUtil: Math.round(mem.reduce((s, m) => s + m.util, 0) / mem.length), renderer, three: info });
}
ws.close(); proc.kill();
console.log(JSON.stringify(out, null, 1));
