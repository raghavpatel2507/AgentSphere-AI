import { Plus, MessageSquare, History, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface SidebarProps {
  sessions: any[];
  currentSessionId: string | null;
  onNewSession: () => void;
  onSwitchSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
}

export function Sidebar({
  sessions,
  currentSessionId,
  onNewSession,
  onSwitchSession,
  onDeleteSession,
}: SidebarProps) {
  return (
    <aside className="w-full h-full glass-sidebar flex flex-col border-none">
      {/* Logo */}
      <div className="p-6">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-orange-600 flex items-center justify-center shadow-lg shadow-primary/20">
            <MessageSquare className="w-4 h-4 text-primary-foreground" />
          </div>
          <h1 className="font-bold text-lg tracking-tight">AgentSphere</h1>
        </div>
      </div>

      {/* New Session */}
      <div className="px-4 mb-6">
        <Button
          onClick={onNewSession}
          className={cn(
            "w-full justify-start gap-3 h-14 rounded-2xl font-bold glass-modern-btn",
            "hover:scale-[1.02] active:scale-[0.98] transition-all duration-300 group"
          )}
        >
          <div className="w-8 h-8 rounded-xl bg-primary text-primary-foreground flex items-center justify-center shadow-lg group-hover:rotate-90 transition-transform duration-500">
            <Plus className="w-5 h-5" />
          </div>
          <span className="tracking-tight">New Conversation</span>
        </Button>
      </div>

      {/* History Section */}
      <div className="flex-1 flex flex-col min-h-0">
        <div className="px-6 py-2 flex items-center gap-2 text-muted-foreground">
          <History className="w-4 h-4" />
          <span className="text-xs font-bold uppercase tracking-widest">Recent Chats</span>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1 scrollbar-premium">
          {sessions.map((s) => (
            <div key={s.session_id} className="group relative">
              <button
                onClick={() => onSwitchSession(s.session_id)}
                className={cn(
                  "w-full text-left px-4 py-4 rounded-xl text-sm transition-all duration-300 flex items-center gap-3 pr-12 relative group/item",
                  currentSessionId === s.session_id
                    ? "glass-active text-primary font-bold"
                    : "text-muted-foreground hover:bg-white/5 hover:text-foreground"
                )}
              >
                {currentSessionId === s.session_id && (
                  <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-primary rounded-r-full shadow-[0_0_10px_rgba(var(--primary),0.5)]" />
                )}
                <MessageSquare className={cn(
                  "w-4 h-4 shrink-0 transition-transform duration-300 group-hover/item:scale-110",
                  currentSessionId === s.session_id ? "text-primary" : "text-muted-foreground/40 group-hover/item:text-primary/60"
                )} />
                <span className="truncate tracking-tight">{s.title || "New Conversation"}</span>
              </button>

              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteSession(s.session_id);
                }}
                className={cn(
                  "absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg opacity-0 group-hover:opacity-100 transition-all duration-200",
                  "hover:bg-destructive/10 hover:text-destructive text-muted-foreground/50"
                )}
                title="Delete conversation"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}

          {sessions.length === 0 && (
            <div className="px-4 py-8 text-center">
              <p className="text-xs text-muted-foreground">No recent chats</p>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-sidebar-border bg-muted/20">
        <div className="flex items-center gap-3 px-2">
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-primary/20 to-orange-600/20 border border-primary/10 flex items-center justify-center">
            <span className="text-[10px] font-bold text-primary">AS</span>
          </div>
          <div className="flex flex-col">
            <span className="text-xs font-semibold">Free Plan</span>
            <span className="text-[10px] text-muted-foreground">AgentSphere-AI v1.0</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
