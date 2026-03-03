"use client";

import { useState } from "react";
import { QuestionItem } from "@/types";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Check, X, AlertTriangle, FileText, Loader2 } from "lucide-react";
import Link from "next/link";
import { ApiClient } from "@/lib/api";
import { config } from "@/lib/config";
import { SourceTransparency } from "@/components/ui/SourceTransparency";
import { AnswerStatusBadge, deriveAnswerStatus } from "@/components/ui/AnswerStatusBadge";

interface ReviewGridProps {
    items: QuestionItem[];
    onItemsChange: (items: QuestionItem[]) => void;
    uploadDocsHref?: string;
    /** When provided, accept/reject actions are persisted to backend */
    runId?: string;
    /** Auth token for backend calls */
    token?: string;
}

export function ReviewGrid({ items, onItemsChange, uploadDocsHref, runId, token }: ReviewGridProps) {
    const [savingIndex, setSavingIndex] = useState<number | null>(null);

    const handleAnswerChange = (index: number, newValue: string) => {
        const newItems = [...items];
        newItems[index].final_answer = newValue;
        newItems[index].edited_by_user = true;
        onItemsChange(newItems);
    };

    const handleAccept = async (index: number) => {
        const newItems = [...items];
        newItems[index].is_verified = true;
        newItems[index].review_status = "approved";
        onItemsChange(newItems);

        // Persist to backend if we have a run_id and audit_id
        const item = newItems[index];
        if (runId && (item as any).audit_id) {
            setSavingIndex(index);
            try {
                await ApiClient.reviewAuditEntry(runId, (item as any).audit_id, "approved", "", token);
            } catch (e) {
                console.error("Failed to persist review approval:", e);
            } finally {
                setSavingIndex(null);
            }
        }
    };

    const handleReject = async (index: number) => {
        const newItems = [...items];
        newItems[index].final_answer = "";
        newItems[index].is_verified = true;
        newItems[index].edited_by_user = true;
        newItems[index].review_status = "rejected";
        onItemsChange(newItems);

        // Persist to backend
        const item = newItems[index];
        if (runId && (item as any).audit_id) {
            setSavingIndex(index);
            try {
                await ApiClient.reviewAuditEntry(runId, (item as any).audit_id, "rejected", "", token);
            } catch (e) {
                console.error("Failed to persist review rejection:", e);
            } finally {
                setSavingIndex(null);
            }
        }
    };

    const handleReset = (index: number) => {
        const newItems = [...items];
        newItems[index].final_answer = newItems[index].ai_answer;
        newItems[index].is_verified = false;
        newItems[index].edited_by_user = false;
        newItems[index].review_status = "pending";
        onItemsChange(newItems);
    };

    const getConfidenceColor = (conf: string) => {
        switch (conf) {
            case "HIGH": return "bg-green-100 text-green-800 hover:bg-green-100";
            case "MEDIUM": return "bg-yellow-100 text-yellow-800 hover:bg-yellow-100";
            case "LOW": return "bg-red-100 text-red-800 hover:bg-red-100";
            default: return "bg-gray-100 text-gray-800";
        }
    };

    return (
        <div className="border rounded-md">
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead className="w-[300px]">Question</TableHead>
                        <TableHead className="w-[400px]">Answer (Editable)</TableHead>
                        <TableHead className="w-[100px]">Confidence</TableHead>
                        <TableHead className="w-[150px]">Source</TableHead>
                        <TableHead className="w-[150px] text-right">Actions</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {(items || []).map((item, index) => (
                        <TableRow key={`${item.sheet_name}-${item.cell_coordinate}`}>
                            <TableCell className="align-top">
                                <p className="font-medium text-sm">{item.question}</p>
                                <p className="text-xs text-slate-500 mt-1">{item.sheet_name}!{item.cell_coordinate}</p>
                                <div className="mt-1.5">
                                    <AnswerStatusBadge status={deriveAnswerStatus(item)} />
                                </div>
                            </TableCell>
                            <TableCell className="align-top">
                                {item.status === "needs_info" && (
                                    <div className="mb-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                                        <div className="font-medium">Missing source context</div>
                                        <div className="mt-0.5 text-amber-700">
                                            {item.status_reason || "Upload supporting documents so the AI can answer with citations."}
                                        </div>
                                        {uploadDocsHref && (
                                            <div className="mt-2">
                                                <Link href={uploadDocsHref}>
                                                    <Button size="sm" variant="outline" className="h-7">
                                                        Upload supporting docs
                                                    </Button>
                                                </Link>
                                            </div>
                                        )}
                                    </div>
                                )}
                                {item.status === "ai_unavailable" && (
                                    <div className="mb-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
                                        <div className="font-medium">AI unavailable</div>
                                        <div className="mt-0.5 text-red-700">
                                            {item.status_reason || "The AI service is temporarily unavailable. Try again later."}
                                        </div>
                                    </div>
                                )}
                                <Textarea
                                    value={item.final_answer}
                                    onChange={(e) => handleAnswerChange(index, e.target.value)}
                                    className={`min-h-[100px] ${item.edited_by_user ? 'border-blue-500 bg-blue-50/10' : ''}`}
                                />
                                {item.edited_by_user && (
                                    <div className="flex items-center mt-1 text-xs text-blue-600">
                                        <div className="w-2 h-2 rounded-full bg-blue-500 mr-1" />
                                        Edited by you
                                    </div>
                                )}
                                {/* Source excerpt display */}
                                {item.source_excerpt && (
                                    <div className="mt-2 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-800">
                                        <div className="font-medium mb-1">Source excerpt</div>
                                        <div className="text-blue-700 whitespace-pre-wrap">{item.source_excerpt}</div>
                                    </div>
                                )}
                                {/* Source Transparency Panel */}
                                <SourceTransparency
                                    confidence={item.confidence}
                                    confidenceScore={null}
                                    sourceDocument={item.sources?.[0]}
                                    sourceExcerpt={item.source_excerpt}
                                    sourcePage={item.source_page}
                                    question={item.question}
                                />
                            </TableCell>
                            <TableCell className="align-top">
                                <Badge variant="secondary" className={getConfidenceColor(item.confidence)}>
                                    {item.confidence}
                                </Badge>
                            </TableCell>
                            <TableCell className="align-top text-xs text-slate-600">
                                {item.sources && item.sources.length > 0 ? (
                                    <div className="flex items-center gap-1" title={item.sources[0]}>
                                        <FileText className="w-3 h-3" />
                                        {item.source_id ? (
                                            <a
                                                href={`${config.apiUrl}/documents/${item.source_id}/view#page=${item.source_page || 1}`}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="truncate max-w-[120px] text-blue-600 hover:underline cursor-pointer"
                                            >
                                                {item.sources[0]} {item.source_page ? `(p. ${item.source_page})` : ''}
                                            </a>
                                        ) : (
                                            <span className="truncate max-w-[120px]">{item.sources[0]}</span>
                                        )}
                                    </div>
                                ) : (
                                    <span className="text-slate-400 italic">No source</span>
                                )}
                            </TableCell>
                            <TableCell className="align-top text-right space-y-2">
                                {savingIndex === index ? (
                                    <div className="flex justify-end">
                                        <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
                                    </div>
                                ) : item.review_status === "approved" ? (
                                    <div className="flex flex-col items-end gap-1">
                                        <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                                            <Check className="w-3 h-3 mr-1" /> Approved
                                        </Badge>
                                        <Button variant="ghost" size="sm" className="h-6 text-xs px-2 text-slate-400 hover:text-slate-600" onClick={() => handleReset(index)}>
                                            Reset
                                        </Button>
                                    </div>
                                ) : item.review_status === "rejected" ? (
                                    <div className="flex flex-col items-end gap-1">
                                        <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
                                            <X className="w-3 h-3 mr-1" /> Rejected
                                        </Badge>
                                        <Button variant="ghost" size="sm" className="h-6 text-xs px-2 text-slate-400 hover:text-slate-600" onClick={() => handleReset(index)}>
                                            Reset
                                        </Button>
                                    </div>
                                ) : (
                                    <div className="flex justify-end gap-2">
                                        <Button size="sm" variant="outline" className="h-8 w-8 p-0 text-red-600 hover:text-red-700 hover:bg-red-50" onClick={() => handleReject(index)} title="Reject / Clear">
                                            <X className="h-4 w-4" />
                                        </Button>
                                        <Button size="sm" variant="outline" className="h-8 w-8 p-0 text-green-600 hover:text-green-700 hover:bg-green-50" onClick={() => handleAccept(index)} title="Approve">
                                            <Check className="h-4 w-4" />
                                        </Button>
                                    </div>
                                )}

                                {item.confidence === 'LOW' && !item.is_verified && !item.edited_by_user && (
                                    <div className="flex items-center justify-end text-xs text-amber-600 font-medium mt-2">
                                        <AlertTriangle className="w-3 h-3 mr-1" />
                                        Review needed
                                    </div>
                                )}
                            </TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </div>
    );
}
