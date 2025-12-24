import { motion } from "framer-motion";

export function TypingIndicator() {
    return (
        <div className="flex items-center gap-3 px-5 py-3 rounded-2xl bg-card/40 backdrop-blur-xl border border-white/10 w-fit shadow-2xl shadow-primary/10">
            <div className="relative w-5 h-5">
                {/* Outer Glow */}
                <motion.div
                    className="absolute inset-0 rounded-full bg-primary/30 blur-md"
                    animate={{
                        scale: [1, 1.5, 1],
                        opacity: [0.3, 0.6, 0.3],
                    }}
                    transition={{
                        duration: 2,
                        repeat: Infinity,
                        ease: "easeInOut",
                    }}
                />
                {/* Inner Orb */}
                <motion.div
                    className="absolute inset-0.5 rounded-full bg-gradient-to-br from-primary to-accent shadow-lg"
                    animate={{
                        scale: [1, 0.8, 1],
                    }}
                    transition={{
                        duration: 2,
                        repeat: Infinity,
                        ease: "easeInOut",
                    }}
                >
                    <div className="absolute inset-0 rounded-full bg-white/20 blur-[1px]" />
                </motion.div>
                {/* Spinning Ring */}
                <motion.div
                    className="absolute inset-[-2px] rounded-full border border-primary/20 border-t-primary"
                    animate={{ rotate: 360 }}
                    transition={{
                        duration: 1.5,
                        repeat: Infinity,
                        ease: "linear",
                    }}
                />
            </div>
            <span className="text-xs font-bold tracking-widest uppercase text-primary/80 animate-pulse">
                Thinking
            </span>
        </div>
    );
}
