import { Message, MessageContent } from '@/types/types'
import { Markdown } from '../Markdown'
import MessageImage from './Image'

type MixedContentProps = {
  message: Message
  contents: MessageContent[]
}

type MixedContentImagesProps = {
  contents: MessageContent[]
}

type MixedContentTextProps = {
  message: Message
  contents: MessageContent[]
}

type TextMessageContent = Extract<MessageContent, { type: 'text' }>
type ImageMessageContent = Extract<MessageContent, { type: 'image_url' }>

const INTERNAL_BLOCK_PATTERNS = [
  /<input_images\b[^>]*>[\s\S]*?<\/input_images>/gi,
  /<video_generation_intent>[\s\S]*?<\/video_generation_intent>/gi,
] as const

const INTERNAL_INLINE_PATTERNS = [
  /<aspect_ratio>[\s\S]*?<\/aspect_ratio>/gi,
  /<quantity>[\s\S]*?<\/quantity>/gi,
  /<image_model>[\s\S]*?<\/image_model>/gi,
  /<selection_mode>[\s\S]*?<\/selection_mode>/gi,
  /<task>[\s\S]*?<\/task>/gi,
  /<preset_name>[\s\S]*?<\/preset_name>/gi,
  /<azimuth>[\s\S]*?<\/azimuth>/gi,
  /<elevation>[\s\S]*?<\/elevation>/gi,
  /<framing>[\s\S]*?<\/framing>/gi,
  /<preview_only>[\s\S]*?<\/preview_only>/gi,
  /<replace_source>[\s\S]*?<\/replace_source>/gi,
  /<start_frame\b[^>]*\/>/gi,
  /<end_frame\b[^>]*\/>/gi,
  /<source_image\b[^>]*\/>/gi,
] as const

const toFileUrl = (fileId: string) => {
  const normalized = String(fileId || '').trim()
  if (!normalized) {
    return ''
  }

  if (
    normalized.startsWith('data:') ||
    normalized.startsWith('http://') ||
    normalized.startsWith('https://') ||
    normalized.startsWith('/api/file/')
  ) {
    return normalized
  }

  return `/api/file/${normalized}`
}

const parseTagAttributes = (tag: string) => {
  const attributes: Record<string, string> = {}

  tag.replace(/([a-zA-Z_]+)="([^"]*)"/g, (_, key: string, value: string) => {
    attributes[key] = value
    return ''
  })

  return attributes
}

const getNormalizedImageKeyFromUrl = (url: string) => {
  const normalized = String(url || '').trim()
  if (!normalized) {
    return ''
  }

  const apiFileMatch = normalized.match(/\/api\/file\/([^/?#]+)/i)
  if (apiFileMatch?.[1]) {
    return apiFileMatch[1]
  }

  const fileIdMatch = normalized.match(/(?:^|[?&/])(im_[A-Za-z0-9._-]+)/)
  if (fileIdMatch?.[1]) {
    return fileIdMatch[1]
  }

  return normalized
}

const isTextContent = (content: MessageContent): content is TextMessageContent =>
  content.type === 'text'

const isImageContent = (content: MessageContent): content is ImageMessageContent =>
  content.type === 'image_url'

const getNormalizedImageKeyFromContent = (content: ImageMessageContent) => {
  return getNormalizedImageKeyFromUrl(content.image_url.url)
}

const extractInlineImagesFromText = (text: string): ImageMessageContent[] => {
  const images: ImageMessageContent[] = []
  const seenUrls = new Set<string>()
  const tags = text.match(/<(image|source_image|start_frame|end_frame)\b[^>]*\/>/gi) || []

  for (const tag of tags) {
    const attributes = parseTagAttributes(tag)
    const url = toFileUrl(
      attributes.file_id ||
        attributes.reference_file_id ||
        attributes.reference_image_file_id ||
        attributes.canvas_file_id
    )

    if (!url || seenUrls.has(url)) {
      continue
    }

    seenUrls.add(url)
    images.push({
      type: 'image_url',
      image_url: { url },
    })
  }

  return images
}

const sanitizeVisibleText = (text: string) => {
  let sanitized = text

  sanitized = sanitized.replace(/<prompt>([\s\S]*?)<\/prompt>/gi, '\n\n$1')

  INTERNAL_BLOCK_PATTERNS.forEach((pattern) => {
    sanitized = sanitized.replace(pattern, '')
  })

  INTERNAL_INLINE_PATTERNS.forEach((pattern) => {
    sanitized = sanitized.replace(pattern, '')
  })

  sanitized = sanitized
    .replace(/!\[.*?\]\(.*?\)/g, '')
    .replace(/!\[.*?\]\[.*?\]/g, '')
    .replace(/^\s*$/gm, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()

  return sanitized
}

// 图片组件 - 独立显示在聊天框外
export const MixedContentImages: React.FC<MixedContentImagesProps> = ({ contents }) => {
  const textContents = contents.filter(isTextContent)
  const explicitImages = contents.filter(isImageContent)
  const inlineImages: ImageMessageContent[] =
    explicitImages.length > 0
      ? []
      : textContents.flatMap((content) => extractInlineImagesFromText(content.text))

  const seenImageKeys = new Set<string>()
  const images: ImageMessageContent[] = [...explicitImages, ...inlineImages].filter((content) => {
    const key = getNormalizedImageKeyFromContent(content)
    const url = String(content.image_url.url || '').trim()
    if (!url) {
      return false
    }
    const dedupeKey = key || url
    if (seenImageKeys.has(dedupeKey)) {
      return false
    }
    seenImageKeys.add(dedupeKey)
    return true
  })

  if (images.length === 0) return null

  return (
    <div className="px-4">
      {images.length === 1 ? (
        // 单张图片：保持长宽比，最大宽度限制
        <div className="max-h-[512px] flex justify-end">
          <MessageImage content={images[0]} />
        </div>
      ) : (
        // 多张图片：横向排布，第一张图靠右
        <div className="flex gap-2 max-h-[512px] justify-end flex-row-reverse">
          {images.map((image, index) => (
            <div key={index} className="max-h-[512px]">
              <MessageImage content={image} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// 文本组件 - 显示在聊天框内
export const MixedContentText: React.FC<MixedContentTextProps> = ({ message, contents }) => {
  const textContents = contents.filter(isTextContent)

  const combinedText = textContents
    .map((content) => content.text)
    .join('\n')
  const visibleText = sanitizeVisibleText(combinedText)

  if (!visibleText) return null

  return (
    <>
      {message.role === 'user' ? (
        <div className="flex justify-end mb-4">
          <div className="bg-primary text-primary-foreground rounded-xl rounded-br-md px-4 py-3 text-left max-w-[300px] w-fit">
            <div className="w-full">
              <Markdown>{visibleText}</Markdown>
            </div>
          </div>
        </div>
      ) : (
        <div className="text-gray-800 dark:text-gray-200 text-left items-start mb-4">
          <div className="w-full">
            <Markdown>{visibleText}</Markdown>
          </div>
        </div>
      )}
    </>
  )
}

// 保持原有的MixedContent组件作为向后兼容（如果需要的话）
const MixedContent: React.FC<MixedContentProps> = ({ message, contents }) => {
  return (
    <>
      <MixedContentImages contents={contents} />
      <MixedContentText message={message} contents={contents} />
    </>
  )
}

export default MixedContent
