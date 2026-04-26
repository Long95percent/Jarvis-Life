import React, { useEffect, useMemo, useState } from "react";
import { jarvisApi, type JarvisMemory } from "@/services/jarvisApi";

const MEMORY_KIND_OPTIONS = [
  { value: "", label: "全部" },
  { value: "preference", label: "偏好" },
  { value: "care_preference", label: "关心方式" },
  { value: "mood_signal", label: "情绪" },
  { value: "rhythm_signal", label: "作息" },
  { value: "long_term_goal", label: "长期目标" },
  { value: "relationship", label: "关系" },
  { value: "fact", label: "事实" },
  { value: "constraint", label: "约束" },
];

const KIND_LABELS: Record<string, string> = Object.fromEntries(
  MEMORY_KIND_OPTIONS.filter((item) => item.value).map((item) => [item.value, item.label]),
);

function formatTime(timestamp?: number | null): string {
  if (!timestamp) return "未使用";
  return new Date(timestamp * 1000).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function sensitivityClass(sensitivity: string): string {
  if (sensitivity === "sensitive") return "bg-red-50 text-red-600 border-red-100";
  if (sensitivity === "private") return "bg-amber-50 text-amber-700 border-amber-100";
  return "bg-gray-50 text-gray-500 border-gray-100";
}

export const MemoryPanel: React.FC = () => {
  const [memories, setMemories] = useState<JarvisMemory[]>([]);
  const [memoryKind, setMemoryKind] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const visibleMemories = useMemo(() => memories.slice(0, 8), [memories]);

  const loadMemories = async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await jarvisApi.listMemories({ memoryKind: memoryKind || undefined, limit: 30 });
      setMemories(items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载记忆失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadMemories();
  }, [memoryKind]);

  const handleDelete = async (memory: JarvisMemory) => {
    const ok = window.confirm(`确定删除这条记忆吗？\n\n${memory.content}`);
    if (!ok) return;
    setDeletingId(memory.id);
    setError(null);
    try {
      await jarvisApi.deleteMemory(memory.id);
      setMemories((items) => items.filter((item) => item.id !== memory.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除记忆失败");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <section className="min-h-0 rounded-2xl border border-gray-200 bg-white p-4 flex flex-col overflow-hidden">
      <div className="flex items-start justify-between gap-2 mb-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-700">长期记忆</h3>
          <p className="text-[11px] text-gray-400 mt-0.5">私聊后自动沉淀，可随时删除</p>
        </div>
        <button
          type="button"
          onClick={() => void loadMemories()}
          disabled={loading}
          className="text-xs px-2 py-1 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 disabled:opacity-50"
        >
          {loading ? "刷新中" : "刷新"}
        </button>
      </div>

      <select
        value={memoryKind}
        onChange={(event) => setMemoryKind(event.target.value)}
        className="mb-3 w-full rounded-lg border border-gray-200 bg-gray-50 px-2 py-1.5 text-xs text-gray-600 outline-none focus:border-blue-300"
      >
        {MEMORY_KIND_OPTIONS.map((item) => (
          <option key={item.value || "all"} value={item.value}>
            {item.label}
          </option>
        ))}
      </select>

      {error && (
        <div className="mb-2 rounded-lg bg-red-50 px-2 py-1.5 text-xs text-red-600">
          {error}
        </div>
      )}

      <div className="flex-1 min-h-0 overflow-y-auto space-y-2 pr-1">
        {!loading && visibleMemories.length === 0 && (
          <div className="rounded-xl border border-dashed border-gray-200 p-3 text-xs text-gray-400 leading-relaxed">
            还没有长期记忆。试着在私聊里告诉 Mira：“我最近备考雅思压力很大，别太频繁提醒我。”
          </div>
        )}

        {visibleMemories.map((memory) => (
          <article key={memory.id} className="rounded-xl border border-gray-100 bg-gray-50/60 p-3">
            <div className="flex items-center justify-between gap-2 mb-2">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[11px] text-blue-600">
                  {KIND_LABELS[memory.memory_kind] || memory.memory_kind}
                </span>
                <span className={`rounded-full border px-2 py-0.5 text-[11px] ${sensitivityClass(memory.sensitivity)}`}>
                  {memory.sensitivity === "normal" ? "普通" : memory.sensitivity === "private" ? "隐私" : "敏感"}
                </span>
              </div>
              <button
                type="button"
                onClick={() => void handleDelete(memory)}
                disabled={deletingId === memory.id}
                className="text-[11px] text-gray-400 hover:text-red-500 disabled:opacity-50"
              >
                {deletingId === memory.id ? "删除中" : "删除"}
              </button>
            </div>
            <p className="text-xs text-gray-700 leading-relaxed whitespace-pre-wrap">{memory.content}</p>
            <div className="mt-2 flex items-center justify-between text-[10px] text-gray-400">
              <span>{memory.source_agent}</span>
              <span>上次使用：{formatTime(memory.last_used_at)}</span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
};
