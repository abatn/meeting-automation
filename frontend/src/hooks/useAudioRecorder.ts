import { useState, useRef, useCallback, useEffect } from "react";
import { meetingsApi } from "../services/meetings";

interface UseAudioRecorderReturn {
  isRecording: boolean;
  isPaused: boolean;
  duration: number;
  startRecording: (meetingId: string) => Promise<void>;
  stopRecording: (meetingId: string) => Promise<any | null>;
  pauseRecording: () => void;
  resumeRecording: () => void;
  error: string | null;
}

export const useAudioRecorder = (): UseAudioRecorderReturn => {
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const timerInterval = useRef<number | null>(null);
  const currentMeetingId = useRef<string | null>(null);

  // Streaming state
  const uploadIdRef = useRef<string | null>(null);
  const fileKeyRef = useRef<string | null>(null);
  const partNumberRef = useRef<number>(1);
  const uploadedPartsRef = useRef<any[]>([]);
  const recordingIdRef = useRef<string | null>(null);
  const isUploadingRef = useRef<boolean>(false);
  const chunkQueue = useRef<Blob[]>([]);
  const isStoppingRef = useRef<boolean>(false);

  const processChunkQueue = useCallback(async () => {
    if (isUploadingRef.current || chunkQueue.current.length === 0) return;

    isUploadingRef.current = true;
    const chunk = chunkQueue.current.shift();

    if (chunk && uploadIdRef.current && fileKeyRef.current) {
      try {
        const currentPart = partNumberRef.current++;
        console.log(`Uploading chunk ${currentPart} (Size: ${chunk.size} bytes)...`);
        const response = await meetingsApi.uploadStreamChunk(
          uploadIdRef.current,
          fileKeyRef.current,
          currentPart,
          chunk,
        );
        uploadedPartsRef.current.push({
          PartNumber: response.part_number,
          ETag: response.etag,
        });
        console.log(`Chunk ${currentPart} uploaded successfully.`);
      } catch (err) {
        console.error("Failed to upload chunk", err);
        setError(
          "Network error during streaming. Recording may be incomplete.",
        );
      }
    }

    isUploadingRef.current = false;

    // Process next chunk if available
    if (chunkQueue.current.length > 0) {
      setTimeout(() => processChunkQueue(), 10);
    }
  }, []);

  const startRecording = useCallback(
    async (meetingId: string) => {
      try {
        isStoppingRef.current = false;
        currentMeetingId.current = meetingId;

        // 1. Start capturing audio
        let stream;
        try {
          stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch (err) {
          setError("Microphone Error: Access denied or no device found.");
          console.error("Microphone access error:", err);
          return;
        }

        // 2. Initialize stream on backend
        try {
          const startResponse = await meetingsApi.startStream(meetingId);
          uploadIdRef.current = startResponse.upload_id;
          fileKeyRef.current = startResponse.file_key;
          recordingIdRef.current = startResponse.recording_id;
          partNumberRef.current = 1;
          uploadedPartsRef.current = [];
          chunkQueue.current = [];
        } catch (err) {
          setError("Failed to initialize recording stream on the server.");
          console.error("Stream start error:", err);
          return;
        }

        // Use webm or default
        const options = MediaRecorder.isTypeSupported("audio/webm")
          ? { mimeType: "audio/webm" }
          : undefined;
        const recorder = new MediaRecorder(stream, options);
        mediaRecorder.current = recorder;

        recorder.ondataavailable = (event) => {
          if (event.data.size > 0) {
            console.log("Chunk available, size:", event.data.size);
            chunkQueue.current.push(event.data);
            processChunkQueue();
          }
        };

        // Start recording and emit chunks every 10 seconds (10000ms)
        recorder.start(10000);
        setIsRecording(true);
        setIsPaused(false);
        setDuration(0);
        setError(null);

        // Poll backend for recording duration (synchronized across all participants)
        timerInterval.current = window.setInterval(async () => {
          try {
            const statusResponse = await meetingsApi.getRecordingStatus(meetingId);
            setDuration(statusResponse.recording_duration);
          } catch (err) {
            console.error("Failed to fetch recording status:", err);
          }
        }, 1000);
      } catch (err) {
        setError("An unexpected error occurred while starting the recording.");
        console.error("Error starting recording:", err);
      }
    },
    [processChunkQueue],
  );

  const pauseRecording = useCallback(() => {
    if (mediaRecorder.current && isRecording && !isPaused) {
      mediaRecorder.current.pause();
      setIsPaused(true);
      if (timerInterval.current) {
        clearInterval(timerInterval.current);
      }
    }
  }, [isRecording, isPaused]);

  const resumeRecording = useCallback(() => {
    if (mediaRecorder.current && isRecording && isPaused) {
      mediaRecorder.current.resume();
      setIsPaused(false);

      // Resume backend polling for recording duration
      if (currentMeetingId.current) {
        timerInterval.current = window.setInterval(async () => {
          try {
            const statusResponse = await meetingsApi.getRecordingStatus(currentMeetingId.current!);
            setDuration(statusResponse.recording_duration);
          } catch (err) {
            console.error("Failed to fetch recording status:", err);
          }
        }, 1000);
      }
    }
  }, [isRecording, isPaused]);

  const stopRecording = useCallback(
    (meetingId: string): Promise<any | null> => {
      return new Promise((resolve) => {
        if (mediaRecorder.current && isRecording) {
          isStoppingRef.current = true;
          
          mediaRecorder.current.onstop = async () => {
            console.log("MediaRecorder stopped. Finalizing uploads...");
            
            // Stop all tracks to release microphone
            mediaRecorder.current?.stream
              .getTracks()
              .forEach((track) => track.stop());

            if (timerInterval.current) {
              clearInterval(timerInterval.current);
            }
            setIsRecording(false);
            setIsPaused(false);

            // Give ondataavailable a chance to fire for the last data chunk
            await new Promise(r => setTimeout(r, 500));

            // Wait for any pending uploads to finish (Wait up to 10 seconds)
            let waitCount = 0;
            while ((isUploadingRef.current || chunkQueue.current.length > 0) && waitCount < 20) {
              console.log("Waiting for last chunks to upload...");
              await new Promise((r) => setTimeout(r, 500));
              waitCount++;
            }

            if (
              recordingIdRef.current &&
              uploadIdRef.current &&
              fileKeyRef.current
            ) {
              try {
                console.log("Finalizing stream for meeting:", meetingId, "Parts:", uploadedPartsRef.current.length);

                const response = await meetingsApi.stopStream(
                  recordingIdRef.current,
                  uploadIdRef.current,
                  fileKeyRef.current,
                  uploadedPartsRef.current,
                );
                console.log("Upload/Stream finalized successfully:", response);
                resolve(response);
              } catch (err: any) {
                console.error(
                  "Failed to finalize recording stream. Status:",
                  err.response?.status,
                  "Data:",
                  err.response?.data,
                );
                setError(
                  `Failed to save recording to server. (${err.response?.status || "Network Error"})`,
                );
                resolve(null);
              }
            } else {
              console.warn("Missing stream identifiers on stop.");
              resolve(null);
            }
          };

          // Request final data and stop
          mediaRecorder.current.requestData();
          mediaRecorder.current.stop();
        } else {
          resolve(null);
        }
      });
    },
    [isRecording],
  );

  return {
    isRecording,
    isPaused,
    duration,
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
    error,
  };
};
