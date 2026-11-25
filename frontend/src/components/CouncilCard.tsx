"use client";

import { Bot, Compass, ChevronDown } from "lucide-react";
import { useState } from "react";

interface CouncilCardProps {
  toolName: string;
  data: {
    query?: string;
    topic?: string;
    aspect?: string;
    claude?: { response?: string; available?: boolean; error?: string };
    deepseek?: { response?: string; available?: boolean; error?: string };
    round_1?: { claude?: string; deepseek?: string };
    round_2_cross_examination?: {
      deepseek_critique_of_claude?: string;
      claude_critique_of_deepseek?: string;
    };
    round_2?: { claude_rebuttal?: string; deepseek_rebuttal?: string };
  };
}

export function CouncilCard({ toolName, data }: CouncilCardProps) {
  const [showRound2, setShowRound2] = useState(false);

  const claudeText = data.claude?.response || data.round_1?.claude || "";
  const deepseekText = data.deepseek?.response || data.round_1?.deepseek || "";
  const hasRound2 = Boolean(data.round_2_cross_examination || data.round_2);

  const title =
    toolName === "ai_council_crosscheck"
      ? `AI Council Cross-Check (${data.aspect || "all"})`
      : toolName === "ai_council_debate"
        ? `AI Council Debate: ${data.topic || ""}`
        : "AI Travel Council";

  return (
    <div className="my-2 rounded-2xl border border-slate-800 bg-slate-950/80 p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Compass className="w-4 h-4 text-violet-400" />
          <span className="text-sm font-semibold text-slate-100">{title}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="rounded-xl border border-violet-900/50 bg-violet-950/20 p-3 space-y-1.5">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-violet-300">
            <Bot className="w-3.5 h-3.5" /> Claude (Culture & Experience)
          </div>
          <p className="text-xs text-slate-300 whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto">
            {claudeText || data.claude?.error || "No response"}
          </p>
        </div>

        <div className="rounded-xl border border-cyan-900/50 bg-cyan-950/20 p-3 space-y-1.5">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-cyan-300">
            <Bot className="w-3.5 h-3.5" /> DeepSeek (Transit & Logistics)
          </div>
          <p className="text-xs text-slate-300 whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto">
            {deepseekText || data.deepseek?.error || "No response"}
          </p>
        </div>
      </div>

      {hasRound2 && (
        <div>
          <button
            type="button"
            onClick={() => setShowRound2((v) => !v)}
            className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 cursor-pointer"
          >
            <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showRound2 ? "rotate-180" : ""}`} />
            {showRound2 ? "Hide" : "Show"} Round 2 Cross-Examination
          </button>
          {showRound2 && (
            <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-3">
                <div className="text-[11px] font-semibold text-violet-300 mb-1">Claude Rebuttal / Critique</div>
                <p className="text-xs text-slate-300 whitespace-pre-wrap max-h-52 overflow-y-auto">
                  {data.round_2_cross_examination?.claude_critique_of_deepseek || data.round_2?.claude_rebuttal}
                </p>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-3">
                <div className="text-[11px] font-semibold text-cyan-300 mb-1">DeepSeek Rebuttal / Critique</div>
                <p className="text-xs text-slate-300 whitespace-pre-wrap max-h-52 overflow-y-auto">
                  {data.round_2_cross_examination?.deepseek_critique_of_claude || data.round_2?.deepseek_rebuttal}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
