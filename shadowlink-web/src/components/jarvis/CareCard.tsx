import React, { useState } from "react";
import { jarvisApi, type ActionResult, type ProactiveMessage } from "@/services/jarvisApi";

type CareFeedback = "helpful" | "too_frequent" | "not_needed" | "snooze" | "handled";

interface Props {
  action?: ActionResult;
  message?: ProactiveMessage;
  state?: string;
  error?: string;
  onFeedback: (feedback: CareFeedback, stateLabel: string) => void;
  submitFeedback?: boolean;
}

function text(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

export const CareCard: React.FC<Props> = ({ action, message, state, error, onFeedback, submitFeedback = true }) => {
  const [submitting, setSubmitting] = useState<CareFeedback | null>(null);
  const args = action?.arguments ?? {};
  const proactiveId = text(args.proactive_message_id, message?.id ?? "");
  const content = text(args.suggested_action, message?.content ?? action?.description ?? "Mira 关怀提醒");
  const risk = text(args.risk_level, message?.priority === "high" ? "high" : "medium");
  const signals = Array.isArray(args.signals) ? args.signals.map(String) : [];

  const send = async (feedback: CareFeedback, stateLabel: string) => {
    onFeedback(feedback, stateLabel);
    if (!proactiveId || !submitFeedback) return;
    setSubmitting(feedback);
    try {
      await jarvisApi.sendCareFeedback(proactiveId, { feedback, snooze_minutes: feedback === "snooze" ? 120 : undefined });
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <div className="w-full rounded-2xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-900">
      <div className="text-sm font-semibold">Mira 关怀卡片</div>
      <div className="mt-1 whitespace-pre-wrap leading-relaxed">{content}</div>
      <div className="mt-2 text-[11px] opacity-80">风险等级：{risk}；不会做医疗诊断，高风险只提示安全求助。</div>
      {signals.length > 0 ? <div className="mt-1 text-[11px] opacity-80">识别信号：{signals.join("、")}</div> : null}
      {proactiveId ? <div className="mt-1 text-[10px] opacity-70">消息 ID：{proactiveId}</div> : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <button disabled={submitting !== null} className="rounded-lg bg-white px-3 py-1.5 text-xs font-medium shadow-sm hover:bg-rose-100" onClick={() => send("helpful", "已记录有帮助")}>有帮助</button>
        <button disabled={submitting !== null} className="rounded-lg bg-white px-3 py-1.5 text-xs font-medium shadow-sm hover:bg-rose-100" onClick={() => send("handled", "已标记处理")}>我已处理</button>
        <button disabled={submitting !== null} className="rounded-lg bg-white px-3 py-1.5 text-xs font-medium shadow-sm hover:bg-rose-100" onClick={() => send("snooze", "会稍后提醒")}>稍后提醒</button>
        <button disabled={submitting !== null} className="rounded-lg bg-white px-3 py-1.5 text-xs font-medium shadow-sm hover:bg-rose-100" onClick={() => send("too_frequent", "已降频")}>太频繁</button>
        <button disabled={submitting !== null} className="rounded-lg border border-white/70 px-3 py-1.5 text-xs font-medium hover:bg-white/60" onClick={() => send("not_needed", "不再需要此类")}>不需要这类</button>
        {state ? <span className="self-center text-[11px] font-medium">{state}</span> : null}
      </div>
      {error ? <div className="mt-2 text-red-600">{error}</div> : null}
    </div>
  );
};
