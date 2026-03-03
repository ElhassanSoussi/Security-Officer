"use client";

import { useEffect, useRef, useState } from "react";
import { ApiClient, AccountProfile } from "@/lib/api";
import { useTheme } from "@/components/ThemeProvider";
import { createClient } from "@/utils/supabase/client";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toaster";
import { User, Camera, Sun, Moon, Monitor, Save, Loader2, ExternalLink } from "lucide-react";

export default function AccountSettingsPage() {
    const [profile, setProfile] = useState<AccountProfile | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [uploadingAvatar, setUploadingAvatar] = useState(false);

    const [displayName, setDisplayName] = useState("");
    const [publicEmail, setPublicEmail] = useState("");

    const fileInputRef = useRef<HTMLInputElement>(null);
    const { theme, setTheme } = useTheme();
    const { toast } = useToast();
    const router = useRouter();
    const supabase = createClient();

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
                if (data.theme_preference) {
                    setTheme(data.theme_preference);
                }
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
                theme_preference: theme,
            }, token);
            setProfile(updated);
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

    const handleThemeChange = (t: "light" | "dark" | "system") => {
        setTheme(t);
    };

    if (loading) {
        return (
            <div className="page-padding flex items-center justify-center min-h-[60vh]">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    const themeOptions: { value: "light" | "dark" | "system"; label: string; icon: React.ReactNode; description: string }[] = [
        { value: "light", label: "Light", icon: <Sun className="h-5 w-5" />, description: "Always use light mode" },
        { value: "dark", label: "Dark", icon: <Moon className="h-5 w-5" />, description: "Always use dark mode" },
        { value: "system", label: "System", icon: <Monitor className="h-5 w-5" />, description: "Follow your device settings" },
    ];

    return (
        <div className="page-padding max-w-2xl mx-auto section-gap">
            <div>
                <h1 className="text-2xl font-semibold text-foreground">Account Settings</h1>
                <p className="text-sm text-muted-foreground mt-1">Manage your profile and appearance preferences.</p>
            </div>

            {/* Profile Picture */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Profile Picture</CardTitle>
                    <CardDescription>Upload an image (JPG, PNG, WebP, GIF — max 2 MB).</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="flex items-center gap-6">
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
                                    className="h-20 w-20 rounded-full object-cover border-2 border-border"
                                />
                            ) : (
                                <div className="h-20 w-20 rounded-full bg-muted flex items-center justify-center border-2 border-border">
                                    <User className="h-8 w-8 text-muted-foreground" />
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
                        <div className="text-sm text-muted-foreground">
                            <p>Click the avatar to upload a new image.</p>
                            {profile?.email && <p className="mt-1 text-xs">{profile.email}</p>}
                        </div>
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept="image/jpeg,image/png,image/webp,image/gif"
                            className="hidden"
                            onChange={handleAvatarChange}
                        />
                    </div>
                </CardContent>
            </Card>

            {/* Name & Public Email */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Profile Information</CardTitle>
                    <CardDescription>Your display name and optional public email.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
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
                        <Label htmlFor="publicEmail">Public Email <span className="text-muted-foreground font-normal">(optional)</span></Label>
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
                </CardContent>
            </Card>

            {/* Appearance */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Appearance</CardTitle>
                    <CardDescription>Choose how the application looks for you.</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-3 gap-3">
                        {themeOptions.map((opt) => (
                            <button
                                key={opt.value}
                                type="button"
                                onClick={() => handleThemeChange(opt.value)}
                                className={`
                                    flex flex-col items-center gap-2 rounded-lg border-2 p-4 transition-colors text-sm
                                    ${theme === opt.value
                                        ? "border-primary bg-primary/5 text-foreground"
                                        : "border-border bg-card text-muted-foreground hover:border-primary/40"
                                    }
                                `}
                            >
                                {opt.icon}
                                <span className="font-medium">{opt.label}</span>
                                <span className="text-xs text-center leading-tight">{opt.description}</span>
                            </button>
                        ))}
                    </div>
                </CardContent>
            </Card>

            {/* Password & Authentication */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Password &amp; Authentication</CardTitle>
                    <CardDescription>Authentication is managed by your identity provider.</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="flex items-center gap-3 text-sm text-muted-foreground">
                        <ExternalLink className="h-4 w-4 flex-shrink-0" />
                        <span>
                            Password changes, MFA, and session management are handled through Supabase Auth.
                            Use the provider&apos;s dashboard to manage these settings.
                        </span>
                    </div>
                </CardContent>
            </Card>

            {/* Save Button */}
            <div className="flex justify-end pb-8">
                <Button onClick={handleSave} disabled={saving} className="gap-2">
                    {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                    Save Changes
                </Button>
            </div>
        </div>
    );
}
