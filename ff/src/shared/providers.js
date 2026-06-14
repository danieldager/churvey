// Provider metadata. `completionHint` is a best-guess regex (on request URL) for
// the chat-completion endpoint; discovery mode confirms/refines it per provider.
(() => {
  const Probe = (globalThis.Probe ||= {});

  const LIST = [
    {
      id: "chatgpt", label: "ChatGPT",
      host: "chatgpt.com", homeUrl: "https://chatgpt.com/",
      matchPattern: "https://chatgpt.com/*",
      // Only the streaming endpoint, NOT /conversation/init or /conversation/prepare.
      completionHint: "backend-api/(f/)?conversation($|\\?)",
    },
    {
      id: "gemini", label: "Gemini",
      host: "gemini.google.com", homeUrl: "https://gemini.google.com/app",
      matchPattern: "https://gemini.google.com/*",
      completionHint: "StreamGenerate|BardFrontendService|assistant\\.lamda",
    },
    {
      id: "grok", label: "Grok",
      host: "grok.com", homeUrl: "https://grok.com/",
      matchPattern: "https://grok.com/*",
      completionHint: "responses|app-chat|conversation",
    },
    {
      id: "claude", label: "Claude",
      host: "claude.ai", homeUrl: "https://claude.ai/new",
      matchPattern: "https://claude.ai/*",
      completionHint: "chat_conversations/.+/completion|/completion",
    },
    {
      id: "deepseek", label: "DeepSeek",
      host: "chat.deepseek.com", homeUrl: "https://chat.deepseek.com/",
      matchPattern: "https://chat.deepseek.com/*",
      completionHint: "chat/completion|completion",
    },
  ];

  const byHost = (hostname) => LIST.find((p) => hostname.endsWith(p.host)) || null;

  Probe.providers = {
    LIST,
    ids: LIST.map((p) => p.id),
    byId: (id) => LIST.find((p) => p.id === id) || null,
    byHost,
    forUrl(url) {
      try { return byHost(new URL(url).hostname); } catch (_) { return null; }
    },
    allMatchPatterns: () => LIST.map((p) => p.matchPattern),
  };
})();
