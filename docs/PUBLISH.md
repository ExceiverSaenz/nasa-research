# First publication from PowerShell

Run these commands only inside this exported repository directory, not the parent research workspace.

```powershell
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git
git init -b main
git add .
git diff --cached --stat
git commit -m "Initial research code and analysis snapshot"
gh repo create nasa-research --private --source=. --remote=origin --push
gh repo view --web
```

The creation command creates the remote repository under the authenticated GitHub account. No repository needs to be created in the browser beforehand. If the name already exists, choose another unused name before retrying; do not overwrite an unrelated repository. After publication, invite the PI through repository Settings / Collaborators.

For subsequent changes, edit/sync this curated directory deliberately, review `git diff`, then commit and push. Changes to the parent workspace do not automatically propagate here. Keep input data outside this repository.
