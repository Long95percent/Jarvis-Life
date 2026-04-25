import React, { useEffect, useRef, useState } from "react";
import { useJarvisStore } from "@/stores/jarvisStore";
import { jarvisApi, type ActionResult, type EscalationHint } from "@/services/jarvisApi";

interface Props {
  agentId: string;
  sessionId: string;
  onClose: () => void;
}

type ConfirmationState = "confirmed" | "cancelled";

const SEVERITY_STYLES: Record<
  EscalationHint["severity"],
  { bg: string; border: string; text: string; label: string }
> = {
  info: { bg: "#eff6ff", border: "#bfdbfe", text: "#1d4ed8", label: "建议" },
  suggest: { bg: "#fffbeb", border: "#fcd34d", text: "#b45309", label: "提醒" },
  urgent: { bg: "#fef2f2", border: "#fca5a5", text: "#b91c1c", label: "紧急" },
};

function actionKey(action: ActionResult, index: number): string {
  return action.confirmation_id ?? `${action.type}-${action.title ?? ""}-${action.start ?? ""}-${index}`;
}

function toText(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function formatDateTime(value: string): string {
  if (!value) return "未设置时间";
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatEndTime(value: string): string {
  if (!value) return "";
  return new Date(value).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function isHttpStatus(error: unknown, status: number): boolean {
  return typeof error === "object" && error !== null && "status" in error && (error as { status?: number }).status === status;
}

export const AgentChatPanel: React.FC<Props> = ({ agentId, sessionId, onClose }) => {
  const agents = useJarvisStore((s) => s.agents);
  const chatHistory = useJarvisStore((s) => s.chatHistory);
  const sendMessage = useJarvisStore((s) => s.sendMessage);
  const startRoundtable = useJarvisStore((s) => s.startRoundtable);
  const loadChatHistory = useJarvisStore((s) => s.loadChatHistory);
  const clearChatHistoryStore = useJarvisStore((s) => s.clearChatHistory);

  const agent = agents.find((item) => item.id === agentId);
  const history = chatHistory[agentId] ?? [];

  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [escalation, setEscalation] = useState<EscalationHint | null>(null);  const [confirmations, setConfirmations] = useState<Record<string, ConfirmationState>>({});
  const [confirmationErrors, setConfirmationErrors] = useState<Record<string, string>>({});
  const [confirmingKey, setConfirmingKey] = useState<string | null>(null);

  const escalationTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastUserMessageRef = useRef("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history.length, sending]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoadingHistory(true);
      try {
        await loadChatHistory(agentId);
      } finally {
        if (!cancelled) setLoadingHistory(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [agentId, loadChatHistory]);

  useEffect(() => {
    return () => {
      if (escalationTimerRef.current) clearInterval(escalationTimerRef.current);
    };
  }, []);

  const clearEscalationTimer = () => {
    if (escalationTimerRef.current) {
      clearInterval(escalationTimerRef.current);
      escalationTimerRef.current = null;
    }
  };

  const handleCancelEscalation = () => {
    clearEscalationTimer();
    setEscalation(null);  };

  const launchEscalation = () => {
    if (!escalation) return;
    const scenarioId = escalation.scenario_id;
    const message = lastUserMessageRef.current;
    handleCancelEscalation();
    startRoundtable(scenarioId, message);
  };
  const handleSend = async () => {
    const message = input.trim();
    if (!message || sending) return;
    setSending(true);
    setInput("");
    handleCancelEscalation();
    lastUserMessageRef.current = message;
    try {
      const hint = await sendMessage(agentId, message, sessionId);
      if (hint) {
        setEscalation(hint);      }
    } finally {
      setSending(false);
    }
  };
  const confirmCalendarAction = async (action: ActionResult, index: number) => {
    const key = actionKey(action, index);
    const args = action.arguments ?? {};
    const title = toText(args.title, action.title ?? "").trim();
    const start = toText(args.start, action.start ?? "");
    const end = toText(args.end, action.end ?? "");
    if (!title || !start || !end) {
      setConfirmationErrors((prev) => ({ ...prev, [key]: "日程缺少标题、开始时间或结束时间，暂时无法写入。" }));
      return;
    }

    setConfirmingKey(key);
    setConfirmationErrors((prev) => ({ ...prev, [key]: "" }));
    try {
      const pendingId = action.pending_action_id ?? action.confirmation_id;
      if (!pendingId) {
        throw new Error("缺少待确认日程 ID，请重新让秘书生成日程卡片。");
      }
      const calendarPayload = {
        ...args,
        title,
        start,
        end,
        stress_weight: Number(args.stress_weight ?? 1),
        location: toText(args.location, "") || null,
        notes: toText(args.notes, "") || null,
        created_reason: toText(args.created_reason, "用户确认了 Agent 建议的日程安排"),
        route_required: Boolean(args.route_required ?? false),
      };

      try {
        await jarvisApi.confirmPendingAction(String(pendingId), {
          title,
          arguments: calendarPayload,
        });
      } catch (error) {
        if (!isHttpStatus(error, 404)) throw error;
        await jarvisApi.addCalendarEvent({
          ...calendarPayload,
          source: "agent_card_fallback",
          status: "confirmed",
        });
      }

      setConfirmations((prev) => ({ ...prev, [key]: "confirmed" }));
      useJarvisStore.getState().refreshAll().catch(() => undefined);
    } catch (error) {
      setConfirmationErrors((prev) => ({
        ...prev,
        [key]: error instanceof Error ? error.message : "确认写入失败，请稍后重试。",
      }));
    } finally {
      setConfirmingKey(null);
    }
  };
  const renderAction = (action: ActionResult, index: number) => {
    const key = actionKey(action, index);
    const state = confirmations[key];
    const error = confirmationErrors[key];
    const args = action.arguments ?? {};
    const title = toText(args.title, action.title ?? "待确认日程");
    const start = toText(args.start, action.start ?? "");
    const end = toText(args.end, action.end ?? "");

    if (action.pending_confirmation && action.type === "calendar.add") {
      return (
        <div key={key} className="w-full rounded-2xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          <div className="text-sm font-semibold">待确认日程</div>
          <div className="mt-1 font-medium">{title}</div>
          <div className="mt-1 text-amber-700">
            {formatDateTime(start)}{end ? ` - ${formatEndTime(end)}` : ""}
          </div>
          {state ? (
            <div className="mt-2 font-medium">{state === "confirmed" ? "已写入日程" : "已取消写入"}</div>
          ) : (
            <div className="mt-3 flex gap-2">
              <button
                className="px-3 py-1.5 rounded-lg bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-60"
                disabled={confirmingKey === key}
                onClick={() => confirmCalendarAction(action, index)}
              >
                {confirmingKey === key ? "写入中…" : "确认写入日程"}
              </button>
              <button
                className="px-3 py-1.5 rounded-lg border border-amber-200 bg-white text-amber-700 hover:bg-amber-100"
                onClick={async () => { const pendingId = action.pending_action_id ?? action.confirmation_id; if (pendingId) await jarvisApi.cancelPendingAction(String(pendingId)); setConfirmations((prev) => ({ ...prev, [key]: "cancelled" })); }}
              >
                取消
              </button>
            </div>
          )}
          {error ? <div className="mt-2 text-red-600">{error}</div> : null}
        </div>
      );
    }

    return (
      <span
        key={key}
        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-medium"
        style={{
          backgroundColor: action.ok ? "#dcfce7" : "#fee2e2",
          color: action.ok ? "#15803d" : "#b91c1c",
          border: `1px solid ${action.ok ? "#86efac" : "#fca5a5"}`,
        }}
        title={action.error ?? ""}
      >
        {action.ok ? `已处理 ${action.type}` : `${action.type} 失败`}
      </span>
    );
  };

  if (!agent) {
    return <div className="h-full flex items-center justify-center text-sm text-gray-400">Agent not found</div>;
  }

  const severityStyle = escalation ? SEVERITY_STYLES[escalation.severity] : null;

  return (
    <div className="h-full flex flex-col bg-white">
      <div
        className="flex items-center justify-between px-5 py-3 border-b border-gray-200"
        style={{ background: `linear-gradient(90deg, color-mix(in srgb, ${agent.color} 14%, white), transparent)` }}
      >
        <div className="flex items-center gap-3">
          <span className="w-10 h-10 rounded-full flex items-center justify-center text-xl" style={{ backgroundColor: `color-mix(in srgb, ${agent.color} 22%, white)` }}>
            {agent.icon}
          </span>
          <div>
            <div className="font-semibold text-gray-800" style={{ color: agent.color }}>{agent.name}</div>
            <div className="text-[11px] text-gray-500">{agent.role}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              if (confirm(`清除和 ${agent.name} 的全部聊天记录？`)) clearChatHistoryStore(agentId);
            }}
            className="text-xs px-2.5 py-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors"
          >
            清空
          </button>
          <button onClick={onClose} className="text-sm px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors">
            返回
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
        {loadingHistory && <p className="text-center text-xs text-gray-400 mt-4">加载历史中…</p>}
        {!loadingHistory && history.length === 0 && <p className="text-center text-sm text-gray-400 mt-8">和 {agent.name} 开始对话…</p>}
        {history.map((message, index) => (
          <div key={index} className={`flex flex-col gap-1 ${message.role === "user" ? "items-end" : "items-start"}`}>
            <div
              className="max-w-[75%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap"
              style={
                message.role === "user"
                  ? { backgroundColor: agent.color, color: "white", borderBottomRightRadius: 4 }
                  : {
                      backgroundColor: `color-mix(in srgb, ${agent.color} 8%, white)`,
                      border: `1px solid color-mix(in srgb, ${agent.color} 20%, transparent)`,
                      color: "#1f2937",
                      borderBottomLeftRadius: 4,
                    }
              }
            >
              {message.content}
            </div>
            {message.role === "agent" && message.actions && message.actions.length > 0 && (
              <div className="flex flex-wrap gap-1.5 max-w-[75%]">
                {message.actions.map((action, actionIndex) => renderAction(action, actionIndex))}
              </div>
            )}
          </div>
        ))}
        {sending && (
          <div className="flex justify-start">
            <div className="px-4 py-2.5 rounded-2xl text-sm flex items-center gap-1" style={{ backgroundColor: `color-mix(in srgb, ${agent.color} 8%, white)`, border: `1px solid color-mix(in srgb, ${agent.color} 20%, transparent)` }}>
              <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "300ms" }} />
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {escalation && severityStyle && (
        <div className="mx-5 mb-3 rounded-2xl border p-3 text-sm shadow-sm" style={{ backgroundColor: severityStyle.bg, borderColor: severityStyle.border, color: severityStyle.text }}>
          <div className="font-semibold">建议进入 Brainstorm / 团队协作模式</div>
          <div className="mt-1 text-xs opacity-90">{escalation.reason}</div>
          <div className="mt-3 flex items-center gap-2">
            <button
              onClick={launchEscalation}
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-white"
              style={{ backgroundColor: severityStyle.text }}
            >
              进入协作模式
            </button>
            <button onClick={handleCancelEscalation} className="px-3 py-1.5 rounded-lg text-xs font-medium border bg-white hover:bg-gray-50" style={{ borderColor: severityStyle.border, color: severityStyle.text }}>
              暂不进入
            </button>
          </div>
        </div>
      )}
      <div className="px-5 py-4 border-t border-gray-200 bg-white flex gap-3">
        <input
          className="flex-1 rounded-xl border border-gray-200 px-4 py-2.5 text-sm focus:outline-none focus:ring-2"
          placeholder={`发消息给 ${agent.name}…`}
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && !event.shiftKey && handleSend()}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || sending}
          className="px-4 py-2.5 rounded-xl text-white text-sm font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
          style={{ backgroundColor: agent.color }}
        >
          发送
        </button>
      </div>
    </div>
  );
};





