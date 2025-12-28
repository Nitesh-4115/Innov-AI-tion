import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  Patient,
  Medication,
  Schedule,
  AdherenceLog,
  AdherenceRate,
  AdherenceStreak,
  AdherenceTrend,
  SymptomReport,
  ChatResponse,
  DrugInteraction,
  DashboardStats,
  ScheduleItem,
  AgentActivity,
} from '@/types';
import { loadChatSession } from '@/lib/chatSession';

// Create axios instance - Updated to match backend API prefix
const api: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // Don't redirect on 401 for now, just reject
    console.error('API Error:', error.response?.status, error.message);
    return Promise.reject(error);
  }
);

// ============================================================================
// Patient API
// ============================================================================

export const patientApi = {
  getAll: async (): Promise<Patient[]> => {
    const response = await api.get('/patients');
    return response.data;
  },

  getById: async (id: number): Promise<Patient> => {
    const response = await api.get(`/patients/${id}`);
    return response.data;
  },

  create: async (patient: Partial<Patient>): Promise<Patient> => {
    const response = await api.post('/patients', patient);
    return response.data;
  },

  update: async (id: number, patient: Partial<Patient>): Promise<Patient> => {
    const response = await api.put(`/patients/${id}`, patient);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/patients/${id}`);
  },

  getDashboardStats: async (id: number): Promise<DashboardStats> => {
    const response = await api.get(`/patients/${id}/insights`);
    return response.data;
  },
};

// ============================================================================
// Medication API
// ============================================================================

// Transform backend medication response to frontend format
const transformMedication = (med: any): Medication => ({
  ...med,
  is_active: med.active ?? med.is_active ?? true, // Map 'active' to 'is_active'
});

export const medicationApi = {
  getByPatient: async (patientId: number): Promise<Medication[]> => {
    const response = await api.get(`/patients/${patientId}/medications`);
    // Transform backend 'active' field to frontend 'is_active'
    return (response.data || []).map(transformMedication);
  },

  getById: async (patientId: number, medicationId: number): Promise<Medication> => {
    const response = await api.get(`/patients/${patientId}/medications/${medicationId}`);
    return transformMedication(response.data);
  },

  create: async (patientId: number, medication: Partial<Medication>): Promise<Medication> => {
    const response = await api.post(`/patients/${patientId}/medications`, medication);
    return response.data;
  },

  update: async (
    patientId: number,
    medicationId: number,
    medication: Partial<Medication>
  ): Promise<Medication> => {
    const response = await api.put(
      `/patients/${patientId}/medications/${medicationId}`,
      medication
    );
    return transformMedication(response.data);
  },

  delete: async (patientId: number, medicationId: number): Promise<void> => {
    await api.delete(`/patients/${patientId}/medications/${medicationId}`);
  },

  checkInteractions: async (patientId: number): Promise<DrugInteraction[]> => {
    // Backend doesn't have this endpoint yet, return empty array
    return [];
  },

  getSideEffects: async (medicationId: number): Promise<string[]> => {
    return [];
  },

  searchDrugs: async (query: string, limit: number = 10): Promise<{ name: string; generic_name: string; drug_class: string }[]> => {
    try {
      const response = await api.get(`/medications/search?query=${encodeURIComponent(query)}&limit=${limit}`);
      return response.data || [];
    } catch (error) {
      console.error('Error searching drugs:', error);
      return [];
    }
  },
};

// ============================================================================
// Schedule API - Matches backend /schedule/today (not /schedules/today)
// ============================================================================

export const scheduleApi = {
  getByPatient: async (patientId: number): Promise<Schedule[]> => {
    const response = await api.get(`/patients/${patientId}/schedule/today`);
    return response.data;
  },

  getTodaySchedule: async (patientId: number): Promise<ScheduleItem[]> => {
    const response = await api.get(`/patients/${patientId}/schedule/today`);
    // Transform backend response to match frontend ScheduleItem interface
    const data = response.data;
    if (Array.isArray(data)) {
      return data.map((item: any) => ({
        id: item.id ?? item.schedule_id ?? item.scheduleId,
        medication_id: item.medication_id,
        medication_name:
          item.medication_name ||
          item.medications?.[0] ||
          item.medications_list?.[0] ||
          'Unknown',
        dosage: item.dosage || '',
        scheduled_time: item.scheduled_time || item.time || item.scheduledTime || '00:00',
        scheduled_date: item.scheduled_date || item.date || null,
        is_next: !!item.is_next,
        status: item.status || item.state || 'pending',
        with_food: item.with_food ?? item.meal_relation === 'with_meal',
        instructions: item.instructions || item.notes,
      }));
    }
    return [];
  },

  create: async (patientId: number, schedule: Partial<Schedule>): Promise<Schedule> => {
    const response = await api.post(`/patients/${patientId}/schedule/regenerate`, schedule);
    return response.data;
  },

  createCustom: async (
    patientId: number,
    payload: { medication_id: number; times: string[]; scheduled_date?: string; meal_relation?: string; notes?: string }
  ): Promise<Schedule[]> => {
    const response = await api.post(`/patients/${patientId}/schedule/custom`, payload);
    return response.data as Schedule[];
  },

  update: async (
    patientId: number,
    scheduleId: number,
    schedule: Partial<Schedule>
  ): Promise<Schedule> => {
    // Not implemented in backend
    return schedule as Schedule;
  },

  delete: async (patientId: number, scheduleId: number): Promise<void> => {
    // Not implemented in backend
  },

  optimize: async (patientId: number): Promise<Schedule[]> => {
    const response = await api.post(`/patients/${patientId}/schedule/regenerate`);
    return response.data;
  },
};

// ============================================================================
// Adherence API - Backend uses /adherence/stats instead of /adherence/rate
// ============================================================================

export const adherenceApi = {
  logDose: async (
    patientId: number,
    data: {
      schedule_id: number;
      medication_id: number;
      status: string;
      scheduled_time?: string;
      taken_at?: string;
      notes?: string;
    }
  ): Promise<AdherenceLog> => {
    // Backend uses /adherence/log with medication_id in body
    // Ensure schedule_id is sent so the backend can update the schedule row
    const scheduledAt = data.scheduled_time
      ? (() => {
          const [h, m] = data.scheduled_time.split(':').map(Number);
          const d = new Date();
          d.setHours(h || 0, m || 0, 0, 0);
          return d.toISOString();
        })()
      : new Date().toISOString();

    const response = await api.post(`/adherence/log`, {
      medication_id: data.medication_id,
      schedule_id: data.schedule_id,
      scheduled_time: scheduledAt,
      actual_time: data.taken_at,
      taken: data.status === 'taken',
      skip_reason: data.status === 'skipped' ? 'User skipped' : undefined,
      notes: data.notes,
    });
    return response.data;
  },

  // Backend has /adherence/stats which combines rate, streak, and trends
  getStats: async (patientId: number, days: number = 30): Promise<any> => {
    const response = await api.get(`/patients/${patientId}/adherence/stats?days=${days}`);
    return response.data;
  },

  getRate: async (
    patientId: number,
    days?: number,
    medicationId?: number
  ): Promise<AdherenceRate> => {
    // Use the combined stats endpoint
    const response = await api.get(`/patients/${patientId}/adherence/stats?days=${days || 30}`);
    const data = response.data;
    return {
      adherence_rate: data.adherence_rate || 0,
      total_doses: data.total_doses || 0,
      taken: data.doses_taken || 0,
      missed: data.doses_missed || 0,
      skipped: 0,
      delayed: data.doses_delayed || 0,
      average_deviation_minutes: 0,
      days_analyzed: data.period_days || days || 30,
    };
  },

  getStreak: async (patientId: number): Promise<AdherenceStreak> => {
    // Use the combined stats endpoint
    const response = await api.get(`/patients/${patientId}/adherence/stats`);
    const data = response.data;
    return {
      current_streak: data.current_streak || 0,
      best_streak: data.current_streak || 0, // Backend might not track best
    };
  },

  getTrends: async (patientId: number, days?: number): Promise<AdherenceTrend[]> => {
    // Use the new daily endpoint to fetch per-day adherence metrics
    const response = await api.get(`/patients/${patientId}/adherence/daily?days=${days || 30}`);
    const data = response.data;
    if (!data || !data.daily) return [];

    return (data.daily || []).map((d: any) => ({
      date: d.date,
      adherence_rate: d.adherence_rate || 0,
      taken: d.taken || 0,
      missed: d.missed || 0,
    }));
  },

  getHistory: async (
    patientId: number,
    startDate?: string,
    endDate?: string
  ): Promise<AdherenceLog[]> => {
    return [];
  },
};

// ============================================================================
// Symptom API - Backend uses /symptoms endpoints
// ============================================================================

export const symptomApi = {
  report: async (
    patientId: number,
    symptom: Partial<SymptomReport>
  ): Promise<SymptomReport> => {
    const severityMap: Record<string, number> = {
      mild: 3,
      moderate: 6,
      severe: 8,
    };
    const response = await api.post(`/symptoms/report?patient_id=${patientId}`, {
      medication_name: symptom.medication_name || '',
      symptom: symptom.symptom_name || 'Symptom',
      severity: typeof symptom.severity === 'number'
        ? symptom.severity
        : severityMap[String(symptom.severity || 'moderate').toLowerCase()] || 5,
      timing: symptom.reported_at || 'unspecified',
      description: symptom.notes,
    });
    const data = response.data;
    return {
      id: data.symptom_id || data.id,
      patient_id: patientId,
      symptom_name: symptom.symptom_name || '',
      severity: String(symptom.severity || 'moderate'),
      notes: symptom.notes,
      reported_at: new Date().toISOString(),
    };
  },

  getByPatient: async (patientId: number, days?: number): Promise<SymptomReport[]> => {
    try {
      const params = days ? `?days=${days}` : '';
      const response = await api.get(`/symptoms/patient/${patientId}${params}`);
      const data = response.data;
      if (data && data.symptoms) {
        return data.symptoms.map((s: any) => ({
          id: s.id,
          patient_id: s.patient_id,
          symptom_name: s.symptom_name,
          severity: String(s.severity),
          notes: s.description,
          reported_at: s.reported_at,
        }));
      }
      return [];
    } catch (error) {
      console.error('Error fetching symptoms:', error);
      return [];
    }
  },

  correlate: async (patientId: number): Promise<Record<string, unknown>> => {
    return {};
  },
};

// ============================================================================
// Chat API - Backend uses /chat (global, not patient-specific)
// ============================================================================

export const chatApi = {
  send: async (
    patientId: number,
    message: string,
    context?: Record<string, unknown>
  ): Promise<ChatResponse> => {
    const response = await api.post(`/chat`, {
      patient_id: patientId,
      message,
      context,
    });
    return response.data;
  },

  getHistory: async (patientId: number, limit?: number): Promise<any[]> => {
    // Fallback to localStorage since backend history is not yet persisted
    if (typeof window === 'undefined') return [];
    const key = `chat_session_${patientId}`;
    const stored = window.localStorage.getItem(key);
    if (!stored) return [];
    const parsed = JSON.parse(stored);
    return (parsed || []).slice(-(limit || 50));
  },

  quickAction: async (
    patientId: number,
    action: string,
    params?: Record<string, unknown>
  ): Promise<ChatResponse> => {
    const response = await api.post(`/chat`, {
      patient_id: patientId,
      message: action,
      context: params,
    });
    return response.data;
  },
};

// ============================================================================
// Agent Activity API - Backend uses /agent-activity (hyphenated)
// ============================================================================

export const agentApi = {
  getActivity: async (patientId: number, limit?: number): Promise<{ events: any[] }> => {
    const params = limit ? `?limit=${limit}` : '';
    const response = await api.get(`/patients/${patientId}/agent-activity${params}`);
    // Transform to expected format
    const data = response.data;
    if (Array.isArray(data)) {
      return {
        events: data.map((item: any) => ({
          id: item.id?.toString() || Math.random().toString(),
          agent: item.agent_name?.toLowerCase().replace(' ', '_') || 'orchestrator',
          action: item.action || 'Activity',
          status: item.status || 'completed',
          message: item.result || item.action || 'Agent activity',
          details: item.error_message,
          timestamp: item.created_at || new Date().toISOString(),
        })),
      };
    }
    return { events: [] };
  },

  getStatus: async (patientId: number): Promise<Record<string, unknown>> => {
    const response = await api.get(`/agents/status`);
    return response.data;
  },
};

// ============================================================================
// Reports API
// ============================================================================

export const reportApi = {
  generate: async (
    patientId: number,
    reportType: string,
    options?: Record<string, unknown>
  ): Promise<Blob> => {
    const response = await api.post(
      `/patients/${patientId}/provider-report`,
      { report_type: reportType, ...options },
      { responseType: 'blob' }
    );
    return response.data;
  },

  getProviderReport: async (patientId: number, days?: number): Promise<Record<string, unknown>> => {
    const params = days ? `?days=${days}` : '';
    const response = await api.get(`/patients/${patientId}/provider-report${params}`);
    return response.data;
  },
};

export default api;
