import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Bot,
  Brain,
  Shield,
  Activity,
  MessageSquare,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  ChevronDown,
  ChevronUp,
  Zap,
  User,
  RefreshCw,
} from 'lucide-react';
import { format, formatDistanceToNow } from 'date-fns';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Button,
  Badge,
  ScrollArea,
} from '@/components/ui';
import { cn } from '@/lib/utils';
import { usePatientStore } from '@/stores/patientStore';
import { agentApi } from '@/services/api';

interface AgentEvent {
  id: string;
  agent: string;
  action: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  message: string;
  details?: string;
  timestamp: string;
}

const AGENT_INFO = {
  orchestrator: {
    name: 'Orchestrator',
    icon: Brain,
    color: 'text-purple-500',
    bgColor: 'bg-purple-100 dark:bg-purple-900/30',
    description: 'Coordinates all agent activities',
  },
  planning_agent: {
    name: 'Planning Agent',
    icon: Activity,
    color: 'text-blue-500',
    bgColor: 'bg-blue-100 dark:bg-blue-900/30',
    description: 'Creates personalized medication schedules',
  },
  monitoring_agent: {
    name: 'Monitoring Agent',
    icon: Shield,
    color: 'text-green-500',
    bgColor: 'bg-green-100 dark:bg-green-900/30',
    description: 'Tracks adherence and alerts',
  },
  barrier_agent: {
    name: 'Barrier Agent',
    icon: AlertTriangle,
    color: 'text-orange-500',
    bgColor: 'bg-orange-100 dark:bg-orange-900/30',
    description: 'Identifies and addresses adherence barriers',
  },
  liaison_agent: {
    name: 'Liaison Agent',
    icon: MessageSquare,
    color: 'text-cyan-500',
    bgColor: 'bg-cyan-100 dark:bg-cyan-900/30',
    description: 'Communicates with healthcare providers',
  },
};

export default function AgentActivity() {
  const { currentPatient } = usePatientStore();
  const patientId = currentPatient?.id || null;
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [expandedEvent, setExpandedEvent] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Fetch agent activity
  const fetchActivity = async () => {
    if (!patientId) return;
    
    try {
      const response = await agentApi.getActivity(patientId);
      setEvents(response.events || []);
    } catch (error) {
      // Generate mock data for demo
      setEvents(generateMockEvents());
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchActivity();
    // Poll for updates every 30 seconds
    const interval = setInterval(fetchActivity, 30000);
    return () => clearInterval(interval);
  }, [patientId]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await fetchActivity();
  };

  // Generate mock events for demo
  const generateMockEvents = (): AgentEvent[] => {
    const now = new Date();
    return [
      {
        id: '1',
        agent: 'orchestrator',
        action: 'Daily Analysis',
        status: 'completed',
        message: 'Completed daily patient analysis',
        details: 'Analyzed 24-hour adherence patterns and medication schedule compliance.',
        timestamp: new Date(now.getTime() - 5 * 60000).toISOString(),
      },
      {
        id: '2',
        agent: 'monitoring_agent',
        action: 'Adherence Check',
        status: 'completed',
        message: 'Morning medication reminder sent',
        details: 'Sent reminder for Metformin 500mg scheduled at 08:00.',
        timestamp: new Date(now.getTime() - 2 * 60 * 60000).toISOString(),
      },
      {
        id: '3',
        agent: 'barrier_agent',
        action: 'Barrier Detection',
        status: 'running',
        message: 'Analyzing recent missed doses',
        details: 'Detected pattern of missed evening doses. Investigating potential causes.',
        timestamp: new Date(now.getTime() - 10 * 60000).toISOString(),
      },
      {
        id: '4',
        agent: 'planning_agent',
        action: 'Schedule Optimization',
        status: 'completed',
        message: 'Recommended schedule adjustment',
        details: 'Suggested moving evening dose from 20:00 to 19:00 based on lifestyle patterns.',
        timestamp: new Date(now.getTime() - 3 * 60 * 60000).toISOString(),
      },
      {
        id: '5',
        agent: 'liaison_agent',
        action: 'Provider Update',
        status: 'pending',
        message: 'Preparing weekly report for Dr. Smith',
        details: 'Compiling adherence metrics and symptom reports for scheduled appointment.',
        timestamp: new Date(now.getTime() - 15 * 60000).toISOString(),
      },
      {
        id: '6',
        agent: 'monitoring_agent',
        action: 'Symptom Alert',
        status: 'completed',
        message: 'Flagged unusual symptom pattern',
        details: 'Detected correlation between new medication and reported dizziness.',
        timestamp: new Date(now.getTime() - 6 * 60 * 60000).toISOString(),
      },
    ];
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'running':
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
      case 'error':
        return <AlertTriangle className="h-4 w-4 text-red-500" />;
      default:
        return <Clock className="h-4 w-4 text-yellow-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge variant="success">Completed</Badge>;
      case 'running':
        return <Badge variant="info">Running</Badge>;
      case 'error':
        return <Badge variant="destructive">Error</Badge>;
      default:
        return <Badge variant="warning">Pending</Badge>;
    }
  };

  const getAgentInfo = (agent: string) => {
    return AGENT_INFO[agent as keyof typeof AGENT_INFO] || {
      name: agent,
      icon: Bot,
      color: 'text-gray-500',
      bgColor: 'bg-gray-100 dark:bg-gray-800',
      description: 'AI Agent',
    };
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
          <h2 className="text-2xl font-bold">Agent Activity</h2>
          <p className="text-muted-foreground">
            Monitor your AI healthcare assistants
          </p>
        </div>
        <Button
          variant="outline"
          onClick={handleRefresh}
          disabled={isRefreshing}
        >
          <RefreshCw className={cn("h-4 w-4 mr-2", isRefreshing && "animate-spin")} />
          Refresh
        </Button>
      </div>

      {/* Agent Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        {Object.entries(AGENT_INFO).map(([key, info]) => {
          const Icon = info.icon;
          const agentEvents = events.filter((e) => e.agent === key);
          const lastActive = agentEvents[0]?.timestamp;
          
          return (
            <Card key={key} className="overflow-hidden">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className={cn("p-2 rounded-lg", info.bgColor)}>
                    <Icon className={cn("h-5 w-5", info.color)} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h4 className="font-medium text-sm truncate">{info.name}</h4>
                    <p className="text-xs text-muted-foreground truncate">
                      {lastActive
                        ? formatDistanceToNow(new Date(lastActive), { addSuffix: true })
                        : 'No recent activity'}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Activity Feed */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Zap className="h-5 w-5 text-primary" />
            <CardTitle>Recent Activity</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          {events.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Bot className="h-12 w-12 mx-auto mb-3 opacity-50" />
              <p>No recent agent activity</p>
            </div>
          ) : (
            <ScrollArea className="h-[500px] pr-4">
              <div className="space-y-4">
                <AnimatePresence>
                  {events.map((event, index) => {
                    const agentInfo = getAgentInfo(event.agent);
                    const Icon = agentInfo.icon;
                    const isExpanded = expandedEvent === event.id;

                    return (
                      <motion.div
                        key={event.id}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.05 }}
                      >
                        <div
                          className={cn(
                            "p-4 rounded-lg border bg-card transition-all cursor-pointer hover:shadow-sm",
                            event.status === 'running' && "border-blue-200 dark:border-blue-800"
                          )}
                          onClick={() => setExpandedEvent(isExpanded ? null : event.id)}
                        >
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex items-start gap-3">
                              <div className={cn("p-2 rounded-lg", agentInfo.bgColor)}>
                                <Icon className={cn("h-5 w-5", agentInfo.color)} />
                              </div>
                              <div>
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="font-medium text-sm">
                                    {agentInfo.name}
                                  </span>
                                  <span className="text-muted-foreground">•</span>
                                  <span className="text-sm text-muted-foreground">
                                    {event.action}
                                  </span>
                                  {getStatusBadge(event.status)}
                                </div>
                                <p className="text-sm text-muted-foreground mt-1">
                                  {event.message}
                                </p>
                                <p className="text-xs text-muted-foreground mt-2 flex items-center gap-1">
                                  <Clock className="h-3 w-3" />
                                  {formatDistanceToNow(new Date(event.timestamp), {
                                    addSuffix: true,
                                  })}
                                </p>
                              </div>
                            </div>

                            <div className="flex items-center gap-2">
                              {getStatusIcon(event.status)}
                              {event.details && (
                                isExpanded ? (
                                  <ChevronUp className="h-4 w-4 text-muted-foreground" />
                                ) : (
                                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                                )
                              )}
                            </div>
                          </div>

                          <AnimatePresence>
                            {isExpanded && event.details && (
                              <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                transition={{ duration: 0.2 }}
                                className="overflow-hidden"
                              >
                                <div className="mt-4 pt-4 border-t">
                                  <p className="text-sm text-muted-foreground bg-muted p-3 rounded-lg">
                                    {event.details}
                                  </p>
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      </motion.div>
                    );
                  })}
                </AnimatePresence>
              </div>
            </ScrollArea>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
