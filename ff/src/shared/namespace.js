// Shared isolated-world / background namespace.
globalThis.Probe = globalThis.Probe || {};
// Build stamp — bump on every change so the popup can show which code is live in
// the background vs. each content-script tab (stale tabs = needs a tab reload).
globalThis.Probe.BUILD = "2026-09-15-e";
