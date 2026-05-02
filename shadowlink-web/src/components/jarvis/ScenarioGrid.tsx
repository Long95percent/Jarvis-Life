// shadowlink-web/src/components/jarvis/ScenarioGrid.tsx
import React, { useEffect, useState } from "react";
import { jarvisScenarioApi, type Scenario } from "@/services/jarvisScenarioApi";
import { JARVIS_AGENTS } from "./agentMeta";

export type { Scenario } from "@/services/jarvisScenarioApi";
interface Props {
  onStart: (scenarioId: string, userInput: string) => void;
}

export const ScenarioGrid: React.FC<Props> = ({ onStart }) => {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [userInput, setUserInput] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await jarvisScenarioApi.listScenarios();
        if (!cancelled) setScenarios(data);
      } catch (err) {
        if (!cancelled) setError((err as Error).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleLaunch = (scenarioId: string) => {
    onStart(scenarioId, userInput.trim());
    setSelectedId(null);
    setUserInput("");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-sm text-gray-400">加载场景中…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-sm text-red-500">场景加载失败: {error}</p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-[var(--color-text)]">
          场景圆桌
        </h2>
        <p className="text-sm text-[var(--color-text-secondary,#6b7280)] mt-1">
          选择一个场景,各领域 agent 协同给出建议。
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {scenarios.map((s) => {
          const isSelected = selectedId === s.id;
          return (
            <div
              key={s.id}
              className="group relative rounded-2xl border border-gray-200 bg-white p-4 hover:shadow-lg transition-all cursor-pointer"
              style={{
                borderColor: isSelected ? "var(--color-primary)" : undefined,
                boxShadow: isSelected
                  ? "0 6px 24px -4px color-mix(in srgb, var(--color-primary) 30%, transparent)"
                  : undefined,
              }}
              onClick={() => setSelectedId(isSelected ? null : s.id)}
            >
              <div className="flex items-start gap-3">
                <span className="text-3xl">{s.icon}</span>
                <div className="min-w-0 flex-1">
                  <h3 className="font-semibold text-gray-800 truncate">
                    {s.name}
                  </h3>
                  <p className="text-xs text-gray-500 mt-0.5">{s.name_en}</p>
                  <p className="text-sm text-gray-600 mt-2 leading-snug">
                    {s.description}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-1 mt-3">
                {s.agents.slice(0, 4).map((aid) => {
                  const meta = JARVIS_AGENTS[aid];
                  return (
                    <span
                      key={aid}
                      className="w-7 h-7 rounded-full flex items-center justify-center text-sm border-2 border-white"
                      style={{
                        backgroundColor: meta
                          ? `color-mix(in srgb, ${meta.color} 18%, white)`
                          : "#f3f4f6",
                        marginLeft: -6,
                        zIndex: 10,
                      }}
                      title={aid}
                    >
                      {meta?.icon ?? "🤖"}
                    </span>
                  );
                })}
                <span className="ml-2 text-[10px] text-gray-400">
                  {s.agents.length} agents
                </span>
              </div>

              {isSelected && (
                <div
                  className="mt-3 space-y-2 animate-fade-in"
                  onClick={(e) => e.stopPropagation()}
                >
                  <textarea
                    className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/40 resize-none"
                    rows={2}
                    placeholder="补充你的诉求（可选）…"
                    value={userInput}
                    onChange={(e) => setUserInput(e.target.value)}
                  />
                  <button
                    className="w-full py-2 rounded-lg text-white text-sm font-medium transition-opacity hover:opacity-90"
                    style={{ backgroundColor: "var(--color-primary)" }}
                    onClick={() => handleLaunch(s.id)}
                  >
                    启动圆桌 · {s.name}
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
