// Static provider metadata, usable in BOTH the content script and the service
// worker (the SW has no adapters/DOM loaded). The adapters provide behavior;
// this provides the id -> URL/match-pattern map needed to open/find tabs.
(() => {
  const Probe = (globalThis.Probe ||= {});

  const LIST = [
    { id: "chatgpt", label: "ChatGPT", homeUrl: "https://chatgpt.com/", matchPattern: "https://chatgpt.com/*" },
    { id: "gemini", label: "Gemini", homeUrl: "https://gemini.google.com/app", matchPattern: "https://gemini.google.com/*" },
    { id: "grok", label: "Grok", homeUrl: "https://grok.com/", matchPattern: "https://grok.com/*" },
    { id: "claude", label: "Claude", homeUrl: "https://claude.ai/new", matchPattern: "https://claude.ai/*" },
    { id: "deepseek", label: "DeepSeek", homeUrl: "https://chat.deepseek.com/", matchPattern: "https://chat.deepseek.com/*" },
  ];

  Probe.providers = {
    LIST,
    ids: LIST.map((p) => p.id),
    byId(id) {
      return LIST.find((p) => p.id === id) || null;
    },
    matchPatterns(ids) {
      return (ids || LIST.map((p) => p.id))
        .map((id) => Probe.providers.byId(id))
        .filter(Boolean)
        .map((p) => p.matchPattern);
    },
  };
})();
