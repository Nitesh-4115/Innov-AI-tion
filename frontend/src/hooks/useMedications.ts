import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { medicationApi, scheduleApi } from '@/services/api';
import { usePatientStore } from '@/stores/patientStore';
import type { Medication, Schedule, DrugInteraction } from '@/types';

export function useMedications(patientId: number | null) {
  const setMedications = usePatientStore((state) => state.setMedications);
  
  return useQuery({
    queryKey: ['medications', patientId],
    queryFn: async () => {
      if (!patientId) return [];
      const medications = await medicationApi.getByPatient(patientId);
      setMedications(medications);
      return medications;
    },
    enabled: !!patientId,
    refetchInterval: 15000,
    refetchOnWindowFocus: true,
    staleTime: 0,
  });
}

export function useMedication(patientId: number | null, medicationId: number | null) {
  return useQuery({
    queryKey: ['medication', patientId, medicationId],
    queryFn: async () => {
      if (!patientId || !medicationId) return null;
      return medicationApi.getById(patientId, medicationId);
    },
    enabled: !!patientId && !!medicationId,
  });
}

export function useCreateMedication() {
  const queryClient = useQueryClient();
  const addMedication = usePatientStore((state) => state.addMedication);
  
  return useMutation({
    mutationFn: async ({ patientId, medication, customTimes }: { patientId: number; medication: Partial<Medication>; customTimes?: string[] }) => {
      // Attach custom times to medication payload so backend creates schedule atomically
      if (customTimes && customTimes.length > 0) {
        (medication as any).custom_times = customTimes;
      }
      const newMed = await medicationApi.create(patientId, medication);
      // If no custom times were provided, we can still trigger optimization to refine the schedule
      if (!customTimes || customTimes.length === 0) {
        scheduleApi.optimize(patientId).catch((err) => console.error('Schedule optimize failed', err));
      }
      return newMed;
    },
    onSuccess: (newMedication, { patientId }) => {
      queryClient.invalidateQueries({ queryKey: ['medications', patientId] });
      queryClient.invalidateQueries({ queryKey: ['dashboardStats', patientId] });
      queryClient.invalidateQueries({ queryKey: ['todaySchedule', patientId] });
      addMedication(newMedication);
    },
  });
}

export function useUpdateMedication() {
  const queryClient = useQueryClient();
  const updateMedication = usePatientStore((state) => state.updateMedication);
  
  return useMutation({
    mutationFn: ({
      patientId,
      medicationId,
      medication,
    }: {
      patientId: number;
      medicationId: number;
      medication: Partial<Medication>;
    }) => medicationApi.update(patientId, medicationId, medication),
    onSuccess: (updatedMedication, { patientId }) => {
      queryClient.invalidateQueries({ queryKey: ['medications', patientId] });
      queryClient.invalidateQueries({ queryKey: ['medication', patientId, updatedMedication.id] });
      updateMedication(updatedMedication.id, updatedMedication);
    },
  });
}

export function useDeleteMedication() {
  const queryClient = useQueryClient();
  const removeMedication = usePatientStore((state) => state.removeMedication);
  
  return useMutation({
    mutationFn: ({ patientId, medicationId }: { patientId: number; medicationId: number }) =>
      medicationApi.delete(patientId, medicationId),
    onSuccess: (_, { patientId, medicationId }) => {
      queryClient.invalidateQueries({ queryKey: ['medications', patientId] });
      queryClient.invalidateQueries({ queryKey: ['dashboardStats', patientId] });
      removeMedication(medicationId);
    },
  });
}

export function useDrugInteractions(patientId: number | null) {
  return useQuery<DrugInteraction[]>({
    queryKey: ['drugInteractions', patientId],
    queryFn: async () => {
      if (!patientId) return [];
      return medicationApi.checkInteractions(patientId);
    },
    enabled: !!patientId,
  });
}

export function useMedicationSideEffects(medicationId: number | null) {
  return useQuery<string[]>({
    queryKey: ['sideEffects', medicationId],
    queryFn: async () => {
      if (!medicationId) return [];
      return medicationApi.getSideEffects(medicationId);
    },
    enabled: !!medicationId,
  });
}

// Schedule hooks
export function useSchedules(patientId: number | null) {
  return useQuery({
    queryKey: ['schedules', patientId],
    queryFn: async () => {
      if (!patientId) return [];
      return scheduleApi.getByPatient(patientId);
    },
    enabled: !!patientId,
  });
}

export function useTodaySchedule(patientId: number | null) {
  return useQuery({
    queryKey: ['todaySchedule', patientId],
    queryFn: async () => {
      if (!patientId) return [];
      return scheduleApi.getTodaySchedule(patientId);
    },
    enabled: !!patientId,
    refetchInterval: 30000, // Refresh every 30s for live dashboard/meds
    refetchOnWindowFocus: true,
    staleTime: 0,
  });
}

export function useCreateSchedule() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ patientId, schedule }: { patientId: number; schedule: Partial<Schedule> }) =>
      scheduleApi.create(patientId, schedule),
    onSuccess: (_, { patientId }) => {
      queryClient.invalidateQueries({ queryKey: ['schedules', patientId] });
      queryClient.invalidateQueries({ queryKey: ['todaySchedule', patientId] });
    },
  });
}

export function useOptimizeSchedule() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (patientId: number) => scheduleApi.optimize(patientId),
    onSuccess: (_, patientId) => {
      queryClient.invalidateQueries({ queryKey: ['schedules', patientId] });
      queryClient.invalidateQueries({ queryKey: ['todaySchedule', patientId] });
    },
  });
}
