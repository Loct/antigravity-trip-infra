# Workspace Rules

## Git Workflow & Branch Protection
- **Never Commit or Push Directly to Main**: You are STRICTLY FORBIDDEN from committing or pushing changes directly to `main` (or `master`).
- **Feature Branch & Pull Request Required**: Whenever creating, updating, or fixing code, skills, or documentation, always:
  1. Create and switch to a new descriptive feature branch (`git checkout -b feat/<name>` or `fix/<name>`).
  2. Commit changes only on the feature branch.
  3. Push the feature branch to remote origin (`git push -u origin <branch>`).
  4. Open a Pull Request using `gh pr create` for user review and merging.
