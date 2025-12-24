import { memo } from 'react';
import { Brain, Search, Wrench, Sparkles, Zap, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';

interface AgentStatusIndicatorProps {
    status: 'planning' | 'searching' | 'executing' | 'thinking' | 'completing' | null;
    message?: string;
}

const statusConfig = {
    planning: {
        icon: Brain,
        label: 'Planning',
        defaultMessage: 'Analyzing your request and creating a plan...',
        color: 'from-blue-500 to-cyan-500',
        bgColor: 'bg-blue-500/10',
        borderColor: 'border-blue-500/20',
    },
    searching: {
        icon: Search,
        label: 'Searching',
        defaultMessage: 'Finding the right tools and resources...',
        color: 'from-purple-500 to-pink-500',
        bgColor: 'bg-purple-500/10',
        borderColor: 'border-purple-500/20',
    },
    executing: {
        icon: Wrench,
        label: 'Executing',
        defaultMessage: 'Running tools and gathering information...',
        color: 'from-orange-500 to-red-500',
        bgColor: 'bg-orange-500/10',
        borderColor: 'border-orange-500/20',
    },
    thinking: {
        icon: Sparkles,
        label: 'Thinking',
        defaultMessage: 'Processing information and formulating response...',
        color: 'from-green-500 to-emerald-500',
        bgColor: 'bg-green-500/10',
        borderColor: 'border-green-500/20',
    },
    completing: {
        icon: CheckCircle2,
        label: 'Completing',
        defaultMessage: 'Finalizing response...',
        color: 'from-teal-500 to-cyan-500',
        bgColor: 'bg-teal-500/10',
        borderColor: 'border-teal-500/20',
    },
};

export const AgentStatusIndicator = memo(function AgentStatusIndicator({
    status,
    message,
}: AgentStatusIndicatorProps) {
    if (!status) return null;

    const config = statusConfig[status];
    const Icon = config.icon;
    const displayMessage = message || config.defaultMessage;

    return (
        <AnimatePresence mode="wait">
            <motion.div
                key={status}
                initial={{ opacity: 0, y: 20, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -20, scale: 0.95 }}
                transition={{
                    duration: 0.5,
                    ease: [0.16, 1, 0.3, 1],
                }}
                className={cn(
                    'relative overflow-hidden flex items-center gap-4 p-5 rounded-2xl border backdrop-blur-xl shadow-2xl',
                    config.bgColor,
                    config.borderColor,
                    'shadow-lg shadow-black/5'
                )}
            >
                {/* Premium AI Orb */}
                <div className="relative flex-shrink-0 w-12 h-12 flex items-center justify-center">
                    {/* Outer Glow Layer 1 */}
                    <motion.div
                        className={cn(
                            'absolute inset-0 rounded-full blur-xl opacity-40 bg-gradient-to-br',
                            config.color
                        )}
                        animate={{
                            scale: [1, 1.4, 1],
                            opacity: [0.2, 0.5, 0.2],
                        }}
                        transition={{
                            duration: 3,
                            repeat: Infinity,
                            ease: "easeInOut",
                        }}
                    />

                    {/* Outer Glow Layer 2 */}
                    <motion.div
                        className={cn(
                            'absolute inset-2 rounded-full blur-md opacity-60 bg-gradient-to-br',
                            config.color
                        )}
                        animate={{
                            scale: [1, 1.2, 1],
                        }}
                        transition={{
                            duration: 2,
                            repeat: Infinity,
                            ease: "easeInOut",
                        }}
                    />

                    {/* The Core Orb */}
                    <div className={cn(
                        'relative w-10 h-10 rounded-full flex items-center justify-center bg-gradient-to-br shadow-inner border border-white/20',
                        config.color
                    )}>
                        <Icon className="w-5 h-5 text-white drop-shadow-md" />

                        {/* Inner Shine */}
                        <div className="absolute inset-0 rounded-full bg-gradient-to-tr from-white/20 to-transparent pointer-events-none" />
                    </div>

                    {/* Spinning Orbital Ring */}
                    <motion.div
                        className={cn(
                            'absolute inset-0 rounded-full border-2 border-transparent border-t-white/30 border-l-white/10',
                        )}
                        animate={{ rotate: 360 }}
                        transition={{
                            duration: 2,
                            repeat: Infinity,
                            ease: "linear",
                        }}
                    />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                        <h4 className="text-sm font-bold tracking-tight text-foreground uppercase">
                            {config.label}
                        </h4>
                        <div className="h-1 w-1 rounded-full bg-muted-foreground/30" />
                        <div className="flex gap-1">
                            {[0, 1, 2].map((i) => (
                                <motion.div
                                    key={i}
                                    className={cn('w-1 h-1 rounded-full bg-current opacity-50')}
                                    animate={{
                                        scale: [1, 1.5, 1],
                                        opacity: [0.3, 1, 0.3],
                                    }}
                                    transition={{
                                        duration: 1,
                                        repeat: Infinity,
                                        delay: i * 0.2,
                                    }}
                                />
                            ))}
                        </div>
                    </div>
                    <p className="text-xs text-muted-foreground font-medium leading-relaxed truncate">
                        {displayMessage}
                    </p>
                </div>

                {/* Subtle Background Animation */}
                <div className="absolute inset-0 pointer-events-none opacity-5">
                    <motion.div
                        className={cn('absolute inset-0 bg-gradient-to-r', config.color)}
                        animate={{
                            x: ['-100%', '100%'],
                        }}
                        transition={{
                            duration: 3,
                            repeat: Infinity,
                            ease: "linear",
                        }}
                    />
                </div>
            </motion.div>
        </AnimatePresence>
    );
});
