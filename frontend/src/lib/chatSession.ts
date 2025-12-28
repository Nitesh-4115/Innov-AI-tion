export const sessionNonce = typeof performance !== 'undefined'
  ? Math.floor(performance.timeOrigin).toString()
  : 'session';

export const getChatSessionKey = (patientId: number | null) => {
  if (!patientId) return null;
  return `chat_session_${patientId}_${sessionNonce}`;
};

export const loadChatSession = (patientId: number | null) => {
  if (typeof window === 'undefined') return [];
  const key = getChatSessionKey(patientId);
  if (!key) return [];
  const raw = window.sessionStorage.getItem(key);
  if (!raw) return [];
  try {
    return JSON.parse(raw);
  } catch (err) {
    console.warn('Failed to parse chat session storage', err);
    return [];
  }
};

export const saveChatSession = (
  patientId: number | null,
  messages: any[]
) => {
  if (typeof window === 'undefined') return;
  const key = getChatSessionKey(patientId);
  if (!key) return;
  if (!messages || messages.length === 0) {
    window.sessionStorage.removeItem(key);
    return;
  }
  window.sessionStorage.setItem(key, JSON.stringify(messages));
};

export const appendChatSession = (
  patientId: number,
  newMessages: { role: 'user' | 'assistant'; content: string }[]
) => {
  if (typeof window === 'undefined') return;
  const key = getChatSessionKey(patientId);
  if (!key) return;
  const existing = loadChatSession(patientId);
  const timestamp = new Date().toISOString();
  const merged = [
    ...existing,
    ...newMessages.map((msg, idx) => ({
      id: `${msg.role}-${Date.now()}-${idx}`,
      role: msg.role,
      content: msg.content,
      timestamp,
    })),
  ];
  saveChatSession(patientId, merged);
};
