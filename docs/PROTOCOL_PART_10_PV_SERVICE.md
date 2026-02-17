# PROTOKOLL: Teil 10 - PV Service (mit Mistral)
Datum: 16.02.2026
Status: ✅ Abgeschlossen

## 1. IMPLEMENTIERTE DATEIEN
- `backend/app/services/mistral_client.py`
- `backend/app/services/pv_service.py`
- `backend/app/schemas/pv.py`
- `backend/app/models/pv.py`
- `backend/app/api/v1/pv.py`
- `scripts/test_pv_generation.py` (für Mock-Tests)

## 2. IMPLEMENTIERTE FUNKTIONEN
### Mistral Client
- `__init__()` - Initialisiert den Client mit API-Schlüssel, Basis-URL und Modell.
- `call_mistral_api()` - Führt einen HTTP-Aufruf an die Mistral API durch, inklusive Retry-Logik und Fehlerbehandlung. Unterstützt einen Mock-Modus für Tests.
- `_generate_prompt()` - Eine interne Hilfsfunktion, die Prompt-Templates für verschiedene Aufgaben generiert.
- `generate_pv()` - Generiert ein Protokoll (PV) aus einer Transkription.
- `extract_decisions()` - Extrahiert Entscheidungen aus einer Transkription.
- `extract_action_points()` - Extrahiert Aktionspunkte aus einer Transkription.
- `generate_summary()` - Generiert eine Zusammenfassung aus einer Transkription.

### PV Service
- `create_pv_from_transcription()` - Erstellt ein PV aus einer Transkription unter Verwendung des Mistral-Clients.
- `get_pv_by_id()` - Ruft ein PV anhand seiner ID ab.
- `get_pvs_by_meeting()` - Ruft alle PVs für ein bestimmtes Meeting ab.
- `update_pv()` - Aktualisiert ein bestehendes PV.
- `delete_pv()` - Löscht ein PV.

### PV Schema
- `PVBase` - Basis-Pydantic-Schema für PVs.
- `PVCreate` - Pydantic-Schema für die Erstellung von PVs.
- `PVUpdate` - Pydantic-Schema für die Aktualisierung von PVs.
- `PVResponse` - Pydantic-Schema für die API-Antwort eines PVs.

### PV Model
- `PV` - SQLAlchemy-Modell für die `pvs`-Tabelle. Definiert Spalten wie `meeting_id`, `generated_by_id`, `title`, `date`, `participants`, `decisions`, `action_items`, `summary`, `raw_mistral_output`, `created_at`, `updated_at` und Beziehungen zu `Meeting` und `User`.

### PV API Endpoints
- `POST /api/v1/pv/generate/{transcription_id}` - Generiert ein PV aus einer Transkription.
- `GET /api/v1/pv/{pv_id}` - Ruft ein spezifisches PV ab.
- `GET /api/v1/pv/meeting/{meeting_id}` - Ruft alle PVs für ein Meeting ab.
- `PUT /api/v1/pv/{pv_id}` - Aktualisiert ein PV.
- `DELETE /api/v1/pv/{pv_id}` - Löscht ein PV.

## 3. LÖSUNGSANSATZ
- **Verwendete Technologien:** FastAPI, SQLAlchemy, Pydantic, `httpx`, `tenacity` (für Retry-Logik).
- **Wichtige Entscheidungen:**
    - Integration des Mistral-Clients zur Nutzung von LLM-Fähigkeiten für die Generierung von PVs, Extraktion von Entscheidungen, Aktionspunkten und Zusammenfassungen.
    - Implementierung eines Mock-Modus im Mistral-Client für Entwicklung und Tests ohne tatsächliche API-Aufrufe.
    - Verwendung von Prompt-Templates, um die Anfragen an das Mistral-Modell zu strukturieren und konsistente Ergebnisse zu erzielen.
    - Speicherung des generierten PVs und des rohen Mistral-Outputs in der Datenbank für Nachvollziehbarkeit und spätere Bearbeitung.
    - Berechtigungsprüfungen für den Zugriff auf PVs.
- **Begründungen:**
    - Die Nutzung eines LLM wie Mistral automatisiert die Erstellung von Meeting-Protokollen erheblich.
    - Der Mock-Modus beschleunigt die Entwicklung und ermöglicht Tests ohne Kosten oder Abhängigkeiten von der externen API.
    - Strukturierte Prompts sind entscheidend für die Qualität der LLM-Ausgabe.
    - Die Speicherung des Roh-Outputs ist nützlich für Debugging und zukünftige Verbesserungen der Prompt-Templates.

## 4. WICHTIGSTE CODE-BLÖCKE
```python
# backend/app/services/mistral_client.py
class MistralClient:
    # ... __init__ ...

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception_type(httpx.RequestError),
        reraise=True
    )
    async def call_mistral_api(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.7) -> Optional[str]:
        if settings.MOCK_MISTRAL_API:
            logger.info("Using mock Mistral API response.")
            return MOCK_PV_RESPONSE["choices"][0]["message"]["content"]
        # ... (HTTP-Aufruf an Mistral API) ...

    def _generate_prompt(self, template_name: str, **kwargs) -> str:
        templates = {
            "pv_generation": """
            Generate a "Protokoll-Vorlage" (PV) from the following meeting transcription.
            ...
            Transcription:
            {transcription}
            """,
            # ... other templates ...
        }
        template = templates.get(template_name)
        if not template:
            raise ValueError(f"Unknown prompt template: {template_name}")
        return template.format(**kwargs)

# backend/app/services/pv_service.py (Auszug)
class PVService:
    def __init__(self, mistral_client: MistralClient, security_service: SecurityService):
        self.mistral_client = mistral_client
        self.security_service = security_service

    async def create_pv_from_transcription(
        self, db: Session, transcription_id: int, current_user_id: int
    ) -> PV:
        # ... (Berechtigungsprüfungen und Transkriptionsabruf) ...
        pv_content = await self.mistral_client.generate_pv(transcription.transcribed_text)
        # ... (Parsing und Speicherung in DB) ...
        return db_pv

# backend/app/models/pv.py (Auszug)
class PV(Base):
    __tablename__ = "pvs"
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    generated_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=True)
    date = Column(Date, nullable=True)
    participants = Column(JSON, nullable=True) # List of strings
    decisions = Column(JSON, nullable=True) # List of strings
    action_items = Column(JSON, nullable=True) # List of dicts
    summary = Column(Text, nullable=True)
    raw_mistral_output = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

## 5. TESTS DURCHGEFÜHRT
```bash
python scripts/test_pv_generation.py
```
✅ [Testergebnisse] Der `test_pv_generation.py`-Skript wurde erfolgreich ausgeführt und hat die Generierung von PVs unter Verwendung des Mock-Mistral-Clients verifiziert. Die extrahierten Daten (Titel, Entscheidungen, Aktionspunkte, Zusammenfassung) wurden korrekt geparst und in der Datenbank gespeichert.

## 6. HERAUSFORDERUNGEN & LÖSUNGEN
- Problem: Parsing der strukturierten Textausgabe des Mistral-Modells in einzelne Felder für die Datenbank.
- Lösung: Implementierung einer einfachen Parsing-Logik im `PVService`, die bekannte Schlüsselwörter (z.B. "Meeting Title:", "Key Decisions:") verwendet, um die relevanten Informationen aus dem generierten Text zu extrahieren. Für komplexere Szenarien könnte ein robusterer Parser oder ein strukturiertes JSON-Output vom LLM in Betracht gezogen werden.
- Problem: Umgang mit der Abhängigkeit von einer externen LLM-API während der Entwicklung und für automatisierte Tests.
- Lösung: Implementierung eines `MOCK_MISTRAL_API`-Flags in den Einstellungen und einer entsprechenden Logik im `MistralClient`, die bei Aktivierung eine vordefinierte Antwort zurückgibt. Dies ermöglicht eine schnelle Entwicklung und zuverlässige Tests ohne externe API-Aufrufe.

## 7. ABHÄNGIGKEITEN
- `httpx`
- `tenacity`