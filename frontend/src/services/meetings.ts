import api from "./api";
import auditService from "./auditService";

export const meetingsApi = {
  getUsers: async () => {
    const response = await api.get("/meetings/users");
    return response.data;
  },

  getMeetings: async () => {
    const response = await api.get("/meetings/");
    return response.data;
  },

  getMeeting: async (id: string) => {
    const response = await api.get(`/meetings/${id}`);
    return response.data;
  },

  createMeeting: async (data: any) => {
    const response = await api.post("/meetings/", data);
    // Log creation for audit trail
    if (response.data?.id) {
      await auditService.logCreate('meetings', response.data.id, { title: data.title });
    }
    return response.data;
  },

  uploadRecording: async (
    meetingId: string,
    file: File,
    recordingId?: string,
  ) => {
    const formData = new FormData();
    formData.append("file", file);
    if (recordingId) {
      formData.append("recording_id", recordingId);
    }
    return api.post(`/recordings/upload/${meetingId}`, formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
  },

  startStream: async (meetingId: string) => {
    const response = await api.post(`/recordings/stream/start/${meetingId}`);
    return response.data;
  },

  uploadStreamChunk: async (
    uploadId: string,
    fileKey: string,
    partNumber: number,
    blob: Blob,
  ) => {
    const formData = new FormData();
    formData.append("upload_id", uploadId);
    formData.append("file_key", fileKey);
    formData.append("part_number", partNumber.toString());
    formData.append("file", blob);
    const response = await api.post(`/recordings/stream/chunk`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  },

  stopStream: async (
    recordingId: string,
    uploadId: string,
    fileKey: string,
    parts: any[],
  ) => {
    const response = await api.post(
      `/recordings/stream/stop/${recordingId}?upload_id=${uploadId}&file_key=${fileKey}`,
      { parts },
    );
    return response.data;
  },

  getRecordingStatus: async (meetingId: string) => {
    const response = await api.get(`/meetings/${meetingId}/recording-status`);
    return response.data;
  },

  getTranscription: async (meetingId: string) => {
    const response = await api.get(`/transcriptions/meeting/${meetingId}`);
    return response.data;
  },
};

// Keep existing exports if they were used elsewhere to avoid breaking changes
export const getMeetings = meetingsApi.getMeetings;
