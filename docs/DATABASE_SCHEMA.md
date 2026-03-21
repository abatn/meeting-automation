# Database Schema for Meeting Automation System

This document outlines the database schema for the Meeting Automation System, which uses PostgreSQL as its primary data store. The schema is designed to support multi-tenant SaaS operations, meeting management, user authentication, recording storage, transcription, PV generation, action item tracking, and audit logging.

## 1. Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    CLIENTS {
        UUID id PK
        VARCHAR company_name UNIQUE
        VARCHAR subscription_plan
        VARCHAR subscription_status
        TIMESTAMP subscription_start_date
        TIMESTAMP subscription_end_date
        VARCHAR billing_cycle
        INT minutes_included
        INT minutes_used
        VARCHAR payment_method
        TEXT observations
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    USERS {
        UUID id PK
        UUID client_id FK
        VARCHAR email UNIQUE
        VARCHAR hashed_password
        VARCHAR full_name
        BOOLEAN is_active
        BOOLEAN is_mfa_enabled
        VARCHAR mfa_secret OPTIONAL
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    MEETINGS {
        UUID id PK
        UUID client_id FK
        VARCHAR title
        TEXT description
        TIMESTAMP start_time
        TIMESTAMP end_time
        VARCHAR status
        UUID creator_id FK
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    RECORDINGS {
        UUID id PK
        UUID client_id FK
        UUID meeting_id FK
        VARCHAR file_path
        VARCHAR status
        TIMESTAMP created_at
    }

    TRANSCRIPTIONS {
        UUID id PK
        UUID client_id FK
        UUID meeting_id FK
        UUID recording_id FK
        VARCHAR language
        TEXT full_text
        JSON segments
        VARCHAR status
        TIMESTAMP created_at
    }

    ACTION_SUGGESTIONS {
        UUID id PK
        UUID client_id FK
        UUID meeting_id FK
        VARCHAR title
        TEXT description
        VARCHAR status
        TIMESTAMP created_at
    }

    PVS {
        UUID id PK
        UUID client_id FK
        UUID meeting_id FK
        TEXT content_html
        VARCHAR status
        TIMESTAMP created_at
    }

    ACTIONS {
        UUID id PK
        UUID client_id FK
        UUID meeting_id FK
        VARCHAR title
        TEXT description
        VARCHAR status
        TIMESTAMP created_at
    }

    AUDIT_LOGS {
        UUID id PK
        UUID client_id FK
        UUID user_id FK
        VARCHAR action
        VARCHAR table_name
        TIMESTAMP timestamp
    }

    CLIENTS ||--o{ USERS : "has"
    CLIENTS ||--o{ MEETINGS : "has"
    CLIENTS ||--o{ RECORDINGS : "has"
    CLIENTS ||--o{ TRANSCRIPTIONS : "has"
    CLIENTS ||--o{ PVS : "has"
    CLIENTS ||--o{ ACTIONS : "has"
    CLIENTS ||--o{ AUDIT_LOGS : "has"

    USERS ||--o{ MEETINGS : "creates"
    MEETINGS ||--o{ RECORDINGS : "has"
    MEETINGS ||--o{ PVS : "has"
    MEETINGS ||--o{ ACTIONS : "has"
    RECORDINGS ||--o{ TRANSCRIPTIONS : "has"
```

## 2. Table Descriptions

### 2.0. `clients` Table (Mandanten)

- **Description**: Stores tenant-specific information, subscription status, and billing details.
- **Fields**:
    - `id` (UUID, Primary Key): Unique identifier for the client.
    - `company_name` (VARCHAR, Unique): Name of the company.
    - `subscription_plan` (VARCHAR): Enum (GRATUIT, PRO, ENTREPRISE).
    - `subscription_status` (VARCHAR): Enum (ACTIVE, DISABLED, PENDING).
    - `minutes_included` (INT): Monthly allowance for transcriptions.
    - `minutes_used` (INT): Usage in the current billing cycle.
    - `created_at` (TIMESTAMP): Timestamp when the tenant was created.

### 2.1. `users` Table

- **Description**: Stores user information. Every user is linked to exactly one client.
- **Fields**:
    - `id` (UUID, Primary Key): Unique identifier for the user.
    - `client_id` (UUID, Foreign Key to `clients.id`): Tenant ID.
    - `email` (VARCHAR, Unique): Login email.
    - `hashed_password` (VARCHAR): Security credential.
    - `is_superuser` (BOOLEAN): Flag for System-Admins.

### 2.2. `meetings` Table

- **Description**: Stores meeting details. Strictly isolated by `client_id`.
- **Fields**:
    - `id` (UUID, Primary Key): Unique identifier.
    - `client_id` (UUID, Foreign Key to `clients.id`): Tenant ID.
    - `title` (VARCHAR): Meeting title.
    - `status` (VARCHAR): Status (planned, in_progress, completed).

### 2.3. `recordings` Table

- **Description**: Audio recording metadata. Isolated by `client_id`.
- **Fields**:
    - `id` (UUID, Primary Key).
    - `client_id` (UUID, FK).
    - `meeting_id` (UUID, FK).
    - `file_path` (VARCHAR): Path in S3 bucket.

### 2.4. `transcriptions` Table

- **Description**: AI generated transcripts. Isolated by `client_id`.
- **Fields**:
    - `id` (UUID, Primary Key).
    - `client_id` (UUID, FK).
    - `meeting_id` (UUID, FK).
    - `full_text` (TEXT).

### 2.5. `pvs` Table

- **Description**: Process-Verbaux (Meeting Minutes). Isolated by `client_id`.
- **Fields**:
    - `id` (UUID, Primary Key).
    - `client_id` (UUID, FK).
    - `meeting_id` (UUID, FK).
    - `content_html` (TEXT).

### 2.6. `actions` Table

- **Description**: Action items from meetings. Isolated by `client_id`.
- **Fields**:
    - `id` (UUID, Primary Key).
    - `client_id` (UUID, FK).
    - `meeting_id` (UUID, FK).
    - `title` (VARCHAR).

### 2.7. `audit_logs` Table

- **Description**: ISO 27001 compliant activity logs. Isolated by `client_id`.
- **Fields**:
    - `id` (UUID, Primary Key).
    - `client_id` (UUID, FK).
    - `user_id` (UUID, FK).
    - `action` (VARCHAR): Request method (POST, PUT, DELETE).
    - `table_name` (VARCHAR).
    - `timestamp` (TIMESTAMP).
