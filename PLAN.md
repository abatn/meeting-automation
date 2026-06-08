# Plan: Integrate Enhanced UI with Edit Online/PDF/Word Button

## Current State
- The `MeetingRoom.tsx` already uses LiveKit components (LiveKitRoom, ControlBar, useParticipants).
- The UI has a three-column layout: left (participants/controls), middle (transcription), right (insights/actions).
- Edit functionality exists elsewhere (MeetingPlanner.tsx, PVValidator.tsx) but not in the main meeting room.
- Backend has OnlyOffice integration and editing capabilities (routes, editor component).

## Plan Overview
Enhance the MeetingRoom.tsx with:
1. Professional UI improvements using LiveKit/agents-ui patterns
2. Pipeline progress indicator
3. Edit online/PDF/word button group (conditional on PV completion)

## Implementation Steps

### 1. Add Pipeline Progress Indicator
- Place above the three-column grid
- Show stages: [● Recording] → [● Transcribing] → [○ Speaker-ID] → [○ PV/Actions]
- Update based on `recordingStatus` from backend:
  - recording: "recording" → Transcribing stage active
  - processing: "processing" → Speaker-ID stage active
  - completed: "completed" → PV/Actions stage active

### 2. Enhance UI Components
**Left Column:**
- Replace custom ParticipantsList with LiveKit's `ParticipantTile` grid via `useParticipants`
- Enhance recording controls: `ControlBar` (mic only) + custom status banner with pulsing indicator
- Improve SpeakingStatsPanel: use `ParticipantTile` for avatars, keep current bar chart

**Middle Column:**
- Implement AgentChatTranscript-inspired display:
  - Speaker avatar/initial left-aligned
  - Message bubble right-aligned with speaker label
  - Timestamps on hover/message menu
  - Auto-scroll to latest
- Enhanced loading: typing indicator + "Transcribing audio..."
- Improved empty state: illustrative graphic + guidance text

**Right Column:**
- Redesign AI Insights as card-based layout with topic header, confidence badge, indented actions
- Enhance Action Suggestions with assignee avatar/name, priority chips, feedback tooltips
- Add refresh button + "Last updated" timestamp

### 3. Add Edit Button Group
**Location:** Right column header (above AI Insights) or as a separate section in right column
**Visibility:** Conditional on PV completion (recordingStatus === "completed" && PV available)
**Button Group:**
- Edit Online: Opens OnlyOffice editor in new tab (`/editor/{pvId}`)
- Edit PDF: Generates/downloads annotated PDF with edits
- Edit Word: Generates/downloads .docx for editing
**State Handling:**
- Fetch PV ID for meeting via new/existing endpoint (e.g., `/meetings/{id}/pv`)
- Store PV ID in component state
- Check backend for edited document availability (Optional: show "Edited" badge)

### 4. Technical Details
- **Data Flow:** 
  - Use existing `/meetings/{id}/ai-insights` polling for insights/actions
  - Add PV fetch: `/meetings/{id}/pv` returning `{ id, title, status, edited_document_url }`
  - Or extend ai-insights endpoint to include PV data
- **Editing:**
  - Edit Online: `window.open(`/editor/${pvId}`, '_blank')`
  - Edit PDF/Word: Generate via backend endpoints (existing PDF generation, DOCX export)
- **Permissions:** Check user role/user_id from JWT against PV meeting's creator/participants
- **Fallback:** If no PV exists, show disabled button with tooltip

### 5. Risk Mitigation
- **Backward Compatibility:** Keep existing components as fallback during transition
- **Feature Flags:** Use env var (REACT_APP_EDIT_BUTTONS) to toggle new UI
- **Incremental Rollout:** Implement UI enhancements first, then edit buttons
- **Graceful Degradation:** Ensure core meeting functionality works if UI enhancements fail

### 6. Expected Outcome
- Professional, cohesive appearance using LiveKit design patterns
- Clear pipeline visualization and speaker attribution
- Functional edit capabilities across all three formats
- Maintained performance and zero regressions in core workflow
- Improved user engagement with actionable insights

## Files to Modify
- `frontend/src/components/meetings/MeetingRoom.tsx` (primary)
- Potential backend endpoint additions (if needed for PV fetch)
- No new technology stacks - uses existing LiveKit Components React, MUI, Redux, Vite

## Dependencies (Already Present)
- @livekit/components-react
- @livekit/components-styles
- MUI, Redux Toolkit, React-i18next, Axios
- OnlyOfficeEditor (existing)

## Notes
- All changes within existing technology stack constraints
- Plan based on analysis of current codebase and LiveKit documentation
- Edit button placement and visibility to be finalized during implementation