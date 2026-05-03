// shadowlink-web/src/components/jarvis/ProactiveMessageFeed.tsx
import React from "react";
import type { ProactiveMessage } from "@/services/jarvisApi";
import { JARVIS_AGENTS } from "./agentMeta";
import { CareCard } from "./CareCard";

interface Props {
  messages: ProactiveMessage[];
  onRead: (id: string) => void;
  variant?: "full" | "compact";
  maxItems?: number;
}

export const ProactiveMessageFeed: React.FC<Props> = ({
  messages,
  onRead,
  variant = "full",
  maxItems,
}) => {
  const visibleMessages =
    typeof maxItems === "number" ? messages.slice(0, maxItems) : messages;

  if (visibleMessages.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-gray-400">暂无主动消息</p>
    );
  }

  if (variant === "compact") {
    return (
      <div className="space-y-3">
        {visibleMessages.map((msg) => {
          const meta = JARVIS_AGENTS[msg.agent_id];
          return (
            <button
              key={msg.id}
              type="button"
              onClick={() => onRead(msg.id)}
              className={`flex w-full items-start gap-3 rounded-2xl px-2 py-1 text-left transition ${
                msg.read ? "opacity-55" : "hover:bg-slate-50"
              }`}
            >
              <span className="mt-1 text-2xl">{meta?.icon ?? "🤖"}</span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-3">
                  <span
                    className="truncate text-sm font-semibold"
                    style={{ color: meta?.color || "#475569" }}
                  >
                    {msg.agent_name}
                  </span>
                  <span className="shrink-0 text-[11px] text-slate-400">
                    {new Date(msg.created_at).toLocaleTimeString("zh-CN", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
              <p className="mt-1 line-clamp-2 break-words text-sm leading-6 text-slate-600">
                  {msg.content}
                </p>
              </div>
              {!msg.read ? (
                <span className="mt-2 h-2.5 w-2.5 rounded-full bg-rose-500" />
              ) : null}
            </button>
          );
        })}
      </div>
    );
  }

  return (
      <div className="min-w-0 space-y-2">
      {visibleMessages.map((msg) => {
        const meta = JARVIS_AGENTS[msg.agent_id];
        if (msg.trigger?.startsWith("care") || msg.trigger?.includes("risk") || msg.trigger?.includes("overload") || msg.trigger?.includes("streak")) {
          return (
            <CareCard
              key={msg.id}
              message={msg}
              onFeedback={() => onRead(msg.id)}
            />
          );
        }
        return (
          <div
            key={msg.id}
            onClick={() => onRead(msg.id)}
            className={`flex min-w-0 gap-3 p-3 rounded-xl cursor-pointer transition-all
              ${msg.read ? "bg-gray-50 opacity-60" : "bg-white border border-gray-200 shadow-sm"}`}
          >
            <span className="text-2xl flex-shrink-0">{meta?.icon ?? "🤖"}</span>
            <div className="min-w-0">
              <div className="flex items-center gap-1 mb-0.5">
                <span className="text-xs font-semibold" style={{ color: meta?.color }}>{msg.agent_name}</span>
                {!msg.read && <span className="w-1.5 h-1.5 rounded-full bg-red-500" />}
              </div>
              <p className="break-words text-sm leading-snug text-gray-700">{msg.content}</p>
              <p className="text-[10px] text-gray-400 mt-1">
                {new Date(msg.created_at).toLocaleTimeString()}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
};
