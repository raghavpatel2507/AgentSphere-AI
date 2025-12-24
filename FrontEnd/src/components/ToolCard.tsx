import { Puzzle, Power } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { cn } from '@/lib/utils';

interface ToolCardProps {
  name: string;
  description: string;
  toolsCount: number;
  connected: boolean;
  onToggle: (enabled: boolean) => void;
}

export function ToolCard({
  name,
  description,
  toolsCount,
  connected,
  onToggle,
}: ToolCardProps) {
  return (
    <div 
      className={cn(
        "p-4 rounded-xl border transition-all duration-300",
        connected 
          ? "bg-gradient-to-br from-primary/5 to-orange-600/5 border-primary/30" 
          : "bg-secondary/30 border-border hover:border-border/80"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <div 
            className={cn(
              "p-2 rounded-lg transition-colors",
              connected 
                ? "bg-primary/20 text-primary" 
                : "bg-muted text-muted-foreground"
            )}
          >
            <Puzzle className="w-4 h-4" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="font-semibold text-sm truncate">{name}</p>
            <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{description}</p>
          </div>
        </div>
        <Switch
          checked={connected}
          onCheckedChange={onToggle}
          className="flex-shrink-0 data-[state=checked]:bg-primary"
        />
      </div>
      
      <div className="mt-3 flex items-center justify-between">
        <span
          className={cn(
            'tool-badge',
            connected ? 'tool-connected' : 'tool-disconnected'
          )}
        >
          <Power className="w-3 h-3" />
          {connected ? 'Active' : 'Inactive'}
        </span>
        <span className="text-xs text-muted-foreground font-medium">
          {toolsCount} {toolsCount === 1 ? 'tool' : 'tools'}
        </span>
      </div>
    </div>
  );
}
