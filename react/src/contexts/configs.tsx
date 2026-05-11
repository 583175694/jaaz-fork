import { listModels, ModelInfo, ToolInfo } from '@/api/model'
import useConfigsStore from '@/stores/configs'
import { useQuery } from '@tanstack/react-query'
import { createContext, useContext, useEffect, useRef } from 'react'

const TOOL_SELECTION_MIGRATION_VERSION = 'apipodvideo-default-v1'

const getPreferredDefaultTools = (toolList: ToolInfo[]): ToolInfo[] => {
  const selected: ToolInfo[] = []

  const preferredImageTool =
    toolList.find((tool) => tool.id === 'generate_image_by_gpt_image_2_zenlayer') ||
    toolList.find((tool) => tool.provider === 'zenlayer' && tool.type === 'image') ||
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
  const DEFAULT_PROVIDER_PRIORITY = ['apipodcode', 'zenlayer', 'openai', 'ollama']
  const configsStore = useConfigsStore()
  const {
    setTextModels,
    setTextModel,
    setSelectedTools,
    setAllTools,
    setShowLoginDialog,
  } = configsStore

  // 存储上一次的 allTools 值，用于检测新添加的工具，并自动选中
  const previousAllToolsRef = useRef<ModelInfo[]>([])

  const { data: modelList, refetch: refreshModels } = useQuery({
    queryKey: ['list_models_2'],
    queryFn: () => listModels(),
    staleTime: 1000, // 5分钟内数据被认为是新鲜的
    placeholderData: (previousData) => previousData, // 关键：显示旧数据同时获取新数据
    refetchOnWindowFocus: true, // 窗口获得焦点时重新获取
    refetchOnReconnect: true, // 网络重连时重新获取
    refetchOnMount: true, // 挂载时重新获取
  })

  useEffect(() => {
    if (!modelList) return
    const { llm: llmModels = [], tools: toolList = [] } = modelList

    setTextModels(llmModels || [])
    setAllTools(toolList || [])

    // 设置选择的文本模型
    const textModel = localStorage.getItem('text_model')
    const apipodDefaultModel = llmModels.find(
      (m) => m.provider === 'apipodcode' && m.model === 'gpt-5.4'
    )
    const shouldMigrateStoredTextModel =
      textModel === 'zenlayer:gpt-5.4' && !!apipodDefaultModel

    if (
      textModel &&
      !shouldMigrateStoredTextModel &&
      llmModels.find((m) => m.provider + ':' + m.model === textModel)
    ) {
      setTextModel(
        llmModels.find((m) => m.provider + ':' + m.model === textModel)
      )
    } else {
      const defaultModel =
        DEFAULT_PROVIDER_PRIORITY.map((provider) =>
          llmModels.find((m) => m.provider === provider && m.type === 'text')
        ).find(Boolean) || llmModels.find((m) => m.type === 'text')
      setTextModel(defaultModel)
      if (defaultModel) {
        localStorage.setItem(
          'text_model',
          `${defaultModel.provider}:${defaultModel.model}`
        )
      }
    }

    // 设置选中的工具模型
    const disabledToolsJson = localStorage.getItem('disabled_tool_ids')
    const toolSelectionMigrationVersion = localStorage.getItem(
      'tool_selection_migration_version'
    )
    let currentSelectedTools: ToolInfo[] = []
    currentSelectedTools = getPreferredDefaultTools(toolList)
    if (disabledToolsJson) {
      try {
        const disabledToolIds: string[] = JSON.parse(disabledToolsJson)
        const shouldMigrateLegacyAllSelected =
          toolSelectionMigrationVersion !== TOOL_SELECTION_MIGRATION_VERSION &&
          disabledToolIds.length === 0

        if (!shouldMigrateLegacyAllSelected) {
          // filter out disabled tools
          currentSelectedTools = toolList.filter(
            (t) => !disabledToolIds.includes(t.id)
          )
        }
      } catch (error) {
        console.error(error)
      }
    }

    localStorage.setItem(
      'disabled_tool_ids',
      JSON.stringify(
        toolList
          .filter((tool) => !currentSelectedTools.some((selected) => selected.id === tool.id))
          .map((tool) => tool.id)
      )
    )
    localStorage.setItem(
      'tool_selection_migration_version',
      TOOL_SELECTION_MIGRATION_VERSION
    )

    setSelectedTools(currentSelectedTools)

    // 只有完全没有文本模型可用时才提示登录/配置 provider。
    // 纯文本使用场景不应因为没有图片/视频工具而强制登录 Jaaz。
    if (llmModels.length === 0) {
      setShowLoginDialog(true)
    }
  }, [
    modelList,
    setSelectedTools,
    setTextModel,
    setTextModels,
    setAllTools,
    setShowLoginDialog,
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
