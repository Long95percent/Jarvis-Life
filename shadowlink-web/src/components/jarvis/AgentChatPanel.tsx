import React, { useEffect, useRef, useState } from "react";
import { useJarvisStore } from "@/stores/jarvisStore";
import { jarvisApi, type ActionResult, type BehaviorEventType, type EscalationHint } from "@/services/jarvisApi";
import { JARVIS_CONVERSATION_HISTORY_CHANGED } from "./ConversationHistoryPanel";
import { CareCard } from "./CareCard";

interface Props {
  agentId: string;
  sessionId: string;
  onClose: () => void;
}

declare global {
  interface Window {
    shadowlink?: {
      onJarvisBehaviorLifecycle?: (callback: (payload: { type: string; occurredAt: number }) => void) => void;
      removeAllListeners?: (channel: string) => void;
    };
  }
}

type ConfirmationState = "confirmed" | "cancelled";
type CareActionState = "read" | "dismissed" | "snoozed" | "helpful" | "too_frequent" | "not_needed" | "handled" | string;

interface TaskPlanFormState {
  goal?: string;
  targetDate?: string;
  weeklyDays?: string;
  dailyMinutes?: string;
  budget?: string;
  companions?: string;
  destination?: string;
  notes?: string;
}

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

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function asList(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => item !== null && typeof item === "object" && !Array.isArray(item)) : [];
}

function asStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String).filter(Boolean) : [];
}

function routingTitle(routing: Record<string, unknown>): string {
  const source = toText(routing.source_agent, "当前 Agent");
  const target = toText(routing.target_agent, "maxwell");
  const type = toText(routing.type, "schedule_intent");
  return type === "task_intent"
    ? `${source} 已把长期任务规划交给 ${target}`
    : `${source} 已把日程安排交给 ${target}`;
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
  const [confirmationMessages, setConfirmationMessages] = useState<Record<string, string>>({});
  const [careActionStates, setCareActionStates] = useState<Record<string, CareActionState>>({});
  const [taskPlanForms, setTaskPlanForms] = useState<Record<string, TaskPlanFormState>>({});
  const [confirmingKey, setConfirmingKey] = useState<string | null>(null);

  const escalationTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const openedAtRef = useRef(Date.now());
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
        await loadChatHistory(agentId, sessionId);
      } finally {
        if (!cancelled) setLoadingHistory(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [agentId, sessionId, loadChatHistory]);

  useEffect(() => {
    return () => {
      if (escalationTimerRef.current) clearInterval(escalationTimerRef.current);
    };
  }, []);

  useEffect(() => {
    openedAtRef.current = Date.now();
    let lastActivityAt = Date.now();
    let idle = false;
    const sessionStartedAt = Math.floor(openedAtRef.current / 1000);
    const recordLifecycle = async (observationType: BehaviorEventType) => {
      const durationMinutes = Math.max(0, Math.round((Date.now() - openedAtRef.current) / 60000));
      await jarvisApi.recordBehaviorEvent({ agent_id: agentId, session_id: sessionId, observation_type: observationType, duration_minutes: durationMinutes, occurred_at: Math.floor(Date.now() / 1000), session_started_at: sessionStartedAt }).catch(() => undefined);
    };
    const recordLifecycleBeacon = (observationType: BehaviorEventType) => {
      const durationMinutes = Math.max(0, Math.round((Date.now() - openedAtRef.current) / 60000));
      jarvisApi.recordBehaviorEventBeacon({ agent_id: agentId, session_id: sessionId, observation_type: observationType, duration_minutes: durationMinutes, occurred_at: Math.floor(Date.now() / 1000), session_started_at: sessionStartedAt });
    };
    const markActive = () => {
      lastActivityAt = Date.now();
      if (idle) {
        idle = false;
        void recordLifecycle("idle_end");
      }
    };

    void recordLifecycle("app_opened");
    const heartbeatTimer = window.setInterval(() => { void recordLifecycle("heartbeat"); }, 30000);
    const idleTimer = window.setInterval(() => {
      if (!idle && Date.now() - lastActivityAt > 5 * 60 * 1000) {
        idle = true;
        void recordLifecycle("idle_start");
      }
    }, 60000);
    const handleVisibilityChange = () => {
      void recordLifecycle(document.visibilityState === "hidden" ? "visibility_hidden" : "visibility_visible");
      if (document.visibilityState === "visible") markActive();
    };
    const handlePageHide = () => recordLifecycleBeacon("closed");
    const handleFocus = () => { markActive(); void recordLifecycle("app_activated"); };
    const handleBlur = () => { void recordLifecycle("visibility_hidden"); };
    const handleOnline = () => { markActive(); void recordLifecycle("resume"); };
    const handleElectronLifecycle = (payload: { type: string; occurredAt: number }) => {
      const allowed: BehaviorEventType[] = ["app_opened", "app_closed", "app_minimized", "app_activated", "app_restored"];
      if (!allowed.includes(payload.type as BehaviorEventType)) return;
      markActive();
      void jarvisApi.recordBehaviorEvent({
        agent_id: agentId,
        session_id: sessionId,
        observation_type: payload.type as BehaviorEventType,
        duration_minutes: Math.max(0, Math.round((Date.now() - openedAtRef.current) / 60000)),
        occurred_at: payload.occurredAt,
        session_started_at: sessionStartedAt,
      }).catch(() => undefined);
    };
    const activityEvents: Array<keyof WindowEventMap> = ["mousemove", "keydown", "pointerdown", "scroll"];
    activityEvents.forEach((eventName) => window.addEventListener(eventName, markActive, { passive: true }));
    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("pagehide", handlePageHide);
    window.addEventListener("focus", handleFocus);
    window.addEventListener("blur", handleBlur);
    window.addEventListener("online", handleOnline);
    window.shadowlink?.onJarvisBehaviorLifecycle?.(handleElectronLifecycle);
    return () => {
      window.clearInterval(heartbeatTimer);
      window.clearInterval(idleTimer);
      activityEvents.forEach((eventName) => window.removeEventListener(eventName, markActive));
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("pagehide", handlePageHide);
      window.removeEventListener("focus", handleFocus);
      window.removeEventListener("blur", handleBlur);
      window.removeEventListener("online", handleOnline);
      window.shadowlink?.removeAllListeners?.("jarvis-behavior-lifecycle");
      recordLifecycleBeacon("closed");
    };
  }, [agentId, sessionId]);

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
    startRoundtable(scenarioId, message, { sessionId, agentId });
  };

  const saveAndClose = async () => {
    if (agent) {
      await jarvisApi.saveConversationHistory({
        conversation_id: `private:${sessionId}:${agentId}`,
        conversation_type: "private_chat",
        title: `${agent.name} 私聊`,
        agent_id: agentId,
        session_id: sessionId,
        route_payload: { mode: "private_chat", agent_id: agentId },
      }).catch(() => undefined);
      window.dispatchEvent(new Event(JARVIS_CONVERSATION_HISTORY_CHANGED));
    }
    onClose();
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
      const latestState = useJarvisStore.getState();
      const visibleAgentId = latestState.activeAgentId || agentId;
      const updatedAgentHistory = latestState.chatHistory[visibleAgentId] ?? latestState.chatHistory[agentId] ?? [];
      const updatedLatestAgentTurn = [...updatedAgentHistory].reverse().find((item) => item.role === "agent");
      const hasUpdatedPendingAction = updatedLatestAgentTurn?.actions?.some((action) => action.pending_confirmation) ?? false;
      if (hint && !hasUpdatedPendingAction) {
        setEscalation(hint);
      }
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

  const updateTaskPlanForm = (key: string, patch: TaskPlanFormState) => {
    setTaskPlanForms((prev) => ({ ...prev, [key]: { ...(prev[key] ?? {}), ...patch } }));
  };

  const buildTaskPlanArguments = (action: ActionResult, key: string): Record<string, unknown> => {
    const args = action.arguments ?? {};
    const plan = typeof args.plan === "object" && args.plan !== null ? { ...(args.plan as Record<string, unknown>) } : { ...args };
    const form = taskPlanForms[key] ?? {};
    const userConstraints = Array.isArray(plan.user_constraints) ? [...plan.user_constraints] : [];
    if (form.goal) userConstraints.push(`目标/分数：${form.goal}`);
    if (form.targetDate) userConstraints.push(`目标日期/考试日期/出发日期：${form.targetDate}`);
    if (form.weeklyDays) userConstraints.push(`每周可投入天数：${form.weeklyDays}`);
    if (form.dailyMinutes) userConstraints.push(`每次/每天可投入分钟数：${form.dailyMinutes}`);
    if (form.destination) userConstraints.push(`目的地：${form.destination}`);
    if (form.budget) userConstraints.push(`预算：${form.budget}`);
    if (form.companions) userConstraints.push(`同行人：${form.companions}`);
    if (form.notes) userConstraints.push(`补充说明：${form.notes}`);

    const timeHorizon = typeof plan.time_horizon === "object" && plan.time_horizon !== null ? { ...(plan.time_horizon as Record<string, unknown>) } : {};
    if (form.targetDate) {
      timeHorizon.target_date = form.targetDate;
      timeHorizon.deadline = form.targetDate;
    }

    const enrichedPlan = {
      ...plan,
      goal: form.goal ? `${toText(plan.goal, toText(plan.title, "后台任务"))}（${form.goal}）` : plan.goal,
      time_horizon: timeHorizon,
      user_constraints: userConstraints,
      user_filled_fields: form,
    };
    return { ...args, plan: enrichedPlan, user_filled_fields: form };
  };

  const confirmTaskPlanAction = async (action: ActionResult, index: number) => {
    const key = actionKey(action, index);
    const pendingId = action.pending_action_id ?? action.confirmation_id;
    if (!pendingId) {
      setConfirmationErrors((prev) => ({ ...prev, [key]: "缺少待确认任务 ID，请重新让秘书生成任务计划。" }));
      return;
    }
    setConfirmingKey(key);
    setConfirmationErrors((prev) => ({ ...prev, [key]: "" }));
    setConfirmationMessages((prev) => ({ ...prev, [key]: "" }));
    try {
      const result = await jarvisApi.confirmPendingAction(String(pendingId), {
        title: toText(action.arguments?.title, "后台任务计划"),
        arguments: buildTaskPlanArguments(action, key),
      });
      const task = result.result?.task as { id?: string; title?: string; persisted?: boolean } | undefined;
      const taskTitle = task?.title || toText(action.arguments?.title, "后台任务计划");
      setConfirmations((prev) => ({ ...prev, [key]: "confirmed" }));
      setConfirmationMessages((prev) => ({ ...prev, [key]: `已保存到后台任务清单：${taskTitle}` }));
      useJarvisStore.getState().refreshAll().catch(() => undefined);
    } catch (error) {
      setConfirmationErrors((prev) => ({
        ...prev,
        [key]: error instanceof Error ? error.message : "确认任务计划失败，请稍后重试。",
      }));
    } finally {
      setConfirmingKey(null);
    }
  };

  const updateCareAction = async (action: ActionResult, index: number, nextState: CareActionState, stateLabel?: string) => {
    const key = actionKey(action, index);
    const args = action.arguments ?? {};
    const proactiveId = toText(args.proactive_message_id);
    setCareActionStates((prev) => ({ ...prev, [key]: nextState }));
    try {
      if (proactiveId) {
        const feedback = nextState === "snoozed" ? "snooze" : nextState === "read" ? "handled" : nextState;
        await jarvisApi.sendCareFeedback(proactiveId, {
          feedback: feedback as "helpful" | "too_frequent" | "not_needed" | "snooze" | "handled",
          snooze_minutes: nextState === "snoozed" ? 120 : undefined,
        });
        useJarvisStore.getState().loadProactiveMessages().catch(() => undefined);
      }
      if (stateLabel) setCareActionStates((prev) => ({ ...prev, [key]: stateLabel }));
    } catch (error) {
      setConfirmationErrors((prev) => ({
        ...prev,
        [key]: error instanceof Error ? error.message : "更新关怀状态失败，请稍后重试。",
      }));
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
    const scheduleGuard = asRecord(args.schedule_guard);
    const guardSummary = toText(scheduleGuard.summary);
    const guardRecommendation = toText(scheduleGuard.recommendation);
    const guardConflicts = asList(scheduleGuard.conflicts);
    const guardAlternatives = asList(scheduleGuard.alternatives);

    if (action.type === "mood.snapshot" || action.type === "care.intervention" || action.type === "care.followup") {
      if (action.type === "care.intervention" || action.type === "care.followup") {
        return (
          <CareCard
            key={key}
            action={action}
            state={careActionStates[key]}
            error={confirmationErrors[key]}
            onFeedback={(feedback, stateLabel) => updateCareAction(action, index, feedback === "snooze" ? "snoozed" : feedback, stateLabel)}
            submitFeedback={false}
          />
        );
      }
      const moodLabel = toText(args.mood_label, "状态记录");
      const riskLevel = toText(args.risk_level, "low");
      const supportNeed = toText(args.support_need, "companionship");
      const signals = asStringList(args.signals);
      const stressLevel = typeof args.stress_level === "number" ? args.stress_level : null;
      const energyLevel = typeof args.energy_level === "number" ? args.energy_level : null;
      const nextCheckinAt = toText(args.next_checkin_at);
      const proactiveId = toText(args.proactive_message_id);
      const isHighRisk = riskLevel === "high";
      const border = isHighRisk ? "border-red-200" : "border-rose-200";
      const bg = isHighRisk ? "bg-red-50" : "bg-rose-50";
      const text = isHighRisk ? "text-red-900" : "text-rose-900";

      return (
        <div key={key} className={`w-full rounded-2xl border ${border} ${bg} p-3 text-xs ${text}`}>
          <div className="flex items-center justify-between gap-2">
            <div className="text-sm font-semibold">
              {action.type === "mood.snapshot" ? "Mira 状态记录" : action.type === "care.followup" ? "Mira 后续回访" : "Mira 关怀建议"}
            </div>
            <span className="rounded-full bg-white/70 px-2 py-0.5 text-[10px] font-medium">
              {riskLevel === "high" ? "高风险" : riskLevel === "medium" ? "需要关怀" : "轻量记录"}
            </span>
          </div>
          {action.description ? <div className="mt-1 leading-relaxed">{action.description}</div> : null}
          <div className="mt-2 grid grid-cols-2 gap-2">
            <div className="rounded-xl bg-white/70 px-2 py-1.5">
              <div className="text-[10px] opacity-70">状态</div>
              <div className="font-medium">{moodLabel}</div>
            </div>
            <div className="rounded-xl bg-white/70 px-2 py-1.5">
              <div className="text-[10px] opacity-70">支持需求</div>
              <div className="font-medium">{supportNeed}</div>
            </div>
            {stressLevel !== null ? (
              <div className="rounded-xl bg-white/70 px-2 py-1.5">
                <div className="text-[10px] opacity-70">压力</div>
                <div className="font-medium">{stressLevel}/10</div>
              </div>
            ) : null}
            {energyLevel !== null ? (
              <div className="rounded-xl bg-white/70 px-2 py-1.5">
                <div className="text-[10px] opacity-70">能量</div>
                <div className="font-medium">{energyLevel}/10</div>
              </div>
            ) : null}
          </div>
          {signals.length > 0 ? <div className="mt-2 opacity-80">识别信号：{signals.join("、")}</div> : null}
          {nextCheckinAt ? <div className="mt-2 font-medium">回访时间：{formatDateTime(nextCheckinAt)}</div> : null}
          {proactiveId ? <div className="mt-1 text-[10px] opacity-70">回访 ID：{proactiveId}</div> : null}
          {error ? <div className="mt-2 text-red-600">{error}</div> : null}
        </div>
      );
    }

    if (action.type === "schedule_intent" || action.type === "task_intent") {
      const intent = asRecord(action.arguments);
      const matched = Array.isArray(intent.matched_keywords) ? intent.matched_keywords.map(String).join("、") : "";
      return (
        <div key={key} className="w-full rounded-2xl border border-indigo-200 bg-indigo-50 p-3 text-xs text-indigo-900">
          <div className="text-sm font-semibold">{routingTitle(intent)}</div>
          <div className="mt-1">秘书 Maxwell 将统一判断：生成日程卡、长期任务卡，或先追问必要信息。</div>
          {matched ? <div className="mt-1 text-indigo-700">命中意图：{matched}</div> : null}
        </div>
      );
    }

    if (action.type === "agent.consult") {
      const consultations = asList(action.arguments?.consultations);
      return (
        <div key={key} className="w-full rounded-2xl border border-violet-200 bg-violet-50 p-3 text-xs text-violet-900">
          <div className="text-sm font-semibold">已完成私下咨询</div>
          <div className="mt-1 text-violet-700">{action.description ?? `已完成 ${consultations.length} 次角色咨询`}</div>
          {consultations.length > 0 && (
            <div className="mt-2 space-y-1">
              {consultations.slice(0, 3).map((item, itemIndex) => {
                const fromName = toText(item.from_agent_name, toText(item.from_agent, "Agent"));
                const toName = toText(item.to_agent_name, toText(item.to_agent, "Agent"));
                const summary = toText(item.summary);
                return (
                  <div key={itemIndex} className="rounded-xl border border-violet-100 bg-white/75 px-2 py-1.5">
                    <div className="font-medium">{fromName}{" -> "}{toName}</div>
                    {summary ? <div className="mt-0.5 text-violet-700">{summary}</div> : null}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      );
    }

    if (action.pending_confirmation && action.type === "calendar.add") {
      return (
        <div key={key} className="w-full rounded-2xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          <div className="text-sm font-semibold">待确认日程</div>
          <div className="mt-1 font-medium">{title}</div>
          <div className="mt-1 text-amber-700">
            {formatDateTime(start)}{end ? ` - ${formatEndTime(end)}` : ""}
          </div>
          {guardSummary ? (
            <div className={`mt-2 rounded-xl border p-2 ${guardRecommendation === "move" ? "border-red-200 bg-red-50 text-red-700" : "border-amber-200 bg-white/70 text-amber-800"}`}>
              <div className="font-semibold">秘书判断：{guardRecommendation === "move" ? "建议调整时间" : guardRecommendation === "review" ? "建议复核" : "可执行"}</div>
              <div className="mt-1">{guardSummary}</div>
              {guardConflicts.length > 0 && (
                <div className="mt-1 space-y-0.5">
                  {guardConflicts.slice(0, 2).map((item, itemIndex) => (
                    <div key={itemIndex}>冲突：{toText(item.title, "已有日程")}（{formatDateTime(toText(item.start))} - {formatEndTime(toText(item.end))}）</div>
                  ))}
                </div>
              )}
              {guardAlternatives.length > 0 && (
                <div className="mt-1 text-[11px]">
                  可选空档：{guardAlternatives.slice(0, 2).map((item) => `${formatDateTime(toText(item.start))} - ${formatEndTime(toText(item.end))}`).join("；")}
                </div>
              )}
            </div>
          ) : null}
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

    if (action.pending_confirmation && action.type === "task.plan") {
      const plan = typeof args.plan === "object" && args.plan !== null ? args.plan as Record<string, unknown> : args;
      const planTitle = toText(plan.title, toText(args.title, "后台任务计划"));
      const classification = toText(args.classification, toText(plan.type, "project"));
      const questions = Array.isArray(args.clarifying_questions) ? args.clarifying_questions.slice(0, 3) : [];
      const milestones = Array.isArray(plan.milestones) ? plan.milestones.slice(0, 3) : [];
      const form = taskPlanForms[key] ?? {};
      const isTravel = planTitle.includes("旅行") || planTitle.includes("旅游");
      return (
        <div key={key} className="w-full rounded-2xl border border-blue-200 bg-blue-50 p-3 text-xs text-blue-900">
          <div className="text-sm font-semibold">待确认长期/后台任务计划</div>
          <div className="mt-1 font-medium">{planTitle}</div>
          <div className="mt-1 text-blue-700">类型：{classification}</div>
          {milestones.length > 0 && (
            <div className="mt-2 space-y-1">
              {milestones.map((item, itemIndex) => (
                <div key={itemIndex}>- {toText((item as Record<string, unknown>).title, String(item))}</div>
              ))}
            </div>
          )}
          {questions.length > 0 && <div className="mt-2 text-blue-700">请直接在下面补充关键信息，秘书会把它们一起保存到任务里。</div>}
          {!state && (
            <div className="mt-3 grid grid-cols-2 gap-2">
              {isTravel ? (
                <>
                  <input className="rounded-lg border border-blue-200 bg-white px-2 py-1.5" placeholder="目的地，例如：大阪" value={form.destination ?? ""} onChange={(event) => updateTaskPlanForm(key, { destination: event.target.value })} />
                  <input className="rounded-lg border border-blue-200 bg-white px-2 py-1.5" type="date" value={form.targetDate ?? ""} onChange={(event) => updateTaskPlanForm(key, { targetDate: event.target.value })} />
                  <input className="rounded-lg border border-blue-200 bg-white px-2 py-1.5" placeholder="预算，例如：8000 元" value={form.budget ?? ""} onChange={(event) => updateTaskPlanForm(key, { budget: event.target.value })} />
                  <input className="rounded-lg border border-blue-200 bg-white px-2 py-1.5" placeholder="同行人，例如：2 人/自己" value={form.companions ?? ""} onChange={(event) => updateTaskPlanForm(key, { companions: event.target.value })} />
                </>
              ) : (
                <>
                  <input className="rounded-lg border border-blue-200 bg-white px-2 py-1.5" placeholder="目标，例如：雅思 7 分" value={form.goal ?? ""} onChange={(event) => updateTaskPlanForm(key, { goal: event.target.value })} />
                  <input className="rounded-lg border border-blue-200 bg-white px-2 py-1.5" type="date" value={form.targetDate ?? ""} onChange={(event) => updateTaskPlanForm(key, { targetDate: event.target.value })} />
                  <input className="rounded-lg border border-blue-200 bg-white px-2 py-1.5" placeholder="每周几天，例如：4" value={form.weeklyDays ?? ""} onChange={(event) => updateTaskPlanForm(key, { weeklyDays: event.target.value })} />
                  <input className="rounded-lg border border-blue-200 bg-white px-2 py-1.5" placeholder="每次多少分钟，例如：60" value={form.dailyMinutes ?? ""} onChange={(event) => updateTaskPlanForm(key, { dailyMinutes: event.target.value })} />
                </>
              )}
              <textarea className="col-span-2 rounded-lg border border-blue-200 bg-white px-2 py-1.5 min-h-16" placeholder="补充约束/偏好，可不填" value={form.notes ?? ""} onChange={(event) => updateTaskPlanForm(key, { notes: event.target.value })} />
            </div>
          )}
          {state ? (
            <div className="mt-2 font-medium">{state === "confirmed" ? (confirmationMessages[key] || "已保存到后台任务清单，可在日历 → 查看所有任务里看到") : "已取消"}</div>
          ) : (
            <div className="mt-3 flex gap-2">
              <button
                className="px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60"
                disabled={confirmingKey === key}
                onClick={() => confirmTaskPlanAction(action, index)}
              >
                {confirmingKey === key ? "加入中…" : "确认加入后台任务"}
              </button>
              <button
                className="px-3 py-1.5 rounded-lg border border-blue-200 bg-white text-blue-700 hover:bg-blue-100"
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
              if (confirm(`清除此会话中和 ${agent.name} 的聊天记录？`)) clearChatHistoryStore(agentId, sessionId);
            }}
            className="text-xs px-2.5 py-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors"
          >
            清空
          </button>
          <button onClick={saveAndClose} className="text-sm px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors">
            返回
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
        {loadingHistory && <p className="text-center text-xs text-gray-400 mt-4">加载历史中…</p>}
        {!loadingHistory && history.length === 0 && <p className="text-center text-sm text-gray-400 mt-8">和 {agent.name} 开始对话…</p>}
        {history.map((message, index) => (
          <div key={index} className={`flex flex-col gap-1 ${message.role === "user" ? "items-end" : "items-start"}`}>
            {message.role === "agent" && message.routing && (
              <div className="max-w-[75%] rounded-2xl border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs text-indigo-900">
                <div className="font-semibold">{routingTitle(message.routing)}</div>
                <div className="mt-1">当前由秘书 Maxwell 接管安排，避免非秘书 Agent 直接写日程或长期计划。</div>
              </div>
            )}
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
              <div className="flex w-full max-w-[75%] flex-col gap-1.5">
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


