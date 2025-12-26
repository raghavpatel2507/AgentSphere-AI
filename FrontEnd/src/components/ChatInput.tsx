import { useState, useRef, useEffect, KeyboardEvent } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  isStreaming?: boolean;
  placeholder?: string;
}

export function ChatInput({ onSend, disabled, isStreaming, placeholder }: ChatInputProps) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
    }
  }, [value]);

  // Autofocus when enabled
  useEffect(() => {
    if (!disabled && !isStreaming) {
      textareaRef.current?.focus();
    }
  }, [disabled, isStreaming]);

  const handleSubmit = () => {
    if (value.trim() && !disabled) {
      onSend(value);
      setValue('');
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="p-4 backdrop-blur-sm">
      <div
        className={cn(
          'relative flex items-end gap-3 p-2 rounded-2xl bg-secondary/50 border border-border transition-all duration-300 max-w-5xl mx-auto',
          !disabled && 'focus-within:border-primary/50 focus-within:shadow-[0_0_30px_-10px] focus-within:shadow-primary/30'
        )}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={placeholder || 'Type your message...'}
          rows={1}
          className={cn(
            'flex-1 resize-none bg-transparent px-3 py-2.5',
            'text-foreground placeholder:text-muted-foreground',
            'focus:outline-none',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'scrollbar-thin'
          )}
        />
        <Button
          onClick={handleSubmit}
          disabled={disabled || !value.trim()}
          size="icon"
          className={cn(
            'h-10 w-10 rounded-xl transition-all duration-300',
            'bg-gradient-to-br from-primary to-accent hover:from-primary/90 hover:to-accent/90',
            'text-primary-foreground shadow-lg shadow-primary/30',
            'disabled:opacity-50 disabled:shadow-none'
          )}
        >
          {isStreaming ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Send className="w-5 h-5" />
          )}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground mt-2 text-center">
        Press <kbd className="px-1.5 py-0.5 rounded bg-muted text-foreground font-mono text-[10px]">Enter</kbd> to send, <kbd className="px-1.5 py-0.5 rounded bg-muted text-foreground font-mono text-[10px]">Shift + Enter</kbd> for new line
      </p>
    </div>
  );
}
