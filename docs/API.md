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

### 1.4. MFA Setup
- **Endpoint**: `/api/v1/auth/mfa/setup`
- **Method**: `POST`
- **Description**: Initiates MFA setup for the authenticated user, returning a QR code URI.
- **Response (200 OK)**:
    ```json
    {
        "otp_uri": "otpauth://totp/...",
        "qr_code_image": "base64_encoded_png_image"
    }
    ```

### 1.5. MFA Verify
- **Endpoint**: `/api/v1/auth/mfa/verify`
- **Method**: `POST`
- **Description**: Verifies the MFA token provided by the user to enable MFA.
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

## 3. Recordings (`/api/v1/recordings`)

### 3.1. Upload Recording
- **Endpoint**: `/api/v1/recordings/upload`
- **Method**: `POST`
- **Description**: Uploads an audio/video recording file for a specific meeting.
- **Request Body**: `multipart/form-data` with `file` (audio/video file) and `meeting_id`.
- **Response (201 Created)**:
    ```json
    {
        "id": "uuid",
        "meeting_id": "uuid",
        "file_url": "s3_file_url",
        "status": "uploaded"
    }
    ```

### 3.2. Get Recording by ID
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
- **Endpoint**: `/api/v1/transcriptions/{transcription_id}`
- **Method**: `GET`
- **Description**: Retrieves the full transcription text for a recording.
- **Response (200 OK)**:
    ```json
    {
        "id": "uuid",
        "recording_id": "uuid",
        "language": "ar-TN",
        "text": "The full transcribed text...",
        "status": "completed"
    }
    ```

## 5. Procès-Verbaux (PV) (`/api/v1/pv`)

### 5.1. Generate PV
- **Endpoint**: `/api/v1/pv/generate`
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
- **Description**: Updates the status of an action item.
- **Request Body**:
    ```json
    {
        "status": "completed"
    }
    ```
- **Response (200 OK)**:
    ```json
    {
        "id": "uuid",
        "status": "completed"
    }
    ```

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
- **Description**: Generates data for role-specific dashboards (DG, Manager, Participant).
- **Path Parameter**: `role` (str: "dg", "manager", "participant")
- **Response (200 OK)**: Returns a JSON object containing relevant metrics and data for the specified role's dashboard.
    ```json
    {
        "total_meetings": 150,
        "completed_meetings": 120,
        "pending_actions": 30,
        "meetings_by_month": {"Jan": 10, "Feb": 15},
        "action_status_distribution": {"open": 20, "in_progress": 10, "completed": 70}
    }
    ```

### 7.2. Generate Export Report
- **Endpoint**: `/api/v1/reports/export`
- **Method**: `GET`
- **Description**: Generates a comprehensive report in a specified format (e.g., PDF, Excel).
- **Query Parameters**: `format` (str: "pdf", "xlsx"), `meeting_id` (uuid, optional), `start_date` (date, optional), `end_date` (date, optional)
- **Response (200 OK)**: Returns the generated report file.
    - `Content-Type: application/pdf` for PDF.
    - `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` for XLSX.