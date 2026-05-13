import { Button } from '@/components/ui/button'
import { TOOL_CALL_STATUS_LABELS } from '@/constants'
import { ToolCall } from '@/types/types'
import {
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  Check,
  X,
} from 'lucide-react'
import MultiChoicePrompt from '../MultiChoicePrompt'
import SingleChoicePrompt from '../SingleChoicePrompt'
import PromptConfirmationContent from './PromptConfirmationContent'
import WritePlanToolCall from './WritePlanToolcall'
import ToolCallContentV2 from './ToolCallContent'
import { useTranslation } from 'react-i18next'

const CONFIRMATION_DISPLAY_LABELS: Record<string, string> = {
  prompt: 'Prompt',
  display_summary: '任务摘要',
  task_type: '任务类型',
  continuity_asset: '参考图设定',
  storyboard_plan: '分镜设定',
  video_brief: '视频设定',
}

const CONFIRMATION_TOOL_NAMES = new Set([
  'generate_storyboard_from_main_image',
  'generate_multiview_variant',
  'generate_video_from_storyboard',
])

const resolveToolCallSummary = (toolCall: ToolCall) => {
  const toolName = String(toolCall.function.name)
  const result = String(toolCall.result || '').trim()

  if (result.includes('工具调用已取消')) {
    return '已取消本次生成'
  }
  if (result.includes('已返回修改')) {
    return '已返回修改'
  }
  if (result.includes('确认已超时')) {
    return '确认已超时'
  }
  if (toolName === 'generate_storyboard_from_main_image') {
    const matches = result.match(/(\d+)\s*张/)
    if (matches?.[1]) {
      return `已生成 ${matches[1]} 张分镜图`
    }
    if (result) {
      return '已生成分镜'
    }
  }
  if (toolName === 'generate_multiview_variant' && result) {
    return '已生成多视角'
  }
  if (
    (toolName === 'generate_video_from_storyboard' ||
      toolName === 'generate_video_by_veo3_apipod') &&
    result
  ) {
    return '已生成视频'
  }
  if (toolName === 'generate_image' && result) {
    return '已生成图片'
  }

  return TOOL_CALL_STATUS_LABELS[toolName] || '处理中'
}

type ToolCallTagProps = {
  toolCall: ToolCall
  isExpanded: boolean
  onToggleExpand: () => void
  requiresConfirmation?: boolean
  onConfirm?: () => void
  onCancel?: () => void
  onRevise?: () => void
}

const ToolCallTag: React.FC<ToolCallTagProps> = ({
  toolCall,
  isExpanded,
  onToggleExpand,
  requiresConfirmation = false,
  onConfirm,
  onCancel,
  onRevise,
}) => {
  const { name, arguments: inputs } = toolCall.function
  const { t } = useTranslation()

  if (name == 'prompt_user_multi_choice') {
    return <MultiChoicePrompt />
  }
  if (name == 'prompt_user_single_choice') {
    return <SingleChoicePrompt />
  }
  if (name == 'write_plan') {
    return <WritePlanToolCall args={inputs} />
  }
  if (name.startsWith('transfer_to')) {
    return null
  }

  const needsConfirmation = requiresConfirmation
  const isPromptConfirmationTool = CONFIRMATION_TOOL_NAMES.has(name)

  let parsedArgs = null
  const trimmedInputs = inputs.trim()
  const looksLikePartialJson =
    !!trimmedInputs &&
    ((trimmedInputs.startsWith('{') && !trimmedInputs.endsWith('}')) ||
      (trimmedInputs.startsWith('[') && !trimmedInputs.endsWith(']')))

  if (looksLikePartialJson) {
    console.debug('⏳ Tool call args still streaming', {
      toolName: name,
      currentLength: trimmedInputs.length,
    })
  } else if (trimmedInputs) {
    try {
      parsedArgs = JSON.parse(trimmedInputs)
    } catch (error) {
      console.warn('⚠️ Failed to parse complete-looking tool args', {
        toolName: name,
        error,
        rawInputPreview: trimmedInputs.slice(0, 500),
      })
      // 尝试清理输入字符串，移除可能的额外内容
      try {
        const jsonEndIndex = trimmedInputs.lastIndexOf('}')
        if (jsonEndIndex > 0) {
          const jsonPart = trimmedInputs.substring(0, jsonEndIndex + 1)
          parsedArgs = JSON.parse(jsonPart)
          console.log('✅ Successfully parsed cleaned tool args', {
            toolName: name,
            cleanedLength: jsonPart.length,
          })
        }
      } catch (cleanError) {
        console.warn('⚠️ Failed to parse tool args after cleaning', {
          toolName: name,
          error: cleanError,
        })
      }
    }
  }

  const resolvedPrompt =
    parsedArgs && typeof parsedArgs === 'object'
      ? typeof parsedArgs.prompt === 'string'
        ? parsedArgs.prompt
        : typeof parsedArgs.display_prompt_zh === 'string'
          ? parsedArgs.display_prompt_zh
          : null
      : null

  const summaryLabel = resolveToolCallSummary(toolCall)

  // 普通模式的样式
  return (
    <div className="overflow-hidden rounded-xl border border-border/70 bg-background/70 shadow-sm backdrop-blur-sm">
      {/* Header */}
      <div
        className="flex cursor-pointer items-center justify-between p-3 transition-colors hover:bg-muted/40"
        onClick={onToggleExpand}
      >
        <div className="flex items-center gap-2">
          <div className="rounded-md bg-muted p-1.5 text-muted-foreground">
            <svg
              className="h-4 w-4"
              fill="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
              aria-hidden="true"
            >
              <path
                clipRule="evenodd"
                fillRule="evenodd"
                d="M20.599 1.5c-.376 0-.743.111-1.055.32l-5.08 3.385a18.747 18.747 0 0 0-3.471 2.987 10.04 10.04 0 0 1 4.815 4.815 18.748 18.748 0 0 0 2.987-3.472l3.386-5.079A1.902 1.902 0 0 0 20.599 1.5Zm-8.3 14.025a18.76 18.76 0 0 0 1.896-1.207 8.026 8.026 0 0 0-4.513-4.513A18.75 18.75 0 0 0 8.475 11.7l-.278.5a5.26 5.26 0 0 1 3.601 3.602l.502-.278ZM6.75 13.5A3.75 3.75 0 0 0 3 17.25a1.5 1.5 0 0 1-1.601 1.497.75.75 0 0 0-.7 1.123 5.25 5.25 0 0 0 9.8-2.62 3.75 3.75 0 0 0-3.75-3.75Z"
              ></path>
            </svg>
          </div>

          <div className="break-all font-medium leading-relaxed text-foreground">
            {summaryLabel}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {needsConfirmation && (
            <div className="flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700 dark:bg-amber-950/60 dark:text-amber-300">
              <AlertTriangle className="h-3 w-3" />
              {t('chat.toolCall.requiresConfirmation', '待确认')}
            </div>
          )}
          {!needsConfirmation && toolCall.result === '工具调用已取消' && (
            <div className="flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
              <X className="h-3 w-3" />
              {t('chat.toolCall.cancelled', '已取消')}
            </div>
          )}
          {parsedArgs && Object.keys(parsedArgs).length > 0 && (
            <div className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
              {Object.keys(parsedArgs).length}
            </div>
          )}
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
      </div>

      {/* Collapsible Content */}
      {isExpanded && (
        <div className="border-t border-border/70">
          <div className="p-3">
            {parsedArgs && Object.keys(parsedArgs).length > 0 ? (
              <div className="space-y-2">
                {isPromptConfirmationTool && (
                  <PromptConfirmationContent
                    parsedArgs={parsedArgs as Record<string, unknown>}
                    resolvedPrompt={resolvedPrompt}
                  />
                )}

                {!isPromptConfirmationTool &&
                  Object.entries(parsedArgs).map(([key, value]) => (
                    <div
                      key={key}
                      className="rounded-lg border border-border/70 bg-background p-3 transition-shadow hover:shadow-sm"
                    >
                      <div className="flex flex-col gap-1">
                        <span className="font-medium text-foreground">
                          {CONFIRMATION_DISPLAY_LABELS[key] ?? key}:
                        </span>
                        <div className="break-all leading-relaxed text-muted-foreground">
                          {typeof value == 'object'
                            ? JSON.stringify(value, null, 2)
                            : String(value)}
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            ) : (
              <div className="rounded-lg border border-border/70 bg-background p-3 transition-shadow hover:shadow-sm">
                <div className="break-all leading-relaxed text-muted-foreground">
                  {inputs}
                </div>
              </div>
            )}
            {toolCall.result && <ToolCallContentV2 content={toolCall.result} />}

            {/* 确认按钮 - 仅在需要确认时显示 */}
            {needsConfirmation && (
              <div className="mt-4 border-t border-border/70 pt-4">
                <div className="flex gap-2">
                  {isPromptConfirmationTool && (
                    <Button
                      onClick={onRevise}
                      variant="outline"
                      className="flex-1"
                    >
                      返回修改
                    </Button>
                  )}
                  <Button
                    onClick={onConfirm}
                    className="flex-1"
                  >
                    <Check className="h-4 w-4 mr-2" />
                    {t('chat.toolCall.confirm', '确认')}
                  </Button>
                  <Button
                    onClick={onCancel}
                    variant="outline"
                    className="flex-1"
                  >
                    <X className="h-4 w-4 mr-2" />
                    {t('chat.toolCall.cancel', '取消')}
                  </Button>
                </div>
              </div>
            )}

            {/* 取消状态显示 */}
            {!needsConfirmation && toolCall.result === '工具调用已取消' && (
              <div className="mt-4 border-t border-border/70 pt-4">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <X className="h-4 w-4" />
                  <span className="text-sm">已取消本次生成</span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default ToolCallTag
