// shadowlink-web/src/components/jarvis/JarvisHome.tsx
import React, { useMemo, useState } from "react";
import { useJarvisStore } from "@/stores/jarvisStore";
import { AgentCard } from "./AgentCard";
import { ScenarioGrid } from "./ScenarioGrid";
import { RoundtableStage } from "./RoundtableStage";
import { AgentChatPanel } from "./AgentChatPanel";
import { DashboardCards } from "./DashboardCards";
import { CalendarPanel } from "./CalendarPanel";
import { MemoryPanel } from "./MemoryPanel";
import { ConversationHistoryPanel } from "./ConversationHistoryPanel";
import { ProactiveMessageFeed } from "./ProactiveMessageFeed";
import { CareTrendsPanel } from "./CareTrendsPanel";

/**
 * JarvisHome 鈥?the unified command center.
 *
 * Layout (CSS grid):
 *   鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? *   鈹? Zone 1: dashboard cards (schedule / state / wx)   鈹?              鈹? *   鈹溾攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? Zone 3:      鈹? *   鈹?                                                   鈹? proactive    鈹? *   鈹? Zone 2: interaction area                          鈹? feed         鈹? *   鈹? (scenarios 路 roundtable 路 private chat)           鈹?              鈹? *   鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹粹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹? */
export const JarvisHome: React.FC = () => {
  const [calendarOpen, setCalendarOpen] = useState(false);
  const agents = useJarvisStore((s) => s.agents);
  const proactiveMessages = useJarvisStore((s) => s.proactiveMessages);
  const activeAgentId = useJarvisStore((s) => s.activeAgentId);
  const sessionId = useJarvisStore((s) => s.sessionId);
  const interactionMode = useJarvisStore((s) => s.interactionMode);
  const activeRoundtableScenario = useJarvisStore(
    (s) => s.activeRoundtableScenario,
  );
  const activeRoundtableInput = useJarvisStore(
    (s) => s.activeRoundtableInput,
  );
  const activeRoundtableSourceSessionId = useJarvisStore((s) => s.activeRoundtableSourceSessionId);
  const activeRoundtableSourceAgentId = useJarvisStore((s) => s.activeRoundtableSourceAgentId);

  const openPrivateChat = useJarvisStore((s) => s.openPrivateChat);
  const startRoundtable = useJarvisStore((s) => s.startRoundtable);
  const closeRoundtable = useJarvisStore((s) => s.closeRoundtable);
  const openExistingPrivateChat = useJarvisStore((s) => s.openExistingPrivateChat);
  const resetToScenarioGrid = useJarvisStore((s) => s.resetToScenarioGrid);
  const markMessageRead = useJarvisStore((s) => s.markMessageRead);

  const unreadCounts = useMemo(
    () =>
      Object.fromEntries(
        agents.map((a) => [
          a.id,
          proactiveMessages.filter((m) => m.agent_id === a.id && !m.read).length,
        ]),
      ),
    [agents, proactiveMessages],
  );
  const recentCareMessages = useMemo(
    () => proactiveMessages.filter((message) => {
      const trigger = message.trigger || "";
      return message.agent_id === "mira" || trigger.startsWith("care") || trigger.includes("risk") || trigger.includes("overload") || trigger.includes("streak") || trigger.includes("planner_missed");
    }),
    [proactiveMessages],
  );

  return (
    <div
      className="flex-1 min-h-0 grid gap-4 p-4"
      style={{
        gridTemplateColumns: "minmax(0,1fr) 320px",
        gridTemplateRows: "auto minmax(0,1fr)",
        backgroundColor: "var(--color-background, #f9fafb)",
      }}
    >
      {/* Zone 1: dashboard cards (spans only the left column) */}
      <div className="col-start-1 row-start-1">
        <DashboardCards onOpenCalendar={() => setCalendarOpen(true)} />
      </div>

      <CalendarPanel open={calendarOpen} onClose={() => setCalendarOpen(false)} />

      {/* Zone 2: interaction area */}
      <section
        className="col-start-1 row-start-2 min-h-0 rounded-2xl border border-gray-200 bg-white overflow-hidden flex flex-col"
        style={{
          boxShadow:
            "0 4px 20px -8px color-mix(in srgb, var(--color-primary) 12%, transparent)",
        }}
      >
        {interactionMode === "scenario_grid" && (
          <div className="flex flex-1 min-h-0">
            {/* Agents quick launcher */}
            <div className="w-56 flex-shrink-0 border-r border-gray-100 bg-gray-50/40 p-3 overflow-y-auto">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 px-1">
                Agents
              </h3>
              <div className="grid grid-cols-2 gap-2">
                {agents.map((agent) => (
                  <AgentCard
                    key={agent.id}
                    agent={agent}
                    isActive={agent.id === activeAgentId}
                    hasUnread={unreadCounts[agent.id] > 0}
                    onClick={() => openPrivateChat(agent.id)}
                  />
                ))}
              </div>
              {agents.length === 0 && (
                <p className="text-xs text-gray-400 text-center py-4">
                  鍔犺浇涓€?                </p>
              )}
            </div>
            <div className="flex-1 min-w-0">
              <ScenarioGrid
                onStart={(scenarioId, userInput) =>
                  startRoundtable(scenarioId, userInput)
                }
              />
            </div>
          </div>
        )}

        {interactionMode === "roundtable" && activeRoundtableScenario && (
          <RoundtableStage
            scenarioId={activeRoundtableScenario}
            userInput={activeRoundtableInput}
            sessionId={sessionId}
            sourceSessionId={activeRoundtableSourceSessionId}
            sourceAgentId={activeRoundtableSourceAgentId}
            onClose={closeRoundtable}
            onReturnToPrivateChat={(agentId, sourceSessionId) => openExistingPrivateChat(agentId, sourceSessionId)}
          />
        )}

        {interactionMode === "private_chat" && (
          <AgentChatPanel
            agentId={activeAgentId}
            sessionId={sessionId}
            onClose={resetToScenarioGrid}
          />
        )}
      </section>
      {/* Zone 3: memory + proactive feed (spans both rows on the right) */}
      <aside
        className="col-start-2 row-start-1 row-span-2 min-h-0 flex flex-col gap-4 overflow-hidden"
      >
        <div className="flex-shrink-0">
          <CareTrendsPanel recentCareMessages={recentCareMessages} onOpenMira={() => openPrivateChat("mira")} />
        </div>
        <div className="min-h-0 flex-1">
          <MemoryPanel />
        </div>
        <section className="min-h-0 flex-[0.9] rounded-2xl border border-gray-200 bg-white p-4 overflow-hidden flex flex-col">
          <div className="flex items-start justify-between gap-2 mb-3">
            <div>
              <h3 className="text-sm font-semibold text-gray-700">主动提醒</h3>
            </div>
          </div>
          <div className="flex-1 min-h-0 overflow-y-auto pr-1">
            <ProactiveMessageFeed
              messages={proactiveMessages}
              onRead={(id) => void markMessageRead(id)}
            />
          </div>
        </section>
        <ConversationHistoryPanel />
      </aside>
    </div>
  );
};
