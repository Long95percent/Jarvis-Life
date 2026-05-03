// shadowlink-web/src/components/jarvis/RoundtableStage.tsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send } from "lucide-react";
import { JARVIS_AGENTS } from "./agentMeta";
import {
  initialRoundtableModeForScenario,
  pendingActionCount,
  routeButtonsFromScenarioState,
} from "./roundtableStageLogic";
import { jarvisApi } from "@/services/jarvisApi";
import type { JarvisMemory, PendingAction, RoundtableBrainstormResult, RoundtableDecisionResult } from "@/services/jarvisApi";

interface Props {
  scenarioId: string;
  userInput: string;
  sessionId: string;
  sourceSessionId?: string | null;
  sourceAgentId?: string | null;
  modeId?: string;
  onClose: () => void;
  onReturnToPrivateChat?: (agentId: string, sessionId: string) => void | Promise<void>;
}

type TurnKind = "user" | "agent";

interface TranscriptEntry {
  key: string;
  kind: TurnKind;
  agentId: string;       // "user" for user turns
  agentName: string;     // "你" for user turns
  agentColor: string;
  agentIcon: string;
  content: string;
  toolCount?: number;
  actionCount?: number;
}

interface SpeakPayload {
  agent_id: string;
  agent_name: string;
  agent_role?: string;
  agent_icon?: string;
  agent_color?: string;
  content?: string;
  phase?: string;
  progress?: RoundtableProgress;
}

interface TokenPayload {
  agent_id: string;
  agent_name: string;
  content: string;
  progress?: RoundtableProgress;
}

interface RoundStartedPayload {
  round_index: number;
  participants?: string[];
}

interface RoleDeltaPayload {
  agent_id: string;
  delta: string;
  round_index: number;
}

interface RoleCompletedPayload extends SpeakPayload {
  content: string;
  round_index: number;
  tool_results?: Array<Record<string, unknown>>;
  action_results?: Array<Record<string, unknown>>;
}

interface RoundSummaryPayload {
  round_index: number;
  minutes: Array<{ agent_id?: string; agent_name?: string; summary?: string }>;
  consensus: string[];
  disagreements: string[];
  questions_for_user: string[];
  next_round_focus: string[];
}

interface RoundtableProgress {
  current?: number;
  total?: number;
  status?: string;
}

interface AgentDegradedPayload extends SpeakPayload {
  error?: string;
  fallback_content?: string;
  continue_next_agent?: boolean;
}

interface PhasePayload {
  phase: string;
  scenario_name?: string;
  participants?: string[];
  round_count?: number;
  mode?: string;
}

interface TimingPayload {
  total_ms?: number;
  spans?: Array<Record<string, unknown>>;
}

interface ScenarioStagePayload {
  scenario_id: string;
  graph_executor?: string;
  state_type?: string;
  stage_id: string;
  stage_title?: string;
  owner_agent?: string;
  round_index?: number;
  objective?: string;
  artifact_keys?: string[];
}

interface ScenarioStatePayload {
  scenario_id: string;
  graph_executor?: string;
  state_type?: string;
  round_index?: number;
  artifacts?: Record<string, unknown>;
  next_routes?: Array<{ label?: string; target_stage?: string; prompt?: string }>;
}

interface AgentMeta {
  id: string;
  name: string;
  role: string;
  color: string;
  icon: string;
}

const USER_COLOR = "#FBBF24"; // amber, distinctive from agent colors
const USER_ICON = "👤";

const SCENARIO_META: Record<string, { icon: string; name: string; subtitle: string }> = {
  schedule_coord: { icon: "📅", name: "今日日程协调", subtitle: "Daily Orchestration" },
  local_lifestyle: { icon: "🌟", name: "本地生活活动推荐", subtitle: "Lifestyle Suggestions" },
  emotional_care: { icon: "🌸", name: "情绪压力疏导", subtitle: "Emotional Care" },
  weekend_recharge: { icon: "🌿", name: "周末恢复规划", subtitle: "Weekend Recharge" },
  work_brainstorm: { icon: "💡", name: "工作难题头脑风暴", subtitle: "Work Brainstorm" },
  study_energy_decision: { icon: "⚖️", name: "疲惫学习决策", subtitle: "Decision Roundtable" },
};

const GRAPH_ROUNDTABLE_SCENARIOS = new Set([
  "schedule_coord",
  "local_lifestyle",
  "emotional_care",
  "study_energy_decision",
  "weekend_recharge",
  "work_brainstorm",
]);

function parseSSEFrames(buffer: string): {
  frames: Array<{ event: string; data: string }>;
  remainder: string;
} {
  const frames: Array<{ event: string; data: string }> = [];
  let remainder = buffer.replace(/\r\n/g, "\n").replace(/\r/g, "\n");

  while (true) {
    const splitIdx = remainder.indexOf("\n\n");
    if (splitIdx === -1) break;
    const frameText = remainder.slice(0, splitIdx);
    remainder = remainder.slice(splitIdx + 2);

    let event = "message";
    const dataLines: string[] = [];
    for (const line of frameText.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (dataLines.length === 0) continue;
    frames.push({ event, data: dataLines.join("\n") });
  }

  return { frames, remainder };
}

function computeAgentPositions(n: number, radius: number): Array<{ x: number; y: number; angle: number }> {
  const positions: Array<{ x: number; y: number; angle: number }> = [];
  for (let i = 0; i < n; i++) {
    const angle = -Math.PI / 2 + (2 * Math.PI * i) / n;
    positions.push({
      x: Math.cos(angle) * radius,
      y: Math.sin(angle) * radius,
      angle,
    });
  }
  return positions;
}

type DecisionResult = RoundtableDecisionResult;
type BrainstormResult = RoundtableBrainstormResult;

function normalizeAgentReply(content: string, agentName: string): string {
  const trimmed = content.trim();
  if (/^\(?Agent\s+[^\s)]+\s+暂无回复\)?$/i.test(trimmed)) {
    return `${agentName} 当前没有拿到模型回复。请检查 AI 服务是否已重启，并确认设置里的 Provider API Key、Base URL、模型名称可用。`;
  }
  return content;
}

function clampSpeech(content: string, maxChars = 420): string {
  const trimmed = content.trim();
  return trimmed.length > maxChars ? `${trimmed.slice(0, maxChars)}…` : trimmed;
}

function transcriptEntryFromTurn(turn: { role: string; speaker_name: string; content: string; timestamp: number }, index: number): TranscriptEntry {
  if (turn.role === "user") {
    return {
      key: `history-user-${index}`,
      kind: "user",
      agentId: "user",
      agentName: "你",
      agentColor: USER_COLOR,
      agentIcon: USER_ICON,
      content: turn.content,
    };
  }
  const agentId = turn.role;
  const meta = JARVIS_AGENTS[agentId];
  return {
    key: `history-agent-${index}`,
    kind: "agent",
    agentId,
    agentName: turn.speaker_name || meta?.name || agentId,
    agentColor: meta?.color ?? "#6366F1",
    agentIcon: meta?.icon ?? "🤖",
    content: turn.content,
  };
}

function contextExplanationItems(result: { context?: Record<string, unknown> } | null): Array<{ key: string; label: string; summary: string; impact: string }> {
  const explanation = result?.context?.context_explanation;
  if (!explanation || typeof explanation !== "object") return [];
  return Object.entries(explanation as Record<string, unknown>).map(([key, raw]) => {
    const item = raw && typeof raw === "object" ? raw as Record<string, unknown> : {};
    return {
      key,
      label: typeof item.label === "string" ? item.label : key,
      summary: typeof item.summary === "string" ? item.summary : "暂无摘要",
      impact: typeof item.impact === "string" ? item.impact : "用于辅助圆桌判断。",
    };
  });
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function recordList(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => !!item && typeof item === "object" && !Array.isArray(item)) : [];
}

function protocolPhasesFromResult(result: { context?: Record<string, unknown> } | null): string[] {
  return stringList(result?.context?.scenario_protocol_phases);
}

function titleOf(item: Record<string, unknown>, fallback: string): string {
  const value = item.title ?? item.name ?? item.summary ?? item.id;
  return typeof value === "string" && value.trim() ? value : fallback;
}

export const RoundtableStage: React.FC<Props> = ({
  scenarioId,
  userInput,
  sessionId,
  sourceSessionId,
  sourceAgentId,
  modeId = "general",
  onClose,
  onReturnToPrivateChat,
}) => {
  const [participants, setParticipants] = useState<AgentMeta[]>([]);
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [activeAgentId, setActiveAgentId] = useState<string | null>(null);
  const [currentContent, setCurrentContent] = useState<string>("");
  const [phase, setPhase] = useState<string>("connecting");
  const [status, setStatus] = useState<"connecting" | "streaming" | "idle" | "error">("connecting");
  const [roundCount, setRoundCount] = useState<number>(0);
  const [roundtableMode, setRoundtableMode] = useState<string>(() => initialRoundtableModeForScenario(scenarioId));
  const [timing, setTiming] = useState<TimingPayload | null>(null);
  const [progress, setProgress] = useState<RoundtableProgress | null>(null);
  const [degradedMessages, setDegradedMessages] = useState<Array<{ agentId: string; agentName: string; message: string }>>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showTranscript, setShowTranscript] = useState(false);
  const [roundSummaries, setRoundSummaries] = useState<RoundSummaryPayload[]>([]);
  const [waitingForCheckpoint, setWaitingForCheckpoint] = useState(false);
  const [scenarioStages, setScenarioStages] = useState<ScenarioStagePayload[]>([]);
  const [scenarioState, setScenarioState] = useState<ScenarioStatePayload | null>(null);

  const [userDraft, setUserDraft] = useState<string>("");
  const [userBubble, setUserBubble] = useState<string | null>(null);
  const [decisionResult, setDecisionResult] = useState<DecisionResult | null>(null);
  const [acceptedPendingAction, setAcceptedPendingAction] = useState<PendingAction | null>(null);
  const [decisionBusy, setDecisionBusy] = useState(false);
  const [returnBusy, setReturnBusy] = useState(false);
  const [returnNotice, setReturnNotice] = useState<string | null>(null);
  const [brainstormResult, setBrainstormResult] = useState<BrainstormResult | null>(null);
  const [savedBrainstormMemory, setSavedBrainstormMemory] = useState<JarvisMemory | null>(null);
  const [brainstormPendingAction, setBrainstormPendingAction] = useState<PendingAction | null>(null);
  const [brainstormBusy, setBrainstormBusy] = useState<"save" | "plan" | null>(null);

  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const isMountedRef = useRef(true);

  const scenarioMeta = SCENARIO_META[scenarioId] ?? {
    icon: "💬",
    name: scenarioId,
    subtitle: "Roundtable",
  };

  useEffect(() => {
    const scenarioAgents: Record<string, string[]> = {
      schedule_coord: ["maxwell", "nora", "mira", "alfred"],
      local_lifestyle: ["leo", "maxwell", "nora", "alfred"],
      emotional_care: ["mira", "nora", "leo", "alfred"],
      weekend_recharge: ["leo", "nora", "mira", "alfred"],
      work_brainstorm: ["moderator", "explorer", "critic", "synthesizer"],
      study_energy_decision: ["mira", "maxwell", "athena", "alfred"],
    };
    const ids = scenarioAgents[scenarioId] ?? [];
    const resolved = ids.map((id) => ({
      id,
      name: JARVIS_AGENTS[id]?.name ?? id,
      role: JARVIS_AGENTS[id]?.role ?? "专家",
      color: JARVIS_AGENTS[id]?.color ?? "#6366F1",
      icon: JARVIS_AGENTS[id]?.icon ?? "🤖",
    }));
    setParticipants(resolved);
  }, [scenarioId]);

  useEffect(() => {
    if (showTranscript) {
      transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [transcript, showTranscript]);

  /** Stream a single round from the backend into local state. */
  const streamRound = async (endpoint: string, body: Record<string, any>) => {
    const controller = new AbortController();
    abortRef.current?.abort();
    abortRef.current = controller;

    try {
      setStatus("streaming");
      setPhase("讨论进行中");
      setTiming(null);
      setProgress(null);
      setScenarioState(null);
      setScenarioStages([]);
      setErrorMsg(null);
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        if (!isMountedRef.current) break;
        buffer += decoder.decode(value, { stream: true });
        const { frames, remainder } = parseSSEFrames(buffer);
        buffer = remainder;
        for (const frame of frames) {
          handleFrame(frame.event, frame.data);
        }
      }
      if (isMountedRef.current) {
        setStatus("idle");
      setPhase("等待你的回应");
        setActiveAgentId(null);
        setCurrentContent("");
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      if (isMountedRef.current) {
        setStatus("error");
        setPhase("错误");
        setErrorMsg((err as Error).message);
      }
    }
  };

  // Initial /start call
  useEffect(() => {
    isMountedRef.current = true;
    (async () => {
      const existingTurns = await jarvisApi.getRoundtableTurns(sessionId).catch(() => []);
      if (!isMountedRef.current) return;
      if (existingTurns.length > 0) {
        setTranscript(existingTurns.map(transcriptEntryFromTurn));
        jarvisApi.getRoundtableDecisionResult(sessionId).then(setDecisionResult).catch(() => undefined);
        jarvisApi.getRoundtableBrainstormResult(sessionId).then(setBrainstormResult).catch(() => undefined);
        setStatus("idle");
        setPhase("已恢复历史讨论");
        setRoundCount(Math.max(1, Math.ceil(existingTurns.filter((turn) => turn.role !== "user").length / Math.max(1, participants.length || 1))));
        return;
      }
      streamRound("/api/v1/jarvis/roundtable/start", {
        scenario_id: scenarioId,
        user_input: userInput,
        session_id: sessionId,
        mode_id: modeId,
        source_session_id: sourceSessionId ?? undefined,
        source_agent_id: sourceAgentId ?? undefined,
      });
    })();
    return () => {
      isMountedRef.current = false;
      abortRef.current?.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenarioId, sessionId, modeId]);

  const handleFrame = (event: string, rawData: string) => {
    let data: unknown;
    try {
      data = JSON.parse(rawData);
    } catch {
      return;
    }

    if (event === "phase_change") {
      const payload = data as PhasePayload;
      const phaseMap: Record<string, string> = {
        open: "开场",
        user_turn: "响应你的发言",
        speaking: "讨论中",
        diverge: "发散讨论",
        converge: "收敛总结",
        conclude: "最终结论",
        round_complete: "本轮结束",
        complete: "结束",
      };
      setPhase(phaseMap[payload.phase] ?? payload.phase);
      if (payload.round_count) setRoundCount(payload.round_count);
      if (payload.mode) setRoundtableMode(payload.mode);
      setProgress(null);
      setCurrentContent("");
      setActiveAgentId(null);
      return;
    }

    if (event === "round_started") {
      const payload = data as RoundStartedPayload;
      setRoundCount(payload.round_index);
      setWaitingForCheckpoint(false);
      setCurrentContent("");
      setActiveAgentId(null);
      setProgress({
        current: 0,
        total: payload.participants?.length ?? participants.length,
        status: "speaking",
      });
      return;
    }

    if (event === "scenario_stage") {
      const payload = data as ScenarioStagePayload;
      setScenarioStages((prev) => [...prev.filter((item) => item.round_index !== payload.round_index || item.stage_id !== payload.stage_id), payload].slice(-8));
      setPhase(payload.stage_title || payload.stage_id);
      return;
    }

    if (event === "scenario_state") {
      setScenarioState(data as ScenarioStatePayload);
      return;
    }

    if (event === "role_started") {
      const payload = data as SpeakPayload;
      setActiveAgentId(payload.agent_id);
      setCurrentContent("");
      setUserBubble(null);
      setProgress((prev) => ({
        current: prev?.current ?? 0,
        total: prev?.total ?? participants.length,
        status: "speaking",
      }));
      return;
    }

    if (event === "role_delta") {
      const payload = data as RoleDeltaPayload;
      setActiveAgentId(payload.agent_id);
      setCurrentContent((prev) => prev + payload.delta);
      return;
    }

    if (event === "role_completed") {
      const payload = data as RoleCompletedPayload;
      const meta = JARVIS_AGENTS[payload.agent_id];
      const normalizedContent = normalizeAgentReply(payload.content, payload.agent_name);
      setTranscript((prev) => [
        ...prev,
        {
          key: `msg-${prev.length}`,
          kind: "agent",
          agentId: payload.agent_id,
          agentName: payload.agent_name,
          agentColor: payload.agent_color ?? meta?.color ?? "#6366F1",
          agentIcon: payload.agent_icon ?? meta?.icon ?? "🤖",
          content: normalizedContent,
          toolCount: payload.tool_results?.length ?? 0,
          actionCount: pendingActionCount(payload.action_results),
        },
      ]);
      setProgress((prev) => ({
        current: Math.min((prev?.current ?? 0) + 1, prev?.total ?? participants.length),
        total: prev?.total ?? participants.length,
        status: "completed",
      }));
      window.setTimeout(() => {
        setActiveAgentId((current) => current === payload.agent_id ? null : current);
        setCurrentContent("");
      }, 450);
      return;
    }

    if (event === "round_summary") {
      setRoundSummaries((prev) => [...prev, data as RoundSummaryPayload]);
      setPhase("等待你的判断");
      return;
    }

    if (event === "user_checkpoint") {
      setWaitingForCheckpoint(true);
      setStatus("idle");
      setPhase("等待你的判断");
      setProgress(null);
      return;
    }

    if (event === "agent_speak") {
      const payload = data as SpeakPayload;
      const normalizedContent = payload.content
        ? normalizeAgentReply(payload.content, payload.agent_name)
        : "";
      setActiveAgentId(payload.agent_id);
      setCurrentContent(normalizedContent);
      if (payload.progress) setProgress(payload.progress);
      // Clear user bubble once the first agent starts speaking
      setUserBubble(null);
      if (normalizedContent.trim()) {
        const meta = JARVIS_AGENTS[payload.agent_id];
        setTranscript((prev) => [
          ...prev,
          {
            key: `msg-${prev.length}`,
            kind: "agent",
            agentId: payload.agent_id,
            agentName: payload.agent_name,
            agentColor: payload.agent_color ?? meta?.color ?? "#6366F1",
            agentIcon: payload.agent_icon ?? meta?.icon ?? "🤖",
            content: normalizedContent,
          },
        ]);
      }
      return;
    }

    if (event === "token") {
      const payload = data as TokenPayload;
      const meta = JARVIS_AGENTS[payload.agent_id];
      const normalizedContent = normalizeAgentReply(payload.content, payload.agent_name);
      setCurrentContent(normalizedContent);
      if (payload.progress) setProgress(payload.progress);
      setTranscript((prev) => [
        ...prev,
        {
          key: `msg-${prev.length}`,
          kind: "agent",
          agentId: payload.agent_id,
          agentName: payload.agent_name,
          agentColor: meta?.color ?? "#6366F1",
          agentIcon: meta?.icon ?? "🤖",
          content: normalizedContent,
        },
      ]);
      return;
    }

    if (event === "done") {
      setActiveAgentId(null);
      setCurrentContent("");
      return;
    }

    if (event === "agent_degraded") {
      const payload = data as AgentDegradedPayload;
      const meta = JARVIS_AGENTS[payload.agent_id];
      const message = payload.error ? `模型暂时不可用：${payload.error}` : "模型暂时不可用，已用降级回复继续下一位。";
      if (payload.progress) setProgress(payload.progress);
      setDegradedMessages((prev) => [
        ...prev,
        { agentId: payload.agent_id, agentName: payload.agent_name || meta?.name || payload.agent_id, message },
      ].slice(-3));
      return;
    }

    if (event === "roundtable_timing") {
      setTiming(data as TimingPayload);
      return;
    }

    if (event === "decision_result") {
      setDecisionResult(data as DecisionResult);
      setWaitingForCheckpoint(false);
      return;
    }

    if (event === "brainstorm_result") {
      setBrainstormResult(data as BrainstormResult);
      setWaitingForCheckpoint(false);
      return;
    }
  };

  const handleSendUserMessage = async () => {
    const msg = userDraft.trim();
    if (!msg || status === "streaming") return;
    setUserDraft("");

    // Push user turn to local transcript + show bubble briefly
    setTranscript((prev) => [
      ...prev,
      {
        key: `user-${prev.length}`,
        kind: "user",
        agentId: "user",
        agentName: "你",
        agentColor: USER_COLOR,
        agentIcon: USER_ICON,
        content: msg,
      },
    ]);
    setUserBubble(msg);

    // Fire continue request
    await streamRound("/api/v1/jarvis/roundtable/continue", {
      session_id: sessionId,
      user_message: msg,
    });
  };

  const handleClose = () => {
    abortRef.current?.abort();
    onClose();
  };

  const handleAcceptDecision = async () => {
    if (!decisionResult || decisionBusy) return;
    setDecisionBusy(true);
    try {
      const res = await jarvisApi.acceptRoundtableDecision(sessionId, decisionResult.id);
      setDecisionResult(res.result);
      setAcceptedPendingAction(res.pending_action);
    } finally {
      setDecisionBusy(false);
    }
  };

  const handleSaveBrainstorm = async () => {
    if (!brainstormResult || brainstormBusy) return;
    setBrainstormBusy("save");
    try {
      const res = await jarvisApi.saveRoundtableBrainstorm(sessionId, brainstormResult.id);
      setBrainstormResult(res.result);
      setSavedBrainstormMemory(res.memory);
    } finally {
      setBrainstormBusy(null);
    }
  };

  const handleBrainstormToPlan = async () => {
    if (!brainstormResult || brainstormBusy) return;
    setBrainstormBusy("plan");
    try {
      const res = await jarvisApi.convertRoundtableBrainstormToPlan(sessionId, brainstormResult.id);
      setBrainstormResult(res.result);
      setBrainstormPendingAction(res.pending_action);
    } finally {
      setBrainstormBusy(null);
    }
  };

  const handleReturnToPrivateChat = async (choice: string) => {
    const resultId = roundtableMode === "brainstorm" ? brainstormResult?.id : decisionResult?.id;
    if (returnBusy) return;
    setReturnBusy(true);
    setReturnNotice(null);
    try {
      const res = await jarvisApi.returnRoundtableToPrivateChat(sessionId, {
        result_id: resultId,
        user_choice: choice,
        note: "用户在圆桌页面选择带总结回到原私聊继续。",
      });
      setReturnNotice("圆桌总结已写回原私聊，正在返回对话。");
      await onReturnToPrivateChat?.(res.source_agent_id || "alfred", res.source_session_id);
    } catch (error) {
      setReturnNotice(error instanceof Error ? error.message : "返回私聊失败，请稍后重试。若本圆桌不是从私聊发起，请先保存结果。");
    } finally {
      setReturnBusy(false);
    }
  };

  const stageRadius = 220;
  const positions = useMemo(
    () => computeAgentPositions(participants.length, stageRadius),
    [participants.length],
  );

  const activeAgent = participants.find((p) => p.id === activeAgentId);
  const modeTone = roundtableMode === "brainstorm"
    ? { label: "Brainstorm", accent: "#A78BFA", panel: "border-violet-300/25", hint: "先发散，不自动执行" }
    : { label: "Decision", accent: "#34D399", panel: "border-emerald-300/25", hint: "先判断，再交给确认" };
  const hostSummary = decisionResult
    ? `主持总结：建议「${decisionResult.recommended_option}」，接受后只生成待确认动作。`
    : brainstormResult
      ? `主持总结：已沉淀 ${brainstormResult.ideas.length} 个想法，可保存灵感或转给 Maxwell。`
      : `${modeTone.label} 圆桌进行中：${modeTone.hint}`;
  const decisionContextItems = contextExplanationItems(decisionResult);
  const latestRoundSummary = roundSummaries[roundSummaries.length - 1];
  const resultForProtocol = decisionResult ?? brainstormResult;
  const protocolPhases = protocolPhasesFromResult(resultForProtocol);
  const activeScenarioStage = scenarioStages[scenarioStages.length - 1];
  const scenarioArtifacts = scenarioState?.artifacts ?? (brainstormResult?.c_artifacts && typeof brainstormResult.c_artifacts === "object" ? brainstormResult.c_artifacts : null);
  const localRankedActivities = recordList(
    scenarioArtifacts?.ranked_activities ?? brainstormResult?.ranked_activities,
  );
  const workValidationSteps = stringList(
    scenarioArtifacts?.validation_plan ?? brainstormResult?.minimum_validation_steps,
  );
  const workRisks = recordList(
    scenarioArtifacts?.critique_matrix ?? brainstormResult?.risks,
  );
  const scenarioRouteButtons = routeButtonsFromScenarioState(scenarioState);

  return (
    <AnimatePresence>
      <motion.div
        key="stage"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 overflow-hidden"
        style={{
          background:
            `radial-gradient(ellipse at center, color-mix(in srgb, ${modeTone.accent} 18%, #0a0a12) 0%, #05050a 75%)`,
          backdropFilter: "blur(8px)",
        }}
      >
        {/* Ambient particle overlay */}
        <div
          className="absolute inset-0 pointer-events-none opacity-30"
          style={{
            background:
              "radial-gradient(circle at 30% 20%, color-mix(in srgb, var(--color-primary) 40%, transparent) 0%, transparent 50%), radial-gradient(circle at 70% 80%, color-mix(in srgb, var(--color-accent) 30%, transparent) 0%, transparent 50%)",
          }}
        />

        {/* Header bar */}
        <div className="relative z-10 flex items-center justify-between px-8 py-5">
          <div className="flex items-center gap-3">
            <span className="text-3xl">{scenarioMeta.icon}</span>
            <div>
              <h1 className="text-xl font-semibold text-white leading-tight">
                {scenarioMeta.name}
              </h1>
              <p className="text-xs text-white/50 uppercase tracking-wider">
                {scenarioMeta.subtitle}
                {roundCount > 0 && ` · Round ${roundCount}`}
              </p>
              <p className="mt-1 text-[11px] text-white/45">
                {modeTone.hint}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <motion.div
              key={phase}
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              className="px-3 py-1.5 rounded-full bg-white/10 border border-white/20 text-xs font-medium text-white/90 backdrop-blur-sm"
            >
              <span className={`inline-block w-1.5 h-1.5 rounded-full mr-2 ${
                status === "streaming" ? "bg-green-400 animate-pulse" :
                status === "idle" ? "bg-blue-400" :
                status === "error" ? "bg-red-400" : "bg-gray-400"
              }`} />
              {phase}
            </motion.div>
            {timing?.total_ms && (
              <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white/55">
                {Math.round(timing.total_ms)}ms
              </span>
            )}
            {progress?.total ? (
              <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white/70">
                进度 {progress.current ?? 0}/{progress.total} · {progress.status === "degraded" ? "已降级继续" : progress.status === "completed" ? "已完成" : "发言中"}
              </span>
            ) : null}

            <button
              onClick={() => setShowTranscript((s) => !s)}
              className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 border border-white/10 text-sm text-white/80 transition-colors"
            >
              {showTranscript ? "隐藏记录" : `完整记录 (${transcript.length})`}
            </button>

            <button
              onClick={handleClose}
              className="w-9 h-9 rounded-full bg-white/10 hover:bg-red-500/80 border border-white/10 flex items-center justify-center text-white transition-colors"
              aria-label="鍏抽棴"
            >
              ×
            </button>
          </div>
        </div>

        {degradedMessages.length > 0 && (
          <div className="absolute left-8 top-24 z-30 max-w-sm space-y-2">
            {degradedMessages.map((item, index) => (
              <div key={`${item.agentId}-${index}`} className="rounded-xl border border-amber-300/25 bg-amber-300/10 px-3 py-2 text-xs text-amber-50 backdrop-blur-md">
                <div className="font-semibold">{item.agentName} 已降级继续</div>
                <div className="mt-0.5 text-amber-50/75">{item.message}</div>
              </div>
            ))}
          </div>
        )}

        {returnNotice && (
          <div className="absolute left-1/2 top-24 z-30 max-w-md -translate-x-1/2 rounded-xl border border-white/15 bg-white/10 px-4 py-2 text-xs text-white/85 backdrop-blur-md">
            {returnNotice}
          </div>
        )}

        {(activeScenarioStage || scenarioState || protocolPhases.length > 0) && !showTranscript && !decisionResult && !brainstormResult && (
          <div className="absolute left-8 top-24 z-30 w-[360px] rounded-2xl border border-white/15 bg-slate-950/90 p-4 text-white shadow-2xl backdrop-blur-xl">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-white/45">Scenario Flow</p>
                <h3 className="text-base font-semibold">
                  {activeScenarioStage?.stage_title || activeScenarioStage?.stage_id || scenarioState?.state_type || "场景协议"}
                </h3>
              </div>
              {scenarioState?.state_type && (
                <span className="rounded-full bg-white/10 px-2 py-1 text-[11px] text-white/65">{scenarioState.state_type}</span>
              )}
            </div>
            {activeScenarioStage?.objective && (
              <p className="mb-3 text-xs leading-relaxed text-white/60">{activeScenarioStage.objective}</p>
            )}
            {scenarioStages.length > 0 ? (
              <div className="mb-3 flex flex-wrap gap-1.5">
                {scenarioStages.slice(-5).map((stage) => (
                  <span
                    key={`${stage.round_index}-${stage.stage_id}`}
                    className={`rounded-full px-2 py-1 text-[11px] ${stage.stage_id === activeScenarioStage?.stage_id ? "bg-emerald-300 text-slate-950" : "bg-white/10 text-white/65"}`}
                  >
                    {stage.stage_id}
                  </span>
                ))}
              </div>
            ) : protocolPhases.length > 0 ? (
              <div className="mb-3 flex flex-wrap gap-1.5">
                {protocolPhases.slice(0, 6).map((stage) => (
                  <span key={stage} className="rounded-full bg-white/10 px-2 py-1 text-[11px] text-white/65">{stage}</span>
                ))}
              </div>
            ) : null}
            {localRankedActivities.length > 0 && (
              <div className="rounded-xl border border-emerald-300/20 bg-emerald-300/10 p-2 text-xs text-emerald-50">
                <div className="mb-1 font-semibold">当前活动排序</div>
                <ul className="space-y-1 text-emerald-50/75">
                  {localRankedActivities.slice(0, 3).map((item, idx) => (
                    <li key={`${item.id ?? idx}`}>• {titleOf(item, `候选 ${idx + 1}`)}</li>
                  ))}
                </ul>
              </div>
            )}
            {workValidationSteps.length > 0 && (
              <div className="rounded-xl border border-violet-300/20 bg-violet-300/10 p-2 text-xs text-violet-50">
                <div className="mb-1 font-semibold">最小验证步骤</div>
                <ul className="space-y-1 text-violet-50/75">
                  {workValidationSteps.slice(0, 3).map((item, idx) => <li key={idx}>• {item}</li>)}
                </ul>
              </div>
            )}
            {scenarioRouteButtons.length > 0 && (
              <div className="mt-3 border-t border-white/10 pt-3">
                <div className="mb-2 text-xs font-semibold text-white/75">下一轮路线</div>
                <div className="flex flex-wrap gap-1.5">
                  {scenarioRouteButtons.map((route) => (
                    <button
                      key={`${route.targetStage ?? route.label}-${route.prompt}`}
                      type="button"
                      onClick={() => setUserDraft(route.prompt)}
                      disabled={status === "streaming"}
                      className="rounded-lg bg-white/10 px-2 py-1 text-[11px] text-white/75 transition-colors hover:bg-white/15 disabled:opacity-45"
                    >
                      {route.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {latestRoundSummary && !showTranscript && !decisionResult && !brainstormResult && (
          <div className="absolute right-8 top-24 z-30 w-[390px] rounded-2xl border border-white/15 bg-slate-950/90 p-4 text-white shadow-2xl backdrop-blur-xl">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-white/45">Round Summary</p>
                <h3 className="text-base font-semibold">第 {latestRoundSummary.round_index} 轮纪要</h3>
              </div>
              {waitingForCheckpoint && (
                <span className="rounded-full bg-amber-300/15 px-2 py-1 text-[11px] text-amber-100">等你判断</span>
              )}
            </div>
            <div className="space-y-3 text-xs">
              {latestRoundSummary.minutes.length > 0 && (
                <section>
                  <div className="mb-1 font-semibold text-white/80">角色纪要</div>
                  <ul className="space-y-1 text-white/65">
                    {latestRoundSummary.minutes.slice(0, 4).map((item, idx) => (
                      <li key={`${item.agent_id ?? idx}-${idx}`}>• {item.agent_name ?? item.agent_id ?? "成员"}：{item.summary ?? "暂无摘要"}</li>
                    ))}
                  </ul>
                </section>
              )}
              {latestRoundSummary.consensus.length > 0 && (
                <section>
                  <div className="mb-1 font-semibold text-emerald-100">共识</div>
                  <ul className="space-y-1 text-emerald-50/75">
                    {latestRoundSummary.consensus.slice(0, 3).map((item, idx) => <li key={idx}>• {item}</li>)}
                  </ul>
                </section>
              )}
              {latestRoundSummary.disagreements.length > 0 && (
                <section>
                  <div className="mb-1 font-semibold text-amber-100">分歧</div>
                  <ul className="space-y-1 text-amber-50/75">
                    {latestRoundSummary.disagreements.slice(0, 3).map((item, idx) => <li key={idx}>• {item}</li>)}
                  </ul>
                </section>
              )}
              {latestRoundSummary.questions_for_user.length > 0 && (
                <section>
                  <div className="mb-1 font-semibold text-sky-100">需要你判断</div>
                  <ul className="space-y-1 text-sky-50/75">
                    {latestRoundSummary.questions_for_user.slice(0, 3).map((item, idx) => <li key={idx}>• {item}</li>)}
                  </ul>
                </section>
              )}
            </div>
          </div>
        )}

        {/* Main stage: circular arrangement */}
        <div className="absolute inset-0 flex items-center justify-center pb-36">
          <div
            className="relative"
            style={{ width: stageRadius * 2 + 200, height: stageRadius * 2 + 200 }}
          >
            {/* Central table */}
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 100 }}
              className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 flex items-center justify-center"
            >
              <div
                className="w-40 h-40 rounded-full flex flex-col items-center justify-center backdrop-blur-md border border-white/20"
                style={{
                  background:
                    `radial-gradient(circle, color-mix(in srgb, ${modeTone.accent} 28%, transparent) 0%, color-mix(in srgb, ${modeTone.accent} 6%, transparent) 100%)`,
                  boxShadow:
                    `0 0 60px color-mix(in srgb, ${modeTone.accent} 30%, transparent), inset 0 0 40px color-mix(in srgb, ${modeTone.accent} 10%, transparent)`,
                }}
              >
                <span className="text-5xl mb-1">{scenarioMeta.icon}</span>
                <span className="text-[11px] text-white/70 uppercase tracking-widest">
                  {modeTone.label}
                </span>
                <span className="mt-1 max-w-[120px] text-center text-[10px] leading-tight text-white/45">
                  {hostSummary}
                </span>
              </div>
            </motion.div>

            {/* Radiating lines */}
            <svg
              className="absolute left-1/2 top-1/2 pointer-events-none"
              style={{
                width: stageRadius * 2 + 200,
                height: stageRadius * 2 + 200,
                transform: "translate(-50%, -50%)",
              }}
            >
              {positions.map((pos, i) => {
                const agent = participants[i];
                const isActive = agent && agent.id === activeAgentId;
                return (
                  <motion.line
                    key={`line-${i}`}
                    x1={stageRadius + 100}
                    y1={stageRadius + 100}
                    x2={stageRadius + 100 + pos.x}
                    y2={stageRadius + 100 + pos.y}
                    stroke={isActive ? agent?.color : "rgba(255,255,255,0.08)"}
                    strokeWidth={isActive ? 2 : 1}
                    initial={{ pathLength: 0, opacity: 0 }}
                    animate={{ pathLength: 1, opacity: isActive ? 0.8 : 0.25 }}
                    transition={{ duration: 0.4 }}
                  />
                );
              })}
            </svg>

            {/* Agents around the table */}
            {participants.map((agent, i) => {
              const pos = positions[i];
              const isActive = agent.id === activeAgentId;
              return (
                <div
                  key={agent.id}
                  className="absolute"
                  style={{
                    left: `calc(50% + ${pos.x}px)`,
                    top: `calc(50% + ${pos.y}px)`,
                  }}
                >
                  <div
                    style={{
                      transform: "translate(-50%, -50%)",
                      width: 160,
                      display: "flex",
                      justifyContent: "center",
                    }}
                  >
                    <motion.div
                      initial={{ scale: 0, opacity: 0 }}
                      animate={{
                        scale: isActive ? 1.15 : 1,
                        opacity: isActive ? 1 : 0.55,
                      }}
                      transition={{
                        type: "spring",
                        stiffness: 200,
                        damping: 20,
                        delay: i * 0.08,
                      }}
                      className="flex flex-col items-center relative"
                    >
                      <motion.div
                        animate={
                          isActive
                            ? {
                                boxShadow: [
                                  `0 0 20px ${agent.color}40`,
                                  `0 0 40px ${agent.color}80`,
                                  `0 0 20px ${agent.color}40`,
                                ],
                              }
                            : { boxShadow: "0 0 0px rgba(0,0,0,0)" }
                        }
                        transition={{ duration: 1.8, repeat: Infinity }}
                        className="w-20 h-20 rounded-full flex items-center justify-center text-4xl border-2 backdrop-blur-md"
                        style={{
                          backgroundColor: isActive
                            ? `color-mix(in srgb, ${agent.color} 35%, #0a0a12)`
                            : "rgba(255,255,255,0.08)",
                          borderColor: isActive ? agent.color : "rgba(255,255,255,0.15)",
                        }}
                      >
                        {agent.icon}
                      </motion.div>
                      <div className="mt-2 text-center whitespace-nowrap">
                        {isActive && (
                          <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.18em]" style={{ color: agent.color }}>
                            Speaking
                          </div>
                        )}
                        <div
                          className="text-sm font-semibold"
                          style={{ color: isActive ? agent.color : "rgba(255,255,255,0.7)" }}
                        >
                          {agent.name}
                        </div>
                        <div className="text-[10px] text-white/40 uppercase tracking-wide">
                          {agent.role}
                        </div>
                      </div>

                      {isActive && !currentContent && (
                        <motion.div
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="absolute -top-10 flex gap-1 px-3 py-1.5 rounded-full backdrop-blur-md"
                          style={{
                            backgroundColor: `color-mix(in srgb, ${agent.color} 30%, #0a0a12)`,
                            border: `1px solid ${agent.color}40`,
                          }}
                        >
                          <span className="w-1.5 h-1.5 rounded-full animate-bounce" style={{ backgroundColor: agent.color, animationDelay: "0ms" }} />
                          <span className="w-1.5 h-1.5 rounded-full animate-bounce" style={{ backgroundColor: agent.color, animationDelay: "150ms" }} />
                          <span className="w-1.5 h-1.5 rounded-full animate-bounce" style={{ backgroundColor: agent.color, animationDelay: "300ms" }} />
                        </motion.div>
                      )}
                    </motion.div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Floating speech bubble for current speaker (agent) */}
        <AnimatePresence mode="wait">
          {!showTranscript && activeAgent && currentContent && (
            <motion.div
              key={`bubble-${activeAgent.id}-${currentContent.length}`}
              initial={{ opacity: 0, y: 20, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -20, scale: 0.95 }}
              transition={{ duration: 0.3 }}
              className="absolute left-1/2 -translate-x-1/2 max-w-2xl w-[min(90vw,640px)] px-6 py-4 rounded-2xl backdrop-blur-xl z-20"
              style={{
                bottom: "calc(14vh + 80px)",
                backgroundColor: "rgba(255,255,255,0.95)",
                border: `2px solid ${activeAgent.color}`,
                boxShadow: `0 20px 60px -20px ${activeAgent.color}80, 0 0 0 6px ${activeAgent.color}15`,
              }}
            >
              <div className="flex items-start gap-3">
                <span
                  className="w-10 h-10 flex-shrink-0 rounded-full flex items-center justify-center text-xl"
                  style={{ backgroundColor: `${activeAgent.color}20` }}
                >
                  {activeAgent.icon}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: activeAgent.color }}>
                    {activeAgent.name} · {activeAgent.role}
                  </div>
                  <p className="text-[15px] leading-relaxed text-gray-800 whitespace-pre-wrap">
                    {clampSpeech(currentContent)}
                  </p>
                  {currentContent.length > 420 && (
                    <p className="mt-2 text-xs text-gray-500">完整内容已进入左侧完整记录。</p>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Floating user bubble (briefly shown after user sends) */}
        <AnimatePresence>
          {!showTranscript && userBubble && !activeAgent && (
            <motion.div
              key={`user-bubble-${userBubble}`}
              initial={{ opacity: 0, y: 30, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -10, scale: 0.95 }}
              className="absolute left-1/2 -translate-x-1/2 max-w-2xl w-[min(90vw,640px)] px-6 py-4 rounded-2xl backdrop-blur-xl z-20"
              style={{
                bottom: "calc(14vh + 80px)",
                backgroundColor: "rgba(251, 191, 36, 0.95)",
                border: `2px solid ${USER_COLOR}`,
                boxShadow: `0 20px 60px -20px ${USER_COLOR}80, 0 0 0 6px ${USER_COLOR}15`,
              }}
            >
              <div className="flex items-start gap-3">
                <span className="w-10 h-10 flex-shrink-0 rounded-full flex items-center justify-center text-xl bg-white/30">
                  {USER_ICON}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-semibold uppercase tracking-wide mb-1 text-gray-900">
                    你 · 老板
                  </div>
                  <p className="text-[15px] leading-relaxed text-gray-900 whitespace-pre-wrap">
                    {userBubble}
                  </p>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Decision result card */}
        {decisionResult && !showTranscript && (
          <div className="absolute right-8 top-24 z-30 w-[360px] rounded-2xl border border-emerald-300/25 bg-slate-950/90 p-4 text-white shadow-2xl backdrop-blur-xl">
            <div className="mb-2 flex items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-emerald-200/70">Decision</p>
                <h3 className="text-base font-semibold">推荐：{decisionResult.recommended_option}</h3>
              </div>
              <span className="rounded-full bg-emerald-400/15 px-2 py-1 text-[11px] text-emerald-100">{decisionResult.status}</span>
            </div>
            {decisionResult.handoff_status && decisionResult.handoff_status !== "none" ? (
              <div className="mb-3 rounded-xl border border-white/10 bg-white/5 p-2 text-xs text-white/65">
                交接状态：{decisionResult.handoff_status}{decisionResult.user_choice ? ` · 选择：${decisionResult.user_choice}` : ""}
              </div>
            ) : null}
            {decisionContextItems.length > 0 ? (
              <div className="mb-3 rounded-xl border border-emerald-300/20 bg-emerald-300/10 p-2 text-xs text-emerald-50">
                <div className="mb-1 font-semibold">为什么这样建议</div>
                <div className="space-y-1.5">
                  {decisionContextItems.map((item) => (
                    <div key={item.key}>
                      <div className="font-medium">{item.label}：{item.summary}</div>
                      <div className="text-emerald-50/70">{item.impact}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            {protocolPhases.length > 0 ? (
              <div className="mb-3 rounded-xl border border-white/10 bg-white/5 p-2 text-xs text-white/65">
                <div className="mb-1 font-semibold text-white/80">场景协议</div>
                <div className="flex flex-wrap gap-1.5">
                  {protocolPhases.slice(0, 5).map((item) => (
                    <span key={item} className="rounded-full bg-white/10 px-2 py-1 text-[11px]">{item}</span>
                  ))}
                </div>
              </div>
            ) : null}
            <p className="mb-3 text-sm leading-relaxed text-white/75">{decisionResult.summary}</p>
            <div className="mb-3 space-y-2">
              {decisionResult.tradeoffs.slice(0, 2).map((item, idx) => (
                <div key={`${item.option}-${idx}`} className="rounded-xl bg-white/5 p-2 text-xs text-white/70">
                  <div className="font-medium text-white/90">{item.option}</div>
                  <div>利：{item.pros?.join("、") || "—"}</div>
                  <div>弊：{item.cons?.join("、") || "—"}</div>
                </div>
              ))}
            </div>
            <div className="mb-4">
              <div className="mb-1 text-xs font-semibold text-white/80">下一步动作</div>
              <ul className="space-y-1 text-xs text-white/65">
                {decisionResult.actions.slice(0, 3).map((action, idx) => (
                  <li key={idx}>• {String(action.title ?? action.owner ?? "待执行动作")}</li>
                ))}
              </ul>
            </div>
            {acceptedPendingAction && (
              <div className="mb-3 rounded-xl border border-amber-300/25 bg-amber-300/10 p-2 text-xs text-amber-50">
                已生成待确认卡：{acceptedPendingAction.title}。请到 Maxwell / 待确认动作中最终确认，不会直接改日程。
              </div>
            )}
            {scenarioRouteButtons.length > 0 && (
              <div className="mb-3 rounded-xl border border-white/10 bg-white/5 p-2 text-xs text-white/70">
                <div className="mb-2 font-semibold text-white/80">下一轮路线</div>
                <div className="flex flex-wrap gap-1.5">
                  {scenarioRouteButtons.map((route) => (
                    <button
                      key={`${route.targetStage ?? route.label}-${route.prompt}`}
                      type="button"
                      onClick={() => setUserDraft(route.prompt)}
                      disabled={status === "streaming"}
                      className="rounded-lg bg-white/10 px-2 py-1 text-[11px] text-white/75 transition-colors hover:bg-white/15 disabled:opacity-45"
                    >
                      {route.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <div className="grid grid-cols-3 gap-2 text-xs">
              <button
                onClick={handleAcceptDecision}
                disabled={decisionBusy || decisionResult.status === "accepted"}
                className="rounded-lg bg-emerald-400 px-2 py-2 font-medium text-slate-950 disabled:opacity-50"
              >
                接受建议
              </button>
              <button onClick={handleClose} className="rounded-lg bg-white/10 px-2 py-2 text-white/80 hover:bg-white/15">
                关闭圆桌
              </button>
              <button
                onClick={() => handleReturnToPrivateChat(decisionResult.recommended_option || "return_to_private_chat")}
                disabled={returnBusy || decisionResult.handoff_status === "returned"}
                className="rounded-lg bg-indigo-400/90 px-2 py-2 font-medium text-white disabled:opacity-50"
              >
                带总结回私聊
              </button>
            </div>
          </div>
        )}

        {/* Brainstorm result card */}
        {brainstormResult && !decisionResult && !showTranscript && (
          <div className="absolute right-8 top-24 z-30 w-[380px] rounded-2xl border border-violet-300/25 bg-slate-950/90 p-4 text-white shadow-2xl backdrop-blur-xl">
            <div className="mb-2 flex items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-violet-200/70">Brainstorm</p>
                <h3 className="text-base font-semibold">灵感结果</h3>
              </div>
              <span className="rounded-full bg-violet-400/15 px-2 py-1 text-[11px] text-violet-100">{brainstormResult.status}</span>
            </div>
            {brainstormResult.handoff_status && brainstormResult.handoff_status !== "none" ? (
              <div className="mb-3 rounded-xl border border-white/10 bg-white/5 p-2 text-xs text-white/65">
                交接状态：{brainstormResult.handoff_status}{brainstormResult.user_choice ? ` · 选择：${brainstormResult.user_choice}` : ""}
              </div>
            ) : null}
            <p className="mb-3 line-clamp-4 text-sm leading-relaxed text-white/75">{brainstormResult.summary}</p>
            {protocolPhases.length > 0 ? (
              <div className="mb-3 rounded-xl border border-white/10 bg-white/5 p-2 text-xs text-white/65">
                <div className="mb-1 font-semibold text-white/80">场景协议</div>
                <div className="flex flex-wrap gap-1.5">
                  {protocolPhases.slice(0, 6).map((item) => (
                    <span key={item} className="rounded-full bg-white/10 px-2 py-1 text-[11px]">{item}</span>
                  ))}
                </div>
              </div>
            ) : null}
            {localRankedActivities.length > 0 && (
              <div className="mb-3 space-y-2">
                <div className="text-xs font-semibold text-emerald-100">本地活动排序</div>
                {localRankedActivities.slice(0, 3).map((activity, idx) => (
                  <div key={`${activity.id ?? idx}`} className="rounded-xl bg-emerald-300/10 p-2 text-xs text-emerald-50/75">
                    <div className="font-medium text-emerald-50">{idx + 1}. {titleOf(activity, `候选活动 ${idx + 1}`)}</div>
                    {typeof activity.reason === "string" && <div className="text-emerald-50/55">{activity.reason}</div>}
                  </div>
                ))}
              </div>
            )}
            {(workRisks.length > 0 || workValidationSteps.length > 0) && (
              <div className="mb-3 space-y-2">
                {workRisks.length > 0 && (
                  <div>
                    <div className="mb-1 text-xs font-semibold text-amber-100">关键风险</div>
                    <ul className="space-y-1 text-xs text-amber-50/75">
                      {workRisks.slice(0, 3).map((risk, idx) => (
                        <li key={idx}>• {titleOf(risk, `风险 ${idx + 1}`)}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {workValidationSteps.length > 0 && (
                  <div>
                    <div className="mb-1 text-xs font-semibold text-violet-100">最小验证</div>
                    <ul className="space-y-1 text-xs text-violet-50/75">
                      {workValidationSteps.slice(0, 4).map((step, idx) => <li key={idx}>• {step}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            )}
            <div className="mb-3">
              <div className="mb-1 text-xs font-semibold text-white/80">主题</div>
              <div className="flex flex-wrap gap-1.5">
                {brainstormResult.themes.slice(0, 3).map((theme, idx) => (
                  <span key={`${theme.title}-${idx}`} className="rounded-full bg-white/10 px-2 py-1 text-[11px] text-white/75">
                    {theme.title || "主题"}
                  </span>
                ))}
              </div>
            </div>
            <div className="mb-3 space-y-2">
              <div className="text-xs font-semibold text-white/80">候选想法</div>
              {brainstormResult.ideas.slice(0, 4).map((idea, idx) => (
                <div key={`${idea.id}-${idx}`} className="rounded-xl bg-white/5 p-2 text-xs text-white/70">
                  <div className="font-medium text-white/90">{idea.title}</div>
                  {idea.source_agent && <div className="text-white/40">from {idea.source_agent}</div>}
                </div>
              ))}
            </div>
            <div className="mb-4 rounded-xl bg-amber-300/10 p-2 text-xs text-amber-50">
              不会自动写计划或改日程；保存灵感或转计划都需要你点击确认。
            </div>
            {savedBrainstormMemory && (
              <div className="mb-3 rounded-xl border border-emerald-300/25 bg-emerald-300/10 p-2 text-xs text-emerald-50">
                已保存为记忆：#{savedBrainstormMemory.id}
              </div>
            )}
            {brainstormPendingAction && (
              <div className="mb-3 rounded-xl border border-amber-300/25 bg-amber-300/10 p-2 text-xs text-amber-50">
                已生成 Maxwell 待确认计划卡：{brainstormPendingAction.title}
              </div>
            )}
            {scenarioRouteButtons.length > 0 && (
              <div className="mb-3 rounded-xl border border-white/10 bg-white/5 p-2 text-xs text-white/70">
                <div className="mb-2 font-semibold text-white/80">下一轮路线</div>
                <div className="flex flex-wrap gap-1.5">
                  {scenarioRouteButtons.map((route) => (
                    <button
                      key={`${route.targetStage ?? route.label}-${route.prompt}`}
                      type="button"
                      onClick={() => setUserDraft(route.prompt)}
                      disabled={status === "streaming"}
                      className="rounded-lg bg-white/10 px-2 py-1 text-[11px] text-white/75 transition-colors hover:bg-white/15 disabled:opacity-45"
                    >
                      {route.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <div className="grid grid-cols-2 gap-2 text-xs">
              <button
                onClick={handleSaveBrainstorm}
                disabled={brainstormBusy !== null || brainstormResult.save_as_memory}
                className="rounded-lg bg-violet-400 px-2 py-2 font-medium text-slate-950 disabled:opacity-50"
              >
                保存灵感
              </button>
              <button
                onClick={() => setUserDraft("我想继续沿着这个方向发散：")}
                className="rounded-lg bg-white/10 px-2 py-2 text-white/80 hover:bg-white/15"
              >
                继续讨论
              </button>
              <button
                onClick={handleBrainstormToPlan}
                disabled={brainstormBusy !== null || brainstormResult.status === "handoff_pending"}
                className="rounded-lg bg-indigo-400/90 px-2 py-2 font-medium text-white disabled:opacity-50"
              >
                转成计划
              </button>
              <button
                onClick={() => handleReturnToPrivateChat("brainstorm_return_to_private_chat")}
                disabled={returnBusy || brainstormResult.handoff_status === "returned"}
                className="rounded-lg bg-white/10 px-2 py-2 text-white/80 hover:bg-white/15 disabled:opacity-50"
              >
                带总结回私聊
              </button>
            </div>
          </div>
        )}

        {/* Bottom: user input bar */}
        <div
          className="absolute bottom-0 left-0 right-0 z-40 px-8 py-5 border-t border-white/10 backdrop-blur-xl"
          style={{
            background:
              "linear-gradient(180deg, transparent, rgba(5,5,10,0.6) 40%, rgba(5,5,10,0.9))",
            paddingBottom: "20px",
          }}
        >
          {waitingForCheckpoint && GRAPH_ROUNDTABLE_SCENARIOS.has(scenarioId) && (
            <div className="mx-auto mb-3 flex max-w-3xl items-center gap-2 text-xs">
              <button
                onClick={() => setUserDraft("继续讨论：")}
                className="rounded-lg border border-white/10 bg-white/10 px-3 py-2 text-white/75 hover:bg-white/15"
              >
                继续讨论
              </button>
              <button
                onClick={() => setUserDraft("直接收敛")}
                className="rounded-lg bg-emerald-300 px-3 py-2 font-medium text-slate-950"
              >
                直接收敛
              </button>
              <span className="text-white/40">也可以直接输入你的补充意见。</span>
            </div>
          )}
          <div className="max-w-3xl mx-auto flex items-center gap-3">
            <div className="w-10 h-10 rounded-full flex items-center justify-center text-xl flex-shrink-0" style={{ backgroundColor: USER_COLOR + "30", border: `2px solid ${USER_COLOR}` }}>
              {USER_ICON}
            </div>
            <input
              type="text"
              value={userDraft}
              onChange={(e) => setUserDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSendUserMessage();
                }
              }}
              disabled={status === "streaming"}
              placeholder={
                status === "streaming"
                  ? "agents 正在讨论…稍等你的回合"
                  : "作为老板，你也可以加入讨论。按 Enter 发送"
              }
              className="flex-1 px-4 py-3 rounded-xl bg-white/10 border border-white/20 text-white placeholder:text-white/40 text-sm outline-none focus:border-white/50 transition-colors disabled:opacity-50"
            />
            <button
              onClick={handleSendUserMessage}
              disabled={status === "streaming" || !userDraft.trim()}
              className="w-11 h-11 rounded-xl flex items-center justify-center transition-all disabled:opacity-30"
              style={{
                backgroundColor: userDraft.trim() && status !== "streaming" ? USER_COLOR : "rgba(255,255,255,0.1)",
                color: userDraft.trim() && status !== "streaming" ? "#0a0a12" : "white",
              }}
              aria-label="发送"
            >
              <Send size={18} />
            </button>
          </div>
        </div>

        {/* Transcript drawer on the left */}
        <AnimatePresence>
          {showTranscript && (
            <motion.div
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", stiffness: 120, damping: 22 }}
              className="absolute left-0 top-0 bottom-0 z-40 w-full max-w-[440px]"
            >
              <div
                className="h-full backdrop-blur-xl overflow-hidden flex flex-col shadow-2xl"
                style={{
                  background: "rgba(8, 8, 16, 0.96)",
                  borderRight: "1px solid rgba(255,255,255,0.12)",
                }}
              >
                <div className="px-5 py-4 border-b border-white/10 flex items-center justify-between flex-shrink-0">
                  <div>
                    <h3 className="text-sm font-semibold text-white/90">
                      完整记录 ({transcript.length})
                    </h3>
                    <p className="text-[11px] text-white/40 mt-0.5">
                      所有智能体的讨论发言会按时间顺序显示在这里
                    </p>
                  </div>
                  <button
                    onClick={() => setShowTranscript(false)}
                    className="text-xs text-white/50 hover:text-white/80"
                  >
                    关闭
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto px-5 py-4 space-y-3">
                  {transcript.length === 0 && (
                    <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-6 text-center">
                      <p className="text-white/60 text-sm">暂时还没有记录</p>
                      <p className="text-white/35 text-xs mt-1">
                        等智能体开始发言后，完整讨论会显示在这里。
                      </p>
                    </div>
                  )}
                  {transcript.map((entry) => (
                    <motion.div
                      key={entry.key}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      className="flex gap-3 rounded-xl border border-white/10 bg-white/[0.04] p-3"
                    >
                      <span
                        className="w-8 h-8 flex-shrink-0 rounded-full flex items-center justify-center text-lg"
                        style={{
                          backgroundColor: entry.kind === "user" ? `${USER_COLOR}30` : `${entry.agentColor}25`,
                        }}
                      >
                        {entry.agentIcon}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div
                          className="text-xs font-semibold mb-1"
                          style={{ color: entry.kind === "user" ? USER_COLOR : entry.agentColor }}
                        >
                          {entry.agentName}
                        </div>
                        <p
                          className={`text-sm leading-relaxed whitespace-pre-wrap break-words ${
                            entry.kind === "user" ? "text-amber-100" : "text-white/85"
                          }`}
                        >
                          {entry.content}
                        </p>
                        {(entry.toolCount || entry.actionCount) ? (
                          <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
                            {entry.toolCount ? (
                              <span className="rounded-full bg-sky-300/15 px-2 py-0.5 text-sky-100">
                                工具 {entry.toolCount}
                              </span>
                            ) : null}
                            {entry.actionCount ? (
                              <span className="rounded-full bg-amber-300/15 px-2 py-0.5 text-amber-100">
                                待确认 {entry.actionCount}
                              </span>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                    </motion.div>
                  ))}
                  <div ref={transcriptEndRef} />
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Error state */}
        {status === "error" && errorMsg && (
          <div className="absolute top-20 left-1/2 -translate-x-1/2 z-40 px-4 py-2 rounded-lg bg-red-500/90 text-white text-sm">
            圆桌出错: {errorMsg}
          </div>
        )}
      </motion.div>
    </AnimatePresence>
  );
};
