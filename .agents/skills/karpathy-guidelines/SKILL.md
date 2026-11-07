---
name: karpathy-guidelines
description: Behavioral guidelines to reduce common LLM coding mistakes, derived from Andrej Karpathy's observations. Activate when planning, writing, reviewing, or refactoring code to avoid overcomplication, enforce surgical changes, surface hidden assumptions, and maintain goal-driven verification loops.
---

# Karpathy Guidelines Skill

Behavioral guidelines to reduce common LLM coding mistakes, derived from Andrej Karpathy's observations on LLM coding pitfalls.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

---

## 1. When to Use This Skill

Activate this skill when:
- Designing new features, scripts, or components.
- Modifying, debugging, or refactoring existing codebases.
- Reviewing pull requests or checking diffs before committing.
- Preventing AI agent anti-patterns: over-engineering, unrequested refactors, drive-by formatting edits, or silent assumptions.

---

## 2. The Four Core Principles

### Principle 1: Think Before Coding
**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before writing code:
- **State assumptions explicitly**: If requirement details or constraints are ambiguous, present them rather than guessing.
- **Multiple interpretations**: If more than one valid approach exists, present the tradeoffs to the user.
- **Simpler path**: If there is a vastly simpler approach that accomplishes the goal with less complexity, suggest it.
- **Stop when unclear**: Identify the exact point of confusion and clarify before making changes.

### Principle 2: Simplicity First
**Minimum code that solves the problem. Nothing speculative.**

- **No unrequested features**: Implement only what was requested.
- **No single-use abstractions**: Avoid building generic frameworks, wrapper classes, or helper hierarchies for code used once.
- **No speculative flexibility**: Avoid premature configurability or future-proofing flags that haven't been asked for.
- **No defensive code for impossible states**: Avoid layers of error-handling for conditions that cannot happen.
- **Senior engineer sniff test**: *"Would a senior engineer say this is overcomplicated?"* If yes, refactor down to the essential logic.

### Principle 3: Surgical Changes
**Touch only what you must. Clean up only your own mess.**

When modifying existing files:
- **No drive-by improvements**: Do not reformat adjacent lines, rewrite existing comments, or "clean up" unrelated functions.
- **Preserve existing style**: Follow local conventions and idioms, even if you would personally format them differently.
- **Orphan management**: Clean up variables, imports, or helper methods that your changes made obsolete, but do not delete pre-existing dead code unless explicitly requested.
- **Diff traceability**: Every line in `git diff` should trace directly to the user's requirement.

### Principle 4: Goal-Driven Execution
**Define success criteria. Loop until verified.**

Transform tasks into verifiable milestones before touching code:
- **Bug fix**: Write a reproducing test or test script, run it to confirm failure, apply the fix, and confirm pass.
- **New feature**: Define the exact command or test that demonstrates success.
- **Refactoring**: Ensure all existing tests pass before touching code, and remain passing after.

Use an explicit step-by-step verification plan:
```
1. [Step] → verify: [command / test]
2. [Step] → verify: [command / test]
3. [Step] → verify: [command / test]
```

---

## 3. Pre-Commit Checklist

Before pushing or opening a PR:
- [ ] Did I make any unrequested architectural additions?
- [ ] Does `git diff` contain any modifications to unrelated lines or files?
- [ ] Have all assumptions been validated or communicated?
- [ ] Are the success criteria and tests passing?
