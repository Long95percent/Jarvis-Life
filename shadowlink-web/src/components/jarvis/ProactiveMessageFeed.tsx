// shadowlink-web/src/components/jarvis/ProactiveMessageFeed.tsx
import React from "react";
import type { ProactiveMessage } from "@/services/jarvisApi";
import { JARVIS_AGENTS } from "./agentMeta";

interface Props {
  messages: ProactiveMessage[];
  onRead: (id: string) => void;
}

export const ProactiveMessageFeed: React.FC<Props> = ({ messages, onRead }) => {
  if (messages.length === 0) {
    return <p className="text-sm text-gray-400 text-center py-4">暂无主动消息</p>;
  }

  return (
    <div className="space-y-2">
      {messages.map((msg) => {
        const meta = JARVIS_AGENTS[msg.agent_id];
        return (
          <div
            key={msg.id}
            onClick={() => onRead(msg.id)}
            className={`flex gap-3 p-3 rounded-xl cursor-pointer transition-all
              ${msg.read ? "bg-gray-50 opacity-60" : "bg-white border border-gray-200 shadow-sm"}`}
          >
            <span className="text-2xl flex-shrink-0">{meta?.icon ?? "🤖"}</span>
            <div className="min-w-0">
              <div className="flex items-center gap-1 mb-0.5">
                <span className="text-xs font-semibold" style={{ color: meta?.color }}>{msg.agent_name}</span>
                {!msg.read && <span className="w-1.5 h-1.5 rounded-full bg-red-500" />}
              </div>
              <p className="text-sm text-gray-700 leading-snug">{msg.content}</p>
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
