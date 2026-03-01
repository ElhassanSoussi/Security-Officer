"use client";

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
import { Building2, CheckCircle2, UploadCloud } from "lucide-react";
import PageHeader from "@/components/ui/PageHeader";

type Step = 1 | 2;

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
            toast({ title: "Organization created", variant: "success" });
            setStep(2);
        } catch (err: any) {
            toast({ title: "Create organization failed", description: err?.message || "Unknown error", variant: "destructive" });
        } finally {
            setSubmitting(false);
        }
    };

    const handleUploadDocs = async () => {
        if (!orgId || !token) return;
        if (files.length === 0) {
            router.push("/dashboard");
            return;
        }
        setUploading(true);
        try {
            for (const file of files) {
                await ApiClient.uploadDocument(file, orgId, undefined, "LOCKER", token);
            }
            toast({ title: "Baseline documents uploaded", variant: "success" });
            router.push("/dashboard");
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

    if (loading) {
        return <div className="min-h-screen flex items-center justify-center text-slate-500">Preparing onboarding…</div>;
    }

    return (
        <div className="min-h-screen bg-slate-50 p-6">
            <div className="max-w-3xl mx-auto space-y-6">
                <PageHeader
                    title="Welcome to NYC Compliance Architect"
                    subtitle="Complete these two setup steps before your first questionnaire run."
                />

                <div className="grid md:grid-cols-2 gap-3">
                    <Card className={step === 1 ? "border-blue-200" : ""}>
                        <CardHeader>
                            <CardTitle className="text-base flex items-center gap-2">
                                <Building2 className="h-4 w-4" /> Step 1: Create Organization
                            </CardTitle>
                            <CardDescription>Set your workspace identity and trade profile.</CardDescription>
                        </CardHeader>
                    </Card>
                    <Card className={step === 2 ? "border-blue-200" : ""}>
                        <CardHeader>
                            <CardTitle className="text-base flex items-center gap-2">
                                <UploadCloud className="h-4 w-4" /> Step 2: Upload Baseline Docs
                            </CardTitle>
                            <CardDescription>Add your primary manuals/certificates to the vault.</CardDescription>
                        </CardHeader>
                    </Card>
                </div>

                {step === 1 && (
                    <Card>
                        <CardHeader>
                            <CardTitle>Organization Details</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="org-name">Organization Name</Label>
                                <Input
                                    id="org-name"
                                    placeholder="e.g. ACME Construction Services"
                                    value={orgName}
                                    onChange={(e) => setOrgName(e.target.value)}
                                />
                            </div>
                            <div className="grid md:grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label htmlFor="trade-type">Primary Trade Type</Label>
                                    <select
                                        id="trade-type"
                                        title="Primary Trade Type"
                                        value={tradeType}
                                        onChange={(e) => setTradeType(e.target.value)}
                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    >
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
                                    <select
                                        id="company-size"
                                        title="Company Size"
                                        value={companySize}
                                        onChange={(e) => setCompanySize(e.target.value)}
                                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                    >
                                        <option value="1-25">1-25 employees</option>
                                        <option value="26-100">26-100 employees</option>
                                        <option value="101-250">101-250 employees</option>
                                        <option value="250+">250+ employees</option>
                                    </select>
                                </div>
                            </div>
                            <div className="flex justify-end">
                                <Button onClick={handleCreateOrg} disabled={!canCreateOrg}>
                                    {submitting ? "Creating..." : "Create Organization"}
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                )}

                {step === 2 && (
                    <Card>
                        <CardHeader>
                            <CardTitle>Upload Baseline Documents</CardTitle>
                            <CardDescription>Optional but recommended before your first run.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="baseline-files">Files</Label>
                                <Input
                                    id="baseline-files"
                                    type="file"
                                    multiple
                                    accept=".pdf,.docx,.xlsx,.xlsm"
                                    onChange={(e) => setFiles(Array.from(e.target.files || []))}
                                />
                                <p className="text-xs text-slate-500">
                                    Files upload to the organization vault and are tagged for onboarding.
                                </p>
                            </div>
                            {files.length > 0 && (
                                <div className="rounded-md border border-slate-200 bg-white p-3 text-sm text-slate-600">
                                    {files.length} file(s) selected.
                                </div>
                            )}
                            <div className="flex justify-between">
                                <Button variant="outline" onClick={() => router.push("/dashboard")} disabled={uploading}>
                                    Skip for now
                                </Button>
                                <Button onClick={handleUploadDocs} disabled={uploading}>
                                    {uploading ? "Uploading..." : (
                                        <span className="inline-flex items-center gap-2">
                                            <CheckCircle2 className="h-4 w-4" />
                                            Finish Setup
                                        </span>
                                    )}
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                )}
            </div>
        </div>
    );
}

