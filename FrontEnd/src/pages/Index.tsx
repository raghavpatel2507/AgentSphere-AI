import { Sidebar } from '@/components/Sidebar';
import { TopBar } from '@/components/TopBar';
import { ChatArea } from '@/components/ChatArea';
import { useSession } from '@/hooks/useSession';
import { useTools } from '@/hooks/useTools';
import { useChat } from '@/hooks/useChat';
import { Toaster } from 'sonner';
import { ThemeSettings } from '@/components/ThemeSettings';

import { CommandPalette } from '@/components/CommandPalette';
import { useState } from 'react';

import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";

const Index = () => {
  const [showTheme, setShowTheme] = useState(false);
  const {
    session,
    sessions,
    messages,
    loading: sessionLoading,
    tenantId,
    userId,
    addMessage,
    updateLastAssistantMessage,
    clearSession,
    deleteSessionById,
    switchSession,
    fetchSessions,
    toggleReaction,
    reconnect,
  } = useSession();

  const {
    tools,
    loading: toolsLoading,
    error: toolsError,
    toggleTool,
    refetch: refetchTools,
  } = useTools();

  const { sendMessage, isStreaming, isPlanning, isRunning, planContent, agentStatus, statusMessage } = useChat({
    sessionId: session?.session_id || null,
    tenantId,
    userId,
    addMessage,
    updateLastAssistantMessage,
    onMessageSent: fetchSessions,
  });

  return (
    <>
      <Toaster
        position="top-right"
        theme="dark"
        toastOptions={{
          style: {
            background: 'hsl(240 10% 6%)',
            border: '1px solid hsl(240 6% 18%)',
            color: 'hsl(0 0% 95%)',
          },
        }}
      />
      <CommandPalette
        onNewChat={clearSession}
        onOpenSettings={() => setShowTheme(true)}
      />
      <div className="flex h-screen w-full bg-background relative z-10">
        <ResizablePanelGroup direction="horizontal">
          <ResizablePanel defaultSize={20} minSize={15} maxSize={30}>
            <Sidebar
              sessions={sessions}
              currentSessionId={session?.session_id || null}
              onNewSession={clearSession}
              onSwitchSession={switchSession}
              onDeleteSession={deleteSessionById}
            />
          </ResizablePanel>
          <ResizableHandle withHandle className="bg-white/5 hover:bg-primary/20 transition-colors" />
          <ResizablePanel defaultSize={80}>
            <main className="flex-1 flex flex-col h-full overflow-hidden">
              <TopBar
                sessionId={session?.session_id || null}
                connected={!!session}
                loading={sessionLoading}
                tools={tools}
                toolsLoading={toolsLoading}
                onClearSession={clearSession}
                onReconnect={reconnect}
                onOpenTheme={() => setShowTheme(true)}
              />

              <ChatArea
                messages={messages}
                loading={sessionLoading}
                isStreaming={isStreaming}
                isPlanning={isPlanning}
                isRunning={isRunning}
                planContent={planContent}
                agentStatus={agentStatus}
                statusMessage={statusMessage}
                onSendMessage={sendMessage}
                onReact={toggleReaction}
              />
            </main>
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>
      <ThemeSettings open={showTheme} onOpenChange={setShowTheme} />
    </>
  );
};

export default Index;
