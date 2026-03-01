"use client"

import * as React from "react"

const ToastContext = React.createContext<{
    toasts: Toast[]
    addToast: (toast: Omit<Toast, "id">) => void
    removeToast: (id: string) => void
} | null>(null)

export interface Toast {
    id: string
    title?: string
    description?: string
    variant?: "default" | "destructive" | "success"
    requestId?: string
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
    const [toasts, setToasts] = React.useState<Toast[]>([])

    const addToast = React.useCallback((toast: Omit<Toast, "id">) => {
        const id = Math.random().toString(36).substring(2, 9)
        setToasts((prev) => [...prev, { ...toast, id }])

        // Auto dismiss
        setTimeout(() => {
            setToasts((prev) => prev.filter((t) => t.id !== id))
        }, 5000)
    }, [])

    const removeToast = React.useCallback((id: string) => {
        setToasts((prev) => prev.filter((t) => t.id !== id))
    }, [])

    return (
        <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
            {children}
            <div className="fixed bottom-0 right-0 z-50 p-4 space-y-3 max-w-md w-full pointer-events-none">
                {toasts.map((toast) => (
                    <div
                        key={toast.id}
                        className={`
                            pointer-events-auto flex w-full items-start justify-between gap-3 overflow-hidden
                            rounded-lg border p-4 shadow-lg transition-all animate-in slide-in-from-bottom-5
                            ${toast.variant === 'destructive' ? 'bg-red-50 text-red-900 border-red-200' : ''}
                            ${toast.variant === 'success' ? 'bg-green-50 text-green-900 border-green-200' : ''}
                            ${!toast.variant || toast.variant === 'default' ? 'bg-white text-slate-900 border-slate-200' : ''}
                        `}
                    >
                        <div className="grid gap-1 flex-1">
                            {toast.title && <div className="text-sm font-semibold">{toast.title}</div>}
                            {toast.description && <div className="text-sm opacity-90">{toast.description}</div>}
                            {toast.requestId && (
                                <div className="text-xs font-mono opacity-60 mt-1">Request ID: {toast.requestId}</div>
                            )}
                        </div>
                        <button
                            onClick={() => removeToast(toast.id)}
                            className="shrink-0 rounded-md p-1 opacity-50 hover:opacity-100 transition-opacity"
                            aria-label="Dismiss"
                        >
                            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                                <path d="M1 1L13 13M1 13L13 1" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                            </svg>
                        </button>
                    </div>
                ))}
            </div>
        </ToastContext.Provider>
    )
}

export function useToast() {
    const context = React.useContext(ToastContext)
    if (!context) {
        throw new Error("useToast must be used within a ToastProvider")
    }
    return {
        toast: context.addToast,
        dismiss: context.removeToast
    }
}
