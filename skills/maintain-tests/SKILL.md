---
name: maintain-tests
description: Analyze and maintain unit test suite quality, coverage, and relevance across a codebase.
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [testing, quality, coverage]
    related_skills: [git-auto-commit, update-docs]
---

# Maintain Tests

Maintain clean, relevant, high-value test suites. Use after completing features, during PR prep, when tests are bloated, after removing features, or when coverage reports show gaps.

## Coverage Standards

| Code Type | Minimum Coverage |
|-----------|-----------------|
| General code | 80% |
| Security code (auth, permissions, tokens) | 95% |
| Data mutation (database writes, state changes) | 95% |
| Business logic (payments, billing, workflows) | 95% |

## Test Organization

**Naming convention:**
- Test file: `test_<module_name>.py` (Python) or `<module>.test.ts` (TypeScript)
- Test class: `Test<ClassName>` (maps to class being tested)
- Test method: `test_<method>_<scenario>_<expected>`

## Testing Philosophy: Real Functionality Over Mocks

**Good tests:**
- Test actual behavior with real domain objects
- Use real enums: `Permission.SOURCE_WRITE` not `"source.write"`
- Verify actual validation functions without mocking
- Create realistic test data matching production schemas

**Bad tests:**
- Mock core business logic functions
- Only verify mock return values, not actual behavior
- Over-isolate components that naturally work together
- Exist purely to increase coverage without testing meaningful logic

## Fixture Guidelines

**Use fixtures for:** Database connections/sessions, authenticated clients, common test data, external service mocks (only external, not internal)

**Prefer inline setup when:** Test data is specific to one test, setup is simple (1-2 lines), fixture would obscure what's being tested

## Workflow

### 1. Analyze Recent Changes
- Review git history for refactorings
- Identify modified files and their test counterparts
- Note removed functions or renamed methods

### 2. Audit Tests
For each test: **Relevance** (tests code that still exists?), **Value** (verifies meaningful behavior?), **Duplication** (redundant?), **Quality** (follows philosophy?), **Speed** (unreasonably slow?)

### 3. Categorize Actions
- **Keep**: Valuable tests with meaningful coverage
- **Update**: Tests needing modification for current code
- **Remove**: Obsolete, redundant, or low-value tests
- **Add**: Missing tests for critical paths

### 4. Execute and Verify
- Run coverage: `pytest --cov=<module> --cov-report=term-missing` (Python) or `npm run test -- --coverage` (JS)
- Verify standards met for each code category
- Ensure no flaky tests introduced

## Decision Framework

**Remove when:** Code being tested no longer exists, test only verifies mock behavior, test is duplicate, test mocks core business logic, test is permanently flaky

**Update when:** Function signatures changed but concept valid, test uses deprecated patterns, assertions outdated but concept valid

**Add when:** New code paths lack coverage, security-critical code below 95%, error handling paths untested, edge cases discovered

## Flaky Test Handling

- Add explicit waits instead of `time.sleep()` (use polling)
- Isolate test data (unique IDs per test)
- Mock external services, not internal code
- Run suspicious tests in loop: `pytest test_file.py --count=10`

## Discovering Test Commands

Find the project's test entry point before running anything — don't assume:

- **Makefile** → `make test` (check `make help` for coverage/subset targets)
- **Python** → `pytest`, often `pytest --cov=<module> --cov-report=term-missing`
- **JS/TS** → `npm run test` / `npm run test -- --coverage` (check `package.json` scripts)
- **Rust** → `cargo test` (or `make test` if wrapped)

Note any environment prerequisites (a local database, a service running, a specific
runner host/GPU box) — capture these per-project as you discover them so reruns are reproducible.

## Pitfalls

- Some test suites have hard environment requirements (a specific runner/GPU host, a local database, an external service). Discover and document these before running — failing tests are often missing prerequisites, not real regressions.
- Integration/e2e suites may target a shared staging environment — never point them at production or localhost unless the project explicitly supports it.
- When tests fail after code changes, assume tests need updating (not that code needs reverting) — ask the user if unsure.
