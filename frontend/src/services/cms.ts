import api from "./api";

export const cmsService = {
  getLandingContent: async (lang: string = "en") => {
    const response = await api.get(`/cms/landing?lang=${lang}`);
    return response.data;
  },

  getFeatures: async (lang: string = "en") => {
    const response = await api.get(`/cms/features?lang=${lang}`);
    return response.data;
  },

  getPricing: async (lang: string = "en") => {
    const response = await api.get(`/cms/pricing?lang=${lang}`);
    return response.data;
  },

  getFAQs: async (lang: string = "en") => {
    const response = await api.get(`/cms/faq?lang=${lang}`);
    return response.data;
  },

  updateSection: async (sectionId: string, data: any) => {
    const response = await api.put(`/cms/sections/${sectionId}`, data);
    return response.data;
  },

  updateFeature: async (featureId: string, data: any) => {
    const response = await api.put(`/cms/features/${featureId}`, data);
    return response.data;
  },

  updatePricingPlan: async (planId: string, data: any) => {
    const response = await api.put(`/cms/pricing/${planId}`, data);
    return response.data;
  },

  updateFAQ: async (faqId: string, data: any) => {
    const response = await api.put(`/cms/faq/${faqId}`, data);
    return response.data;
  },
};

export default cmsService;