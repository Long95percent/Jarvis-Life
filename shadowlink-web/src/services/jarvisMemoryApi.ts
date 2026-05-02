import { jarvisApi, type JarvisMemory } from './jarvisApi'

export type { JarvisMemory } from './jarvisApi'

export const jarvisMemoryApi = {
  listMemories(params?: { memoryKind?: string; limit?: number }): Promise<JarvisMemory[]> {
    return jarvisApi.listMemories(params)
  },

  deleteMemory(memoryId: number): Promise<void> {
    return jarvisApi.deleteMemory(memoryId)
  },
}
