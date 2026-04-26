// shadowlink-web/src/components/jarvis/RoundtableStage.tsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send } from "lucide-react";
import { JARVIS_AGENTS } from "./agentMeta";
import { jarvisApi } from "@/services/jarvisApi";

interface Props {
  scenarioId: string;
  userInput: string;
  sessionId: string;
  modeId?: string;
  onClose: () => void;
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
}

interface SpeakPayload {
  agent_id: string;
  agent_name: string;
  agent_role?: string;
  agent_icon?: string;
  agent_color?: string;
  content?: string;
  phase?: string;
}

interface TokenPayload {
  agent_id: string;
  agent_name: string;
  content: string;
}

interface PhasePayload {
  phase: string;
  scenario_name?: string;
  participants?: string[];
  round_count?: number;
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
};

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

function normalizeAgentReply(content: string, agentName: string): string {
  const trimmed = content.trim();
  if (/^\(?Agent\s+[^\s)]+\s+暂无回复\)?$/i.test(trimmed)) {
    return `${agentName} 当前没有拿到模型回复。请检查 AI 服务是否已重启，并确认设置里的 Provider API Key、Base URL、模型名称可用。`;
  }
  return content;
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

export const RoundtableStage: React.FC<Props> = ({
  scenarioId,
  userInput,
  sessionId,
  modeId = "general",
  onClose,
}) => {
  const [participants, setParticipants] = useState<AgentMeta[]>([]);
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [activeAgentId, setActiveAgentId] = useState<string | null>(null);
  const [currentContent, setCurrentContent] = useState<string>("");
  const [phase, setPhase] = useState<string>("connecting");
  const [status, setStatus] = useState<"connecting" | "streaming" | "idle" | "error">("connecting");
  const [roundCount, setRoundCount] = useState<number>(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showTranscript, setShowTranscript] = useState(false);

  const [userDraft, setUserDraft] = useState<string>("");
  const [userBubble, setUserBubble] = useState<string | null>(null);

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
        complete: "缁撴潫",
      };
      setPhase(phaseMap[payload.phase] ?? payload.phase);
      if (payload.round_count) setRoundCount(payload.round_count);
      setCurrentContent("");
      setActiveAgentId(null);
      return;
    }

    if (event === "agent_speak") {
      const payload = data as SpeakPayload;
      const normalizedContent = payload.content
        ? normalizeAgentReply(payload.content, payload.agent_name)
        : "";
      setActiveAgentId(payload.agent_id);
      setCurrentContent(normalizedContent);
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

  const stageRadius = 220;
  const positions = useMemo(
    () => computeAgentPositions(participants.length, stageRadius),
    [participants.length],
  );

  const activeAgent = participants.find((p) => p.id === activeAgentId);

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
            "radial-gradient(ellipse at center, color-mix(in srgb, var(--color-primary) 18%, #0a0a12) 0%, #05050a 75%)",
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
                    "radial-gradient(circle, color-mix(in srgb, var(--color-primary) 25%, transparent) 0%, color-mix(in srgb, var(--color-primary) 5%, transparent) 100%)",
                  boxShadow:
                    "0 0 60px color-mix(in srgb, var(--color-primary) 30%, transparent), inset 0 0 40px color-mix(in srgb, var(--color-primary) 10%, transparent)",
                }}
              >
                <span className="text-5xl mb-1">{scenarioMeta.icon}</span>
                <span className="text-[11px] text-white/70 uppercase tracking-widest">
                  Roundtable
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
                    {currentContent}
                  </p>
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

        {/* Bottom: user input bar */}
        <div
          className="absolute bottom-0 left-0 right-0 z-40 px-8 py-5 border-t border-white/10 backdrop-blur-xl"
          style={{
            background:
              "linear-gradient(180deg, transparent, rgba(5,5,10,0.6) 40%, rgba(5,5,10,0.9))",
            paddingBottom: "20px",
          }}
        >
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
