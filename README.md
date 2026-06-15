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
| `slack-search` | Search Slack messages, files, and channels via the Web API — find vaguely-referenced files/messages, cross-reference chat with tickets/PRs, pull historical decisions. Workspace-agnostic: a bootstrap step self-discovers your workspace IDs on first use. Reads `SLACK_BOT_TOKEN` from `~/.hermes/.env` at runtime. |
| `git-auto-commit` | Analyze git changes, group them into atomic commits with conventional commit messages, handle pre-commit hooks safely, and optionally push. |
| `update-docs` | Keep documentation in sync with code using index-not-duplication discipline — docs point to source of truth, never copy it. Run before commits that touch docs/architecture/config. |
| `maintain-tests` | Audit and maintain a unit test suite for relevance, coverage, and value — real-functionality-over-mocks philosophy, tiered coverage standards, flaky-test handling. |

## Notes

- Skills read all secrets from `~/.hermes/.env` at runtime; nothing sensitive is committed here.
- `slack-channel-create` assumes a systemd-managed gateway and `sudo systemctl restart hermes-gateway.service`. Adjust the restart step if your install runs the gateway differently.
