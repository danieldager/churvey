# Who reaches the models: apps versus APIs

The numbers behind the first figure in the [README](../README.md), as published by the
companies or reported from their statements, collected on 27 September 2026. They are meant as
orders of magnitude. The denominators differ (weekly users, monthly users, developers), users
overlap across apps, and some figures are third-party estimates; each row says which.

## People using the consumer apps

| App | Figure | As of | Source | Kind |
|---|---|---|---|---|
| ChatGPT | more than 900M weekly active users | Feb 2026 | [TechCrunch](https://techcrunch.com/2026/02/27/chatgpt-reaches-900m-weekly-active-users) | reporting of an OpenAI announcement |
| ChatGPT | approaching 1B weekly active users | Jul 2026 | [PYMNTS](https://www.pymnts.com/news/artificial-intelligence/2026/chatgpt-approaches-1-billion-weekly-active-user-milestone/) | reporting, unnamed company data |
| Gemini app | 950M monthly active users | Jul 2026 (Q2 earnings) | [Alphabet Q2 2026 remarks](https://blog.google/company-news/inside-google/message-ceo/alphabet-earnings-q2-2026/) | company |
| Gemini app | 1B monthly active users | Aug 2026 | [TechCrunch](https://techcrunch.com/2026/08/11/googles-gemini-app-surges-to-one-billion-users/) | reporting of an executive post |
| Grok | about 117M monthly users of Grok features, including inside X | Mar 2026 (S-1 filed May 2026) | [Social Media Today](https://www.socialmediatoday.com/news/spacex-filing-provides-insight-into-x-grok-and-xai/820945/) | reporting of an SEC filing |
| DeepSeek | 130M monthly active users in China | May 2026 | [TechNode, citing QuestMobile](https://technode.com/2026/07/14/questmobile-chinas-ai-native-apps-reach-499-million-monthly-active-users/) | third-party panel |
| Claude | no official figure; third-party estimates range from tens to hundreds of millions | 2026 | not shown in the figure | unreliable |
| All AI tools | about 2B users worldwide | survey Jul 2026 | [Menlo Ventures, State of Consumer AI 2026](https://menlovc.com/perspective/2026-the-state-of-consumer-ai/) | independent survey |

The figure uses the first row for ChatGPT and Gemini (the company figure) and the 2B survey
estimate as a ceiling for distinct people.

## Developers on the APIs

| API | Figure | As of | Source | Kind |
|---|---|---|---|---|
| OpenAI | 4M developers | Oct 2025 (DevDay) | [Business Analytics](https://businessanalytics.substack.com/p/openais-api-hits-15-billion-tokens) | reporting of a keynote |
| Google | more than 9M developers building with Google models each month, across APIs and developer products | Jul 2026 | [Alphabet Q2 2026 remarks](https://blog.google/company-news/inside-google/message-ceo/alphabet-earnings-q2-2026/) | company |
| OpenRouter | more than 5M developers | May 2026 | [OpenRouter, State of AI](https://openrouter.ai/state-of-ai) | company |

## What the comparison does and does not support

- **Supported:** more people use first-party consumer apps directly (around 10^9) than call a
  frontier model's API themselves (around 10^7), by roughly two orders of magnitude.
- **Not counted:** people who reach a model indirectly through products built on the API
  (coding tools, search products, customer-service bots). That number is not published and
  could also be large; those products wrap the model too.
- **Not supported:** that most *tokens* or *revenue* go through the apps. No provider publishes
  consumer-app token volumes, and API and business revenue is a large share at several
  providers.

## How the app differs from the API

These are documented by the vendors themselves unless marked otherwise.

1. **System prompts.** The Claude apps use a system prompt that is periodically updated and does
   not apply to the API. [Anthropic, system prompt release notes](https://platform.claude.com/docs/en/release-notes/system-prompts).
   xAI publishes separate prompts for grok.com and X. [xai-org/grok-prompts](https://github.com/xai-org/grok-prompts)
2. **Model routing.** GPT-5 in ChatGPT is a unified system in which a real-time router picks
   between models; the API exposes the models directly. [OpenAI, Introducing GPT-5](https://openai.com/index/introducing-gpt-5/)
3. **Safety routing.** ChatGPT routes conversations flagged as sensitive to a reasoning model
   mid-chat. [OpenAI, Building more helpful ChatGPT experiences](https://openai.com/index/building-more-helpful-chatgpt-experiences-for-everyone/)
4. **Live A/B tests.** OpenAI tests changes on small numbers of ChatGPT users and judges them on
   feedback and usage; the April 2025 GPT-4o update was rolled back after such a rollout.
   [OpenAI, Expanding on sycophancy](https://openai.com/index/expanding-on-sycophancy/)
5. **A different model snapshot.** The API's `gpt-5-chat-latest` points to the snapshot used in
   ChatGPT, distinct from the API reasoning models. [OpenAI model page](https://developers.openai.com/api/docs/models/gpt-5-chat-latest)
6. **Memory and personal context.** ChatGPT memory and chat-history reference
   ([OpenAI Memory FAQ](https://help.openai.com/en/articles/8590148-memory-faq)); Gemini personal
   context, on by default for eligible accounts
   ([Google](https://blog.google/products-and-platforms/products/gemini/temporary-chats-privacy-controls/)).
   A stateless API call has neither.
7. **Web search.** On in the Claude apps ([Anthropic](https://www.anthropic.com/news/web-search)); a
   separately declared, separately billed tool on the API
   ([Claude web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)).
8. **App-only behaviours.** Claude can end abusive conversations in the consumer apps.
   [Anthropic](https://www.anthropic.com/research/end-subset-conversations)
