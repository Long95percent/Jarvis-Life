// shadowlink-web/src/components/jarvis/JarvisHome.tsx
import React, { useMemo, useState } from "react";
import { useJarvisStore } from "@/stores/jarvisStore";
import { AgentCard } from "./AgentCard";
import { ProactiveMessageFeed } from "./ProactiveMessageFeed";
import { ScenarioGrid } from "./ScenarioGrid";
import { RoundtableStage } from "./RoundtableStage";
import { AgentChatPanel } from "./AgentChatPanel";
import { DashboardCards } from "./DashboardCards";
import { CalendarPanel } from "./CalendarPanel";

/**
 * JarvisHome — the unified command center.
 *
 * Layout (CSS grid):
 *   ┌────────────────────────────────────────────────────┬───────────────┐
 *   │  Zone 1: dashboard cards (schedule / state / wx)   │               │
 *   ├────────────────────────────────────────────────────┤  Zone 3:      │
 *   │                                                    │  proactive    │
 *   │  Zone 2: interaction area                          │  feed         │
 *   │  (scenarios · roundtable · private chat)           │               │
 *   └────────────────────────────────────────────────────┴───────────────┘
 */
export const JarvisHome: React.FC = () => {
  const [calendarOpen, setCalendarOpen] = useState(false);
  const agents = useJarvisStore((s) => s.agents);
  const proactiveMessages = useJarvisStore((s) => s.proactiveMessages);
  const markMessageRead = useJarvisStore((s) => s.markMessageRead);
  const activeAgentId = useJarvisStore((s) => s.activeAgentId);
  const interactionMode = useJarvisStore((s) => s.interactionMode);
  const activeRoundtableScenario = useJarvisStore(
    (s) => s.activeRoundtableScenario,
  );
  const activeRoundtableInput = useJarvisStore(
    (s) => s.activeRoundtableInput,
  );

  const openPrivateChat = useJarvisStore((s) => s.openPrivateChat);
  const startRoundtable = useJarvisStore((s) => s.startRoundtable);
  const closeRoundtable = useJarvisStore((s) => s.closeRoundtable);
  const resetToScenarioGrid = useJarvisStore((s) => s.resetToScenarioGrid);

  const sessionId = useMemo(() => `jarvis-${Date.now()}`, []);
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
                  加载中…
                </p>
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
            onClose={closeRoundtable}
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

      {/* Zone 3: proactive feed (spans both rows on the right) */}
      <aside
        className="col-start-2 row-start-1 row-span-2 min-h-0 rounded-2xl border border-gray-200 bg-white p-4 overflow-hidden flex flex-col"
      >
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-700">主动消息</h3>
          {proactiveMessages.filter((m) => !m.read).length > 0 && (
            <span className="px-1.5 py-0.5 rounded-full bg-red-100 text-red-600 text-xs">
              {proactiveMessages.filter((m) => !m.read).length}
            </span>
          )}
        </div>
        <div className="flex-1 min-h-0 overflow-y-auto -mx-1 px-1">
          <ProactiveMessageFeed
            messages={proactiveMessages}
            onRead={markMessageRead}
          />
        </div>
      </aside>
    </div>
  );
};
