"use client";

/**
 * Phase 22 — Contact / Lead Capture Page (/contact)
 *
 * Public page (no auth required). Submits to POST /api/v1/contact.
 * Fields: Company Name, Name, Email, Phone, Company Size, Message.
 */

import { useState } from "react";
import Link from "next/link";
import {
    ShieldCheck,
    Send,
    CheckCircle2,
    AlertTriangle,
    Building2,
    User,
    Mail,
    Phone,
    Users,
    MessageSquare,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiClient } from "@/lib/api";

const COMPANY_SIZES = [
    "1-10 employees",
    "11-50 employees",
    "51-200 employees",
    "201-1,000 employees",
    "1,001-5,000 employees",
    "5,000+ employees",
];

export default function ContactPage() {
    const [form, setForm] = useState({
        company_name: "",
        name: "",
        email: "",
        phone: "",
        company_size: "",
        message: "",
    });
    const [submitting, setSubmitting] = useState(false);
    const [success, setSuccess] = useState(false);
    const [error, setError] = useState<string | null>(null);

    function onChange(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) {
        setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    }

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        setError(null);

        if (!form.company_name.trim() || !form.name.trim() || !form.email.trim()) {
            setError("Please fill in all required fields.");
            return;
        }

        setSubmitting(true);
        try {
            await ApiClient.submitContactForm({
                company_name: form.company_name.trim(),
                name: form.name.trim(),
                email: form.email.trim(),
                phone: form.phone.trim() || undefined,
                company_size: form.company_size || undefined,
                message: form.message.trim() || undefined,
            });
            setSuccess(true);
        } catch (err: any) {
            setError(err?.message ?? "Something went wrong. Please try again.");
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
            {/* Header */}
            <header className="border-b bg-white/80 backdrop-blur-sm">
                <div className="max-w-5xl mx-auto flex items-center justify-between px-6 py-4">
                    <Link href="/" className="flex items-center gap-2.5">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/10">
                            <ShieldCheck className="h-4.5 w-4.5 text-blue-600" />
                        </div>
                        <span className="font-semibold text-slate-900">NYC Compliance Architect</span>
                    </Link>
                    <Link href="/login">
                        <Button variant="ghost" size="sm">Sign In</Button>
                    </Link>
                </div>
            </header>

            <div className="max-w-3xl mx-auto px-6 py-16">
                {success ? (
                    /* ── Success state ── */
                    <Card className="text-center py-12">
                        <CardContent className="space-y-4">
                            <div className="mx-auto w-14 h-14 rounded-full bg-emerald-100 flex items-center justify-center">
                                <CheckCircle2 className="h-7 w-7 text-emerald-600" />
                            </div>
                            <h1 className="text-2xl font-semibold text-slate-900">Thank You!</h1>
                            <p className="text-slate-600 max-w-md mx-auto">
                                We&apos;ve received your inquiry. Our team will reach out within one business day to discuss your compliance needs.
                            </p>
                            <div className="flex items-center justify-center gap-3 pt-4">
                                <Link href="/">
                                    <Button variant="outline" size="sm">Back to Home</Button>
                                </Link>
                                <Link href="/login">
                                    <Button size="sm">Sign In</Button>
                                </Link>
                            </div>
                        </CardContent>
                    </Card>
                ) : (
                    /* ── Form state ── */
                    <>
                        <div className="text-center mb-10">
                            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">
                                Contact Sales
                            </h1>
                            <p className="mt-3 text-lg text-slate-600 max-w-xl mx-auto">
                                Ready to automate your compliance workflow? Tell us about your organization and we&apos;ll tailor a solution for you.
                            </p>
                        </div>

                        <Card>
                            <CardHeader>
                                <CardTitle className="text-base">Enterprise Inquiry</CardTitle>
                            </CardHeader>
                            <CardContent>
                                {error && (
                                    <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 mb-6">
                                        <AlertTriangle className="h-4 w-4 shrink-0" />
                                        {error}
                                    </div>
                                )}

                                <form onSubmit={handleSubmit} className="space-y-5">
                                    {/* Company Name */}
                                    <div className="space-y-1.5">
                                        <label htmlFor="company_name" className="flex items-center gap-1.5 text-sm font-medium text-slate-700">
                                            <Building2 className="h-3.5 w-3.5 text-slate-400" />
                                            Company Name <span className="text-red-500">*</span>
                                        </label>
                                        <input
                                            id="company_name"
                                            name="company_name"
                                            type="text"
                                            required
                                            value={form.company_name}
                                            onChange={onChange}
                                            className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                                            placeholder="Acme Construction LLC"
                                        />
                                    </div>

                                    {/* Name + Email row */}
                                    <div className="grid gap-4 sm:grid-cols-2">
                                        <div className="space-y-1.5">
                                            <label htmlFor="name" className="flex items-center gap-1.5 text-sm font-medium text-slate-700">
                                                <User className="h-3.5 w-3.5 text-slate-400" />
                                                Your Name <span className="text-red-500">*</span>
                                            </label>
                                            <input
                                                id="name"
                                                name="name"
                                                type="text"
                                                required
                                                value={form.name}
                                                onChange={onChange}
                                                className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                                                placeholder="Jane Smith"
                                            />
                                        </div>
                                        <div className="space-y-1.5">
                                            <label htmlFor="email" className="flex items-center gap-1.5 text-sm font-medium text-slate-700">
                                                <Mail className="h-3.5 w-3.5 text-slate-400" />
                                                Work Email <span className="text-red-500">*</span>
                                            </label>
                                            <input
                                                id="email"
                                                name="email"
                                                type="email"
                                                required
                                                value={form.email}
                                                onChange={onChange}
                                                className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                                                placeholder="jane@acme.com"
                                            />
                                        </div>
                                    </div>

                                    {/* Phone + Company Size row */}
                                    <div className="grid gap-4 sm:grid-cols-2">
                                        <div className="space-y-1.5">
                                            <label htmlFor="phone" className="flex items-center gap-1.5 text-sm font-medium text-slate-700">
                                                <Phone className="h-3.5 w-3.5 text-slate-400" />
                                                Phone <span className="text-slate-400 text-xs">(optional)</span>
                                            </label>
                                            <input
                                                id="phone"
                                                name="phone"
                                                type="tel"
                                                value={form.phone}
                                                onChange={onChange}
                                                className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                                                placeholder="+1 (555) 123-4567"
                                            />
                                        </div>
                                        <div className="space-y-1.5">
                                            <label htmlFor="company_size" className="flex items-center gap-1.5 text-sm font-medium text-slate-700">
                                                <Users className="h-3.5 w-3.5 text-slate-400" />
                                                Company Size <span className="text-slate-400 text-xs">(optional)</span>
                                            </label>
                                            <select
                                                id="company_size"
                                                name="company_size"
                                                value={form.company_size}
                                                onChange={onChange}
                                                className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                                            >
                                                <option value="">Select…</option>
                                                {COMPANY_SIZES.map((s) => (
                                                    <option key={s} value={s}>{s}</option>
                                                ))}
                                            </select>
                                        </div>
                                    </div>

                                    {/* Message */}
                                    <div className="space-y-1.5">
                                        <label htmlFor="message" className="flex items-center gap-1.5 text-sm font-medium text-slate-700">
                                            <MessageSquare className="h-3.5 w-3.5 text-slate-400" />
                                            Message <span className="text-slate-400 text-xs">(optional)</span>
                                        </label>
                                        <textarea
                                            id="message"
                                            name="message"
                                            rows={4}
                                            value={form.message}
                                            onChange={onChange}
                                            className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
                                            placeholder="Tell us about your compliance requirements, questionnaire volume, or anything else we should know…"
                                        />
                                    </div>

                                    <Button
                                        type="submit"
                                        disabled={submitting}
                                        className="w-full gap-2 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white"
                                    >
                                        {submitting ? (
                                            <>Submitting…</>
                                        ) : (
                                            <>
                                                <Send className="h-4 w-4" />
                                                Submit Inquiry
                                            </>
                                        )}
                                    </Button>
                                </form>

                                <p className="mt-4 text-xs text-center text-slate-400">
                                    By submitting, you agree to be contacted about NYC Compliance Architect.
                                    We&apos;ll never share your information with third parties.
                                </p>
                            </CardContent>
                        </Card>
                    </>
                )}
            </div>
        </div>
    );
}
