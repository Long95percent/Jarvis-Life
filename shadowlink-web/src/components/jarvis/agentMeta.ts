// shadowlink-web/src/components/jarvis/agentMeta.ts
export const JARVIS_AGENTS: Record<
  string,
  { icon: string; color: string; name: string; role: string }
> = {
  alfred:      { icon: "🎩", color: "#6C63FF", name: "Alfred",  role: "总管家" },
  maxwell:     { icon: "📋", color: "#3B82F6", name: "Maxwell", role: "秘书" },
  nora:        { icon: "🥗", color: "#10B981", name: "Nora",    role: "营养师" },
  mira:        { icon: "🌸", color: "#F59E0B", name: "Mira",    role: "心理师" },
  leo:         { icon: "🌟", color: "#EF4444", name: "Leo",     role: "生活顾问" },

  // Brainstorm scenario roster
  moderator:   { icon: "🎙️", color: "#8B5CF6", name: "Moderator",   role: "主持人" },
  explorer:    { icon: "🧭", color: "#06B6D4", name: "Explorer",    role: "探索者" },
  critic:      { icon: "🛡️", color: "#F43F5E", name: "Critic",      role: "批判者" },
  synthesizer: { icon: "🧩", color: "#84CC16", name: "Synthesizer", role: "综合者" },
};
