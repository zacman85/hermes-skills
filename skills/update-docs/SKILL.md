---
name: update-docs
description: Synchronize documentation with codebase changes before commits. Index-based docs that point to code, never duplicate it.
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [documentation, docs]
    related_skills: [git-auto-commit, maintain-tests]
---

# Update Docs

Maintain streamlined, index-based documentation that helps agents build context efficiently. Use before commits that affect docs, architecture, or configuration.

## Core Philosophy: Index, Not Duplication

Documentation should **point to code**, not **duplicate code**.

**Bad** (duplicates, drifts out of sync):
```markdown
## Commands
- `make setup` - Creates venv and installs deps
- `make test` - Runs pytest with coverage
- `make databases` - Starts MongoDB (OUTDATED!)
```

**Good** (indexes to source of truth):
```markdown
## Commands
Run `make help` for all available commands. Key commands:
- `make setup` - Initial setup
- `make test` - Run tests (see Makefile for options)
```

## Priority Order

1. **Schema/Architecture** (source of truth): Mermaid diagrams, schema files, ADRs
2. **Code** (derived from schema): Docstrings, type hints, inline comments
3. **Indexes** (point to truth): README.md, CLAUDE.md, docs/*.md

## What Belongs in Project Docs

**Include:**
- Overview (1-2 sentences: what this project does)
- Quick Start (minimal commands, point to Makefile)
- Architecture (high-level structure, point to schema files and key directories)
- Key Concepts (domain-specific terminology unique to this project)
- Development (point to Makefile, key workflows, testing approach)

**Does NOT belong:**
- Duplicated Makefile commands
- Code implementation details
- Full API documentation (point to OpenAPI)
- Configuration values (point to config files)

## Multi-Repository Documentation

**Workspace-level** (monorepo root):
- Overview of all repositories
- Shared patterns and conventions
- Inter-service communication
- Development setup across repos

**Project-level** (per-repo):
- Project-specific details only
- Points to workspace docs for shared info
- Doesn't duplicate workspace-level content

## When to Create vs Update vs Delete

**Create:** New major feature needs architectural explanation, new repo added, new integration pattern, decision record needed

**Update:** File paths or locations changed, commands or workflows changed, existing feature modified, pointers are stale/broken

**Delete:** Feature/code it describes is removed, it duplicates information available elsewhere, it's consistently out of sync (replace with pointer)

## Pre-Commit Checklist

1. Are schema/architecture diagrams current?
2. Are docstrings accurate for changed functions?
3. Do indexes (README, CLAUDE.md) point to correct locations?
4. Is anything duplicated that could drift?
5. For multi-repo changes: is workspace-level doc updated?

## Rules

**NEVER duplicate:** Makefile commands in markdown, code structure in docs, configuration details, schema details outside schema files

**ALWAYS prefer:** "See `file.py:123`" over "the implementation does X, Y, Z"; "Run `make help`" over listing all commands; updating docstrings over updating markdown

## Pitfalls

- If the project uses schema-first development, edit the schema source of truth (e.g. a `.mmd` data-schema file) before modifying models
- `CLAUDE.md` / `AGENTS.md` files in sub-repos are the primary context source for coding agents — keep them accurate
- If the project generates a CLI/SDK from an API spec, operation IDs often follow a `<resource>_<operation>` convention — document changes there
