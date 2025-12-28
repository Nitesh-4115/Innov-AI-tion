import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Activity,
  Calendar,
  Pill,
  Clock,
  AlertTriangle,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { Card, CardContent, Badge } from '@/components/ui';
import { cn, formatTime, getAdherenceColor } from '@/lib/utils';
import { usePatientStore } from '@/stores/patientStore';
import { useAdherenceRate, useAdherenceStreak } from '@/hooks/useAdherence';
import { useMedications, useTodaySchedule } from '@/hooks/useMedications';
import AdherenceChart from './AdherenceChart';
import Schedule from './Schedule';

export default function Dashboard() {
  const { currentPatient } = usePatientStore();
  const patientId = currentPatient?.id || null;
  
  const { data: adherenceRate } = useAdherenceRate(patientId, 30);
  const { data: streak } = useAdherenceStreak(patientId);
  const { data: medications } = useMedications(patientId);
  const { data: todaySchedule } = useTodaySchedule(patientId);
  
  const [nextDose, setNextDose] = useState<{
    name: string;
    time: string;
    timeUntil: string;
  } | null>(null);

  // Calculate next dose
  useEffect(() => {
    if (!todaySchedule || todaySchedule.length === 0) return;
    let mounted = true;

    const computeNext = () => {
      if (!mounted) return;
      const now = new Date();
      // Prefer pending items scheduled for today. If none, use pending items
      // flagged as `is_next` (created-next / next-day entries).
      const pendingToday = todaySchedule
        .filter((item) => item.status === 'pending' && (!item.scheduled_date || new Date(item.scheduled_date).toDateString() === new Date().toDateString()))
        .sort((a, b) => a.scheduled_time.localeCompare(b.scheduled_time));

      const pendingNext = todaySchedule
        .filter((item) => item.status === 'pending' && item.is_next)
        .sort((a, b) => a.scheduled_date?.localeCompare(b.scheduled_date || '') || a.scheduled_time.localeCompare(b.scheduled_time));

      const nextItem = pendingToday.length > 0 ? pendingToday[0] : (pendingNext.length > 0 ? pendingNext[0] : null);

      if (!nextItem) {
        setNextDose(null);
        return;
      }

      const next = nextItem;
      const [hours, minutes] = next.scheduled_time.split(':').map(Number);

      // Build a timezone-aware target date using the scheduled_date if present,
      // otherwise assume today.
      const targetDate = next.scheduled_date ? new Date(next.scheduled_date) : new Date();
      const scheduleTime = new Date(targetDate);
      scheduleTime.setHours(hours, minutes, 0, 0);

      const isTomorrow = scheduleTime.getDate() !== now.getDate() || scheduleTime.getTime() > now.getTime() && (scheduleTime.getTime() - now.getTime()) > 24 * 60 * 60 * 1000;

      const targetMs = scheduleTime.getTime();

      const diffMs = Math.max(0, targetMs - now.getTime());
      const diffMins = Math.round(diffMs / 60000);
      const diffHours = Math.floor(diffMins / 60);
      const remainingMins = diffMins % 60;

      let timeUntil = '';
      if (isTomorrow) {
        // Show combined label: 'Tomorrow · In X hours'
        if (diffHours > 0) {
          timeUntil = `Tomorrow · In ${diffHours} hour${diffHours > 1 ? 's' : ''}`;
          if (remainingMins > 0) timeUntil += ` ${remainingMins} min`;
        } else if (diffMins > 0) {
          timeUntil = `Tomorrow · In ${diffMins} minutes`;
        } else {
          timeUntil = 'Tomorrow';
        }
      } else {
        if (diffHours > 0) {
          timeUntil = `In ${diffHours} hour${diffHours > 1 ? 's' : ''}`;
          if (remainingMins > 0) timeUntil += ` ${remainingMins} min`;
        } else if (diffMins > 0) {
          timeUntil = `In ${diffMins} minutes`;
        } else {
          timeUntil = 'Now';
        }
      }

      setNextDose({
        name: next.medication_name,
        time: next.scheduled_time,
        timeUntil,
      });
    };

    // Initial compute
    computeNext();

    // Live update every 30 seconds so 'In X minutes' updates
    const iv = setInterval(computeNext, 30 * 1000);

    return () => {
      mounted = false;
      clearInterval(iv);
    };
  }, [todaySchedule]);

  const activeMeds = medications?.filter((m) => m.is_active).length || 0;
  const adherenceRateValue = adherenceRate?.adherence_rate || 0;
  const currentStreak = streak?.current_streak || 0;
  const bestStreak = streak?.best_streak || 0;

  const cardVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: (i: number) => ({
      opacity: 1,
      y: 0,
      transition: {
        delay: i * 0.1,
        duration: 0.5,
        ease: 'easeOut',
      },
    }),
  };

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Overall Adherence */}
        <motion.div
          custom={0}
          initial="hidden"
          animate="visible"
          variants={cardVariants}
        >
          <Card className="gradient-green border-0 overflow-hidden">
            <CardContent className="p-6">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-sm font-medium text-green-700 dark:text-green-300">
                    Overall Adherence
                  </p>
                  <h2 className={cn(
                    "text-4xl font-bold mt-2",
                    getAdherenceColor(adherenceRateValue)
                  )}>
                    {adherenceRateValue.toFixed(0)}%
                  </h2>
                  <p className="text-sm mt-1 text-green-700 dark:text-green-300">
                    {adherenceRateValue >= 80 ? 'Keep it up' : 'Please adhere to your medication'}
                  </p>
                </div>
                <div className="p-3 bg-white/50 dark:bg-white/10 rounded-xl">
                  <Activity className="h-6 w-6 text-green-600 dark:text-green-400" />
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Streak */}
        <motion.div
          custom={1}
          initial="hidden"
          animate="visible"
          variants={cardVariants}
        >
          <Card className="gradient-blue border-0 overflow-hidden">
            <CardContent className="p-6">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-sm font-medium text-blue-700 dark:text-blue-300">
                    Streak
                  </p>
                  <h2 className="text-4xl font-bold text-blue-600 dark:text-blue-400 mt-2">
                    {currentStreak} days
                  </h2>
                  <p className="text-sm text-blue-600/80 dark:text-blue-400/80 mt-2">
                    {currentStreak >= bestStreak ? '🏆 Personal best!' : `Best: ${bestStreak} days`}
                  </p>
                </div>
                <div className="p-3 bg-white/50 dark:bg-white/10 rounded-xl">
                  <Calendar className="h-6 w-6 text-blue-600 dark:text-blue-400" />
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Active Meds */}
        <motion.div
          custom={2}
          initial="hidden"
          animate="visible"
          variants={cardVariants}
        >
          <Card className="gradient-purple border-0 overflow-hidden">
            <CardContent className="p-6">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-sm font-medium text-purple-700 dark:text-purple-300">
                    Active Meds
                  </p>
                  <h2 className="text-4xl font-bold text-purple-600 dark:text-purple-400 mt-2">
                    {activeMeds}
                  </h2>
                  <p className="text-sm text-purple-600/80 dark:text-purple-400/80 mt-2">
                    All monitored
                  </p>
                </div>
                <div className="p-3 bg-white/50 dark:bg-white/10 rounded-xl">
                  <Pill className="h-6 w-6 text-purple-600 dark:text-purple-400" />
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Next Dose */}
        <motion.div
          custom={3}
          initial="hidden"
          animate="visible"
          variants={cardVariants}
        >
          <Card className="gradient-orange border-0 overflow-hidden">
            <CardContent className="p-6">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-sm font-medium text-orange-700 dark:text-orange-300">
                    Next Dose
                  </p>
                  <h2 className="text-4xl font-bold text-orange-600 dark:text-orange-400 mt-2">
                    {nextDose ? formatTime(nextDose.time) : '--:--'}
                  </h2>
                  <p className="text-sm text-orange-600/80 dark:text-orange-400/80 mt-2">
                    {nextDose?.timeUntil || 'No pending doses'}
                  </p>
                </div>
                <div className="p-3 bg-white/50 dark:bg-white/10 rounded-xl">
                  <Clock className="h-6 w-6 text-orange-600 dark:text-orange-400" />
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Today's Schedule */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, duration: 0.5 }}
      >
        <Schedule />
      </motion.div>

      {/* Adherence Chart */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5, duration: 0.5 }}
      >
        <AdherenceChart />
      </motion.div>

      {/* Quick Stats Row */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6, duration: 0.5 }}
        className="grid grid-cols-1 md:grid-cols-4 gap-4"
      >
        {/* Taken Today */}
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-xl">
              <CheckCircle2 className="h-6 w-6 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Taken Today</p>
              <p className="text-2xl font-bold">
                {todaySchedule?.filter((s) => s.status === 'taken').length || 0}
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Missed Today */}
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-red-100 dark:bg-red-900/30 rounded-xl">
              <XCircle className="h-6 w-6 text-red-600" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Missed Today</p>
              <p className="text-2xl font-bold">
                {todaySchedule?.filter((s) => s.status === 'missed').length || 0}
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Skipped Today */}
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-yellow-100 dark:bg-yellow-900/30 rounded-xl">
              <AlertTriangle className="h-6 w-6 text-yellow-600" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Skipped Today</p>
              <p className="text-2xl font-bold">
                {todaySchedule?.filter((s) => s.status === 'skipped').length || 0}
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Pending Today */}
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-xl">
              <Clock className="h-6 w-6 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Pending Today</p>
              <p className="text-2xl font-bold">
                {todaySchedule?.filter((s) => s.status === 'pending').length || 0}
              </p>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
