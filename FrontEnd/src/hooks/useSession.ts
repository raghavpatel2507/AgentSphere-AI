import { useState, useEffect, useCallback, useRef } from 'react';
import { createSession, getSessionHistory, deleteSession, listSessions, type Session, type Message } from '@/lib/api';
import { toast } from 'sonner';

const TENANT_ID = '550e8400-e29b-41d4-a716-446655440000';
const USER_ID = '550e8400-e29b-41d4-a716-446655440001';
const STORAGE_KEY = 'agentsphere-session-id';

export function useSession() {
  const [session, setSession] = useState<Session | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const initRef = useRef(false);

  const fetchSessions = useCallback(async () => {
    try {
      const list = await listSessions(TENANT_ID, USER_ID);
      setSessions(list);
    } catch (err) {
      console.error('Failed to fetch sessions:', err);
    }
  }, []);

  const initSession = useCallback(async (forceNew = false) => {
    setLoading(true);
    setError(null);

    try {
      if (forceNew) {
        localStorage.removeItem(STORAGE_KEY);
      }

      // 1. Fetch existing sessions first
      const list = await listSessions(TENANT_ID, USER_ID);
      setSessions(list);

      let sessionIdToLoad = localStorage.getItem(STORAGE_KEY);
      let sessionToLoad = null;

      // 2. Determine which session to load
      if (!forceNew && list.length > 0) {
        if (sessionIdToLoad) {
          // Check if stored session still exists
          sessionToLoad = list.find(s => s.session_id === sessionIdToLoad);
        }

        // If no stored session or it doesn't exist anymore, pick the latest
        if (!sessionToLoad) {
          sessionToLoad = list[0];
          sessionIdToLoad = sessionToLoad.session_id;
          localStorage.setItem(STORAGE_KEY, sessionIdToLoad);
        }
      }

      // 3. Create or resume session
      const currentSession = await createSession(TENANT_ID, USER_ID, forceNew, sessionIdToLoad || undefined);
      setSession(currentSession);
      localStorage.setItem(STORAGE_KEY, currentSession.session_id);

      // 4. Load history
      if (!currentSession.is_new) {
        try {
          const history = await getSessionHistory(
            currentSession.session_id,
            TENANT_ID,
            USER_ID
          );
          setMessages(history);
        } catch {
          setMessages([]);
        }
      } else {
        setMessages([]);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to initialize session';
      setError(errorMessage);
      toast.error('Connection Error', {
        description: 'Could not connect to server. Please check if the API is running.',
      });
    } finally {
      setLoading(false);
    }
  }, [fetchSessions]);

  const switchSession = useCallback(async (sessionId: string) => {
    setLoading(true);
    try {
      const history = await getSessionHistory(sessionId, TENANT_ID, USER_ID);
      setMessages(history);
      setSession({
        session_id: sessionId,
        tenant_id: TENANT_ID,
        created_at: '',
        is_new: false
      });
      localStorage.setItem(STORAGE_KEY, sessionId);
    } catch (err) {
      toast.error('Failed to switch session');
    } finally {
      setLoading(false);
    }
  }, []);

  const addMessage = useCallback((message: Message) => {
    setMessages((prev) => [...prev, message]);
  }, []);

  const updateLastAssistantMessage = useCallback((content: string) => {
    setMessages((prev) => {
      const updated = [...prev];
      const lastIndex = updated.length - 1;
      if (lastIndex >= 0 && updated[lastIndex].role === 'assistant') {
        updated[lastIndex] = { ...updated[lastIndex], content };
      }
      return updated;
    });
  }, []);

  const toggleReaction = useCallback((messageIndex: number, emoji: string) => {
    setMessages((prev) => {
      const updated = [...prev];
      const message = updated[messageIndex];
      if (!message) return prev;

      const reactions = message.reactions || [];
      const hasReaction = reactions.includes(emoji);

      updated[messageIndex] = {
        ...message,
        reactions: hasReaction
          ? reactions.filter((r) => r !== emoji)
          : [...reactions, emoji],
      };
      return updated;
    });
  }, []);

  const deleteSessionById = useCallback(async (sessionId: string) => {
    try {
      await deleteSession(sessionId);
      if (session?.session_id === sessionId) {
        setMessages([]);
        initSession(true);
      } else {
        fetchSessions();
      }
      toast.success('Conversation deleted');
    } catch (err) {
      toast.error('Failed to delete conversation');
    }
  }, [session, initSession, fetchSessions]);

  const clearSession = useCallback(async () => {
    // We no longer delete the session on the backend when starting a new chat.
    // This allows the previous chat to be saved in history.
    setMessages([]);
    initSession(true);
  }, [initSession]);

  useEffect(() => {
    if (!initRef.current) {
      initRef.current = true;
      initSession();
    }
  }, [initSession]);

  return {
    session,
    sessions,
    messages,
    loading,
    error,
    tenantId: TENANT_ID,
    userId: USER_ID,
    addMessage,
    updateLastAssistantMessage,
    clearSession,
    deleteSessionById,
    switchSession,
    fetchSessions,
    toggleReaction,
    reconnect: () => initSession(false),
  };
}
