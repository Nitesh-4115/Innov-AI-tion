import { useState, useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { format, subDays, parseISO } from 'date-fns';
import { TrendingUp, Calendar } from 'lucide-react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Button,
} from '@/components/ui';
import { cn, getAdherenceColor } from '@/lib/utils';
import { usePatientStore } from '@/stores/patientStore';
import { useAdherenceTrends } from '@/hooks/useAdherence';

type TimeRange = 7 | 14 | 30 | 90;

export default function AdherenceChart() {
  const { currentPatient, theme } = usePatientStore();
  const patientId = currentPatient?.id || null;
  const [timeRange, setTimeRange] = useState<TimeRange>(30);
  
  const { data: trends, isLoading } = useAdherenceTrends(patientId, timeRange);

  // Generate chart data
  const chartData = useMemo(() => {
    if (!trends) {
      // Generate mock data for demo
      return Array.from({ length: timeRange }, (_, i) => {
        const date = subDays(new Date(), timeRange - 1 - i);
        return {
          date: format(date, 'MMM dd'),
          fullDate: date.toISOString(),
          adherence: Math.floor(Math.random() * 30) + 70,
        };
      });
    }

    return trends.map((t) => ({
      date: format(parseISO(t.date), 'MMM dd'),
      fullDate: t.date,
      adherence: Math.round(t.adherence_rate),
    }));
  }, [trends, timeRange]);

  const avgAdherence = useMemo(() => {
    if (chartData.length === 0) return 0;
    const sum = chartData.reduce((acc, d) => acc + d.adherence, 0);
    return Math.round(sum / chartData.length);
  }, [chartData]);

  const timeRanges: { value: TimeRange; label: string }[] = [
    { value: 7, label: '7D' },
    { value: 14, label: '14D' },
    { value: 30, label: '30D' },
    { value: 90, label: '90D' },
  ];

  const isDark = theme === 'dark' || 
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-popover border rounded-lg shadow-lg p-3">
          <p className="text-sm font-medium">{label}</p>
          <p className={cn('text-lg font-bold', getAdherenceColor(payload[0].value))}>
            {payload[0].value}%
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-primary" />
            <CardTitle>Adherence Trends</CardTitle>
          </div>
          <div className="flex items-center gap-1 bg-muted rounded-lg p-1">
            {timeRanges.map((range) => (
              <Button
                key={range.value}
                variant={timeRange === range.value ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setTimeRange(range.value)}
                className="px-3"
              >
                {range.label}
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="mb-4 flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-primary" />
            <span className="text-sm text-muted-foreground">Daily Adherence</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-green-500" />
            <span className="text-sm text-muted-foreground">Target (80%)</span>
          </div>
          <div className="ml-auto flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Average:</span>
            <span className={cn('font-bold', getAdherenceColor(avgAdherence))}>
              {avgAdherence}%
            </span>
          </div>
        </div>

        <div className="h-[300px] w-full">
          {isLoading ? (
            <div className="h-full flex items-center justify-center">
              <div className="animate-pulse flex flex-col items-center">
                <div className="w-full h-48 bg-muted rounded" />
              </div>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={chartData}
                margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="adherenceGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop
                      offset="5%"
                      stopColor="hsl(var(--primary))"
                      stopOpacity={0.3}
                    />
                    <stop
                      offset="95%"
                      stopColor="hsl(var(--primary))"
                      stopOpacity={0}
                    />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke={isDark ? 'hsl(var(--border))' : '#e5e7eb'}
                  vertical={false}
                />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 12, fill: isDark ? '#9ca3af' : '#6b7280' }}
                  tickLine={false}
                  axisLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fontSize: 12, fill: isDark ? '#9ca3af' : '#6b7280' }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(value) => `${value}%`}
                />
                <Tooltip content={<CustomTooltip />} />
                <ReferenceLine
                  y={80}
                  stroke="#22c55e"
                  strokeDasharray="5 5"
                  label={{
                    value: 'Target',
                    position: 'right',
                    fill: '#22c55e',
                    fontSize: 12,
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="adherence"
                  stroke="hsl(var(--primary))"
                  strokeWidth={2}
                  fill="url(#adherenceGradient)"
                  dot={false}
                  activeDot={{
                    r: 6,
                    fill: 'hsl(var(--primary))',
                    stroke: 'hsl(var(--background))',
                    strokeWidth: 2,
                  }}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
