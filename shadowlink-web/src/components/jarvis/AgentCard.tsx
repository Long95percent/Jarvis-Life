// shadowlink-web/src/components/jarvis/AgentCard.tsx
import React from "react";
import type { JarvisAgent } from "@/services/jarvisApi";

interface Props {
  agent: JarvisAgent;
  isActive: boolean;
  hasUnread: boolean;
  onClick: () => void;
}

export const AgentCard: React.FC<Props> = ({ agent, isActive, hasUnread, onClick }) => (
  <button
    onClick={onClick}
    className={`relative flex flex-col items-center gap-1 p-3 rounded-xl border-2 transition-all
      ${isActive ? "border-current shadow-lg scale-105" : "border-transparent hover:border-gray-300"}
    `}
    style={{ color: agent.color }}
  >
    <div className="relative text-3xl">{agent.icon}
      {hasUnread && (
        <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-red-500 animate-pulse" />
      )}
    </div>
    <span className="text-xs font-semibold text-gray-700">{agent.name}</span>
    <span className="text-[10px] text-gray-400">{agent.role}</span>
  </button>
);
