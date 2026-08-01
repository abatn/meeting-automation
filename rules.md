rules.md
# REGELN — Meeting Automation

## Git
- **Git ist VERBOTEN ohne explizite Erlaubnis des Users**
- Keine Commits, Pushes, Merges, Rebases ohne Freigabe
- `git add`, `git commit`, `git push` — nur auf ausdrücklichen Befehl

## Docker/k3s
- **`docker image prune` ist VERBOTEN** (AGENTS.md Z.64)
- **`docker system prune` ist VERBOTEN** (AGENTS.md Z.64)
- **Deploy-Pattern**: build → k3s ctr image import → kubectl set image → rollout restart
- **Niemals während des Deploys löschen**

## Commands
- **`rm` ist blockiert** — nur `sudo rm` verwenden
- **`git` ist verboten** — nur mit Erlaubnis
- **dont make mistake ** - 100% solution
