import * as React from "react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export default function SectionCard({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <Card className={cn("p-0 overflow-hidden", className)}>
      {children}
    </Card>
  );
}
