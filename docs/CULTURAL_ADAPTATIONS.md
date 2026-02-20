# Cultural Adaptations for Meeting Automation System in Tunisia/Maghreb

This document details the cultural adaptations and localized features implemented in the Meeting Automation System to better serve the Tunisia/Maghreb markets. These adaptations aim to enhance user experience, improve efficiency, and ensure compliance with local communication norms.

## 1. Multilingual Support

The system provides comprehensive multilingual support, acknowledging the linguistic diversity of the region.

### 1.1. Supported Languages
- **Arabic (ar-TN)**: Tunisian Arabic, including dialectal nuances in transcription and UI.
- **Arabic (ar-MSA)**: Modern Standard Arabic, for formal documentation and reporting.
- **French (fr-TN)**: Tunisian French, reflecting common usage.
- **English (en)**: Standard English for international users and technical documentation.

### 1.2. Code-Switching in Transcription
- **Feature**: The AI transcription service (Whisper) is specifically trained and configured to handle code-switching between Arabic, French, and English, which is a common linguistic phenomenon in the Maghreb region. This ensures accurate transcription of conversations that mix languages.

### 1.3. UI Localization (i18n)
- **Framework**: `react-i18next` is used in the frontend for robust internationalization.
- **Translation Files**: Dedicated JSON files (`ar-TN.json`, `fr-TN.json`, `en.json`) store UI translations.
- **Dynamic Content**: Backend APIs return localized content where appropriate, or provide keys for frontend translation.

## 2. Right-to-Left (RTL) Layout Support

Recognizing that Arabic is a Right-to-Left language, the frontend is designed to adapt its layout accordingly.

### 2.1. Dynamic RTL Switching
- **Implementation**: The frontend utilizes `useRTL.ts` hook and `RTLLayout.tsx` component to dynamically switch between LTR (Left-to-Right) and RTL layouts based on the selected language.
- **Material-UI Integration**: Material-UI's theming capabilities are extended to support RTL, ensuring components render correctly.
- **CSS Overrides**: `rtl.css` contains specific CSS rules to adjust alignment, spacing, and component flow for RTL languages.

## 3. Cultural Calendar and Date Formatting

Dates and times are presented in formats familiar to the local users, and cultural calendar considerations are taken into account.

### 3.1. Hijri Calendar Integration
- **Feature**: The `useCulturalCalendar.ts` hook provides utilities for displaying dates in both Gregorian and Hijri (Islamic) calendars, which is culturally significant in Tunisia.
- **Date Formatting**: The `dateFormatter.ts` utility handles formatting dates and times according to local conventions (e.g., `DD/MM/YYYY`, `HH:mm`, Arabic numerals).

## 4. WhatsApp Integration for Notifications and Action Tracking

WhatsApp is a primary communication channel in Tunisia, and the system leverages this for effective user engagement.

### 4.1. High Open Rate Strategy
- **Justification**: WhatsApp boasts a significantly higher open rate (around 90% in Tunisia) compared to traditional email, making it an ideal channel for critical notifications.
- **Use Cases**:
    - **Meeting Reminders**: Sending automated reminders for upcoming meetings.
    - **Action Item Notifications**: Notifying users when an action item is assigned to them or its status changes.
    - **PV Distribution**: Sending links to generated or validated PVs.
    - **Custom Alerts**: Workflow-driven alerts for specific events (e.g., recording uploaded, transcription completed).

### 4.2. n8n Workflows
- **Automation**: `n8n` is used to orchestrate WhatsApp messages, integrating with the WhatsApp Business API.
- **Workflow Examples**:
    - `daily-reminders.json`: Sends daily summaries or reminders via WhatsApp.
    - Workflows linked to `meeting-created.json`, `audio-uploaded.json`, and `pv-validated.json` can be extended to include WhatsApp notifications.

## 5. Optimized AI Models

AI models are specifically chosen and, where necessary, fine-tuned for regional linguistic characteristics.

### 5.1. Whisper for Multilingual Transcription
- **Optimization**: The Whisper model is robust for transcribing mixed-language audio, which is crucial for the Maghreb context.

### 5.2. Mistral for Arabic NLP
- **Model Choice**: Mistral 7B Arabic is used for natural language processing tasks, particularly for generating PVs. This model is chosen for its strong performance in understanding and generating Arabic text, including regional variations.

## 6. Regulatory and Compliance Considerations

While ISO 27001 provides a global security framework, local data protection regulations (e.g., related to personal data processing) are also considered.

### 6.1. Data Residency
- **Requirement**: (To be defined based on specific local regulations and client requirements regarding where data must be stored).

### 6.2. Privacy by Design
- **Principle**: The system is designed with privacy in mind, adhering to principles of data minimization and purpose limitation for personal and sensitive information.