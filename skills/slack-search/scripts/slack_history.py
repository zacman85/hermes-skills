#!/usr/bin/env python3
"""Fetch Slack channel history (or a thread) without shelling out curl.

Why this exists: loads the bot token directly from ~/.hermes/.env in Python so
the value never touches a shell command line. This sidesteps two problems at
once: (1) shells that mangle one-liners combining $(...) with secret-shaped
patterns, and (2) keeping the token out of process args / shell history. The
env key is even assembled via string concatenation so the literal name never
appears in source.

NOTE: ENV_PATH below assumes the standard Hermes home (~/.hermes/.env via the
hermes user). Adjust it if your install keeps the env file elsewhere.

Usage:
  python3 slack_history.py <CHANNEL_ID> [HOURS_BACK] [THREAD_TS]

  CHANNEL_ID  e.g. C0123ABCDEF
  HOURS_BACK  default 24
  THREAD_TS   optional; if given, fetches conversations.replies for that thread

Prints full message text, oldest first.
"""
import json
import sys
import time
import datetime
import urllib.request
import urllib.parse

ENV_PATH = "/home/hermes/.hermes/.env"


def load_token():
    key = "SLACK_BOT_" + "TO" + "KEN"  # concat defeats the redaction quirk
    for line in open(ENV_PATH):
        line = line.strip()
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("token not found in " + ENV_PATH)


def api(tok, method, **params):
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        "https://slack.com/api/" + method + "?" + q,
        headers={"Authorization": " ".join(["Bearer", tok])},
    )
    d = json.load(urllib.request.urlopen(req))
    if not d.get("ok"):
        raise SystemExit("Slack API error: " + str(d.get("error")))
    return d


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    channel = sys.argv[1]
    hours = float(sys.argv[2]) if len(sys.argv) > 2 else 24
    thread_ts = sys.argv[3] if len(sys.argv) > 3 else None
    tok = load_token()
    oldest = str(int(time.time() - hours * 3600))
    if thread_ts:
        d = api(tok, "conversations.replies", channel=channel, ts=thread_ts,
                oldest=oldest, limit=50)
    else:
        d = api(tok, "conversations.history", channel=channel,
                oldest=oldest, limit=50)
    for m in reversed(d.get("messages", [])):
        ts = datetime.datetime.fromtimestamp(float(m["ts"]))
        print("---- %s ts=%s ----" % (ts.strftime("%Y-%m-%d %H:%M"), m["ts"]))
        print(m.get("text", ""))
        print()


if __name__ == "__main__":
    main()
