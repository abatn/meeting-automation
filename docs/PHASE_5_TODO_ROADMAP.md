# TODO ROADMAP: PHASE 5 - PRODUCTION OPERATIONS & OPTIMIZATION

**Status:** In Arbeit 🔄
**Letztes Update:** 23.03.2026

## 🎯 ÜBERSICHT
Dieses Dokument dient als zentrale Checkliste für die noch ausstehenden Aufgaben der Phase 5. Nach erfolgreichem Abschluss dieser Punkte ist das System vollständig bereit für den kommerziellen Live-Betrieb (Go-Live) unter Enterprise-Bedingungen.

---

## 🚀 1. INFRASTRUKTUR & SKALIERBARKEIT (PRODUKTIONS-REIFE)

- [ ] **Kubernetes Auto-Scaling (HPA)**
  - **Aufgabe:** Konfiguration des *Horizontal Pod Autoscaler (HPA)*.
  - **Ziel:** Dynamisches Hoch- und Herunterfahren von Celery-Workern (AI-Worker) basierend auf der CPU-Auslastung und Warteschlangengröße.
  - **Nutzen:** Kostenoptimierung und Vermeidung von Transkriptions-Staus.

- [ ] **Mobile App / PWA (Progressive Web App)**
  - **Aufgabe:** Entwicklung einer mobilen Lösung (PWA).
  - **Ziel:** Bereitstellung einer für Smartphones optimierten Oberfläche für Meeting-Aufnahmen.
  - **Nutzen:** Höhere Flexibilität für Nutzer (Aufnahme via Smartphone ohne Laptop).

- [ ] **Disaster Recovery & Offsite-Backups**
  - **Aufgabe:** Validierung und Automatisierung täglicher Offsite-Backups.
  - **Ziel:** Sicherung der PostgreSQL-Datenbank und des MinIO-Storages an einem geografisch getrennten Standort.
  - **Nutzen:** Erfüllung der ISO 27001 Vorgaben zur Ausfallsicherheit und Schutz vor Datenverlust bei Rechenzentrum-Ausfall.

- [x] **Online Document Editing (OnlyOffice)**
  - **Aufgabe:** Integration des *OnlyOffice Document Servers* und Font-Optimierung (Noto-Fonts).
  - **Status:** Abgeschlossen ✅ (Inkl. RTL-Rendering Fixes und Font-Cache Rebuild).
  - **Nutzen:** Hohe Benutzerfreundlichkeit bei 100%iger Einhaltung der Datensouveränität (ISO 27001).

---

## 🧠 2. KI-OPTIMIERUNG (LOKALER FOKUS)

- [ ] **KI-Finetuning (Lokaler Dialekt)**
  - **Aufgabe:** Optimierung der Mistral-Prompts basierend auf gesammeltem Feedback.
  - **Ziel:** Verbesserung des Verständnisses von tunesischem Arabisch (Derja) und Erhöhung der Präzision bei Zusammenfassungen.
  - **Nutzen:** Höhere Qualität der Protokolle für den Kernmarkt im Maghreb.

---

## 🛡️ 3. SECURITY & CI/CD (ISO 27001 / QUALITY)

- [ ] **Vulnerability Scanning in CI/CD**
  - **Aufgabe:** Integration von Sicherheitsscans (Trivy, OWASP ZAP) in die GitHub Actions.
  - **Ziel:** Automatisches Scannen von Code-Commits und Docker-Images auf Schwachstellen (CVEs).
  - **Nutzen:** Kontinuierliche Sicherheit und Schutz vor Supply-Chain-Angriffen.

- [ ] **Data Residency Definition**
  - **Aufgabe:** Finale rechtliche und technische Festlegung der Speicherorte.
  - **Ziel:** Umsetzung spezifischer Anforderungen an den physischen Speicherort (z.B. Tunis vs. Europa).
  - **Nutzen:** Rechtssicherheit und Compliance mit lokalen Datenschutzgesetzen.

---

## ✅ ERLEDIGTE MEILENSTEINE (PHASE 5)
- [x] Erweitertes System-Monitoring (Mission Control Dashboard)
- [x] Behebung von Frontend-Build Speicherproblemen (Bus Error)
- [x] Dynamische AI Recommendation Übersetzung (Dashboard Sync)
- [x] Intelligente Teilnehmer-Zuweisung (Context Injection)
- [x] Natives Arabisches PDF-Rendering (HarfBuzz/Pango)
- [x] Dynamischer Meeting Planner (Teilnehmer & Zeitwahl)


## 🧠 NEU: ENTERPRISE AI SEARCH & KNOWLEDGE BASE (Ollama RAG)
**Status:** Geplant 📅
**Ziel:** Transformation des starren Meeting-Archivs in ein interaktives, semantisch durchsuchbares "Firmen-Gedächtnis", das zu 100% lokal und ISO 27001-konform läuft.

### 1. Backend-Architektur (Local RAG Pipeline)
- [ ] **PostgreSQL `pgvector` Setup:** Erweiterung der Datenbank für die Speicherung von hochdimensionalen Vektoren.
- [ ] **Embedding-Service:** Integration eines lokalen Ollama-Embedding-Modells (z. B. `nomic-embed-text`).
- [ ] **Auto-Vektorisierung:** Workflow implementieren: Bei Klick auf `Approve & Sign` (`/pv/{id}/validate`) wird der PV-Text automatisch vektorisiert und in der DB gespeichert.
- [ ] **Semantic Search API:** Neuer Endpunkt `/api/v1/search/semantic`, der Suchanfragen (User-Prompts) vektorisiert und die Top-3-relevantesten PV-Ausschnitte (Context) via Kosinus-Ähnlichkeit zurückgibt.
- [ ] **LLM Answer Synthesis:** Der extrahierte Kontext wird an das lokale LLM (z. B. Qwen-1.5B) übergeben, um eine natürliche Antwort zu generieren (z. B. "Im Meeting vom 12.03. wurde beschlossen, dass...").

### 2. Frontend-Architektur ("Command Palette" & Library)
- [ ] **Global Command Palette (Navbar):** 
  - Ein prominenter "Ask AI" Button (`✨ Ask your Meetings`) im Header.
  - Tastenkürzel-Unterstützung (`Strg + K` / `Cmd + K`), um ein Mac-Spotlight/Raycast-ähnliches Overlay zu öffnen.
  - Live-Streaming der LLM-Antwort direkt in das UI mit Quellen-Verlinkung auf die originalen PVs.
- [ ] **PV Archive / Knowledge Base (Sidebar):** 
  - Neuer Menüpunkt in der Sidebar für die klassische Recherche.
  - Hochperformante Tabelle (Virtualisierung für tausende Einträge) mit Filtern für Datum, Raum und Teilnehmer.
  - **Smart Filters:** Automatische Extraktion von Themenwolken/Tags (z. B. `#Budget`, `#HR`) durch Mistral, nach denen gefiltert werden kann.

### 3. Infrastruktur & Compliance (ISO 27001)
- [ ] **Ressourcen-Monitoring:** Überwachung des RAM/GPU-Verbrauchs des Embedding-Modells im Mission Control Dashboard.
- [ ] **Multi-Tenant-Isolation (RLS):** Striktes Row-Level-Security-Enforcement in `pgvector`: Ein Tenant darf niemals Embeddings oder Suchergebnisse aus den PVs eines anderen Tenants erhalten.
