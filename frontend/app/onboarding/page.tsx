"use client";

/**
 * Onboarding Flow — /onboarding
 *
 * 4-step guided wizard:
 *   Step 1: Welcome + overview
 *   Step 2: Create Organization (name, trade, size)
 *   Step 3: Upload Baseline Documents
 *   Step 4: Compliance Checklist + finish
 */

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/utils/supabase/client";
import { ApiClient } from "@/lib/api";
import { setStoredOrgId } from "@/lib/orgContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toaster";
import {
    Building2,
    CheckCircle2,
    UploadCloud,
    Sparkles,
    ArrowRight,
    ArrowLeft,
    ShieldCheck,
    FileText,
    Zap,
    Rocket,
} from "lucide-react";
import PageHeader from "@/components/ui/PageHeader";

type Step = 1 | 2 | 3 | 4;

const STEPS: { num: Step; title: string; icon: React.ReactNode }[] = [
    { num: 1, title: "Welcome",     icon: <Sparkles className="h-4 w-4" /> },
    { num: 2, title: "Organization", icon: <Building2 className="h-4 w-4" /> },
    { num: 3, title: "Documents",   icon: <UploadCloud className="h-4 w-4" /> },
    { num: 4, title: "Ready!",      icon: <Rocket className="h-4 w-4" /> },
];

const CHECKLIST = [
    { id: "org",  label: "Create your organization",             icon: <Building2 className="h-4 w-4" /> },
    { id: "docs", label: "Upload baseline compliance docs",      icon: <FileText className="h-4 w-4" /> },
    { id: "run",  label: "Run your first compliance analysis",   icon: <Zap className="h-4 w-4" /> },
    { id: "kb",   label: "Build your knowledge base for reuse",  icon: <ShieldCheck className="h-4 w-4" /> },
];

export default function OnboardingPage() {
    const router = useRouter();
    const { toast } = useToast();
    const supabase = createClient();

    const [token, setToken] = useState<string>("");
    const [step, setStep] = useState<Step>(1);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [uploading, setUploading] = useState(false);

    const [orgId, setOrgId] = useState<string>("");
    const [orgName, setOrgName] = useState("");
    const [tradeType, setTradeType] = useState("general-contractor");
    const [companySize, setCompanySize] = useState("1-25");
    const [files, setFiles] = useState<File[]>([]);
    const [checkedItems, setCheckedItems] = useState<Set<string>>(new Set());

    useEffect(() => {
        const init = async () => {
            const { data: { session } } = await supabase.auth.getSession();
            const accessToken = session?.access_token || "";
            if (!accessToken) {
                router.replace("/login");
                return;
            }
            setToken(accessToken);

            try {
                const orgs = await ApiClient.getMyOrgs(accessToken);
                if (orgs.length > 0) {
                    setStoredOrgId(orgs[0].id);
                    router.replace("/dashboard");
                    return;
                }
            } catch {
                // Continue onboarding flow.
            }
            setLoading(false);
        };
        init();
    }, [router, supabase.auth]);

    const canCreateOrg = useMemo(() => orgName.trim().length >= 2 && !submitting, [orgName, submitting]);

    const handleCreateOrg = async () => {
        if (!canCreateOrg || !token) return;
        setSubmitting(true);
        try {
            const created = await ApiClient.createOrg(
                orgName.trim(),
                token,
                { trade_type: tradeType, company_size: companySize }
            );
            setOrgId(created.id);
            setStoredOrgId(created.id);
            setCheckedItems(prev => { const next = new Set(Array.from(prev)); next.add("org"); return next; });
            toast({ title: "Organization created", variant: "success" });
            setStep(3);
        } catch (err: any) {
            toast({ title: "Create organization failed", description: err?.message || "Unknown error", variant: "destructive" });
        } finally {
            setSubmitting(false);
        }
    };

    const handleUploadDocs = async () => {
        if (!orgId || !token) return;
        if (files.length === 0) {
            setStep(4);
            return;
        }
        setUploading(true);
        try {
            for (const file of files) {
                await ApiClient.uploadDocument(file, orgId, undefined, "LOCKER", token);
            }
            setCheckedItems(prev => { const next = new Set(Array.from(prev)); next.add("docs"); return next; });
            toast({ title: "Baseline documents uploaded", variant: "success" });
            setStep(4);
        } catch (err: any) {
            toast({
                title: "Upload failed",
                description: err?.message || "Failed to upload one or more files.",
                variant: "destructive",
            });
        } finally {
            setUploading(false);
        }
    };

    const toggleCheck = (id: string) => {
        setCheckedItems(prev => {
            const next = new Set(Array.from(prev));
            if (next.has(id)) next.delete(id); else next.add(id);
            return next;
        });
    };

    if (loading) {
        return <div className="min-h-screen flex items-center justify-center text-slate-500">Preparing onboarding…</div>;
    }

    return (
        <div className="min-h-screen bg-slate-50 p-6">
            <div className="max-w-3xl mx-auto space-y-6">
                <PageHeader
                    title="Welcome to NYC Compliance Architect"
                    subtitle="Complete your workspace setup in a few easy steps."
                />

                {/* Step Indicators */}
                <div className="flex items-center gap-2">
                    {STEPS.map((s, i) => (
                        <div key={s.num} className="flex items-center gap-2">
                            <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                                step === s.num
                                    ? "bg-blue-600 text-white"
                                    : step > s.num
                                        ? "bg-emerald-100 text-emerald-700"
                                        : "bg-slate-100 text-slate-400"
                            }`}>
                                {step > s.num ? <CheckCircle2 className="h-3 w-3" /> : s.icon}
                                {s.title}
                            </div>
                            {i < STEPS.length - 1 && <div className="w-6 h-px bg-slate-200" />}
                        </div>
                    ))}
                </div>

                {/* Step 1: Welcome */}
                {step === 1 && (
                    <Card className="border-blue-200">
                        <CardHeader className="text-center pb-2">
                            <div className="mx-auto w-14 h-14 rounded-full bg-blue-100 flex items-center justify-center mb-3">
                                <ShieldCheck className="h-7 w-7 text-blue-600" />
                            </div>
                            <CardTitle className="text-xl">Welcome aboard! 🎉</CardTitle>
                            <CardDescription className="text-base max-w-md mx-auto">
                                NYC Compliance Architect automates SCA, MTA, and PASSPort questionnaire completion
                                using AI-powered analysis of your existing compliance documents.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="grid sm:grid-cols-3 gap-3 text-center">
                                <div className="p-4 rounded-lg bg-slate-50 border">
                                    <FileText className="h-6 w-6 text-purple-600 mx-auto mb-2" />
                                    <p className="text-sm font-medium">Upload Questionnaires</p>
                                    <p className="text-xs text-muted-foreground mt-1">Drag & drop Excel files</p>
                                </div>
                                <div className="p-4 rounded-lg bg-slate-50 border">
                                    <Zap className="h-6 w-6 text-amber-600 mx-auto mb-2" />
                                    <p className="text-sm font-medium">AI Analysis</p>
                                    <p className="text-xs text-muted-foreground mt-1">Auto-fill with AI answers</p>
                                </div>
                                <div className="p-4 rounded-lg bg-slate-50 border">
                                    <CheckCircle2 className="h-6 w-6 text-emerald-600 mx-auto mb-2" />
                                    <p className="text-sm font-medium">Export & Submit</p>
                                    <p className="text-xs text-muted-foreground mt-1">Download ready-to-submit Excel</p>
                                </div>
                            </div>
                            <div className="flex justify-end pt-2">
                                <Button onClick={() => setStep(2)} className="gap-1.5">
                                    Get Started <ArrowRight className="h-4 w-4" />
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                )}

                {/* Step 2: Organization */}
                {step === 2 && (
                    <Card className="border-blue-200">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2"><Building2 className="h-5 w-5" /> Organization Details</CardTitle>
                            <CardDescription>Set your workspace identity and trade profile.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="org-name">Organization Name</Label>
                                <Input id="org-name" placeholder="e.g. ACME Construction Services" value={orgName} onChange={(e) => setOrgName(e.target.value)} />
                            </div>
                            <div className="grid md:grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="trade-type">Primary Trade Type</Label>
                                    <select id="trade-type" title="Primary Trade Type" value={tradeType} onChange={(e) => setTradeType(e.target.value)}
                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring">
                                        <option value="general-contractor">General Contractor</option>
                                        <option value="electrical">Electrical</option>
                                        <option value="mechanical">Mechanical</option>
                                        <option value="plumbing">Plumbing</option>
                                        <option value="fire-safety">Fire Safety</option>
                                        <option value="other">Other</option>
                                    </select>
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="company-size">Company Size</Label>
                                    <select id="company-size" title="Company Size" value={companySize} onChange={(e) => setCompanySize(e.target.value)}
                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring">
                                        <option value="1-25">1-25 employees</option>
                                        <option value="26-100">26-100 employees</option>
                                        <option value="101-250">101-250 employees</option>
                                        <option value="250+">250+ employees</option>
                                    </select>
                                </div>
                            </div>
                            <div className="flex justify-between">
                                <Button variant="outline" onClick={() => setStep(1)} className="gap-1.5"><ArrowLeft className="h-4 w-4" /> Back</Button>
                                <Button onClick={handleCreateOrg} disabled={!canCreateOrg}>
                                    {submitting ? "Creating..." : "Create Organization"}
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                )}

                {/* Step 3: Documents */}
                {step === 3 && (
                    <Card className="border-blue-200">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2"><UploadCloud className="h-5 w-5" /> Upload Baseline Documents</CardTitle>
                            <CardDescription>Optional but recommended — add your safety manuals, certifications, and prior submissions.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="baseline-files">Files</Label>
                                <Input id="baseline-files" type="file" multiple accept=".pdf,.docx,.xlsx,.xlsm" onChange={(e) => setFiles(Array.from(e.target.files || []))} />
                                <p className="text-xs text-slate-500">Files upload to the organization vault and are tagged for onboarding.</p>
                            </div>
                            {files.length > 0 && (
                                <div className="rounded-md border border-slate-200 bg-white p-3 text-sm text-slate-600">
                                    {files.length} file(s) selected.
                                </div>
                            )}
                            <div className="flex justify-between">
                                <Button variant="outline" onClick={() => setStep(4)} disabled={uploading}>Skip for now</Button>
                                <Button onClick={handleUploadDocs} disabled={uploading}>
                                    {uploading ? "Uploading..." : <><CheckCircle2 className="h-4 w-4 mr-1.5" /> Upload & Continue</>}
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                )}

                {/* Step 4: Compliance Checklist + Finish */}
                {step === 4 && (
                    <Card className="border-emerald-200">
                        <CardHeader className="text-center pb-2">
                            <div className="mx-auto w-14 h-14 rounded-full bg-emerald-100 flex items-center justify-center mb-3">
                                <Rocket className="h-7 w-7 text-emerald-600" />
                            </div>
                            <CardTitle className="text-xl">You&apos;re all set! 🚀</CardTitle>
                            <CardDescription className="text-base">Here&apos;s your compliance getting-started checklist.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-2">
                                {CHECKLIST.map((item) => (
                                    <button
                                        key={item.id}
                                        onClick={() => toggleCheck(item.id)}
                                        className={`w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-colors ${
                                            checkedItems.has(item.id)
                                                ? "bg-emerald-50 border-emerald-200"
                                                : "bg-white border-slate-200 hover:bg-slate-50"
                                        }`}
                                    >
                                        <div className={`h-5 w-5 rounded-full border-2 flex items-center justify-center transition-colors ${
                                            checkedItems.has(item.id) ? "bg-emerald-500 border-emerald-500" : "border-slate-300"
                                        }`}>
                                            {checkedItems.has(item.id) && <CheckCircle2 className="h-3 w-3 text-white" />}
                                        </div>
                                        <span className="text-slate-500">{item.icon}</span>
                                        <span className={`text-sm font-medium ${checkedItems.has(item.id) ? "text-emerald-700 line-through" : "text-slate-700"}`}>
                                            {item.label}
                                        </span>
                                    </button>
                                ))}
                            </div>
                            <div className="flex justify-center pt-2">
                                <Button size="lg" onClick={() => router.push("/dashboard")} className="gap-1.5">
                                    <Rocket className="h-4 w-4" /> Go to Dashboard
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                )}
            </div>
        </div>
    );
}

