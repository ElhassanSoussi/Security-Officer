"use client";

import * as React from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ErrorBoundaryProps {
    children: React.ReactNode;
    fallback?: React.ReactNode;
}

interface ErrorBoundaryState {
    hasError: boolean;
    error: Error | null;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
    constructor(props: ErrorBoundaryProps) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): ErrorBoundaryState {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        console.error("[ErrorBoundary] Caught:", error, errorInfo);
    }

    handleReset = () => {
        this.setState({ hasError: false, error: null });
    };

    render() {
        if (this.state.hasError) {
            if (this.props.fallback) return this.props.fallback;

            return (
                <div className="flex flex-col items-center justify-center min-h-[400px] p-8 text-center">
                    <div className="rounded-full bg-red-100 p-4 mb-4">
                        <AlertTriangle className="h-8 w-8 text-red-600" />
                    </div>
                    <h2 className="text-lg font-semibold text-foreground mb-1">Something went wrong</h2>
                    <p className="text-sm text-muted-foreground max-w-md mb-1">
                        An unexpected error occurred. Please try again or contact support if the problem persists.
                    </p>
                    {this.state.error?.message && (
                        <p className="text-xs text-muted-foreground font-mono bg-muted rounded px-3 py-1.5 max-w-md truncate mb-4">
                            {this.state.error.message}
                        </p>
                    )}
                    <div className="flex gap-2">
                        <Button variant="outline" onClick={this.handleReset} className="gap-2">
                            <RotateCcw className="h-4 w-4" /> Try Again
                        </Button>
                        <Button variant="outline" onClick={() => window.location.href = "/dashboard"}>
                            Go to Dashboard
                        </Button>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}
