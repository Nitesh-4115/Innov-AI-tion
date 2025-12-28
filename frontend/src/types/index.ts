// Patient types
export interface Patient {
  id: number;
  name: string;
  email: string;
  phone?: string;
  date_of_birth?: string;
  timezone: string;
  conditions: string[];
  allergies: string[];
  emergency_contact?: string;
  notification_preferences: NotificationPreferences;
  created_at: string;
  updated_at: string;
  is_active: boolean;
  avatar_url?: string;
}

export interface NotificationPreferences {
  email: boolean;
  sms: boolean;
  push: boolean;
  reminder_minutes_before: number;
}

// Medication types
export interface Medication {
  id: number;
  patient_id: number;
  name: string;
  generic_name?: string;
  dosage: string;
  frequency: string;
  route: string;
  instructions?: string;
  purpose?: string;
  prescriber?: string;
  pharmacy?: string;
  refills_remaining?: number;
  is_active: boolean;
  start_date: string;
  end_date?: string;
  rxcui?: string;
  created_at: string;
}

// Schedule types
export interface Schedule {
  id: number;
  patient_id: number;
  medication_id: number;
  medication?: Medication;
  scheduled_time: string;
  days_of_week: string[];
  with_food: boolean;
  special_instructions?: string;
  is_active: boolean;
  created_at: string;
}

export interface ScheduleItem {
  id: number;
  medication_id?: number;
  medication_name: string;
  dosage: string;
  scheduled_time: string;
  status: 'pending' | 'taken' | 'missed' | 'skipped';
  with_food: boolean;
  instructions?: string;
  special_instructions?: string;
  taken_at?: string;
}

// Adherence types
export interface AdherenceLog {
  id: number;
  patient_id: number;
  schedule_id: number;
  medication_id: number;
  status: AdherenceStatus;
  scheduled_time?: string;
  taken_at?: string;
  deviation_minutes?: number;
  notes?: string;
  reported_by: string;
  logged_at: string;
}

export type AdherenceStatus = 'taken' | 'missed' | 'skipped' | 'delayed';

export interface AdherenceRate {
  adherence_rate: number;
  total_doses: number;
  taken: number;
  missed: number;
  skipped: number;
  delayed: number;
  average_deviation_minutes: number;
  days_analyzed: number;
}

export interface AdherenceStreak {
  current_streak: number;
  best_streak: number;
  streak_start?: string;
}

export interface AdherenceTrend {
  date: string;
  adherence_rate: number;
  rate?: number;
  taken: number;
  missed: number;
}

// Symptom types
export interface SymptomReport {
  id: number;
  patient_id: number;
  medication_id?: number;
  symptom_name: string;
  severity: string;
  notes?: string;
  reported_at: string;
}

// Chat types
export interface ChatMessage {
  id: number;
  patient_id: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
  metadata?: {
    agent?: string;
    action?: string;
    sources?: string[];
  };
}

export interface ChatResponse {
  response: string;
  agent_used?: string;
  actions_taken?: string[];
  sources?: string[];
  suggested_actions?: {
    id: string;
    label: string;
    type: string;
  }[];
}

// Agent Activity types
export interface AgentActivity {
  id: string;
  agent_name: string;
  action: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  timestamp: string;
  details?: Record<string, unknown>;
}

// Drug Interaction types
export interface DrugInteraction {
  drug1_name: string;
  drug2_name: string;
  severity: string;
  description: string;
  mechanism?: string;
  clinical_effects?: string;
  management?: string;
}

// Dashboard types
export interface DashboardStats {
  adherence_rate: number;
  adherence_trend: number;
  current_streak: number;
  best_streak: number;
  active_medications: number;
  next_dose?: {
    medication_name: string;
    scheduled_time: string;
    time_until: string;
  };
}

// API Response types
export interface ApiResponse<T> {
  data: T;
  message?: string;
  success: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// Theme types
export type Theme = 'light' | 'dark' | 'system';

// Quick Action types
export interface QuickAction {
  id: string;
  label: string;
  icon: string;
  action: string;
  variant?: 'default' | 'success' | 'warning' | 'destructive';
}
