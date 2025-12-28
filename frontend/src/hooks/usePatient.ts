import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { patientApi } from '@/services/api';
import { usePatientStore } from '@/stores/patientStore';
import type { Patient, DashboardStats } from '@/types';

export function usePatients() {
  return useQuery({
    queryKey: ['patients'],
    queryFn: patientApi.getAll,
  });
}

export function usePatient(patientId: number | null) {
  const setCurrentPatient = usePatientStore((state) => state.setCurrentPatient);
  
  return useQuery({
    queryKey: ['patient', patientId],
    queryFn: async () => {
      if (!patientId) return null;
      const patient = await patientApi.getById(patientId);
      setCurrentPatient(patient);
      return patient;
    },
    enabled: !!patientId,
  });
}

export function useDashboardStats(patientId: number | null) {
  const setDashboardStats = usePatientStore((state) => state.setDashboardStats);
  
  return useQuery({
    queryKey: ['dashboardStats', patientId],
    queryFn: async (): Promise<DashboardStats | null> => {
      if (!patientId) return null;
      const stats = await patientApi.getDashboardStats(patientId);
      setDashboardStats(stats);
      return stats;
    },
    enabled: !!patientId,
    refetchInterval: 60000, // Refresh every minute
  });
}

export function useCreatePatient() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (patient: Partial<Patient>) => patientApi.create(patient),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] });
    },
  });
}

export function useUpdatePatient() {
  const queryClient = useQueryClient();
  const setCurrentPatient = usePatientStore((state) => state.setCurrentPatient);
  
  return useMutation({
    mutationFn: ({ id, patient }: { id: number; patient: Partial<Patient> }) =>
      patientApi.update(id, patient),
    onSuccess: (updatedPatient) => {
      queryClient.invalidateQueries({ queryKey: ['patients'] });
      queryClient.invalidateQueries({ queryKey: ['patient', updatedPatient.id] });
      setCurrentPatient(updatedPatient);
    },
  });
}

export function useDeletePatient() {
  const queryClient = useQueryClient();
  const setCurrentPatient = usePatientStore((state) => state.setCurrentPatient);
  
  return useMutation({
    mutationFn: (id: number) => patientApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] });
      setCurrentPatient(null);
    },
  });
}
