---
name: slack-search
description: "Search Slack messages, files, channels via Web API + bot token."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Slack, Search, Productivity]
    related_skills: [slack-canvas, slack-channel-create]
---

# Slack Search

Search Slack from Hermes using the bot token in `~/.hermes/.env` as `SLACK_BOT_TOKEN`. The bot operates in whatever Slack workspace it was installed into. This skill is workspace-agnostic — the first time you use it, run the **bootstrap** step below to discover and cache your own workspace's stable IDs at the bottom of this file.

## Required scopes

The bot must have these OAuth scopes granted in the Slack app config. If a search returns `not_authed`, `missing_scope`, or empty results where you expect hits, verify these are present:

`search:read.public`, `search:read.files`, `search:read.users`, `channels:history`, `groups:history`, `files:read`, `channels:join`, `channels:read`, `groups:read`, `users:read`.

## When to use

- **Find a file or message** someone references vaguely ("there was a PDF in #brand", "didn't we discuss X somewhere")
- **Cross-reference** chat with tickets / PRs ("what was the conversation behind TICKET-N")
- **Pull historical decisions** when responding to "wait, didn't we decide Y?"
- **Discover what channels exist** for a topic without bothering the user

Default to searching before asking the user to repeat themselves.

## Token loading

Always load the token freshly from the env file — do not assume it's in the process env (the gateway filters env vars to subprocesses):

```bash
TOKEN=$(grep '^SLACK_BOT_TOKEN=' ~/.hermes/.env | cut -d= -f2- | tr -d '"' | tr -d "'")
```

Never echo it. Never put it in command-line args (Slack API accepts it as a Bearer header — keep it there).

## Bootstrap: discover your workspace (run once per bot)

On first use in a new workspace, confirm auth and cache the team identity, then populate the channel ID table at the bottom of this file with the channels you actually use:

```bash
TOKEN=$(grep '^SLACK_BOT_TOKEN=' ~/.hermes/.env | cut -d= -f2- | tr -d '"' | tr -d "'")

# Who am I / what workspace?
curl -sS -H "Authorization: Bearer $TOKEN" "https://slack.com/api/auth.test" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('team'), d.get('team_id'), '| bot:', d.get('user'), d.get('user_id'))"

# List channels — pick the ones you reuse and paste their IDs into the table below
curl -sS -H "Authorization: Bearer $TOKEN" \
  "https://slack.com/api/conversations.list?types=public_channel,private_channel&limit=500" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); [print(c['id'], c['name']) for c in d.get('channels',[])]"
```

Save IDs to the table — channel **names** are mutable, **IDs** are stable.

## Core API patterns

All endpoints live under `https://slack.com/api/`. Auth is `Authorization: Bearer $TOKEN`. All responses are JSON with `{"ok": true/false, ...}` — always check `ok` and `error`.

### Find a channel by name

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  "https://slack.com/api/conversations.list?types=public_channel,private_channel&limit=200" \
  | python3 -c "
import json,sys
d=json.load(sys.stdin)
for c in d.get('channels',[]):
    if 'KEYWORD' in c.get('name',''):
        print(c['id'], c['name'])
"
```

### Search messages across the workspace

```bash
curl -sS -H "Authorization: Bearer $TOKEN" -G \
  "https://slack.com/api/search.messages" \
  --data-urlencode "query=YOUR QUERY" \
  --data-urlencode "count=20" \
  --data-urlencode "sort=timestamp"
```

Supports Slack search syntax: `in:#channel`, `from:@user`, `before:YYYY-MM-DD`, `after:YYYY-MM-DD`, `has:link`, `has:pin`. Combine freely.

> **Heads up — `search.*` needs a USER token, not a bot token.** With a bot token, `search.messages` and `search.files` return `not_allowed_token_type` even when the `search:read.*` scopes are granted — those scopes don't make the bot token work for search. If you only have a bot token (the common case), fall back to `conversations.history` / `conversations.replies` on candidate channels (the cached channel-ID table makes this fast). To use `search.*` for real, install a user token (`xoxp-…`) with `search:read` and load it separately.

### Search files across the workspace

```bash
curl -sS -H "Authorization: Bearer $TOKEN" -G \
  "https://slack.com/api/search.files" \
  --data-urlencode "query=positioning pdf" \
  --data-urlencode "count=20"
```

Same user-token caveat as `search.messages` above. When it works, `search.files` only returns files **the bot can already see** — i.e. in channels the bot is in. If you suspect a file is in a channel the bot isn't a member of, search messages instead (often the message will be indexed even if the file isn't), or join the channel first (next pattern).

### Join a public channel before listing its files

The bot must be a member of a channel to list files via `files.list?channel=…`. Public channels can be self-joined:

```bash
curl -sS -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-type: application/json; charset=utf-8" \
  --data '{"channel":"CHANNEL_ID"}' \
  "https://slack.com/api/conversations.join"
```

Private channels (`groups:write` doesn't grant unilateral join) require a human to `/invite` the bot.

### List files in a channel

```bash
curl -sS -H "Authorization: Bearer $TOKEN" -G \
  "https://slack.com/api/files.list" \
  --data-urlencode "channel=CHANNEL_ID" \
  --data-urlencode "count=50" \
  --data-urlencode "types=pdfs,images,gdocs"
```

`types=` accepts: `all`, `spaces`, `snippets`, `images`, `gdocs`, `zips`, `pdfs`. Combine with comma.

### Fetch channel history (most recent first)

```bash
curl -sS -H "Authorization: Bearer $TOKEN" -G \
  "https://slack.com/api/conversations.history" \
  --data-urlencode "channel=CHANNEL_ID" \
  --data-urlencode "limit=50"
```

For a specific thread:

```bash
curl -sS -H "Authorization: Bearer $TOKEN" -G \
  "https://slack.com/api/conversations.replies" \
  --data-urlencode "channel=CHANNEL_ID" \
  --data-urlencode "ts=THREAD_TS"
```

`scripts/slack_history.py <CHANNEL_ID> [HOURS_BACK] [THREAD_TS]` wraps both of these in one call, loads the token without shelling out, and prints full message text oldest-first. Prefer it when a shell one-liner that interpolates the token gives you trouble.

### Download a file (auth required)

The `url_private` / `url_private_download` URLs in API responses are NOT public — they require the same Bearer token:

```bash
curl -sSL -H "Authorization: Bearer $TOKEN" -o "OUTPUT" "$URL_PRIVATE_DOWNLOAD"
```

Common mistake: downloading without the auth header returns a Slack login page (HTML), not the file.

### Look up a user by email or ID

```bash
curl -sS -H "Authorization: Bearer $TOKEN" -G \
  "https://slack.com/api/users.lookupByEmail" \
  --data-urlencode "email=someone@example.com"

curl -sS -H "Authorization: Bearer $TOKEN" -G \
  "https://slack.com/api/users.info" \
  --data-urlencode "user=U0…"
```

### Phone numbers in profiles: TWO fields, and `users.list` misses one

Workspaces can have **two distinct "Phone" fields**:
1. The **legacy built-in** `profile.phone` — present in `users.list`/`users.info` responses, but newer Slack UIs often don't render an edit box for it, so it sits empty ("the field is enabled but I can't see it" symptom).
2. A **custom "Phone" field** (a per-workspace field id like `Xf0…`) — what users actually fill in via Edit Profile. Lives under `profile.fields`, which `users.list` does NOT include — you must call `users.profile.get` per user to see it.

So a phone-directory build must: `team.profile.get` → collect field ids whose label contains "phone" → per-user `users.profile.get` → read BOTH `profile.phone` and the matching `profile.fields[id].value`. Normalize all numbers to E.164 before comparing (users enter `14155550119`, `(415) 555-…`, etc.; SIP/caller-ID sources give `+1415…`).

## Common workflow: "find that file someone mentioned"

```bash
TOKEN=$(grep '^SLACK_BOT_TOKEN=' ~/.hermes/.env | cut -d= -f2- | tr -d '"' | tr -d "'")

# 1. Identify likely channels
curl -sS -H "Authorization: Bearer $TOKEN" \
  "https://slack.com/api/conversations.list?types=public_channel,private_channel&limit=500" \
  | jq -r '.channels[] | select(.name | test("brand|market|positioning")) | "\(.id) \(.name)"'

# 2. If bot isn't in target channel, join it (public only)
curl -sS -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-type: application/json" \
  --data '{"channel":"C0…"}' \
  "https://slack.com/api/conversations.join"

# 3. List PDFs in that channel
curl -sS -H "Authorization: Bearer $TOKEN" -G \
  "https://slack.com/api/files.list" \
  --data-urlencode "channel=C0…" \
  --data-urlencode "types=pdfs" \
  | jq -r '.files[] | "\(.id) \(.name) \(.url_private_download)"'

# 4. Download with auth header
curl -sSL -H "Authorization: Bearer $TOKEN" -o "/tmp/file.pdf" "$URL"
```

## Pitfalls

- **`search.messages`/`search.files` reject bot tokens with `not_allowed_token_type`.** The `search:read.*` scopes don't change this — search endpoints require a *user* token (`xoxp-…`). With only a bot token, use `conversations.history` / `conversations.replies` on candidate channels instead.
- **Token from env doesn't propagate to MCP subprocesses.** The gateway filters env for security. Always re-read from `~/.hermes/.env`.
- **Private channel searches return nothing if the bot isn't a member.** No error — just empty results. If you expect hits and get none, suspect membership before suspecting the query.
- **`files.list` is channel-scoped.** No workspace-wide file listing. Use `search.files` for that (user token), but it only sees files in bot-accessible channels.
- **`search.messages` indexes are eventually consistent.** Very recent messages (<1 min) may not appear. Fall back to `conversations.history` for fresh content.
- **Rate limits are generous but real** — Tier 2 (~20 req/min) for search endpoints. Don't burst. Use `sleep 0.5` between sequential calls in scripts.
- **The `url_private` URL is auth-gated.** Without the Bearer header you get HTML, not the file. Watch for this in download scripts.
- **`channels.join` only works on public channels** despite the bot having `groups:write`. Private channels require `/invite @bot` from a human member.
- **Profile phone numbers live in TWO places** — see §"Phone numbers in profiles" above (`users.list` misses the custom field; per-user `users.profile.get` required).

## When to update this skill

- New workspace conventions for naming channels
- New scopes added to the bot (update the scope list above)
- New Slack API quirks discovered (rate-limit changes, deprecations)
- Patterns used 3+ times become canonical snippets here

## Quick reference: workspace IDs

Populate this once per bot via the **Bootstrap** step above. Channel names are mutable; IDs are stable, so cache the IDs here.

| Channel | ID |
|---|---|
| `#general` | `TODO` |
| `#…` | `TODO` |

Team: `TODO` (run `auth.test`). Bot user: `TODO`.
