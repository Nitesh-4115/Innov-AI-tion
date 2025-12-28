import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Calendar,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Pill,
  Loader2,
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
} from '@/components/ui';
import { cn, formatTime } from '@/lib/utils';
import { usePatientStore } from '@/stores/patientStore';
import { useTodaySchedule } from '@/hooks/useMedications';
import { useLogDose } from '@/hooks/useAdherence';
import { ScheduleItem } from '@/types';

interface ScheduleProps {
  showHeader?: boolean;
}

export default function Schedule({ showHeader = true }: ScheduleProps) {
  const { currentPatient } = usePatientStore();
  const patientId = currentPatient?.id || null;
  const { data: schedule, isLoading } = useTodaySchedule(patientId);
  const logDose = useLogDose(patientId);
  const [processingId, setProcessingId] = useState<number | null>(null);

  const handleTakeDose = async (scheduleItem: ScheduleItem, action: 'taken' | 'missed' | 'skipped') => {
    setProcessingId(scheduleItem.id);
    try {
      await logDose.mutateAsync({
        schedule_id: scheduleItem.id,
        medication_id: scheduleItem.medication_id,
        status: action,
        scheduled_time: scheduleItem.scheduled_time,
        taken_at: action === 'taken' ? new Date().toISOString() : undefined,
      });
    } finally {
      setProcessingId(null);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'taken':
        return <CheckCircle2 className="h-5 w-5 text-green-500" />;
      case 'missed':
        return <XCircle className="h-5 w-5 text-red-500" />;
      case 'skipped':
        return <AlertCircle className="h-5 w-5 text-yellow-500" />;
      default:
        return <Clock className="h-5 w-5 text-blue-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'taken':
        return <Badge variant="success">Taken</Badge>;
      case 'missed':
        return <Badge variant="destructive">Missed</Badge>;
      case 'skipped':
        return <Badge variant="warning">Skipped</Badge>;
      default:
        return <Badge variant="info">Pending</Badge>;
    }
  };

  const sortedSchedule = schedule?.slice().sort((a, b) =>
    a.scheduled_time.localeCompare(b.scheduled_time)
  ) || [];

  const groupedSchedule = sortedSchedule.reduce((acc, item) => {
    const time = item.scheduled_time;
    if (!acc[time]) acc[time] = [];
    acc[time].push(item);
    return acc;
  }, {} as Record<string, ScheduleItem[]>);
  
  const todayItems = sortedSchedule.filter((item) => {
    return !item.scheduled_date || new Date(item.scheduled_date).toDateString() === new Date().toDateString();
  });

  const upcomingItems = sortedSchedule.filter((item) => {
    return !!item.scheduled_date && new Date(item.scheduled_date).toDateString() !== new Date().toDateString();
  });

  const groupByTime = (items: ScheduleItem[]) =>
    items.reduce((acc: Record<string, ScheduleItem[]>, item) => {
      const time = item.scheduled_time;
      if (!acc[time]) acc[time] = [];
      acc[time].push(item);
      return acc;
    }, {} as Record<string, ScheduleItem[]>);

  const todayGroups = groupByTime(todayItems);
  const upcomingGroups = groupByTime(upcomingItems);
  const renderItem = (item: ScheduleItem, index: number) => {
    const isTodayItem = !item.scheduled_date || new Date(item.scheduled_date).toDateString() === new Date().toDateString();

    return (
      <motion.div
        key={item.id ?? `${item.medication_id}-${item.scheduled_time}-${index}`}
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: 20 }}
        transition={{ delay: index * 0.05 }}
        className={cn(
          'relative p-4 rounded-lg border bg-card transition-all',
          item.status === 'pending' && 'border-blue-200 dark:border-blue-800',
          item.status === 'taken' && 'border-green-200 dark:border-green-800 bg-green-50/50 dark:bg-green-900/10',
          item.status === 'missed' && 'border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/10',
          item.status === 'skipped' && 'border-yellow-200 dark:border-yellow-800 bg-yellow-50/50 dark:bg-yellow-900/10'
        )}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            {getStatusIcon(item.status)}
            <div>
              <h4 className="font-medium">{item.medication_name}</h4>
              <p className="text-sm text-muted-foreground">{item.dosage}</p>
              {item.instructions && (
                <p className="text-xs text-muted-foreground mt-1">{item.instructions}</p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {item.status === 'pending' && isTodayItem ? (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleTakeDose(item, 'skipped')}
                  disabled={processingId === item.id}
                  className="text-xs"
                >
                  Skip
                </Button>
                <Button
                  size="sm"
                  onClick={() => handleTakeDose(item, 'taken')}
                  disabled={processingId === item.id}
                  className="bg-green-600 hover:bg-green-700"
                >
                  {processingId === item.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <>
                      <CheckCircle2 className="h-4 w-4 mr-1" />
                      Take
                    </>
                  )}
                </Button>
              </>
            ) : item.status === 'pending' && !isTodayItem ? (
              <Badge variant="secondary">Upcoming</Badge>
            ) : (
              getStatusBadge(item.status)
            )}
          </div>
        </div>

        {item.taken_at && (
          <p className="text-xs text-muted-foreground mt-2 ml-8">
            Taken at {format(new Date(item.taken_at), 'h:mm a')}
          </p>
        )}
      </motion.div>
    );
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-8 flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      {showHeader && (
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Calendar className="h-5 w-5 text-primary" />
              <CardTitle>Today's Schedule</CardTitle>
            </div>
            <Badge variant="secondary">{format(new Date(), 'EEEE, MMMM d')}</Badge>
          </div>
        </CardHeader>
      )}

      <CardContent className={cn(!showHeader && 'pt-6')}>
        {sortedSchedule.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Pill className="h-12 w-12 mx-auto mb-3 opacity-50" />
            <p>No medications scheduled for today</p>
          </div>
        ) : (
          <ScrollArea className="h-[400px] pr-4">
            <div className="space-y-4">
              {Object.entries(todayGroups).length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">No medications scheduled for today</div>
              ) : (
                Object.entries(todayGroups).map(([time, items]) => (
                  <div key={`today-${time}`} className="relative">
                    <div className="sticky top-0 bg-background z-10 py-2 flex items-center gap-3 mb-2">
                      <div className="flex items-center gap-2 text-sm font-medium">
                        <Clock className="h-4 w-4 text-muted-foreground" />
                        {formatTime(time)}
                      </div>
                      <div className="flex-1 h-px bg-border" />
                    </div>

                    <div className="space-y-3 ml-6">
                      <AnimatePresence>
                        {items.map((item, index) => renderItem(item, index))}
                      </AnimatePresence>
                    </div>
                  </div>
                ))
              )}

              {Object.entries(upcomingGroups).length > 0 && (
                <div className="mt-6">
                  <div className="mb-3 text-sm font-medium text-muted-foreground">Upcoming</div>
                  {Object.entries(upcomingGroups).map(([time, items]) => (
                    <div key={`upcoming-${time}`} className="relative">
                      <div className="sticky top-0 bg-background z-10 py-2 flex items-center gap-3 mb-2">
                        <div className="flex items-center gap-2 text-sm font-medium">
                          <Clock className="h-4 w-4 text-muted-foreground" />
                          {formatTime(time)}
                        </div>
                        <div className="flex-1 h-px bg-border" />
                      </div>

                      <div className="space-y-3 ml-6">
                        <AnimatePresence>
                          {items.map((item, index) => renderItem(item, index))}
                        </AnimatePresence>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}
