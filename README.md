# Project Hunt

Find new Web3 projects, understand what they are building, identify a supported service opportunity, draft a pitch, and send the brief to **your own Telegram inbox**. You choose which skill or profession to pitch. The system does not decide that you must sell websites, design or growth services.

## v0.2: implemented, awaiting configuration

- `hunt.py`: live-tested DEX Screener + GeckoTerminal discovery, source-listed contact filtering, deduplication, CSV/JSON and searchable HTML exports.
- `monitor.py`: periodic discovery, optional direct X search/post reading, OpenAI web research, source-backed opportunity drafts, a daily delivery target, persistent state and Telegram delivery to a confirmed private chat.
- `SETUP.md`: API configuration, testing, deployment, coverage and operational limits.
- `Dockerfile` / `compose.yaml`: a continuous Linux service with persistent state. Default polling is every 15 minutes; target/cap is 50 briefs per Lagos calendar day.
- `research-brief.md`: the role-neutral research checklist.
- `sample-research-2026-10-14.md`: two partial manual examples from the initial discovery session. These examples explore optional service angles, not prescribed professions.

## Run discovery now

Python 3.10+; no third-party Python dependencies.

```bash
python hunt.py --target 50 --max-age-days 7
python -m unittest discover -s tests -v
```

Open `reports/<timestamp>/index.html`, or use `leads.csv` / `leads.json`. Keep `state.sqlite3` between discovery runs for deduplication. The monitor uses its own durable `monitor-data/monitor.sqlite3`.

For the research bot, follow **[SETUP.md](SETUP.md)**. A `.env.example` lists the required variables. Credentials are not included. The research API, X and Telegram integrations have fixture-based tests but have not been live-tested with an authenticated account. No bot or schedule is currently running. The Docker deployment has not been launched here.

## Research standard

Each brief should explain purpose and audience, cite launch and recent-post evidence, identify a concrete issue or tentative improvement, suggest a deliverable, provide a neutral pitch idea and link a contact route. It must explain what remains unknown. Every citation must be traceable to retrieved evidence; AI interpretation still needs your review.

Never equate a new pool/profile with a new project, a missing link with a missing website/community, or a viral post with team ownership. Never invent needs to fill a quota. The initial launch window is seven days and configurable. Fifty researched briefs is a target; actual supply and source access can produce a shortfall.

## Current source coverage

DEX Screener and GeckoTerminal collectors are live-tested. The X adapter requires your API access; OpenAI web research depends on reachable/indexed public sources. Instagram, Axiom, FOMO, Pump and “X39” do not have direct collectors yet. Pump-related tokens may appear in indexed pools. FOMO and X39 need exact URLs. Both contract-based manual CSV imports and pre-token JSON seeds are supported; see SETUP.md.

## Initial run

147 candidate contracts discovered, 144 enriched, 26 passed the seven-day pool-age and source-listed contact filters. **These are candidates, not 26 completed research briefs or verified launches today.** Raw evidence and the candidate report are in the downloadable starter archive; generated reports are not tracked in Git. `RUN-RESULT.md` describes this initial run.

Source repository: https://github.com/devsops4-cmyk/job-hunt

The research bot is not deployed or running yet. Configure the API credentials and Telegram destination using SETUP.md before starting it. No project outreach or LinkedIn publication has occurred.
