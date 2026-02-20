# Database Schema for Meeting Automation System

This document outlines the database schema for the Meeting Automation System, which uses PostgreSQL as its primary data store. The schema is designed to support meeting management, user authentication, recording storage, transcription, PV generation, action item tracking, and audit logging.

## 1. Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    USERS {
        UUID id PK
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
        VARCHAR title
        TEXT description
        TIMESTAMP start_time
        TIMESTAMP end_time
        VARCHAR status ENUM("scheduled", "in_progress", "completed", "cancelled")
        UUID organizer_id FK
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    PARTICIPANTS {
        UUID user_id PK,FK
        UUID meeting_id PK,FK
        VARCHAR role ENUM("organizer", "attendee")
    }

    RECORDINGS {
        UUID id PK
        UUID meeting_id FK
        VARCHAR file_url
        VARCHAR file_name
        VARCHAR file_type
        INT file_size
        VARCHAR status ENUM("uploaded", "processing", "completed", "failed")
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    TRANSCRIPTIONS {
        UUID id PK
        UUID recording_id FK
        VARCHAR language
        TEXT text
        VARCHAR status ENUM("in_progress", "completed", "failed")
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    PROCES_VERBAUX {
        UUID id PK
        UUID meeting_id FK
        UUID transcription_id FK
        TEXT content
        VARCHAR status ENUM("generated", "reviewed", "validated", "finalized")
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    ACTIONS {
        UUID id PK
        UUID meeting_id FK
        TEXT description
        UUID assigned_to_id FK
        TIMESTAMP due_date
        VARCHAR priority ENUM("low", "medium", "high")
        VARCHAR status ENUM("open", "in_progress", "completed", "cancelled")
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    AUDIT_LOGS {
        UUID id PK
        UUID user_id FK
        VARCHAR action_type
        TEXT details
        TIMESTAMP timestamp
        VARCHAR ip_address
    }

    USERS ||--o{ MEETINGS : "organizes"
    USERS ||--o{ PARTICIPANTS : "participates_in"
    MEETINGS ||--o{ PARTICIPANTS : "has_participants"
    MEETINGS ||--o{ RECORDINGS : "has_recording"
    MEETINGS ||--o{ PROCES_VERBAUX : "has_pv"
    MEETINGS ||--o{ ACTIONS : "has_actions"
    RECORDINGS ||--o{ TRANSCRIPTIONS : "has_transcription"
    TRANSCRIPTIONS ||--o{ PROCES_VERBAUX : "generates_pv_from"
    USERS ||--o{ ACTIONS : "assigned_to"
    USERS ||--o{ AUDIT_LOGS : "performs_action"
```

## 2. Table Descriptions

### 2.1. `users` Table

- **Description**: Stores user information, including authentication credentials and profile details.
- **Fields**:
    - `id` (UUID, Primary Key): Unique identifier for the user.
    - `email` (VARCHAR, Unique): User's email address, used for login.
    - `hashed_password` (VARCHAR): Hashed password for security.
    - `full_name` (VARCHAR): User's full name.
    - `is_active` (BOOLEAN, Default: `TRUE`): Indicates if the user account is active.
    - `is_mfa_enabled` (BOOLEAN, Default: `FALSE`): Indicates if multi-factor authentication is enabled.
    - `mfa_secret` (VARCHAR, Nullable): Secret key for MFA, encrypted.
    - `created_at` (TIMESTAMP): Timestamp when the user account was created.
    - `updated_at` (TIMESTAMP): Timestamp of the last update to the user account.

### 2.2. `meetings` Table

- **Description**: Stores details about scheduled and past meetings.
- **Fields**:
    - `id` (UUID, Primary Key): Unique identifier for the meeting.
    - `title` (VARCHAR): Title of the meeting.
    - `description` (TEXT): Detailed description of the meeting.
    - `start_time` (TIMESTAMP): Scheduled start time of the meeting.
    - `end_time` (TIMESTAMP): Scheduled end time of the meeting.
    - `status` (VARCHAR, Enum): Current status of the meeting (`scheduled`, `in_progress`, `completed`, `cancelled`).
    - `organizer_id` (UUID, Foreign Key to `users.id`): User who organized the meeting.
    - `created_at` (TIMESTAMP): Timestamp when the meeting was created.
    - `updated_at` (TIMESTAMP): Timestamp of the last update to the meeting.

### 2.3. `participants` Table

- **Description**: Junction table for many-to-many relationship between users and meetings, defining participants.
- **Fields**:
    - `user_id` (UUID, Primary Key, Foreign Key to `users.id`): Participant's user ID.
    - `meeting_id` (UUID, Primary Key, Foreign Key to `meetings.id`): Meeting ID.
    - `role` (VARCHAR, Enum): Role of the participant in the meeting (`organizer`, `attendee`).

### 2.4. `recordings` Table

- **Description**: Stores information about audio/video recordings associated with meetings.
- **Fields**:
    - `id` (UUID, Primary Key): Unique identifier for the recording.
    - `meeting_id` (UUID, Foreign Key to `meetings.id`): The meeting this recording belongs to.
    - `file_url` (VARCHAR): URL to the stored recording file (e.g., S3 URL).
    - `file_name` (VARCHAR): Original name of the uploaded file.
    - `file_type` (VARCHAR): MIME type of the file (e.g., `audio/mpeg`, `video/mp4`).
    - `file_size` (INT): Size of the file in bytes.
    - `status` (VARCHAR, Enum): Current status of the recording (`uploaded`, `processing`, `completed`, `failed`).
    - `created_at` (TIMESTAMP): Timestamp when the recording was uploaded.
    - `updated_at` (TIMESTAMP): Timestamp of the last update to the recording.

### 2.5. `transcriptions` Table

- **Description**: Stores the transcribed text of meeting recordings.
- **Fields**:
    - `id` (UUID, Primary Key): Unique identifier for the transcription.
    - `recording_id` (UUID, Foreign Key to `recordings.id`): The recording this transcription is for.
    - `language` (VARCHAR): Language of the transcription (e.g., `en`, `fr-TN`, `ar-TN`).
    - `text` (TEXT): The full transcribed text of the recording.
    - `status` (VARCHAR, Enum): Current status of the transcription (`in_progress`, `completed`, `failed`).
    - `created_at` (TIMESTAMP): Timestamp when transcription was initiated.
    - `updated_at` (TIMESTAMP): Timestamp of the last update to the transcription.

### 2.6. `proces_verbaux` Table

- **Description**: Stores the generated meeting minutes (PVs) and their associated metadata.
- **Fields**:
    - `id` (UUID, Primary Key): Unique identifier for the PV.
    - `meeting_id` (UUID, Foreign Key to `meetings.id`): The meeting this PV is for.
    - `transcription_id` (UUID, Foreign Key to `transcriptions.id`): The transcription used to generate this PV.
    - `content` (TEXT): The full content of the PV (e.g., in Markdown or HTML format).
    - `status` (VARCHAR, Enum): Current status of the PV (`generated`, `reviewed`, `validated`, `finalized`).
    - `created_at` (TIMESTAMP): Timestamp when the PV was generated.
    - `updated_at` (TIMESTAMP): Timestamp of the last update to the PV.

### 2.7. `actions` Table

- **Description**: Tracks action items identified during meetings or in PVs.
- **Fields**:
    - `id` (UUID, Primary Key): Unique identifier for the action item.
    - `meeting_id` (UUID, Foreign Key to `meetings.id`): The meeting this action item is associated with.
    - `description` (TEXT): Description of the action item.
    - `assigned_to_id` (UUID, Foreign Key to `users.id`): The user responsible for the action.
    - `due_date` (TIMESTAMP, Nullable): Deadline for completing the action.
    - `priority` (VARCHAR, Enum): Priority level (`low`, `medium`, `high`).
    - `status` (VARCHAR, Enum): Current status of the action item (`open`, `in_progress`, `completed`, `cancelled`).
    - `created_at` (TIMESTAMP): Timestamp when the action item was created.
    - `updated_at` (TIMESTAMP): Timestamp of the last update to the action.

### 2.8. `audit_logs` Table

- **Description**: Records all significant user actions for security and compliance purposes (ISO 27001).
- **Fields**:
    - `id` (UUID, Primary Key): Unique identifier for the log entry.
    - `user_id` (UUID, Foreign Key to `users.id`, Nullable): The user who performed the action (can be null for system actions).
    - `action_type` (VARCHAR): Type of action performed (e.g., `user_login`, `meeting_created`, `pv_validated`).
    - `details` (TEXT): JSONB field with detailed information about the action, including old/new values where applicable.
    - `timestamp` (TIMESTAMP): Timestamp when the action occurred.
    - `ip_address` (VARCHAR): IP address from which the action was performed.