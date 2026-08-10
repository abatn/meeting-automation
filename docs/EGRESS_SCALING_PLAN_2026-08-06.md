# Egress Scaling Plan — 2026-08-06

## Status
- **Staging**: ⏳ Bereit zur Umsetzung
- **Production**: ⏳ Wartet auf Staging-Verifikation

## Problem
- Egress: 1 Pod, hostNetwork, 1 CPU → Nur 1 Recording gleichzeitig
- Scaling versuch: 2. Pod Pending (hostNetwork Port-Konflikt)

## Lösung
- Egress ohne hostNetwork (offizielle LiveKit Empfehlung)
- RollingUpdate statt Recreate
- Mehrere Pods für parallele Recordings

---

## FALLBACK SCENARIOS

### Scenario 1: Egress kann LiveKit nicht erreichen
**Ursache:** WebSocket-Verbindung zu LiveKit Server funktioniert nicht
**Symptom:** Recording startet nicht, 503 Error
**Rollback:** Sofort zu hostNetwork: true zurückkehren
**Verifikation:** `kubectl logs deployment/livekit-egress-staging | grep "ws://"`

### Scenario 2: Recording funktioniert nicht
**Ursache:** Egress kann Media-Streams nicht empfangen
**Symptom:** Recording bleibt "streaming", keine Pipeline
**Rollback:** Sofort zu hostNetwork: true zurückkehren
**Verifikation:** `kubectl logs deployment/livekit-egress-staging | grep "connected"`

### Scenario 3: Pipeline wird nicht getriggert
**Ursache:** Webhook kommt nicht an oder wird ignoriert
**Symptom:** recording.status bleibt "uploaded"
**Rollback:** Sofort zu hostNetwork: true zurückkehren
**Verifikation:** `kubectl logs deployment/backend | grep "egress_ended"`

### Scenario 4: 2. Pod kann nicht starten
**Ursache:** Ressourcen oder andere Kubernetes-Probleme
**Symptom:** Pod Pending oder CrashLoopBackOff
**Rollback:** Sofort zu 1 Pod zurückkehren
**Verifikation:** `kubectl get pods -l app=livekit-egress-staging`

### Scenario 5: Recording-Qualität sinkt
**Ursache:** TCP/WebSocket ist langsamer als UDP
**Symptom:** Audio/Video desync, Stuttering
**Rollback:** Sofort zu hostNetwork: true zurückkehren
**Verifikation:** Manuelle Prüfung der Recording-Qualität

---

## IMPLEMENTIERUNGSPLAN

### Phase 1: Vorbereitung (5 Minuten)
1. **Backup erstellen**
   ```bash
   kubectl get deployment livekit-egress-staging -o yaml > /tmp/egress-backup.yaml
   kubectl get networkpolicy livekit-egress-policy -o yaml > /tmp/egress-np-backup.yaml
   ```

2. **Aktuellen Zustand dokumentieren**
   ```bash
   kubectl get pods -l app=livekit-egress-staging -o wide
   kubectl logs deployment/livekit-egress-staging --tail=10
   ```

3. **Erfolgskriterien definieren**
   - [ ] 2 Egress Pods laufen (Status=Running, Ready=1/1)
   - [ ] Recording funktioniert (status=completed)
   - [ ] Pipeline wird getriggert (Transkription + PV existieren)
   - [ ] Keine Fehler in Logs

### Phase 2: Deployment ändern (2 Minuten)
1. **Deployment patchen**
   ```bash
   kubectl patch deployment livekit-egress-staging -n meeting-automation-staging -p '{
     "spec": {
       "replicas": 2,
       "strategy": {"type": "RollingUpdate"},
       "template": {
         "spec": {
           "hostNetwork": false,
           "dnsPolicy": "ClusterFirst",
           "nodeSelector": null
         }
       }
     }
   }'
   ```

2. **Warten bis Pods starten**
   ```bash
   kubectl rollout status deployment/livekit-egress-staging --timeout=120s
   ```

3. **SOFORT PRÜFEN**
   ```bash
   kubectl get pods -l app=livekit-egress-staging -o wide
   # BEIDE Pods müssen Running sein!
   ```

### Phase 3: Verifikation (5 Minuten)
1. **Health Check**
   ```bash
   kubectl exec -n meeting-automation-staging <egress-pod> -- curl -s http://localhost:7000/health
   # Erwartet: HTTP 200
   ```

2. **LiveKit Verbindung prüfen**
   ```bash
   kubectl logs deployment/livekit-egress-staging --tail=50 | grep -i "connected\|websocket"
   ```

3. **Recording Test**
   - Login als dg@meeting.tn
   - Meeting erstellen
   - Recording starten
   - Audio senden
   - Recording stoppen
   - **PRÜFEN:** Pipeline wird getriggert?

4. **DB Status prüfen**
   ```sql
   SELECT status, egress_id FROM recordings ORDER BY created_at DESC LIMIT 3;
   # Erwartet: status=completed
   ```

### Phase 4: Rollback (falls nötig)
1. **Bei JEDEM Fehler: SOFORT STOP**
2. **Rollback ausführen**
   ```bash
   kubectl apply -f /tmp/egress-backup.yaml -n meeting-automation-staging
   kubectl rollout status deployment/livekit-egress-staging
   ```

3. **Verifikation**
   ```bash
   kubectl get pods -l app=livekit-egress-staging -o wide
   # Ein Pod muss Running sein
   ```

---

## ROLLBACK TRIGGER

| Trigger | Aktion |
|---------|--------|
| Pod nicht Running nach 2min | SOFORT ROLLBACK |
| Health Check fehlschlägt | SOFORT ROLLBACK |
| Recording startet nicht | SOFORT ROLLBACK |
| Recording bleibt "streaming" | SOFORT ROLLBACK |
| Pipeline wird nicht getriggert | SOFORT ROLLBACK |
| Fehler in Egress Logs | SOFORT ROLLBACK |
| Fehler in Backend Logs | SOFORT ROLLBACK |

---

## ERFOLGSKRITERIEN

| Kriterium | Erfolg | Misserfolg |
|-----------|--------|------------|
| 2 Egress Pods | Beide Running | Pod Pending/CrashLoop |
| Health Check | HTTP 200 | Timeout/Error |
| Recording | status=completed | status=streaming |
| Pipeline | Transkription existiert | Keine Transkription |
| PV | PV existiert | Kein PV |
| Logs | Keine Fehler | Fehler vorhanden |

---

## TECHNISCHE DETAILS

### Änderungen am Deployment
```yaml
# VORHER:
spec:
  replicas: 1
  strategy:
    type: Recreate
  template:
    spec:
      hostNetwork: true
      dnsPolicy: ClusterFirstWithHostNet
      nodeSelector:
        kubernetes.io/hostname: instance-20260329-0846

# NACHHER:
spec:
  replicas: 2
  strategy:
    type: RollingUpdate
  template:
    spec:
      hostNetwork: false
      dnsPolicy: ClusterFirst
      # nodeSelector entfernt
```

### Kommunikationswege (bleiben gleich)
```yaml
# Egress → LiveKit Server (WebSocket)
LIVEKIT_WS_URL=ws://livekit-config-staging:7880

# Egress → Redis (TCP)
redis.address=redis-staging.meeting-automation-staging.svc.cluster.local:6379

# Egress → MinIO (HTTP)
s3.endpoint=http://minio-staging:9000
```

### NetworkPolicy (bleibt gleich)
```yaml
# Egress NetworkPolicy erlaubt:
- port: 6379 (TCP) → Redis
- port: 9000 (TCP) → MinIO
- port: 7880 (TCP) → LiveKit Server
- port: 53 (UDP/TCP) → DNS
```

---

## ZEITPLAN

| Phase | Dauer | Verantwortlich |
|-------|-------|----------------|
| Vorbereitung | 5min | Buffy |
| Deployment ändern | 2min | Buffy |
| Verifikation | 5min | Buffy + User |
| Rollback (falls nötig) | 2min | Buffy |
| **Gesamt** | **~15min** | |

---

## NÄCHSTE SCHRITTE

1. User genehmigt Plan
2. Phase 1: Vorbereitung
3. Phase 2: Deployment ändern
4. Phase 3: Verifikation
5. Bei Erfolg: Production Deployment planen
6. Bei Misserfolg: Rollback + Analyse
