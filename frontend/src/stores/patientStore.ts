import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Patient, Medication, DashboardStats, Theme } from '@/types';

interface PatientState {
  // Current patient
  currentPatient: Patient | null;
  setCurrentPatient: (patient: Patient | null) => void;

  // Per-day taken tracker (medicationId-date -> true)
  takenToday: Record<string, boolean>;
  setTakenToday: (key: string, taken: boolean) => void;
  
  // Medications
  medications: Medication[];
  setMedications: (medications: Medication[]) => void;
  addMedication: (medication: Medication) => void;
  updateMedication: (id: number, medication: Partial<Medication>) => void;
  removeMedication: (id: number) => void;
  
  // Dashboard stats
  dashboardStats: DashboardStats | null;
  setDashboardStats: (stats: DashboardStats) => void;
  
  // Theme
  theme: Theme;
  setTheme: (theme: Theme) => void;
  
  // UI State
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  
  // Notifications
  notificationCount: number;
  setNotificationCount: (count: number) => void;
  incrementNotificationCount: () => void;
  clearNotifications: () => void;
  
  // Loading states
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  
  // Error handling
  error: string | null;
  setError: (error: string | null) => void;
  clearError: () => void;
  
  // Reset store (for logout)
  resetStore: () => void;
}

export const usePatientStore = create<PatientState>()(
  persist(
    (set) => ({
      // Current patient
      currentPatient: null,
      setCurrentPatient: (patient) =>
        set((state) => ({
          currentPatient: patient,
          // Keep takenToday map keyed by patient id+date so logout/login preserves same-day status
          dashboardStats: patient && state.currentPatient?.id !== patient.id ? null : state.dashboardStats,
          activeTab: 'dashboard',
        })),

      // Taken tracker
      takenToday: {},
      setTakenToday: (key, taken) =>
        set((state) => ({ takenToday: { ...state.takenToday, [key]: taken } })),
      
      // Medications
      medications: [],
      setMedications: (medications) => set({ medications }),
      addMedication: (medication) =>
        set((state) => ({ medications: [...state.medications, medication] })),
      updateMedication: (id, medication) =>
        set((state) => ({
          medications: state.medications.map((m) =>
            m.id === id ? { ...m, ...medication } : m
          ),
        })),
      removeMedication: (id) =>
        set((state) => ({
          medications: state.medications.filter((m) => m.id !== id),
        })),
      
      // Dashboard stats
      dashboardStats: null,
      setDashboardStats: (stats) => set({ dashboardStats: stats }),
      
      // Theme
      theme: 'dark',
      setTheme: (theme) => {
        // Apply theme to document
        const root = window.document.documentElement;
        root.classList.remove('light', 'dark');
        
        if (theme === 'system') {
          const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches
            ? 'dark'
            : 'light';
          root.classList.add(systemTheme);
        } else {
          root.classList.add(theme);
        }
        
        set({ theme });
      },
      
      // UI State
      sidebarOpen: true,
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      activeTab: 'dashboard',
      setActiveTab: (tab) => set({ activeTab: tab }),
      
      // Notifications
      notificationCount: 0,
      setNotificationCount: (count) => set({ notificationCount: count }),
      incrementNotificationCount: () =>
        set((state) => ({ notificationCount: state.notificationCount + 1 })),
      clearNotifications: () => set({ notificationCount: 0 }),
      
      // Loading states
      isLoading: false,
      setIsLoading: (loading) => set({ isLoading: loading }),
      
      // Error handling
      error: null,
      setError: (error) => set({ error }),
      clearError: () => set({ error: null }),
      
      // Reset store (for logout)
      resetStore: () => {
        set({
          currentPatient: null, // Set to null to show login/signup page
          medications: [],
          dashboardStats: null,
          // Preserve theme and takenToday so the next login keeps preferences and same-day marks
          sidebarOpen: true,
          activeTab: 'dashboard',
          notificationCount: 0,
          isLoading: false,
          error: null,
        });
      },
    }),
    {
      name: 'adherence-guardian-storage',
      version: 2,
      migrate: (persistedState: any) => {
        const state = persistedState?.state || {};
        // Drop the old mock patient and reset taken map
        if (state?.currentPatient?.email === 'john.doe@example.com') {
          return {
            ...state,
            currentPatient: null,
            takenToday: {},
          };
        }

        // Normalize missing names for newly created users
        const cp = state.currentPatient;
        let normalizedPatient = cp;
        if (cp && (!cp.name || cp.name.includes('undefined'))) {
          const fallbackName = cp.email ? (cp.email.split('@')[0] || 'New User') : 'New User';
          normalizedPatient = { ...cp, name: fallbackName };
        }

        return {
          ...state,
          currentPatient: normalizedPatient,
          takenToday: state?.takenToday || {},
        };
      },
      // Do not persist authenticated user so app always opens on the login screen
      partialize: (state) => ({
        theme: state.theme,
        sidebarOpen: state.sidebarOpen,
        takenToday: state.takenToday,
      }),
    }
  )
);

// Initialize theme on load
if (typeof window !== 'undefined') {
  const stored = localStorage.getItem('adherence-guardian-storage');
  if (stored) {
    try {
      const { state } = JSON.parse(stored);
      if (state?.theme) {
        const root = window.document.documentElement;
        root.classList.remove('light', 'dark');
        
        if (state.theme === 'system') {
          const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches
            ? 'dark'
            : 'light';
          root.classList.add(systemTheme);
        } else {
          root.classList.add(state.theme);
        }
      }
    } catch (e) {
      console.error('Failed to parse stored state:', e);
    }
  }
}
