"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Legacy redirect: /settings/account → /settings/profile
 */
export default function AccountRedirect() {
    const router = useRouter();
    useEffect(() => {
        router.replace("/settings/profile");
    }, [router]);
    return null;
}
