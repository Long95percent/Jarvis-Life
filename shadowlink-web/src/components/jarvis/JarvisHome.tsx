import React, { useMemo, useState } from "react";
import { ChevronRight, Plus, UsersRound, X } from "lucide-react";
import { useJarvisStore } from "@/stores/jarvisStore";
import { AgentCard } from "./AgentCard";
import { ScenarioGrid } from "./ScenarioGrid";
import { RoundtableStage } from "./RoundtableStage";
import { AgentChatPanel } from "./AgentChatPanel";
import { TodayScheduleCard } from "./DashboardCards";
import { CalendarPanel } from "./CalendarPanel";
import { MemoryPanel } from "./MemoryPanel";
import { ConversationHistoryPanel } from "./ConversationHistoryPanel";
import { ProactiveMessageFeed } from "./ProactiveMessageFeed";
import { CareTrendsPanel } from "./CareTrendsPanel";

type SidePanelView = "history" | "memory" | "care" | "proactive";

function careMessageMatches(trigger: string, agentId: string): boolean {
  return (
    agentId === "mira" ||
    trigger.startsWith("care") ||
    trigger.includes("risk") ||
    trigger.includes("overload") ||
    trigger.includes("streak") ||
    trigger.includes("planner_missed")
  );
}

export const JarvisHome: React.FC = () => {
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [sidePanelView, setSidePanelView] = useState<SidePanelView | null>(null);

  const agents = useJarvisStore((state) => state.agents);
  const proactiveMessages = useJarvisStore((state) => state.proactiveMessages);
  const activeAgentId = useJarvisStore((state) => state.activeAgentId);
  const sessionId = useJarvisStore((state) => state.sessionId);
  const interactionMode = useJarvisStore((state) => state.interactionMode);
  const activeRoundtableScenario = useJarvisStore(
    (state) => state.activeRoundtableScenario,
  );
  const activeRoundtableInput = useJarvisStore(
    (state) => state.activeRoundtableInput,
  );
  const activeRoundtableSourceSessionId = useJarvisStore(
    (state) => state.activeRoundtableSourceSessionId,
  );
  const activeRoundtableSourceAgentId = useJarvisStore(
    (state) => state.activeRoundtableSourceAgentId,
  );

  const openPrivateChat = useJarvisStore((state) => state.openPrivateChat);
  const startRoundtable = useJarvisStore((state) => state.startRoundtable);
  const closeRoundtable = useJarvisStore((state) => state.closeRoundtable);
  const openExistingPrivateChat = useJarvisStore(
    (state) => state.openExistingPrivateChat,
  );
  const resetToScenarioGrid = useJarvisStore(
    (state) => state.resetToScenarioGrid,
  );
  const markMessageRead = useJarvisStore((state) => state.markMessageRead);

  const unreadCounts = useMemo(
    () =>
      Object.fromEntries(
        agents.map((agent) => [
          agent.id,
          proactiveMessages.filter(
            (message) => message.agent_id === agent.id && !message.read,
          ).length,
        ]),
      ),
    [agents, proactiveMessages],
  );

  const recentCareMessages = useMemo(
    () =>
      proactiveMessages.filter((message) =>
        careMessageMatches(message.trigger || "", message.agent_id),
      ),
    [proactiveMessages],
  );

  const activeAgent = agents.find((agent) => agent.id === activeAgentId) ?? agents[0];
  const isRoundtable = interactionMode === "roundtable";

  const openSidePanel = (view: SidePanelView) => setSidePanelView(view);
  const closeSidePanel = () => setSidePanelView(null);

  return (
    <div className="relative flex-1 min-h-0 overflow-hidden bg-[radial-gradient(circle_at_top_left,rgba(224,231,255,0.72),transparent_30%),linear-gradient(180deg,#f8fafc,#f3f5fb_48%,#eef2ff)]">
      <CalendarPanel open={calendarOpen} onClose={() => setCalendarOpen(false)} />

      <div className="grid h-full min-h-0 gap-4 p-4 lg:grid-cols-[304px_minmax(0,1fr)] xl:grid-cols-[304px_minmax(0,1fr)_332px]">
        <aside className="min-h-0 rounded-[32px] border border-white/70 bg-white/82 p-4 shadow-sm shadow-slate-200/70 backdrop-blur lg:row-span-2 xl:row-span-1">
          <div className="flex h-full min-h-0 flex-col">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-lg font-semibold text-slate-900">AI 团队</div>
                <div className="mt-1 text-sm text-slate-500">
                  选择一位搭档继续对话
                </div>
              </div>
              <button
                type="button"
                onClick={() => openPrivateChat(activeAgentId)}
                className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-slate-200 bg-white text-slate-500 transition hover:border-slate-300 hover:text-slate-900"
                title="开启新的私聊"
              >
                <Plus size={18} />
              </button>
            </div>

            <div className="mt-4 min-h-0 flex-1 space-y-1.5 pr-0.5">
              {agents.map((agent) => (
                <AgentCard
                  key={agent.id}
                  agent={agent}
                  isActive={agent.id === activeAgentId}
                  hasUnread={unreadCounts[agent.id] > 0}
                  unreadCount={unreadCounts[agent.id]}
                  onClick={() => openPrivateChat(agent.id)}
                />
              ))}
            </div>

            <button
              type="button"
              onClick={() => {
                closeSidePanel();
                resetToScenarioGrid();
              }}
              className={`mt-3 inline-flex min-h-[62px] items-center justify-center gap-2.5 rounded-[22px] border px-5 py-3.5 text-base font-semibold shadow-[0_18px_36px_-28px_rgba(79,70,229,0.5)] transition duration-200 ${
                interactionMode === "scenario_grid"
                  ? "border-indigo-300 bg-indigo-50 text-indigo-700"
                  : "border-indigo-300 bg-white text-indigo-700 hover:-translate-y-0.5 hover:border-indigo-400 hover:bg-indigo-50"
              }`}
            >
              <UsersRound size={19} strokeWidth={2.2} />
              开启圆桌会议
            </button>
          </div>
        </aside>

        <section
          className={`min-h-0 overflow-hidden rounded-[36px] border border-white/70 bg-white/92 shadow-[0_24px_60px_-32px_rgba(15,23,42,0.28)] backdrop-blur ${
            isRoundtable ? "lg:row-span-2 xl:col-span-2" : ""
          }`}
        >
          {interactionMode === "scenario_grid" ? (
            <div className="h-full min-h-[560px] overflow-hidden">
              <ScenarioGrid
                onStart={(scenarioId, userInput) =>
                  startRoundtable(scenarioId, userInput)
                }
              />
            </div>
          ) : null}

          {interactionMode === "roundtable" && activeRoundtableScenario ? (
            <RoundtableStage
              scenarioId={activeRoundtableScenario}
              userInput={activeRoundtableInput}
              sessionId={sessionId}
              sourceSessionId={activeRoundtableSourceSessionId}
              sourceAgentId={activeRoundtableSourceAgentId}
              onClose={closeRoundtable}
              onReturnToPrivateChat={(agentId, sourceSessionId) =>
                openExistingPrivateChat(agentId, sourceSessionId)
              }
            />
          ) : null}

          {interactionMode === "private_chat" && activeAgent ? (
            <AgentChatPanel
              agentId={activeAgent.id}
              sessionId={sessionId}
              onOpenHistory={() => openSidePanel("history")}
              onOpenMemory={() => openSidePanel("memory")}
              activeUtilityView={
                sidePanelView === "history" || sidePanelView === "memory"
                  ? sidePanelView
                  : null
              }
            />
          ) : null}
        </section>

        {!isRoundtable ? (
          <aside className="min-h-0 space-y-4 lg:col-start-2 xl:col-start-3">
            <TodayScheduleCard onOpenCalendar={() => setCalendarOpen(true)} />

            <CareTrendsPanel
              variant="compact"
              recentCareMessages={recentCareMessages}
              onOpenMira={() => openPrivateChat("mira")}
              onOpenDetails={() => openSidePanel("care")}
            />

            <section className="rounded-[28px] border border-white/70 bg-white/95 p-5 shadow-sm shadow-slate-200/60">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <div className="text-base font-semibold text-slate-800">
                    主动提醒
                  </div>
                  <div className="mt-1 text-xs text-slate-400">
                    来自各位 Agent 的及时提醒
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => openSidePanel("proactive")}
                  className="inline-flex items-center gap-1 text-sm font-medium text-indigo-600 transition hover:text-indigo-700"
                >
                  查看更多
                  <ChevronRight size={16} />
                </button>
              </div>

              <div className="max-h-[340px] overflow-y-auto pr-1">
                <ProactiveMessageFeed
                  messages={proactiveMessages}
                  onRead={(id) => void markMessageRead(id)}
                  variant="compact"
                  maxItems={4}
                />
              </div>
            </section>
          </aside>
        ) : null}
      </div>

      {sidePanelView ? (
        <>
          <button
            type="button"
            aria-label="关闭侧边面板"
            onClick={closeSidePanel}
            className="absolute inset-0 z-30 bg-slate-950/10"
          />

          <aside className="absolute inset-y-4 right-4 z-40 flex w-[min(460px,calc(100vw-2rem))] flex-col overflow-hidden rounded-[32px] border border-slate-200 bg-white p-4 shadow-[0_30px_80px_-28px_rgba(15,23,42,0.45)]">
            <div className="flex items-start justify-end gap-3">
              <button
                type="button"
                onClick={closeSidePanel}
                className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-slate-200 bg-white text-slate-500 transition hover:border-slate-300 hover:text-slate-900"
              >
                <X size={18} />
              </button>
            </div>

            <div className="mt-2 min-h-0 flex-1 overflow-hidden">
              {sidePanelView === "history" ? (
                <div className="flex h-full min-h-0 flex-col">
                  <ConversationHistoryPanel />
                </div>
              ) : null}

              {sidePanelView === "memory" ? (
                <div className="flex h-full min-h-0 flex-col">
                  <MemoryPanel />
                </div>
              ) : null}

              {sidePanelView === "care" ? (
                <div className="h-full min-h-0 overflow-y-auto pr-1">
                  <CareTrendsPanel
                    recentCareMessages={recentCareMessages}
                    onOpenMira={() => openPrivateChat("mira")}
                  />
                </div>
              ) : null}

              {sidePanelView === "proactive" ? (
                <div className="h-full min-h-0 overflow-y-auto pr-1">
                  <ProactiveMessageFeed
                    messages={proactiveMessages}
                    onRead={(id) => void markMessageRead(id)}
                  />
                </div>
              ) : null}
            </div>
          </aside>
        </>
      ) : null}
    </div>
  );
};
