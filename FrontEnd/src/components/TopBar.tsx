import { Hash, Wifi, WifiOff, Trash2, RefreshCw, Settings2, Globe, Server, Palette, Menu } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useState } from 'react';
import type { Tool } from '@/lib/api';

interface TopBarProps {
  sessionId: string | null;
  connected: boolean;
  loading: boolean;
  tools: Tool[];
  toolsLoading: boolean;
  onClearSession: () => void;
  onReconnect: () => void;
  onOpenTheme: () => void;
  onOpenMenu: () => void;
}

export function TopBar({
  sessionId,
  connected,
  loading,
  tools,
  toolsLoading,
  onClearSession,
  onReconnect,
  onOpenTheme,
  onOpenMenu,
}: TopBarProps) {
  const [showMCP, setShowMCP] = useState(false);
  const connectedCount = tools.filter(t => t.connected).length;

  return (
    <header className="glass-topbar flex items-center justify-between px-3 md:px-6 h-16">
      <div className="flex items-center gap-2 md:gap-6">
        {onOpenMenu && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onOpenMenu}
            className="md:hidden h-9 w-9 text-muted-foreground hover:bg-primary/10 hover:text-primary transition-colors"
          >
            <Menu className="w-5 h-5" />
          </Button>
        )}
        <div className="flex items-center gap-2 px-2.5 md:px-3 py-1.5 rounded-lg bg-secondary/50 border border-border font-mono text-sm shadow-inner overflow-hidden">
          <Hash className="w-3.5 h-3.5 text-primary" />
          <span className="text-muted-foreground hidden md:inline">Session:</span>
          <span className="text-foreground font-medium">
            {loading ? '...' : sessionId ? (sessionId.includes('_thread_') ? sessionId.split('_thread_')[1] : sessionId.slice(-8)) : '—'}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2 md:gap-4">
        {/* Theme Button */}
        <Button
          variant="outline"
          size="sm"
          onClick={onOpenTheme}
          className="text-xs h-9 md:h-10 w-9 md:w-auto gap-2 transition-all duration-300 rounded-xl px-0 md:px-5 hover:bg-primary/10 hover:text-primary hover:border-primary/50 group"
        >
          <Palette className="w-4 h-4 transition-transform group-hover:rotate-12" />
          <span className="hidden md:inline font-semibold">Theme</span>
        </Button>

        {/* MCP Connect Button */}
        <div className="relative">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowMCP(!showMCP)}
            className={cn(
              "text-xs h-9 md:h-10 w-16 md:w-auto gap-1 md:gap-2 transition-all duration-300 rounded-xl px-0 md:px-4",
              showMCP ? "bg-primary/10 border-primary/50 text-primary shadow-[0_0_15px_rgba(var(--primary),0.1)]" : "hover:bg-secondary"
            )}
          >
            <Server className="w-4 h-4" />
            <span className="hidden md:inline font-semibold">MCP Connect</span>
            <div className="flex items-center gap-1 ml-0 md:ml-1 bg-muted/50 px-1.5 md:px-2 py-0.5 rounded-full text-[10px] font-bold">
              <span className="text-emerald-500">{connectedCount}</span>
              <span className="text-muted-foreground mr-[1px]">/</span>
              <span>{tools.length}</span>
            </div>
          </Button>
          {/* ... MCP dropdown content remains same ... */}
          {showMCP && (
            <>
              <div
                className="fixed inset-0 z-40 bg-background/20 backdrop-blur-[2px]"
                onClick={() => setShowMCP(false)}
              />
              <div className="absolute top-full right-0 mt-3 w-80 bg-card border border-border rounded-2xl shadow-2xl z-50 overflow-hidden animate-in fade-in zoom-in slide-in-from-top-2 duration-200">
                <div className="p-4 border-b border-border bg-muted/30 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Settings2 className="w-4 h-4 text-primary" />
                    <h3 className="text-xs font-bold uppercase tracking-wider">MCP Servers</h3>
                  </div>
                  {toolsLoading && <RefreshCw className="w-3 h-3 animate-spin text-primary" />}
                </div>
                <div className="p-2 max-h-[400px] overflow-y-auto scrollbar-premium">
                  <div className="space-y-1">
                    {tools.map(t => (
                      <div key={t.name} className="flex items-center justify-between p-3 rounded-xl hover:bg-muted/50 transition-colors border border-transparent hover:border-border/50 group">
                        <div className="flex items-center gap-3 min-w-0">
                          <div className={cn(
                            "w-2 h-2 rounded-full shrink-0",
                            t.connected
                              ? "bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.4)]"
                              : "bg-muted-foreground/30"
                          )} />
                          <div className="flex flex-col min-w-0">
                            <span className="text-sm font-medium truncate group-hover:text-primary transition-colors">{t.name}</span>
                            <span className="text-[10px] text-muted-foreground">{t.tools_count} tools available</span>
                          </div>
                        </div>
                        <div className={cn(
                          "px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-tighter",
                          t.connected ? "bg-emerald-500/10 text-emerald-500" : "bg-muted text-muted-foreground"
                        )}>
                          {t.connected ? "Active" : "Offline"}
                        </div>
                      </div>
                    ))}
                    {tools.length === 0 && !toolsLoading && (
                      <div className="py-12 text-center">
                        <Globe className="w-8 h-8 text-muted-foreground/20 mx-auto mb-2" />
                        <p className="text-xs text-muted-foreground">No MCP servers configured</p>
                      </div>
                    )}
                  </div>
                </div>
                <div className="p-3 bg-muted/10 border-t border-border text-[10px] text-muted-foreground text-center italic">
                  Manage your MCP connections in the config file
                </div>
              </div>
            </>
          )}
        </div>

        <div
          className={cn(
            'flex items-center gap-2 px-3 md:px-5 py-2 rounded-xl text-xs font-bold transition-all duration-300 border shadow-sm h-10',
            connected
              ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
              : 'bg-destructive/10 text-destructive border-destructive/20'
          )}
        >
          <div className={cn(
            "w-1.5 h-1.5 rounded-full animate-pulse",
            connected ? "bg-emerald-500" : "bg-destructive"
          )} />
          <span className="hidden md:inline">System {connected ? 'Online' : 'Offline'}</span>
        </div>

        <div className="w-px h-6 bg-border mx-2" />

        <Button
          variant="ghost"
          size="sm"
          onClick={onClearSession}
          className="text-muted-foreground hover:text-destructive hover:bg-destructive/10 h-9 md:h-10 w-9 md:w-auto rounded-xl px-0 md:px-4 transition-colors font-semibold"
        >
          <Trash2 className="w-4 h-4 md:mr-2" />
          <span className="text-xs hidden md:inline">Clear Chat</span>
        </Button>
      </div>
    </header>
  );
}
