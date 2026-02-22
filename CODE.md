# CODE.md — Development Workflow & Conventions

**This document defines the mandatory workflow for all code changes in this project.**
Every contributor (human or AI agent) must follow these rules before writing any code.

---

## 1. Branch First

Before starting any work, create a new branch from `main`.

- The branch name must concisely summarize the task being performed.
- Use a descriptive prefix: `feat/`, `fix/`, `refactor/`, `docs/`, `test/`, `chore/`.
- Examples:
  - `feat/add-dark-mode-toggle`
  - `fix/telegram-url-escaping`
  - `refactor/notion-handler-dedup`
  - `docs/add-code-conventions`

```bash
git checkout -b <prefix>/<short-description>
```

**Never commit directly to `main`.**

---

## 2. Test-Driven Development (TDD)

All code must be written following the TDD cycle:

1. **Red** — Write a failing test that defines the expected behavior.
2. **Green** — Write the minimum code to make the test pass.
3. **Refactor** — Clean up the implementation while keeping all tests green.

### Rules

- Write tests **before** implementation code.
- Each new function, bug fix, or behavior change requires at least one corresponding test.
- Run the full test suite after every change:

```bash
uv run pytest tests/ -v
```

- All tests must pass before proceeding to the next step.
- Never delete or skip failing tests to make the suite pass.

---

## 3. Code Review

After completing the implementation (all tests green, no lint errors):

1. **Self-review** the changes — read every diff line for correctness, style, and edge cases.
2. **Verify** that the code follows existing project patterns and conventions.
3. **Run diagnostics** — ensure no type errors, lint warnings, or regressions.
4. **Check test coverage** — confirm that new/changed behavior is adequately tested.

### Review Checklist

- [ ] All tests pass (`uv run pytest tests/ -v`)
- [ ] No type errors or lint issues
- [ ] Code follows existing project conventions
- [ ] Edge cases are handled and tested
- [ ] No hardcoded secrets or credentials
- [ ] Documentation updated if public API changed

---

## 4. Pull Request

If the review passes, create a pull request:

1. Push the branch to the remote repository.
2. Create a PR with a clear title and summary describing what changed and why.
3. The PR description should include:
   - A concise summary of the changes
   - Link to any related issues
   - Testing evidence (e.g., test results)

```bash
git push -u origin <branch-name>
gh pr create --title "<descriptive title>" --body "<summary>"
```

---

## Workflow Summary

```
main
 └─ git checkout -b feat/my-feature
     ├─ 1. Write failing test (Red)
     ├─ 2. Implement code (Green)
     ├─ 3. Refactor
     ├─ 4. Run full test suite
     ├─ 5. Self-review all changes
     └─ 6. Create PR if review passes
```