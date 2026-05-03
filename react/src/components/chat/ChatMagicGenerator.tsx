import { sendMagicGenerate } from '@/api/magic'
import { eventBus, TCanvasMagicGenerateEvent } from '@/lib/event'
import { Message, PendingType } from '@/types/types'
import { useCallback, useEffect } from 'react'
import { DEFAULT_SYSTEM_PROMPT } from '@/constants'

type ChatMagicGeneratorProps = {
    sessionId: string
    canvasId: string
    messages: Message[]
    setMessages: (messages: Message[]) => void
    setPending: (pending: PendingType) => void
    scrollToBottom: () => void
}

const ChatMagicGenerator: React.FC<ChatMagicGeneratorProps> = ({
    sessionId,
    canvasId,
    messages,
    setMessages,
    setPending,
    scrollToBottom
}) => {
    const handleMagicGenerate = useCallback(
        async (data: TCanvasMagicGenerateEvent) => {
            setPending('text')

            const magicMessage: Message = {
                role: 'user',
                content: [
                    {
                        type: 'text',
                        text: '✨ GPT Image 2 Edit: redraw the selected canvas region and keep the overall composition.'
                    },
                    {
                        type: 'image_url',
                        image_url: {
                            url: data.base64
                        }
                    },
                ]
            }

            const newMessages = [...messages, magicMessage]
            setMessages(newMessages)
            scrollToBottom()

            try {
                await sendMagicGenerate({
                    sessionId: sessionId,
                    canvasId: canvasId,
                    newMessages: newMessages,
                    systemPrompt: localStorage.getItem('system_prompt') || DEFAULT_SYSTEM_PROMPT,
                    width: data.width,
                    height: data.height,
                    relationHint: data.relationHint,
                    selectedImageCount: data.selectedImageCount,
                    selectedImageBase64s: data.selectedImageBase64s,
                    selectedImagePositions: data.selectedImagePositions,
                })

                scrollToBottom()
                console.log('GPT Image 2 Edit message sent')
            } catch (error) {
                console.error('Failed to send GPT Image 2 Edit message:', error)
                setPending(false)
            }
        },
        [sessionId, canvasId, messages, setMessages, setPending, scrollToBottom]
    )

    useEffect(() => {
        eventBus.on('Canvas::MagicGenerate', handleMagicGenerate)

        return () => {
            eventBus.off('Canvas::MagicGenerate', handleMagicGenerate)
        }
    }, [handleMagicGenerate])

    return null
}

export default ChatMagicGenerator
