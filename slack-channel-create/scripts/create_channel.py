#!/usr/bin/env python3
"""Create a Slack channel end-to-end and wire its personality prompt.

Sequence (each step printed; failures abort with a clear status block):

  1. conversations.list           → name-collision check
  2. conversations.create         → channel_id
  3. conversations.invite         → invite SLACK_ALLOWED_USERS (best-effort)
  4. conversations.setPurpose + setTopic
  5. canvases.create + conversations.canvases.create
  6. Patch ~/.hermes/config.yaml: slack.channel_prompts[<channel_id>] = <prompt>
  7. sudo systemctl restart hermes-gateway.service
  8. chat.postMessage → intro

Use --dry-run to validate inputs and print the request bodies without hitting the API.

Reads SLACK_BOT_TOKEN and SLACK_ALLOWED_USERS from ~/.hermes/.env.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ENV_FILE = Path.home() / ".hermes" / ".env"
CONFIG_FILE = Path.home() / ".hermes" / "config.yaml"
SLACK_API = "https://slack.com/api"
RESTART_CMD = ["sudo", "-n", "/bin/systemctl", "restart", "hermes-gateway.service"]


# ---------- helpers ----------

def load_env() -> dict[str, str]:
    """Tiny .env parser — only KEY=VALUE lines, ignores comments + blanks."""
    if not ENV_FILE.exists():
        sys.exit(f"FATAL: {ENV_FILE} not found")
    env: dict[str, str] = {}
    for raw in ENV_FILE.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def slack(token: str, method: str, payload: dict[str, Any] | None = None,
          form: bool = False) -> dict[str, Any]:
    """POST to Slack Web API. form=True for endpoints that want form-encoded bodies."""
    url = f"{SLACK_API}/{method}"
    headers = {"Authorization": f"Bearer {token}"}
    if form:
        data = urllib.parse.urlencode(payload or {}).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    else:
        data = json.dumps(payload or {}).encode()
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} on {method}: {e.read().decode()[:300]}")
    return body


def must_ok(method: str, result: dict[str, Any], *, ok_errors: tuple[str, ...] = ()) -> None:
    if result.get("ok"):
        return
    err = result.get("error", "unknown")
    if err in ok_errors:
        print(f"  ↳ {method}: {err} (treated as ok)")
        return
    print(json.dumps(result, indent=2))
    sys.exit(f"FATAL: {method} failed: {err}")


def normalize_name(name: str) -> str:
    """Slack lowercases + restricts to a-z0-9-_."""
    n = name.lower()
    n = re.sub(r"[^a-z0-9_-]+", "-", n)
    n = re.sub(r"-+", "-", n).strip("-")
    return n[:21]


def patch_config_with_prompt(channel_id: str, channel_name: str, prompt: str) -> None:
    """Append a new entry under slack.channel_prompts. Idempotent: skip if ID exists."""
    text = CONFIG_FILE.read_text()
    if channel_id in text:
        print(f"  ↳ config.yaml already has {channel_id} — skipping patch")
        return

    # Find the channel_prompts: block. We append the new entry just before the
    # next top-level YAML key (anything starting at column 0 that isn't whitespace).
    lines = text.splitlines(keepends=True)
    in_block = False
    block_indent_seen = False
    insert_at = None
    base_indent = "    "  # match existing 4-space indent under channel_prompts:

    for i, line in enumerate(lines):
        stripped = line.rstrip("\n")
        if not in_block:
            if re.match(r"^\s*channel_prompts:\s*$", stripped):
                in_block = True
            continue
        # We're inside the block — detect the end (a non-indented line that isn't blank).
        if stripped == "":
            continue
        if re.match(r"^\S", stripped):
            insert_at = i
            break
        block_indent_seen = True

    if not in_block:
        sys.exit("FATAL: could not find slack.channel_prompts: in config.yaml")
    if insert_at is None:
        insert_at = len(lines)
    if not block_indent_seen:
        print("  ⚠ slack.channel_prompts block looks empty; appending as first entry")

    # Indent the prompt body by 6 spaces (4 for the block + 2 for the YAML pipe scalar).
    prompt_indented = "\n".join(f"{base_indent}  {ln}" if ln else ""
                                 for ln in prompt.splitlines())
    new_entry = (
        f"\n{base_indent}# #{channel_name}\n"
        f"{base_indent}{channel_id}: |\n"
        f"{prompt_indented}\n"
    )
    lines.insert(insert_at, new_entry)
    CONFIG_FILE.write_text("".join(lines))
    print(f"  ↳ patched {CONFIG_FILE} with {channel_id}")


def restart_gateway(dry_run: bool) -> None:
    if dry_run:
        print("  ↳ DRY RUN: would run:", " ".join(RESTART_CMD))
        return
    print(f"  ↳ running: {' '.join(RESTART_CMD)}")
    res = subprocess.run(RESTART_CMD, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr, file=sys.stderr)
        sys.exit(f"FATAL: gateway restart returned {res.returncode}")
    print("  ↳ gateway restart queued (completes after this script exits)")


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True, help="Channel name (lowercase-hyphenated)")
    ap.add_argument("--purpose", required=True, help="Channel purpose (≤ 250 chars)")
    ap.add_argument("--topic", default="", help="Channel topic (one-liner, optional)")
    ap.add_argument("--personality-prompt-file", required=True, type=Path,
                    help="File containing the channel_prompt body (plain text, 2–4 paragraphs)")
    ap.add_argument("--canvas-file", required=True, type=Path,
                    help="Markdown file containing the canvas body")
    ap.add_argument("--canvas-title", default="",
                    help="Canvas tab title (default: derived from channel name)")
    ap.add_argument("--intro", default="",
                    help="Intro message posted to the new channel after wiring")
    ap.add_argument("--private", action="store_true",
                    help="Create as private channel (default: public)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate inputs + print plan; do not call API or restart gateway")
    ap.add_argument("--no-restart", action="store_true",
                    help="Skip the gateway restart (use when batching multiple channels; "
                         "caller is responsible for running `sudo systemctl restart "
                         "hermes-gateway.service` afterward). The new prompt won't take "
                         "effect until the gateway restarts.")
    args = ap.parse_args()

    name = normalize_name(args.name)
    if name != args.name:
        print(f"⚠ Normalized name: {args.name!r} → {name!r}")
    if len(args.purpose) > 250:
        sys.exit(f"FATAL: purpose is {len(args.purpose)} chars; Slack max is 250")
    if not args.personality_prompt_file.exists():
        sys.exit(f"FATAL: prompt file not found: {args.personality_prompt_file}")
    if not args.canvas_file.exists():
        sys.exit(f"FATAL: canvas file not found: {args.canvas_file}")

    prompt = args.personality_prompt_file.read_text().rstrip() + "\n"
    canvas_md = args.canvas_file.read_text()
    canvas_title = args.canvas_title or name.replace("-", " ").title()

    env = load_env()
    token = env.get("SLACK_BOT_TOKEN")
    if not token:
        sys.exit("FATAL: SLACK_BOT_TOKEN missing from ~/.hermes/.env")
    invitees_raw = env.get("SLACK_ALLOWED_USERS", "").strip()
    invitees = [u.strip() for u in invitees_raw.split(",") if u.strip()]

    print(f"=== Plan: create #{name} ===")
    print(f"  visibility : {'private' if args.private else 'public'}")
    print(f"  purpose    : {args.purpose}")
    print(f"  topic      : {args.topic or '(none)'}")
    print(f"  invitees   : {invitees or '(none — only the bot)'}")
    print(f"  prompt     : {len(prompt)} chars")
    print(f"  canvas     : {len(canvas_md)} chars, title {canvas_title!r}")
    print(f"  intro      : {args.intro or '(none)'}")
    print()

    if args.dry_run:
        print("=== DRY RUN — exiting before any API call ===")
        return 0

    # 1. Name-collision check
    print("[1/8] conversations.list — name collision check")
    cursor = ""
    while True:
        result = slack(token, "conversations.list",
                       {"types": "public_channel,private_channel",
                        "limit": "1000",
                        "exclude_archived": "false",
                        "cursor": cursor}, form=True)
        must_ok("conversations.list", result)
        for c in result.get("channels", []):
            if c["name"] == name or c.get("name_normalized") == name:
                sys.exit(f"FATAL: channel #{c['name']} already exists ({c['id']})")
        cursor = result.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            break
    print(f"  ↳ no collision for #{name}")

    # 2. Create channel
    print("[2/8] conversations.create")
    result = slack(token, "conversations.create",
                   {"name": name, "is_private": args.private})
    must_ok("conversations.create", result)
    channel = result["channel"]
    channel_id = channel["id"]
    print(f"  ↳ created {channel_id}  (#{name})")

    # 3. Invite users (best-effort)
    if invitees:
        print(f"[3/8] conversations.invite ({len(invitees)} user(s))")
        result = slack(token, "conversations.invite",
                       {"channel": channel_id, "users": ",".join(invitees)})
        # Slack returns ok=false if ANY user fails; tolerate the common no-ops.
        if not result.get("ok"):
            err = result.get("error", "")
            if err in ("already_in_channel", "cant_invite_self"):
                print(f"  ↳ {err} (ok)")
            else:
                # Per-user error list may be in `errors`
                errs = result.get("errors") or []
                print(f"  ⚠ invite returned: {err}")
                for e in errs:
                    print(f"    - {e.get('user','?')}: {e.get('error','?')}")
                # Don't abort — channel exists, wiring still useful
        else:
            print(f"  ↳ invited: {','.join(invitees)}")
    else:
        print("[3/8] (no invitees configured — skipping)")

    # 4. Purpose + topic
    print("[4/8] conversations.setPurpose + setTopic")
    result = slack(token, "conversations.setPurpose",
                   {"channel": channel_id, "purpose": args.purpose})
    must_ok("conversations.setPurpose", result)
    if args.topic:
        result = slack(token, "conversations.setTopic",
                       {"channel": channel_id, "topic": args.topic})
        must_ok("conversations.setTopic", result)
    print(f"  ↳ purpose + topic set")

    # 5. Canvas: create the document, then attach as channel tab.
    print("[5/8] canvases.create + conversations.canvases.create")
    result = slack(token, "canvases.create",
                   {"title": canvas_title,
                    "document_content": {"type": "markdown", "markdown": canvas_md}})
    must_ok("canvases.create", result)
    canvas_id = result["canvas_id"]
    result = slack(token, "conversations.canvases.create",
                   {"channel_id": channel_id, "document_content":
                    {"type": "markdown", "markdown": canvas_md},
                    "title": canvas_title})
    # If the channel auto-provisioned its own canvas, edit it instead.
    if not result.get("ok") and result.get("error") == "channel_canvas_already_exists":
        print("  ↳ channel already has a canvas; editing instead")
        # Look up the existing channel canvas id
        info = slack(token, "conversations.info",
                     {"channel": channel_id}, form=True)
        must_ok("conversations.info", info)
        tabs = info.get("channel", {}).get("properties", {}).get("tabs", [])
        existing = next((t for t in tabs if t.get("type") == "canvas"), None)
        if existing:
            file_id = existing["data"]["file_id"]
            edit = slack(token, "canvases.edit",
                         {"canvas_id": file_id,
                          "changes": [{"operation": "replace",
                                       "document_content":
                                          {"type": "markdown", "markdown": canvas_md}}]})
            must_ok("canvases.edit", edit)
            print(f"  ↳ edited existing channel canvas {file_id}")
        else:
            print("  ⚠ channel reported existing canvas but none found in tabs; skipping")
    else:
        must_ok("conversations.canvases.create", result)
        print(f"  ↳ canvas {canvas_id} attached to {channel_id}")

    # 6. Patch config.yaml
    print("[6/8] patch ~/.hermes/config.yaml channel_prompts")
    patch_config_with_prompt(channel_id, name, prompt)

    # 7. Restart gateway (unless --no-restart for batched runs)
    if args.no_restart:
        print("[7/8] (--no-restart) — caller must run: sudo systemctl restart hermes-gateway.service")
    else:
        print("[7/8] restart hermes-gateway.service")
        restart_gateway(dry_run=False)

    # 8. Intro message
    if args.intro:
        print("[8/8] chat.postMessage (intro)")
        if not args.no_restart:
            # Tiny pause so the restart-triggered drain doesn't race the post.
            time.sleep(2)
        result = slack(token, "chat.postMessage",
                       {"channel": channel_id, "text": args.intro})
        must_ok("chat.postMessage", result)
        print(f"  ↳ intro posted: {result.get('ts')}")
    else:
        print("[8/8] (no intro message)")

    print()
    print("=== DONE ===")
    print(json.dumps({
        "channel_id": channel_id,
        "channel_name": name,
        "canvas_id": canvas_id,
        "invitees_invited": invitees,
        "config_patched": str(CONFIG_FILE),
        "gateway_restarted": not args.no_restart,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
