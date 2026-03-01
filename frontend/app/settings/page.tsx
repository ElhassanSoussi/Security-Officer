"use client";

import { useEffect, useState } from "react";
import { ApiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toaster";
import { createClient } from "@/utils/supabase/client";
import { getStoredOrgId, setStoredOrgId } from "@/lib/orgContext";
import { Building2, User, UserPlus, Trash2, Save, Crown, Shield, Loader2, ShieldCheck, Lock, Info, Eye, ClipboardCheck, BarChart3, ExternalLink, Download } from "lucide-react";
import React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Label } from "@/components/ui/label";
import { TableEmptyState } from "@/components/ui/EmptyState";
import { Select } from "@/components/ui/select";
import { MemoryGovPanel } from "@/components/settings/MemoryGovPanel";

function UsageBar({ pct, color }: { pct: number; color: string }) {
    const ref = React.useRef<HTMLDivElement>(null);
    React.useEffect(() => { if (ref.current) ref.current.style.width = `${pct}%`; }, [pct]);
    return (
        <div className="w-full bg-muted rounded-full h-2">
            <div ref={ref} className={`${color} h-2 rounded-full transition-all`} />
        </div>
    );
}

export default function SettingsPage() {
    const [orgSettings, setOrgSettings] = useState<any>(null);
    const [profile, setProfile] = useState<any>(null);
    const [orgSettingsError, setOrgSettingsError] = useState<string>("");
    const [loading, setLoading] = useState(true);
    const [orgName, setOrgName] = useState("");
    const [tradeType, setTradeType] = useState("");
    const [companySize, setCompanySize] = useState("");
    const [saving, setSaving] = useState(false);
    const [savingProfile, setSavingProfile] = useState(false);
    const [inviteEmail, setInviteEmail] = useState("");
    const [inviteRole, setInviteRole] = useState("viewer");
    const [inviting, setInviting] = useState(false);
    const [dialogOpen, setDialogOpen] = useState(false);
    const { toast } = useToast();
    const supabase = createClient();
    const router = useRouter();
    const [orgId, setOrgId] = useState<string | null>(getStoredOrgId());
    const [fullName, setFullName] = useState("");
    const [phone, setPhone] = useState("");
    const [title, setTitle] = useState("");
    const [tab, setTab] = useState<"organization" | "profile" | "security" | "memory">("organization");

    useEffect(() => {
        async function ensureOrg() {
            if (orgId) return;
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            if (!token) {
                router.push("/login");
                return;
            }
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
                setFullName(prof?.full_name || "");
                setPhone(prof?.phone || "");
                setTitle(prof?.title || "");

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
                        if (isForbidden) {
                            setTab("profile");
                        }
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
            setOrgSettings((prev: any) => ({
                ...prev,
                name: orgName,
                trade_type: tradeType,
                company_size: companySize,
            }));
        } catch (e: any) {
            toast({ title: "Failed to update", description: e.message, variant: "destructive" });
        } finally {
            setSaving(false);
        }
    };

    const handleSaveProfile = async () => {
        setSavingProfile(true);
        try {
            const { data: { session } } = await supabase.auth.getSession();
            const updated = await ApiClient.updateProfile({
                full_name: fullName || undefined,
                phone: phone || undefined,
                title: title || undefined,
            }, session?.access_token);
            setProfile(updated);
            toast({ title: "Profile updated", variant: "success" });
        } catch (e: any) {
            toast({ title: "Failed to update profile", description: e.message, variant: "destructive" });
        } finally {
            setSavingProfile(false);
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
            setOrgSettings((prev: any) => ({
                ...prev,
                members: prev.members.filter((m: any) => m.user_id !== userId),
            }));
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
        <div className="max-w-4xl mx-auto space-y-6">
            <div className="h-8 w-48 bg-muted rounded animate-pulse" />
            <div className="space-y-4">
                {[1, 2, 3].map(i => (
                    <div key={i} className="h-32 bg-muted/50 rounded-lg animate-pulse" />
                ))}
            </div>
        </div>
    );

    const role = String(orgSettings?.my_role || "").toLowerCase();
    const canManageOrg = ["owner", "admin"].includes(role);
    const canManageMembers = ["owner", "admin"].includes(role);

    return (
        <div className="flex flex-col md:flex-row gap-6 items-start max-w-7xl mx-auto">
            <Tabs value={tab} onValueChange={(value) => setTab(value as "organization" | "profile" | "security" | "memory")} className="w-full flex-col md:flex-row flex gap-6">
                <TabsList className="flex flex-row md:flex-col h-auto bg-transparent w-full md:w-64 gap-2 p-0 overflow-x-auto justify-start border-r border-border md:pr-4 sticky top-6">
                    <TabsTrigger value="organization" className="w-full justify-start gap-2 data-[state=active]:bg-muted/50 px-4 py-2 hover:bg-muted/30 whitespace-nowrap">
                        <Building2 className="h-4 w-4" /> Organization
                    </TabsTrigger>
                    <TabsTrigger value="profile" className="w-full justify-start gap-2 data-[state=active]:bg-muted/50 px-4 py-2 hover:bg-muted/30 whitespace-nowrap">
                        <User className="h-4 w-4" /> Profile
                    </TabsTrigger>
                    <TabsTrigger value="security" className="w-full justify-start gap-2 data-[state=active]:bg-muted/50 px-4 py-2 hover:bg-muted/30 whitespace-nowrap">
                        <Shield className="h-4 w-4" /> Sec. & Compliance
                    </TabsTrigger>
                    <TabsTrigger value="memory" className="w-full justify-start gap-2 data-[state=active]:bg-muted/50 px-4 py-2 hover:bg-muted/30 whitespace-nowrap">
                        <Building2 className="h-4 w-4" /> Inst. Memory
                    </TabsTrigger>
                </TabsList>
                
                <div className="flex-1 min-w-0">
                    <TabsContent value="organization" className="space-y-6 mt-0">
                        {orgSettings ? (
                            <>
                                {/* Org Name */}
                                <Card>
                                    <CardHeader>
                                        <CardTitle>Organization Name</CardTitle>
                                        <CardDescription>Company details and trade information.</CardDescription>
                                    </CardHeader>
                                    <CardContent className="space-y-4">
                                        <div className="grid md:grid-cols-3 gap-4">
                                            <div>
                                                <Label htmlFor="org-name">Organization Name</Label>
                                                <Input
                                                    id="org-name"
                                                    value={orgName}
                                                    onChange={(e) => setOrgName(e.target.value)}
                                                    disabled={!canManageOrg}
                                                    className="mt-1.5"
                                                />
                                            </div>
                                            <div>
                                                <Label htmlFor="trade-type">Trade Type</Label>
                                                <Input
                                                    id="trade-type"
                                                    value={tradeType}
                                                    onChange={(e) => setTradeType(e.target.value)}
                                                    placeholder="e.g. Construction"
                                                    disabled={!canManageOrg}
                                                    className="mt-1.5"
                                                />
                                            </div>
                                            <div>
                                                <Label htmlFor="company-size">Company Size</Label>
                                                <Input
                                                    id="company-size"
                                                    value={companySize}
                                                    onChange={(e) => setCompanySize(e.target.value)}
                                                    placeholder="e.g. 50-100"
                                                    disabled={!canManageOrg}
                                                    className="mt-1.5"
                                                />
                                            </div>
                                        </div>
                                        {canManageOrg && (
                                            <Button
                                                onClick={handleSaveOrg}
                                                disabled={
                                                    saving ||
                                                    (
                                                        orgName === (orgSettings?.name || "") &&
                                                        tradeType === (orgSettings?.trade_type || "") &&
                                                        companySize === (orgSettings?.company_size || "")
                                                    )
                                                }
                                                className="gap-2"
                                            >
                                                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save
                                            </Button>
                                        )}
                                    </CardContent>
                                </Card>

                                {/* Plan & Usage */}
                                <Card>
                                    <CardHeader>
                                        <CardTitle>Plan & Usage</CardTitle>
                                    </CardHeader>
                                    <CardContent className="space-y-4">
                                        <div className="flex items-center gap-3">
                                            <span className="text-sm text-muted-foreground">Current Plan:</span>
                                            <Badge variant="secondary" className="uppercase font-semibold">{orgSettings.plan}</Badge>
                                        </div>
                                        <div className="space-y-2">
                                            <div className="flex justify-between text-sm">
                                                <span>Exports</span>
                                                <span className="font-medium">{orgSettings.exports_used} / {orgSettings.exports_limit}</span>
                                            </div>
                                            <UsageBar
                                                pct={Math.min(100, (orgSettings.exports_used / Math.max(1, orgSettings.exports_limit)) * 100)}
                                                color="bg-primary"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <div className="flex justify-between text-sm">
                                                <span>Storage</span>
                                                <span className="font-medium">
                                                    {(orgSettings.storage_used / (1024 * 1024)).toFixed(1)} MB / {(orgSettings.storage_limit / (1024 * 1024)).toFixed(0)} MB
                                                </span>
                                            </div>
                                            <UsageBar
                                                pct={Math.min(100, (orgSettings.storage_used / Math.max(1, orgSettings.storage_limit)) * 100)}
                                                color="bg-success"
                                            />
                                        </div>
                                    </CardContent>
                                </Card>

                                {/* Members */}
                                <Card>
                                    <CardHeader className="flex flex-row items-center justify-between">
                                        <div>
                                            <CardTitle>Members</CardTitle>
                                            <CardDescription>Team members in your organization.</CardDescription>
                                        </div>
                                        {canManageMembers && (
                                            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                                                <DialogTrigger asChild>
                                                    <Button size="sm" variant="outline" className="gap-2">
                                                        <UserPlus className="h-4 w-4" /> Invite Member
                                                    </Button>
                                                </DialogTrigger>
                                                <DialogContent>
                                                    <DialogHeader>
                                                        <DialogTitle>Invite Member</DialogTitle>
                                                    </DialogHeader>
                                                    <div className="space-y-4 pt-4">
                                                        <div>
                                                            <Label htmlFor="invite-email">Email Address</Label>
                                                            <Input
                                                                id="invite-email"
                                                                placeholder="colleague@company.com"
                                                                type="email"
                                                                value={inviteEmail}
                                                                onChange={(e) => setInviteEmail(e.target.value)}
                                                                className="mt-1.5"
                                                            />
                                                        </div>
                                                        <div>
                                                            <Label htmlFor="invite-role">Role</Label>
                                                            <Select
                                                                id="invite-role"
                                                                value={inviteRole}
                                                                onChange={(e) => setInviteRole(e.target.value)}
                                                                className="mt-1.5"
                                                                aria-label="Member role"
                                                            >
                                                                <option value="viewer">Viewer</option>
                                                                <option value="reviewer">Reviewer</option>
                                                                <option value="compliance_manager">Compliance Manager</option>
                                                                <option value="admin">Admin</option>
                                                                <option value="owner">Owner</option>
                                                            </Select>
                                                        </div>
                                                        <p className="text-xs text-amber-600">
                                                            ⚠️ Email delivery coming soon. The invite will be saved but no email sent yet.
                                                        </p>
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
                                                    <TableEmptyState
                                                        cols={canManageMembers ? 5 : 4}
                                                        icon={<User className="h-10 w-10" />}
                                                        title="No members yet"
                                                        description="Invite your first team member to get started."
                                                    />
                                                ) : (
                                                (orgSettings.members || []).map((m: any) => {
                                                    const memberStatus = getMemberStatus(m);
                                                    const isCurrentUser = m.user_id === profile?.user_id;
                                                    const isOwner = m.role === "owner";
                                                    return (
                                                    <TableRow key={m.user_id}>
                                                        <TableCell>
                                                            <div className="flex items-center gap-2">
                                                                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-xs font-semibold uppercase">
                                                                    {(m.full_name || m.email || m.user_id || "?").charAt(0)}
                                                                </div>
                                                                <div>
                                                                    <p className="text-sm font-medium">{m.full_name || "—"}</p>
                                                                    <p className="text-xs text-muted-foreground font-mono">{m.user_id?.slice(0, 8)}…</p>
                                                                </div>
                                                            </div>
                                                        </TableCell>
                                                        <TableCell className="text-sm text-muted-foreground">{m.email || "—"}</TableCell>
                                                        <TableCell>
                                                            {canManageMembers && !isOwner && !isCurrentUser ? (
                                                                <Select
                                                                    value={m.role}
                                                                    onChange={async (e) => {
                                                                        const newRole = e.target.value;
                                                                        try {
                                                                            // Optimistic update
                                                                            setOrgSettings((prev: any) => ({
                                                                                ...prev,
                                                                                members: prev.members.map((mem: any) =>
                                                                                    mem.user_id === m.user_id ? { ...mem, role: newRole } : mem
                                                                                ),
                                                                            }));
                                                                            toast({ title: "Role updated", description: `Changed to ${newRole}`, variant: "success" });
                                                                        } catch (err: any) {
                                                                            toast({ title: "Failed to update role", description: err.message, variant: "destructive" });
                                                                        }
                                                                    }}
                                                                    className="h-8 text-xs w-32"
                                                                    aria-label={`Change role for ${m.full_name || m.user_id}`}
                                                                >
                                                                    <option value="viewer">Viewer</option>
                                                                    <option value="analyst">Analyst</option>
                                                                    <option value="reviewer">Reviewer</option>
                                                                    <option value="compliance_manager">Manager</option>
                                                                    <option value="admin">Admin</option>
                                                                </Select>
                                                            ) : (
                                                                getRoleBadge(m.role)
                                                            )}
                                                        </TableCell>
                                                        <TableCell>
                                                            <span className={`text-xs font-medium ${memberStatus.color}`}>● {memberStatus.label}</span>
                                                        </TableCell>
                                                        {canManageMembers && (
                                                            <TableCell>
                                                                {!isCurrentUser && !isOwner ? (
                                                                    <Button
                                                                        size="sm"
                                                                        variant="ghost"
                                                                        onClick={() => handleRemoveMember(m.user_id)}
                                                                        className="h-8 text-xs text-muted-foreground hover:text-red-600"
                                                                    >
                                                                        <Trash2 className="h-3.5 w-3.5 mr-1" /> Remove
                                                                    </Button>
                                                                ) : (
                                                                    <span className="text-xs text-muted-foreground" title={isCurrentUser ? "You cannot remove yourself" : "Owner cannot be removed"}>
                                                                        —
                                                                    </span>
                                                                )}
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
                            </>
                        ) : orgSettingsError ? (
                            <Card>
                                <CardContent className="p-8 text-center">
                                    <p className="text-sm font-medium text-foreground mb-1">Organization settings unavailable</p>
                                    <p className="text-sm text-muted-foreground">{orgSettingsError}</p>
                                </CardContent>
                            </Card>
                        ) : (
                            <Card>
                                <CardContent className="p-8 text-center text-muted-foreground">
                                    No organization selected. Complete <a href="/onboarding" className="text-primary underline">Onboarding</a> to create your workspace.
                                </CardContent>
                            </Card>
                        )}
                    </TabsContent>

                    {/* ── Profile Tab ───────────────────────────────── */}
                    <TabsContent value="profile" className="mt-6">
                        <Card>
                            <CardHeader>
                                <CardTitle>Your Profile</CardTitle>
                                <CardDescription>Basic account information.</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4 max-w-md">
                                <div>
                                    <Label htmlFor="profile-name">Full Name</Label>
                                    <Input id="profile-name" value={fullName} onChange={(e) => setFullName(e.target.value)} className="mt-1.5" />
                                </div>
                                <div>
                                    <Label htmlFor="profile-title">Title</Label>
                                    <Input id="profile-title" value={title} onChange={(e) => setTitle(e.target.value)} className="mt-1.5" />
                                </div>
                                <div>
                                    <Label htmlFor="profile-phone">Phone</Label>
                                    <Input id="profile-phone" value={phone} onChange={(e) => setPhone(e.target.value)} className="mt-1.5" />
                                </div>
                                <div>
                                    <Label htmlFor="profile-email">Email</Label>
                                    <Input id="profile-email" value={profile?.email || "—"} disabled className="mt-1.5" />
                                </div>
                                <div>
                                    <Label htmlFor="profile-uid">User ID</Label>
                                    <Input id="profile-uid" value={profile?.user_id || "—"} disabled className="mt-1.5 font-mono text-xs" />
                                </div>
                                <div>
                                    <Label htmlFor="profile-role">Current Role</Label>
                                    <Input id="profile-role" value={orgSettings?.my_role || "viewer"} disabled className="mt-1.5" />
                                </div>
                                <div className="pt-2">
                                    <Button onClick={handleSaveProfile} disabled={savingProfile} className="gap-2">
                                        {savingProfile ? <><Loader2 className="h-4 w-4 animate-spin" /> Saving...</> : "Save Profile"}
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* ── Security & Compliance Tab ────────────────── */}
                    <TabsContent value="security" className="space-y-6 mt-6">
                        <Card>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <ShieldCheck className="h-5 w-5 text-primary" /> Security &amp; Compliance
                                </CardTitle>
                                <CardDescription>
                                    How NYC Compliance Architect protects your data and maintains regulatory alignment.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-5">
                                <div className="grid gap-4 md:grid-cols-2">
                                    <div className="rounded-lg border bg-muted/30 p-4 space-y-1.5">
                                        <div className="flex items-center gap-2">
                                            <Lock className="h-4 w-4 text-muted-foreground" />
                                            <h4 className="text-sm font-semibold text-foreground">Data Encryption</h4>
                                        </div>
                                        <p className="text-xs text-muted-foreground leading-relaxed">
                                            All data is encrypted in transit (TLS 1.2+) and at rest via Supabase-managed AES-256 encryption.
                                        </p>
                                    </div>
                                    <div className="rounded-lg border bg-muted/30 p-4 space-y-1.5">
                                        <div className="flex items-center gap-2">
                                            <Shield className="h-4 w-4 text-muted-foreground" />
                                            <h4 className="text-sm font-semibold text-foreground">Role-Based Access</h4>
                                        </div>
                                        <p className="text-xs text-muted-foreground leading-relaxed">
                                            Row-level security policies enforce organization boundaries. Members can only access their own org data.
                                        </p>
                                    </div>
                                    <div className="rounded-lg border bg-muted/30 p-4 space-y-1.5">
                                        <div className="flex items-center gap-2">
                                            <ShieldCheck className="h-4 w-4 text-muted-foreground" />
                                            <h4 className="text-sm font-semibold text-foreground">Audit Trail</h4>
                                        </div>
                                        <p className="text-xs text-muted-foreground leading-relaxed">
                                            Every AI-generated answer, manual edit, review decision, and export is logged with timestamps and user IDs.
                                        </p>
                                    </div>
                                    <div className="rounded-lg border bg-muted/30 p-4 space-y-1.5">
                                        <div className="flex items-center gap-2">
                                            <Info className="h-4 w-4 text-muted-foreground" />
                                            <h4 className="text-sm font-semibold text-foreground">Source Transparency</h4>
                                        </div>
                                        <p className="text-xs text-muted-foreground leading-relaxed">
                                            Each answer includes the source document, page reference, and confidence score for full traceability.
                                        </p>
                                    </div>
                                </div>
                                <div className="rounded-lg border border-blue-100 bg-blue-50/50 p-4 text-xs text-blue-800 leading-relaxed">
                                    <strong>Compliance note:</strong> NYC Compliance Architect is designed to align with SOC 2 Type II controls
                                    for data handling, access management, and audit logging. Contact your administrator for your organization&apos;s
                                    specific compliance documentation.
                                </div>
                                <div className="pt-1">
                                    <Link href="/security" className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline">
                                        <ExternalLink className="h-3.5 w-3.5" /> View full Security &amp; Data Practices →
                                    </Link>
                                </div>
                            </CardContent>
                        </Card>

                        {/* About */}
                        {/* Phase 21: Access Audit Report */}
                        {canManageOrg && orgId && (
                            <Card>
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2">
                                        <Download className="h-5 w-5 text-primary" /> Access Audit Report
                                    </CardTitle>
                                    <CardDescription>
                                        Download a SOC2-ready report of all users, roles, and activity for this organization.
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-3">
                                    <div className="flex flex-wrap gap-3">
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            className="gap-2"
                                            onClick={async () => {
                                                try {
                                                    const { data: { session } } = await supabase.auth.getSession();
                                                    await ApiClient.downloadAccessReportCSV(orgId!, session?.access_token);
                                                    toast({ title: "Access report downloaded", variant: "success" });
                                                } catch (e: any) {
                                                    toast({ title: "Download failed", description: e.message, variant: "destructive" });
                                                }
                                            }}
                                        >
                                            <Download className="h-4 w-4" /> Download CSV
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            className="gap-2"
                                            onClick={async () => {
                                                try {
                                                    const { data: { session } } = await supabase.auth.getSession();
                                                    const report = await ApiClient.getAccessReport(orgId!, session?.access_token);
                                                    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
                                                    const url = window.URL.createObjectURL(blob);
                                                    const a = document.createElement("a");
                                                    a.href = url;
                                                    a.download = `access_report_${orgId!.slice(0, 8)}.json`;
                                                    document.body.appendChild(a);
                                                    a.click();
                                                    window.URL.revokeObjectURL(url);
                                                    document.body.removeChild(a);
                                                    toast({ title: "Access report downloaded", variant: "success" });
                                                } catch (e: any) {
                                                    toast({ title: "Download failed", description: e.message, variant: "destructive" });
                                                }
                                            }}
                                        >
                                            <Download className="h-4 w-4" /> Download JSON
                                        </Button>
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        Includes: user roles, member-since dates, last activity timestamps, activity counts, and evidence export counts.
                                    </p>
                                </CardContent>
                            </Card>
                        )}

                        <Card>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <Info className="h-5 w-5 text-muted-foreground" /> About
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3 text-sm">
                                <div className="flex justify-between">
                                    <span className="text-muted-foreground">Product</span>
                                    <span className="font-medium">NYC Compliance Architect</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-muted-foreground">Version</span>
                                    <span className="font-mono text-xs">1.0.0</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-muted-foreground">Environment</span>
                                    <span className="font-mono text-xs">{process.env.NODE_ENV === "production" ? "Production" : "Development"}</span>
                                </div>
                                {orgId && (
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">Organization ID</span>
                                        <span className="font-mono text-xs">{orgId.slice(0, 12)}…</span>
                                    </div>
                                )}
                                <p className="text-xs text-muted-foreground pt-2 border-t">
                                    AI-powered security questionnaire automation for NYC construction compliance.
                                    Built for SCA, MTA, and PASSPort submissions.
                                </p>
                            </CardContent>
                        </Card>
                    </TabsContent>
                    <TabsContent value="memory" className="space-y-6 mt-6">
                        <MemoryGovPanel />
                    </TabsContent>
                </div>
            </Tabs>
        </div>
    );
}
