# Project Hunt v0.2 — research drafts to your Telegram

## Exact delivery flow

Every 15 minutes by default, discover candidate projects from DEX Screener and GeckoTerminal; optionally search X directly using your X API access. Deduplicate by contract/profile, read accessible source material, record purpose and launch evidence, identify a specific opportunity, draft a role-neutral pitch, and send the brief to your own Telegram chat. You choose whether to pitch as a frontend developer, designer or something else.

The default **50 per Lagos calendar day is a delivery target and cap**, not a promise that 50 qualifying projects exist. The monitor processes five research candidates per cycle and limits attempted research calls to 100/day by default. Change `--target`, `--batch`, `--max-research-daily`, and `--max-age-days` as needed. The initial launch window is seven days; `--max-age-days 1` is today/yesterday by calendar date, not exclusively today. Pool/profile updates cannot qualify a project without separate launch evidence. Source limitations can mean a shortfall.

This is polling, not a real-time firehose. A cycle can take longer than 15 minutes, and provider caches/rate limits affect freshness. No activity happens while the server is stopped. A 50-project day entails paid API usage; set provider spending limits and test a small batch first. No API budget is preselected or activated by this package.

## Configure services

1. Clone this repository: `git clone https://github.com/devsops4-cmyk/job-hunt.git`, then `cd job-hunt`.
2. Configure `OPENAI_API_KEY` and `OPENAI_MODEL` on your server. Choose a model available to your account that supports Responses API web search and structured outputs. The collector does not require a model; the research layer does. API billing is separate from merely using this source code.
3. Optionally configure `X_BEARER_TOKEN` with access to recent search. Without it, the research layer uses accessible public web sources; inaccessible X content is recorded as unknown and may prevent qualification.
4. Create a Telegram bot using the official [@BotFather](https://t.me/BotFather), then open your bot and send `/start` from the account that should receive briefs.
5. Configure `TELEGRAM_BOT_TOKEN` and your numeric `TELEGRAM_CHAT_ID` in the server's secret environment. Never commit credentials or paste the bot token in a public repository. The local `.env.example` lists variable names only.
6. Run the read-only Telegram identity check and verify that it identifies your own account:

```bash
python monitor.py --check-telegram
```

This performs `getMe` and `getChat`; it sends no message. Only a matching numeric private-chat ID is allowed initially. The bot cannot infer which person you want. If you do not know your chat ID, retrieve your own `/start` update through the official Bot API `getUpdates` using a local client; do not expose a token in a screenshot or URL shared publicly. Do not run getUpdates against a bot already managed by another application.

## Test before continuous operation

Python 3.10+ on Linux; all dependencies are standard-library modules.

```bash
python -m unittest discover -s tests -v
# Public discovery only; no research charge and no Telegram messages:
python monitor.py --once --discover-only
# One research run, at most two model calls, save drafts without messaging:
python monitor.py --once --batch 2
# One run with delivery of eligible briefs to your configured private chat:
python monitor.py --once --batch 2 --send-telegram
```

Environment variables must be loaded into the process. `monitor.py` does not automatically parse `.env`; Docker Compose does. To run through Compose, copy `.env.example` to `.env` and enter credentials there locally, then:

```bash
docker compose run --rm hunter python monitor.py --check-telegram
docker compose run --rm hunter python monitor.py --data /data --once --batch 2
docker compose up -d --build
docker compose logs -f
```

The final `up` command starts continuous collection and Telegram delivery. Run only after the read-only check confirms your destination and the draft test succeeds. The named volume retains deduplication and delivery state across restarts; back it up. Do not run a second instance with an independent state volume, which could send duplicates. The file lock prevents simultaneous writers using the same state directory.

## Evidence and reliability

- An eligible brief needs purpose evidence, a sourced launch date inside the configured window, contact-identity evidence, at least one substantive post read, and at least one supported opportunity.
- Every cited URL must occur in returned search-source metadata or directly fetched X posts. This prevents arbitrary invented citation URLs, but does **not** prove the model correctly interpreted a source. All messages remain explicitly labelled AI-researched drafts.
- The researcher distinguishes an observed issue from a possible improvement. It must not claim a visual audit, transaction test, missing feature or founder identity it did not establish.
- API response snapshots, source URLs and available X post text are saved under `monitor-data/runs/`; `briefs.json` contains drafts and rejection reasons; `status.json` contains counts and shortfalls.
- Failed/incomplete research is eligible for one further attempt after 24 hours. A successful draft is not repeatedly regenerated. Canonical contact identity prevents common token/profile cross-source duplicates, but multiple official contacts can still require manual merging.
- A Telegram timeout can occur after a message reached the chat. Such a row becomes `delivery_uncertain` and is not retried automatically. Inspect the chat and reconcile that row before changing state. Uncertain sends count toward the daily cap to avoid excess duplicates. Exactly-once delivery is not guaranteed by Telegram.
- The bot sends briefs only to your configured chat. It does not DM project teams, connect wallets, trade tokens, publish to LinkedIn or sell anything.
- The original `hunt.py` remains available for free discovery-only CSV/HTML exports. The included GitHub Actions workflow still runs discovery/tests manually; it does not host the continuous monitor.

## Coverage still needing connections or clarification

DEX Screener and GeckoTerminal discovery are live-tested. The OpenAI research, direct X API and Telegram adapters are implemented and locally tested with controlled fixtures, but not live-tested because credentials have not been provided. Docker deployment is supplied but not started or verified here.

There is no direct Instagram, Axiom, FOMO, Pump or “X39” collector yet. Pump-related tokens can be found through indexed pools. Confirm the exact FOMO and X39 URLs before implementing their adapters. Do not describe these sources as connected. Project profiles can also be supplied using `--seed-json projects.json` with an array of objects containing `id`, `name`, `description`, `contact_links`, and `sources`; these may be pre-token projects, without a contract. All still pass the same research gate.

## Official implementation references

- https://docs.dexscreener.com/api/reference
- https://api.geckoterminal.com/docs/index.html
- https://docs.x.com/x-api/posts/search/quickstart/recent-search
- https://developers.openai.com/api/docs/guides/tools-web-search
- https://developers.openai.com/api/docs/guides/structured-outputs
- https://core.telegram.org/bots/api
- https://core.telegram.org/bots/tutorial
