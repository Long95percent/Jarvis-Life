/** Chat and messaging types */

export type MessageRole = 'user' | 'assistant' | 'system'

export interface ChatMessage {
  id: string
  sessionId: string
  role: MessageRole
  content: string
  tokenCount: number
  model: string
  createdAt: string
  /** Client-side streaming state */
  isStreaming?: boolean
}

export interface ChatSession {
  sessionId: string
  modeId: string
  title: string
  createdAt: string
  updatedAt: string
  /** Client-side: last message preview */
  lastMessage?: string
  messageCount?: number
}

export interface SendMessageRequest {
  sessionId: string
  modeId: string
  message: string
  stream?: boolean
}
