"use client";

import { useEffect, useRef, useState } from "react";
import { ApiClient, AccountProfile } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toaster";
import { User, Camera, Save, Loader2 } from "lucide-react";

export default function ProfilePage() {
    const [profile, setProfile] = useState<AccountProfile | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [uploadingAvatar, setUploadingAvatar] = useState(false);

    const [displayName, setDisplayName] = useState("");
    const [publicEmail, setPublicEmail] = useState("");

    // Track initial values for dirty-state detection
    const [initialName, setInitialName] = useState("");
    const [initialEmail, setInitialEmail] = useState("");

    const fileInputRef = useRef<HTMLInputElement>(null);
    const { toast } = useToast();
    const router = useRouter();
    const supabase = createClient();

    const isDirty = displayName !== initialName || publicEmail !== initialEmail;

    useEffect(() => {
        async function load() {
            try {
                const { data: { session } } = await supabase.auth.getSession();
                if (!session) {
                    router.push("/login");
                    return;
                }
                const token = session.access_token;
                const data = await ApiClient.getAccountProfile(token);
                setProfile(data);
                setDisplayName(data.display_name || "");
                setPublicEmail(data.public_email || "");
                setInitialName(data.display_name || "");
                setInitialEmail(data.public_email || "");
            } catch (e: any) {
                toast({ title: "Failed to load profile", description: e.message, variant: "destructive" });
            } finally {
                setLoading(false);
            }
        }
        load();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleSave = async () => {
        setSaving(true);
        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            const updated = await ApiClient.patchAccountProfile({
                display_name: displayName || undefined,
                public_email: publicEmail || undefined,
            }, token);
            setProfile(updated);
            setInitialName(updated.display_name || "");
            setInitialEmail(updated.public_email || "");
            toast({ title: "Profile saved", variant: "success" });
        } catch (e: any) {
            toast({ title: "Save failed", description: e.message, variant: "destructive" });
        } finally {
            setSaving(false);
        }
    };

    const handleAvatarClick = () => {
        fileInputRef.current?.click();
    };

    const handleAvatarChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        if (!file.type.startsWith("image/")) {
            toast({ title: "Invalid file", description: "Please select an image file.", variant: "destructive" });
            return;
        }
        if (file.size > 2 * 1024 * 1024) {
            toast({ title: "File too large", description: "Maximum size is 2 MB.", variant: "destructive" });
            return;
        }

        setUploadingAvatar(true);
        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            const updated = await ApiClient.uploadAvatar(file, token);
            setProfile(updated);
            toast({ title: "Avatar updated", variant: "success" });
        } catch (e: any) {
            toast({ title: "Upload failed", description: e.message, variant: "destructive" });
        } finally {
            setUploadingAvatar(false);
            if (fileInputRef.current) fileInputRef.current.value = "";
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[40vh]">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="space-y-6 max-w-3xl">
            {/* Two-column: Avatar left, Info right */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Profile</CardTitle>
                    <CardDescription>Your personal information and avatar.</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="flex flex-col sm:flex-row gap-8">
                        {/* Avatar column */}
                        <div className="flex flex-col items-center gap-3 sm:pt-1">
                            <button
                                onClick={handleAvatarClick}
                                disabled={uploadingAvatar}
                                className="relative group flex-shrink-0"
                                type="button"
                            >
                                {profile?.avatar_url ? (
                                    <img
                                        src={profile.avatar_url}
                                        alt="Avatar"
                                        className="h-24 w-24 rounded-full object-cover border-2 border-border"
                                    />
                                ) : (
                                    <div className="h-24 w-24 rounded-full bg-muted flex items-center justify-center border-2 border-border">
                                        <User className="h-10 w-10 text-muted-foreground" />
                                    </div>
                                )}
                                <div className="absolute inset-0 rounded-full bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                                    {uploadingAvatar ? (
                                        <Loader2 className="h-5 w-5 text-white animate-spin" />
                                    ) : (
                                        <Camera className="h-5 w-5 text-white" />
                                    )}
                                </div>
                            </button>
                            <p className="text-[11px] text-muted-foreground text-center leading-tight">
                                JPG, PNG, WebP, GIF<br />Max 2 MB
                            </p>
                            <input
                                ref={fileInputRef}
                                type="file"
                                accept="image/jpeg,image/png,image/webp,image/gif"
                                className="hidden"
                                onChange={handleAvatarChange}
                                aria-label="Upload avatar image"
                            />
                        </div>

                        {/* Form column */}
                        <div className="flex-1 space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="displayName">Display Name</Label>
                                <Input
                                    id="displayName"
                                    placeholder="Your name"
                                    value={displayName}
                                    onChange={(e) => setDisplayName(e.target.value)}
                                    maxLength={100}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="publicEmail">
                                    Public Email <span className="text-muted-foreground font-normal">(optional)</span>
                                </Label>
                                <Input
                                    id="publicEmail"
                                    type="email"
                                    placeholder="public@example.com"
                                    value={publicEmail}
                                    onChange={(e) => setPublicEmail(e.target.value)}
                                    maxLength={254}
                                />
                                <p className="text-xs text-muted-foreground">
                                    If set, this email may be visible to other members of your organization.
                                </p>
                            </div>
                            <div className="space-y-2">
                                <Label>Account Email</Label>
                                <Input value={profile?.email || "—"} disabled />
                            </div>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Save — only enabled when dirty */}
            <div className="flex justify-end">
                <Button onClick={handleSave} disabled={saving || !isDirty} size="sm" className="gap-2">
                    {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                    Save Changes
                </Button>
            </div>
        </div>
    );
}
