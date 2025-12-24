import { useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface CodeBlockProps {
    language: string;
    value: string;
}

export const CodeBlock = ({ language, value }: CodeBlockProps) => {
    const [copied, setCopied] = useState(false);

    const onCopy = () => {
        navigator.clipboard.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="relative group rounded-xl overflow-hidden my-6 border border-white/10 bg-[#0d0d0d]/80 backdrop-blur-sm shadow-2xl">
            <div className="flex items-center justify-between px-4 py-2.5 bg-white/5 border-b border-white/5">
                <div className="flex items-center gap-2">
                    <div className="flex gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full bg-red-500/20 border border-red-500/40" />
                        <div className="w-2.5 h-2.5 rounded-full bg-amber-500/20 border border-amber-500/40" />
                        <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/20 border border-emerald-500/40" />
                    </div>
                    <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-[0.2em] ml-2">
                        {language || 'text'}
                    </span>
                </div>
                <button
                    onClick={onCopy}
                    className="flex items-center gap-2 px-3 py-1 rounded-lg text-[10px] font-bold text-muted-foreground hover:text-primary hover:bg-primary/10 transition-all duration-300"
                >
                    {copied ? (
                        <>
                            <Check className="w-3 h-3 text-emerald-500" />
                            <span className="text-emerald-500">COPIED</span>
                        </>
                    ) : (
                        <>
                            <Copy className="w-3 h-3" />
                            <span>COPY CODE</span>
                        </>
                    )}
                </button>
            </div>
            <div className="p-0 overflow-x-auto scrollbar-premium">
                <SyntaxHighlighter
                    language={language || 'text'}
                    style={vscDarkPlus}
                    customStyle={{
                        margin: 0,
                        padding: '1.5rem',
                        background: 'transparent',
                        fontSize: '0.85rem',
                        lineHeight: '1.6',
                    }}
                    codeTagProps={{
                        style: {
                            fontFamily: '"IBM Plex Mono", monospace',
                        },
                    }}
                >
                    {value}
                </SyntaxHighlighter>
            </div>
        </div>
    );
};
