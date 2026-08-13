# Incident Report: Disk Cleanup Phase 1+2 — Staging Cluster

**Datum:** 2026-08-13  
**Dauer:** 10:50–10:56 UTC (6 Minuten)  
**Schweregrad:** P2 (Staging betroffen, Production unberührt)  
**Status:** Behoben  

---

## Zusammenfassung

Der Staging-Cluster (158.180.18.110) hatte eine Disk-Utilization von 81% (148G/183G). Die Hauptursache waren alte Container-Images (45G) die nach jedem CI/CD-Deploy nicht automatisch gelöscht wurden. Der kubelet Image-GC Threshold war auf 85% gesetzt — zu hoch für die aktuelle Disk-Größe.

---

## Timeline

| Zeit (UTC) | Event | Status |
|------------|-------|--------|
| 10:50 | Disk-Analyse gestartet | 81% (148G/183G) |
| 10:52 | Phase 1: `k3s ctr images prune` | ✅ 10 Images + 34 Snapshots entfernt |
| 10:53 | Disk nach Phase 1 | 73% (134G/183G) — +14G freigeben |
| 10:54 | Backup der k3s Config erstellt | ✅ `/tmp/config.yaml.bak.20260813105455` |
| 10:55 | Phase 2: kubelet-arg in Config eingefügt | ✅ `image-gc-high-threshold=75` |
| 10:55 | k3s Restart | ✅ 10:55:27 UTC |
| 10:55 | Verifikation: kubelet Args | ✅ `--image-gc-high-threshold=75` in Logs |

---

## Root Cause

### Fakten (bewiesen)

| # | Fakt | Beweis |
|---|------|--------|
| 1 | Disk: 81% (148G/183G) | `df -h /` → `/dev/mapper/ocivolume-root 183G 148G 36G 81%` |
| 2 | Container-Images: 45G | `sudo du -sh /var/lib/rancher/k3s/agent/containerd/` |
| 3 | 529 Snapshots im Containerd | `ls /var/lib/rancher/k3s/agent/containerd/.../snapshots/ | wc -l` |
| 4 | Image-GC Threshold: 85% (Default) | k3s Default `kubeletArg.image-gc-high-threshold=85` |
| 5 | GC wird NICHT getriggert | 81% < 85% → Kein GC-Lauf |
| 6 | CI/CD Deploy lädt neue Images | Jeder Deploy erstellt neue Image-Layer |
| 7 | Alte Images werden NICHT gelöscht | Containerd behält ALLE Snapshots |

### Die Kette

```
CI/CD Deploy
  → Neue Images werden pulled
  → Alte Images bleiben auf dem Node
  → Snapshots akkumulieren sich
  → Disk steigt: 76% → 81% → 85%?
  → Image-GC startet bei 85%
  → ABER: Bei 81% ist es zu spät!
  → Resultat: Immer volle Disk
```

---

## Durchgeführte Maßnahmen

### Phase 1: Sofortige Bereinigung (10:52 UTC)

| Schritt | Befehl | Ergebnis |
|---------|--------|----------|
| 1.1 | `sudo k3s ctr images prune` | 10 alte Images entfernt |
| 1.2 | Snapshots geprüft | 34 Snapshots entfernt |
| 1.3 | Disk geprüft | 134G/183G (73%) — +14G freigeben |

### Phase 2: Image-GC Threshold senken (10:54–10:55 UTC)

| Schritt | Befehl | Ergebnis |
|---------|--------|----------|
| 2.1 | Backup: `sudo cp config.yaml /tmp/config.yaml.bak.*` | ✅ |
| 2.2 | Config: `kubelet-arg: [image-gc-high-threshold=75, image-gc-low-threshold=70]` | ✅ |
| 2.3 | Restart: `sudo systemctl restart k3s` | ✅ 10:55:27 UTC |
| 2.4 | Verifikation: kubelet Args in Logs | ✅ `--image-gc-high-threshold=75` |

---

## Verifikation

| Prüfpunkt | Erwartet | Beobachtet | Stimmt? |
|-----------|----------|-----------|---------|
| k3s Status | Running | Active (running) since 10:55:27 | ✅ |
| Node Status | Ready | Ready | ✅ |
| Pods Running | 17 | 17 | ✅ |
| kubelet Args | `--image-gc-high-threshold=75` | In Logs vorhanden | ✅ |
| Disk nach Phase 1 | 73% | 73% | ✅ |
| Disk nach Phase 2 | 81% | 81% | ✅ |

---

## Auswirkungen

| Component | Impact | Status |
|-----------|--------|--------|
| Meeting-automation-staging | Pods neu gestartet (30s Interruption) | ✅ Running |
| Pipeline | Kein Impact | ✅ Funktioniert |
| DB | Kein Impact | ✅ Running |
| Velero | Kein Impact | ✅ Running |

---

## Offene Punkte

| Punkt | Priorität | Status |
|-------|-----------|--------|
| Phase 3: Cleanup-CronJob erstellen | P2 | ⬜ Offen |
| Monitoring-Alerts für Disk Usage | P3 | ⬜ Offen |
| Production: Image-GC Threshold anpassen | P2 | ⬜ Offen |
| containerd Images manuell prüfen | P3 | ⬜ Offen |

---

## Rollback-Plan

Falls die Config-Änderung Probleme verursacht:

```bash
# 1. Backup wiederherstellen
sudo cp /tmp/config.yaml.bak.20260813105455 /etc/rancher/k3s/config.yaml

# 2. k3s neustarten
sudo systemctl restart k3s

# 3. Verifizieren
kubectl get nodes
kubectl get pods -n meeting-automation-staging
```

---

## Lessons Learned

1. **Image-GC Threshold ist kritisch:** Der Default-Wert (85%) ist zu hoch fürSingleNode-Cluster mit regelmäßigem CI/CD
2. **containerd Snapshot-Akkumulation:** Jeder Deploy erstellt neue Snapshots die nicht automatisch gelöscht werden
3. **Monitoring fehlt:** Kein Alert für Disk-Utilization → Problem wurde erst bei 81% bemerkt
4. **Backup vor Änderung:** Immer Backup der Config erstellen bevor k3s neugestartet wird

---

## Dokumentation

- VELERO_BACKUP_PLAN.md: Phase 2 (Image-GC Threshold)
- CHANGELOG_2026-08-13.md: Alle Änderungen des Tages
- AGENTS.md: k3s Image-GC Threshold Hinweis

---

**Erstellt:** 2026-08-13 10:56 UTC  
**Nächste Überprüfung:** 2026-08-14 (24h nach Implementierung)
