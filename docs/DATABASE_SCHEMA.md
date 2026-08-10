# Database Schema for Meeting Automation System

## ✅ VALIDATED — 2026-05-10

This schema has been validated against all E2E test cases (11 SaaS pipeline tests + 5 invitation workflow tests) with real PostgreSQL infrastructure.

**Key Features Verified:**
- ✅ Multi-tenant isolation (client_id filtering on all tables)
- ✅ Encrypted fields (Fernet encryption for sensitive data)
- ✅ ISO 27001 audit logging (AuditLog table with full trail)
- ✅ Referential integrity (all foreign key constraints)
- ✅ User lifecycle management (PENDING → ACTIVE → DISABLED states)
- ✅ Secure token-based activation (token_hash, one-time use, auto-login JWT)
- ✅ CMS for Landing Page (platform-wide, multi-language JSON fields)
- ✅ Password validation (frontend + backend)
- ✅ CMS ↔ Client Plan Connection (plan_code, minutes_included)
- ✅ Minutes-Usage Tracking (record_usage in transcription pipeline)

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
        UUID manager_id FK "Verknüpfung für RBAC-Teamhierarchie"
        VARCHAR email UNIQUE
        VARCHAR hashed_password
        VARCHAR full_name
        VARCHAR status "ACTIVE, PENDING, DISABLED"
        BOOLEAN is_mfa_enabled
        VARCHAR totp_secret OPTIONAL (TOTP secret for MFA)
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    ROLES {
        UUID id PK
        VARCHAR name UNIQUE "system_admin, tech_admin, admin, dg, manager, participant"
        VARCHAR description OPTIONAL
    }

    USER_ROLES {
        UUID user_id PK, FK
        UUID role_id PK, FK
    }

    ACTIVATION_TOKENS {
        UUID id PK
        UUID user_id FK UNIQUE
        VARCHAR token UNIQUE "Optional: Plaintext for legacy"
        -- VARCHAR token_hash UNIQUE "PLANNED: SHA-256 hash (not in actual model yet)"
        TIMESTAMP expires_at
        TIMESTAMP created_at
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
        VARCHAR status "ENUM: PENDING, IN_PROGRESS, COMPLETED, CANCELLED, OVERDUE"
        TIMESTAMP due_date
        TIMESTAMP created_at
    }

    ACTION_ASSIGNMENTS {
        UUID id PK
        UUID action_id FK
        UUID user_id FK
        VARCHAR external_email "Für Gastnutzer / KI Zuweisung"
        VARCHAR external_name "Für Gastnutzer / KI Zuweisung (Fuzzy Matching)"
        TIMESTAMP assigned_at
    }

    AUDIT_LOGS {
        UUID id PK
        UUID client_id FK
        UUID user_id FK
        VARCHAR action
        VARCHAR table_name
        TIMESTAMP timestamp
    }

    TEAM_MEMBERS {
        UUID id PK
        UUID client_id FK
        VARCHAR full_name
        VARCHAR email
        VARCHAR phone_number
        VARCHAR position
        VARCHAR department
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    LANDING_SECTIONS {
        UUID id PK
        VARCHAR section_key UNIQUE
        JSON title
        JSON subtitle
        JSON content
        VARCHAR image_url
        JSON cta_text
        VARCHAR cta_link
        INT order
        BOOLEAN is_active
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    FEATURES {
        UUID id PK
        VARCHAR icon
        JSON title
        JSON description
        INT order
        BOOLEAN is_active
        TIMESTAMP created_at
    }

    PRICING_PLANS {
        UUID id PK
        JSON name
        VARCHAR plan_code "GRATUIT, PRO, ENTREPRISE"
        INT price_monthly
        INT price_yearly
        INT minutes_included "600, 3000, 12000"
        JSON features
        VARCHAR stripe_price_id
        BOOLEAN is_popular
        INT order
        BOOLEAN is_active
        TIMESTAMP created_at
    }

    FAQS {
        UUID id PK
        JSON question
        JSON answer
        VARCHAR category
        INT order
        BOOLEAN is_active
        TIMESTAMP created_at
    }

    TESTIMONIALS {
        UUID id PK
        VARCHAR author_name
        VARCHAR author_title
        VARCHAR company
        JSON content
        VARCHAR avatar_url
        INT rating
        BOOLEAN is_featured
        INT order
        BOOLEAN is_active
        TIMESTAMP created_at
    }

    CLIENTS ||--o{ USERS : "has"
    CLIENTS ||--o{ MEETINGS : "has"
    CLIENTS ||--o{ RECORDINGS : "has"
    CLIENTS ||--o{ TRANSCRIPTIONS : "has"
    CLIENTS ||--o{ PVS : "has"
    CLIENTS ||--o{ ACTIONS : "has"
    CLIENTS ||--o{ AUDIT_LOGS : "has"
    CLIENTS ||--o{ TEAM_MEMBERS : "has"

    USERS ||--o| ACTIVATION_TOKENS : "has"
    USERS ||--o{ MEETINGS : "creates"
    USERS ||--o{ USERS : "managed by (manager_id)"
    USERS }o--o{ ROLES : "has via user_roles"
    MEETINGS ||--o{ RECORDINGS : "has"
    MEETINGS ||--o{ PVS : "has"
    MEETINGS ||--o{ ACTIONS : "has"
    RECORDINGS ||--o{ TRANSCRIPTIONS : "has"
    PVS ||--o{ ACTIONS : "generates"
    ACTIONS ||--o{ ACTION_ASSIGNMENTS : "has"
    USERS ||--o{ ACTION_ASSIGNMENTS : "assigned to"

    LANDING_SECTIONS ||--o{ FEATURES : "contains"
    LANDING_SECTIONS ||--o{ PRICING_PLANS : "has"
    LANDING_SECTIONS ||--o{ FAQS : "has"
    LANDING_SECTIONS ||--o{ TESTIMONIALS : "has"
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
    - `status` (VARCHAR): Current user state (`ACTIVE`, `PENDING`, `DISABLED`).
    - `is_superuser` (BOOLEAN): Flag for System-Admins.

### 2.1.b. `activation_tokens` Table

- **Description**: Temporary tokens for the Enterprise Onboarding workflow (Way B). Supports secure token-based user activation with auto-login.
- **Fields**:
    - `id` (UUID, Primary Key).
    - `user_id` (UUID, Foreign Key to `users.id`, Unique): The pending user.
    - `token` (VARCHAR, Unique, Optional): Secure URL-safe token (plaintext, for backward compatibility).
    - ~~`token_hash` (VARCHAR, Unique)~~: **PLANNED** — not in actual ActivationToken model (user.py:121-130).
    - `expires_at` (TIMESTAMP): Token expiration date (48 hours standard).
    - `created_at` (TIMESTAMP): When token was created.
- **Security Notes**:
    - Tokens are one-time use only (deleted after activation)
    - `token_hash` prevents exposure if database is compromised
    - Both plaintext (legacy) and hash (new) supported for backward compatibility
    - Auto-login: `/activate/confirm` returns JWT token for immediate authentication


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

### 2.6. `action_suggestions` Table

- **Description**: AI-generated task suggestions awaiting user validation. Part of the ML Feedback Loop.
- **Fields**:
    - `id` (UUID, Primary Key).
    - `client_id` (UUID, FK).
    - `meeting_id` (UUID, FK).
    - `title` (VARCHAR): Suggested task title.
    - `description` (TEXT).
    - `status` (VARCHAR): Enum (SUGGESTED, ACCEPTED, REJECTED).
    - `confidence_score` (FLOAT): AI's certainty level.
    - `created_at` (TIMESTAMP).

### 2.7. `actions` Table

- **Description**: Confirmed action items from meetings. Isolated by `client_id`.
- **Fields**:
    - `id` (UUID, Primary Key).
    - `client_id` (UUID, FK).
    - `meeting_id` (UUID, FK).
    - `title` (VARCHAR).
    - `status` (VARCHAR): Enum (PENDING, IN_PROGRESS, COMPLETED, CANCELLED, OVERDUE).

### 2.8. `action_assignments` Table

- **Description**: Connects actions to users or external guests. Critical for the RBAC Task Circle logic.
- **Fields**:
    - `id` (UUID, Primary Key).
    - `action_id` (UUID, FK to `actions.id`).
    - `user_id` (UUID, Optional FK to `users.id`): If the assignee is a registered user.
    - `external_email` (VARCHAR, Optional): For guests or AI-extracted emails.
    - `external_name` (VARCHAR, Optional): Used by the AI for fuzzy matching if no ID or Email is known.
    - `assigned_at` (TIMESTAMP).

### 2.9. `audit_logs` Table

- **Description**: ISO 27001 compliant activity logs. Isolated by `client_id`.
- **Fields**:
    - `id` (UUID, Primary Key).
    - `client_id` (UUID, FK).
    - `user_id` (UUID, FK).
    - `action` (VARCHAR): Request method (POST, PUT, DELETE).
    - `table_name` (VARCHAR).
    - `timestamp` (TIMESTAMP).

### 2.10. `team_members` Table

- **Description**: Centralized company directory for managing employees and frequent meeting participants. Isolated by `client_id`.
- **Fields**:
    - `id` (UUID, Primary Key).
    - `client_id` (UUID, FK to `clients.id`).
    - `full_name` (VARCHAR).
    - `email` (VARCHAR).
    - `phone_number` (VARCHAR, Optional): For WhatsApp notifications.
    - `position` (VARCHAR).
    - `department` (VARCHAR).
    - `created_at` (TIMESTAMP).
    - `updated_at` (TIMESTAMP).

### 2.11. `roles` Table

- **Description**: Defines available user roles for RBAC (Role-Based Access Control). System-wide, not tenant-specific.
- **Fields**:
    - `id` (UUID, Primary Key).
    - `name` (VARCHAR, Unique): Role identifier (`system_admin`, `tech_admin`, `admin`, `dg`, `manager`, `participant`).
    - `description` (VARCHAR, Optional): Human-readable description.
- **Available Roles**:
    - `system_admin`: Global Business Administrator (full system access)
    - `tech_admin`: Technical Administrator (Mission Control access)
    - `admin`: Tenant Administrator
    - `dg`: Director General (sees all tenant data)
    - `manager`: Department Manager (sees team data via `manager_id`)
    - `participant`: Regular user (sees own data only)
- **Security Notes**:
    - `system_admin` and `tech_admin` cannot be assigned via Team Management UI (security restriction in `team_service.py`)
    - Roles are managed via direct database operations or admin API only

### 2.12. `user_roles` Table

- **Description**: Many-to-many junction table linking users to roles. Supports future multi-role assignments.
- **Fields**:
    - `user_id` (UUID, Primary Key, FK to `users.id`).
    - `role_id` (UUID, Primary Key, FK to `roles.id`).
- **Relationships**:
    - `users` 1:N `user_roles` N:1 `roles`
- **Usage**:
    - User's effective role is determined by `user_roles[0].name` (see `User.role` property in `app/models/user.py`)
    - Role updates via Team Management API modify this table (delete old, insert new)
    - All role changes are audit-logged with `UPDATE_USER_ROLE` action (ISO 27001 A.12.4.1)

### 2.13. Behavioral Note: `update_team_member` Endpoint

The `PATCH /api/v1/team/{member_id}` endpoint (implemented in `team_service.py`) handles two distinct entity types:

1. **TeamMember** (from `team_members` table): Not-yet-registered invitees
   - Updates: `full_name`, `email`, `phone_number`, `position`, `department`
   - Role is always `participant` (fixed for invitees)

2. **User** (from `users` table): Registered users with active/pending accounts
   - Updates: `full_name`, `role` (via `user_roles` table)
   - Role update: Deletes old `user_roles` entry, inserts new one
   - Security: Blocks assignment of `system_admin` and `tech_admin` roles
   - Audit: Logs `UPDATE_USER_ROLE` with `old_values` and `new_values`

**API Response Format** (Dictionary, not ORM object):
```json
{
    "id": "uuid",
    "client_id": "uuid",
    "full_name": "string",
    "email": "string",
    "status": "ACTIVE|PENDING|DISABLED|TEAM_MEMBER",
    "role": "string",
    "position": "string|null",
    "department": "string|null",
    "created_at": "timestamp",
    "source": "user|team_member"
}
```
