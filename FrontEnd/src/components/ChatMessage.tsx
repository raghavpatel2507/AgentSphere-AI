import { memo } from 'react';
import { User, Sparkles, Image as ImageIcon, Link as LinkIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { motion } from 'framer-motion';

import { CodeBlock } from './CodeBlock';
import { useTheme } from '@/hooks/useTheme';
import { LinkPreview } from './LinkPreview';

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  isDarkMode: boolean;
  isStreaming?: boolean;
  reactions?: string[];
  onReact?: (emoji: string) => void;
}

export const ChatMessage = memo(function ChatMessage({
  role,
  content,
  isDarkMode,
  isStreaming,
  reactions = [],
  onReact,
}: ChatMessageProps) {
  const isUser = role === 'user';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{
        duration: 0.4,
        ease: [0.16, 1, 0.3, 1],
        scale: { duration: 0.3 }
      }}
      className={cn(
        'flex gap-3 mb-6',
        isUser ? 'flex-row-reverse' : 'flex-row'
      )}
    >
      <div
        className={cn(
          'flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center',
          isUser
            ? 'bg-gradient-to-br from-primary to-accent shadow-lg shadow-primary/30'
            : 'bg-secondary border border-border'
        )}
      >
        {isUser ? (
          <User className="w-5 h-5 text-primary-foreground" />
        ) : (
          <Sparkles className="w-5 h-5 text-primary" />
        )}
      </div>

      <div
        className={cn(
          'message-bubble relative group/bubble',
          isUser ? 'message-user' : 'message-assistant'
        )}
      >
        {/* Reaction Picker (Hover) */}
        {!isStreaming && (
          <div className={cn(
            "absolute -top-10 opacity-0 group-hover/bubble:opacity-100 transition-all duration-300 flex gap-1 bg-card/90 backdrop-blur-md border border-white/10 p-1 rounded-full shadow-2xl z-30",
            isUser ? "right-0" : "left-0"
          )}>
            {['👍', '❤️', '🔥', '👏', '😮'].map(emoji => (
              <button
                key={emoji}
                className={cn(
                  "hover:scale-125 transition-transform px-1.5 py-0.5 rounded-full hover:bg-white/10",
                  reactions.includes(emoji) && "bg-primary/20"
                )}
                onClick={() => onReact?.(emoji)}
              >
                {emoji}
              </button>
            ))}
          </div>
        )}

        <div className={cn(
          "whitespace-pre-wrap break-words leading-relaxed prose max-w-none",
          isDarkMode && "prose-invert",
          "prose-p:leading-relaxed prose-pre:p-0 prose-pre:bg-transparent prose-pre:border-none prose-code:text-primary prose-code:bg-muted/50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none",
          "prose-headings:text-foreground prose-strong:text-foreground prose-em:text-foreground prose-ul:text-foreground prose-ol:text-foreground prose-li:text-foreground prose-blockquote:text-foreground/90",
          isUser ? "prose-p:text-primary-foreground" : "prose-p:text-foreground"
        )}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              a({ node, href, children, ...props }) {
                return (
                  <>
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1 my-1 rounded-lg bg-primary/10 border border-primary/20 text-primary font-bold hover:bg-primary/20 hover:underline transition-all duration-200 no-underline group/link max-w-full break-all flex-wrap"
                      {...props}
                    >
                      <span className="break-all">{children}</span>
                      <LinkIcon className="w-3 h-3 opacity-60 group-hover/link:opacity-100 transition-opacity flex-shrink-0" />
                    </a>
                    {!isStreaming && href && <LinkPreview url={href} />}
                  </>
                );
              },
              code({ node, className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || '');
                const isBlock = className?.includes('language-');
                return isBlock && match ? (
                  <CodeBlock
                    language={match[1]}
                    value={String(children).replace(/\n$/, '')}
                  />
                ) : (
                  <code className={className} {...props}>
                    {children}
                  </code>
                );
              },
            }}
          >
            {content}
          </ReactMarkdown>
          {isStreaming && <span className="streaming-cursor" />}
        </div>

        {/* Display Reactions */}
        {
          reactions.length > 0 && (
            <div className={cn(
              "flex gap-1.5 mt-2 flex-wrap",
              isUser ? "justify-end" : "justify-start"
            )}>
              {reactions.map(emoji => (
                <div
                  key={emoji}
                  className="bg-card/90 backdrop-blur-md border border-white/10 px-2 py-1 rounded-full text-sm shadow-sm animate-scale-in flex items-center justify-center min-w-[28px]"
                >
                  {emoji}
                </div>
              ))}
            </div>
          )
        }
      </div >
    </motion.div >
  );
});
