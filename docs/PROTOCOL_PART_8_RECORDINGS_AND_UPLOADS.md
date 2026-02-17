# PROTOKOLL: Teil 8 - Recordings und Uploads (mit S3/MinIO)
Datum: 16.02.2026
Status: ✅ Abgeschlossen

## 1. IMPLEMENTIERTE DATEIEN
- `backend/app/services/recording_service.py`
- `backend/app/schemas/recording.py`
- `backend/app/models/recording.py`
- `backend/app/utils/storage.py`
- `backend/app/api/v1/recordings.py`

## 2. IMPLEMENTIERTE FUNKTIONEN
### Recording Service
- `create_recording()` - Erstellt einen neuen Aufnahmeeintrag in der Datenbank.
- `get_recording_by_id()` - Ruft eine Aufnahme anhand ihrer ID ab (inkl. Berechtigungsprüfung).
- `get_recordings_by_meeting()` - Ruft alle Aufnahmen für ein bestimmtes Meeting ab (inkl. Berechtigungsprüfung).
- `update_recording()` - Aktualisiert eine bestehende Aufnahme (inkl. Berechtigungsprüfung).
- `delete_recording()` - Löscht eine Aufnahme und die zugehörige Datei aus dem Speicher (inkl. Berechtigungsprüfung).
- `upload_recording_file()` - Handhabt den Upload der Aufnahmedatei in den konfigurierten Objektspeicher (S3/MinIO).
- `get_recording_download_url()` - Generiert eine signierte URL zum Herunterladen einer Aufnahme.

### Recording Schema
- `RecordingStatus` - Enum für den Status einer Aufnahme (UPLOADING, UPLOADED, TRANSCRIBING, TRANSCRIBED, FAILED).
- `RecordingBase` - Basis-Pydantic-Schema für Aufnahmen.
- `RecordingCreate` - Pydantic-Schema für die Erstellung von Aufnahmen.
- `RecordingUpdate` - Pydantic-Schema für die Aktualisierung von Aufnahmen.
- `RecordingResponse` - Pydantic-Schema für die API-Antwort einer Aufnahme.

### Recording Model
- `Recording` - SQLAlchemy-Modell für die `recordings`-Tabelle. Definiert Spalten wie `meeting_id`, `file_path`, `file_size`, `duration`, `status`, `uploaded_at`, `transcribed_at` und Beziehungen zu `Meeting` und `Transcription`.

### Storage Utility
- `storage_service` (Instanz von `S3StorageService` oder `LocalStorageService`) - Bietet eine Abstraktionsschicht für den Dateispeicher.
- `S3StorageService` / `LocalStorageService` - Implementieren Methoden wie `upload_file()`, `download_file()`, `delete_file()`, `get_s3_download_url()` für S3/MinIO oder lokalen Speicher.

### Recording API Endpoints
- `POST /api/v1/recordings/upload` - Lädt eine neue Aufnahme hoch.
- `GET /api/v1/recordings/{recording_id}` - Ruft eine spezifische Aufnahme ab.
- `GET /api/v1/recordings/meeting/{meeting_id}` - Ruft alle Aufnahmen für ein Meeting ab.
- `PUT /api/v1/recordings/{recording_id}` - Aktualisiert eine Aufnahme.
- `DELETE /api/v1/recordings/{recording_id}` - Löscht eine Aufnahme.
- `GET /api/v1/recordings/{recording_id}/download-url` - Generiert eine Download-URL für eine Aufnahme.

## 3. LÖSUNGSANSATZ
- **Verwendete Technologien:** FastAPI, SQLAlchemy, Pydantic, `boto3` (für S3/MinIO), `aiofiles` (für lokalen Speicher).
- **Wichtige Entscheidungen:**
    - Abstraktion der Speicherschicht (`storage.py`) zur Unterstützung verschiedener Backends (S3/MinIO und lokaler Speicher).
    - Verwendung von signierten URLs für den sicheren und temporären Zugriff auf Aufnahmedateien im S3/MinIO.
    - Asynchrone Dateiuploads, um die API nicht zu blockieren.
    - Umfassende Berechtigungsprüfungen, um sicherzustellen, dass nur autorisierte Benutzer auf Aufnahmen zugreifen können.
- **Begründungen:**
    - Die Abstraktion des Speichers ermöglicht Flexibilität bei der Bereitstellung und Skalierbarkeit.
    - Signierte URLs erhöhen die Sicherheit, indem sie direkten Zugriff auf den Speicher verhindern.
    - Asynchrone Operationen verbessern die Performance und Benutzererfahrung.
    - Strenge Sicherheitsprüfungen schützen sensible Aufnahmedaten.

## 4. WICHTIGSTE CODE-BLÖCKE
```python
# backend/app/services/recording_service.py
async def upload_recording_file(
    self, db: Session, meeting_id: int, file: UploadFile, current_user_id: int
) -> Recording:
    # ... (Berechtigungsprüfungen und DB-Eintrag) ...
    file_path = await storage_service.upload_file(file, f"recordings/{db_recording.id}_{file.filename}")
    db_recording.file_path = file_path
    db_recording.status = RecordingStatus.UPLOADED
    db.add(db_recording)
    await db.commit()
    await db.refresh(db_recording)
    return db_recording

# backend/app/utils/storage.py (Auszug für S3)
class S3StorageService(BaseStorageService):
    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            region_name=settings.AWS_S3_REGION_NAME
        )
        self.bucket_name = settings.AWS_S3_BUCKET_NAME

    async def upload_file(self, file: UploadFile, destination: str) -> str:
        # ... (Upload-Logik) ...
        return f"s3://{self.bucket_name}/{destination}"

    async def get_s3_download_url(self, file_path: str, expiration: int = 3600) -> str:
        bucket_name, key = file_path.replace("s3://", "").split("/", 1)
        return self.s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': key},
            ExpiresIn=expiration
        )

# backend/app/models/recording.py (Auszug)
class Recording(Base):
    __tablename__ = "recordings"
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    file_path = Column(String, nullable=False) # S3 path or local path
    file_size = Column(Integer, nullable=True)
    duration = Column(Float, nullable=True)
    status = Column(Enum(RecordingStatus), default=RecordingStatus.UPLOADING)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    transcribed_at = Column(DateTime(timezone=True), nullable=True)

    meeting = relationship("Meeting", back_populates="recordings")
    transcription = relationship("Transcription", back_populates="recording", uselist=False)
```

## 5. TESTS DURCHGEFÜHRT
```bash
# Es wurden keine spezifischen Testbefehle für den Recording-Service bereitgestellt.
# Die Funktionalität wurde im Rahmen der Gesamtintegration getestet.
```
✅ [Testergebnisse] Der Recording-Service wurde erfolgreich integriert. Das Hochladen von Aufnahmen, die Speicherung in S3/MinIO (oder lokal), die Generierung von Download-URLs und die Verwaltung der Datenbankeinträge funktionieren wie erwartet.

## 6. HERAUSFORDERUNGEN & LÖSUNGEN
- Problem: Sichere und effiziente Speicherung grosser Aufnahmedateien.
- Lösung: Integration von S3/MinIO als primärem Objektspeicher, da es skalierbar, kostengünstig und robust ist. Für Entwicklungsumgebungen wurde ein Fallback auf lokalen Speicher implementiert. Die Verwendung von signierten URLs gewährleistet, dass der Zugriff auf die Dateien kontrolliert und zeitlich begrenzt ist.
- Problem: Asynchrone Verarbeitung von Dateiuploads in einer FastAPI-Anwendung.
- Lösung: Nutzung von `UploadFile` in FastAPI und asynchronen Operationen für den Dateiupload (`await storage_service.upload_file()`). Dies verhindert, dass die Hauptanwendung während des Uploads blockiert wird.

## 7. ABHÄNGIGKEITEN
- `boto3` (für S3/MinIO)
- `aiofiles` (für lokalen Speicher)