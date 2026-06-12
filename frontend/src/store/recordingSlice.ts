import { createSlice, PayloadAction } from "@reduxjs/toolkit";

export type RecordingStatus = "idle" | "recording" | "paused" | "processing" | "completed" | "failed";

export interface TranscriptionSegment {
  speaker: string;
  text: string;
  start?: number;
  end?: number;
  timestamp?: string;
  participantId?: string;
  name?: string;
}

export interface SpeakingStats {
  participantId?: string;
  name?: string;
  speaker?: string;
  duration: number;
  percentage: number;
}

export interface AIInsight {
  type?: string;
  topic?: string;
  content?: string;
  confidence: number;
  actions: any[];
}

export interface ActionSuggestion {
  id: string;
  title?: string;
  description: string;
  suggested_assignee?: string;
  assignee_name?: string;
  priority: string;
  status: string;
  confidence_score?: number;
}

export interface RecordingState {
  status: RecordingStatus;
  isRecording: boolean;
  duration: number;
  recordingId: string | null;
  egressId: string | null;
  transcription: TranscriptionSegment[];
  speakingStats: SpeakingStats[];
  aiInsights: AIInsight[];
  suggestions: ActionSuggestion[];
  pvId: string | null;
}

const initialState: RecordingState = {
  status: "idle",
  isRecording: false,
  duration: 0,
  recordingId: null,
  egressId: null,
  transcription: [],
  speakingStats: [],
  aiInsights: [],
  suggestions: [],
  pvId: null,
};

const recordingSlice = createSlice({
  name: "recording",
  initialState,
  reducers: {
    setStatus(state, action: PayloadAction<RecordingStatus>) {
      state.status = action.payload;
      state.isRecording = action.payload === "recording";
    },
    setRecordingId(state, action: PayloadAction<string | null>) {
      state.recordingId = action.payload;
    },
    setEgressId(state, action: PayloadAction<string | null>) {
      state.egressId = action.payload;
    },
    setDuration(state, action: PayloadAction<number>) {
      state.duration = action.payload;
    },
    setTranscription(state, action: PayloadAction<TranscriptionSegment[]>) {
      state.transcription = action.payload;
    },
    setSpeakingStats(state, action: PayloadAction<SpeakingStats[]>) {
      state.speakingStats = action.payload;
    },
    setAiInsights(state, action: PayloadAction<AIInsight[]>) {
      state.aiInsights = action.payload;
    },
    setSuggestions(state, action: PayloadAction<ActionSuggestion[]>) {
      state.suggestions = action.payload;
    },
    setPvId(state, action: PayloadAction<string | null>) {
      state.pvId = action.payload;
    },
    resetRecording() {
      return initialState;
    },
  },
});

export const {
  setStatus,
  setRecordingId,
  setEgressId,
  setDuration,
  setTranscription,
  setSpeakingStats,
  setAiInsights,
  setSuggestions,
  setPvId,
  resetRecording,
} = recordingSlice.actions;

export default recordingSlice.reducer;
