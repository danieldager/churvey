// Cross-browser API handle. Firefox exposes the promise-based `browser`;
// `chrome` is the fallback. Everything else uses `ext.*` (promise-based).
globalThis.ext = globalThis.browser || globalThis.chrome;
