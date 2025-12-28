import { useState, useCallback } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { chatApi } from '@/services/api';
import type { ChatMessage, ChatResponse } from '@/types';

// Hook to get chat messages history
export function useChatMessages(patientId: number | null) {
  return useQuery<ChatMessage[]>({
    queryKey: ['chatMessages', patientId],
    queryFn: async () => {
      if (!patientId) return [];
      return chatApi.getHistory(patientId, 50);
    },
    enabled: !!patientId,
  });
}

// Hook to send a message
export function useSendMessage(patientId: number | null) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (data: { message: string; context?: Record<string, unknown> }) => {
      if (!patientId) throw new Error('No patient selected');
      return chatApi.send(patientId, data.message, data.context);
    },
    onSuccess: () => {
      if (!patientId) return;
      queryClient.invalidateQueries({ queryKey: ['chatMessages', patientId] });
    },
  });
}

// Hook to perform quick actions
export function useQuickActions(patientId: number | null) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (data: { action: string; params?: Record<string, unknown> }) => {
      if (!patientId) throw new Error('No patient selected');
      return chatApi.quickAction(patientId, data.action, data.params);
    },
    onSuccess: () => {
      if (!patientId) return;
      queryClient.invalidateQueries({ queryKey: ['chatMessages', patientId] });
      queryClient.invalidateQueries({ queryKey: ['dashboardStats', patientId] });
      queryClient.invalidateQueries({ queryKey: ['todaySchedule', patientId] });
    },
  });
}

export function useChat(patientId: number | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const queryClient = useQueryClient();

  // Load chat history
  const { isLoading: isLoadingHistory } = useQuery({
    queryKey: ['chatHistory', patientId],
    queryFn: async () => {
      if (!patientId) return [];
      const history = await chatApi.getHistory(patientId, 50);
      // Convert history to messages
      const initialMessages: ChatMessage[] = [];
      // Add a welcome message if no history
      if (history.length === 0) {
        initialMessages.push({
          id: 'welcome',
          role: 'assistant',
          content: `👋 Hello! I'm your AdherenceGuardian AI assistant. I can help you with:

• **Medication questions** - dosage, timing, interactions
• **Schedule management** - set up reminders, optimize your routine
• **Adherence tracking** - check your progress, identify patterns
• **Symptom reporting** - log side effects, get guidance
• **Provider communication** - generate reports for your healthcare team

How can I help you today?`,
          timestamp: new Date().toISOString(),
        });
      }
      setMessages(initialMessages);
      return history;
    },
    enabled: !!patientId,
  });

  // Send message mutation
  const sendMessageMutation = useMutation({
    mutationFn: async ({ message, context }: { message: string; context?: Record<string, unknown> }) => {
      if (!patientId) throw new Error('No patient selected');
      return chatApi.send(patientId, message, context);
    },
    onMutate: async ({ message }) => {
      // Optimistically add user message
      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: message,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsTyping(true);
    },
    onSuccess: (response: ChatResponse) => {
      // Add assistant response
      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.response,
        timestamp: new Date().toISOString(),
        metadata: {
          agent: response.agent_used,
          action: response.actions_taken?.join(', '),
          sources: response.sources,
        },
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsTyping(false);
      
      // Invalidate relevant queries if actions were taken
      if (response.actions_taken && response.actions_taken.length > 0) {
        queryClient.invalidateQueries({ queryKey: ['dashboardStats', patientId] });
        queryClient.invalidateQueries({ queryKey: ['todaySchedule', patientId] });
        queryClient.invalidateQueries({ queryKey: ['adherenceRate', patientId] });
      }
    },
    onError: (error) => {
      setIsTyping(false);
      const errorMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: `I apologize, but I encountered an error: ${error.message}. Please try again.`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    },
  });

  // Quick action mutation
  const quickActionMutation = useMutation({
    mutationFn: async ({ action, params }: { action: string; params?: Record<string, unknown> }) => {
      if (!patientId) throw new Error('No patient selected');
      return chatApi.quickAction(patientId, action, params);
    },
    onMutate: ({ action }) => {
      setIsTyping(true);
      // Add a system message about the action
      const actionMessage: ChatMessage = {
        id: `action-${Date.now()}`,
        role: 'user',
        content: `[Quick Action: ${action}]`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, actionMessage]);
    },
    onSuccess: (response: ChatResponse) => {
      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.response,
        timestamp: new Date().toISOString(),
        metadata: {
          agent: response.agent_used,
          action: response.actions_taken?.join(', '),
        },
      };
      setMessages((prev) => [...prev, assistantMessage]);
      setIsTyping(false);
      
      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: ['dashboardStats', patientId] });
      queryClient.invalidateQueries({ queryKey: ['todaySchedule', patientId] });
    },
    onError: (error) => {
      setIsTyping(false);
      const errorMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: `Failed to perform action: ${error.message}`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    },
  });

  const sendMessage = useCallback(
    (message: string, context?: Record<string, unknown>) => {
      if (!message.trim()) return;
      sendMessageMutation.mutate({ message, context });
    },
    [sendMessageMutation]
  );

  const performQuickAction = useCallback(
    (action: string, params?: Record<string, unknown>) => {
      quickActionMutation.mutate({ action, params });
    },
    [quickActionMutation]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return {
    messages,
    isTyping,
    isLoadingHistory,
    sendMessage,
    performQuickAction,
    clearMessages,
    isSending: sendMessageMutation.isPending,
  };
}
