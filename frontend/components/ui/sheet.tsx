"use client"

import * as React from "react"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

interface SheetProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    children: React.ReactNode;
}

export function Sheet({ open, onOpenChange, children }: SheetProps) {
    // Close on Escape
    React.useEffect(() => {
        if (!open) return;
        const handler = (e: KeyboardEvent) => {
            if (e.key === "Escape") onOpenChange(false);
        };
        window.addEventListener("keydown", handler);
        return () => window.removeEventListener("keydown", handler);
    }, [open, onOpenChange]);

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-50 flex justify-end">
            <div className="fixed inset-0 bg-black/50" onClick={() => onOpenChange(false)} />
            {children}
        </div>
    );
}

interface SheetContentProps extends React.HTMLAttributes<HTMLDivElement> {
    onClose?: () => void;
}

export const SheetContent = React.forwardRef<HTMLDivElement, SheetContentProps>(
    ({ className, children, onClose, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={cn(
                    "relative z-50 ml-auto h-full w-full max-w-xl bg-white shadow-xl border-l animate-in slide-in-from-right overflow-y-auto",
                    className
                )}
                {...props}
            >
                {onClose && (
                    <button
                        onClick={onClose}
                        className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none"
                        aria-label="Close"
                    >
                        <X className="h-5 w-5" />
                    </button>
                )}
                {children}
            </div>
        );
    }
);
SheetContent.displayName = "SheetContent";

export function SheetHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
    return <div className={cn("px-6 py-4 border-b space-y-1", className)} {...props} />;
}

export function SheetTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
    return <h2 className={cn("text-lg font-semibold text-slate-900", className)} {...props} />;
}

export function SheetDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
    return <p className={cn("text-sm text-slate-500", className)} {...props} />;
}

export function SheetBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
    return <div className={cn("px-6 py-4 space-y-4", className)} {...props} />;
}

export function SheetFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
    return <div className={cn("px-6 py-4 border-t flex items-center justify-end gap-2", className)} {...props} />;
}
