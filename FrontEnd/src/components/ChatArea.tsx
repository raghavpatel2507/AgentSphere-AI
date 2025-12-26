import { useEffect, useRef } from 'react';
import { Sparkles, Loader2, MessageSquarePlus } from 'lucide-react';
import { ChatMessage } from '@/components/ChatMessage';
import { ChatInput } from '@/components/ChatInput';
import { Skeleton } from '@/components/ui/skeleton';
import type { Message } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useTheme } from '@/hooks/useTheme';
import { ChatSkeleton } from '@/components/SkeletonLoader';
import { TypingIndicator } from '@/components/TypingIndicator';
import { AgentStatusIndicator } from '@/components/AgentStatusIndicator';

interface ChatAreaProps {
  messages: Message[];
  loading: boolean;
  isStreaming: boolean;
  isPlanning: boolean;
  isRunning: boolean;
  planContent: any;
  agentStatus: 'planning' | 'searching' | 'executing' | 'thinking' | 'completing' | null;
  statusMessage: string;
  onSendMessage: (content: string) => void;
  onReact: (messageIndex: number, emoji: string) => void;
}

export function ChatArea({
  messages,
  loading,
  isStreaming,
  isPlanning,
  isRunning,
  planContent,
  agentStatus,
  statusMessage,
  onSendMessage,
  onReact,
}: ChatAreaProps) {
  const { settings } = useTheme();
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isPlanning]);

  return (
    <div
      className="flex-1 flex flex-col relative overflow-hidden"
      style={{ fontSize: settings.fontSize }}
    >
      {/* Background Image with Overlay */}
      <div
        className="absolute inset-0 z-0 bg-cover bg-center bg-no-repeat transition-all duration-500"
        style={{
          backgroundImage: `url("${settings.backgroundImage}")`,
          filter: 'brightness(0.4) contrast(1.2)'
        }}
      />
      <div className="absolute inset-0 z-0 bg-gradient-to-b from-background/40 via-transparent to-background/60" />

      {/* Messages Area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-4 md:px-6 py-6 scrollbar-premium relative z-10"
      >
        {loading ? (
          <div className="max-w-5xl mx-auto">
            <ChatSkeleton />
          </div>
        ) : messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary/20 to-accent/20 flex items-center justify-center mb-6 shadow-lg shadow-primary/10">
              <MessageSquarePlus className="w-10 h-10 text-primary" />
            </div>
            <h2 className="text-2xl font-bold mb-3">Start a Conversation</h2>
            <p className="text-muted-foreground leading-relaxed">
              Send a message to begin chatting with the AI agent. Your conversation history will be saved automatically.
            </p>
          </div>
        ) : (
          <div className="max-w-5xl mx-auto space-y-4 px-2 sm:px-0">
            {messages.map((msg, index) => (
              <ChatMessage
                key={index}
                role={msg.role}
                content={msg.content}
                isDarkMode={settings.mode === 'dark'}
                reactions={msg.reactions}
                onReact={(emoji) => onReact(index, emoji)}
                isStreaming={
                  isStreaming &&
                  index === messages.length - 1 &&
                  msg.role === 'assistant'
                }
              />
            ))}
          </div>
        )}


        {/* Agent Status Indicator (Priority) */}
        {agentStatus ? (
          <div className="max-w-5xl mx-auto mt-4">
            <AgentStatusIndicator status={agentStatus} message={statusMessage} />
          </div>
        ) : isStreaming ? (
          /* Fallback Typing Indicator */
          <div className="max-w-5xl mx-auto mt-4">
            <TypingIndicator />
          </div>
        ) : null}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <ChatInput
        onSend={onSendMessage}
        disabled={isStreaming || loading}
        isStreaming={isStreaming}
        placeholder={
          isStreaming
            ? 'Agent is responding...'
            : 'Type your message...'
        }
      />
    </div>
  );
}
