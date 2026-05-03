// shadowlink-web/src/components/jarvis/agentMeta.ts
export const JARVIS_AGENTS: Record<
  string,
  { icon: string; color: string; name: string; role: string; description?: string }
> = {
  alfred:      { icon: "🎩", color: "#6C63FF", name: "Alfred",  role: "总管家", description: "任务规划、日程管理、综合决策" },
  maxwell:     { icon: "📋", color: "#3B82F6", name: "Maxwell", role: "秘书", description: "文件处理、资料整理、信息检索" },
  nora:        { icon: "🥗", color: "#10B981", name: "Nora",    role: "营养师", description: "饮食建议、健康分析、营养指导" },
  mira:        { icon: "🌸", color: "#F59E0B", name: "Mira",    role: "心理师", description: "情绪关怀、心理疏导、陪伴支持" },
  leo:         { icon: "🌟", color: "#EF4444", name: "Leo",     role: "生活顾问", description: "生活技巧、出行建议、效率提升" },
  athena:      { icon: "🦉", color: "#8B5CF6", name: "Athena",  role: "学习策略师", description: "学习规划、知识总结、方法指导" },

  // Brainstorm scenario roster
  moderator:   { icon: "🎙️", color: "#8B5CF6", name: "Moderator",   role: "主持人", description: "组织讨论、推进流程、收束结论" },
  explorer:    { icon: "🧭", color: "#06B6D4", name: "Explorer",    role: "探索者", description: "补充信息、延展思路、寻找可能" },
  critic:      { icon: "🛡️", color: "#F43F5E", name: "Critic",      role: "批判者", description: "识别风险、指出漏洞、提出质疑" },
  synthesizer: { icon: "🧩", color: "#84CC16", name: "Synthesizer", role: "综合者", description: "整合观点、提炼方案、生成共识" },
};
