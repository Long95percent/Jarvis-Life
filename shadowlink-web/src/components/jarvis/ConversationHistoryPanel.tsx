import React, { useEffect, useState } from "react";
import { jarvisApi, type ConversationHistoryItem } from "@/services/jarvisApi";
import { useJarvisStore } from "@/stores/jarvisStore";

export const JARVIS_CONVERSATION_HISTORY_CHANGED = "jarvis:conversation-history-changed";

function formatTime(timestamp?: number | null): string {
  if (!timestamp) return "未打开";
  return new Date(timestamp * 1000).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function typeLabel(type: string): string {
  if (type === "private_chat") return "私聊";
  if (type === "brainstorm") return "Brainstorm";
  if (type === "roundtable") return "圆桌";
  return type;
}

export const ConversationHistoryPanel: React.FC = () => {
  const openConversation = useJarvisStore((s) => s.openConversation);
  const [items, setItems] = useState<ConversationHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [openingId, setOpeningId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await jarvisApi.listConversationHistory(30));
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载历史对话失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    const refresh = () => void load();
    window.addEventListener(JARVIS_CONVERSATION_HISTORY_CHANGED, refresh);
    window.addEventListener("focus", refresh);
    return () => {
      window.removeEventListener(JARVIS_CONVERSATION_HISTORY_CHANGED, refresh);
      window.removeEventListener("focus", refresh);
    };
  }, []);

  const handleOpen = async (item: ConversationHistoryItem) => {
    setOpeningId(item.id);
    setError(null);
    try {
      await openConversation(item);
      setItems((current) =>
        current.map((entry) =>
          entry.id === item.id ? { ...entry, last_opened_at: Date.now() / 1000 } : entry,
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "打开历史对话失败");
    } finally {
      setOpeningId(null);
    }
  };

  const handleDelete = async (item: ConversationHistoryItem) => {
    const ok = window.confirm(`确定删除这条历史对话吗？\n\n${item.title}`);
    if (!ok) return;
    setDeletingId(item.id);
    setError(null);
    try {
      await jarvisApi.deleteConversationHistory(item.id);
      setItems((current) => current.filter((entry) => entry.id !== item.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除历史对话失败");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <section className="min-h-0 flex-1 rounded-2xl border border-gray-200 bg-white p-4 overflow-hidden flex flex-col">
      <div className="flex items-start justify-between gap-2 mb-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-700">历史对话</h3>
          <p className="text-[11px] text-gray-400 mt-0.5">7 天未打开会自动清理</p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="text-xs px-2 py-1 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 disabled:opacity-50"
        >
          {loading ? "刷新中" : "刷新"}
        </button>
      </div>

      {error && (
        <div className="mb-2 rounded-lg bg-red-50 px-2 py-1.5 text-xs text-red-600">
          {error}
        </div>
      )}

      <div className="flex-1 min-h-0 overflow-y-auto space-y-2 pr-1">
        {!loading && items.length === 0 && (
          <div className="rounded-xl border border-dashed border-gray-200 p-3 text-xs text-gray-400 leading-relaxed">
            暂无历史对话。开始一次私聊、圆桌或 Brainstorm 后会出现在这里。
          </div>
        )}

        {items.map((item) => (
          <article key={item.id} className="rounded-xl border border-gray-100 bg-gray-50/60 p-3">
            <div className="flex items-center justify-between gap-2 mb-2">
              <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] text-indigo-600">
                {typeLabel(item.conversation_type)}
              </span>
              <button
                type="button"
                onClick={() => void handleDelete(item)}
                disabled={deletingId === item.id}
                className="text-[11px] text-gray-400 hover:text-red-500 disabled:opacity-50"
              >
                {deletingId === item.id ? "删除中" : "删除"}
              </button>
            </div>
            <button
              type="button"
              onClick={() => void handleOpen(item)}
              disabled={openingId === item.id}
              className="block w-full text-left text-xs font-medium text-gray-700 hover:text-indigo-600 disabled:opacity-50"
            >
              {openingId === item.id ? "打开中…" : item.title}
            </button>
            <div className="mt-2 flex items-center justify-between text-[10px] text-gray-400">
              <span>{formatTime(item.updated_at)}</span>
              <span>上次打开：{formatTime(item.last_opened_at)}</span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
};
