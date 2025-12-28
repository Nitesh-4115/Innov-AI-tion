import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Pill,
  Plus,
  Clock,
  Calendar,
  AlertTriangle,
  Info,
  ChevronDown,
  ChevronUp,
  Edit,
  Trash2,
  MoreVertical,
  Loader2,
  Activity,
  AlertCircle,
  Check,
  CheckCircle,
} from 'lucide-react';
import { format } from 'date-fns';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Button,
  Badge,
  ScrollArea,
  Input,
} from '@/components/ui';
import { cn, formatTime, getAdherenceColor } from '@/lib/utils';
import { usePatientStore } from '@/stores/patientStore';
import {
  useMedications,
  useDrugInteractions,
  useCreateMedication,
  useUpdateMedication,
  useDeleteMedication,
} from '@/hooks/useMedications';
import { useLogDose } from '@/hooks/useAdherence';
import { Medication } from '@/types';
import AddMedicationModal from './AddMedicationModal';
import { useTodaySchedule } from '@/hooks/useMedications';
import { scheduleApi } from '@/services/api';

export default function MedicationList() {
  const { currentPatient } = usePatientStore();
  const patientId = currentPatient?.id || null;
  const queryClient = useQueryClient();
  
  const { data: medications, isLoading } = useMedications(patientId);
  const { data: interactions } = useDrugInteractions(patientId);
  const { data: todaySchedule } = useTodaySchedule(patientId);
  const createMedication = useCreateMedication();
  const updateMedication = useUpdateMedication();
  const deleteMedication = useDeleteMedication();
  const logDose = useLogDose(patientId);

  const [expandedMed, setExpandedMed] = useState<number | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [doseStatus, setDoseStatus] = useState<Record<number, string>>({});
  const [schedulingId, setSchedulingId] = useState<number | null>(null);

  const filteredMedications = medications?.filter((med) =>
    med.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    med.purpose?.toLowerCase().includes(searchQuery.toLowerCase())
  ) || [];

  const activeMeds = filteredMedications.filter((m) => m.is_active);
  const inactiveMeds = filteredMedications.filter((m) => !m.is_active);

  const getInteractionsForMed = (medName: string) => {
    return interactions?.filter(
      (i) =>
        i.drug1_name.toLowerCase() === medName.toLowerCase() ||
        i.drug2_name.toLowerCase() === medName.toLowerCase()
    ) || [];
  };

  const getSeverityColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'high':
      case 'major':
        return 'text-red-500 bg-red-100 dark:bg-red-900/30';
      case 'moderate':
        return 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900/30';
      case 'low':
      case 'minor':
        return 'text-green-500 bg-green-100 dark:bg-green-900/30';
      default:
        return 'text-gray-500 bg-gray-100 dark:bg-gray-800';
    }
  };

  const MedicationCard = ({ medication }: { medication: Medication }) => {
    const isExpanded = expandedMed === medication.id;
    const medInteractions = getInteractionsForMed(medication.name);
    const hasInteractions = medInteractions.length > 0;
    const highSeverityInteractions = medInteractions.filter(
      (i) => i.severity.toLowerCase() === 'high' || i.severity.toLowerCase() === 'major'
    );

    const doses = (todaySchedule || []).filter(
      (item) =>
        item.medication_name?.toLowerCase() === medication.name.toLowerCase() &&
        // only include items scheduled for today (or items without a scheduled_date)
        (!item.scheduled_date || new Date(item.scheduled_date).toDateString() === new Date().toDateString())
    );
    const pendingDose = doses.find((d) => d.status === 'pending');
    const completedDoses = doses.filter((d) => d.status === 'taken').length;
    const totalDoses = doses.length;

    const getDefaultTimes = () => {
      const count = medication.frequency_per_day || 1;
      if (count >= 3) return ['08:00', '14:00', '20:00'];
      if (count === 2) return ['08:00', '20:00'];
      return ['08:00'];
    };

    const handleAddSchedule = async () => {
      if (!patientId) return;
      setSchedulingId(medication.id);
      try {
        const defaultTimes = getDefaultTimes();
        const input = window.prompt(
          'Enter dose times (HH:MM, comma separated)',
          defaultTimes.join(', ')
        );
        if (!input) return;
        const times = input
          .split(',')
          .map((t) => t.trim())
          .filter((t) => /^\d{1,2}:\d{2}$/.test(t));
        if (times.length === 0) return;
        await scheduleApi.createCustom(patientId, {
          medication_id: medication.id,
          times,
        });
        queryClient.invalidateQueries({ queryKey: ['todaySchedule', patientId] });
        queryClient.invalidateQueries({ queryKey: ['medications', patientId] });
      } catch (err) {
        console.error('Add schedule failed', err);
      } finally {
        setSchedulingId(null);
      }
    };

    return (
      <motion.div
        layout
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        className="overflow-hidden"
      >
        <Card
          className={cn(
            "transition-all cursor-pointer hover:shadow-md",
            !medication.is_active && "opacity-60"
          )}
        >
          <CardContent className="p-4">
            <div
              className="flex items-start justify-between"
              onClick={() => setExpandedMed(isExpanded ? null : medication.id)}
            >
              <div className="flex items-start gap-3">
                <div
                  className={cn(
                    "p-2 rounded-lg",
                    medication.is_active
                      ? "bg-primary/10 text-primary"
                      : "bg-muted text-muted-foreground"
                  )}
                >
                  <Pill className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold">{medication.name}</h3>
                    {hasInteractions && (
                      <Badge
                        variant={highSeverityInteractions.length > 0 ? 'destructive' : 'warning'}
                        className="text-xs"
                      >
                        <AlertTriangle className="h-3 w-3 mr-1" />
                        {medInteractions.length} interaction{medInteractions.length > 1 ? 's' : ''}
                      </Badge>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {medication.dosage} • {medication.frequency}
                  </p>
                  {medication.purpose && (
                    <p className="text-xs text-muted-foreground mt-1">
                      {medication.purpose}
                    </p>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2">
                {/* Quick Take Button - per-dose (marks next pending dose) */}
                {medication.is_active && (
                  <Button
                    variant={pendingDose ? "outline" : totalDoses === 0 ? "secondary" : "default"}
                    size="sm"
                    className={cn(
                      "h-8",
                      !pendingDose && totalDoses > 0 && "bg-green-600 hover:bg-green-700 text-white"
                    )}
                    disabled={!pendingDose || logDose.isPending || totalDoses === 0}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (!patientId || !pendingDose) return;
                      setDoseStatus((prev) => ({ ...prev, [pendingDose.id]: 'taken' }));
                      logDose.mutate({
                        schedule_id: pendingDose.id,
                        medication_id: pendingDose.medication_id,
                        status: 'taken',
                        scheduled_time: pendingDose.scheduled_time,
                        taken_at: new Date().toISOString(),
                      });
                    }}
                  >
                    {totalDoses === 0 ? (
                      <>
                        <Clock className="h-4 w-4 mr-1" />
                        Awaiting schedule
                      </>
                    ) : pendingDose ? (
                      <>
                        <Check className="h-4 w-4 mr-1" />
                        Mark next dose
                      </>
                    ) : (
                      <>
                        <CheckCircle className="h-4 w-4 mr-1" />
                        All doses done
                      </>
                    )}
                  </Button>
                )}
                {medication.is_active && totalDoses === 0 && (
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={schedulingId === medication.id}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleAddSchedule();
                    }}
                  >
                    {schedulingId === medication.id ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                        Adding...
                      </>
                    ) : (
                      <>
                        <Clock className="h-4 w-4 mr-1" />
                        Add schedule
                      </>
                    )}
                  </Button>
                )}
                <Badge variant={medication.is_active ? 'success' : 'secondary'}>
                  {medication.is_active ? 'Active' : 'Inactive'}
                </Badge>
                {isExpanded ? (
                  <ChevronUp className="h-5 w-5 text-muted-foreground" />
                ) : (
                  <ChevronDown className="h-5 w-5 text-muted-foreground" />
                )}
              </div>
            </div>

            <AnimatePresence>
              {isExpanded && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="overflow-hidden"
                >
                  <div className="mt-4 pt-4 border-t space-y-4">
                    {/* Schedule Info */}
                    <div className="grid grid-cols-2 gap-4">
                      {medication.start_date && (
                        <div className="flex items-center gap-2 text-sm">
                          <Calendar className="h-4 w-4 text-muted-foreground" />
                          <span className="text-muted-foreground">Started:</span>
                          <span>{format(new Date(medication.start_date), 'MMM d, yyyy')}</span>
                        </div>
                      )}
                      {medication.end_date && (
                        <div className="flex items-center gap-2 text-sm">
                          <Calendar className="h-4 w-4 text-muted-foreground" />
                          <span className="text-muted-foreground">Ends:</span>
                          <span>{format(new Date(medication.end_date), 'MMM d, yyyy')}</span>
                        </div>
                      )}
                    </div>

                    {/* Instructions */}
                    {medication.instructions && (
                      <div className="flex items-start gap-2 p-3 bg-muted rounded-lg">
                        <Info className="h-4 w-4 text-blue-500 mt-0.5" />
                        <div className="text-sm">
                          <p className="font-medium mb-1">Instructions</p>
                          <p className="text-muted-foreground">
                            {medication.instructions}
                          </p>
                        </div>
                      </div>
                    )}

                    {/* Interactions */}
                    {hasInteractions && (
                      <div className="space-y-2">
                        <p className="text-sm font-medium flex items-center gap-2">
                          <AlertTriangle className="h-4 w-4 text-yellow-500" />
                          Drug Interactions
                        </p>
                        <div className="space-y-2">
                          {medInteractions.map((interaction, idx) => (
                            <div
                              key={idx}
                              className={cn(
                                "p-3 rounded-lg text-sm",
                                getSeverityColor(interaction.severity)
                              )}
                            >
                              <div className="flex items-center justify-between mb-1">
                                <span className="font-medium">
                                  {interaction.drug1_name === medication.name
                                    ? interaction.drug2_name
                                    : interaction.drug1_name}
                                </span>
                                <Badge
                                  variant={
                                    interaction.severity.toLowerCase() === 'high'
                                      ? 'destructive'
                                      : 'warning'
                                  }
                                >
                                  {interaction.severity}
                                </Badge>
                              </div>
                              <p className="text-xs opacity-80">
                                {interaction.description}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Action Buttons */}
                    <div className="flex flex-col sm:flex-row sm:items-center gap-2 pt-2">
                      {medication.is_active && (
                        <div className="flex flex-col gap-2 w-full">
                          <div className="text-xs text-muted-foreground">
                            {totalDoses > 0
                              ? `${completedDoses}/${totalDoses} doses taken today`
                              : 'No scheduled doses today'}
                          </div>
                          {doses.map((dose) => (
                            <div key={dose.id} className="flex items-center justify-between gap-2 rounded border p-2">
                              <div className="text-sm">
                                <span className="font-medium">{formatTime(dose.scheduled_time)}</span>
                                <span className="ml-2 text-muted-foreground text-xs">{dose.status}</span>
                              </div>
                              {dose.status === 'pending' ? (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  disabled={logDose.isPending || doseStatus[dose.id] === 'taken'}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setDoseStatus((prev) => ({ ...prev, [dose.id]: 'taken' }));
                                    logDose.mutate({
                                      schedule_id: dose.id,
                                      medication_id: dose.medication_id,
                                      status: 'taken',
                                      scheduled_time: dose.scheduled_time,
                                      taken_at: new Date().toISOString(),
                                    });
                                  }}
                                >
                                  {logDose.isPending && doseStatus[dose.id] === 'taken' ? (
                                    <>
                                      <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                                      Saving
                                    </>
                                  ) : (
                                    <>
                                      <Check className="h-4 w-4 mr-1" />
                                      Mark dose
                                    </>
                                  )}
                                </Button>
                              ) : (
                                <Badge variant={dose.status === 'taken' ? 'success' : 'secondary'}>
                                  {dose.status === 'taken' ? 'Taken' : dose.status}
                                </Badge>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (!patientId) return;
                          updateMedication.mutate({
                            patientId,
                            medicationId: medication.id,
                            medication: { active: !medication.is_active },
                          });
                        }}
                      >
                        {medication.is_active ? 'Deactivate' : 'Activate'}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (!patientId) return;
                          if (confirm('Are you sure you want to delete this medication?')) {
                            deleteMedication.mutate({ patientId, medicationId: medication.id });
                          }
                        }}
                      >
                        <Trash2 className="h-4 w-4 mr-1" />
                        Delete
                      </Button>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </CardContent>
        </Card>
      </motion.div>
    );
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Medications</h2>
          <p className="text-muted-foreground">
            Manage your medication regimen
          </p>
        </div>
        <Button onClick={() => setShowAddModal(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Add Medication
        </Button>
      </div>

      {/* Search */}
      <div className="relative">
        <Input
          placeholder="Search medications..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="max-w-md"
        />
      </div>

      {/* Interactions Summary */}
      {interactions && interactions.length > 0 && (
        <Card className="border-yellow-200 dark:border-yellow-800 bg-yellow-50/50 dark:bg-yellow-900/10">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-yellow-600 mt-0.5" />
              <div>
                <h3 className="font-medium text-yellow-800 dark:text-yellow-200">
                  Drug Interactions Detected
                </h3>
                <p className="text-sm text-yellow-700 dark:text-yellow-300">
                  {interactions.length} potential interaction{interactions.length > 1 ? 's' : ''} found between your medications.
                  Expand individual medications to see details.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Active Medications */}
      <div className="space-y-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Activity className="h-5 w-5 text-green-500" />
          Active Medications ({activeMeds.length})
        </h3>
        {activeMeds.length === 0 ? (
          <Card>
            <CardContent className="p-8 text-center">
              <Pill className="h-12 w-12 mx-auto mb-3 text-muted-foreground opacity-50" />
              <p className="text-muted-foreground">No active medications</p>
              <Button variant="outline" className="mt-4" onClick={() => setShowAddModal(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Add your first medication
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4">
            <AnimatePresence>
              {activeMeds.map((med) => (
                <MedicationCard key={med.id} medication={med} />
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>

      {/* Inactive Medications */}
      {inactiveMeds.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold flex items-center gap-2 text-muted-foreground">
            <Pill className="h-5 w-5" />
            Inactive Medications ({inactiveMeds.length})
          </h3>
          <div className="grid gap-4">
            <AnimatePresence>
              {inactiveMeds.map((med) => (
                <MedicationCard key={med.id} medication={med} />
              ))}
            </AnimatePresence>
          </div>
        </div>
      )}

      {/* Add Medication Modal */}
      <AddMedicationModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
      />
    </div>
  );
}
