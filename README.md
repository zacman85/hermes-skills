# hermes-skills

Personal [Hermes Agent](https://hermes-agent.nousresearch.com) skills hub.

Add this repo as a skill tap on any machine, then install skills from it:

```bash
hermes skills tap add zacman85/hermes-skills
hermes skills search slack
hermes skills install slack-channel-create
```

Each top-level directory is one skill (a `SKILL.md` plus optional
`scripts/`, `references/`, `templates/`, `assets/`).

## Skills

| Skill | Description |
|-------|-------------|
| `slack-channel-create` | Create a Slack channel end-to-end — provision, invite, set purpose/topic, attach a canvas, wire a per-channel personality prompt in `config.yaml`, and restart the gateway. Reads `SLACK_BOT_TOKEN` + `SLACK_ALLOWED_USERS` from `~/.hermes/.env` at runtime. |

## Notes

- Skills read all secrets from `~/.hermes/.env` at runtime; nothing sensitive is committed here.
- `slack-channel-create` assumes a systemd-managed gateway and `sudo systemctl restart hermes-gateway.service`. Adjust the restart step if your install runs the gateway differently.
