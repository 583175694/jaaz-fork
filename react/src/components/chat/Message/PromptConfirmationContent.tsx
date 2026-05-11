const PROMPT_CONFIRMATION_OBJECT_SECTIONS = [
  ['continuity_asset', 'Continuity 资产'],
  ['storyboard_plan', '分镜规划'],
  ['continuity_summary', '连续性摘要'],
  ['video_brief', '视频 Brief'],
] as const

const renderSectionCard = (
  title: string,
  content: React.ReactNode,
  key?: string
) => (
  <div
    key={key ?? title}
    className="bg-white dark:bg-gray-950 border border-green-200 dark:border-green-950 rounded-md p-3 hover:shadow-sm transition-shadow"
  >
    <div className="flex flex-col gap-2">
      <span className="font-bold text-green-900 dark:text-green-100">
        {title}
      </span>
      {content}
    </div>
  </div>
)

const renderJsonBlock = (value: unknown) => (
  <div className="text-sm text-gray-600 dark:text-gray-400 whitespace-pre-wrap break-words">
    {JSON.stringify(value, null, 2)}
  </div>
)

const renderMainImageSummary = (value: Record<string, unknown>) =>
  renderSectionCard(
    '主图摘要:',
    <>
      {Object.entries(value).map(([summaryKey, summaryValue]) => (
        <div
          key={summaryKey}
          className="text-sm text-gray-600 dark:text-gray-400 break-all"
        >
          <span className="font-semibold text-green-800 dark:text-green-200">
            {summaryKey}:
          </span>{' '}
          {typeof summaryValue === 'object'
            ? JSON.stringify(summaryValue, null, 2)
            : String(summaryValue)}
        </div>
      ))}
    </>
  )

const renderDisplaySummary = (value: Record<string, unknown>) =>
  renderSectionCard(
    '任务摘要:',
    <>
      {Object.entries(value).map(([summaryKey, summaryValue]) => (
        <div
          key={summaryKey}
          className="flex flex-col gap-1 rounded border border-green-100 bg-green-50/50 p-2 dark:border-green-900 dark:bg-green-950/30"
        >
          <span className="text-xs font-semibold uppercase tracking-wide text-green-800 dark:text-green-200">
            {summaryKey}
          </span>
          <div className="text-sm text-gray-600 dark:text-gray-400 break-all">
            {typeof summaryValue === 'object'
              ? JSON.stringify(summaryValue, null, 2)
              : String(summaryValue)}
          </div>
        </div>
      ))}
    </>
  )

type PromptConfirmationContentProps = {
  parsedArgs: Record<string, unknown>
  resolvedPrompt: string | null
}

const PromptConfirmationContent: React.FC<PromptConfirmationContentProps> = ({
  parsedArgs,
  resolvedPrompt,
}) => {
  const sections: React.ReactNode[] = []

  if (resolvedPrompt) {
    sections.push(
      renderSectionCard(
        'Prompt:',
        <div className="whitespace-pre-wrap text-gray-600 dark:text-gray-400 leading-relaxed break-words">
          {resolvedPrompt}
        </div>
      )
    )
  }

  if (
    parsedArgs.display_summary &&
    typeof parsedArgs.display_summary === 'object'
  ) {
    sections.push(
      renderDisplaySummary(parsedArgs.display_summary as Record<string, unknown>)
    )
  }

  for (const [key, title] of PROMPT_CONFIRMATION_OBJECT_SECTIONS) {
    const value = parsedArgs[key]
    if (!value || typeof value !== 'object') {
      continue
    }
    sections.push(renderSectionCard(`${title}:`, renderJsonBlock(value), key))
  }

  if (
    parsedArgs.main_image_summary &&
    typeof parsedArgs.main_image_summary === 'object'
  ) {
    sections.push(
      renderMainImageSummary(
        parsedArgs.main_image_summary as Record<string, unknown>
      )
    )
  }

  return <>{sections}</>
}

export default PromptConfirmationContent
