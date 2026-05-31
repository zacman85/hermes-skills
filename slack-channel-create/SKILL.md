---
name: slack-channel-create
description: Create a new Slack channel end-to-end — provisions the channel, invites SLACK_ALLOWED_USERS, sets purpose/topic, attaches a canvas, wires a per-channel personality prompt in config.yaml, and restarts the gateway. Always draft-then-confirm; never silent.
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [slack, channels, ops]
---

# slack-channel-create

Create a Slack channel end-to-end: provision, invite, decorate, wire personality, restart gateway.
Use when the operator (or another admin) asks for one or more new channels — "spin up #foo",
"I want channels for a GTM motion", "create a channel for X".

## Hard rules (do not skip)

1. **Always draft first.** Show the operator the full plan (name, purpose, topic, invitees,
   personality, channel_prompt body, canvas outline) and wait for explicit approval
   before any API call. No silent channel creation, even when the request seems
   unambiguous. The cost of an unwanted channel is annoying; the cost of asking once is seconds.

2. **Public by default.** Never set `is_private=true` unless the request literally
   says "private" / "DM-style" / "restricted." Most workspaces default to open channels.

3. **One channel per skill invocation.** If the operator asks for several, loop the skill
   sequentially with one approval per channel (or one batch approval covering all
   names + prompts up front). Never create >3 in one batch without re-confirming.

4. **Refuse name collisions.** Always list existing channels first and refuse
   `conversations.create` if the name (or its normalized form) already exists.
   Slack returns `name_taken` — surface it cleanly, don't retry blind.

5. **No half-wired channels.** If `channel_prompts` patch or gateway restart fails,
   surface it. Offer: (a) finish wiring manually, or (b) archive the new channel.
   Do not leave a channel with no personality.

6. **Canvas + prompt must cross-reference siblings.** Every new channel's
   `channel_prompt` body and canvas should redirect to the right existing channel
   for off-topic work (e.g. a broadcast channel, a reviews channel). Future agents
   lack context; wiring those redirects costs seconds and saves confusion.

7. **TODO/HACK/TEMP comments** stay out of personality prompts and canvases —
   those are public artifacts. If the skill needs a workaround, mark it inside
   `scripts/create_channel.py`, not in the channel itself.

## What you collect before drafting

| Field | Default | Notes |
|---|---|---|
| `name` | required | Lowercase, hyphenated, ≤ 21 chars. Suggest a team prefix (e.g. `team-`, `ops-`) if missing. |
| `purpose` | required | ≤ 250 chars. Shows in channel header. |
| `topic` | optional | One-liner pinned in channel UI. |
| `personality` | required | Persona for the agent in this room (Builder, Reporter, Reviewer, etc.). |
| `routing` | required | Sibling channels this room is NOT for, so the prompt redirects correctly. |
| `default_skills` | optional | Skill names to surface in canvas + prompt. |
| `invitees` | `SLACK_ALLOWED_USERS` from `~/.hermes/.env` | Comma-separated user IDs. Grows automatically as team scales. |
| `private` | `false` | Override only on explicit request. |

## Presets

Detect these phrasings in the request and offer the matching preset (don't force it):

- **"bulletins" / "announcements" / "alerts" / "cron output"** → Reporter preset:
  `purpose` emphasizes broadcast-only, `channel_prompt` says "no new work originates here,
  formatted summaries only, redirect human follow-ups." Model after an existing broadcast channel.
- **"incidents" / "on-call" / "pager"** → Incident Commander preset.
- **"reviews" / "audit log"** → Reviewer preset: structured one-line entries,
  no editorializing, model after an existing reviews channel.

## Execution order (sequence is strategy)

```
1. conversations.list                    → confirm name not taken
2. conversations.create                  → channel_id
3. conversations.invite (SLACK_ALLOWED_USERS, comma-joined)
4. conversations.setPurpose + setTopic
5. canvases.create + conversations.canvases.create   → attach to channel
6. patch ~/.hermes/config.yaml slack.channel_prompts → add new ID
7. sudo systemctl restart hermes-gateway.service
8. chat.postMessage to new channel       → brief intro
```

If step 6 or 7 fails, do not proceed to 8. Surface the failure.

## How to run

Use the included script:

```bash
python3 ~/.hermes/skills/slack-channel-create/scripts/create_channel.py \
    --name team-foo \
    --purpose "..." \
    --topic "..." \
    --personality-prompt-file /tmp/foo-prompt.txt \
    --canvas-file /tmp/foo-canvas.md \
    --intro "..."
```

The script reads `SLACK_BOT_TOKEN` and `SLACK_ALLOWED_USERS` from `~/.hermes/.env`,
runs steps 1–8, and prints a structured result. Pass `--dry-run` to validate inputs
and print the request bodies without hitting the API.

Multi-line prompt / canvas content lives in files (not CLI args) so quoting stays sane
and you can review the draft as a file before running.

### Batching multiple channels

When creating 2+ channels in one session, pass `--no-restart` to each call and run
**one** gateway restart at the end — saves a restart per channel and avoids
needless drain cycles. The new prompts don't take effect until the restart, so
batch the work, then:

```bash
sudo -n /bin/systemctl restart hermes-gateway.service
```

The restart blocks until the current Hermes turn ends, so it completes after the
response that triggers it.

## Drafting the channel_prompt

Match the existing channel-prompt shape (see `~/.hermes/config.yaml` →
`slack.channel_prompts`):

- 2–4 paragraph block. Plain text. No markdown headers.
- Para 1: who the agent IS in this channel ("You are in the X channel. Your job is to…").
- Para 2: default mode / tone / cadence.
- Para 3: what belongs here vs. where it goes (cross-refs to sibling channels by name).
- Optional para 4: default skills to load, output expectations.

Keep total length under ~150 words. Longer prompts crowd the system context.

## Drafting the canvas

Channel canvases are short structured docs pinned to the channel tab. Sections:

- **Purpose** (1–2 sentences, matches `purpose` field but can be richer)
- **What belongs here** (bulleted)
- **What doesn't** (bulleted, with redirects to sibling channels)
- **Default skills** (if any)
- **Routing** (table or bullets cross-referencing other channels)

Write as markdown — the canvas API converts to its block format.

## Verification after running

After the script returns, verify:

1. Channel appears in `conversations.list` with correct `purpose` and `topic`.
2. Bot is a member (`is_member: true`) and the operator (or other invitees) is in the channel.
3. Canvas is attached as a tab (`properties.tabs[].type == "canvas"`).
4. `~/.hermes/config.yaml` has the new channel ID under `slack.channel_prompts`.
5. Gateway restarted successfully (`systemctl status hermes-gateway.service`).
6. Send a test message in the new channel and confirm the personality lands.

The restart blocks during the current Hermes turn — it completes after the response is sent.

## Pitfalls

- **`create_channel.py` can time out at step 7 (gateway restart) and leave the channel half-wired.**
  Step 1–6 (provision, invite, purpose/topic, canvas attach, config patch) are
  individually fast. Step 7 (`sudo -n /bin/systemctl restart hermes-gateway.service`)
  *blocks until the current Hermes turn ends* — which is the turn that invoked the
  script. From the script's perspective this hangs indefinitely and tool wrappers
  typically kill it at 60s. Result: channel exists, canvas is attached, config is
  patched, but step 8 (intro `chat.postMessage`) never runs and the new personality
  isn't loaded yet. The channel is "alive" but quiet and using the default agent prompt.

  **How to recognize this state.** If the script exit code is 124 (timed out),
  immediately verify via Slack API:
  - `conversations.info` → confirm purpose/topic set and `properties.tabs[]` has the canvas
  - `conversations.history` → if the only messages are "set the channel topic / description"
    bot events, the intro never posted
  - `grep <channel_id> ~/.hermes/config.yaml` → should already show the personality block (step 6 ran)

  **How to finish manually.** Post the intro with a direct
  `chat.postMessage` call, then restart the gateway in background mode so the
  scheduler can track it (`terminal(background=true)` for the systemctl command).
  Do NOT re-run the full script — it'll fail at `conversations.create` with
  `name_taken` and the script doesn't recover gracefully from that.

- **Slack name normalization.** Slack lowercases + strips invalid chars. `Team GTM`
  becomes `team-gtm`. Always pre-normalize and confirm with the operator before submitting.
- **Bot must be invited to private channels it created.** For public channels the bot is
  auto-added. If you ever do create a private channel, the bot must invite itself first
  with `conversations.invite` for its own user ID before posting or attaching canvases.
- **Invite errors are non-fatal.** `already_in_channel` is success; ignore it.
  `user_not_found` means a stale ID in `SLACK_ALLOWED_USERS` — flag it, don't abort.
- **Canvas attachment is two calls.** `canvases.create` creates the document
  (returns `canvas_id`), then `conversations.canvases.create` attaches it as a tab.
  The second call is where it shows up in the channel UI.
- **Config edits before restart.** Patch `channel_prompts` in `config.yaml` BEFORE the
  restart — restart picks up the new prompt. If you restart first, the new channel
  exists but talks with the default personality until the next restart.
- **Restart is the last step.** Restart drains active runs, so any work in flight
  (other channels' conversations) keeps running. Still: avoid restarting during a
  live incident in your incidents/on-call channel — ask first.

## When NOT to use this skill

- Renaming an existing channel → use `conversations.rename` directly.
- Editing an existing channel's prompt or canvas → patch `config.yaml` and the canvas
  by ID; no need to provision anything.
- Inviting more people to an existing channel → `conversations.invite` directly.
- DM-only conversations → use the existing `slack:` send_message target.
