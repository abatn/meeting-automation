# Meeting Automation System - Project Context for Gemini CLI

This `GEMINI.md` file provides essential context for the Gemini CLI to effectively assist with tasks related to the "Meeting Automation System".

## 📚 Project Overview

The Meeting Automation System is a comprehensive application designed for automated meeting transcription, automatic "Procès-Verbaux" (PV) generation using AI, and efficient action tracking. It is specifically optimized for the Tunisia/Maghreb markets with multilingual support (French, Tunisian Arabic, MSA, English) and WhatsApp integration for notifications. The system is built with a strong emphasis on ISO 27001 compliance, featuring a full audit trail.

**Key Features:**
*   🎙️ **Audio Recording & Transcription** (FR/AR/EN with code-switching)
*   📝 **Automatic PV Generation** using AI
*   ✅ **Action Item Tracking** with WhatsApp notifications
*   📊 **Dashboards & Reports** (for Director General, Manager, and Participant roles)
*   🔒 **ISO 27001 Compliant** with full audit trail
*   🌍 **Multilingual** support
*   📱 **WhatsApp Integration**

## 💻 Tech Stack

### Backend
*   FastAPI (Python 3.11)
*   PostgreSQL 15 (Database)
*   Redis (Caching, Session Management)
*   Celery + RabbitMQ (Asynchronous Task Queue)
*   n8n (Workflow Automation)

### Frontend
*   React 18 + TypeScript
*   Material-UI (UI Component Library)
*   Redux Toolkit (State Management)
*   i18next (Internationalization with RTL support)

### AI Services
*   Whisper (Speech-to-Text)
*   Mistral 7B Arabic (Natural Language Processing)

## 🚀 Building and Running the Project

### Prerequisites
*   Docker & Docker Compose
*   Python 3.11+
*   Node.js 20+

### Development Setup (Recommended)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourorg/meeting-automation.git
    cd meeting-automation
    ```

2.  **Copy environment file:**
    ```bash
    cp .env.example .env
    # IMPORTANT: Review and update .env settings as needed.
    ```

3.  **Start Docker services:**
    ```bash
    docker compose up -d
    ```
    *(Note: The `docker-compose` command might vary based on your Docker installation. `docker compose` (without hyphen) is the modern standard.)*

4.  **Initialize the system (Database, Migrations, Users, S3 Buckets):**
    ```bash
    ./setup-system.sh
    ```
    *This script handles database health checks, Alembic migrations (stamping `head` if tables exist or upgrading from scratch), n8n auxiliary table creation, seeding test users, and initializing MinIO S3 buckets.*

5.  **Access Applications:**
    *   **Backend API Docs:** `http://localhost:8000/api/docs`
    *   **Frontend:** `http://localhost:3000`
    *   **n8n Workflow UI:** `http://localhost:5678`
    *   **RabbitMQ Management:** `http://localhost:15672`

### Manual Setup (without Docker)
Refer to `docs/DEPLOYMENT.md` for detailed instructions on setting up the project components manually.

## 📐 Development Conventions & Guidelines

*   **Documentation:** Comprehensive documentation is available in the `docs/` directory, covering architecture, API, database schema, ISO 27001 compliance, cultural adaptations, and deployment.
*   **Implementation Protocols:** Specific implementation details and chronological development steps are documented in `docs/PROTOCOL_PART_*.md` files. Always review relevant protocols before starting new tasks.
*   **Contributing:** Refer to `CONTRIBUTING.md` for guidelines on contributing to the project.
*   **Security:** ISO 27001 compliance is a core mandate, implying rigorous security practices, audit trails, and data protection.
*   **Testing:** Look for `tests/` directories in `backend/` and `frontend/` for existing test patterns.

## ⚠️ Important Considerations for Gemini CLI

*   **Always read `docs/PROJECT_STATUS.md` first** to understand the current project state and prioritized tasks.
*   **Prioritize `setup-system.sh` for initialization.** Do not attempt manual orchestration of `docker compose`, `alembic`, or `seed_users.py` unless specifically debugging or modifying the script itself.
*   **Be mindful of Docker Compose restart behavior:** If changes are made to Docker configurations or Python code, ensure containers are restarted correctly (`docker compose up -d --force-recreate` or `docker compose restart <service>`) and allow sufficient `start_period` for services, especially the backend, to become healthy.
*   **Database Migrations:** Alembic's behavior with `auto-generate` can be complex, particularly with external tools like `n8n` that might auto-create tables. Always review generated migration scripts carefully.
*   **Multi-Tenant Transformation (Current Goal):** The immediate overarching goal is to transform the application into a multi-tenant SaaS platform, as detailed in `docs/SAAS_MULTI_TENANT_BRIEFING.md`. This involves significant database schema changes (`client_id` in many tables, `clients` table), authentication adjustments (JWT payload), and implementing Row-Level Security (RLS) or a global filtering mechanism. **Approach these changes in extremely small, verifiable steps.**
*   **RabbitMQ Stability (WSL2-specific fix):** The `docker-compose.yml` includes a specific `command` for the RabbitMQ service (`chown -R rabbitmq:rabbitmq /var/lib/rabbitmq && rabbitmq-server`) to address `eacces` permission issues often encountered in WSL2/Docker environments. Ensure this fix remains in place if `docker-compose.yml` is modified.
