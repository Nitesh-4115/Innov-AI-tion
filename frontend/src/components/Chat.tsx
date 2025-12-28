import { useState, useRef, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Send,
  Bot,
  User,
  Loader2,
  Pill,
  Clock,
  AlertCircle,
  Activity,
  HelpCircle,
  Sparkles,
  ChevronRight,
} from 'lucide-react';
import { format } from 'date-fns';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Button,
  Input,
  ScrollArea,
  Avatar,
  AvatarFallback,
  Badge,
} from '@/components/ui';
// Dialog component not present in ui exports; use a simple inline modal instead
import { cn } from '@/lib/utils';
import { usePatientStore } from '@/stores/patientStore';
import { useSendMessage, useQuickActions } from '@/hooks/useChat';
import { medicationApi, scheduleApi } from '@/services/api';
import { getChatSessionKey, loadChatSession, saveChatSession } from '@/lib/chatSession';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  actions?: QuickAction[];
}

interface QuickAction {
  id: string;
  label: string;
  type: 'schedule' | 'adherence' | 'medication' | 'symptom' | 'general';
}

const QUICK_ACTIONS: QuickAction[] = [
  { id: '1', label: "What's my next dose?", type: 'schedule' },
  { id: '2', label: 'I took my medication', type: 'medication' },
  { id: '3', label: 'Show my adherence stats', type: 'adherence' },
  { id: '4', label: 'Check drug interactions', type: 'medication' },
  { id: '5', label: 'Report a side effect', type: 'symptom' },
];

const safeFormatTime = (value?: string) => {
  if (!value) return '';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  return format(d, 'h:mm a');
};

const getActionIcon = (type: string) => {
  switch (type) {
    case 'schedule':
      return <Clock className="h-4 w-4" />;
    case 'adherence':
      return <Activity className="h-4 w-4" />;
    case 'medication':
      return <Pill className="h-4 w-4" />;
    case 'symptom':
      return <AlertCircle className="h-4 w-4" />;
    default:
      return <HelpCircle className="h-4 w-4" />;
  }
};

export default function Chat() {
  const { currentPatient } = usePatientStore();
  const patientId = currentPatient?.id || null;
  const queryClient = useQueryClient();

  const sendMessage = useSendMessage(patientId);
  const quickAction = useQuickActions(patientId);
  
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [confirmModalOpen, setConfirmModalOpen] = useState(false);
  const [pendingActivityId, setPendingActivityId] = useState<number | null>(null);
  const [pendingActivity, setPendingActivity] = useState<any | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const initializedRef = useRef(false);

  const sessionKey = getChatSessionKey(patientId);

  // If no patient is selected, show a gentle prompt instead of rendering nothing
  if (!patientId) {
    return (
      <div className="h-[calc(100vh-200px)] flex items-center justify-center">
        <Card className="max-w-md w-full">
          <CardHeader>
            <CardTitle>AI Chat</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground space-y-2">
            <p>No patient is selected. Please log in or choose a patient to chat.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Load session history if present; otherwise start with welcome
  useEffect(() => {
    if (!patientId || initializedRef.current) return;

    const stored = loadChatSession(patientId);
    if (stored && stored.length > 0) {
      setMessages(stored);
    } else {
      setMessages([
        {
          id: 'welcome',
          role: 'assistant',
          content: `Hello! I'm your AdherenceGuardian AI assistant. I can help you with:\n\n• Medication schedules and reminders\n• Understanding your medications\n• Tracking adherence\n• Reporting symptoms or side effects\n• Answering health questions\n\nHow can I help you today?`,
          timestamp: new Date().toISOString(),
        },
      ]);
    }
    initializedRef.current = true;
  }, [patientId]);

  // Persist chat per session/patient (tab-scoped)
  useEffect(() => {
    if (!sessionKey) return;
    saveChatSession(patientId, messages);
  }, [messages, patientId, sessionKey]);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  const handleSend = async (content: string) => {
    if (!content.trim() || !patientId) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: content.trim(),
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    try {
      // Send message to backend chat endpoint which routes to agents
      const response = await sendMessage.mutateAsync({
        message: content.trim(),
        context: { patient_id: patientId },
      });

      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.response || 'Sorry, I could not generate a response.',
        timestamp: new Date().toISOString(),
        actions: response.suggested_actions,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // If assistant is asking to clarify the timezone, auto-confirm using the
      // patient's profile timezone (user requested inference from profile).
      try {
        const tzQuestionRe = /clarify if these times are intended to be in the/i;
        if (
          assistantMessage.content &&
          tzQuestionRe.test(assistantMessage.content) &&
          currentPatient?.timezone
        ) {
          const confirmText = `Yes — please use ${currentPatient.timezone} timezone.`;
          // small delay so the assistant message renders before we send
          setTimeout(() => handleSend(confirmText), 600);
        }
      } catch (e) {
        // swallow any errors to avoid breaking chat flow
      }

      // If agents performed actions, invalidate queries
      if (response.actions_taken && response.actions_taken.length > 0) {
        // Look for an agent_activity entry and, if found, poll its status and show a confirmation modal
        const act = response.actions_taken.find((a: any) => a.type === 'agent_activity' && a.activity_id);
        if (act && act.activity_id) {
          setPendingActivityId(act.activity_id);
          setConfirmModalOpen(true);
        } else {
          // no agent activity id returned — still invalidate caches
          queryClient.invalidateQueries({ queryKey: ['medications', patientId] });
          queryClient.invalidateQueries({ queryKey: ['dashboardStats', patientId] });
          queryClient.invalidateQueries({ queryKey: ['todaySchedule', patientId] });
        }
      }
    } catch (error: any) {
      const errMsg: ChatMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: `I encountered an error: ${error?.message || error}. Please try again.`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsTyping(false);
    }
  };

  // All message generation is handled by backend agents via `sendMessage`.
  // We keep no hardcoded responses here so agents provide the answers.

  // Poll agent activity endpoint when we have a pending activity id
  useEffect(() => {
    if (!pendingActivityId) return;
    let mounted = true;
    let attempts = 0;
    const maxAttempts = 60; // poll up to 60s

    const fetchActivity = async () => {
      try {
        const res = await fetch(`/api/v1/chat/activity/${pendingActivityId}`);
        if (!res.ok) throw new Error('Failed to fetch activity');
        const json = await res.json();
        if (!mounted) return;
        setPendingActivity(json);
        // If activity finished successfully, close modal and invalidate caches
        if (json.is_successful) {
          setConfirmModalOpen(false);
          setPendingActivityId(null);
          queryClient.invalidateQueries({ queryKey: ['medications', patientId] });
          queryClient.invalidateQueries({ queryKey: ['todaySchedule', patientId] });
          queryClient.invalidateQueries({ queryKey: ['dashboardStats', patientId] });
        }
      } catch (e) {
        // ignore transient errors
      }
      attempts += 1;
      if (mounted && !pendingActivity?.is_successful && attempts < maxAttempts) {
        setTimeout(fetchActivity, 1000);
      }
    };

    fetchActivity();

    return () => {
      mounted = false;
    };
  }, [pendingActivityId, patientId, queryClient]);

  const handleQuickAction = async (action: QuickAction) => {
    // Prefer backend quick-action routing to allow agents to act
    try {
      setIsTyping(true);
      // Add user-like quick action message
      const actionMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: action.label,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, actionMsg]);

      const response = await quickAction.mutateAsync({ action: action.label });

      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.response || 'Action completed.',
        timestamp: new Date().toISOString(),
        actions: response.suggested_actions,
      };
      setMessages((prev) => [...prev, assistantMessage]);

      // Also auto-confirm timezone questions for quick-action responses
      try {
        const tzQuestionRe = /clarify if these times are intended to be in the/i;
        if (
          assistantMessage.content &&
          tzQuestionRe.test(assistantMessage.content) &&
          currentPatient?.timezone
        ) {
          const confirmText = `Yes — please use ${currentPatient.timezone} timezone.`;
          setTimeout(() => handleSend(confirmText), 600);
        }
      } catch (e) {
        /* ignore */
      }

      if (response.actions_taken && response.actions_taken.length > 0) {
        queryClient.invalidateQueries({ queryKey: ['todaySchedule', patientId] });
        queryClient.invalidateQueries({ queryKey: ['dashboardStats', patientId] });
      }
    } catch (err: any) {
      const errMsg: ChatMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: `Quick action failed: ${err?.message || err}`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(input);
    }
  };

  return (
    <div className="h-[calc(100vh-200px)] flex flex-col">
      <Card className="flex-1 flex flex-col overflow-hidden">
        <CardHeader className="border-b">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-lg">
              <Bot className="h-6 w-6 text-primary" />
            </div>
            <div>
              <CardTitle className="flex items-center gap-2">
                AI Health Assistant
                <Badge variant="success" className="text-xs">
                  <Sparkles className="h-3 w-3 mr-1" />
                  Online
                </Badge>
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                Powered by AdherenceGuardian AI
              </p>
            </div>
          </div>
        </CardHeader>

        {/* Messages */}
        <CardContent className="flex-1 overflow-hidden p-0">
          <ScrollArea className="h-full" ref={scrollRef}>
            <div className="p-4 space-y-4">
              <AnimatePresence>
                {messages.map((message, index) => (
                  <motion.div
                    key={message.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className={cn(
                      "flex gap-3",
                      message.role === 'user' && "flex-row-reverse"
                    )}
                  >
                    <Avatar className="h-8 w-8 shrink-0">
                      {message.role === 'assistant' ? (
                        <>
                          <AvatarFallback className="bg-primary text-primary-foreground">
                            <Bot className="h-4 w-4" />
                          </AvatarFallback>
                        </>
                      ) : (
                        <>
                          <AvatarFallback className="bg-secondary">
                            <User className="h-4 w-4" />
                          </AvatarFallback>
                        </>
                      )}
                    </Avatar>

                    <div
                      className={cn(
                        "max-w-[80%] rounded-2xl px-4 py-3",
                        message.role === 'assistant'
                          ? "bg-muted"
                          : "bg-primary text-primary-foreground"
                      )}
                    >
                      <div
                        className={cn(
                          "text-sm whitespace-pre-wrap",
                          message.role === 'assistant'
                            ? "prose prose-sm dark:prose-invert max-w-none"
                            : ""
                        )}
                        dangerouslySetInnerHTML={{
                          __html: message.content
                            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                            .replace(/\n/g, '<br />'),
                        }}
                      />
                      <p
                        className={cn(
                          "text-xs mt-2",
                          message.role === 'assistant'
                            ? "text-muted-foreground"
                            : "text-primary-foreground/70"
                        )}
                      >
                        {safeFormatTime(message.timestamp) || 'Just now'}
                      </p>

                      {/* Suggested Actions */}
                      {message.actions && message.actions.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {message.actions.map((action) => (
                            <Button
                              key={action.id}
                              variant="outline"
                              size="sm"
                              className="text-xs"
                              onClick={() => handleQuickAction(action)}
                            >
                              {getActionIcon(action.type)}
                              <span className="ml-1">{action.label}</span>
                            </Button>
                          ))}
                        </div>
                      )}
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>

              {/* Typing Indicator */}
              {isTyping && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex gap-3"
                >
                  <Avatar className="h-8 w-8 shrink-0">
                    <AvatarFallback className="bg-primary text-primary-foreground">
                      <Bot className="h-4 w-4" />
                    </AvatarFallback>
                  </Avatar>
                  <div className="bg-muted rounded-2xl px-4 py-3">
                    <div className="flex items-center gap-1">
                      <span className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-2 h-2 bg-muted-foreground/50 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                </motion.div>
              )}
            </div>
          </ScrollArea>
        </CardContent>

        {/* Quick Actions (always visible) */}
        <div className="px-4 py-3 border-t bg-muted/30">
          <p className="text-xs text-muted-foreground mb-2">Quick Actions</p>
          <div className="flex flex-wrap gap-2">
            {QUICK_ACTIONS.map((action) => (
              <Button
                key={action.id}
                variant="outline"
                size="sm"
                className="text-xs"
                onClick={() => handleQuickAction(action)}
              >
                {getActionIcon(action.type)}
                <span className="ml-1">{action.label}</span>
                <ChevronRight className="h-3 w-3 ml-1" />
              </Button>
            ))}
          </div>
        </div>

        {/* Input */}
        <div className="p-4 border-t bg-background">
          <div className="flex items-center gap-2">
            <Input
              ref={inputRef}
              placeholder="Type your message..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyPress}
              disabled={isTyping}
              className="flex-1"
            />
            <Button
              onClick={() => handleSend(input)}
              disabled={!input.trim() || isTyping}
              size="icon"
            >
              {isTyping ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-2 text-center">
            AI responses are for informational purposes. Always consult your healthcare provider.
          </p>
        </div>
      </Card>
      {/* Confirmation Modal (simple inline modal) */}
      {confirmModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40" onClick={() => { setConfirmModalOpen(false); setPendingActivityId(null); }} />
          <div className="relative bg-white dark:bg-slate-800 rounded-lg shadow-lg max-w-lg w-full p-4 z-10">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Adding medication...</h3>
              <Button variant="ghost" size="sm" onClick={() => { setConfirmModalOpen(false); setPendingActivityId(null); }}>Close</Button>
            </div>
            <div className="py-2">
              {pendingActivity ? (
                <div className="text-sm">
                  <p className="mb-2">Status: {pendingActivity.is_successful ? 'Completed' : (pendingActivity.error_message ? 'Failed' : 'Processing')}</p>
                  {pendingActivity.output_data && (
                    <pre className="text-xs bg-muted p-2 rounded">{JSON.stringify(pendingActivity.output_data, null, 2)}</pre>
                  )}
                  {pendingActivity.error_message && (
                    <p className="text-xs text-destructive mt-2">{pendingActivity.error_message}</p>
                  )}
                </div>
              ) : (
                <p className="text-sm">Waiting for the system to apply the new medication. This may take a few seconds.</p>
              )}
            </div>
            <div className="mt-4 flex justify-end">
              <Button variant="secondary" onClick={() => { setConfirmModalOpen(false); setPendingActivityId(null); }}>Close</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
