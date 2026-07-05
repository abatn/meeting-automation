import React, { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Box,
  Grid,
  Typography,
  Stack,
  Button,
  CircularProgress,
  alpha,
  Paper,
  Avatar,
  Chip,
  LinearProgress,
  Tooltip,
  Skeleton,
  IconButton,
  Badge,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  useTheme,
  FormControl,
  InputLabel,
  Select,
  SelectChangeEvent,
} from "@mui/material";
import {
  AutoFixHigh as SuggestionIcon,
  MicOff as MicOffIcon,
  Mic as MicIcon,
  AccessTime as AccessTimeIcon,
  Group as GroupIcon,
  SmartToy as SmartToyIcon,
  TextSnippet as TextSnippetIcon,
  FiberManualRecord as RecordIcon,
  Person as PersonIcon,
  CheckCircle as CheckIcon,
  CheckCircleOutline as ApproveIcon,
  RadioButtonChecked as LiveIcon,
  VolumeUp as VolumeIcon,
  Stop as StopIcon,
  Pause as PauseIcon,
  PlayArrow as ResumeIcon,
  CallEnd as LeaveIcon,
  Edit as EditIcon,
  PictureAsPdf as PdfIcon,
  Description as WordIcon,
  Timeline as TimelineIcon,
  SpeakerNotes as SpeakerNotesIcon,
  Assignment as AssignmentIcon,
} from "@mui/icons-material";
import { Theme } from "@mui/material/styles";
import { LiveKitRoom, RoomAudioRenderer, useParticipants, useRoomInfo, useConnectionState, useLocalParticipant, useDisconnectButton } from "@livekit/components-react";
import "@livekit/components-styles";
import { ConnectionState, ConnectionQuality, RoomEvent } from "livekit-client";
import { useTranslation } from "react-i18next";
import { useSelector } from "react-redux";
import { meetingsApi } from "../../services/meetings";
import { RootState } from "../../store";
import { animations } from "../../styles/animations";
import { speakerColor, speakerInitial, formatDuration } from "../../utils/speakerUtils";

// ─── Design Tokens (theme-derived) ─────────────────────────────────────────
const PURPLE = "#8B5CF6";

function buildColor(theme: Theme) {
  return {
    primary:   theme.palette.primary.main,
    success:   theme.palette.success.main,
    warning:   theme.palette.warning.main,
    error:     theme.palette.error.main,
    purple:    PURPLE,
    bg:        theme.palette.background.default,
    card:      theme.palette.background.paper,
    border:    theme.palette.divider,
    textMuted: theme.palette.text.secondary,
  };
}

type ColorTokens = ReturnType<typeof buildColor>;

// ─── Interfaces ───────────────────────────────────────────────────────────────
interface MeetingInfo {
  id: string;
  title: string;
  topic?: string;
  organizer?: string;
  scheduled_at?: string;
  status?: string;
}

interface ActionSuggestion {
  id: string;
  title: string;
  description: string;
  suggested_assignee: string | null;
  priority?: "high" | "medium" | "low";
  status: "suggested" | "accepted" | "rejected";
}

interface TranscriptionSegment {
  speaker: string;
  text: string;
  start?: number;
  end?: number;
  timestamp?: string;
}

interface SpeakingStats {
  participantId: string;
  name: string;
  duration: number;
  percentage: number;
}

interface AIInsight {
  topic: string;
  confidence: number;
  actions: string[];
}

function priorityColor(priority: string | undefined, COLOR: ColorTokens): string {
  if (priority === "high")   return COLOR.error;
  if (priority === "medium") return COLOR.warning;
  return COLOR.success;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function ParticipantsList() {
  const theme = useTheme();
  const COLOR = buildColor(theme);
  const participants = useParticipants();
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();
  const { t } = useTranslation();
  if (participants.length === 0) {
    return (
      <Stack alignItems="center" spacing={1.5} sx={{ py: 2.5, color: COLOR.textMuted }}>
        <GroupIcon sx={{ fontSize: 32, color: alpha("#000", 0.08) }} />
        <Typography sx={{ fontSize: 13, textAlign: "center" }}>
          {t("meeting_assistant.no_participants")}
        </Typography>
      </Stack>
    );
  }
  return (
    <Stack spacing={0.75} sx={{ px: 0.5 }}>
      {participants.map((p) => (
        <Box
          key={p.identity}
          sx={{
            display: "flex", alignItems: "center", gap: 1.25, px: 1.5, py: 1.25,
            borderRadius: 2.5,
            bgcolor: p.isSpeaking ? alpha(COLOR.success, 0.06) : alpha("#000", 0.01),
            border: p.isSpeaking ? `1px solid ${alpha(COLOR.success, 0.2)}` : "1px solid transparent",
            transition: "all 0.2s ease",
            "&:hover": { bgcolor: alpha(COLOR.primary, 0.04) },
          }}
        >
          <Box sx={{ position: "relative", flexShrink: 0 }}>
            <Avatar sx={{
              width: 32, height: 32, fontSize: 13, fontWeight: 600,
              bgcolor: speakerColor(p.name || p.identity),
              boxShadow: p.isSpeaking ? `0 0 0 3px ${alpha(COLOR.success, 0.25)}` : "none",
              transition: "box-shadow 0.2s",
            }}>
              {speakerInitial(p.name || p.identity)}
            </Avatar>
            {p.isSpeaking && (
              <Box sx={{
                position: "absolute", bottom: -2, right: -2,
                width: 12, height: 12, borderRadius: "50%",
                bgcolor: COLOR.success, border: "2px solid #fff",
                animation: "pulse-opacity 1s infinite",
              }} />
            )}
          </Box>
           <Box sx={{ flexGrow: 1, minWidth: 0 }}>
             <Typography sx={{
               fontSize: 13, fontWeight: p.isSpeaking ? 600 : 500,
               color: p.isSpeaking ? COLOR.success : "text.primary",
               overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
             }}>
               {p.name || p.identity}
             </Typography>
             {p.isSpeaking && (
               <Stack direction="row" alignItems="center" spacing={0.5} sx={{ mt: 0.25 }}>
                 {[0, 1, 2].map((i) => (
                   <Box
                     key={i}
                     sx={{
                       width: 3, height: 8, borderRadius: 1.5,
                       bgcolor: COLOR.success,
                       animation: `wave 0.8s ease-in-out ${i * 0.15}s infinite`,
                     }}
                   />
                 ))}
                 <Typography sx={{ fontSize: 10, color: COLOR.success, fontWeight: 500 }}>
                   {t("meeting_assistant.participant_speaking")}
                 </Typography>
               </Stack>
             )}
           </Box>
           <Stack direction="row" alignItems="center" spacing={0.75} sx={{ flexShrink: 0 }}>
             {p.isLocal ? (
               <Tooltip title={isMicrophoneEnabled ? t("meeting_assistant.mic_mute") : t("meeting_assistant.mic_unmute")}>
                 <IconButton
                   size="small"
                   aria-label={isMicrophoneEnabled ? t("meeting_assistant.mic_mute") : t("meeting_assistant.mic_unmute")}
                   onClick={() => localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled)}
                   sx={{
                     p: 0.25,
                     color: isMicrophoneEnabled ? COLOR.success : COLOR.error,
                     "&:focus-visible": { outline: `2px solid ${COLOR.primary}`, outlineOffset: 2 },
                   }}
                 >
                   {isMicrophoneEnabled
                     ? <MicIcon sx={{ fontSize: 14 }} />
                     : <MicOffIcon sx={{ fontSize: 14 }} />}
                 </IconButton>
               </Tooltip>
             ) : (
               p.isMicrophoneEnabled ? (
                 <Tooltip title={t("meeting_assistant.mic_on", "Mic On")}>
                   <MicIcon sx={{ fontSize: 14, color: COLOR.success }} />
                 </Tooltip>
               ) : (
                 <Tooltip title={t("meeting_assistant.mic_muted", "Mic Muted")}>
                   <MicOffIcon sx={{ fontSize: 14, color: COLOR.textMuted }} />
                 </Tooltip>
               )
             )}
             {p.isSpeaking && (
               <VolumeIcon sx={{ fontSize: 16, color: COLOR.success }} />
             )}
           </Stack>
        </Box>
      ))}
    </Stack>
  );
}

function LiveKitConnectionBridge({ onStateChange }: { onStateChange: (state: ConnectionState) => void }) {
  const connectionState = useConnectionState();

  useEffect(() => {
    onStateChange(connectionState);
  }, [connectionState, onStateChange]);

  return null;
}

function LiveKitDisconnectBridge({ onReady }: { onReady: (fn: () => void) => void }) {
  const { buttonProps } = useDisconnectButton({});
  useEffect(() => {
    onReady(buttonProps.onClick);
  }, [buttonProps.onClick, onReady]);
  return null;
}

function MicToggleBridge({
  onMicState,
}: {
  onMicState: (enabled: boolean, toggle: () => void) => void;
}) {
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();
  const toggle = useCallback(() => {
    localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled);
  }, [localParticipant, isMicrophoneEnabled]);
  useEffect(() => {
    onMicState(isMicrophoneEnabled, toggle);
  }, [isMicrophoneEnabled, toggle, onMicState]);
  return null;
}


// ─── Pipeline Progress Indicator ─────────────────────────────────────────────
function PipelineProgressIndicator({ status }: { status: string }) {
  const theme = useTheme();
  const COLOR = buildColor(theme);
  const stages = [
    { key: "recording", label: "Recording", icon: <RecordIcon sx={{ fontSize: 14 }} /> },
    { key: "transcribing", label: "Transcription", icon: <TextSnippetIcon sx={{ fontSize: 14 }} /> },
    { key: "speaker_id", label: "Speaker-ID", icon: <SpeakerNotesIcon sx={{ fontSize: 14 }} /> },
    { key: "completed", label: "PV + Actions", icon: <AssignmentIcon sx={{ fontSize: 14 }} /> },
  ];

  const getStageStatus = (stageKey: string) => {
    const order = ["idle", "recording", "transcribing", "processing", "completed", "failed"];
    const currentIdx = order.indexOf(status);
    const stageIdx = order.indexOf(stageKey === "speaker_id" ? "processing" : stageKey);
    if (status === "failed") return "error";
    if (stageIdx < currentIdx) return "completed";
    if (stageIdx === currentIdx) return "active";
    return "pending";
  };

  return (
    <Paper
      elevation={0}
      sx={{
        p: { xs: 1.5, md: 2 }, mb: 2.5, borderRadius: 3,
        border: `1px solid ${COLOR.border}`,
        background: `linear-gradient(135deg, ${alpha(COLOR.primary, 0.02)} 0%, ${alpha(COLOR.purple, 0.02)} 100%)`,
      }}
    >
      <Stack direction="row" alignItems="center" justifyContent="center" spacing={{ xs: 1, md: 2 }} flexWrap="wrap">
        <TimelineIcon sx={{ fontSize: 16, color: COLOR.textMuted, mr: 1 }} />
        {stages.map((stage, idx) => {
          const stageStatus = getStageStatus(stage.key);
          const isCompleted = stageStatus === "completed";
          const isActive = stageStatus === "active";
          const isError = stageStatus === "error";

          return (
            <React.Fragment key={stage.key}>
              {idx > 0 && (
                <Box
                  sx={{
                    width: { xs: 16, md: 24 },
                    height: 2,
                    bgcolor: isCompleted ? COLOR.success : alpha(COLOR.border, 0.5),
                    borderRadius: 1,
                  }}
                />
              )}
              <Stack
                direction="row"
                alignItems="center"
                spacing={0.75}
                sx={{
                  px: 1.5,
                  py: 0.75,
                  borderRadius: 2,
                  bgcolor: isActive ? alpha(COLOR.primary, 0.08) : "transparent",
                  border: isActive ? `1px solid ${alpha(COLOR.primary, 0.2)}` : "1px solid transparent",
                  transition: "all 0.2s",
                }}
              >
                <Box
                  sx={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    bgcolor: isCompleted ? COLOR.success : isActive ? COLOR.primary : isError ? COLOR.error : COLOR.border,
                    border: isCompleted || isActive ? "none" : `1px solid ${COLOR.textMuted}`,
                    animation: isActive ? "pulse 1.5s infinite" : "none",
                  }}
                />
                {isCompleted ? (
                  <CheckIcon sx={{ fontSize: 14, color: COLOR.success, ml: -0.5 }} />
                ) : (
                  <Box sx={{ color: isActive ? COLOR.primary : COLOR.textMuted, display: "flex" }}>
                    {stage.icon}
                  </Box>
                )}
                <Typography
                  sx={{
                    fontSize: { xs: 11, md: 12 },
                    fontWeight: isActive ? 700 : 500,
                    color: isCompleted ? COLOR.success : isActive ? COLOR.primary : COLOR.textMuted,
                  }}
                >
                  {stage.label}
                </Typography>
              </Stack>
            </React.Fragment>
          );
        })}
      </Stack>
    </Paper>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
const MeetingRoom: React.FC = () => {
  const theme = useTheme();
  const COLOR = buildColor(theme);
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const currentUser = useSelector((state: RootState) => state.auth.user);

  // Meeting info
  const [meetingInfo, setMeetingInfo] = useState<MeetingInfo | null>(null);
  const [meetingCreatorId, setMeetingCreatorId] = useState<string>("");

  // LiveKit
  const [livekitToken, setLivekitToken] = useState<string | null>(null);
  const [livekitUrl, setLivekitUrl]     = useState<string>("");
  const [livekitConnectionState, setLivekitConnectionState] = useState<ConnectionState>(ConnectionState.Disconnected);
  const [livekitConnected, setLivekitConnected]             = useState(false);
const [livekitError, setLivekitError] = useState<string | null>(null);

   // Room stabilization (for clean Egress recording start)
   const [roomConnectionReady, setRoomConnectionReady] = useState(false);
   const [isStarting, setIsStarting] = useState(false);

   // Recording
  const [isRecording, setIsRecording]             = useState(false);
  const [recordingStatus, setRecordingStatus]     = useState<"idle" | "recording" | "paused" | "processing" | "stopped" | "completed" | "failed">("idle");
  const [isSyncing, setIsSyncing]                 = useState(true);  // true until first syncFromBackend completes
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [recordingId, setRecordingId]             = useState<string | null>(null);
  const [egressId, setEgressId]                   = useState<string | null>(null);

  // Timers
  const [meetingDuration, setMeetingDuration] = useState(0);
  const [startTime]                           = useState<Date>(new Date());

  // Real data from APIs — NO MOCKS
  const [speakingStats, setSpeakingStats]       = useState<SpeakingStats[]>([]);
  const [liveTranscription, setLiveTranscription] = useState<TranscriptionSegment[]>([]);
  const [aiInsights, setAiInsights]             = useState<AIInsight[]>([]);
  const [suggestions, setSuggestions]           = useState<ActionSuggestion[]>([]);
  const [insightsLoading, setInsightsLoading]   = useState(false);
  const [pvId, setPvId]                         = useState<string | null>(null);
  const [isValidated, setIsValidated]           = useState(false);
  const [isApproving, setIsApproving]           = useState(false);
  const [editMenuAnchor, setEditMenuAnchor]     = useState<null | HTMLElement>(null);
  const [exportLanguage, setExportLanguage]     = useState<string>(i18n.language.split("-")[0] || "fr");

  // Mic state (propagated from inside LiveKitRoom via MicToggleBridge)
  const [micEnabled, setMicEnabled] = useState(true);
  const micToggleRef = useRef<(() => void) | null>(null);

  const handleMicState = useCallback((enabled: boolean, toggle: () => void) => {
    setMicEnabled(enabled);
    micToggleRef.current = toggle;
  }, []);

  const handleMicToggle = useCallback(() => {
    if (micToggleRef.current) micToggleRef.current();
  }, []);

  // Refs
  const transcriptionEndRef = useRef<HTMLDivElement>(null);
  const pollingRef          = useRef<NodeJS.Timeout | null>(null);

  const handleLiveKitConnectionState = useCallback((state: ConnectionState) => {
    const connected = state === ConnectionState.Connected;

    setLivekitConnectionState(state);
    setLivekitConnected(connected);

    if (connected) {
      setLivekitError(null);
    }
  }, []);

  // ── DIAGNOSTIC: Log all recordingStatus changes with stack trace ──────────
  useEffect(() => {
    console.log("[State] recordingStatus changed to:", recordingStatus, "\nstack:", new Error().stack?.split('\n').slice(1, 4).join(' <- '));
  }, [recordingStatus]);

  // ── State Reset bei Meeting-Wechsel ─────────────────────────────────────
  useEffect(() => {
    setIsSyncing(true);
    setRecordingId(null);
    setEgressId(null);
    setIsRecording(false);
    setRecordingDuration(0);
    setMeetingDuration(0);
    setLiveTranscription([]);
    setAiInsights([]);
    setSuggestions([]);
    setPvId(null);
    setIsValidated(false);
    setIsApproving(false);
    setLivekitToken(null);
    setLivekitError(null);
    setLivekitConnected(false);
    setLivekitConnectionState(ConnectionState.Disconnected);
    setMeetingInfo(null);
  }, [id]);

  // ── Fetch meeting info + token on mount ──────────────────────────────────
  useEffect(() => {
    if (!id || !currentUser) return;

    const fetchAll = async () => {
      try {
        const [m, tokenRes] = await Promise.all([
          meetingsApi.getMeeting(id),
          meetingsApi.getLivekitToken(id),
        ]);
        setMeetingInfo({
          id:           m.id,
          title:        m.title || `Meeting #${m.id?.slice(0, 8)}`,
          topic:        m.topic || m.agenda || "",
          organizer:    m.creator_name || m.organizer || "",
          scheduled_at: m.scheduled_at || m.date || "",
          status:       m.status || "",
        });
        setMeetingCreatorId(m.creator_id || "");
        // Support both old and new response formats (backward compatibility)
        const nextLivekitToken = tokenRes.participantToken || tokenRes.token;
        const nextLivekitUrl = tokenRes.serverUrl || tokenRes.server_url;
        console.info("[LiveKit] Token response", {
          serverUrl: nextLivekitUrl,
          hasToken: Boolean(nextLivekitToken),
          tokenPrefix: nextLivekitToken?.slice(0, 12),
        });
        setLivekitToken(nextLivekitToken);
        // TEST-ONLY: Handle both ws:// and wss:// URLs (remove for production)
        // Production: Backend will return correctly formatted URLs
        setLivekitUrl(
          nextLivekitUrl.startsWith('ws://') || nextLivekitUrl.startsWith('wss://')
            ? nextLivekitUrl
            : `ws://${nextLivekitUrl}`
        );
      } catch (err) {
        console.error("Failed to fetch meeting or token", err);
      }
    };

    fetchAll();
  }, [id, currentUser]);

  useEffect(() => {
    const connected = livekitConnectionState === ConnectionState.Connected;
    setLivekitConnected(connected);

    if (connected) {
      setLivekitError(null);
    }
  }, [livekitConnectionState]);

  // ── Fetch suggestions on mount + every 30s ───────────────────────────────
  useEffect(() => {
    if (!id || !currentUser) return;
    const fetchSuggestions = async () => {
      try {
        const lang = i18n.language.split("-")[0] || "fr";
        const data = await meetingsApi.getSuggestions(id, lang);
        if (data) {
          setSuggestions(data.filter((s: ActionSuggestion) => s.status.toLowerCase() === "suggested"));
        }
      } catch { /* no suggestions yet */ }
    };
    fetchSuggestions();
    const iv = setInterval(fetchSuggestions, 30000);
    return () => clearInterval(iv);
  }, [id, i18n.language, currentUser]);

  // ── Tier 4.1: Sync recording state from backend on mount ─────────────────
  // If a recording already exists for this meeting (e.g. user navigates back
  // after the meeting ended), pull its real status and populate the UI with
  // transcription/PV/actions data instead of starting at "idle".
  useEffect(() => {
    if (!id || !currentUser) return;
    const syncFromBackend = async () => {
      try {
        console.log("[Sync] syncFromBackend called, current recordingStatus:", recordingStatus);
        const data = await meetingsApi.getAiInsights(id);
        console.log("[Sync] backend returned:", { status: data?.status, recordingId: data?.recording_id, hasTranscription: !!data?.transcription });

        // Set the state machine to the real backend status
        // Guard: don't overwrite frontend "processing" with stale backend data
        if (data?.status) {
          setRecordingStatus((prev) => {
            if (prev === "processing" && data.status !== "completed" && data.status !== "failed") {
              console.log("[Sync] BLOCKED overwrite:", { prev, attempted: data.status });
              return prev;
            }
            console.log("[Sync] setting recordingStatus:", { from: prev, to: data.status });
            return data.status;
          });
        }
        if (data?.recording_id) {
          setRecordingId(data.recording_id);
        }

        // Populate transcription
        if (data?.transcription?.segments?.length > 0) {
          setLiveTranscription(data.transcription.segments);
        }

        // Populate insights
        if (data?.insights?.length > 0) {
          setAiInsights(data.insights);
        }
      } catch (err) { console.log("[Sync] syncFromBackend error:", err); }
      finally { setIsSyncing(false); }
    };
    syncFromBackend();
  }, [id, currentUser]);

  // ── Meeting duration timer ────────────────────────────────────────────────
  useEffect(() => {
    const iv = setInterval(() => {
      setMeetingDuration(Math.floor((Date.now() - startTime.getTime()) / 1000));
    }, 1000);
    return () => clearInterval(iv);
  }, [startTime]);

  // ── Recording duration timer ──────────────────────────────────────────────
  useEffect(() => {
    let iv: NodeJS.Timeout;
    if (isRecording) {
      iv = setInterval(() => setRecordingDuration((d) => d + 1), 1000);
    }
    return () => clearInterval(iv);
  }, [isRecording]);

  // ── Poll transcription + speaking stats when recording ───────────────────
  const pollTranscriptionData = useCallback(async () => {
    if (!id) return;
    try {
      const data = await meetingsApi.getTranscription(id);
      if (data?.segments?.length > 0) {
        const segs: TranscriptionSegment[] = data.segments.map((s: any) => ({
          speaker:   s.speaker || t("meeting_assistant.unknown_speaker"),
          text:      s.text    || "",
          start:     s.start,
          end:       s.end,
          timestamp: s.start != null
            ? new Date(s.start * 1000).toISOString().substr(11, 8)
            : "",
        }));
        setLiveTranscription(segs);

        // Derive speaking stats from segments
        const durationMap: Record<string, number> = {};
        segs.forEach((s) => {
          const dur = (s.end ?? 0) - (s.start ?? 0);
          durationMap[s.speaker] = (durationMap[s.speaker] || 0) + dur;
        });
        const total = Object.values(durationMap).reduce((a, b) => a + b, 0) || 1;
        const stats: SpeakingStats[] = Object.entries(durationMap).map(([name, dur], idx) => ({
          participantId: String(idx),
          name,
          duration:    Math.round(dur),
          percentage:  Math.round((dur / total) * 100),
        }));
        setSpeakingStats(stats);
      }
    } catch { /* transcription not ready yet */ }
  }, [id, t]);

  // ── Poll AI insights after recording ends ─────────────────────────────────
  // Tier 4.1: Pull real backend status (recording.status, transcription, PV, actions)
  // and stop polling when the pipeline reaches a terminal state.
  const pollAIInsights = useCallback(async () => {
    if (!id) return;
    setInsightsLoading(true);
    try {
      console.log("[Poll] pollAIInsights called");
      const data = await meetingsApi.getAiInsights(id);
      console.log("[Poll] pollAIInsights response:", { status: data?.status, hasTranscription: !!data?.transcription, insightsCount: data?.insights?.length, pvId: data?.pv_id || data?.pv?.id });

      // Update recording status from backend (single source of truth)
      if (data?.status) {
        const next = data.status as "idle" | "recording" | "processing" | "completed" | "failed";
        setRecordingStatus((prev) => {
          // Don't downgrade from a terminal state
          if ((prev === "completed" || prev === "failed") && next !== prev) {
            console.log("[Poll] BLOCKED terminal downgrade:", { prev, attempted: next });
            return prev;
          }
          // Don't overwrite processing/paused with stale data — but allow terminal states through
          if ((prev === "processing" || prev === "paused") && next !== "completed" && next !== "failed") {
            console.log("[Poll] BLOCKED processing/paused overwrite:", { prev, attempted: next });
            return prev;
          }
          console.log("[Poll] pollAIInsights setting recordingStatus:", { from: prev, to: next });
          return next;
        });
      }

      // Populate transcription if backend has it
      if (data?.transcription) {
        setLiveTranscription(data.transcription.segments || []);
      }

      // Populate PV-derived insights
      if (data?.insights?.length > 0) {
        setAiInsights(data.insights);
      }

      // Extract PV ID for edit functionality
      if (data?.pv_id) {
        setPvId(data.pv_id);
      } else if (data?.pv?.id) {
        setPvId(data.pv.id);
      } else if (data?.status === "completed" && !pvId) {
        // Try to fetch PV ID separately if not in insights response
        meetingsApi.getPvByMeeting(id)
          .then((pvData) => {
            if (pvData?.id) setPvId(pvData.id);
          })
          .catch(() => { /* no PV yet */ });
      }

      // Sync validated state from backend
      if (data?.pv?.is_validated || data?.pv?.status === "published") {
        setIsValidated(true);
      }

      // Stop polling on terminal states
      if (data?.status === "completed" || data?.status === "failed") {
        setIsRecording(false);
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
      }
    } catch { /* insights not ready yet */ }
    finally { setInsightsLoading(false); }
  }, [id]);

  // Start/stop polling based on recording state
  useEffect(() => {
    if (isRecording && recordingStatus !== "completed" && recordingStatus !== "failed") {
      console.log("[Poll] START transcription polling, state:", { isRecording, recordingStatus });
      pollingRef.current = setInterval(pollTranscriptionData, 5000);
    } else if (recordingStatus === "processing") {
      console.log("[Poll] START AI insights polling, state:", { isRecording, recordingStatus });
      pollingRef.current = setInterval(pollAIInsights, 8000);
    } else {
      console.log("[Poll] STOP polling, state:", { isRecording, recordingStatus });
      if (pollingRef.current) clearInterval(pollingRef.current);
    }
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [isRecording, recordingStatus, pollTranscriptionData, pollAIInsights]);

  // Auto-scroll transcription
  useEffect(() => {
    transcriptionEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [liveTranscription]);

  // ── Handlers ─────────────────────────────────────────────────────────────
  const handleStartRecording = async () => {
    console.log("[Recording] handleStartRecording called, id:", id, "isStarting:", isStarting, "livekitConnectionState:", livekitConnectionState);
    if (!id || isStarting) {
      console.warn("[Recording] Early return — id:", id, "isStarting:", isStarting);
      return;
    }
    try {
      setIsStarting(true);
      setIsRecording(true);
      setRecordingStatus("recording");
      setLivekitError(null);

      const res = await meetingsApi.startRecording(id);
      console.log("[Recording] API response:", res);
      setRecordingId(res.recording_id || null);
      setEgressId(res.egress_id || null);
      setRecordingDuration(0);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || String(err);
      console.error("[Recording] Failed to start recording:", errorMsg, err);
      setLivekitError(`Recording Error: ${errorMsg}`);
      setIsRecording(false);
      setRecordingStatus("idle");
    } finally {
      setIsStarting(false);
    }
  };

const handleStopRecording = async () => {
  if (!id) return;
  try {
    console.log("[Recording] STOP clicked — before setState:", { recordingStatus, isRecording, isSyncing });
    setRecordingStatus("processing");
    setIsRecording(false);
    console.log("[Recording] STOP — after setState, before API call");
    await meetingsApi.stopRecording(id);
    console.log("[Recording] STOP — API success");
    setEgressId(null);
  } catch (err) {
    console.error("[Recording] STOP — API error:", err);
    setRecordingStatus("recording");
    setIsRecording(true);
  }
};

  const handlePauseRecording = () => {
    // LiveKit Egress has no native pause — we toggle local timer only
    // The recording continues on server but user sees "paused" state locally
    setRecordingStatus("paused");
    setIsRecording(false);
  };

  const handleResumeRecording = () => {
    setRecordingStatus("recording");
    setIsRecording(true);
  };

  // ── Leave Handler ────────────────────────────────────────────────────────
  const leaveButtonRef = useRef<(() => void) | null>(null);

  const handleDisconnectReady = useCallback((fn: () => void) => {
    leaveButtonRef.current = fn;
  }, []);

  const handleLeave = async () => {
    try {
      // 1. Stop recording if active
      if (recordingStatus === "recording" || recordingStatus === "paused") {
        try {
          await handleStopRecording();
        } catch {
          // best-effort — still proceed with leave
        }
      }
    } finally {
      // 2. Disconnect LiveKit (via ref callback set by LeaveButton inner component)
      if (leaveButtonRef.current) {
        leaveButtonRef.current();
      }
      // 3. Navigate to meetings list
      navigate("/meetings");
    }
  };

  const handleSuggestionFeedback = async (suggestionId: string, action: "accept" | "reject") => {
    try {
      await meetingsApi.learnSuggestion({ suggestion_id: suggestionId, action });
      setSuggestions((prev) => prev.filter((s) => s.id !== suggestionId));
    } catch (err) {
      console.error(`Failed to ${action} suggestion`, err);
    }
  };

  // ── Edit Menu Handlers ───────────────────────────────────────────────────
  const handleEditMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setEditMenuAnchor(event.currentTarget);
  };

  const handleEditMenuClose = () => {
    setEditMenuAnchor(null);
  };

  const handleEditOnline = () => {
    if (pvId) {
      window.open(`/editor/${pvId}?lang=${exportLanguage}`, "_blank");
    }
    handleEditMenuClose();
  };

  const handleEditPdf = async () => {
    if (!pvId) return;
    try {
      const blob = await meetingsApi.getPvPdf(pvId, exportLanguage);
      const url = window.URL.createObjectURL(new Blob([blob], { type: "application/pdf" }));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `PV_${meetingInfo?.title || "meeting"}_${exportLanguage}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to export PDF:", err);
    }
    handleEditMenuClose();
  };

  const handleEditWord = async () => {
    if (!pvId) return;
    try {
      const blob = await meetingsApi.getPvDocx(pvId, exportLanguage);
      const url = window.URL.createObjectURL(new Blob([blob]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `PV_${meetingInfo?.title || "meeting"}_${exportLanguage}.docx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to export Word:", err);
    }
    handleEditMenuClose();
  };

  const handleValidatePv = async () => {
    if (!pvId || isValidated || isApproving) return;
    setIsApproving(true);
    try {
      await meetingsApi.validatePv(pvId);
      setIsValidated(true);
      alert(t("pv.approved_success") || "Protocol successfully validated! Action items have been assigned.");
    } catch (err) {
      console.error("Failed to approve PV", err);
      alert(t("pv.approved_error") || "Error validating the protocol.");
    } finally {
      setIsApproving(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <Box sx={{ p: { xs: 2, md: 3 }, maxWidth: 1800, mx: "auto", bgcolor: COLOR.bg, minHeight: "100vh" }}>

      {/* ── HEADER ─────────────────────────────────────────────────────────── */}
      <Paper
        elevation={0}
        sx={{
          p: { xs: 2, md: 3 }, mb: 3, borderRadius: 3,
          border: `1px solid ${COLOR.border}`,
          background: `linear-gradient(135deg, ${alpha(COLOR.primary, 0.04)} 0%, ${alpha(COLOR.purple, 0.04)} 100%)`,
        }}
      >
        <Stack direction={{ xs: "column", md: "row" }} alignItems={{ md: "center" }} justifyContent="space-between" gap={2}>
          {/* Left: Title + badges */}
          <Stack direction="row" alignItems="center" spacing={2} flexWrap="wrap">
            <Box sx={{
              width: 10, height: 10, borderRadius: "50%",
              bgcolor: isRecording ? COLOR.error : COLOR.success,
              animation: "pulse-opacity 2s infinite",
              boxShadow: `0 0 0 3px ${alpha(isRecording ? COLOR.error : COLOR.success, 0.2)}`,
            }} />

            <Box>
              <Typography sx={{ fontSize: { xs: 16, md: 20 }, fontWeight: 700, lineHeight: 1.2 }}>
                {meetingInfo?.title || <Skeleton width={220} />}
              </Typography>
              {meetingInfo?.topic && (
                <Typography sx={{ fontSize: 12, color: COLOR.textMuted, mt: 0.25 }}>
                  {meetingInfo.topic}
                </Typography>
              )}
            </Box>

            <Stack direction="row" spacing={1} flexWrap="wrap">
              <Chip
                label={isRecording ? t("meeting_assistant.recording_badge") : t("meeting_assistant.live_badge")}
                size="small"
                icon={isRecording ? <RecordIcon sx={{ fontSize: "12px !important" }} /> : <LiveIcon sx={{ fontSize: "12px !important" }} />}
                sx={{
                  bgcolor: isRecording ? alpha(COLOR.error, 0.1) : alpha(COLOR.success, 0.1),
                  color:   isRecording ? COLOR.error : COLOR.success,
                  fontWeight: 700, fontSize: 11, height: 24,
                  "& .MuiChip-icon": { color: "inherit" },
                }}
              />
              {meetingInfo?.organizer && (
                <Chip
                  label={meetingInfo.organizer}
                  size="small"
                  icon={<PersonIcon sx={{ fontSize: "12px !important" }} />}
                  sx={{ bgcolor: alpha(COLOR.primary, 0.08), color: COLOR.primary, fontSize: 11, height: 24 }}
                />
              )}
            </Stack>
          </Stack>

          {/* Right: Timers + participant count */}
          <Stack direction="row" alignItems="center" spacing={3} flexWrap="wrap">
            <Tooltip title={t("meeting_assistant.meeting_duration")}>
              <Stack direction="row" alignItems="center" spacing={0.75}>
                <AccessTimeIcon sx={{ fontSize: 15, color: COLOR.textMuted }} />
                <Typography sx={{ fontSize: 14, fontWeight: 600, fontFamily: "monospace", color: "text.primary" }}>
                  {formatDuration(meetingDuration)}
                </Typography>
              </Stack>
            </Tooltip>

            {isRecording && (
              <Tooltip title={t("meeting_assistant.recording_duration")}>
                <Stack direction="row" alignItems="center" spacing={0.75}>
                  <RecordIcon sx={{ fontSize: 15, color: COLOR.error, animation: "pulse-opacity 1.5s infinite" }} />
                  <Typography sx={{ fontSize: 14, fontWeight: 600, fontFamily: "monospace", color: COLOR.error }}>
                    {formatDuration(recordingDuration)}
                  </Typography>
                </Stack>
              </Tooltip>
            )}

            <Tooltip title={t("meeting_assistant.participants")}>
              <Stack direction="row" alignItems="center" spacing={0.75}>
                <GroupIcon sx={{ fontSize: 15, color: COLOR.textMuted }} />
                <Typography sx={{ fontSize: 14, fontWeight: 600 }}>
                  {livekitToken ? "●" : "—"}
                </Typography>
              </Stack>
            </Tooltip>
          </Stack>
        </Stack>
      </Paper>

      {/* ── PIPELINE PROGRESS INDICATOR ─────────────────────────────────────── */}
      <PipelineProgressIndicator status={recordingStatus} />

      {/* ── 3-COLUMN LAYOUT ─────────────────────────────────────────────────── */}
      <Grid container spacing={2.5}>

        {/* ── LEFT COLUMN: Audio + Recording + Speaking Stats ─────────────── */}
        <Grid item xs={12} lg={3}>
          <Stack spacing={2.5}>

            {/* LiveKit Audio */}
<Paper elevation={0} sx={{ borderRadius: 3, border: `1px solid ${COLOR.border}`, overflow: "hidden" }}>
              <Box sx={{ px: 2.5, pt: 2.5, pb: 1 }}>
                <Typography sx={{ fontSize: 13, fontWeight: 600, color: COLOR.textMuted, textTransform: "uppercase", letterSpacing: 0.5 }}>
                  {t("meeting_assistant.participants")}
                </Typography>
              </Box>
              {livekitToken ? (
                  <LiveKitRoom
                    token={livekitToken}
                    serverUrl={livekitUrl}
                    connect={true}
                    audio={true}
                    video={false}
                    connectOptions={{
                      peerConnectionTimeout: 30000,
                      maxRetries: 3,
                    }}
onConnected={() => {
                       setLivekitError(null);
                       setRoomConnectionReady(true);
                     }}
onError={(error) => {
                       console.error("[LiveKit] Connection error:", error, "serverUrl:", livekitUrl);
                       if (recordingStatus === "idle") {
                         setLivekitError(error.message || String(error));
                       }
                     }}
                    onMediaDeviceFailure={(failure, kind) => {
                      console.error("[LiveKit] Media device failure:", failure, kind);
                      if (recordingStatus === "idle") {
                        setLivekitError(`Media device failure: ${failure} (${kind})`);
                      }
                    }}
                    onDisconnected={() => {
                      setLivekitConnected(false);
                      setRoomConnectionReady(false);
                    }}
                   >
                     <LiveKitConnectionBridge onStateChange={handleLiveKitConnectionState} />
                     <LiveKitDisconnectBridge onReady={handleDisconnectReady} />
                     <MicToggleBridge onMicState={handleMicState} />
                     <RoomAudioRenderer />
                     <Box sx={{ px: 2, pb: 1, minHeight: 80 }}>
                       <ParticipantsList />
                     </Box>
</LiveKitRoom>
              ) : (
                <Box sx={{ px: 2.5, pb: 2.5, display: "flex", alignItems: "center", gap: 1.5 }}>
                  <CircularProgress size={18} />
                  <Typography sx={{ fontSize: 13, color: COLOR.textMuted }}>
                    {t("meeting_assistant.connecting")}
                  </Typography>
                </Box>
              )}
              {livekitError && (
                 <Box sx={{ px: 2.5, py: 2, bgcolor: alpha(COLOR.error, 0.08), borderTop: `1px solid ${alpha(COLOR.error, 0.2)}` }}>
                   <Typography sx={{ fontSize: 12, fontWeight: 600, color: COLOR.error, mb: 0.5 }}>
                     LiveKit Connection Error
                   </Typography>
                   <Typography sx={{ fontSize: 11, color: COLOR.error, fontFamily: "monospace", wordBreak: "break-all" }}>
                     {livekitError}
</Typography>
                  </Box>
                )}
            </Paper>

            {/* ── TEAMS-LIKE RECORDING CONTROLS ── */}
            <Paper elevation={0} sx={{ p: 2.5, borderRadius: 3, border: `1px solid ${COLOR.border}` }}>
              <Typography sx={{ fontSize: 13, fontWeight: 600, color: COLOR.textMuted, textTransform: "uppercase", letterSpacing: 0.5, mb: 2 }}>
                {t("meeting_assistant.recording")}
              </Typography>

{/* IDLE — Show Start button (only for creator) */}
               {recordingStatus === "idle" && !isSyncing && meetingCreatorId === currentUser?.id && (
                <>
                <Button variant="contained" fullWidth disableElevation onClick={handleStartRecording}
                    disabled={!roomConnectionReady || isStarting}
                   startIcon={<RecordIcon />}
                   sx={{ bgcolor: COLOR.error, color: "#FFF", borderRadius: 2, textTransform: "none", fontSize: 14, fontWeight: 600, py: 1.25, "&:hover": { bgcolor: "#DC2626" } }}
                 >
                   {roomConnectionReady ? t("meeting_assistant.start_recording") : t("meeting_assistant.waiting_connection")}
                 </Button>
                 {livekitError && livekitError.startsWith("Recording Error:") && (
                   <Typography sx={{ fontSize: 11, color: COLOR.error, mt: 1, fontFamily: "monospace", wordBreak: "break-all" }}>
                     {livekitError}
                   </Typography>
                 )}
                </>
               )}

              {/* SYNCING — Loading state while backend status is fetched */}
              {recordingStatus === "idle" && isSyncing && (
                <Stack direction="row" alignItems="center" spacing={1.5} sx={{ p: 1.5, borderRadius: 2, bgcolor: alpha(COLOR.primary, 0.05), border: `1px solid ${alpha(COLOR.primary, 0.15)}` }}>
                  <CircularProgress size={18} sx={{ color: COLOR.primary }} />
                  <Typography sx={{ fontSize: 13, color: COLOR.textMuted }}>
                    {t("meeting_assistant.insights_processing") || "Loading..."}
                  </Typography>
                </Stack>
              )}

              {/* IDLE — Non-creator waiting */}
              {recordingStatus === "idle" && !isSyncing && meetingCreatorId !== currentUser?.id && (
                 <Stack alignItems="center" spacing={1} sx={{ py: 1, color: COLOR.textMuted }}>
                   <RecordIcon sx={{ fontSize: 28, color: alpha("#000", 0.1) }} />
                   <Typography sx={{ fontSize: 12, textAlign: "center" }}>
                     {t("meeting_assistant.waiting_for_host")}
                   </Typography>
                </Stack>
              )}

              {/* RECORDING — Show status + Stop + Pause */}
              {recordingStatus === "recording" && (
                <Stack spacing={1.5}>
                  {/* Status indicator */}
                  <Stack direction="row" alignItems="center" spacing={1.5} sx={{
                    p: 1.5, borderRadius: 2,
                    bgcolor: alpha(COLOR.error, 0.06),
                    border: `1px solid ${alpha(COLOR.error, 0.15)}`,
                  }}>
                    <Box sx={{ width: 10, height: 10, borderRadius: "50%", bgcolor: COLOR.error, animation: "pulse-opacity 1s infinite", flexShrink: 0 }} />
                    <Box sx={{ flexGrow: 1 }}>
                      <Typography sx={{ fontSize: 13, fontWeight: 600, color: COLOR.error }}>
                        {t("meeting_assistant.recording_in_progress")}
                      </Typography>
                      <Typography sx={{ fontSize: 12, color: COLOR.textMuted, fontFamily: "monospace" }}>
                        {formatDuration(recordingDuration)}
                      </Typography>
                    </Box>
                  </Stack>

                  {/* Teams-like Stop + Pause buttons */}
                  {meetingCreatorId === currentUser?.id && (
                    <Stack direction="row" spacing={1}>
                       <Button
                         variant="outlined" fullWidth onClick={handlePauseRecording}
                         startIcon={<PauseIcon />}
                         sx={{ borderRadius: 2, textTransform: "none", fontSize: 13, fontWeight: 600, py: 1, borderColor: COLOR.warning, color: COLOR.warning, "&:hover": { bgcolor: alpha(COLOR.warning, 0.06), borderColor: COLOR.warning } }}
                       >
                         {t("meeting_assistant.pause_recording")}
                       </Button>
                       <Button
                         variant="contained" fullWidth disableElevation onClick={handleStopRecording}
                         startIcon={<StopIcon />}
                         sx={{ bgcolor: "#1F2937", color: "#FFF", borderRadius: 2, textTransform: "none", fontSize: 13, fontWeight: 600, py: 1, "&:hover": { bgcolor: "#111827" } }}
                       >
                         {t("meeting_assistant.stop_recording")}
                       </Button>
                    </Stack>
                  )}
                </Stack>
              )}

              {/* PAUSED — Show Resume + Stop */}
              {recordingStatus === "paused" && (
                <Stack spacing={1.5}>
                  <Stack direction="row" alignItems="center" spacing={1.5} sx={{
                    p: 1.5, borderRadius: 2,
                    bgcolor: alpha(COLOR.warning, 0.06),
                    border: `1px solid ${alpha(COLOR.warning, 0.2)}`,
                  }}>
                    <PauseIcon sx={{ fontSize: 18, color: COLOR.warning }} />
                     <Box sx={{ flexGrow: 1 }}>
                       <Typography sx={{ fontSize: 13, fontWeight: 600, color: COLOR.warning }}>
                         {t("meeting_assistant.recording_paused")}
                       </Typography>
                       <Typography sx={{ fontSize: 12, color: COLOR.textMuted, fontFamily: "monospace" }}>
                         {formatDuration(recordingDuration)}
                       </Typography>
                     </Box>
                   </Stack>
                   {meetingCreatorId === currentUser?.id && (
                     <Stack direction="row" spacing={1}>
                       <Button
                         variant="contained" fullWidth disableElevation onClick={handleResumeRecording}
                         startIcon={<ResumeIcon />}
                         sx={{ bgcolor: COLOR.success, color: "#FFF", borderRadius: 2, textTransform: "none", fontSize: 13, fontWeight: 600, py: 1, "&:hover": { bgcolor: "#16A34A" } }}
                       >
                         {t("meeting_assistant.resume_recording")}
                       </Button>
                      <Button
                        variant="outlined" fullWidth onClick={handleStopRecording}
                        startIcon={<StopIcon />}
                        sx={{ borderRadius: 2, textTransform: "none", fontSize: 13, fontWeight: 600, py: 1, borderColor: COLOR.border, color: "text.secondary" }}
                      >
                        Stop
                      </Button>
                    </Stack>
                  )}
                </Stack>
              )}

              {/* PROCESSING — AI pipeline running */}
              {recordingStatus === "processing" && (
                <Stack direction="row" alignItems="center" spacing={1.5} sx={{ p: 1.5, borderRadius: 2, bgcolor: alpha(COLOR.primary, 0.05), border: `1px solid ${alpha(COLOR.primary, 0.15)}` }}>
                  <CircularProgress size={18} sx={{ color: COLOR.primary }} />
                  <Box>
                    <Typography sx={{ fontSize: 13, fontWeight: 600, color: COLOR.primary }}>
                      {t("meeting_assistant.insights_processing")}
                    </Typography>
                    <Typography sx={{ fontSize: 11, color: COLOR.textMuted }}>
                      Gladia → Mistral AI pipeline
                    </Typography>
                  </Box>
                </Stack>
              )}

              {/* COMPLETED — Tier 4.1: pipeline finished, show real data */}
              {recordingStatus === "completed" && (
                <Stack direction="row" alignItems="center" spacing={1.5} sx={{ p: 1.5, borderRadius: 2, bgcolor: alpha(COLOR.success, 0.05), border: `1px solid ${alpha(COLOR.success, 0.2)}` }}>
                  <CheckIcon sx={{ fontSize: 18, color: COLOR.success }} />
                  <Box sx={{ flexGrow: 1 }}>
                    <Typography sx={{ fontSize: 13, fontWeight: 600, color: COLOR.success }}>
                      Recording complete
                    </Typography>
                    <Typography sx={{ fontSize: 11, color: COLOR.textMuted }}>
                      {liveTranscription.length > 0
                        ? `${liveTranscription.length} segments transcribed`
                        : "Transcription ready"}
                      {aiInsights.length > 0 && ` • ${aiInsights.length} insights`}
                      {suggestions.length > 0 && ` • ${suggestions.length} actions`}
                    </Typography>
                  </Box>
                </Stack>
              )}

              {/* FAILED — pipeline errored */}
              {recordingStatus === "failed" && (
                <Stack direction="row" alignItems="center" spacing={1.5} sx={{ p: 1.5, borderRadius: 2, bgcolor: alpha(COLOR.error, 0.05), border: `1px solid ${alpha(COLOR.error, 0.2)}` }}>
                  <Box sx={{ flexGrow: 1 }}>
                    <Typography sx={{ fontSize: 13, fontWeight: 600, color: COLOR.error }}>
                      Recording failed
                    </Typography>
                    <Typography sx={{ fontSize: 11, color: COLOR.textMuted }}>
                      Check the audit log for details
                    </Typography>
                  </Box>
                </Stack>
              )}

              {/* STOPPED — Done */}
              {recordingStatus === "stopped" && (
                <Stack direction="row" alignItems="center" spacing={1.5} sx={{ p: 1.5, borderRadius: 2, bgcolor: alpha(COLOR.success, 0.05), border: `1px solid ${alpha(COLOR.success, 0.2)}` }}>
                  <CheckIcon sx={{ fontSize: 18, color: COLOR.success }} />
                  <Box>
                    <Typography sx={{ fontSize: 13, fontWeight: 600, color: COLOR.success }}>
                      Recording Saved
                    </Typography>
                    <Typography sx={{ fontSize: 11, color: COLOR.textMuted }}>
                      AI processing started...
                    </Typography>
                  </Box>
                 </Stack>
               )}
             </Paper>

           </Stack>
         </Grid>

        {/* ── MIDDLE COLUMN: Live Transcription ───────────────────────────── */}
        <Grid item xs={12} lg={6}>
          <Paper
            elevation={0}
            sx={{
              borderRadius: 3, border: `1px solid ${COLOR.border}`,
              minHeight: "70vh", display: "flex", flexDirection: "column",
              overflow: "hidden",
              boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
            }}
          >
            {/* Transcription header */}
            <Stack
              direction="row" alignItems="center" justifyContent="space-between"
              sx={{
                px: 2.5, py: 2,
                borderBottom: `1px solid ${COLOR.border}`,
                background: `linear-gradient(135deg, ${alpha(COLOR.primary, 0.03)} 0%, ${alpha(COLOR.purple, 0.03)} 100%)`,
              }}
            >
              <Stack direction="row" alignItems="center" spacing={1}>
                <Box sx={{
                  width: 8, height: 8, borderRadius: "50%",
                  bgcolor: isRecording ? COLOR.success : COLOR.textMuted,
                  animation: isRecording ? "pulse 1.5s infinite" : "none",
                }} />
                <Typography sx={{ fontSize: 14, fontWeight: 600, display: "flex", alignItems: "center", gap: 1 }}>
                  <TextSnippetIcon sx={{ fontSize: 18, color: COLOR.primary }} />
                  {t("meetings.live_transcription")}
                </Typography>
              </Stack>
              {liveTranscription.length > 0 && (
                <Chip
                  size="small"
                  label={`${liveTranscription.length} segments`}
                  sx={{
                    bgcolor: alpha(COLOR.primary, 0.1),
                    color: COLOR.primary,
                    fontSize: 11,
                    fontWeight: 700,
                    height: 22,
                  }}
                />
              )}
            </Stack>

            {/* Transcription body */}
            <Box sx={{ flexGrow: 1, overflowY: "auto", p: 2.5, bgcolor: alpha("#000", 0.01) }}>
              {liveTranscription.length === 0 ? (
                <Stack
                  alignItems="center" justifyContent="center" spacing={2.5}
                  sx={{ height: "100%", minHeight: 300, color: COLOR.textMuted }}
                >
                  {isRecording ? (
                    <>
                      <Box sx={{
                        width: 56, height: 56, borderRadius: "50%",
                        bgcolor: alpha(COLOR.primary, 0.08),
                        display: "flex", alignItems: "center", justifyContent: "center",
                      }}>
                        <Box sx={{ display: "flex", gap: 0.5, alignItems: "center" }}>
                          {[0, 1, 2, 3, 4].map((i) => (
                            <Box
                              key={i}
                              sx={{
                                width: 4, height: 24, borderRadius: 2,
                                bgcolor: COLOR.primary,
                                animation: `wave 1s ease-in-out ${i * 0.15}s infinite`,
                              }}
                            />
                          ))}
                        </Box>
                      </Box>
                      <Typography sx={{ fontSize: 15, fontWeight: 600, color: "text.primary" }}>
                        {t("meeting_assistant.transcription_streaming")}
                      </Typography>
                      <Typography sx={{ fontSize: 12, textAlign: "center", maxWidth: 280 }}>
                        {t("meeting_assistant.ai_processing")}
                      </Typography>
                    </>
                  ) : (
                    <>
                      <Box sx={{
                        width: 64, height: 64, borderRadius: "50%",
                        bgcolor: alpha("#000", 0.04),
                        display: "flex", alignItems: "center", justifyContent: "center",
                      }}>
                        <MicOffIcon sx={{ fontSize: 32, color: alpha("#000", 0.15) }} />
                      </Box>
                      <Typography sx={{ fontSize: 14, fontWeight: 600, color: "text.primary" }}>
                        {t("meeting_assistant.no_transcription_yet")}
                      </Typography>
                      <Typography sx={{ fontSize: 12, textAlign: "center", maxWidth: 280 }}>
                        {t("meeting_assistant.start_recording_for_stats")}
                      </Typography>
                    </>
                  )}
                </Stack>
              ) : (
                <Stack spacing={1}>
                  {liveTranscription.map((seg, idx) => {
                    const color = speakerColor(seg.speaker);
                    const isLast = idx === liveTranscription.length - 1;
                    return (
                      <Box
                        key={idx}
                        sx={{
                          display: "flex",
                          gap: 1.5,
                          p: 1.5,
                          borderRadius: 2,
                          bgcolor: isLast ? alpha(COLOR.primary, 0.04) : "transparent",
                          border: isLast ? `1px solid ${alpha(COLOR.primary, 0.1)}` : "1px solid transparent",
                          transition: "all 0.2s ease",
                          "&:hover": { bgcolor: alpha("#000", 0.02) },
                        }}
                      >
                        <Avatar sx={{
                          width: 28, height: 28, fontSize: 11, fontWeight: 600,
                          bgcolor: color, flexShrink: 0, mt: 0.5,
                        }}>
                          {speakerInitial(seg.speaker)}
                        </Avatar>
                        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                          <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.5 }}>
                            <Typography sx={{ fontSize: 12, fontWeight: 700, color }}>
                              {seg.speaker}
                            </Typography>
                            {seg.timestamp && (
                              <Typography sx={{ fontSize: 10, color: COLOR.textMuted, fontFamily: "monospace" }}>
                                {seg.timestamp}
                              </Typography>
                            )}
                          </Stack>
                          <Typography sx={{
                            fontSize: 14,
                            lineHeight: 1.65,
                            color: "text.primary",
                          }}>
                            {seg.text}
                          </Typography>
                        </Box>
                      </Box>
                    );
                  })}
                  {isRecording && (
                    <Stack direction="row" alignItems="center" spacing={1.5} sx={{ px: 1.5, py: 1 }}>
                      {[0, 1, 2].map((i) => (
                        <Box
                          key={i}
                          sx={{
                            width: 6, height: 6, borderRadius: "50%",
                            bgcolor: COLOR.primary,
                            animation: `pulse 1s ease-in-out ${i * 0.2}s infinite`,
                          }}
                        />
                      ))}
                      <Typography sx={{ fontSize: 12, color: COLOR.primary, fontWeight: 500 }}>
                        {t("meeting_assistant.transcription_streaming")}
                      </Typography>
                    </Stack>
                  )}
                  <div ref={transcriptionEndRef} />
                </Stack>
              )}
            </Box>
          </Paper>
        </Grid>

        {/* ── RIGHT COLUMN: AI Insights + Recommendations ─────────────────── */}
        <Grid item xs={12} lg={3}>
          <Stack spacing={2.5}>

            {/* ── EDIT PV BUTTON GROUP ─────────────────────────────────────── */}
            <Paper elevation={0} sx={{ p: 2, borderRadius: 3, border: `1px solid ${COLOR.border}`, background: `linear-gradient(135deg, ${alpha(COLOR.success, 0.04)} 0%, ${alpha(COLOR.primary, 0.04)} 100%)` }}>
              <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1.5 }}>
                <Typography sx={{ fontSize: 13, fontWeight: 600, color: COLOR.success, display: "flex", alignItems: "center", gap: 0.75 }}>
                  <CheckIcon sx={{ fontSize: 16 }} />
                  {t("meeting_assistant.pipeline_complete")}
                </Typography>
              </Stack>
              <FormControl size="small" fullWidth sx={{ mb: 1.5 }}>
                <InputLabel sx={{ fontSize: 13 }}>{t("common.language") || "Language"}</InputLabel>
                <Select
                  value={exportLanguage}
                  label={t("common.language") || "Language"}
                  onChange={(e: SelectChangeEvent) => setExportLanguage(e.target.value as string)}
                  sx={{ borderRadius: 2, fontSize: 13 }}
                >
                  <MenuItem value="ar">العربية</MenuItem>
                  <MenuItem value="fr">Français</MenuItem>
                  <MenuItem value="en">English</MenuItem>
                </Select>
              </FormControl>
              <Button
                variant="contained"
                fullWidth
                disableElevation
                disabled={!(recordingStatus === "completed" && pvId)}
                onClick={handleEditMenuOpen}
                startIcon={<EditIcon sx={{ fontSize: 16 }} />}
                sx={{
                  bgcolor: COLOR.primary,
                  color: "#FFF",
                  borderRadius: 2,
                  textTransform: "none",
                  fontSize: 13,
                  fontWeight: 600,
                  py: 1,
                  "&:hover": { bgcolor: "#2563EB" },
                }}
              >
                {t("meeting_assistant.edit_pv")}
              </Button>
              <Menu
                anchorEl={editMenuAnchor}
                open={Boolean(editMenuAnchor)}
                onClose={handleEditMenuClose}
                PaperProps={{ sx: { borderRadius: 2, minWidth: 200 } }}
              >
                <MenuItem onClick={handleEditOnline}>
                  <ListItemIcon>
                    <EditIcon sx={{ fontSize: 18, color: COLOR.primary }} />
                  </ListItemIcon>
                  <ListItemText
                    primary={t("pv.edit_online", "Edit Online")}
                    secondary={t("meeting_assistant.edit_online_desc", "Open in OnlyOffice editor")}
                    primaryTypographyProps={{ fontSize: 13, fontWeight: 600 }}
                    secondaryTypographyProps={{ fontSize: 11 }}
                  />
                </MenuItem>
                <MenuItem onClick={handleEditPdf}>
                  <ListItemIcon>
                    <PdfIcon sx={{ fontSize: 18, color: COLOR.error }} />
                  </ListItemIcon>
                  <ListItemText
                    primary={t("meeting_assistant.export_pdf", "Export PDF")}
                    secondary={t("meeting_assistant.export_pdf_desc", "Download as PDF document")}
                    primaryTypographyProps={{ fontSize: 13, fontWeight: 600 }}
                    secondaryTypographyProps={{ fontSize: 11 }}
                  />
                </MenuItem>
                <MenuItem onClick={handleEditWord}>
                  <ListItemIcon>
                    <WordIcon sx={{ fontSize: 18, color: "#2B579A" }} />
                  </ListItemIcon>
                  <ListItemText
                    primary={t("meeting_assistant.export_word", "Export Word")}
                    secondary={t("meeting_assistant.export_word_desc", "Download as DOCX file")}
                    primaryTypographyProps={{ fontSize: 13, fontWeight: 600 }}
                    secondaryTypographyProps={{ fontSize: 11 }}
                  />
                </MenuItem>
              </Menu>
              <Button
                variant="contained"
                fullWidth
                disableElevation
                disabled={!(recordingStatus === "completed" && pvId) || isValidated || isApproving}
                onClick={handleValidatePv}
                startIcon={
                  isApproving ? <CircularProgress size={16} color="inherit" /> :
                  isValidated  ? <CheckIcon /> :
                                 <ApproveIcon />
                }
                sx={{
                  mt: 1.5,
                  bgcolor: isValidated ? "#10B981" : "#3B82F6",
                  color: "#FFF",
                  borderRadius: 2,
                  textTransform: "none",
                  fontWeight: 600,
                  fontSize: 13,
                  py: 1,
                  "&:hover": { bgcolor: isValidated ? "#059669" : "#2563EB" },
                  "&.Mui-disabled": {
                    bgcolor: isValidated ? alpha("#10B981", 0.6) : undefined,
                    color: isValidated ? "#FFF" : undefined,
                  },
                }}
              >
                {isValidated ? (t("pv.validated") || "Validated") : (t("pv.approve") || "Approve & Sign")}
              </Button>
            </Paper>

            {/* AI Insights */}
            <Paper elevation={0} sx={{ p: 2.5, borderRadius: 3, border: `1px solid ${COLOR.border}` }}>
              <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
                <Stack direction="row" alignItems="center" spacing={1}>
                  <SmartToyIcon sx={{ fontSize: 18, color: COLOR.primary }} />
                  <Typography sx={{ fontSize: 13, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
                    {t("meeting_assistant.ai_insights")}
                  </Typography>
                </Stack>
                {aiInsights.length > 0 && (
                  <Badge
                    badgeContent={aiInsights.length}
                    sx={{
                      "& .MuiBadge-badge": {
                        bgcolor: COLOR.primary,
                        color: "#FFF",
                        fontSize: 10,
                        fontWeight: 700,
                        height: 18,
                        minWidth: 18,
                      },
                    }}
                  />
                )}
              </Stack>

              {insightsLoading ? (
                <Stack spacing={1.5}>
                  {[1, 2].map((i) => (
                    <Box key={i} sx={{ p: 1.5, borderRadius: 2, bgcolor: alpha("#000", 0.02) }}>
                      <Skeleton width="60%" height={14} sx={{ mb: 1 }} />
                      <Skeleton variant="rectangular" height={4} sx={{ borderRadius: 2, mb: 1 }} />
                      <Skeleton width="80%" height={12} />
                    </Box>
                  ))}
                  <Stack alignItems="center" spacing={1} sx={{ mt: 1 }}>
                    <CircularProgress size={16} sx={{ color: COLOR.primary }} />
                    <Typography sx={{ fontSize: 11, color: COLOR.textMuted, textAlign: "center" }}>
                      {t("meeting_assistant.insights_processing")}
                    </Typography>
                  </Stack>
                </Stack>
              ) : aiInsights.length === 0 ? (
                <Stack alignItems="center" spacing={1.5} sx={{ py: 3, color: COLOR.textMuted }}>
                  <Box sx={{
                    width: 48, height: 48, borderRadius: "50%",
                    bgcolor: alpha("#000", 0.04),
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}>
                    <SmartToyIcon sx={{ fontSize: 24, color: alpha("#000", 0.12) }} />
                  </Box>
                  <Typography sx={{ fontSize: 12, textAlign: "center", maxWidth: 200 }}>
                    {isRecording
                      ? t("meeting_assistant.ai_processing")
                      : t("meeting_assistant.poll_for_insights")}
                  </Typography>
                </Stack>
              ) : (
                <Stack spacing={1.25}>
                  {aiInsights.map((insight, idx) => (
                    <Box
                      key={idx}
                      sx={{
                        p: 1.75,
                        borderRadius: 2.5,
                        bgcolor: alpha(COLOR.primary, 0.03),
                        border: `1px solid ${alpha(COLOR.primary, 0.08)}`,
                        transition: "all 0.15s ease",
                        "&:hover": {
                          bgcolor: alpha(COLOR.primary, 0.06),
                          borderColor: alpha(COLOR.primary, 0.15),
                        },
                      }}
                    >
                      <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 0.75 }}>
                        <Typography sx={{ fontSize: 12, fontWeight: 700, color: COLOR.primary, flexGrow: 1 }}>
                          {insight.topic}
                        </Typography>
                        <Chip
                          label={`${Math.round(insight.confidence * 100)}%`}
                          size="small"
                          sx={{
                            height: 18, fontSize: 9, fontWeight: 700,
                            bgcolor: alpha(COLOR.primary, 0.1),
                            color: COLOR.primary,
                          }}
                        />
                      </Stack>
                      <LinearProgress
                        variant="determinate"
                        value={insight.confidence * 100}
                        sx={{
                          mb: 1, height: 3, borderRadius: 2,
                          bgcolor: alpha(COLOR.primary, 0.08),
                          "& .MuiLinearProgress-bar": { bgcolor: COLOR.primary, borderRadius: 2 },
                        }}
                      />
                      <Stack spacing={0.5}>
                        {insight.actions.map((action, i) => (
                          <Stack key={i} direction="row" alignItems="flex-start" spacing={0.75}>
                            <Box sx={{
                              width: 4, height: 4, borderRadius: "50%",
                              bgcolor: COLOR.primary, mt: 1, flexShrink: 0,
                            }} />
                            <Typography sx={{ fontSize: 11, color: "text.secondary", lineHeight: 1.5 }}>
                              {action}
                            </Typography>
                          </Stack>
                        ))}
                      </Stack>
                    </Box>
                  ))}
                </Stack>
              )}
            </Paper>

            {/* AI Recommendations */}
            <Paper elevation={0} sx={{ p: 2.5, borderRadius: 3, border: `1px solid ${COLOR.border}` }}>
              <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 2 }}>
                <Stack direction="row" alignItems="center" spacing={1}>
                  <SuggestionIcon sx={{ fontSize: 18, color: COLOR.purple }} />
                  <Typography sx={{ fontSize: 13, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
                    {t("meeting_assistant.ai_recommendations")}
                  </Typography>
                </Stack>
                {suggestions.length > 0 && (
                  <Chip
                    size="small"
                    label={suggestions.length}
                    sx={{ bgcolor: alpha("#000", 0.08), color: "text.primary", fontSize: 11, fontWeight: 700, height: 20 }}
                  />
                )}
              </Stack>

              {suggestions.length === 0 ? (
                <Stack alignItems="center" spacing={1} sx={{ py: 3, color: COLOR.textMuted }}>
                  <SuggestionIcon sx={{ fontSize: 32, color: alpha("#000", 0.08) }} />
                  <Typography sx={{ fontSize: 13, textAlign: "center" }}>
                    {t("meeting_assistant.no_suggestions")}
                  </Typography>
                </Stack>
              ) : (
                <Stack spacing={1.25} sx={{ maxHeight: 380, overflowY: "auto" }}>
                  {suggestions.map((s) => (
                    <Box
                      key={s.id}
                      sx={{
                        p: 1.75,
                        borderRadius: 2.5,
                        bgcolor: COLOR.card,
                        border: `1px solid ${COLOR.border}`,
                        boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
                        "&:hover": {
                          borderColor: alpha(COLOR.primary, 0.25),
                          boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
                        },
                        transition: "all 0.15s ease",
                      }}
                    >
                      <Stack direction="row" alignItems="flex-start" justifyContent="space-between" sx={{ mb: 0.75 }}>
                        <Typography sx={{ fontSize: 12, fontWeight: 700, flexGrow: 1, pr: 1, lineHeight: 1.4 }}>
                          {s.title}
                        </Typography>
                        {s.priority && (
                          <Chip
                            size="small"
                            label={s.priority}
                            sx={{
                              bgcolor: alpha(priorityColor(s.priority, COLOR), 0.1),
                              color: priorityColor(s.priority, COLOR),
                              fontSize: 9, fontWeight: 700, height: 18,
                              textTransform: "uppercase",
                              flexShrink: 0,
                            }}
                          />
                        )}
                      </Stack>
                      <Typography sx={{ fontSize: 11, color: COLOR.textMuted, mb: 1.25, lineHeight: 1.5 }}>
                        {s.description}
                      </Typography>
                      {s.suggested_assignee && (
                        <Stack direction="row" alignItems="center" spacing={0.75} sx={{ mb: 1.25 }}>
                          <Avatar sx={{
                            width: 20, height: 20, fontSize: 9, fontWeight: 600,
                            bgcolor: alpha(COLOR.primary, 0.12), color: COLOR.primary,
                          }}>
                            {speakerInitial(s.suggested_assignee)}
                          </Avatar>
                          <Typography sx={{ fontSize: 11, color: "text.secondary", fontWeight: 500 }}>
                            {s.suggested_assignee}
                          </Typography>
                        </Stack>
                      )}
                      <Stack direction="row" spacing={0.75}>
                        <Button
                          size="small" variant="contained" disableElevation
                          onClick={() => handleSuggestionFeedback(s.id, "accept")}
                          startIcon={<CheckIcon sx={{ fontSize: "12px !important" }} />}
                          sx={{
                            flexGrow: 1,
                            bgcolor: COLOR.success,
                            color: "#FFF",
                            borderRadius: 1.5,
                            textTransform: "none",
                            fontSize: 11,
                            fontWeight: 600,
                            py: 0.5,
                            "&:hover": { bgcolor: "#16A34A" },
                          }}
                        >
                          {t("meeting_assistant.accept")}
                        </Button>
                        <Button
                          size="small" variant="outlined"
                          onClick={() => handleSuggestionFeedback(s.id, "reject")}
                          sx={{
                            borderRadius: 1.5,
                            textTransform: "none",
                            fontSize: 11,
                            fontWeight: 500,
                            py: 0.5,
                            borderColor: alpha(COLOR.error, 0.3),
                            color: COLOR.error,
                            "&:hover": {
                              bgcolor: alpha(COLOR.error, 0.04),
                              borderColor: COLOR.error,
                            },
                          }}
                        >
                          {t("meeting_assistant.reject")}
                        </Button>
                      </Stack>
                    </Box>
                  ))}
                </Stack>
              )}
            </Paper>
          </Stack>
        </Grid>
      </Grid>

      {/* ── BOTTOM CONTROL BAR ─────────────────────────────────────────────── */}
      <Paper
        elevation={0}
        sx={{
          mt: 3, p: 2, borderRadius: 3,
          border: `1px solid ${COLOR.border}`,
          background: `linear-gradient(135deg, #1F2937 0%, #111827 100%)`,
        }}
      >
        <Stack direction="row" alignItems="center" justifyContent="space-between" gap={2}>

          {/* Left: Connection status */}
          <Stack direction="row" alignItems="center" spacing={1}>
            <Box
              role="status"
              aria-live="polite"
              aria-label={`Connection: ${livekitConnectionState}`}
              sx={{ display: "flex", alignItems: "center", gap: 1 }}
            >
              <Box sx={{
                width: 8, height: 8, borderRadius: "50%", flexShrink: 0,
                bgcolor:
                  livekitConnectionState === ConnectionState.Connected ? COLOR.success :
                  livekitConnectionState === ConnectionState.Reconnecting ? COLOR.warning :
                  COLOR.error,
                animation:
                  livekitConnectionState === ConnectionState.Reconnecting
                    ? "pulse-opacity 1s infinite"
                    : "none",
              }} />
              <Typography sx={{
                fontSize: 12, fontWeight: 500,
                color:
                  livekitConnectionState === ConnectionState.Connected ? "rgba(255,255,255,0.85)" :
                  livekitConnectionState === ConnectionState.Reconnecting ? COLOR.warning :
                  COLOR.error,
              }}>
                {livekitConnectionState === ConnectionState.Connected && t("meeting_assistant.connection_connected")}
                {livekitConnectionState === ConnectionState.Connecting && t("meeting_assistant.connection_connecting")}
                {livekitConnectionState === ConnectionState.Reconnecting && t("meeting_assistant.connection_reconnecting")}
                {livekitConnectionState === ConnectionState.Disconnected && t("meeting_assistant.connection_disconnected")}
              </Typography>
            </Box>
          </Stack>

          {/* Center: Mic toggle (only when connected) */}
          <Stack direction="row" alignItems="center" spacing={1}>
            {livekitConnected && (
              <Tooltip title={micEnabled ? t("meeting_assistant.mic_mute") : t("meeting_assistant.mic_unmute")}>
                <IconButton
                  tabIndex={0}
                  aria-label={micEnabled ? t("meeting_assistant.mic_mute") : t("meeting_assistant.mic_unmute")}
                  onClick={handleMicToggle}
                  sx={{
                    width: 44, height: 44, borderRadius: "50%",
                    bgcolor: micEnabled ? alpha("#fff", 0.1) : alpha(COLOR.error, 0.3),
                    color: "#fff",
                    "&:hover": {
                      bgcolor: micEnabled ? alpha("#fff", 0.2) : alpha(COLOR.error, 0.5),
                    },
                    "&:focus-visible": { outline: "2px solid #fff", outlineOffset: 2 },
                  }}
                >
                  {micEnabled
                    ? <MicIcon sx={{ fontSize: 20 }} />
                    : <MicOffIcon sx={{ fontSize: 20 }} />}
                </IconButton>
              </Tooltip>
            )}
          </Stack>

          {/* Right: Leave */}
          <Button
            variant="contained"
            disableElevation
            tabIndex={0}
            aria-label={t("meeting_assistant.leave_meeting")}
            onClick={handleLeave}
            startIcon={<LeaveIcon />}
            sx={{
              bgcolor: COLOR.error, color: "#FFF",
              borderRadius: 2, textTransform: "none",
              fontSize: 13, fontWeight: 600, px: 2.5,
              "&:hover": { bgcolor: "#DC2626" },
              "&:focus-visible": { outline: `2px solid #fff`, outlineOffset: 2 },
            }}
          >
            {t("meeting_assistant.leave")}
          </Button>
        </Stack>
      </Paper>

      {/* CSS Animations — imported from shared styles/animations.ts */}
      <style>{animations}</style>
    </Box>
  );
};

export default MeetingRoom;
