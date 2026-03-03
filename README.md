# Meeting Automation System

Automated meeting transcription, PV generation, and action tracking system optimized for Tunisia/Maghreb markets.

## Features

- 🎙️ **Audio Recording & Transcription** (FR/AR/EN with code-switching)
- 📝 **Automatic PV Generation** using AI
- ✅ **Action Item Tracking** with WhatsApp notifications
- 📊 **Dashboards & Reports** (DG, Manager, Participant)
- 🔒 **ISO 27001 Compliant** with full audit trail
- 🌍 **Multilingual** (French, Tunisian Arabic, MSA, English)
- 📱 **WhatsApp Integration** (90% open rate in Tunisia)

## Tech Stack

### Backend
- FastAPI (Python 3.11)
- PostgreSQL 15
- Redis
- Celery + RabbitMQ
- n8n (Workflow Automation)

### Frontend
- React 18 + TypeScript
- Material-UI
- Redux Toolkit
- i18next (RTL support)

### AI Services
- Whisper (Speech-to-Text)
- Mistral 7B Arabic (NLP)

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 20+

### Development Setup

1. Clone repository
```bash
git clone https://github.com/yourorg/meeting-automation.git
cd meeting-automation
```

2. Copy environment file
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Start services
```bash
docker-compose up -d
```

4. Access applications
- Backend API: http://localhost:8000/api/docs
- Frontend: http://localhost:3000
- n8n: http://localhost:5678
- RabbitMQ: http://localhost:15672

### Manual Setup (without Docker)

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed instructions.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API Documentation](docs/API.md)
- [Database Schema](docs/DATABASE_SCHEMA.md)
- [ISO 27001 Compliance](docs/ISO27001.md)
- [Cultural Adaptations](docs/CULTURAL_ADAPTATIONS.md)
- [Deployment Guide](docs/DEPLOYMENT.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

## License

MIT License - see [LICENSE](LICENSE)

## Support

For issues and questions, please open a GitHub issue or contact support@example.com 
