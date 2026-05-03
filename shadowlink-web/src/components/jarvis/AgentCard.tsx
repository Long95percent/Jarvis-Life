import React from "react";
import type { JarvisAgent } from "@/services/jarvisApi";
import { JARVIS_AGENTS } from "./agentMeta";

interface Props {
  agent: JarvisAgent;
  isActive: boolean;
  hasUnread: boolean;
  unreadCount?: number;
  onClick: () => void;
}

export const AgentCard: React.FC<Props> = ({
  agent,
  isActive,
  hasUnread,
  unreadCount = 0,
  onClick,
}) => {
  const description = JARVIS_AGENTS[agent.id]?.description;

  return (
    <button
      type="button"
      onClick={onClick}
      className={`group relative flex w-full items-start gap-2.5 rounded-[20px] border px-3.5 py-2.5 text-left transition-all ${
        isActive
          ? "border-indigo-300 bg-white shadow-[0_14px_36px_-22px_rgba(99,102,241,0.7)]"
          : "border-transparent bg-transparent hover:border-slate-200 hover:bg-white/80"
      }`}
    >
      <div
        className="mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-[15px] border border-white/70 text-[1.6rem] shadow-sm"
        style={{
          background: `linear-gradient(135deg, color-mix(in srgb, ${agent.color} 18%, white), white)`,
        }}
      >
        {agent.icon}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-[1.02rem] font-semibold text-slate-950">
            {agent.name}
          </span>
          {hasUnread && unreadCount > 0 ? (
            <span className="inline-flex min-w-[20px] items-center justify-center rounded-full bg-rose-500 px-1.5 text-[11px] font-semibold text-white">
              {unreadCount}
            </span>
          ) : null}
        </div>
        <div className="mt-0.5 truncate text-[0.92rem] text-slate-700">{agent.role}</div>
        {description ? (
          <div className="mt-0.5 truncate text-[11px] leading-4 text-slate-500">
            {description}
          </div>
        ) : null}
      </div>

      <span
        className="mt-2 h-2.5 w-2.5 shrink-0 rounded-full self-start"
        style={{
          backgroundColor: isActive ? agent.color : "#10b981",
          boxShadow: isActive
            ? `0 0 0 5px color-mix(in srgb, ${agent.color} 18%, transparent)`
            : "none",
        }}
      />
    </button>
  );
};
