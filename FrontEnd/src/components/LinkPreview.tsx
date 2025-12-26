import React, { useState, useEffect } from 'react';
import { ExternalLink, Loader2, Link as LinkIcon } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';

interface Metadata {
    title?: string;
    description?: string;
    image?: string;
    url: string;
}

interface LinkPreviewProps {
    url: string;
    className?: string;
}

const API_BASE = 'http://localhost:8000/api/v1';

export function LinkPreview({ url, className }: LinkPreviewProps) {
    const [metadata, setMetadata] = useState<Metadata | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);

    useEffect(() => {
        let isMounted = true;
        const fetchMetadata = async () => {
            try {
                const response = await fetch(`${API_BASE}/metadata?url=${encodeURIComponent(url)}`);
                if (!response.ok) throw new Error('Failed to fetch metadata');
                const data = await response.json();
                if (isMounted) {
                    setMetadata(data);
                    setLoading(false);
                }
            } catch (err) {
                console.error('Error fetching link metadata:', err);
                if (isMounted) {
                    setError(true);
                    setLoading(false);
                }
            }
        };

        fetchMetadata();
        return () => { isMounted = false; };
    }, [url]);

    if (loading) {
        return (
            <div className={cn("inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-card/30 backdrop-blur-sm border border-border animate-pulse mt-2", className)}>
                <Loader2 className="w-4 h-4 animate-spin text-primary" />
                <span className="text-xs text-muted-foreground">Loading preview...</span>
            </div>
        );
    }

    if (error || !metadata?.title) {
        return null; // Don't show anything if it fails or has no title
    }

    return (
        <motion.a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            whileHover={{ scale: 1.02, translateY: -2 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className={cn(
                "block mt-3 overflow-hidden rounded-2xl bg-card/40 backdrop-blur-md border border-white/10 shadow-xl hover:shadow-primary/20 transition-all duration-300 group/preview max-w-lg no-underline",
                className
            )}
        >
            <div className="flex flex-col sm:flex-row min-h-[140px]">
                {metadata.image && (
                    <div className="sm:w-64 h-40 sm:h-auto relative overflow-hidden bg-muted flex-shrink-0 group-hover/preview:shadow-2xl transition-shadow duration-500">
                        {/* Background Layer: Blurred Cover */}
                        <img
                            src={metadata.image}
                            alt=""
                            className="absolute inset-0 w-full h-full object-cover blur-xl scale-110 opacity-50 transition-transform duration-700 group-hover/preview:scale-125"
                        />

                        {/* Foreground Layer: Contain Original */}
                        <img
                            src={metadata.image}
                            alt={metadata.title}
                            className="relative z-10 w-full h-full object-contain transition-transform duration-700 group-hover/preview:scale-105"
                            onError={(e) => (e.currentTarget.style.display = 'none')}
                        />

                        <div className="absolute inset-0 z-20 bg-gradient-to-t from-black/40 via-transparent to-transparent opacity-60" />
                        <div className="absolute inset-0 z-20 border-r border-white/10 hidden sm:block" />
                    </div>
                )}
                <div className={cn(
                    "flex-1 p-5 flex flex-col justify-center gap-1.5 relative overflow-hidden",
                    !metadata.image && "sm:w-full"
                )}>
                    {/* Background Glow */}
                    <div className="absolute -right-10 -top-10 w-32 h-32 bg-primary/10 rounded-full blur-[80px]" />

                    <div className="flex items-center gap-2 mb-1 relative z-10">
                        <div className="p-1 rounded-md bg-primary/10 border border-primary/20">
                            <LinkIcon className="w-3 h-3 text-primary" />
                        </div>
                        <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-muted-foreground/90 truncate">
                            {new URL(url).hostname}
                        </span>
                    </div>

                    <h3 className="text-sm font-bold text-foreground line-clamp-2 leading-tight group-hover/preview:text-primary transition-colors duration-300 relative z-10">
                        {metadata.title}
                    </h3>

                    {metadata.description && (
                        <p className="text-xs text-muted-foreground line-clamp-2 mt-1 leading-relaxed opacity-90 relative z-10">
                            {metadata.description}
                        </p>
                    )}

                    <div className="flex items-center mt-3 text-[10px] font-black text-primary tracking-[0.2em] uppercase opacity-0 group-hover/preview:opacity-100 transition-all duration-500 transform translate-x-[-15px] group-hover/preview:translate-x-0 relative z-10">
                        EXPERIENCE <ExternalLink className="w-3 h-3 ml-2" />
                    </div>
                </div>
            </div>
        </motion.a>
    );
}
