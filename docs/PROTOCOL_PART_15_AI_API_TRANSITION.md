PROTOKOLL: PART_15_AI_API_TRANSITION

Datum: 22.02.2026
Status: Abgeschlossen
🎯 ZIEL

Transition von lokalen AI-Services (Whisper/Mistral Docker-Container) zu externen APIs (OpenAI/Mistral), um Systemressourcen zu sparen und die Qualität/Stabilität zu erhöhen.

🔧 TECHNOLOGIEN

- Backend: FastAPI, OpenAI API (Whisper-1), Mistral API (mistral-large-latest)
- Infrastruktur: Docker Compose (entfernte Whisper/Mistral Services)
- Konfiguration: Pydantic Settings mit Environment-Variablen

📝 DURCHGEFÜHRTE ARBEITSSCHRITTE

1. **Backend-Konfiguration erweitert**: In `backend/app/core/config.py` wurden `OPENAI_API_KEY` und `MISTRAL_API_KEY` hinzugefügt. Die alten URL-basierten Settings wurden entfernt.
2. **TranscriptionService umgestellt**: In `backend/app/services/transcription_service.py` erfolgt die Transkription nun direkt über die OpenAI Audio API (`whisper-1`).
3. **PVService umgestellt**: In `backend/app/services/pv_service.py` wird nun die Mistral AI API genutzt. Inklusive System-Prompt für strukturierte JSON-Ausgabe.
4. **Docker-Infrastruktur bereinigt**: In `docker-compose.yml` wurden die Services `whisper` und `mistral` sowie deren Volumes entfernt. API-Keys werden an Backend und n8n durchgereicht.
5. **Dokumentation & Env-Beispiele**: `.env.example` wurde aktualisiert.

⚠️ HERAUSFORDERUNGEN & LÖSUNGEN

- **Problem**: Lokale Ressourcenlast war zu hoch für eine Standard-VM.
- **Lösung**: Auslagerung an spezialisierte SaaS-APIs. Dies erfordert zwar API-Keys, bietet aber eine deutlich höhere Zuverlässigkeit und Geschwindigkeit.
- **Sicherheit**: API-Keys werden über Docker Secrets / Env-Variablen gehandhabt und nicht im Code gespeichert.

🔗 ZUSAMMENHANG ZUM PROJEKT

Dieser Schritt markiert den Übergang von einem experimentellen Setup mit lokalen Modellen zu einer produktionsreifen Cloud-Hybrid-Architektur.

📊 ERGEBNIS

✅ Systemressourcen-Verbrauch signifikant gesenkt.
✅ Höhere Transkriptionsgenauigkeit durch OpenAI Whisper API.
✅ Bessere PV-Strukturierung durch Mistral-Large.
✅ Vereinfachtes Deployment durch Wegfall komplexer GPU/ML-Container-Setups.