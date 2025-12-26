import { Sidebar } from '@/components/Sidebar';
import { TopBar } from '@/components/TopBar';
import { ChatArea } from '@/components/ChatArea';
import { useSession } from '@/hooks/useSession';
import { useTools } from '@/hooks/useTools';
import { useChat } from '@/hooks/useChat';
import { Toaster } from 'sonner';
import { ThemeSettings } from '@/components/ThemeSettings';
import { useIsMobile } from '@/hooks/use-mobile';
import { Sheet, SheetContent } from "@/components/ui/sheet";

import { CommandPalette } from '@/components/CommandPalette';
import { useState } from 'react';

import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";

const Index = () => {
  const [showTheme, setShowTheme] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const isMobile = useIsMobile();

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

  const sidebarProps = {
    sessions,
    currentSessionId: session?.session_id || null,
    onNewSession: () => {
      clearSession();
      setMobileMenuOpen(false);
    },
    onSwitchSession: (id: string) => {
      switchSession(id);
      setMobileMenuOpen(false);
    },
    onDeleteSession: deleteSessionById,
  };

  const mainContent = (
    <main className="flex-1 flex flex-col h-full overflow-hidden w-full">
      <TopBar
        sessionId={session?.session_id || null}
        connected={!!session}
        loading={sessionLoading}
        tools={tools}
        toolsLoading={toolsLoading}
        onClearSession={clearSession}
        onReconnect={reconnect}
        onOpenTheme={() => setShowTheme(true)}
        onOpenMenu={() => setMobileMenuOpen(true)}
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
  );

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
        {isMobile ? (
          <>
            <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
              <SheetContent side="left" className="p-0 border-none w-80">
                <Sidebar {...sidebarProps} />
              </SheetContent>
            </Sheet>
            {mainContent}
          </>
        ) : (
          <ResizablePanelGroup direction="horizontal">
            <ResizablePanel defaultSize={20} minSize={15} maxSize={30}>
              <Sidebar {...sidebarProps} />
            </ResizablePanel>
            <ResizableHandle withHandle className="bg-white/5 hover:bg-primary/20 transition-colors" />
            <ResizablePanel defaultSize={80}>
              {mainContent}
            </ResizablePanel>
          </ResizablePanelGroup>
        )}
      </div>
      <ThemeSettings open={showTheme} onOpenChange={setShowTheme} />
    </>
  );
};
export default Index;
