# Agent Prompt — Phase 55: TLS Certificate Verification + X-Forwarded-Proto

## Auftrag

Lies `.loop.md` (Phase 54 ganz oben). Der vorherige Agent hat cert-manager v1.20.2 + nginx-ingress installiert (Phase 53) und die Dokumentation bereinigt (Phase 54). Du bist verantwortlich für Phase 55: TLS Certificate verifizieren und X-Forwarded-Proto Header für Backend konfigurieren.

## Schritte

1. ~~**Prüfe OCI Security List**: Sind Ports 30080/30443 geöffnet?~~ → **NICHT noetig — nginx-ingress auf hostPort umgestellt**
2. **Prüfe Certificate**: `kubectl get certificate -n meeting-automation-staging` — ist `staging-tls` noch pending oder bereits valid?
3. ~~**Wenn Certificate ready**: Teste `curl -vI https://staging.meeting-automation.com`~~ → **BLOCKIERT: OCI Security List Ports 80/443**
4. **Wenn Certificate pending**: Prüfe ACME Challenge Pod: `kubectl get pods -n cert-manager` + `kubectl describe challenge -n meeting-automation-staging`
5. ~~**X-Forwarded-Proto Header**: Konfiguriere nginx-ingress Annotation `nginx.ingress.kubernetes.io/configuration-snippet: more_set_headers "X-Forwarded-Proto: https";` im Ingress~~ → **NOCH OFFEN nach OCI Ports**
6. ~~**Backend Restart**: Nach Header-Änderung Backend-Pods neustarten~~ → **NOCH OFFEN nach OCI Ports**
7. **LiveKit WSS**: Prüfe ob `LIVEKIT_PUBLIC_URL` auf `wss://` umgestellt werden muss (für HTTPS)
8. **Update `.loop.md`**: Phase 55 Eintrag mit Verifikation

## Wichtig

- Kubectl Context: `~/.kube/config-staging`, Context: `staging-cluster`
- Domain: `staging.meeting-automation.com`
- cert-manager: v1.20.2 (Helm)
- nginx-ingress: NodePort 30080/30443
- Alle Pods müssen Running bleiben
