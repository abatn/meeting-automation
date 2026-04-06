-- Complete database schema for Meeting Automation System (Staging)
-- Based on SQLAlchemy Models - Created 2026-04-05

\set ON_ERROR_STOP on

-- 1. EXTENSIONS
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "unaccent";

-- 2. REFERENCE TABLES (no dependencies)
CREATE TABLE IF NOT EXISTS roles (
    id VARCHAR PRIMARY KEY,
    name VARCHAR(128) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS permissions (
    id VARCHAR PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. CORE TENANT TABLE (clients)
CREATE TABLE IF NOT EXISTS clients (
    id VARCHAR PRIMARY KEY,
    company_name VARCHAR(255) UNIQUE NOT NULL,
    subscription_plan VARCHAR(50),
    subscription_status VARCHAR(50),
    subscription_start_date TIMESTAMPTZ,
    subscription_end_date TIMESTAMPTZ,
    billing_cycle VARCHAR(20),
    minutes_included INT,
    minutes_used INT,
    payment_method VARCHAR(20),
    observations TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. ASSOCIATION TABLES (dependencies: roles, permissions)
CREATE TABLE IF NOT EXISTS role_permissions (
    role_id VARCHAR NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id VARCHAR NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

-- 5. USERS (depends on clients)
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR PRIMARY KEY,
    client_id VARCHAR NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
    is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
    totp_secret TEXT,
    is_mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_users_client_id ON users(client_id);
CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);

-- 6. USER-ROLE ASSOCIATION (depends on users, roles)
CREATE TABLE IF NOT EXISTS user_roles (
    user_id VARCHAR NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id VARCHAR NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

-- 7. MEETING_ROOMS (depends on clients)
CREATE TABLE IF NOT EXISTS meeting_rooms (
    id VARCHAR PRIMARY KEY,
    client_id VARCHAR NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    location_description TEXT,
    capacity INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_meeting_rooms_client_id ON meeting_rooms(client_id);

-- 8. MEETINGS (depends on clients, users, meeting_rooms)
CREATE TABLE IF NOT EXISTS meetings (
    id VARCHAR PRIMARY KEY,
    client_id VARCHAR NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    status VARCHAR(50),
    creator_id VARCHAR REFERENCES users(id),
    room_id VARCHAR REFERENCES meeting_rooms(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_meetings_client_id ON meetings(client_id);
CREATE INDEX IF NOT EXISTS ix_meetings_creator_id ON meetings(creator_id);

-- 9. ACTION_SUGGESTIONS (depends on clients, meetings)
CREATE TABLE IF NOT EXISTS action_suggestions (
    id VARCHAR PRIMARY KEY,
    client_id VARCHAR NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    meeting_id VARCHAR NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    suggested_assignee VARCHAR,
    confidence_score FLOAT,
    language VARCHAR(10) DEFAULT 'en' NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_action_suggestions_client_id ON action_suggestions(client_id);
CREATE INDEX IF NOT EXISTS ix_action_suggestions_meeting_id ON action_suggestions(meeting_id);

-- 10. ACTIONS (depends on clients, meetings)
CREATE TABLE IF NOT EXISTS actions (
    id VARCHAR PRIMARY KEY,
    client_id VARCHAR NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    meeting_id VARCHAR NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    priority VARCHAR(20) DEFAULT 'medium',
    due_date TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_actions_client_id ON actions(client_id);
CREATE INDEX IF NOT EXISTS ix_actions_meeting_id ON actions(meeting_id);

-- 11. ACTION_ASSIGNMENTS (depends on actions, users)
CREATE TABLE IF NOT EXISTS action_assignments (
    id VARCHAR PRIMARY KEY,
    action_id VARCHAR NOT NULL REFERENCES actions(id) ON DELETE CASCADE,
    user_id VARCHAR REFERENCES users(id),
    external_email VARCHAR,
    external_name VARCHAR,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_action_assignments_action_id ON action_assignments(action_id);
CREATE INDEX IF NOT EXISTS ix_action_assignments_user_id ON action_assignments(user_id);

-- 12. RECORDINGS (depends on clients, meetings)
CREATE TABLE IF NOT EXISTS recordings (
    id VARCHAR PRIMARY KEY,
    client_id VARCHAR NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    meeting_id VARCHAR NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    file_path VARCHAR(255),
    status VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_recordings_client_id ON recordings(client_id);
CREATE INDEX IF NOT EXISTS ix_recordings_meeting_id ON recordings(meeting_id);

-- 13. TRANSCRIPTIONS (depends on clients, meetings, recordings)
CREATE TABLE IF NOT EXISTS transcriptions (
    id VARCHAR PRIMARY KEY,
    client_id VARCHAR NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    meeting_id VARCHAR NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    recording_id VARCHAR REFERENCES recordings(id),
    language VARCHAR(50),
    full_text TEXT,
    segments JSON,
    status VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_transcriptions_client_id ON transcriptions(client_id);
CREATE INDEX IF NOT EXISTS ix_transcriptions_meeting_id ON transcriptions(meeting_id);

-- 14. PVS (depends on clients, meetings)
CREATE TABLE IF NOT EXISTS pvs (
    id VARCHAR PRIMARY KEY,
    client_id VARCHAR NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    meeting_id VARCHAR NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    content_html TEXT,
    language VARCHAR(10) DEFAULT 'fr',
    status VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_pvs_client_id ON pvs(client_id);
CREATE INDEX IF NOT EXISTS ix_pvs_meeting_id ON pvs(meeting_id);

-- 15. PV_VERSIONS (depends on pvs)
CREATE TABLE IF NOT EXISTS pv_versions (
    id VARCHAR PRIMARY KEY,
    pv_id VARCHAR NOT NULL REFERENCES pvs(id) ON DELETE CASCADE,
    version_number INT NOT NULL,
    content_html TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_pv_versions_pv_id ON pv_versions(pv_id);

-- 16. AUDIT_LOGS (depends on clients, users)
CREATE TABLE IF NOT EXISTS audit_logs (
    id VARCHAR PRIMARY KEY,
    client_id VARCHAR NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    user_id VARCHAR REFERENCES users(id),
    action VARCHAR(50) NOT NULL,
    table_name VARCHAR(100),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_audit_logs_client_id ON audit_logs(client_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_timestamp ON audit_logs(timestamp);

-- 17. TEAM_MEMBERS (depends on clients)
CREATE TABLE IF NOT EXISTS team_members (
    id VARCHAR PRIMARY KEY,
    client_id VARCHAR NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone_number VARCHAR(50),
    position VARCHAR(255),
    department VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_team_members_client_id ON team_members(client_id);

-- 18. OAUTH (no FK dependencies except clients)
CREATE TABLE IF NOT EXISTS oauth_clients (
    id VARCHAR PRIMARY KEY,
    client_id VARCHAR UNIQUE NOT NULL,
    client_secret VARCHAR,
    name VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS oauth_access_tokens (
    id VARCHAR PRIMARY KEY,
    access_token VARCHAR(255) UNIQUE NOT NULL,
    token_type VARCHAR(50),
    expires_at TIMESTAMPTZ,
    user_id VARCHAR REFERENCES users(id) ON DELETE CASCADE,
    client_id VARCHAR REFERENCES oauth_clients(client_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_oauth_access_tokens_user_id ON oauth_access_tokens(user_id);

-- 19. SETTINGS (standalone)
CREATE TABLE IF NOT EXISTS settings (
    id VARCHAR PRIMARY KEY,
    key VARCHAR(255) UNIQUE NOT NULL,
    value TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 20. ALEMBIC VERSION
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL PRIMARY KEY
);
INSERT INTO alembic_version (version_num) VALUES ('4fb76575fee0')
ON CONFLICT (version_num) DO NOTHING;

-- 21. SEED DATA (only if empty)
-- Seed roles
INSERT INTO roles (id, name, description) VALUES
('role-sysadmin', 'system_admin', 'Global Business/System Administrator'),
('role-techadmin', 'tech_admin', 'Technical Administrator (Mission Control)'),
('role-admin', 'admin', 'Tenant Administrator'),
('role-dg', 'dg', 'Director General'),
('role-manager', 'manager', 'Department Manager'),
('role-participant', 'participant', 'Regular Participant')
ON CONFLICT (name) DO NOTHING;

-- Seed permissions (minimal)
INSERT INTO permissions (id, name, description) VALUES
('perm-users-read', 'users:read', 'Read user information'),
('perm-users-write', 'users:write', 'Create/update users'),
('perm-meetings-read', 'meetings:read', 'Read meetings'),
('perm-meetings-write', 'meetings:write', 'Create/update meetings'),
('perm-actions-read', 'actions:read', 'Read actions'),
('perm-actions-write', 'actions:write', 'Create/update actions')
ON CONFLICT (name) DO NOTHING;

-- Seed default OAuth client
INSERT INTO oauth_clients (id, client_id, client_secret, name)
VALUES ('oauth-client-default', 'meeting-automation-app', 'hashed-secret-placeholder', 'Meeting Automation Application')
ON CONFLICT (client_id) DO NOTHING;

SELECT 'Schema created successfully!' as status;
