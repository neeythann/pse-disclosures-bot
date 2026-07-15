# AGENTS.md

Compact guide for OpenCode sessions working in this repo.

## Commands

Toolchain is **uv** (Python 3.11+; `.python-version` pins 3.11, Dockerfile uses 3.12).

- `uv sync --frozen` — install deps from lockfile
- `uv run pytest` — run tests
- `uv run -m src.main` — run the scraper (runtime entrypoint; also the Docker `CMD`)
- Single test: `uv run pytest tests/test_CompanyDisclosure.py::TestCompanyDisclosure::test_CompanyDisclosure_parse`

## WEBHOOK_URL is optional

`WEBHOOK_URL` is read at **import time** via the `Config` singleton (`src/config.py`). It accepts **comma-delimited URLs** (e.g. `https://discord.com/.../a,https://discord.com/.../b`), parsed into `config.webhook_urls` (a list). If unset/empty, the list is empty and the scraper runs in **archive-only mode**: items are still parsed, deduped, and persisted to SQLite, but webhook notifications are skipped. `tests/conftest.py` sets a default so tests construct webhooks without a real URL.

## Webhook factory

`create_webhook(url, data)` (`src/main.py`) infers the sender class from the URL host via `urlparse`. `discord.com` / `discordapp.com` → `DiscordWebhook`; `hooks.slack.com` → `SlackWebhook`; unknown hosts raise `ValueError`. To add a provider, subclass `Webhook` and add a host branch in the factory. `_notify` calls `create_webhook` rather than constructing a sender directly. `SlackWebhook._format_data()` reuses the dataclass `to_embed()` and translates the Discord embed shape into a Slack `attachments` payload (`author.name`→`author_name`, `author.url`→`author_link`, `title`/`url`→`title`+`title_link`, `fields[].name`→`fields[].title`, `inline`→`short`, `footer.text`→`footer`); `to_embed()` stays the single source of truth and no dataclass changes are needed.

## OUTPUT_MODE

`OUTPUT_MODE` (read at import time via `Config`) selects the runtime mode, validated against `both` | `archive` | `webhook` (default `both`, case-insensitive):

- `both` — SQLite archive + webhook notifications (requires `WEBHOOK_URL`).
- `archive` — SQLite only, webhook skipped (`WEBHOOK_URL` optional).
- `webhook` — Webhook only, no SQLite; dedup uses an in-memory cache (restarts may re-send). Requires `WEBHOOK_URL`.

`Config` raises `ValueError` for an invalid mode, or when `both`/`webhook` is selected without `WEBHOOK_URL`. `main()` instantiates `Database` only for `both`/`archive`; otherwise it dispatches to `_diff_and_send_mem` (in-memory cache) instead of `_diff_and_send` (SQLite path). `_notify` gates the webhook send on `config.mode in ("both", "webhook")` and fans out to every URL in `config.webhook_urls`.

## Run tests from repo root

`tests/test_CompanyDisclosure.py` opens `./tests/html/*.html` via relative path — run pytest from the repo root or fixtures won't be found.

## No lint / typecheck / formatter is wired up

`pyproject.toml` has a `[tool.pyright]` block, but **pyright is not a dependency** and `uv run pyright` is not available. No ruff/black/mypy/pre-commit. The only dev dep is pytest. Don't claim to "run typecheck" — there is none enforced. CI (`.github/workflows/test.yaml`) only runs `uv run pytest -v`, on PRs and non-main pushes touching `**.py`.

## Architecture

Single-module PSE Edge scraper. `src/main.py`:

- Polls disclosure endpoints from `src/config.py` `API_URLS` (`announcement`, `financial`, `other`) via `POST` with `fromDate`/`toDate`, and `DIVIDENDS_RIGHTS_URLS` (`dividends`, `rights`) via `GET`, with a 5-min interval
- Parses returned HTML tables with BeautifulSoup into `CompanyDisclosure` / `Dividend` / `StockRights` dataclasses (5 / 8 / 7 columns respectively)
- Diffs new items against a SQLite archive (`src/db.py`, `Database`) and POSTs them to a webhook via `create_webhook()` (each dataclass has a `to_embed()`)

`src/db.py` is duck-typed (does not import `src.main`, so no circular import) — `insert` reads item fields via `getattr`. Three tables keyed by `edge_no` PRIMARY KEY: `company_disclosures` (shared by all three disclosure endpoints), `dividends`, `stock_rights`; each has a `created_at` column. `DB_PATH` env var overrides the default `pse_disclosures.db` (the Dockerfile sets `DB_PATH=/app/data/pse_disclosures.db` and declares `/app/data` as a `VOLUME` for persistence). On first run (empty table) the current page is seeded without sending to avoid flooding the webhook; on restarts, items not yet in the DB are sent. `*.db` is gitignored.

Each `parse` selects `<td>` cells by index (column-driven). This is **brittle and tied to exact PSE HTML structure** — col 0 is always the company `<a>` (href → `_id`), and the `edge_no` `<a>` is col 1 for disclosures but the last col for dividends/rights. Tests assert row counts (`50`/`50`/`11`) against the fixtures in `tests/html/`. If you touch a parser, regenerate/verify against its fixture.

## Import layout

The package is imported as `src.*` (tests do `from src.main import ...`), not by the dist name `pse-disclosures`. `src/__init__.py` exists; there is no installed package name.
