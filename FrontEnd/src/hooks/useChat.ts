import { useState, useCallback } from 'react';
import { streamChat, type Message } from '@/lib/api';
import { toast } from 'sonner';

interface UseChatOptions {
  sessionId: string | null;
  tenantId: string;
  userId: string;
  addMessage: (message: Message) => void;
  updateLastAssistantMessage: (content: string) => void;
  onMessageSent?: () => void;
}

export function useChat({
  sessionId,
  tenantId,
  userId,
  addMessage,
  updateLastAssistantMessage,
  onMessageSent,
}: UseChatOptions) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [isPlanning, setIsPlanning] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [planContent, setPlanContent] = useState<any>(null);
  const [agentStatus, setAgentStatus] = useState<'planning' | 'searching' | 'executing' | 'thinking' | 'completing' | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>('');

  const sendMessage = useCallback(
    async (content: string) => {
      if (!sessionId || !content.trim() || isStreaming) return;

      const trimmedContent = content.trim();

      // Add user message immediately
      addMessage({ role: 'user', content: trimmedContent });

      // Add empty assistant message for streaming
      addMessage({ role: 'assistant', content: '' });

      setIsStreaming(true);
      setIsRunning(true);
      setIsPlanning(false);
      setPlanContent(null);

      let fullContent = '';

      try {
        for await (const event of streamChat(sessionId, tenantId, userId, trimmedContent)) {
          switch (event.type) {
            case 'status':
              setAgentStatus(event.status);
              setStatusMessage(event.message || '');
              break;
            case 'plan':
              setIsPlanning(true);
              setPlanContent(event.content);
              break;
            case 'token':
              setIsPlanning(false);
              setAgentStatus(null);
              if (typeof event.content === 'string') {
                fullContent += event.content;
                updateLastAssistantMessage(fullContent);
              }
              break;
            case 'done':
              setIsPlanning(false);
              setPlanContent(null);
              setAgentStatus(null);
              setStatusMessage('');
              break;
          }
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to send message';
        toast.error('Error', {
          description: errorMessage,
        });
        updateLastAssistantMessage('*Error: Could not get response from agent*');
      } finally {
        setIsStreaming(false);
        setIsPlanning(false);
        setIsRunning(false);
        setAgentStatus(null);
        setStatusMessage('');
        if (onMessageSent) onMessageSent();
      }
    },
    [sessionId, tenantId, userId, isStreaming, addMessage, updateLastAssistantMessage, onMessageSent]
  );

  return {
    sendMessage,
    isStreaming,
    isPlanning,
    isRunning,
    planContent,
    agentStatus,
    statusMessage,
  };
}
