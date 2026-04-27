// shadowlink-web/src/stores/jarvisStore.ts
import { create } from "zustand";
import { jarvisApi, type ActionResult, type CalendarEvent, type ConversationHistoryItem, type EscalationHint, type JarvisAgent, type LifeContext, type ProactiveMessage, type TeamCollaborationResponse } from "@/services/jarvisApi";

export type InteractionMode = "scenario_grid" | "private_chat" | "roundtable";

const UI_STATE_KEY = "jarvis.uiState.v1";

interface PersistedUiState {
  interactionMode?: InteractionMode;
  activeAgentId?: string;
  activeRoundtableScenario?: string | null;
  activeRoundtableInput?: string;
  sessionId?: string;
}

function readPersistedUiState(): PersistedUiState {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(window.localStorage.getItem(UI_STATE_KEY) || "{}") as PersistedUiState;
  } catch {
    return {};
  }
}

function writePersistedUiState(patch: PersistedUiState) {
  if (typeof window === "undefined") return;
  const current = readPersistedUiState();
  window.localStorage.setItem(UI_STATE_KEY, JSON.stringify({ ...current, ...patch }));
}

const persistedUiState = readPersistedUiState();

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
  chatHistory: Record<string, Array<{ role: "user" | "agent"; content: string; actions?: ActionResult[]; routing?: Record<string, unknown> | null }>>;
  isLoading: boolean;

  // Local-life snapshot (shared reactive state so every card updates in sync)
  localLife: LocalLifeSnapshot | null;

  // Interaction-mode slice
  interactionMode: InteractionMode;
  activeRoundtableScenario: string | null;
  activeRoundtableInput: string;
  sessionId: string;

  loadContext: () => Promise<void>;
  updateContext: (fields: Partial<LifeContext>) => Promise<void>;
  loadAgents: () => Promise<void>;
  loadProactiveMessages: () => Promise<void>;
  addProactiveMessage: (msg: ProactiveMessage) => void;
  markMessageRead: (id: string) => Promise<void>;
  setActiveAgent: (agentId: string) => void;
  sendMessage: (agentId: string, message: string, sessionId: string) => Promise<EscalationHint | null>;
  loadChatHistory: (agentId: string, sessionId?: string) => Promise<void>;
  clearChatHistory: (agentId: string, sessionId?: string) => Promise<void>;

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
  openConversation: (conversation: ConversationHistoryItem) => Promise<void>;
  startTeamCollaboration: (goal: string, userMessage: string, agents?: string[]) => Promise<TeamCollaborationResponse>;
  closeRoundtable: () => void;
  resetToScenarioGrid: () => void;
}

export const useJarvisStore = create<JarvisState>((set, get) => ({
  context: null,
  agents: [],
  proactiveMessages: [],
  activeAgentId: persistedUiState.activeAgentId ?? "alfred",
  chatHistory: {},
  isLoading: false,
  localLife: null,

  interactionMode: persistedUiState.interactionMode ?? "scenario_grid",
  activeRoundtableScenario: persistedUiState.activeRoundtableScenario ?? null,
  activeRoundtableInput: persistedUiState.activeRoundtableInput ?? "",
  sessionId: persistedUiState.sessionId ?? `jarvis-${Date.now()}`,

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

  loadProactiveMessages: async () => {
    const proactiveMessages = await jarvisApi.getPendingMessages();
    set({ proactiveMessages });
  },

  addProactiveMessage: (msg) => {
    set((s) => {
      const existing = s.proactiveMessages.find((m) => m.id === msg.id);
      if (existing) {
        return {
          proactiveMessages: s.proactiveMessages.map((m) =>
            m.id === msg.id ? { ...m, ...msg } : m
          ),
        };
      }
      return { proactiveMessages: [msg, ...s.proactiveMessages] };
    });
  },

  markMessageRead: async (id) => {
    const updated = await jarvisApi.markProactiveMessageRead(id);
    set((s) => ({
      proactiveMessages: s.proactiveMessages.map((m) =>
        m.id === id ? { ...m, ...updated } : m
      ),
    }));
  },

  setActiveAgent: (agentId) => {
    writePersistedUiState({ activeAgentId: agentId });
    set({ activeAgentId: agentId });
  },

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
    const routedAgentId = response.agent_id || agentId;
    const agentTurn = {
      role: "agent" as const,
      content: response.content,
      actions: response.actions ?? undefined,
      routing: response.routing ?? undefined,
    };
    set((s) => ({
      chatHistory: {
        ...s.chatHistory,
        ...(routedAgentId === agentId
          ? {
              [agentId]: [
                ...(s.chatHistory[agentId] ?? []),
                agentTurn,
              ],
            }
          : {
              [agentId]: (s.chatHistory[agentId] ?? []).filter((turn, index, turns) => {
                const isOptimisticUserTurn =
                  index === turns.length - 1 &&
                  turn.role === "user" &&
                  turn.content === message;
                return !isOptimisticUserTurn;
              }),
              [routedAgentId]: [
                { role: "user" as const, content: message },
                agentTurn,
              ],
            }),
      },
    }));
    if (routedAgentId !== agentId) {
      writePersistedUiState({ activeAgentId: routedAgentId, interactionMode: "private_chat", sessionId });
      set({ activeAgentId: routedAgentId, interactionMode: "private_chat", sessionId });
    }
    window.dispatchEvent(new Event("jarvis:conversation-history-changed"));
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

  loadChatHistory: async (agentId, sessionId) => {
    const effectiveSessionId = sessionId ?? get().sessionId;
    const turns = await jarvisApi.getChatHistory(agentId, 50, effectiveSessionId);
    set((s) => ({
      chatHistory: {
        ...s.chatHistory,
        [agentId]: turns.map((t) => ({ role: t.role, content: t.content, actions: t.actions })),
      },
    }));
  },

  clearChatHistory: async (agentId, sessionId) => {
    const effectiveSessionId = sessionId ?? get().sessionId;
    await jarvisApi.clearChatHistory(agentId, effectiveSessionId);
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

  setInteractionMode: (mode) => {
    writePersistedUiState({ interactionMode: mode });
    set({ interactionMode: mode });
  },

  openPrivateChat: (agentId) => {
    const sessionId = `private-${agentId}-${Date.now()}`;
    writePersistedUiState({ activeAgentId: agentId, interactionMode: "private_chat", sessionId });
    set({ activeAgentId: agentId, interactionMode: "private_chat", sessionId });
  },

  startRoundtable: (scenarioId, userInput) => {
    const sessionId = `jarvis-${Date.now()}`;
    const isBrainstorm = scenarioId === "work_brainstorm";
    writePersistedUiState({
      interactionMode: "roundtable",
      activeRoundtableScenario: scenarioId,
      activeRoundtableInput: userInput,
      sessionId,
    });
    jarvisApi.saveConversationHistory({
      conversation_id: `${isBrainstorm ? "brainstorm" : "roundtable"}:${sessionId}`,
      conversation_type: isBrainstorm ? "brainstorm" : "roundtable",
      title: `${isBrainstorm ? "工作难题头脑风暴" : "圆桌讨论"}${userInput ? `：${userInput.slice(0, 18)}` : ""}`,
      scenario_id: scenarioId,
      session_id: sessionId,
      route_payload: { mode: "roundtable", scenario_id: scenarioId, user_input: userInput, mode_id: "general" },
    }).catch(() => {});
    set({
      interactionMode: "roundtable",
      activeRoundtableScenario: scenarioId,
      activeRoundtableInput: userInput,
      sessionId,
    });
  },

  openConversation: async (conversation) => {
    await jarvisApi.openConversationHistory(conversation.id).catch(() => {});
    const payload = conversation.route_payload ?? {};
    if (conversation.conversation_type === "private_chat" && conversation.agent_id) {
      writePersistedUiState({
        interactionMode: "private_chat",
        activeAgentId: conversation.agent_id,
        sessionId: conversation.session_id,
      });
      set({ interactionMode: "private_chat", activeAgentId: conversation.agent_id, sessionId: conversation.session_id });
      await get().loadChatHistory(conversation.agent_id, conversation.session_id);
      return;
    }
    const scenarioId = conversation.scenario_id ?? (typeof payload.scenario_id === "string" ? payload.scenario_id : null);
    if (scenarioId) {
      const userInput = typeof payload.user_input === "string" ? payload.user_input : "";
      writePersistedUiState({
        interactionMode: "roundtable",
        activeRoundtableScenario: scenarioId,
        activeRoundtableInput: userInput,
        sessionId: conversation.session_id,
      });
      set({
        interactionMode: "roundtable",
        activeRoundtableScenario: scenarioId,
        activeRoundtableInput: userInput,
        sessionId: conversation.session_id,
      });
    }
  },

  startTeamCollaboration: async (goal, userMessage, agents) => {
    return jarvisApi.startTeamCollaboration({
      goal,
      user_message: userMessage,
      agents,
      source_agent: get().activeAgentId,
    });
  },

  closeRoundtable: () =>
  {
    writePersistedUiState({ interactionMode: "scenario_grid", activeRoundtableScenario: null, activeRoundtableInput: "" });
    set({
      interactionMode: "scenario_grid",
      activeRoundtableScenario: null,
      activeRoundtableInput: "",
    });
  },

  resetToScenarioGrid: () =>
  {
    writePersistedUiState({ interactionMode: "scenario_grid", activeRoundtableScenario: null, activeRoundtableInput: "" });
    set({
      interactionMode: "scenario_grid",
      activeRoundtableScenario: null,
      activeRoundtableInput: "",
    });
  },
}));
