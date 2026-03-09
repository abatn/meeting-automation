# Projekt-Architektur Diagramm

Dieses Diagramm zeigt den aktuellen, stabilisierten Datenfluss des Meeting Automation Systems.

```mermaid
graph TD
    %% Definition der Stile
    classDef frontend fill:#61dafb,stroke:#333,stroke-width:2px,color:#000
    classDef backend fill:#4584b6,stroke:#333,stroke-width:2px,color:#fff
    classDef storage fill:#ff9900,stroke:#333,stroke-width:2px,color:#000
    classDef queue fill:#ff6600,stroke:#333,stroke-width:2px,color:#fff
    classDef external fill:#2ea44f,stroke:#333,stroke-width:2px,color:#fff
    classDef n8n fill:#ea4b5e,stroke:#333,stroke-width:2px,color:#fff

    %% Komponenten
    User((Nutzer / Browser))
    
    subgraph "Frontend (React)"
        UI[Frontend App]:::frontend
    end

    subgraph "Core (FastAPI)"
        API[Backend API]:::backend
    end

    subgraph "Datenbanken"
        DB[(PostgreSQL)]:::storage
        S3[(MinIO Object Storage)]:::storage
        Cache[(Redis)]:::storage
    end

    subgraph "Asynchrone Pipeline"
        Broker[[RabbitMQ Broker]]:::queue
        Worker[Celery Worker]:::backend
    end

    subgraph "KI-Dienste"
        Deepgram[Deepgram Nova-2]:::external
        Mistral[Mistral AI]:::external
    end

    subgraph "Automation (n8n)"
        N8N[n8n Hub]:::n8n
        Email[E-Mail / WhatsApp]:::external
    end

    %% Verbindungen
    User <--> UI
    UI <--> API
    
    API <--> DB
    API <--> S3
    API <--> Cache
    
    API -- "Task" --> Broker
    Broker -- "Job" --> Worker
    
    Worker <--> S3
    Worker <--> DB
    
    Worker -- "Audio -> Text" --> Deepgram
    Worker -- "Text -> PV" --> Mistral
    
    API -- "Webhook" --> N8N
    Worker -- "Webhook" --> N8N
    N8N --> Email
```

### Kurzbeschreibung:
1. **Frontend**: React-App für Nutzerinteraktion.
2. **Backend**: FastAPI für Logik und S3-Management.
3. **Pipeline**: Celery/RabbitMQ für langlaufende KI-Aufgaben.
4. **KI**: Deepgram (Transkription) & Mistral (Protokollerstellung).
5. **n8n**: Zentraler Hub für den Versand von E-Mails und Benachrichtigungen.
