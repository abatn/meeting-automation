# API Documentation for Meeting Automation System

This document details the RESTful API endpoints for the Meeting Automation System, built with FastAPI.

## 1. Authentication (`/api/v1/auth`)

### 1.1. User Registration
- **Endpoint**: `/api/v1/auth/register`
- **Method**: `POST`
- **Description**: Registers a new user.
- **Request Body**:
    ```json
    {
        "email": "user@example.com",
        "password": "strongpassword123",
        "full_name": "John Doe"
    }
    ```
- **Response (201 Created)**:
    ```json
    {
        "id": "uuid",
        "email": "user@example.com",
        "full_name": "John Doe",
        "is_active": true
    }
    ```

### 1.2. User Login
- **Endpoint**: `/api/v1/auth/login`
- **Method**: `POST`
- **Description**: Authenticates a user and returns access and refresh tokens.
- **Request Body**:
    ```json
    {
        "username": "user@example.com",
        "password": "strongpassword123"
    }
    ```
- **Response (200 OK)**:
    ```json
    {
        "access_token": "jwt_access_token",
        "refresh_token": "jwt_refresh_token",
        "token_type": "bearer"
    }
    ```

### 1.3. Refresh Token
- **Endpoint**: `/api/v1/auth/refresh`
- **Method**: `POST`
- **Description**: Generates a new access token using a valid refresh token.
- **Request Body**:
    ```json
    {
        "refresh_token": "jwt_refresh_token"
    }
    ```
- **Response (200 OK)**:
    ```json
    {
        "access_token": "new_jwt_access_token",
        "token_type": "bearer"
    }
    ```

### 1.4. MFA Setup (PLANNED — NOT IMPLEMENTED)
- **Endpoint**: `/api/v1/auth/mfa/setup`
- **Method**: `POST`
- **Description**: Initiates MFA setup for the authenticated user, returning a QR code URI.
- **Status**: Not implemented in backend/app/api/v1/auth.py
- **Response (200 OK)**:
    ```json
    {
        "otp_uri": "otpauth://totp/...",
        "qr_code_image": "base64_encoded_png_image"
    }
    ```

### 1.5. MFA Verify (PLANNED — NOT IMPLEMENTED)
- **Endpoint**: `/api/v1/auth/mfa/verify`
- **Method**: `POST`
- **Description**: Verifies the MFA token provided by the user to enable MFA.
- **Status**: Not implemented in backend/app/api/v1/auth.py
- **Request Body**:
    ```json
    {
        "otp_code": "123456"
    }
    ```
- **Response (200 OK)**:
    ```json
    {
        "message": "MFA enabled successfully"
    }
    ```

## 2. Meetings (`/api/v1/meetings`)

### 2.1. Create Meeting
- **Endpoint**: `/api/v1/meetings/`
- **Method**: `POST`
- **Description**: Schedules a new meeting.
- **Request Body**:
    ```json
    {
        "title": "Project Alpha Sync",
        "description": "Weekly sync meeting for Project Alpha.",
        "start_time": "2026-03-01T10:00:00Z",
        "end_time": "2026-03-01T11:00:00Z",
        "participants": ["participant1_id", "participant2_id"]
    }
    ```
- **Response (201 Created)**:
    ```json
    {
        "id": "uuid",
        "title": "Project Alpha Sync",
        "description": "Weekly sync meeting for Project Alpha.",
        "start_time": "2026-03-01T10:00:00Z",
        "end_time": "2026-03-01T11:00:00Z",
        "status": "scheduled"
    }
    ```

### 2.2. Get Meeting by ID
- **Endpoint**: `/api/v1/meetings/{meeting_id}`
- **Method**: `GET`
- **Description**: Retrieves details of a specific meeting.
- **Response (200 OK)**: Returns a `Meeting` object.

### 2.3. List Meetings
- **Endpoint**: `/api/v1/meetings/`
- **Method**: `GET`
- **Description**: Retrieves a list of meetings, with optional filters.
- **Query Parameters**: `skip` (int), `limit` (int), `status` (str), `participant_id` (uuid)
- **Response (200 OK)**:
    ```json
    [
        {
            "id": "uuid",
            "title": "Project Alpha Sync",
            "start_time": "2026-03-01T10:00:00Z",
            "end_time": "2026-03-01T11:00:00Z",
            "status": "scheduled"
        }
    ]
    ```

## 3. LiveKit (`/api/v1/meetings/{meeting_id}/livekit`)

### 3.1. Generate LiveKit Token
- **Endpoint**: `/api/v1/meetings/{meeting_id}/livekit/token`
- **Method**: `POST`
- **Description**: Generates LiveKit access token for meeting room.
- **Response (200 OK)**:
    ```json
    {
        "token": "eyJhbGciOiJIUzI1NiIs...",
        "server_url": "ws://localhost:7880"
    }
    ```

### 3.2. Start Recording
- **Endpoint**: `/api/v1/meetings/{meeting_id}/livekit/start-recording`
- **Method**: `POST`
- **Description**: Starts LiveKit Egress recording.
- **Response (200 OK)**:
    ```json
    {
        "recording_id": "uuid",
        "egress_id": "EG_xxx"
    }
    ```

### 3.3. Stop Recording
- **Endpoint**: `/api/v1/meetings/{meeting_id}/livekit/stop-recording`
- **Method**: `POST`
- **Description**: Stops active Egress recording.

### 3.4. Recording Status
- **Endpoint**: `/api/v1/meetings/{meeting_id}/livekit/recording-status`
- **Method**: `GET`
- **Description**: Returns current recording status (idle/recording/processing/completed/failed).

## 4. Recordings (`/api/v1/recordings`)

### 4.1. Upload Recording
- **Endpoint**: `/api/v1/recordings/upload/{meeting_id}`
- **Method**: `POST`
- **Description**: Uploads an audio/video recording file for a specific meeting.
- **Request Body**: `multipart/form-data` with `file` (audio/video file).
- **Response (200 OK)**:
    ```json
    {
        "id": "uuid",
        "meeting_id": "uuid",
        "file_path": "s3_file_key",
        "status": "uploaded",
        "created_at": "timestamp",
        "chunks": []
    }
    ```

### 4.2. Get Recording by ID
- **Endpoint**: `/api/v1/recordings/{recording_id}`
- **Method**: `GET`
- **Description**: Retrieves details of a specific recording.
- **Response (200 OK)**: Returns a `Recording` object.

## 4. Transcriptions (`/api/v1/transcriptions`)

### 4.1. Initiate Transcription
- **Endpoint**: `/api/v1/transcriptions/initiate`
- **Method**: `POST`
- **Description**: Initiates the transcription process for a given recording.
- **Request Body**:
    ```json
    {
        "recording_id": "uuid",
        "language": "ar-TN"
    }
    ```
- **Response (202 Accepted)**:
    ```json
    {
        "message": "Transcription initiated",
        "transcription_id": "uuid",
        "status": "in_progress"
    }
    ```
### 4.2. Get Transcription by ID
- **Endpoint**: `/api/v1/transcriptions/meeting/{meeting_id}`
- **Method**: `GET`
- **Description**: Retrieves the full transcription text and speaker segments for a meeting.
- **Response (200 OK)**:
    ```json
    {
        "id": "uuid",
        "meeting_id": "uuid",
        "language": "ar",
        "full_text": "The full transcribed text...",
        "segments": [
            {"speaker": "Speaker 0", "text": "Hello...", "start": 0.0, "end": 2.5},
            {"speaker": "Speaker 1", "text": "Hi...", "start": 2.6, "end": 4.1}
        ],
        "status": "completed"
    }
    ```

## 5. AI Insights (`/api/v1/meetings/{meeting_id}/ai-insights`)

### 5.1. Get AI Insights
- **Endpoint**: `/api/v1/meetings/{meeting_id}/ai-insights`
- **Method**: `GET`
- **Description**: Returns AI-generated insights including transcription, PV, and actions for a meeting.
- **Response (200 OK)**:
    ```json
    {
        "status": "completed",
        "transcription": {
            "segments": [
                {"speaker": "Abdelkader Batnini", "text": "...", "start": 0.0, "end": 2.5}
            ]
        },
        "insights": [
            {"topic": "Meeting Summary", "confidence": 0.85, "actions": ["..."]}
        ],
        "actions": [
            {"id": "uuid", "title": "Action item", "status": "pending"}
        ],
        "pv_id": "uuid"
    }
    ```

## 6. Procès-Verbaux (PV) (`/api/v1/pv`)
...
### 6.4. List Actions
...
## 7. Action Suggestions (`/api/v1/actions/suggestions`)

### 7.1. Get Suggestions for Meeting
- **Endpoint**: `/api/v1/actions/suggestions/{meeting_id}`
- **Method**: `GET`
- **Description**: Retrieves AI-suggested actions for a specific meeting.
- **Response (200 OK)**:
    ```json
    [
        {
            "id": "uuid",
            "title": "Proposed Task",
            "description": "Details...",
            "suggested_assignee": "John Doe",
            "confidence_score": 0.95,
            "status": "SUGGESTED"
        }
    ]
    ```

### 7.2. Submit Suggestion Feedback (Learn)
- **Endpoint**: `/api/v1/actions/suggestions/learn`
- **Method**: `POST`
- **Description**: Records user feedback (accept/reject) on a suggestion. If accepted, a real Action is created.
- **Request Body**:
    ```json
    {
        "suggestion_id": "uuid",
        "action": "accept"
    }
    ```
- **Response (200 OK)**: `{"status": "success"}`

### 7.3. Translate Suggestions
- **Endpoint**: `/api/v1/actions/suggestions/translate`
- **Method**: `POST`
- **Description**: Translates a list of suggestions on-the-fly for the UI.
- **Request Body**:
    ```json
    {
        "suggestions": [...],
        "target_language": "ar"
    }
    ```

## 8. Reports (`/api/v1/reports`)

- **Method**: `POST`
- **Description**: Generates a PV (meeting minutes) from a transcription.
- **Request Body**:
    ```json
    {
        "transcription_id": "uuid"
    }
    ```
- **Response (202 Accepted)**:
    ```json
    {
        "message": "PV generation initiated",
        "pv_id": "uuid",
        "status": "in_progress"
    }
    ```

### 5.2. Get PV by ID
- **Endpoint**: `/api/v1/pv/{pv_id}`
- **Method**: `GET`
- **Description**: Retrieves the generated PV content.
- **Response (200 OK)**:
    ```json
    {
        "id": "uuid",
        "meeting_id": "uuid",
        "content": "Full PV content in Markdown/HTML format.",
        "status": "generated",
        "actions": [
            {"id": "uuid", "description": "Action item 1", "assigned_to": "user_id"},
            ...
        ]
    }
    ```

### 5.3. Validate PV
- **Endpoint**: `/api/v1/pv/{pv_id}/validate`
- **Method**: `POST`
- **Description**: Marks a PV as validated.
- **Response (200 OK)**:
    ```json
    {
        "message": "PV validated successfully",
        "status": "validated"
    }
    ```

## 6. Actions (`/api/v1/actions`)

### 6.1. Create Action Item
- **Endpoint**: `/api/v1/actions/`
- **Method**: `POST`
- **Description**: Manually creates a new action item.
- **Request Body**:
    ```json
    {
        "meeting_id": "uuid",
        "description": "Follow up with client X.",
        "assigned_to": "user_id",
        "due_date": "2026-03-05T17:00:00Z",
        "priority": "high"
    }
    ```
- **Response (201 Created)**:
    ```json
    {
        "id": "uuid",
        "meeting_id": "uuid",
        "description": "Follow up with client X.",
        "assigned_to": "user_id",
        "status": "open"
    }
    ```

### 6.2. Get Action by ID
- **Endpoint**: `/api/v1/actions/{action_id}`
- **Method**: `GET`
- **Description**: Retrieves details of a specific action item.
- **Response (200 OK)**: Returns an `Action` object.

### 6.3. Update Action Status
- **Endpoint**: `/api/v1/actions/{action_id}/status`
- **Method**: `PATCH`
- **Description**: Updates the status of an action item. The status must be one of the allowed `ActionStatus` enum values.
- **Request Body**:
    ```json
    {
        "status": "completed"
    }
    ```
- **Allowed status values** (case-sensitive):
    - `PENDING`
    - `IN_PROGRESS`
    - `COMPLETED`
    - `CANCELLED`
    - `OVERDUE`
- **Response (200 OK)**:
    ```json
    {
        "id": "uuid",
        "title": "Action title",
        "status": "COMPLETED",
        ...
    }
    ```
- **Error Responses**:
    - `400 Bad Request`: If the provided status is not one of the allowed enum values.
    - `404 Not Found`: If the action does not exist or does not belong to the user's client.
- **Side Effects**: On successful update, a notification webhook is sent to `N8N_WEBHOOK_URL` with the event `action.status_updated`, enabling downstream automation (e.g., manager alerts, WhatsApp reminders).

### 6.4. List Actions
- **Endpoint**: `/api/v1/actions/`
- **Method**: `GET`
- **Description**: Retrieves a list of action items, with optional filters.
- **Query Parameters**: `skip` (int), `limit` (int), `status` (str), `assigned_to` (uuid), `meeting_id` (uuid)
- **Response (200 OK)**:
    ```json
    [
        {
            "id": "uuid",
            "description": "Follow up with client X.",
            "status": "open"
        }
    ]
    ```

## 7. Reports (`/api/v1/reports`)

### 7.1. Generate Dashboard Data
- **Endpoint**: `/api/v1/reports/dashboard/{role}`
- **Method**: `GET`
- **Description**: Generates data for role-specific dashboards (DG, Manager, Participant). Includes strict RBAC filtering (DG sees tenant-wide data, Manager sees only team data).
- **Path Parameter**: `role` (str: "dg", "manager", "participant")
- **Response (200 OK)**: Returns a JSON object containing relevant metrics, dynamic trends, and audit logs.
    ```json
    {
        "meeting_stats": {
            "total": 150,
            "completed": 120,
            "scheduled": 20,
            "cancelled": 10
        },
        "action_stats": {
            "completed": 70,
            "overdue": 5,
            "pending": 25
        },
        "team_productivity": [
            {
                "user_id": "uuid",
                "name": "Sami Ben Ali",
                "completed": 10,
                "overdue": 0,
                "pending": 2
            }
        ],
        "kpi_trends": {
            "meetings": { "percent": 15.5, "direction": "up" },
            "completion_rate": { "percent": 2.0, "direction": "down" }
        },
        "recent_audit_logs": [
            {
                "id": "uuid",
                "action": "POST",
                "table_name": "meetings",
                "timestamp": "2026-03-31T14:00:22Z",
                "user_id": "uuid"
            }
        ],
        "system_health": {
            "api": "healthy",
            "ai": "healthy",
            "storage": "healthy"
        },
        "upcoming_meetings_list": [],
        "open_actions_list": [],
        "team_members_count": 5,
        "total_meetings": 150,
        "client_usage": {
            "period": "2026-03",
            "minutes_used": 120,
            "minutes_included": 1000,
            "remaining": 880,
            "next_billing_date": "April 26, 2026"
        }
    }
    ```

### 7.2. Generate Export Report (PLANNED — NOT IMPLEMENTED)
- **Endpoint**: `/api/v1/reports/export`
- **Method**: `GET`
- **Description**: Generates a comprehensive report in a specified format (e.g., PDF, Excel).
- **Status**: Not implemented in backend/app/api/v1/reports.py
- **Query Parameters**: `format` (str: "pdf", "xlsx"), `meeting_id` (uuid, optional), `start_date` (date, optional), `end_date` (date, optional)
- **Response (200 OK)**: Returns the generated report file.
    - `Content-Type: application/pdf` for PDF.
    - `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` for XLSX.