import api from './api';

export const meetingsApi = {
  getMeetings: async () => {
    const response = await api.get('/meetings');
    return response.data;
  },

  getMeeting: async (id: string) => {
    const response = await api.get(`/meetings/${id}`);
    return response.data;
  },

  createMeeting: async (data: any) => {
    const response = await api.post('/meetings', data);
    return response.data;
  },

  uploadRecording: async (meetingId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/recordings/upload/${meetingId}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },

  getTranscription: async (meetingId: string) => {
    const response = await api.get(`/transcriptions/meeting/${meetingId}`);
    return response.data;
  }
};

// Keep existing exports if they were used elsewhere to avoid breaking changes
export const getMeetings = meetingsApi.getMeetings;