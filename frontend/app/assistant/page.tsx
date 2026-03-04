"use client";

/*
 * Assistant — /assistant
 *
 * In-app AI assistant — platform guidance only.
 * No document content access. No legal advice or attestation.
 */

import { useState, useRef, useEffect, useCallback, FormEvent } from "react";
import Link from "next/link";
import {
    MessageSquare,
    Send,
    Loader2,
    AlertTriangle,
    ArrowRight,
    RotateCcw,
    Copy,
    Check,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ApiClient } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";
import { getStoredOrgId } from "@/lib/orgContext";

// ── Types ────────────────────────────────────────────────────────────────────

interface Action {
    label: string;
    href: string;
}

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    actions?: Action[];
    error?: boolean;
}

// ── Help topic shortcuts ───────────────────────────────────────────────────────

const HELP_TOPICS: { label: string; prompt: string }[] = [
    { label: "Getting Started",  prompt: "How do I get started with the platform?" },
    { label: "Documents",        prompt: "How do I upload and manage documents?" },
    { label: "Runs",             prompt: "How do I start a questionnaire run?" },
    { label: "Review & Audit",   prompt: "Where do I find my audit log?" },
    { label: "Plans & Billing",  prompt: "What's my current plan and usage?" },
];

// ── Suggested prompts ────────────────────────────────────────────────────────

const SUGGESTED_PROMPTS = [
    "What's my current plan and usage?",
    "How do I start a new compliance run?",
    "How do I add documents to a project?",
    "Where do I find my audit log?",
    "Why am I blocked from uploading?",
];

// ── Helpers ──────────────────────────────────────────────────────────────────

function uid() {
    return Math.random().toString(36).slice(2, 10);
}

function CopyButton({ text }: { text: string }) {
    const [copied, setCopied] = useState(false);
    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(text);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch { /* clipboard unavailable */ }
    };
    return (
        <button
            onClick={handleCopy}
            className="ml-1 inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            title="Copy answer"
            aria-label="Copy answer"
        >
            {copied ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
            {copied ? "Copied" : "Copy"}
        </button>
    );
}

function renderMarkdown(text: string): React.ReactNode[] {
    return text.split(/(\*\*[^*]+\*\*)/g).map((p, i) =>
        p.startsWith("**") && p.endsWith("**")
            ? <strong key={i}>{p.slice(2, -2)}</strong>
            : <span key={i}>{p}</span>,
    );
}

// ── Page ─────────────────────────────────────────────────────────────────────

function AssistantBubble({ msg }: { msg: Message }) {
    if (msg.role === "user") {
        return (
            <div className="flex justify-end">
                <div className="max-w-[75%] rounded-2xl rounded-tr-sm bg-primary px-4 py-2.5 text-sm text-primary-foreground shadow-sm">
                    {msg.content}
                </div>
            </div>
        );
    }
    return (
        <div className="flex justify-start">
            <div className="max-w-[82%] space-y-2">
                <div className={`rounded-2xl rounded-tl-sm px-4 py-3 text-sm shadow-sm leading-relaxed whitespace-pre-wrap ${
                    msg.error
                        ? "border border-red-200 bg-red-50 text-red-800"
                        : "border border-border bg-card text-foreground"
                }`}>
                    {renderMarkdown(msg.content)}
                </div>
                <div className="flex flex-wrap items-center gap-2 pl-1">
                    {msg.actions?.map((a) => (
                        <Link key={a.href} href={a.href}>
                            <Badge variant="outline" className="gap-1 cursor-pointer text-xs hover:bg-accent transition-colors">
                                <ArrowRight className="h-3 w-3" />
                                {a.label}
                            </Badge>
                        </Link>
                    ))}
                    {!msg.error && <CopyButton text={msg.content} />}
                </div>
            </div>
        </div>
    );
}

export default function AssistantPage() {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [conversationId, setConversationId] = useState<string | undefined>();
    const [orgId, setOrgId] = useState<string | null>(null);
    const [token, setToken] = useState<string | undefined>();
    const [initError, setInitError] = useState<string | null>(null);
    const bottomRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Resolve org + token on mount
    useEffect(() => {
        (async () => {
            try {
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                const tok = session?.access_token;
                setToken(tok);

                let oid = getStoredOrgId();
                if (!oid && tok) {
                    const orgs = await ApiClient.getMyOrgs(tok);
                    oid = orgs?.[0]?.id ?? null;
                }
                setOrgId(oid);
            } catch {
                setInitError("Could not load your account. Please refresh.");
            }
        })();
    }, []);

    // Scroll to bottom on new messages
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages, loading]);

    const sendMessage = useCallback(
        async (text: string) => {
            const trimmed = text.trim();
            if (!trimmed || loading) return;
            if (!orgId) {
                setInitError("No organization found. Please refresh or sign in again.");
                return;
            }

            const userMsg: Message = { id: uid(), role: "user", content: trimmed };
            setMessages((prev) => [...prev, userMsg]);
            setInput("");
            setLoading(true);

            try {
                const res = await ApiClient.sendAssistantMessage(orgId, trimmed, conversationId, token);
                setConversationId(res.conversation_id);
                const assistantMsg: Message = {
                    id: uid(),
                    role: "assistant",
                    content: res.reply,
                    actions: res.actions,
                };
                setMessages((prev) => [...prev, assistantMsg]);
            } catch (e: any) {
                const errMsg: Message = {
                    id: uid(),
                    role: "assistant",
                    content: e?.message ?? "Something went wrong. Please try again.",
                    error: true,
                };
                setMessages((prev) => [...prev, errMsg]);
            } finally {
                setLoading(false);
                // Re-focus textarea after reply
                setTimeout(() => textareaRef.current?.focus(), 50);
            }
        },
        [orgId, token, conversationId, loading],
    );

    const handleSubmit = (e: FormEvent) => {
        e.preventDefault();
        sendMessage(input);
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage(input);
        }
    };

    const handleReset = () => {
        setMessages([]);
        setConversationId(undefined);
        setInput("");
        textareaRef.current?.focus();
    };

    const isEmpty = messages.length === 0;

    return (
        <div className="flex flex-col h-[calc(100vh-4rem)] max-w-3xl mx-auto">
            {/* Header */}
            <div className="flex items-center justify-between py-5 border-b border-border shrink-0">
                <div className="flex items-center gap-2.5">
                    <MessageSquare className="h-5 w-5 text-primary" />
                    <div>
                        <h1 className="text-base font-semibold text-foreground leading-none">Assistant</h1>
                        <p className="text-xs text-muted-foreground mt-0.5">
                            Platform guidance only — no legal advice
                        </p>
                    </div>
                </div>
                {!isEmpty && (
                    <Button variant="ghost" size="sm" className="gap-1.5 text-xs" onClick={handleReset}>
                        <RotateCcw className="h-3.5 w-3.5" />
                        New conversation
                    </Button>
                )}
            </div>

            {/* Help topics bar */}
            <div className="flex flex-wrap gap-1.5 py-3 border-b border-border shrink-0">
                {HELP_TOPICS.map((t) => (
                    <button
                        key={t.label}
                        onClick={() => sendMessage(t.prompt)}
                        disabled={loading || !!initError}
                        className="rounded-full border border-border bg-card px-3 py-1 text-xs text-foreground hover:bg-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {t.label}
                    </button>
                ))}
            </div>

            {/* Init error */}
            {initError && (
                <div className="mt-4 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 shrink-0">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    {initError}
                </div>
            )}

            {/* Message list */}
            <div className="flex-1 overflow-y-auto py-6 space-y-4 min-h-0">
                {isEmpty && !initError && (
                    <div className="flex flex-col items-center justify-center h-full gap-6 text-center pb-8">
                        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10">
                            <MessageSquare className="h-7 w-7 text-primary" />
                        </div>
                        <div className="space-y-1.5">
                            <h2 className="text-base font-semibold text-foreground">
                                How can I help you?
                            </h2>
                            <p className="text-sm text-muted-foreground max-w-xs">
                                Ask me anything about using the platform — projects, runs, documents, billing, or settings.
                            </p>
                        </div>
                        <div className="flex flex-col gap-2 w-full max-w-sm">
                            {SUGGESTED_PROMPTS.map((p) => (
                                <button
                                    key={p}
                                    onClick={() => sendMessage(p)}
                                    disabled={!orgId || loading}
                                    className="rounded-xl border border-border bg-card px-4 py-2.5 text-sm text-left text-foreground hover:bg-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {p}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {messages.map((msg) => (
                    <AssistantBubble key={msg.id} msg={msg} />
                ))}

                {loading && (
                    <div className="flex justify-start">
                        <div className="rounded-2xl rounded-tl-sm border border-border bg-card px-4 py-3 shadow-sm">
                            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                        </div>
                    </div>
                )}

                <div ref={bottomRef} />
            </div>

            {/* Input */}
            <form
                onSubmit={handleSubmit}
                className="shrink-0 border-t border-border pt-4 pb-5 flex gap-2 items-end"
            >
                <Textarea
                    ref={textareaRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask me anything about the platform…"
                    rows={1}
                    className="resize-none min-h-[42px] max-h-[160px] flex-1 text-sm"
                    disabled={loading || !!initError}
                    autoFocus
                />
                <Button
                    type="submit"
                    size="sm"
                    className="shrink-0 h-[42px] px-3"
                    disabled={!input.trim() || loading || !!initError}
                >
                    {loading ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                        <Send className="h-4 w-4" />
                    )}
                </Button>
            </form>
        </div>
    );
}
