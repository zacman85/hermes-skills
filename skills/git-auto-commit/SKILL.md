---
name: git-auto-commit
description: Intelligently analyze git changes, create atomic commits with detailed conventional commit messages, and optionally push.
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [git, commits, automation]
    related_skills: [github-pr-workflow]
---

# Git Auto-Commit

Create clean, atomic commits with intelligent grouping and detailed messages.

## Core Workflow

1. **Analyze**: `git status --porcelain`, `git diff`, `git diff --staged`, `git log --oneline -5`
2. **Group**: Organize changes into logical atomic commits
3. **Commit**: Create commits with conventional commit messages
4. **Push**: Push to remote if requested (with `-u` flag for new branches)

## Branch Policy

**Always use feature branches** except for very small one-off changes (typo fixes, single-line config changes).

- On `main`/`master` with substantial changes → Create feature branch first
- On `main`/`master` with tiny one-off → OK to commit directly
- Already on feature branch → Continue on current branch

**Branch naming**: `feature/<name>`, `fix/<name>`, `refactor/<name>`, `docs/<name>`

## Intelligent Grouping Rules

**Group by change type and cohesion:**
- Feature implementation files together (API + service + models)
- Tests separate from implementation (unless small fix+test)
- Documentation separate when substantial
- Refactoring separate from behavior changes

**Never mix:**
- Features and bug fixes
- Refactoring and new functionality
- Unrelated features

## Commit Message Format

```
<type>(<scope>): <subject>

<body explaining what and why>

🤖 Generated with [Claude](https://claude.ai)

```

Use HEREDOC for multi-line messages:
```bash
git commit -m "$(cat <<'EOF'
<message here>
EOF
)"
```

**Types:** `feat`, `fix`, `refactor`, `docs`, `test`, `ci`, `chore`, `perf`

## Pre-Commit Hook Handling

When hooks fail:

**Linting failures:**
- Run formatters automatically (`ruff format`, `black`, `isort`, `eslint --fix`)
- Re-stage formatted files and retry commit

**Test failures:**
- Check if tests are outdated (testing old behavior) → Update tests automatically
- Check if tests reveal a real bug → **STOP AND ASK** user
- If unclear → **STOP AND ASK** user

**Hook modified files (e.g., formatters changed code):**
- If commit succeeded but files were modified: safe to amend
- Check authorship first: `git log -1 --format='%an %ae'`
- Only amend your own commits, never others'

## CRITICAL: Never Revert User's Code

When tests fail after code changes:

**DO automatically:**
- Update test assertions to match new behavior
- Fix test signatures to match new parameters
- Run formatters (ruff, black, isort)

**NEVER automatically:**
- Revert function parameter changes
- Revert logic/algorithm changes
- Revert API modifications

**When unsure:** Stop and ask the user. Assume tests need updating, not that code needs reverting.

## Safety Rules

**Never without explicit permission:**
- `git reset --hard`
- `git push --force`
- `git rebase` on shared branches
- Delete branches

**Always:**
- Check `git status` before operations
- Verify branch before pushing
- Use the repo's configured git identity (`git config user.name` / `user.email`)

## Pitfalls

- Always use `git push -u origin HEAD` for new branches (not branch name)
- For GitHub API calls, prefer the `gh` CLI if available; otherwise use git + curl with a token from your credential helper
- Multi-line commit messages need HEREDOC or `-m` flag per line
- Check for unstaged changes before committing — `git add` only what belongs in each atomic commit
