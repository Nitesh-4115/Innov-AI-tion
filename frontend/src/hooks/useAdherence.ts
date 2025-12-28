import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { adherenceApi, symptomApi } from '@/services/api';
import type { AdherenceRate, AdherenceStreak, AdherenceTrend, AdherenceLog, SymptomReport } from '@/types';

export function useAdherenceRate(patientId: number | null, days: number = 30, medicationId?: number) {
  return useQuery<AdherenceRate | null>({
    queryKey: ['adherenceRate', patientId, days, medicationId],
    queryFn: async () => {
      if (!patientId) return null;
      return adherenceApi.getRate(patientId, days, medicationId);
    },
    enabled: !!patientId,
    refetchInterval: 60000,
  });
}

export function useAdherenceStreak(patientId: number | null) {
  return useQuery<AdherenceStreak | null>({
    queryKey: ['adherenceStreak', patientId],
    queryFn: async () => {
      if (!patientId) return null;
      return adherenceApi.getStreak(patientId);
    },
    enabled: !!patientId,
    refetchInterval: 60000,
  });
}

export function useAdherenceTrends(patientId: number | null, days: number = 30) {
  return useQuery<AdherenceTrend[]>({
    queryKey: ['adherenceTrends', patientId, days],
    queryFn: async () => {
      if (!patientId) return [];
      return adherenceApi.getTrends(patientId, days);
    },
    enabled: !!patientId,
  });
}

export function useAdherenceHistory(
  patientId: number | null,
  startDate?: string,
  endDate?: string
) {
  return useQuery<AdherenceLog[]>({
    queryKey: ['adherenceHistory', patientId, startDate, endDate],
    queryFn: async () => {
      if (!patientId) return [];
      return adherenceApi.getHistory(patientId, startDate, endDate);
    },
    enabled: !!patientId,
  });
}

export function useLogDose(patientId: number | null) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: {
      schedule_id: number;
      medication_id?: number;
      status: string;
      scheduled_time?: string;
      taken_at?: string;
      notes?: string;
    }) => {
      if (!patientId) throw new Error('Patient ID is required');
      return adherenceApi.logDose(patientId, {
        ...data,
        medication_id: data.medication_id || 0,
      });
    },
    // Optimistic update: update the todaySchedule cache immediately so UI updates live
    onMutate: async (vars) => {
      if (!patientId) return {};
      await queryClient.cancelQueries({ queryKey: ['todaySchedule', patientId] });
      const previous = queryClient.getQueryData<any[]>(['todaySchedule', patientId]);

      // Apply optimistic update
      if (previous) {
        const updated = previous.map((item: any) => {
          if (vars.schedule_id && item.id === vars.schedule_id) {
            return {
              ...item,
              status: vars.status,
              taken_at: vars.taken_at ?? (vars.status === 'taken' ? new Date().toISOString() : item.taken_at),
            };
          }
          // Fallback: if schedule_id not provided, match by medication_id + scheduled_time
          if (!vars.schedule_id && vars.medication_id && item.medication_id === vars.medication_id) {
            return {
              ...item,
              status: vars.status,
              taken_at: vars.taken_at ?? (vars.status === 'taken' ? new Date().toISOString() : item.taken_at),
            };
          }
          return item;
        });

        queryClient.setQueryData(['todaySchedule', patientId], updated);
      }

      return { previous };
    },
    onError: (_err, _vars, context: any) => {
      // Rollback optimistic update
      if (!patientId) return;
      if (context?.previous) {
        queryClient.setQueryData(['todaySchedule', patientId], context.previous);
      }
    },
    onSettled: () => {
      if (!patientId) return;
      // Ensure fresh data from server after mutation settles
      queryClient.invalidateQueries({ queryKey: ['adherenceRate', patientId] });
      queryClient.invalidateQueries({ queryKey: ['adherenceStreak', patientId] });
      queryClient.invalidateQueries({ queryKey: ['adherenceTrends', patientId] });
      queryClient.invalidateQueries({ queryKey: ['adherenceHistory', patientId] });
      queryClient.invalidateQueries({ queryKey: ['todaySchedule', patientId] });
      queryClient.invalidateQueries({ queryKey: ['dashboardStats', patientId] });
    },
  });
}

// Simple hook to mark a medication as taken
export function useMarkMedicationTaken(patientId: number | null) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (medicationId: number) => {
      if (!patientId) throw new Error('Patient ID is required');
      return adherenceApi.logDose(patientId, {
        schedule_id: 0, // Will use medication_id primarily
        medication_id: medicationId,
        status: 'taken',
        taken_at: new Date().toISOString(),
      });
    },
    onSuccess: () => {
      if (!patientId) return;
      // Invalidate all adherence-related queries
      queryClient.invalidateQueries({ queryKey: ['adherenceRate', patientId] });
      queryClient.invalidateQueries({ queryKey: ['adherenceStreak', patientId] });
      queryClient.invalidateQueries({ queryKey: ['adherenceTrends', patientId] });
      queryClient.invalidateQueries({ queryKey: ['adherenceHistory', patientId] });
      queryClient.invalidateQueries({ queryKey: ['todaySchedule', patientId] });
      queryClient.invalidateQueries({ queryKey: ['dashboardStats', patientId] });
    },
  });
}

// Helper hook to get formatted adherence data for charts
export function useAdherenceChartData(patientId: number | null, days: number = 30) {
  const { data: trends, isLoading, error } = useAdherenceTrends(patientId, days);
  
  const chartData = trends?.map((trend) => ({
    date: new Date(trend.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    rate: trend.rate,
    taken: trend.taken,
    missed: trend.missed,
  })) || [];
  
  return { chartData, isLoading, error };
}

// Symptom hooks
export function useSymptoms(patientId: number | null, days?: number) {
  return useQuery<SymptomReport[]>({
    queryKey: ['symptoms', patientId, days],
    queryFn: async () => {
      if (!patientId) return [];
      return symptomApi.getByPatient(patientId, days);
    },
    enabled: !!patientId,
  });
}

export function useCreateSymptom(patientId: number | null) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: Partial<SymptomReport>) => {
      if (!patientId) throw new Error('Patient ID is required');
      return symptomApi.report(patientId, data);
    },
    onSuccess: () => {
      if (!patientId) return;
      queryClient.invalidateQueries({ queryKey: ['symptoms', patientId] });
    },
  });
}
