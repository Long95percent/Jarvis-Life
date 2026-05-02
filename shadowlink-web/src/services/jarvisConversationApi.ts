import { jarvisApi, type ConversationHistoryItem } from './jarvisApi'

export type { ConversationHistoryItem } from './jarvisApi'

export const jarvisConversationApi = {
  listConversationHistory(limit = 30): Promise<ConversationHistoryItem[]> {
    return jarvisApi.listConversationHistory(limit)
  },

  saveConversationHistory(payload: Parameters<typeof jarvisApi.saveConversationHistory>[0]): Promise<ConversationHistoryItem> {
    return jarvisApi.saveConversationHistory(payload)
  },

  openConversationHistory(conversationId: string): Promise<ConversationHistoryItem> {
    return jarvisApi.openConversationHistory(conversationId)
  },

  deleteConversationHistory(conversationId: string): Promise<void> {
    return jarvisApi.deleteConversationHistory(conversationId)
  },
}
