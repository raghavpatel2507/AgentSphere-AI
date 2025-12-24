import { cn } from "@/lib/utils";

interface SkeletonProps {
    className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
    return (
        <div
            className={cn(
                "animate-pulse rounded-md bg-muted/50",
                className
            )}
        />
    );
}

export function MessageSkeleton() {
    return (
        <div className="flex gap-3 mb-6 animate-fade-up">
            <Skeleton className="w-9 h-9 rounded-xl shrink-0" />
            <div className="space-y-2 w-full max-w-[80%]">
                <Skeleton className="h-4 w-[40%] rounded-lg" />
                <Skeleton className="h-20 w-full rounded-2xl" />
            </div>
        </div>
    );
}

export function ChatSkeleton() {
    return (
        <div className="space-y-6 p-4">
            <MessageSkeleton />
            <MessageSkeleton />
            <div className="flex flex-row-reverse gap-3 mb-6">
                <Skeleton className="w-9 h-9 rounded-xl shrink-0" />
                <div className="space-y-2 w-full max-w-[80%] flex flex-col items-end">
                    <Skeleton className="h-4 w-[30%] rounded-lg" />
                    <Skeleton className="h-12 w-full rounded-2xl" />
                </div>
            </div>
        </div>
    );
}
