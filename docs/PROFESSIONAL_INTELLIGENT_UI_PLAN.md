# Professionelle Intelligente Meeting UI

**Erstellt:** 2026-06-05 | **Status:** In Entwicklung

---

## Ziel

Transformatioın der MeetingRoom.tsx von einer statischen 2-Column-UI in eine professionelle, intelligente Meeting-Experience mit Echtzeit-Transkription, AI-Assistance und ISO-27001-konformem E-Signature-Workflow.

## Analyse des aktuellen Zustands

**Probleme:**
1. AI Recommendations: Keine Echtzeit-Daten, placeholder text
2. Transcription: "No transcription available yet" — funktional leer
3. PV Draft (Mistral): Leer, keine Auto-Generierung
4. E-Signature: Leer, kein Workflow
5. Layout: Ungleichgewicht — links viele kleine Widgets, rechts statische Tabs
6. Keine visuelle Feedback für Live-Audio (Waveforms, Speaking-Indicators)
7. Keine Meeting-Timer oder Speaking-Time-Statistiken

## Neue Vision: "Executive Meeting Assistant"

### Phase 1: Layout-Refaktorisierung (Heute)
- 3-Column oder verbessertes 2-Column Layout
- Professional Cards mit Material Design 3
- Consistent spacing und typography
- Mobile-Responsive Design

### Phase 2: Live-Transkription (Phase 2)
- WebSocket-Verbindung zu ASR (Gladia)
- Speaker-Diarization mit Visualisierung
- Echtzeit-Transkriptions-Stream mit Markdown-Support
- Suchfunktion in Transkriptionen

### Phase 3: Smart AI Sidebar (Phase 2)
- Echtzeit-Suggestions basieren auf Gesprächsthemen
- Action-Item-Auto-Detection
- Meeting-Ziel-Tracking
- ISO-27001 Audit Trail für AI-Entscheidungen

### Phase 4: E-Signature Workflow (Phase 3)
- PDF-PV-Draft anzeigen (OnlyOffice)
- Staußen+Review+Sign Workflow
- Multi-Signatur Support
- Audit-Log für jede Signatur-Aktion

## UI-Komponenten-Plan

```
┌─ MEETING: Live ───────────────────────────────────────────┐
│ Header: Timer + Status + Teilnehmerzahl + Recording-Status │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─ Audio-Panel ───┐ ┌─ Smart Transcript ──┐ ┌─ AI-Panel ─┐│
│  │                 │ │                     │ │             ││
│  │ 🔊 LiveKit      │ │ Speaker A: "Hallo   │ │ 🧠 AI-      ││
│  │    Audio Widget │ │ ..."               │ │    Insights ││
│  │                 │ │ Speaker B: "Ja,    │ │             ││
│  │ 👤 Teilnehmer   │ │ ich bin einverstanden│ │ • Topic:    ││
│  │    (Visual)     │ │ ..."               │ │    Budget   ││
│  │                 │ │                     │ │ • Action:   ││
│  │ ⏱️ Timer        │ │ 💡 Live-Suche       │ │    Folge    ││
│  │    02:14        │ │                     │ │    Meeting  ││
│  │                 │ │ 📊 Speaking-Time   │ │ • Auto-Tag: ││
│  │ 🔴 Record        │ │    User 1: 62%     │ │    #budget  ││
│  │    (Start/Stop) │ │    User 2: 24%     │ │             ││
│  │                 │ │                     │ │ 🤖 Vorschläge││
│  └──────────────────┘ └─────────────────────┘ └─────────────│
│                                                             │
│  ┌─ PV Draft Preview ───────────────────────────────────────┐│
│  │ 🤖 Mistral-Generated Protocol Draft (Auto-Refresh)      ││
│  │ • Auto-kategorisierte Abschnitte                       ││
│  │ • 1-Click-Review: akzeptieren/ablehnen/ändern          ││
│  │ • ISO 27001 Audit Trail für jeden Review-Schritt       ││
│  └──────────────────────────────────────────────────────────│
│                                                             │
│  ┌─ Electronic Signature (ISO 27001) ──────────────────────┐│
│  │ 🔐 Workflow: Review → Internal Sign → External Sign      ││
│  │ • Digitale Signatur mit PKI-Zertifikat                   ││
│  │ • Zeitstempel und Non-Repudiation                        ││
│  │ • Audit-Log exportierbar (PDF)                           ││
│  │ • Multi-Faktor-Authentifikation                          ││
│  └──────────────────────────────────────────────────────────│
└─────────────────────────────────────────────────────────────┘
```

## E2E-Test-Plan

| # | Test | Beschreibung |
|---|------|-------------|
| 1 | `test_meeting_room_ui_loaded` | MeetingRoom zeigt Audio-Panel, Transkription, AI-Panel |
| 2 | `test_live_transcription_visible` | WebSocket-Stream zeigt Echtzeit-Transkription |
| 3 | `test_recording_timer_counts_up` | Recording-Timer zeigt korrekte Sekunden an |
| 4 | `test_ai_insights_update` | AI-Sidebar mit Live-Insights |
| 5 | `test_pv_draft_preview_visible` | PV-Draft wird angezeigt |
| 6 | `test_e_signature_workflow` | ISO-27001 E-Signature Workflow Schritte |
| 7 | `test_meeting_archive_download` | Archivierter Download (Audio + Transcript + PV) |

## Ergebnis der E2E-Tests

### LiveKit-Integration (7/7 ✅)
- Alle LiveKit Tests bestanden
- Egress Recording funktioniert produktionsreif

### MeetingCreation (7/8, 1 Fehler)
- Grundlegende Meeting-Erstellung funktioniert
- Ein Test fehlerhaft: `test_get_meeting_by_id` (unrelated zu LiveKit)

## Nächste Schritte

1. ✅ MeetingRoom.tsx Layout Refactoring
2. 🔄 WebSocket-Verbindung zu ASR (Gladia) für Live-Transkription
3. 🔄 AI-Suggestions basieren auf Transkriptions-Stream (Mistral/ChatGPT)
4. 🔄 E-Signature Workflow mit OnlyOffice-Integration

## Acceptance Criteria

- [ ] MeetingRoom zeigt Live-Audio-Visualisierung
- [ ] Transkription ist in Echtzeit sichtbar
- [ ] AI-Sidebar zeigt Live-Insights (Topic, Action)
- [ ] PV-Draft wird automatisch generiert und angezeigt
- [ ] E-Signature Workflow ist vollständig implementiert
- [ ] Alle E2E-Tests bestanden
- [ ] ISO 27001 Audit Trail funktioniert für alle Aktionen
