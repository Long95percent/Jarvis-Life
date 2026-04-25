// shadowlink-web/src/stores/jarvisStore.ts
import { create } from "zustand";
import { jarvisApi, type ActionResult, type CalendarEvent, type EscalationHint, type JarvisAgent, type LifeContext, type ProactiveMessage, type TeamCollaborationResponse } from "@/services/jarvisApi";

export type InteractionMode = "scenario_grid" | "private_chat" | "roundtable";

interface LocalLifeSnapshot {
  weather: Record<string, any> | null;
  activities: any[];
  news: any[];
  upcoming_events: CalendarEvent[];
  schedule_density: number;
  fetched_at?: number;
}

interface JarvisState {
  context: LifeContext | null;
  agents: JarvisAgent[];
  proactiveMessages: ProactiveMessage[];
  activeAgentId: string;
  chatHistory: Record<string, Array<{ role: "user" | "agent"; content: string; actions?: ActionResult[] }>>;
  isLoading: boolean;

  // Local-life snapshot (shared reactive state so every card updates in sync)
  localLife: LocalLifeSnapshot | null;

  // Interaction-mode slice
  interactionMode: InteractionMode;
  activeRoundtableScenario: string | null;
  activeRoundtableInput: string;

  loadContext: () => Promise<void>;
  updateContext: (fields: Partial<LifeContext>) => Promise<void>;
  loadAgents: () => Promise<void>;
  addProactiveMessage: (msg: ProactiveMessage) => void;
  markMessageRead: (id: string) => void;
  setActiveAgent: (agentId: string) => void;
  sendMessage: (agentId: string, message: string, sessionId: string) => Promise<EscalationHint | null>;
  loadChatHistory: (agentId: string) => Promise<void>;
  clearChatHistory: (agentId: string) => Promise<void>;

  // Local-life + calendar
  refreshLocalLife: (force?: boolean) => Promise<void>;
  refreshAll: () => Promise<void>;
  addCalendarEvent: (payload: {
    title: string;
    start: string;
    end: string;
    stress_weight?: number;
    location?: string | null;
    notes?: string | null;
    source?: string;
    source_agent?: string | null;
    created_reason?: string | null;
    status?: string;
    route_required?: boolean;
  }) => Promise<void>;
  deleteCalendarEvent: (eventId: string) => Promise<void>;
  updateCalendarEvent: (
    eventId: string,
    patch: Partial<{
      title: string;
      start: string;
      end: string;
      stress_weight: number;
      location: string | null;
      notes: string | null;
      source: string;
      source_agent: string | null;
      created_reason: string | null;
      status: string;
      route_required: boolean;
    }>
  ) => Promise<void>;

  // New interaction actions
  setInteractionMode: (mode: InteractionMode) => void;
  openPrivateChat: (agentId: string) => void;
  startRoundtable: (scenarioId: string, userInput: string) => void;
  startTeamCollaboration: (goal: string, userMessage: string, agents?: string[]) => Promise<TeamCollaborationResponse>;
  closeRoundtable: () => void;
  resetToScenarioGrid: () => void;
}

export const useJarvisStore = create<JarvisState>((set, get) => ({
  context: null,
  agents: [],
  proactiveMessages: [],
  activeAgentId: "alfred",
  chatHistory: {},
  isLoading: false,
  localLife: null,

  interactionMode: "scenario_grid",
  activeRoundtableScenario: null,
  activeRoundtableInput: "",

  loadContext: async () => {
    const context = await jarvisApi.getContext();
    set({ context });
  },

  updateContext: async (fields) => {
    const context = await jarvisApi.updateContext(fields);
    set({ context });
  },

  loadAgents: async () => {
    const agents = await jarvisApi.listAgents();
    set({ agents });
  },

  addProactiveMessage: (msg) => {
    set((s) => ({ proactiveMessages: [msg, ...s.proactiveMessages] }));
  },

  markMessageRead: (id) => {
    set((s) => ({
      proactiveMessages: s.proactiveMessages.map((m) =>
        m.id === id ? { ...m, read: true } : m
      ),
    }));
  },

  setActiveAgent: (agentId) => set({ activeAgentId: agentId }),

  sendMessage: async (agentId, message, sessionId) => {
    set((s) => ({
      chatHistory: {
        ...s.chatHistory,
        [agentId]: [...(s.chatHistory[agentId] ?? []), { role: "user", content: message }],
      },
    }));
    let response;
    try {
      response = await jarvisApi.chat(agentId, message, sessionId);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Jarvis 对话失败：未知错误";
      set((s) => ({
        chatHistory: {
          ...s.chatHistory,
          [agentId]: [
            ...(s.chatHistory[agentId] ?? []),
            { role: "agent", content: message },
          ],
        },
      }));
      throw error;
    }
    set((s) => ({
      chatHistory: {
        ...s.chatHistory,
        [agentId]: [
          ...(s.chatHistory[agentId] ?? []),
          {
            role: "agent",
            content: response.content,
            actions: response.actions ?? undefined,
          },
        ],
      },
    }));
    // If the agent executed any actions that may have changed state, refresh.
    if (response.actions && response.actions.length > 0) {
      const mutating = response.actions.some((a) =>
        a.ok && !a.pending_confirmation && (
          a.type.startsWith("calendar.") ||
          a.type.startsWith("context.")
        )
      );
      if (mutating) {
        get().refreshAll().catch(() => {});
      }
    }
    return response.escalation ?? null;
  },

  loadChatHistory: async (agentId) => {
    const turns = await jarvisApi.getChatHistory(agentId);
    set((s) => ({
      chatHistory: {
        ...s.chatHistory,
        [agentId]: turns.map((t) => ({ role: t.role, content: t.content })),
      },
    }));
  },

  clearChatHistory: async (agentId) => {
    await jarvisApi.clearChatHistory(agentId);
    set((s) => ({
      chatHistory: { ...s.chatHistory, [agentId]: [] },
    }));
  },

  refreshLocalLife: async (force = false) => {
    try {
      const data = await jarvisApi.getLocalLife(force);
      set({
        localLife: {
          weather: data.weather ?? null,
          activities: data.activities ?? [],
          news: data.news ?? [],
          upcoming_events: data.upcoming_events ?? [],
          schedule_density: data.schedule_density ?? 0,
          fetched_at: data.fetched_at,
        },
      });
    } catch {
      // silent; card will show its own fallback
    }
  },

  refreshAll: async () => {
    await Promise.all([
      get().loadContext(),
      get().refreshLocalLife(true),
    ]);
  },

  addCalendarEvent: async (payload) => {
    await jarvisApi.addCalendarEvent(payload);
    await get().refreshAll();
  },

  deleteCalendarEvent: async (eventId) => {
    await jarvisApi.deleteCalendarEvent(eventId);
    await get().refreshAll();
  },

  updateCalendarEvent: async (eventId, patch) => {
    await jarvisApi.updateCalendarEvent(eventId, patch);
    await get().refreshAll();
  },

  setInteractionMode: (mode) => set({ interactionMode: mode }),

  openPrivateChat: (agentId) =>
    set({ activeAgentId: agentId, interactionMode: "private_chat" }),

  startRoundtable: (scenarioId, userInput) =>
    set({
      interactionMode: "roundtable",
      activeRoundtableScenario: scenarioId,
      activeRoundtableInput: userInput,
    }),

  startTeamCollaboration: async (goal, userMessage, agents) => {
    return jarvisApi.startTeamCollaboration({
      goal,
      user_message: userMessage,
      agents,
      source_agent: get().activeAgentId,
    });
  },

  closeRoundtable: () =>
    set({
      interactionMode: "scenario_grid",
      activeRoundtableScenario: null,
      activeRoundtableInput: "",
    }),

  resetToScenarioGrid: () =>
    set({
      interactionMode: "scenario_grid",
      activeRoundtableScenario: null,
      activeRoundtableInput: "",
    }),
}));

