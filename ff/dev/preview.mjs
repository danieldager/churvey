// Visual-iteration harness: opens the popup with a mocked `browser` API and
// realistic mid-run data, then screenshots light + dark to ff/dev/shots/.
// Usage: node preview.mjs   (needs `npx playwright install chromium` once)
import { chromium } from "playwright";
import { fileURLToPath } from "url";
import path from "path";

const here = path.dirname(fileURLToPath(import.meta.url));
const popup = "file://" + path.join(here, "..", "src", "popup", "popup.html");

const QIDS = ["P1","P2","P3","P4","P5","P6","P7","P8","16.2","16.3","16.4","16.5","16.6","16.7","16.8"];
const mkItems = (okTo, errAt = [], runAt = null) => {
  const items = [];
  for (let r = 0; r < 3; r++) for (let i = 0; i < 15; i++) {
    const n = r * 15 + i;
    const k = `neutral#r${r}#${QIDS[i]}`;
    let s = "idle";
    if (n < okTo) s = "ok";
    if (errAt.includes(n)) s = "err";
    if (n === runAt) s = "run";
    items.push({ k, q: QIDS[i], r, s, n: s === "err" ? 2 : 0, in: s === "err" ? 40 : 0,
                 e: s === "err" ? "Too many requests" : null });
  }
  return items;
};
const OVERVIEW = {
  ok: true, status: "running", recordCount: 117, canResume: false,
  perProvider: {
    gemini:   { total: 45, ok: 37, error: 2, inflight: false, items: mkItems(37, [3, 18]) },
    grok:     { total: 45, ok: 30, error: 9, inflight: true,  items: mkItems(30, [31,32,33,34,35,36,37,38,39], 30) },
    deepseek: { total: 45, ok: 39, error: 0, inflight: false, items: mkItems(39) },
  },
};
const RUNS = { ok: true, runs: [
  { runId: "run_2026-07-11T12-21-35-319Z", providers: ["gemini","grok","deepseek"], repetitions: 3, questions: 15, expected: 45, ok: 106, total: 135, active: true, running: true },
  { runId: "run_2026-07-10T04-45-08-383Z", providers: ["chatgpt","claude"], repetitions: 2, questions: 15, expected: 30, ok: 60, total: 60, active: false, running: false },
]};
const LOG = [
  "2026-07-11T13:02:11Z [runner] INFO: [grok] submitted neutral#r2#P1 (vis=visible)",
  "2026-07-11T13:02:40Z [runner] WARN: [grok] neutral#r2#P1 failed (attempt 2): Too many requests — re-asking in 60s",
  "2026-07-11T13:03:05Z [runner] INFO: [deepseek] recorded neutral#r2#16.2 ok 2141c 12cites 21083ms",
];

const MOCK = `
  const respond = (msg) => {
    switch (msg && msg.type) {
      case "GET_OVERVIEW": return ${JSON.stringify(OVERVIEW)};
      case "LIST_RUNS": return ${JSON.stringify(RUNS)};
      case "REC_ACTIVE": return { recording: false };
      default: return { ok: true };
    }
  };
  globalThis.browser = {
    runtime: { id: "mock", sendMessage: async (m) => respond(m) },
    tabs: { query: async () => [{ id: 1 }], sendMessage: async () => ({ ok: true, build: "2026-07-11-c" }) },
    windows: { getCurrent: async () => ({ id: 1 }) },
    storage: { local: {
      get: async (k) => (k === "logRing" || (k && k.logRing !== undefined)) ? { logRing: ${JSON.stringify(LOG)} } : {},
      set: async () => {},
    } },
    downloads: { download: async () => 1 },
  };
`;

const browser = await chromium.launch();
for (const scheme of ["light", "dark"]) {
  const ctx = await browser.newContext({ viewport: { width: 480, height: 940 }, colorScheme: scheme, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  await page.addInitScript(MOCK);
  await page.goto(popup);
  await page.waitForTimeout(700);
  const out = path.join(here, "shots", `popup-${scheme}.png`);
  await page.screenshot({ path: out, fullPage: true });
  console.log("shot:", out);
  await ctx.close();
}
await browser.close();
