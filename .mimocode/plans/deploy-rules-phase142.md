# Deploy Rules — added to session context (user requested in .loop.md but permission denied)

## HARTE DEPLOY-REGELN (nach Phase 142 Outage)

### VERBOTEN
1. **`k3s ctr images prune --all`** — löscht ALLE ungenutzten Images inkl. CNPG, Init Container, etc. → DiskPressure → Ketten-Eviction
2. **`kubectl delete pods --force --grace-period=0`** auf mehrere Pods gleichzeitig
3. **`docker build --no-cache`** — unnötig, verursacht 3+ min Rebuilds ohne Mehrwert

### PFLICHT
1. **Deploy-Schritte in exakter Reihenfolge:**
   - `docker build -t <image>:<tag> .`
   - `docker save <image>:<tag> | sudo k3s ctr image import -`
   - `kubectl set image deployment/X container=<image>:<tag> -n meeting-automation-staging`
   - `kubectl rollout status deployment/X -n meeting-automation-staging`
2. **Alte Images nur gezielt entfernen:**
   - `sudo k3s ctr image rm <exakter-image-name>` (NIE prune --all!)
3. **Vor Deploy prüfen:**
   - `kubectl get pods` → keine Evicted/Error Pods
   - `kubectl get clusters.postgresql.cnpg.io meeting-db` → Healthy
   - `df -h /` → kein Disk-Pressure
4. **CNPG Policy: Port 8000 (Instance Manager) MUSS freigegeben sein** neben Port 5432
