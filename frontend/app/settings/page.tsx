"use client";

import { useEffect, useState } from "react";
import { ApiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toaster";
import { createClient } from "@/utils/supabase/client";
import { getStoredOrgId, setStoredOrgId } from "@/lib/orgContext";
import { User, UserPlus, Trash2, Save, Crown, Shield, Loader2, ShieldCheck, Eye, ClipboardCheck, BarChart3 } from "lucide-react";
import React from "react";
import { useRouter } from "next/navigation";
import { Label } from "@/components/ui/label";
import { TableEmptyState } from "@/components/ui/EmptyState";
import { Select } from "@/components/ui/select";

function UsageBar({ pct, color }: { pct: number; color: string }) {
    const ref = React.useRef<HTMLDivElement>(null);
    React.useEffect(() => { if (ref.current) ref.current.style.width = `${pct}%`; }, [pct]);
    return (
        <div className="w-full bg-muted rounded-full h-2">
            <div ref={ref} className={`${color} h-2 rounded-full transition-all`} />
        </div>
    );
}

export default function SettingsOrgPage() {
    const [orgSettings, setOrgSettings] = useState<any>(null);
    const [profile, setProfile] = useState<any>(null);
    const [orgSettingsError, setOrgSettingsError] = useState<string>("");
    const [loading, setLoading] = useState(true);
    const [orgName, setOrgName] = useState("");
    const [tradeType, setTradeType] = useState("");
    const [companySize, setCompanySize] = useState("");
    const [saving, setSaving] = useState(false);
    const [inviteEmail, setInviteEmail] = useState("");
    const [inviteRole, setInviteRole] = useState("viewer");
    const [inviting, setInviting] = useState(false);
    const [dialogOpen, setDialogOpen] = useState(false);
    const { toast } = useToast();
    const supabase = createClient();
    const router = useRouter();
    const [orgId, setOrgId] = useState<string | null>(getStoredOrgId());

    useEffect(() => {
        async function ensureOrg() {
            if (orgId) return;
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) { router.push("/login"); return; }
            try {
                const current = await ApiClient.getCurrentOrg(token);
                if (current?.id) {
                    setStoredOrgId(current.id);
                    setOrgId(current.id);
                } else {
                    router.push("/onboarding");
                }
            } catch {
                router.push("/onboarding");
            }
        }

        async function load() {
            try {
                const { data: { session } } = await supabase.auth.getSession();
                if (!session) return;
                const t = session.access_token;

                const prof = await ApiClient.getProfile(t);
                setProfile(prof);

                if (orgId) {
                    try {
                        const org = await ApiClient.getOrgSettings(orgId, t);
                        setOrgSettingsError("");
                        setOrgSettings(org);
                        setOrgName(org.name);
                        setTradeType(org.trade_type || "");
                        setCompanySize(org.company_size || "");
                    } catch (orgErr: any) {
                        setOrgSettings(null);
                        const msg = String(orgErr?.message || "");
                        const isForbidden = orgErr?.code === "forbidden" || msg.toLowerCase().includes("forbidden");
                        setOrgSettingsError(isForbidden ? "Only owner/admin can access organization settings." : msg || "Failed to load organization settings.");
                    }
                }
            } catch (e: any) {
                toast({ title: "Failed to load settings", description: e.message, variant: "destructive" });
            } finally {
                setLoading(false);
            }
        }
        ensureOrg().then(load);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [orgId, router]);

    const handleSaveOrg = async () => {
        if (!orgId) return;
        setSaving(true);
        try {
            const { data: { session } } = await supabase.auth.getSession();
            await ApiClient.updateOrgSettings(orgId, {
                name: orgName,
                trade_type: tradeType || undefined,
                company_size: companySize || undefined,
            }, session?.access_token);
            toast({ title: "Organization updated", variant: "success" });
            setOrgSettings((prev: any) => ({ ...prev, name: orgName, trade_type: tradeType, company_size: companySize }));
        } catch (e: any) {
            toast({ title: "Failed to update", description: e.message, variant: "destructive" });
        } finally {
            setSaving(false);
        }
    };

    const handleInvite = async () => {
        if (!orgId || !inviteEmail) return;
        setInviting(true);
        try {
            const { data: { session } } = await supabase.auth.getSession();
            const res = await ApiClient.inviteMember(orgId, inviteEmail, inviteRole, session?.access_token);
            toast({ title: "Invite sent", description: res.note || "Member invited", variant: "success" });
            setInviteEmail("");
            setDialogOpen(false);
        } catch (e: any) {
            toast({ title: "Failed to invite", description: e.message, variant: "destructive" });
        } finally {
            setInviting(false);
        }
    };

    const handleRemoveMember = async (userId: string) => {
        if (!orgId) return;
        try {
            const { data: { session } } = await supabase.auth.getSession();
            await ApiClient.removeMember(orgId, userId, session?.access_token);
            toast({ title: "Member removed", variant: "success" });
            setOrgSettings((prev: any) => ({ ...prev, members: prev.members.filter((m: any) => m.user_id !== userId) }));
        } catch (e: any) {
            toast({ title: "Failed to remove", description: e.message, variant: "destructive" });
        }
    };

    const ROLE_CONFIG: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
        owner: { icon: <Crown className="h-3 w-3" />, color: "bg-amber-100 text-amber-800 border-amber-200", label: "Owner" },
        admin: { icon: <Shield className="h-3 w-3" />, color: "bg-blue-100 text-blue-800 border-blue-200", label: "Admin" },
        reviewer: { icon: <ClipboardCheck className="h-3 w-3" />, color: "bg-purple-100 text-purple-800 border-purple-200", label: "Reviewer" },
        analyst: { icon: <BarChart3 className="h-3 w-3" />, color: "bg-teal-100 text-teal-800 border-teal-200", label: "Analyst" },
        compliance_manager: { icon: <ShieldCheck className="h-3 w-3" />, color: "bg-indigo-100 text-indigo-800 border-indigo-200", label: "Manager" },
        viewer: { icon: <Eye className="h-3 w-3" />, color: "bg-slate-100 text-slate-700 border-slate-200", label: "Viewer" },
    };

    const getRoleBadge = (memberRole: string) => {
        const cfg = ROLE_CONFIG[memberRole] || ROLE_CONFIG.viewer;
        return (
            <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold ${cfg.color}`}>
                {cfg.icon} {cfg.label}
            </span>
        );
    };

    const getMemberStatus = (m: any) => {
        if (m.invited && !m.accepted) return { label: "Invited", color: "text-amber-600" };
        return { label: "Active", color: "text-green-600" };
    };

    if (loading) return (
        <div className="space-y-4">
            {[1, 2, 3].map(i => <div key={i} className="h-32 bg-muted/50 rounded-lg animate-pulse" />)}
        </div>
    );

    const role = String(orgSettings?.my_role || "").toLowerCase();
    const canManageOrg = ["owner", "admin"].includes(role);
    const canManageMembers = ["owner", "admin"].includes(role);

    if (orgSettingsError) {
        return (
            <Card>
                <CardContent className="p-8 text-center">
                    <p className="text-sm font-medium text-foreground mb-1">Organization settings unavailable</p>
                    <p className="text-sm text-muted-foreground">{orgSettingsError}</p>
                </CardContent>
            </Card>
        );
    }

    if (!orgSettings) {
        return (
            <Card>
                <CardContent className="p-8 text-center text-muted-foreground">
                    No organization selected. Complete <a href="/onboarding" className="text-primary underline">Onboarding</a> to create your workspace.
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Organization Details</CardTitle>
                    <CardDescription>Company name, trade type, and size.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid md:grid-cols-3 gap-4">
                        <div>
                            <Label htmlFor="org-name">Organization Name</Label>
                            <Input id="org-name" value={orgName} onChange={(e) => setOrgName(e.target.value)} disabled={!canManageOrg} className="mt-1.5" />
                        </div>
                        <div>
                            <Label htmlFor="trade-type">Trade Type</Label>
                            <Input id="trade-type" value={tradeType} onChange={(e) => setTradeType(e.target.value)} placeholder="e.g. Construction" disabled={!canManageOrg} className="mt-1.5" />
                        </div>
                        <div>
                            <Label htmlFor="company-size">Company Size</Label>
                            <Input id="company-size" value={companySize} onChange={(e) => setCompanySize(e.target.value)} placeholder="e.g. 50-100" disabled={!canManageOrg} className="mt-1.5" />
                        </div>
                    </div>
                    {canManageOrg && (
                        <Button onClick={handleSaveOrg} disabled={saving || (orgName === (orgSettings?.name || "") && tradeType === (orgSettings?.trade_type || "") && companySize === (orgSettings?.company_size || ""))} size="sm" className="gap-2">
                            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save Changes
                        </Button>
                    )}
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Plan &amp; Usage</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex items-center gap-3">
                        <span className="text-sm text-muted-foreground">Current Plan:</span>
                        <Badge variant="secondary" className="uppercase font-semibold">{orgSettings.plan}</Badge>
                    </div>
                    <div className="space-y-2">
                        <div className="flex justify-between text-sm"><span>Exports</span><span className="font-medium">{orgSettings.exports_used} / {orgSettings.exports_limit}</span></div>
                        <UsageBar pct={Math.min(100, (orgSettings.exports_used / Math.max(1, orgSettings.exports_limit)) * 100)} color="bg-primary" />
                    </div>
                    <div className="space-y-2">
                        <div className="flex justify-between text-sm"><span>Storage</span><span className="font-medium">{(orgSettings.storage_used / (1024 * 1024)).toFixed(1)} MB / {(orgSettings.storage_limit / (1024 * 1024)).toFixed(0)} MB</span></div>
                        <UsageBar pct={Math.min(100, (orgSettings.storage_used / Math.max(1, orgSettings.storage_limit)) * 100)} color="bg-green-500" />
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                        <CardTitle className="text-base">Members</CardTitle>
                        <CardDescription>Team members in your organization.</CardDescription>
                    </div>
                    {canManageMembers && (
                        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                            <DialogTrigger asChild>
                                <Button size="sm" variant="outline" className="gap-2"><UserPlus className="h-4 w-4" /> Invite</Button>
                            </DialogTrigger>
                            <DialogContent>
                                <DialogHeader><DialogTitle>Invite Member</DialogTitle></DialogHeader>
                                <div className="space-y-4 pt-4">
                                    <div>
                                        <Label htmlFor="invite-email">Email Address</Label>
                                        <Input id="invite-email" placeholder="colleague@company.com" type="email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} className="mt-1.5" />
                                    </div>
                                    <div>
                                        <Label htmlFor="invite-role">Role</Label>
                                        <Select id="invite-role" value={inviteRole} onChange={(e) => setInviteRole(e.target.value)} className="mt-1.5" aria-label="Member role">
                                            <option value="viewer">Viewer</option>
                                            <option value="reviewer">Reviewer</option>
                                            <option value="compliance_manager">Compliance Manager</option>
                                            <option value="admin">Admin</option>
                                            <option value="owner">Owner</option>
                                        </Select>
                                    </div>
                                    <p className="text-xs text-amber-600">⚠️ Email delivery coming soon. The invite will be saved but no email sent yet.</p>
                                    <Button onClick={handleInvite} disabled={inviting || !inviteEmail} className="w-full gap-2">
                                        {inviting ? <><Loader2 className="h-4 w-4 animate-spin" /> Sending...</> : "Send Invite"}
                                    </Button>
                                </div>
                            </DialogContent>
                        </Dialog>
                    )}
                </CardHeader>
                <CardContent>
                    <div className="overflow-auto">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Name</TableHead>
                                    <TableHead>Email</TableHead>
                                    <TableHead>Role</TableHead>
                                    <TableHead>Status</TableHead>
                                    {canManageMembers && <TableHead className="w-28">Actions</TableHead>}
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {(orgSettings.members || []).length === 0 ? (
                                    <TableEmptyState cols={canManageMembers ? 5 : 4} icon={<User className="h-10 w-10" />} title="No members yet" description="Invite your first team member to get started." />
                                ) : (
                                    (orgSettings.members || []).map((m: any) => {
                                        const memberStatus = getMemberStatus(m);
                                        const isCurrentUser = m.user_id === profile?.user_id;
                                        const isOwner = m.role === "owner";
                                        return (
                                            <TableRow key={m.user_id}>
                                                <TableCell>
                                                    <div className="flex items-center gap-2">
                                                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-xs font-semibold uppercase">{(m.full_name || m.email || m.user_id || "?").charAt(0)}</div>
                                                        <div>
                                                            <p className="text-sm font-medium">{m.full_name || "—"}</p>
                                                            <p className="text-xs text-muted-foreground font-mono">{m.user_id?.slice(0, 8)}…</p>
                                                        </div>
                                                    </div>
                                                </TableCell>
                                                <TableCell className="text-sm text-muted-foreground">{m.email || "—"}</TableCell>
                                                <TableCell>
                                                    {canManageMembers && !isOwner && !isCurrentUser ? (
                                                        <Select value={m.role} onChange={async (e) => {
                                                            const newRole = e.target.value;
                                                            try {
                                                                setOrgSettings((prev: any) => ({ ...prev, members: prev.members.map((mem: any) => mem.user_id === m.user_id ? { ...mem, role: newRole } : mem) }));
                                                                toast({ title: "Role updated", description: `Changed to ${newRole}`, variant: "success" });
                                                            } catch (err: any) {
                                                                toast({ title: "Failed to update role", description: err.message, variant: "destructive" });
                                                            }
                                                        }} className="h-8 text-xs w-32" aria-label={`Change role for ${m.full_name || m.user_id}`}>
                                                            <option value="viewer">Viewer</option>
                                                            <option value="analyst">Analyst</option>
                                                            <option value="reviewer">Reviewer</option>
                                                            <option value="compliance_manager">Manager</option>
                                                            <option value="admin">Admin</option>
                                                        </Select>
                                                    ) : getRoleBadge(m.role)}
                                                </TableCell>
                                                <TableCell><span className={`text-xs font-medium ${memberStatus.color}`}>● {memberStatus.label}</span></TableCell>
                                                {canManageMembers && (
                                                    <TableCell>
                                                        {!isCurrentUser && !isOwner ? (
                                                            <Button size="sm" variant="ghost" onClick={() => handleRemoveMember(m.user_id)} className="h-8 text-xs text-muted-foreground hover:text-red-600"><Trash2 className="h-3.5 w-3.5 mr-1" /> Remove</Button>
                                                        ) : <span className="text-xs text-muted-foreground" title={isCurrentUser ? "You cannot remove yourself" : "Owner cannot be removed"}>—</span>}
                                                    </TableCell>
                                                )}
                                            </TableRow>
                                        );
                                    })
                                )}
                            </TableBody>
                        </Table>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
