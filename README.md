# pse-disclosures

Scraper for the Philippine Stock Exchange (PSE) Edge disclosure system. Polls
announcement, financial report, other report, dividend, and stock rights
endpoints, parses the returned HTML tables, and posts new items to a Discord
or Slack webhook.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for dependency management

## Setup

```sh
uv sync --frozen
```

## Configuration

Set `WEBHOOK_URL` to a webhook url (optional, depending on mode). Multiple
URLs can be provided as a comma-delimited list, and each item is sent to all
of them. The sender is inferred from the URL host — `discord.com` /
`discordapp.com` uses `DiscordWebhook`, `hooks.slack.com` uses
`SlackWebhook`; other hosts raise `ValueError` at send time:

```sh
# single (Discord)
export WEBHOOK_URL="https://discord.com/api/webhooks/..."

# single (Slack)
export WEBHOOK_URL="https://hooks.slack.com/services/T000/B000/XXXXXXXX"

# multiple (comma-delimited, can mix providers)
export WEBHOOK_URL="https://discord.com/api/webhooks/a,https://hooks.slack.com/services/T000/B000/XXXXXXXX"
```

`OUTPUT_MODE` selects what the scraper does with new items (default `both`):

| Mode       | SQLite archive | Webhook notifications | `WEBHOOK_URL` |
|------------|----------------|-----------------------|---------------|
| `both`     | yes            | yes                   | required      |
| `archive`  | yes            | no                    | optional      |
| `webhook`  | no             | yes                   | required      |

```sh
export OUTPUT_MODE="both"   # or "archive" or "webhook"
```

In `webhook` mode, dedup uses an in-memory cache, so a restart may re-send
items that appeared during the previous run. In `archive` mode, items are
parsed, deduped, and persisted to SQLite with no webhook notifications.

Optionally set `DB_PATH` to override the SQLite database location (defaults to
`pse_disclosures.db` in the working directory):

```sh
export DB_PATH="/data/pse_disclosures.db"
```

Optionally set `HMAC_SECRET` to sign every webhook payload with HMAC-SHA256
(Generic V2 scheme). The shared secret authenticates requests to receivers
that are otherwise unauthenticated, and the included timestamp prevents
captured requests from being replayed later. When set, each request carries:

- `X-Webhook-Signature-V2` — the hex HMAC-SHA256 digest of
  `<timestamp>.<body>` (the serialized JSON body prefixed with the timestamp
  and a dot)
- `X-Webhook-Timestamp` — the current Unix time in seconds

Receivers verify by checking the timestamp is within ±300 seconds of their
clock and recomputing the digest over `<timestamp>.<received_body>` with the
shared secret. If unset, no signature headers are added.

Both header names are env-configurable:

```sh
export HMAC_SECRET="a-long-random-shared-secret"
export WEBHOOK_SIGNATURE_HEADER="X-Webhook-Signature-V2"   # optional
export WEBHOOK_TIMESTAMP_HEADER="X-Webhook-Timestamp"      # optional
```

## Running

```sh
uv run -m src.main
```

The scraper polls the PSE Edge endpoints every 5 minutes, diffs new items
against the SQLite archive, and POSTs any newly appearing items to the
configured webhook(s). Items are persisted to SQLite so the dedup state
and full history survive restarts. On the first run (empty database) the
current page is seeded without sending, so the webhook is not flooded; on
restarts, items that appeared during downtime are sent as usual.

### Docker

```sh
docker build -t pse-disclosures .
docker run -e WEBHOOK_URL="https://discord.com/api/webhooks/..." \
           -v pse-data:/app/data \
           pse-disclosures
```

The image defaults `DB_PATH` to `/app/data/pse_disclosures.db` and declares
`/app/data` as a `VOLUME`, so mount a named volume there to persist the
SQLite archive across container recreations. Set `OUTPUT_MODE` to change
the runtime mode (defaults to `both`).

## Testing

```sh
uv run pytest
```

Tests parse HTML fixtures saved from the live PSE Edge endpoints
(`tests/html/`) and assert row counts and diff behavior. No network access or
real webhook is required — `tests/conftest.py` supplies a default
`WEBHOOK_URL` for the test process.

## Endpoints

| Key            | URL                                                                                | Method | Dataclass        | Columns |
|----------------|------------------------------------------------------------------------------------|--------|------------------|---------|
| announcement   | `edge.pse.com.ph/announcements/search.ax`                                          | POST   | CompanyDisclosure | 5       |
| financial      | `edge.pse.com.ph/financialReports/search.ax`                                       | POST   | CompanyDisclosure | 5       |
| other          | `edge.pse.com.ph/otherReports/search.ax`                                           | POST   | CompanyDisclosure | 5       |
| dividends      | `edge.pse.com.ph/disclosureData/dividends_and_rights_info_list.ax?...=Dividends`   | GET    | Dividend         | 8       |
| rights         | `edge.pse.com.ph/disclosureData/dividends_and_rights_info_list.ax?...=Rights`      | GET    | StockRights      | 7       |

The three disclosure endpoints share the same 5-column table layout and are
parsed by `CompanyDisclosure`. Dividends and stock rights have distinct column
layouts and are parsed by `Dividend` and `StockRights` respectively. Each
dataclass produces a Discord embed via `to_embed()`.
