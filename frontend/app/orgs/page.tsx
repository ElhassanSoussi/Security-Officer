"use client";

import { useEffect, useState } from "react";
import { ApiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useRouter } from "next/navigation";
import { useToast } from "@/components/ui/toaster";
import { Building2, Plus } from "lucide-react";
import { createClient } from "@/utils/supabase/client";
import { setStoredOrgId } from "@/lib/orgContext";

export default function OrgSelectionPage() {
    const [orgs, setOrgs] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [newOrgName, setNewOrgName] = useState("");
    const [creating, setCreating] = useState(false);
    const router = useRouter();
    const { toast } = useToast();
    const supabase = createClient();

    // Fetch Orgs on Load
    useEffect(() => {
        async function loadOrgs() {
            try {
                // Auth check
                const { data: { session } } = await supabase.auth.getSession();
                if (!session) {
                    router.push("/login");
                    return;
                }

                const data = await ApiClient.getMyOrgs(session.access_token);

                // Auto-onboard if no orgs found
                if (!data || data.length === 0) {
                    setLoading(true);
                    try {
                        const newOrg = await ApiClient.post<any>("/orgs/onboard", {}, session.access_token);
                        setStoredOrgId(newOrg.id);
                        router.push(`/projects?orgId=${newOrg.id}`);
                        return;
                    } catch {
                        toast({ title: "Onboarding Failed", description: "Could not create default organization.", variant: "destructive" });
                    }
                }

                setOrgs(data);
            } catch (e) {
                console.error(e);
            } finally {
                setLoading(false);
            }
        }
        loadOrgs();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [router, supabase.auth]);

    const handleCreate = async (e: React.FormEvent) => {
        e.preventDefault();
        setCreating(true);
        try {
            const { data: { session } } = await supabase.auth.getSession();
            if (!session) return;

            const newOrg = await ApiClient.createOrg(newOrgName, session.access_token);
            toast({ title: "Organization Created", variant: "success" });
            setStoredOrgId(newOrg.id);
            router.push(`/projects?orgId=${newOrg.id}`);
        } catch (e: any) {
            toast({ title: "Failed to create", description: e.message, variant: "destructive" });
        } finally {
            setCreating(false);
        }
    };

    const handleSelect = (orgId: string) => {
        setStoredOrgId(orgId);
        router.push(`/projects?orgId=${orgId}`);
    };

    if (loading) return <div className="flex h-screen items-center justify-center">Loading...</div>;

    return (
        <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
            <div className="w-full max-w-2xl space-y-8">
                <div className="text-center">
                    <h1 className="text-3xl font-bold tracking-tight">Select Organization</h1>
                    <p className="text-muted-foreground mt-2">Choose a workspace to continue.</p>
                </div>

                {orgs.length > 0 && (
                    <div className="flex justify-end">
                        <Button variant="outline" size="sm" onClick={() => setStoredOrgId("")}>
                            Switch Organization
                        </Button>
                    </div>
                )}

                <div className="grid gap-4 md:grid-cols-2">
                    {orgs.map(org => (
                        <Card key={org.id} className="cursor-pointer hover:border-primary transition-colors" onClick={() => handleSelect(org.id)}>
                            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                <CardTitle className="text-lg font-medium">{org.name}</CardTitle>
                                <Building2 className="h-4 w-4 text-muted-foreground" />
                            </CardHeader>
                            <CardContent>
                                <div className="text-xs text-muted-foreground capitalize">{org.role} Role</div>
                            </CardContent>
                        </Card>
                    ))}

                    {/* Create New Card */}
                    <Card className="border-dashed bg-slate-50/50">
                        <CardHeader>
                            <CardTitle>Create New</CardTitle>
                            <CardDescription>Start a new workspace</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <form onSubmit={handleCreate} className="space-y-4">
                                <Input
                                    placeholder="Org Name"
                                    value={newOrgName}
                                    onChange={e => setNewOrgName(e.target.value)}
                                    required
                                />
                                <Button type="submit" disabled={creating} className="w-full">
                                    <Plus className="mr-2 h-4 w-4" /> Create
                                </Button>
                            </form>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    );
}
