import { useState, useEffect } from 'react'
import { useAmbientStore } from '@/stores'
import { X, Folder, File, Link as LinkIcon, Box, Terminal, Trash2, Zap, Wrench } from 'lucide-react'
import type { WorkModeResource } from '@/types'

export function ModeSettingsModal({ modeId, onClose }: { modeId: string; onClose: () => void }) {
  const modes = useAmbientStore((s) => s.modes)
  const updateModeResources = useAmbientStore((s) => s.updateModeResources)
  const updateModeSystemPrompt = useAmbientStore((s) => s.updateModeSystemPrompt)
  const updateModeStrategy = useAmbientStore((s) => s.updateModeStrategy)
  const updateModeTools = useAmbientStore((s) => s.updateModeTools)
  const mode = modes.find(m => m.modeId === modeId)

  const [resources, setResources] = useState<WorkModeResource[]>([])
  const [systemPrompt, setSystemPrompt] = useState<string>('')
  const [strategy, setStrategy] = useState<string>('auto')
  const [enabledTools, setEnabledTools] = useState<string[]>([])

  useEffect(() => {
    if (mode) {
      setResources(mode.resources || [])
      setSystemPrompt(mode.systemPrompt || '')
      setStrategy(mode.strategy || 'auto')
      setEnabledTools(mode.enabledTools || [])
    }
  }, [mode])

  if (!mode) return null

  const handleAdd = (type: WorkModeResource['type']) => {
    const newRes: WorkModeResource = {
      id: Math.random().toString(36).substring(7),
      type,
      name: `New ${type}`,
      value: ''
    }
    setResources([...resources, newRes])
  }

  const handleUpdate = (id: string, field: keyof WorkModeResource, value: string) => {
    setResources(resources.map(r => r.id === id ? { ...r, [field]: value } : r))
  }

  const handleRemove = (id: string) => {
    setResources(resources.filter(r => r.id !== id))
  }

  const handleSave = () => {
    updateModeResources(modeId, resources)
    updateModeSystemPrompt(modeId, systemPrompt)
    updateModeStrategy(modeId, strategy)
    updateModeTools(modeId, enabledTools)
    onClose()
  }

  const toggleTool = (toolId: string) => {
    setEnabledTools(prev => 
      prev.includes(toolId) 
        ? prev.filter(t => t !== toolId)
        : [...prev, toolId]
    )
  }

  const availableTools = [
    { id: 'web_search', label: 'Web Search', desc: 'Search the internet for real-time info' },
    { id: 'knowledge_search', label: 'Knowledge Base', desc: 'Search indexed documents & vectors' },
    { id: 'code_executor', label: 'Code Execution', desc: 'Run Python code locally' },
    { id: 'file_reader', label: 'File Reader', desc: 'Read local files' },
    { id: 'calculator', label: 'Calculator', desc: 'Evaluate math expressions' },
  ]

  const TypeIcon = ({ type }: { type: string }) => {
    switch (type) {
      case 'folder': return <Folder size={14} />
      case 'file': return <File size={14} />
      case 'url': return <LinkIcon size={14} />
      case 'app': return <Box size={14} />
      case 'script': return <Terminal size={14} />
      default: return <File size={14} />
    }
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-surface border border-surface-tertiary rounded-2xl w-full max-w-2xl shadow-2xl flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-tertiary">
          <div>
            <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
              <span className="w-6 h-6 rounded-md ambient-gradient flex items-center justify-center text-white text-[10px] font-bold">
                {mode.icon.charAt(0)}
              </span>
              {mode.name} Resources
            </h2>
            <p className="text-xs text-muted mt-1">Configure system prompts and resources for this mode.</p>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-surface-secondary text-muted transition-colors">
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
          {/* Execution Strategy */}
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-foreground flex items-center gap-2">
              <Zap size={14} className="text-primary-400" />
              Execution Strategy
            </h3>
            <p className="text-xs text-muted leading-relaxed">
              How should the AI approach tasks in this mode? "Auto" will let the engine decide based on complexity.
            </p>
            <div className="flex flex-wrap gap-2">
              {['auto', 'direct', 'react', 'plan_execute'].map(s => (
                <button
                  key={s}
                  onClick={() => setStrategy(s)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border ${
                    strategy === s 
                      ? 'bg-primary-500/20 text-primary-400 border-primary-500/50' 
                      : 'bg-surface-secondary text-muted border-transparent hover:bg-surface-tertiary'
                  }`}
                >
                  {s === 'auto' ? 'Auto-Route' : s === 'direct' ? 'Direct LLM' : s === 'react' ? 'ReAct Loop' : 'Plan & Execute'}
                </button>
              ))}
            </div>
          </div>

          <div className="h-px w-full bg-surface-tertiary" />

          {/* Tools Scope */}
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-foreground flex items-center gap-2">
              <Wrench size={14} className="text-primary-400" />
              Enabled Tools
            </h3>
            <p className="text-xs text-muted leading-relaxed">
              Select which tools are permitted for the AI to use in this mode.
            </p>
            <div className="grid grid-cols-2 gap-2">
              {availableTools.map(tool => (
                <label key={tool.id} className="flex items-start gap-3 p-3 rounded-xl border border-surface-tertiary bg-surface-secondary cursor-pointer hover:bg-surface-tertiary transition-colors">
                  <div className="flex items-center h-5">
                    <input
                      type="checkbox"
                      className="w-4 h-4 rounded border-surface-tertiary text-primary-500 focus:ring-primary-500/50 bg-black/20"
                      checked={enabledTools.includes(tool.id)}
                      onChange={() => toggleTool(tool.id)}
                    />
                  </div>
                  <div className="flex flex-col">
                    <span className="text-sm font-medium text-foreground">{tool.label}</span>
                    <span className="text-[10px] text-muted leading-tight mt-0.5">{tool.desc}</span>
                  </div>
                </label>
              ))}
            </div>
          </div>

          <div className="h-px w-full bg-surface-tertiary" />

          {/* System Prompt Section */}
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-foreground flex items-center gap-2">
              <Terminal size={14} className="text-primary-400" />
              System Prompt
            </h3>
            <p className="text-xs text-muted leading-relaxed">
              Define the AI's persona, instructions, and rules for this mode. If left empty, the default system prompt will be used.
            </p>
            <textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="You are ShadowLink in this mode. Your task is to..."
              className="w-full h-28 bg-surface-secondary border border-surface-tertiary rounded-xl p-3 text-sm text-foreground placeholder:text-muted/50 focus:outline-none focus:border-primary-500/50 resize-none font-mono"
            />
          </div>

          <div className="h-px w-full bg-surface-tertiary" />

          {/* Resources Section */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-foreground flex items-center gap-2">
                <Box size={14} className="text-primary-400" />
                Quick Resources
              </h3>
            </div>
            
            <div className="flex gap-2">
            <button onClick={() => handleAdd('folder')} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-secondary text-xs hover:bg-surface-tertiary transition-colors"><Folder size={14} /> Folder</button>
            <button onClick={() => handleAdd('file')} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-secondary text-xs hover:bg-surface-tertiary transition-colors"><File size={14} /> File</button>
            <button onClick={() => handleAdd('url')} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-secondary text-xs hover:bg-surface-tertiary transition-colors"><LinkIcon size={14} /> URL</button>
            <button onClick={() => handleAdd('app')} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-secondary text-xs hover:bg-surface-tertiary transition-colors"><Box size={14} /> App (.exe)</button>
            <button onClick={() => handleAdd('script')} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-secondary text-xs hover:bg-surface-tertiary transition-colors"><Terminal size={14} /> Script (.bat)</button>
          </div>

          <div className="space-y-2">
            {resources.length === 0 ? (
              <div className="text-center py-12 text-muted text-sm border border-dashed border-white/10 rounded-xl">
                No resources added yet. Click above to add some.
              </div>
            ) : (
              resources.map(res => (
                <div key={res.id} className="flex items-start gap-3 p-3 bg-surface-secondary border border-white/5 rounded-xl group">
                  <div className="mt-2.5 text-muted"><TypeIcon type={res.type} /></div>
                  <div className="flex-1 space-y-2">
                    <input
                      type="text"
                      value={res.name}
                      onChange={e => handleUpdate(res.id, 'name', e.target.value)}
                      placeholder="Display Name (e.g., Project Folder)"
                      className="w-full bg-transparent text-sm font-medium text-foreground outline-none border-b border-transparent focus:border-primary-500/50 pb-1"
                    />
                    <input
                      type="text"
                      value={res.value}
                      onChange={e => handleUpdate(res.id, 'value', e.target.value)}
                      placeholder={res.type === 'url' ? 'https://...' : 'C:\\Path\\to\\...'}
                      className="w-full bg-black/20 px-2 py-1.5 rounded text-xs text-muted font-mono outline-none border border-transparent focus:border-primary-500/50"
                    />
                  </div>
                  <button onClick={() => handleRemove(res.id)} className="p-2 mt-1 text-muted hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors">
                    <Trash2 size={16} />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-surface-tertiary flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 rounded-lg text-sm font-medium hover:bg-surface-secondary transition-colors">
            Cancel
          </button>
          <button onClick={handleSave} className="px-4 py-2 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors shadow-lg shadow-primary-500/20">
            Save Resources
          </button>
        </div>
      </div>
    </div>
  )
}