import { jarvisApi, type PendingAction } from './jarvisApi'

export type { PendingAction } from './jarvisApi'

export type PendingActionPatch = { title?: string; arguments?: Record<string, unknown> }
export type ConfirmPendingActionResult = Awaited<ReturnType<typeof jarvisApi.confirmPendingAction>>

export const jarvisPendingActionApi = {
  listPendingActions(status = 'pending'): Promise<PendingAction[]> {
    return jarvisApi.listPendingActions(status)
  },

  updatePendingAction(pendingId: string, payload: PendingActionPatch): Promise<PendingAction> {
    return jarvisApi.updatePendingAction(pendingId, payload)
  },

  confirmPendingAction(pendingId: string, payload?: PendingActionPatch): Promise<ConfirmPendingActionResult> {
    return jarvisApi.confirmPendingAction(pendingId, payload)
  },

  cancelPendingAction(pendingId: string): Promise<PendingAction> {
    return jarvisApi.cancelPendingAction(pendingId)
  },
}
