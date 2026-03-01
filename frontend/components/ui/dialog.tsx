"use client"

import * as React from "react"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

const Dialog = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement> & { open?: boolean; onOpenChange?: (open: boolean) => void }
>(({ children, open, onOpenChange, ..._props }, _ref) => {
    // For simple implementation, we assume controlled state is mostly used, or we just render children that are Triggers/Content.
    // However, shadcn pattern separates Root (Dialog) from Trigger and Content.
    // We need a Context to share state.

    const [isOpen, setIsOpen] = React.useState(open || false);

    React.useEffect(() => {
        if (open !== undefined) setIsOpen(open);
    }, [open]);

    const setOpen = (val: boolean) => {
        setIsOpen(val);
        onOpenChange?.(val);
    };

    return (
        <DialogContext.Provider value={{ open: isOpen, setOpen }}>
            {children}
        </DialogContext.Provider>
    );
})
Dialog.displayName = "Dialog"

const DialogContext = React.createContext<{
    open: boolean;
    setOpen: (open: boolean) => void;
} | null>(null);

const DialogTrigger = React.forwardRef<
    HTMLButtonElement,
    React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }
>(({ className, onClick, children, asChild, ...props }, ref) => {
    const context = React.useContext(DialogContext);
    const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
        context?.setOpen(true);
        onClick?.(e);
    };

    if (asChild && React.isValidElement(children)) {
        return React.cloneElement(children as React.ReactElement, {
            onClick: handleClick,
            className: cn(className, (children.props as any).className),
            ...props,
            ref,
        });
    }

    return (
        <button
            ref={ref}
            onClick={handleClick}
            className={cn(className)}
            {...props}
        >
            {children}
        </button>
    )
})
DialogTrigger.displayName = "DialogTrigger"

const DialogContent = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => {
    const context = React.useContext(DialogContext);
    if (!context?.open) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div className="fixed inset-0 bg-black/50" onClick={() => context.setOpen(false)} />
            <div
                ref={ref}
                className={cn(
                    "z-50 grid w-full max-w-lg gap-4 border bg-background p-6 shadow-lg sm:rounded-lg relative animate-in zoom-in-95 fade-in-0 duration-200",
                    className
                )}
                {...props}
            >
                {children}
                <button
                    onClick={() => context.setOpen(false)}
                    className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground"
                >
                    <X className="h-4 w-4" />
                    <span className="sr-only">Close</span>
                </button>
            </div>
        </div>
    )
})
DialogContent.displayName = "DialogContent"

const DialogHeader = ({
    className,
    ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
    <div
        className={cn(
            "flex flex-col space-y-1.5 text-center sm:text-left",
            className
        )}
        {...props}
    />
)
DialogHeader.displayName = "DialogHeader"

const DialogFooter = ({
    className,
    ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
    <div
        className={cn(
            "flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2",
            className
        )}
        {...props}
    />
)
DialogFooter.displayName = "DialogFooter"

const DialogTitle = React.forwardRef<
    HTMLHeadingElement,
    React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
    <h3
        ref={ref}
        className={cn(
            "text-lg font-semibold leading-none tracking-tight",
            className
        )}
        {...props}
    />
))
DialogTitle.displayName = "DialogTitle"

const DialogDescription = React.forwardRef<
    HTMLParagraphElement,
    React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
    <p
        ref={ref}
        className={cn("text-sm text-muted-foreground", className)}
        {...props}
    />
))
DialogDescription.displayName = "DialogDescription"

export {
    Dialog,
    DialogTrigger,
    DialogContent,
    DialogHeader,
    DialogFooter,
    DialogTitle,
    DialogDescription,
}
