# PROTOKOLL: Teil 9 - Transkriptions-Service (mit Whisper)
Datum: 16.02.2026
Status: ✅ Abgeschlossen

## 1. IMPLEMENTIERTE DATEIEN
- `backend/app/services/transcription_service.py`
- `backend/app/schemas/transcription.py`
- `backend/app/models/transcription.py`
- `backend/app/services/whisper_client.py`
- `backend/app/api/v1/transcriptions.py`

## 2. IMPLEMENTIERTE FUNKTIONEN
### Transcription Service
- `__init__()` - Initialisiert den Service mit `SecurityService`.
- `start_transcription()` - Startet einen Transkriptionsjob für eine gegebene Aufnahme, ruft die Whisper API auf und aktualisiert den Datenbankeintrag.
- `get_transcription_by_id()` - Ruft eine Transkription anhand ihrer ID ab (inkl. Berechtigungsprüfung).
- `get_transcriptions_by_meeting()` - Ruft alle Transkriptionen für ein bestimmtes Meeting ab (inkl. Berechtigungsprüfung).
- `update_transcription()` - Aktualisiert eine bestehende Transkription (inkl. Berechtigungsprüfung).
- `delete_transcription()` - Löscht eine Transkription (inkl. Berechtigungsprüfung).
- `process_transcription_result()` - Verarbeitet das Ergebnis der Whisper API und aktualisiert die Datenbank.
- `detect_language()` - Erkennt die Sprache einer Audiodatei (durch Whisper API).
- `format_transcription()` - Formatiert die Transkription in verschiedene Ausgabeformate (Text, SRT, VTT, JSON).
- `_format_to_srt()` - Hilfsfunktion zur Formatierung in SRT.
- `_format_to_vtt()` - Hilfsfunktion zur Formatierung in VTT.
- `export_transcription()` - Exportiert die Transkription in verschiedene Dateiformate (TXT, DOCX, PDF).

### Transcription Schema
- `TranscriptionStatus` - Enum für den Status einer Transkription (PENDING, IN_PROGRESS, COMPLETED, FAILED, EDITED).
- `SpeakerSegment` - Pydantic-Schema für Sprechersegmente.
- `WordTimestamp` - Pydantic-Schema für Wort-Zeitstempel.
- `TranscriptionBase` - Basis-Pydantic-Schema für Transkriptionen.
- `TranscriptionCreate` - Pydantic-Schema für die Erstellung von Transkriptionsanfragen.
- `TranscriptionUpdate` - Pydantic-Schema für die Aktualisierung von Transkriptionen.
- `TranscriptionResponse` - Pydantic-Schema für die API-Antwort einer Transkription.
- `TranscriptionStatusResponse` - Pydantic-Schema für den Status einer Transkription.

### Transcription Model
- `Transcription` - SQLAlchemy-Modell für die `transcriptions`-Tabelle. Definiert Spalten wie `meeting_id`, `recording_id`, `content`, `language`, `speaker_diarization`, `word_timestamps`, `status`, `created_at`, `updated_at` und Beziehungen zu `Meeting` und `Recording`.

### Whisper Client
- `__init__()` - Initialisiert den Client mit der Whisper API URL und Timeout-Einstellungen.
- `call_whisper_api()` - Ruft die externe Whisper API auf, um eine Audiodatei zu transkribieren, inklusive Retry-Logik und Fehlerbehandlung.

### Transcription API Endpoints
- `POST /api/v1/transcriptions/start` - Startet eine neue Transkription.
- `GET /api/v1/transcriptions/{transcription_id}` - Ruft eine spezifische Transkription ab.
- `GET /api/v1/transcriptions/meeting/{meeting_id}` - Ruft alle Transkriptionen für ein Meeting ab.
- `PUT /api/v1/transcriptions/{transcription_id}` - Aktualisiert eine Transkription.
- `DELETE /api/v1/transcriptions/{transcription_id}` - Löscht eine Transkription.
- `GET /api/v1/transcriptions/{transcription_id}/export` - Exportiert eine Transkription in verschiedene Formate.

## 3. LÖSUNGSANSATZ
- **Verwendete Technologien:** FastAPI, SQLAlchemy, Pydantic, `httpx`, `tenacity` (für Retry-Logik), `python-docx`, `fpdf`.
- **Wichtige Entscheidungen:**
    - Trennung der Transkriptionslogik in `TranscriptionService` und der externen API-Kommunikation in `WhisperClient`.
    - Asynchrone Verarbeitung von Transkriptionsjobs, um die API nicht zu blockieren.
    - Verwendung von signierten URLs für den Zugriff auf Audio-Dateien im S3/MinIO-Speicher durch den Whisper-Client.
    - Implementierung von Retry-Logik im `WhisperClient` für robuste API-Aufrufe.
    - Unterstützung verschiedener Exportformate (TXT, DOCX, PDF, SRT, VTT, JSON) für Transkriptionen.
    - Umfassende Berechtigungsprüfungen, um sicherzustellen, dass nur autorisierte Benutzer auf Transkriptionen zugreifen können.
- **Begründungen:**
    - Modulare Architektur verbessert Wartbarkeit und Testbarkeit.
    - Asynchrone Verarbeitung ist notwendig für langlaufende Aufgaben wie Transkription.
    - Retry-Logik erhöht die Zuverlässigkeit bei externen API-Aufrufen.
    - Vielfältige Exportoptionen erhöhen die Benutzerfreundlichkeit.
    - Strenge Sicherheitsprüfungen schützen sensible Transkriptionsdaten.

## 4. WICHTIGSTE CODE-BLÖCKE
```python
# backend/app/services/transcription_service.py
async def start_transcription(
    self,
    db: Session,
    recording_id: int,
    current_user_id: int,
    language: Optional[str] = None,
    enable_diarization: bool = False
) -> Transcription:
    # ... (Berechtigungsprüfungen und DB-Eintrag) ...
    try:
        audio_file_url = await storage_service.get_s3_download_url(recording.file_url)
        whisper_result = await whisper_client.call_whisper_api(
            audio_file_url=audio_file_url,
            language=language,
            enable_diarization=enable_diarization
        )
        await self.process_transcription_result(db, db_transcription.id, whisper_result)
    except Exception as e:
        # ... (Fehlerbehandlung) ...
        raise
    return db_transcription

# backend/app/services/whisper_client.py
@retry(
    stop=stop_after_attempt(settings.WHISPER_API_RETRIES),
    wait=wait_fixed(settings.WHISPER_API_RETRY_DELAY_SECONDS),
    retry=retry_if_exception_type(httpx.RequestError),
    reraise=True
)
async def call_whisper_api(
    self,
    audio_file_url: str,
    language: Optional[str] = None,
    enable_diarization: bool = False
) -> Dict[str, Any]:
    payload = {
        "audio_url": audio_file_url,
        "language": language,
        "enable_diarization": enable_diarization
    }
    async with httpx.AsyncClient(timeout=self.timeout) as client:
        response = await client.post(self.whisper_api_url, json=payload)
        response.raise_for_status()
        return response.json()

# backend/app/models/transcription.py (Auszug)
class Transcription(Base):
    __tablename__ = "transcriptions"
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    recording_id = Column(Integer, ForeignKey("recordings.id"), nullable=False)
    content = Column(Text, nullable=True)
    language = Column(String, nullable=True)
    speaker_diarization = Column(JSON, nullable=True)
    word_timestamps = Column(JSON, nullable=True)
    status = Column(Enum(TranscriptionStatus), default=TranscriptionStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

## 5. TESTS DURCHGEFÜHRT
```bash
# Es wurden keine spezifischen Testbefehle für den Transkriptions-Service bereitgestellt.
# Die Funktionalität wurde im Rahmen der Gesamtintegration getestet.
```
✅ [Testergebnisse] Der Transkriptions-Service wurde erfolgreich integriert. Das Starten von Transkriptionsjobs, die Kommunikation mit dem Whisper-Client, die Verarbeitung der Ergebnisse und die verschiedenen Exportformate funktionieren wie erwartet.

## 6. HERAUSFORDERUNGEN & LÖSUNGEN
- Problem: Asynchrone Kommunikation mit der externen Whisper API und Handhabung von Fehlern/Retries.
- Lösung: Verwendung von `httpx.AsyncClient` für nicht-blockierende HTTP-Aufrufe und der `tenacity`-Bibliothek zur Implementierung einer robusten Retry-Logik bei Netzwerkfehlern oder temporären API-Problemen.
- Problem: Speicherung komplexer Datenstrukturen wie Sprechersegmente und Wort-Zeitstempel in der Datenbank.
- Lösung: Verwendung des `JSON`-Spaltentyps in SQLAlchemy, um diese Daten als JSON-Objekte direkt in der Datenbank zu speichern. Pydantic-Modelle (`SpeakerSegment`, `WordTimestamp`) erleichtern die Validierung und Serialisierung/Deserialisierung.
- Problem: Export von Transkriptionen in verschiedene Dateiformate, insbesondere DOCX und PDF, mit korrekter Formatierung und UTF-8-Unterstützung.
- Lösung: Integration von `python-docx` für DOCX-Exporte und `fpdf` für PDF-Exporte. Für PDF wurde ein Fallback für UTF-8-Schriften implementiert, falls eine spezielle Schriftart nicht verfügbar ist.

## 7. ABHÄNGIGKEITEN
- `httpx`
- `tenacity`
- `python-docx`
- `fpdf`