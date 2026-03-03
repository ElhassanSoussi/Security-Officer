"use client";

import { useEffect, useState } from "react";
import { ApiClient } from "@/lib/api";
import { useTheme } from "@/components/ThemeProvider";
import { createClient } from "@/utils/supabase/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toaster";
import { Sun, Moon, Monitor, Save, Loader2, Check } from "lucide-react";

export default function AppearancePage() {
    const { theme, setTheme } = useTheme();
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);
    const { toast } = useToast();
    const supabase = createClient();

    const themeOptions: { value: "light" | "dark" | "system"; label: string; icon: React.ReactNode; description: string }[] = [
        { value: "light", label: "Light", icon: <Sun className="h-5 w-5" />, description: "Always use light mode" },
        { value: "dark", label: "Dark", icon: <Moon className="h-5 w-5" />, description: "Always use dark mode" },
        { value: "system", label: "System", icon: <Monitor className="h-5 w-5" />, description: "Follow your device settings" },
    ];

    const handleThemeChange = (t: "light" | "dark" | "system") => {
        setTheme(t);
        setSaved(false);
    };

    const handleSave = async () => {
        setSaving(true);
        try {
            const { data: { session } } = await supabase.auth.getSession();
            const token = session?.access_token;
            await ApiClient.patchAccountProfile({ theme_preference: theme }, token);
            setSaved(true);
            toast({ title: "Appearance saved", variant: "success" });
        } catch (e: any) {
            toast({ title: "Save failed", description: e.message, variant: "destructive" });
        } finally {
            setSaving(false);
        }
    };

    // Load saved preference on mount
    useEffect(() => {
        async function load() {
            try {
                const { data: { session } } = await supabase.auth.getSession();
                if (!session) return;
                const data = await ApiClient.getAccountProfile(session.access_token);
                if (data.theme_preference) {
                    setTheme(data.theme_preference);
                }
            } catch {
                // Use localStorage fallback — already handled by ThemeProvider
            }
        }
        load();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return (
        <div className="space-y-6 max-w-2xl">
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Theme</CardTitle>
                    <CardDescription>Choose how the application looks for you. Changes apply immediately.</CardDescription>
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

            <div className="flex justify-end">
                <Button onClick={handleSave} disabled={saving} size="sm" className="gap-2">
                    {saving ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                    ) : saved ? (
                        <Check className="h-4 w-4" />
                    ) : (
                        <Save className="h-4 w-4" />
                    )}
                    {saved ? "Saved" : "Save Preference"}
                </Button>
            </div>
        </div>
    );
}
