import { listModels, ModelInfo, ToolInfo } from '@/api/model'
import useConfigsStore from '@/stores/configs'
import { useQuery } from '@tanstack/react-query'
import { createContext, useContext, useEffect } from 'react'

const getPreferredDefaultTools = (toolList: ToolInfo[]): ToolInfo[] => {
  const selected: ToolInfo[] = []

  const preferredImageTool =
    toolList.find((tool) => tool.id === 'generate_image_by_gpt_image_2_edit_apipod') ||
    toolList.find((tool) => tool.provider === 'apipodgptimage' && tool.type === 'image') ||
    toolList.find((tool) => tool.type === 'image')

  const preferredVideoTool =
    toolList.find((tool) => tool.id === 'generate_video_by_veo3_apipod') ||
    toolList.find((tool) => tool.provider === 'apipodvideo' && tool.type === 'video') ||
    toolList.find((tool) => tool.type === 'video')

  if (preferredImageTool) {
    selected.push(preferredImageTool)
  }
  if (preferredVideoTool) {
    selected.push(preferredVideoTool)
  }

  return selected
}

export const ConfigsContext = createContext<{
  configsStore: typeof useConfigsStore
  refreshModels: () => void
} | null>(null)

export const ConfigsProvider = ({
  children,
}: {
  children: React.ReactNode
}) => {
  const configsStore = useConfigsStore()
  const {
    setTextModels,
    setTextModel,
    setSelectedTools,
    setAllTools,
  } = configsStore

  const { data: modelList, refetch: refreshModels } = useQuery({
    queryKey: ['list_models_2'],
    queryFn: () => listModels(),
    staleTime: 1000,
    placeholderData: (previousData) => previousData,
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
    refetchOnMount: true,
  })

  useEffect(() => {
    if (!modelList) return
    const { llm: llmModels = [], tools: toolList = [] } = modelList

    setTextModels(llmModels || [])
    setAllTools(toolList || [])

    const defaultModel = llmModels.find(
      (m) => m.provider === 'apipodcode' && m.model === 'gpt-5.4'
    )
    setTextModel(defaultModel || llmModels.find((m) => m.type === 'text'))
    setSelectedTools(getPreferredDefaultTools(toolList))

    localStorage.removeItem('text_model')
    localStorage.removeItem('disabled_tool_ids')
    localStorage.removeItem('tool_selection_migration_version')
    localStorage.removeItem('app_access_token_legacy')
    localStorage.removeItem('app_user_info_legacy')
    localStorage.removeItem('show_settings_dialog')
  }, [
    modelList,
    setSelectedTools,
    setTextModel,
    setTextModels,
    setAllTools,
  ])

  return (
    <ConfigsContext.Provider
      value={{ configsStore: useConfigsStore, refreshModels }}
    >
      {children}
    </ConfigsContext.Provider>
  )
}

export const useConfigs = () => {
  const context = useContext(ConfigsContext)
  if (!context) {
    throw new Error('useConfigs must be used within a ConfigsProvider')
  }
  return context.configsStore()
}

export const useRefreshModels = () => {
  const context = useContext(ConfigsContext)
  if (!context) {
    throw new Error('useRefreshModels must be used within a ConfigsProvider')
  }
  return context.refreshModels
}
