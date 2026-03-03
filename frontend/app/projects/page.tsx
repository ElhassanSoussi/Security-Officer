"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FolderKanban, Plus, Search, ExternalLink, Clock } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { useRouter } from "next/navigation";
import { ApiClient } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";
import { Project } from "@/types";
import { getStoredOrgId, setStoredOrgId } from "@/lib/orgContext";
import { useToast } from "@/components/ui/toaster";
import PageHeader from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { OnboardingStepBanner } from "@/components/onboarding/OnboardingStepBanner";

export default function ProjectsPage() {
    const [projects, setProjects] = useState<Project[]>([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState("");
    const [error, setError] = useState("");
    const [token, setToken] = useState<string | undefined>(undefined);
    const [selectedOrgId, setSelectedOrgId] = useState("");
    const [selectedOrgName, setSelectedOrgName] = useState("");

    // New Project State
    const [newProjectName, setNewProjectName] = useState("");
    const [isOpen, setIsOpen] = useState(false);
    const [creating, setCreating] = useState(false);
    const [formError, setFormError] = useState("");
    const router = useRouter();
    const { toast } = useToast();

    useEffect(() => {
        const fetchProjects = async () => {
            setLoading(true);
            setError("");
            try {
                const supabase = createClient();
                const { data: { session } } = await supabase.auth.getSession();
                const accessToken = session?.access_token;
                setToken(accessToken);

                if (!accessToken) {
                    router.push("/login");
                    setProjects([]);
                    return;
                }

                const orgs = await ApiClient.getMyOrgs(accessToken);
                if (!orgs || orgs.length === 0) {
                    router.push("/onboarding");
                    return;
                }

                const storedOrg = getStoredOrgId() || "";
                const requestedOrg =
                    typeof window !== "undefined"
                        ? new URLSearchParams(window.location.search).get("orgId") || ""
                        : "";
                const selectedOrg =
                    orgs.find((o: any) => o.id === requestedOrg) ||
                    orgs.find((o: any) => o.id === storedOrg) ||
                    orgs[0];

                setSelectedOrgId(selectedOrg.id);
                setSelectedOrgName(selectedOrg.name || selectedOrg.id);
                setStoredOrgId(selectedOrg.id);
                const projectRows = await ApiClient.getProjects(selectedOrg.id, accessToken);
                setProjects(projectRows || []);
            } catch (err: any) {
                console.error("Failed to fetch projects:", err);
                if (String(err?.message || "").toLowerCase().includes("unauthorized")) {
                    router.push("/login");
                    return;
                }
                setError(err?.message || "Failed to load projects.");
                setProjects([]);
            } finally {
                setLoading(false);
            }
        };
        fetchProjects();
    }, [router]);

    const handleCreate = async () => {
        setFormError("");
        if (!selectedOrgId || !newProjectName.trim()) {
            setFormError("Project name is required.");
            return;
        }

        try {
            setCreating(true);
            const created = await ApiClient.createProject(selectedOrgId, newProjectName.trim(), undefined, token);
            setProjects((prev) => [created, ...prev]);
            setNewProjectName("");
            setIsOpen(false);
            toast({ title: "Project Created", description: `"${created.project_name || newProjectName.trim()}" is ready.`, variant: "success" });

            // Phase 26 onboarding: completing step 2 (create a project) advances to step 3
            try {
                if (token) {
                    const st = await ApiClient.getOnboardingState(token);
                    if (!st.onboarding_completed && st.onboarding_step === 2) {
                        await ApiClient.patchOnboardingState({ onboarding_step: 3 }, token);
                    }
                }
            } catch {
                // ignore
            }

            router.push(`/projects/${created.org_id}/${created.project_id}`);
        } catch (err: any) {
            console.error("Create project failed:", err);
            if (String(err?.message || "").toLowerCase().includes("unauthorized")) {
                router.push("/login");
                return;
            }
            setFormError(err?.message || "Failed to create project.");
            toast({ title: "Create Failed", description: err?.message || "Failed to create project.", variant: "destructive" });
        } finally {
            setCreating(false);
        }
    };

    const filtered = projects.filter(p =>
        (p.project_name || "").toLowerCase().includes(search.toLowerCase()) ||
        p.project_id.toLowerCase().includes(search.toLowerCase()) ||
        p.org_id.toLowerCase().includes(search.toLowerCase())
    );

    return (
        <div className="space-y-8">
            <OnboardingStepBanner expectedStep={2} />
            <Dialog open={isOpen} onOpenChange={setIsOpen}>
                <PageHeader
                    title="Projects"
                    subtitle="Organize documents and runs into compliance workspaces."
                    actions={(
                        <div>
                            <DialogTrigger asChild>
                                <Button>
                                    <Plus className="mr-2 h-4 w-4" /> New Project
                                </Button>
                            </DialogTrigger>
                        </div>
                    )}
                />
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Create New Project</DialogTitle>
                        <DialogDescription>
                            Create a workspace to organize documents and runs.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label>Organization</Label>
                            <Input value={selectedOrgName || selectedOrgId} readOnly />
                        </div>
                        <div className="space-y-2">
                            <Label>Project Name</Label>
                            <Input placeholder="e.g. SCA Bid - PS 182 Modernization" value={newProjectName} onChange={e => setNewProjectName(e.target.value)} />
                        </div>
                        {formError && <p className="text-sm text-destructive">{formError}</p>}
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsOpen(false)}>Cancel</Button>
                        <Button onClick={handleCreate} disabled={!selectedOrgId || !newProjectName.trim() || creating}>
                            {creating ? "Creating..." : "Create Project"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            <div className="flex items-center gap-2 max-w-sm">
                <div className="relative flex-1">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                    <Input
                        id="project-search"
                        aria-label="Search projects"
                        placeholder="Search by name or ID…"
                        className="pl-8"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>
                {search && (
                    <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground px-2" onClick={() => setSearch("")}>
                        Clear
                    </Button>
                )}
            </div>
            {search && !loading && (
                <p className="text-xs text-muted-foreground -mt-5">
                    {filtered.length} result{filtered.length !== 1 ? "s" : ""} for &ldquo;{search}&rdquo;
                </p>
            )}

            {error && (
                <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                    {error}
                </div>
            )}

            {loading && (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {[1, 2, 3].map((i) => (
                        <Card key={i} className="border-border">
                            <CardHeader className="pb-2">
                                <div className="h-10 w-10 bg-muted rounded-lg animate-pulse mb-2" />
                                <div className="h-5 w-3/4 bg-muted rounded animate-pulse" />
                                <div className="h-3 w-1/2 bg-muted/60 rounded animate-pulse mt-2" />
                            </CardHeader>
                            <CardContent>
                                <div className="h-3 w-1/3 bg-muted/60 rounded animate-pulse mt-2" />
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {filtered.map((project, idx) => (
                    <Card
                        key={idx}
                        className="group hover:shadow-md hover:border-primary/30 transition-all cursor-pointer border-border"
                        onClick={() => router.push(`/projects/${project.org_id}/${project.project_id}`)}
                    >
                        <CardHeader className="pb-2">
                            <div className="flex justify-between items-start">
                                <div className="p-2 bg-blue-50 text-blue-600 rounded-lg w-fit mb-2">
                                    <FolderKanban className="h-5 w-5" />
                                </div>
                                <ExternalLink className="h-4 w-4 text-muted group-hover:text-primary transition-colors" />
                            </div>
                            <CardTitle className="text-base leading-snug group-hover:text-primary transition-colors">
                                {project.project_name || project.project_id}
                            </CardTitle>
                            <CardDescription className="truncate text-xs">{project.project_id}</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="flex items-center justify-between">
                                <div className="text-xs text-muted-foreground group-hover:text-foreground transition-colors">
                                    View vault &amp; runs →
                                </div>
                                {project.last_activity && (
                                    <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                                        <Clock className="h-3 w-3" />
                                        {new Date(project.last_activity).toLocaleDateString()}
                                    </div>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {!loading && filtered.length === 0 && search && (
                <EmptyState
                    icon={<Search className="h-12 w-12" />}
                    title="No matching projects"
                    description={`No projects match "${search}". Try a different name or ID.`}
                    action={
                        <Button variant="outline" onClick={() => setSearch("")}>
                            Clear search
                        </Button>
                    }
                />
            )}

            {!loading && projects.length === 0 && !search && (
                <div className="space-y-6">
                    <EmptyState
                        icon={<FolderKanban className="h-12 w-12" />}
                        title="No projects yet"
                        description="Projects organize your documents, questionnaire runs, and exports into separate compliance workspaces."
                        action={
                            <Button onClick={() => setIsOpen(true)}>
                                <Plus className="mr-2 h-4 w-4" /> Create First Project
                            </Button>
                        }
                    />
                    <div className="max-w-lg mx-auto rounded-lg border bg-muted/30 p-5 space-y-3">
                        <h4 className="text-sm font-semibold text-foreground">Quick-start guide</h4>
                        <ol className="space-y-2 text-sm text-muted-foreground list-decimal list-inside">
                            <li>Create a project (e.g. &quot;SCA Bid — PS 182 Modernization&quot;)</li>
                            <li>Upload supporting documents like safety manuals and insurance certs</li>
                            <li>Run a questionnaire analysis to generate cited answers</li>
                            <li>Review low-confidence answers and export the final Excel</li>
                        </ol>
                    </div>
                </div>
            )}
        </div>
    );
}
