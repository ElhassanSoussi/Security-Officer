"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Upload, Loader2, CheckCircle, AlertCircle } from "lucide-react";
import { ApiClient } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";
import { useToast } from "@/components/ui/toaster";

interface UploadDialogProps {
    label: string;
    orgId: string;
    projectId?: string;
    scope: "LOCKER" | "PROJECT" | "NYC_GLOBAL";
    onSuccess?: () => void;
}

export function UploadDialog({ label, orgId, projectId, scope, onSuccess }: UploadDialogProps) {
    const [open, setOpen] = useState(false);
    const [file, setFile] = useState<File | null>(null);
    const [uploading, setUploading] = useState(false);
    const [status, setStatus] = useState<"idle" | "success" | "error">("idle");
    const [errorMsg, setErrorMsg] = useState("");
    const { toast } = useToast();

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setStatus("idle");
            setErrorMsg("");
        }
    };

    const handleUpload = async () => {
        if (!file) return;

        setUploading(true);
        setStatus("idle");

        try {
            const supabase = createClient();
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            await ApiClient.uploadDocument(file, orgId, projectId, scope, token);
            setStatus("success");
            setFile(null);
            toast({ title: "Upload Complete", description: `${file.name} uploaded successfully.`, variant: "success" });
            
            // Phase 26 onboarding: completing step 1 (upload document) advances to step 2
            try {
                if (token) {
                    const st = await ApiClient.getOnboardingState(token);
                    if (!st.onboarding_completed && st.onboarding_step === 1) {
                        await ApiClient.patchOnboardingState({ onboarding_step: 2 }, token);
                    }
                }
            } catch {
                // ignore onboarding errors
            }
            
            setTimeout(() => {
                setOpen(false);
                setStatus("idle");
                if (onSuccess) onSuccess();
            }, 1500);
        } catch (e: any) {
            console.error(e);
            setStatus("error");
            const msg = e.message || "Upload failed";
            setErrorMsg(msg);
            toast({ title: "Upload Failed", description: msg, variant: "destructive" });
        } finally {
            setUploading(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button size="sm" variant="outline">
                    <Upload className="mr-2 h-4 w-4" /> {label}
                </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <DialogTitle>Upload Document</DialogTitle>
                    <DialogDescription>
                        Add a file to the <strong>{scope === "PROJECT" ? "Project Workspace" : "Organization Vault"}</strong>.
                        Supported formats: PDF, DOCX, TXT.
                    </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                    <div className="grid w-full max-w-sm items-center gap-1.5">
                        <Label htmlFor="doc-upload">File</Label>
                        <Input id="doc-upload" type="file" accept=".pdf,.docx,.txt" onChange={handleFileChange} disabled={uploading} />
                    </div>

                    {status === "error" && (
                        <div className="flex items-center text-sm text-red-600 bg-red-50 p-2 rounded">
                            <AlertCircle className="mr-2 h-4 w-4" />
                            {errorMsg}
                        </div>
                    )}

                    {status === "success" && (
                        <div className="flex items-center text-sm text-green-600 bg-green-50 p-2 rounded">
                            <CheckCircle className="mr-2 h-4 w-4" />
                            Upload Complete!
                        </div>
                    )}
                </div>
                <DialogFooter>
                    <Button type="submit" onClick={handleUpload} disabled={!file || uploading || status === "success"}>
                        {uploading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        {uploading ? "Uploading..." : "Upload"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
