export type RoundtableMode = "decision" | "brainstorm";

export interface ScenarioRoute {
  label?: string;
  target_stage?: string;
  prompt?: string;
}

export interface ScenarioStateLike {
  next_routes?: ScenarioRoute[];
}

export interface ScenarioRouteButton {
  label: string;
  targetStage?: string;
  prompt: string;
}

const BRAINSTORM_SCENARIOS = new Set([
  "local_lifestyle",
  "emotional_care",
  "weekend_recharge",
  "work_brainstorm",
]);

export function initialRoundtableModeForScenario(scenarioId: string): RoundtableMode {
  return BRAINSTORM_SCENARIOS.has(scenarioId) ? "brainstorm" : "decision";
}

export function pendingActionCount(actionResults: Array<Record<string, unknown>> | undefined): number {
  return (actionResults ?? []).filter((item) => item.pending_confirmation === true).length;
}

export function routeButtonsFromScenarioState(state: ScenarioStateLike | null | undefined): ScenarioRouteButton[] {
  return (state?.next_routes ?? [])
    .map((route): ScenarioRouteButton | null => {
      const prompt = typeof route.prompt === "string" ? route.prompt.trim() : "";
      if (!prompt) return null;
      const explicitLabel = typeof route.label === "string" ? route.label.trim() : "";
      const targetStage = typeof route.target_stage === "string" && route.target_stage.trim()
        ? route.target_stage.trim()
        : undefined;
      return {
        label: explicitLabel || targetStage || "继续",
        targetStage,
        prompt,
      };
    })
    .filter((item): item is ScenarioRouteButton => item !== null);
}
