// Establishes the shared isolated-world namespace used by every module.
// Content-script files are listed in dependency order in manifest.json and run
// in the same isolated world, so they all share `globalThis.Probe`.
// The service worker loads the same files via importScripts().
globalThis.Probe = globalThis.Probe || {};
