# Workspace Rules

## Git Workflow & Branch Protection
- **Never Commit or Push Directly to Main**: You are STRICTLY FORBIDDEN from committing or pushing changes directly to `main` (or `master`).
- **Feature Branch & Pull Request Required**: Whenever creating, updating, or fixing code, skills, or documentation, always:
  1. Create and switch to a new descriptive feature branch (`git checkout -b feat/<name>` or `fix/<name>`).
  2. Commit changes only on the feature branch.
  3. Push the feature branch to remote origin (`git push -u origin <branch>`).
  4. Open a Pull Request using `gh pr create` for user review and merging.

## Self-Update Disambiguation & Procedure
- **Workspace Script Priority**: When the user requests "self update", "run self update", or "update yourself", ALWAYS execute the workspace updater script (`/workspace/scripts/self_update.sh`). NEVER run `agy update` directly in isolation.
- **Branch Awareness**:
  1. If currently on a feature branch that has been merged or is clean, switch to `main` (`git checkout main`) prior to running the update script so upstream commits are fetched.
  2. First run `/workspace/scripts/self_update.sh --check` or execute `/workspace/scripts/self_update.sh` to pull changes, check `agy` CLI binary updates, and trigger Docker rebuilds/restarts if infrastructure files changed.
