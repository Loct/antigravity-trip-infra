"use client";

import { CheckCircle2, ShieldAlert, XCircle } from "lucide-react";
import { useState } from "react";

interface ApprovalCardProps {
  toolCallId: string;
  toolName: string;
  args: Record<string, unknown>;
  state: "partial-call" | "call" | "result";
  result?: unknown;
  onApprove: (toolCallId: string, toolName: string, args: Record<string, unknown>) => Promise<void>;
  onDecline: (toolCallId: string) => void;
}

export function ApprovalCard({
  toolCallId,
  toolName,
  args,
  state,
  result,
  onApprove,
  onDecline,
}: ApprovalCardProps) {
  const [submitting, setSubmitting] = useState(false);

  const handleApprove = async () => {
    setSubmitting(true);
    try {
      await onApprove(toolCallId, toolName, args);
    } finally {
      setSubmitting(false);
    }
  };

  const resultObj = result && typeof result === "object" ? (result as Record<string, unknown>) : null;
  const isCancelled = Boolean(resultObj?.cancelled);

  return (
    <div className="my-2 rounded-2xl border border-amber-700/60 bg-amber-950/25 p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-amber-400" />
          <span className="text-sm font-semibold text-amber-200">
            Trip Mutation Approval Required: <code className="text-amber-100">{toolName}</code>
          </span>
        </div>
        {state === "result" && (
          <span
            className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${
              isCancelled
                ? "bg-slate-800 text-slate-300"
                : "bg-emerald-950 text-emerald-300 border border-emerald-800"
            }`}
          >
            {isCancelled ? (
              <>
                <XCircle className="w-3.5 h-3.5" /> Declined
              </>
            ) : (
              <>
                <CheckCircle2 className="w-3.5 h-3.5" /> Applied
              </>
            )}
          </span>
        )}
      </div>

      <pre className="text-xs text-slate-200 bg-slate-950/80 border border-slate-800 rounded-xl p-3 overflow-x-auto">
        {JSON.stringify(args, null, 2)}
      </pre>

      {state === "call" && (
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={submitting}
            onClick={handleApprove}
            className="inline-flex items-center gap-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg transition cursor-pointer"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            {submitting ? "Applying..." : "Approve & Apply to Trip"}
          </button>
          <button
            type="button"
            disabled={submitting}
            onClick={() => onDecline(toolCallId)}
            className="inline-flex items-center gap-1.5 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1.5 rounded-lg transition cursor-pointer"
          >
            <XCircle className="w-3.5 h-3.5" />
            Decline
          </button>
        </div>
      )}
    </div>
  );
}
