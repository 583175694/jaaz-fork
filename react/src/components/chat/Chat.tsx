import { sendMessages } from '@/api/chat'
import {
  getCurrentContinuity,
  getCurrentStoryboardPlan,
  getCurrentVideoBrief,
  getPendingWorkflowConfirmations,
} from '@/api/canvas'
import Blur from '@/components/common/Blur'
import { ScrollArea } from '@/components/ui/scroll-area'
import { eventBus, TEvents } from '@/lib/event'
import ChatCanvasMultiviewGenerator from './ChatCanvasMultiviewGenerator'
import ChatCanvasStoryboardGenerator from './ChatCanvasStoryboardGenerator'
import ChatCanvasVideoGenerator from './ChatCanvasVideoGenerator'
import {
  AssistantMessage,
  Message,
  Model,
  PendingType,
  Session,
  ToolCallFunctionName,
} from '@/types/types'
import { useSearch } from '@tanstack/react-router'
import { produce } from 'immer'
import { motion } from 'motion/react'
import { nanoid } from 'nanoid'
import {
  Dispatch,
  SetStateAction,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { PhotoProvider } from 'react-photo-view'
import { toast } from 'sonner'
import ChatTextarea from './ChatTextarea'
import MessageRegular from './Message/Regular'
import { ToolCallContent } from './Message/ToolCallContent'
import ToolCallTag from './Message/ToolCallTag'
import SessionSelector from './SessionSelector'
import ChatSpinner from './Spinner'
import ToolcallProgressUpdate from './ToolcallProgressUpdate'

import { useConfigs } from '@/contexts/configs'
import { useCanvas } from '@/contexts/canvas'
import 'react-photo-view/dist/react-photo-view.css'
import { DEFAULT_SYSTEM_PROMPT } from '@/constants'
import { ModelInfo, ToolInfo } from '@/api/model'
import MixedContent, { MixedContentImages, MixedContentText } from './Message/MixedContent'


type ChatInterfaceProps = {
  canvasId: string
  sessionList: Session[]
  setSessionList: Dispatch<SetStateAction<Session[]>>
  sessionId: string
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({
  canvasId,
  sessionList,
  setSessionList,
  sessionId: searchSessionId,
}) => {
  const { t } = useTranslation()
  const [session, setSession] = useState<Session | null>(null)
  const { initCanvas, setInitCanvas } = useConfigs()
  const { setCurrentContinuity, setCurrentVideoBrief, setStoryboardPlan } =
    useCanvas()

  useEffect(() => {
    if (sessionList.length > 0) {
      let _session = null
      if (searchSessionId) {
        _session = sessionList.find((s) => s.id === searchSessionId) || null
      } else {
        _session = sessionList[0]
      }
      setSession(_session)
    } else {
      setSession(null)
    }
  }, [sessionList, searchSessionId])

  const [messages, setMessages] = useState<Message[]>([])
  const [pending, setPending] = useState<PendingType>(
    initCanvas ? 'text' : false
  )
  const mergedToolCallIds = useRef<string[]>([])

  const sessionId = session?.id ?? searchSessionId

  const sessionIdRef = useRef<string>(session?.id || nanoid())
  const [expandingToolCalls, setExpandingToolCalls] = useState<string[]>([])
  const [pendingToolConfirmations, setPendingToolConfirmations] = useState<
    string[]
  >([])

  const scrollRef = useRef<HTMLDivElement>(null)
  const isAtBottomRef = useRef(false)

  const scrollToBottom = useCallback(() => {
    if (!isAtBottomRef.current) {
      return
    }
    setTimeout(() => {
      scrollRef.current?.scrollTo({
        top: scrollRef.current!.scrollHeight,
        behavior: 'smooth',
      })
    }, 200)
  }, [])

  const submitToolConfirmation = useCallback(
    async (
      toolCallId: string,
      action: 'confirm' | 'cancel' | 'revise'
    ) => {
      try {
        const response = await fetch('/api/tool_confirmation', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            session_id: sessionId,
            tool_call_id: toolCallId,
            action,
            confirmed: action === 'confirm',
          }),
        })

        if (!response.ok) {
          throw new Error(`Tool confirmation failed: ${response.status}`)
        }

        if (action !== 'confirm') {
          setPendingToolConfirmations((prev) =>
            prev.filter((id) => id !== toolCallId)
          )
        }
      } catch (error) {
        console.error('Failed to submit tool confirmation', {
          toolCallId,
          action,
          error,
        })
        toast.error('提交确认失败', {
          description: String(error),
        })
      }
    },
    [sessionId]
  )

  const mergeToolCallResult = (messages: Message[]) => {
    const messagesWithToolCallResult = messages.map((message, index) => {
      if (message.role === 'assistant' && message.tool_calls) {
        for (const toolCall of message.tool_calls) {
          // From the next message, find the tool call result
          for (let i = index + 1; i < messages.length; i++) {
            const nextMessage = messages[i]
            if (
              nextMessage.role === 'tool' &&
              nextMessage.tool_call_id === toolCall.id
            ) {
              toolCall.result = nextMessage.content
              mergedToolCallIds.current.push(toolCall.id)
            }
          }
        }
      }
      return message
    })

    return messagesWithToolCallResult
  }

  const upsertAssistantToolCallMessage = useCallback(
    (
      draft: Message[],
      payload: {
        id: string
        name: ToolCallFunctionName
        argumentsText: string
      }
    ) => {
      for (const message of draft) {
        if (message.role !== 'assistant' || !message.tool_calls) {
          continue
        }

        const existingToolCall = message.tool_calls.find(
          (toolCall) => toolCall.id === payload.id
        )
        if (!existingToolCall) {
          continue
        }

        existingToolCall.function.name = payload.name as typeof existingToolCall.function.name
        if (payload.argumentsText) {
          existingToolCall.function.arguments = payload.argumentsText
        }
        return
      }

      draft.push({
        role: 'assistant',
        content: '',
        tool_calls: [
          {
            type: 'function',
            function: {
              name: payload.name,
              arguments: payload.argumentsText,
            },
            id: payload.id,
          },
        ],
      })
    },
    []
  )

  const mergePendingToolCallsIntoMessages = useCallback(
    (nextMessages: Message[], currentMessages: Message[]) => {
      const merged = [...nextMessages]
      const seenToolCallIds = new Set<string>()

      for (const message of merged) {
        if (message.role !== 'assistant' || !message.tool_calls) {
          continue
        }
        for (const toolCall of message.tool_calls) {
          seenToolCallIds.add(toolCall.id)
        }
      }

      for (const message of currentMessages) {
        if (message.role !== 'assistant' || !message.tool_calls) {
          continue
        }

        const pendingToolCalls = message.tool_calls.filter((toolCall) => {
          return (
            pendingToolConfirmations.includes(toolCall.id) &&
            !seenToolCallIds.has(toolCall.id)
          )
        })

        if (pendingToolCalls.length === 0) {
          continue
        }

        merged.push({
          role: 'assistant',
          content: message.content ?? '',
          tool_calls: pendingToolCalls.map((toolCall) => ({
            ...toolCall,
            function: {
              ...toolCall.function,
            },
          })),
        })

        for (const toolCall of pendingToolCalls) {
          seenToolCallIds.add(toolCall.id)
        }
      }

      return merged
    },
    [pendingToolConfirmations]
  )

  const handleDelta = useCallback(
    (data: TEvents['Socket::Session::Delta']) => {
      if (data.session_id && data.session_id !== sessionId) {
        return
      }

      setPending('text')
      setMessages(
        produce((prev) => {
          const last = prev.at(-1)
          if (
            last?.role === 'assistant' &&
            last.content != null &&
            last.tool_calls == null
          ) {
            if (typeof last.content === 'string') {
              last.content += data.text
            } else if (
              last.content &&
              last.content.at(-1) &&
              last.content.at(-1)!.type === 'text'
            ) {
              ;(last.content.at(-1) as { text: string }).text += data.text
            }
          } else {
            prev.push({
              role: 'assistant',
              content: data.text,
            })
          }
        })
      )
      scrollToBottom()
    },
    [sessionId, scrollToBottom]
  )

  const handleToolCall = useCallback(
    (data: TEvents['Socket::Session::ToolCall']) => {
      if (data.session_id && data.session_id !== sessionId) {
        return
      }

      setMessages(
        produce((prev) => {
          console.log('👇tool_call event get', data)
          setPending('tool')
          upsertAssistantToolCallMessage(prev, {
            id: data.id,
            name: data.name,
            argumentsText: '',
          })
        })
      )

      setExpandingToolCalls(
        produce((prev) => {
          if (!prev.includes(data.id)) {
            prev.push(data.id)
          }
        })
      )
    },
    [sessionId, upsertAssistantToolCallMessage]
  )

  const handleToolCallPendingConfirmation = useCallback(
    (data: TEvents['Socket::Session::ToolCallPendingConfirmation']) => {
      if (data.session_id && data.session_id !== sessionId) {
        return
      }

      setMessages(
        produce((prev) => {
          console.log('👇tool_call_pending_confirmation event get', data)
          setPending('tool')
          upsertAssistantToolCallMessage(prev, {
            id: data.id,
            name: data.name,
            argumentsText: data.arguments,
          })
        })
      )

      setPendingToolConfirmations(
        produce((prev) => {
          if (!prev.includes(data.id)) {
            prev.push(data.id)
          }
        })
      )

      // 自动展开需要确认的工具调用
      setExpandingToolCalls(
        produce((prev) => {
          if (!prev.includes(data.id)) {
            prev.push(data.id)
          }
        })
      )
    },
    [sessionId, upsertAssistantToolCallMessage]
  )

  const syncPendingToolConfirmations = useCallback(async () => {
    if (!sessionId) {
      return
    }

    try {
      const data = await getPendingWorkflowConfirmations(sessionId)
      const items = Array.isArray(data?.items) ? data.items : []

      items.forEach((item) => {
        const normalized = {
          session_id: String(item.session_id || sessionId),
          type: 'tool_call_pending_confirmation' as TEvents['Socket::Session::ToolCallPendingConfirmation']['type'],
          id: String(item.tool_call_id || ''),
          name: String(item.tool_name || '') as ToolCallFunctionName,
          arguments: JSON.stringify(item.arguments || {}),
        }

        if (!normalized.id || !normalized.name) {
          return
        }

        handleToolCallPendingConfirmation(normalized)
      })
    } catch (error) {
      console.warn('Failed to sync pending tool confirmations', {
        sessionId,
        error,
      })
    }
  }, [handleToolCallPendingConfirmation, sessionId])

  const handleToolCallConfirmed = useCallback(
    (data: TEvents['Socket::Session::ToolCallConfirmed']) => {
      if (data.session_id && data.session_id !== sessionId) {
        return
      }

      setPendingToolConfirmations(
        produce((prev) => {
          return prev.filter((id) => id !== data.id)
        })
      )

      setExpandingToolCalls(
        produce((prev) => {
          if (!prev.includes(data.id)) {
            prev.push(data.id)
          }
        })
      )
    },
    [sessionId]
  )

  const handleToolCallCancelled = useCallback(
    (data: TEvents['Socket::Session::ToolCallCancelled']) => {
      if (data.session_id && data.session_id !== sessionId) {
        return
      }

      setPendingToolConfirmations(
        produce((prev) => {
          return prev.filter((id) => id !== data.id)
        })
      )

      // 更新工具调用的状态
      setMessages(
        produce((prev) => {
          prev.forEach((msg) => {
            if (msg.role === 'assistant' && msg.tool_calls) {
              msg.tool_calls.forEach((tc) => {
                if (tc.id === data.id) {
                  if (data.reason === 'revise') {
                    tc.result = '已返回修改'
                  } else if (data.reason === 'timeout') {
                    tc.result = '确认已超时'
                  } else {
                    tc.result = '工具调用已取消'
                  }
                }
              })
            }
          })
        })
      )
    },
    [sessionId]
  )

  const handleToolCallArguments = useCallback(
    (data: TEvents['Socket::Session::ToolCallArguments']) => {
      if (data.session_id && data.session_id !== sessionId) {
        return
      }

      setMessages(
        produce((prev) => {
          setPending('tool')
          const lastMessage = prev.find(
            (m) =>
              m.role === 'assistant' &&
              m.tool_calls &&
              m.tool_calls.find((t) => t.id == data.id)
          ) as AssistantMessage

          if (lastMessage) {
            const toolCall = lastMessage.tool_calls!.find(
              (t) => t.id == data.id
            )
            if (toolCall) {
              // 检查是否是待确认的工具调用，如果是则跳过参数追加
              if (pendingToolConfirmations.includes(data.id)) {
                return
              }
              toolCall.function.arguments += data.text
            }
          }
        })
      )
      scrollToBottom()
    },
    [sessionId, scrollToBottom, pendingToolConfirmations]
  )

  const handleToolCallResult = useCallback(
    (data: TEvents['Socket::Session::ToolCallResult']) => {
      console.log('😘🖼️tool_call_result event get', data)
      if (data.session_id && data.session_id !== sessionId) {
        return
      }
      // TODO: support other non string types of returning content like image_url
      if (data.message.content) {
        setMessages(
          produce((prev) => {
            prev.forEach((m) => {
              if (m.role === 'assistant' && m.tool_calls) {
                m.tool_calls.forEach((t) => {
                  if (t.id === data.id) {
                    t.result = data.message.content
                  }
                })
              }
            })
          })
        )
      }
    },
    [canvasId, sessionId]
  )

  const handleImageGenerated = useCallback(
    (data: TEvents['Socket::Session::ImageGenerated']) => {
      if (
        data.canvas_id &&
        data.canvas_id !== canvasId &&
        data.session_id !== sessionId
      ) {
        return
      }

      console.log('⭐️dispatching image_generated', data)
      setPending('image')
      window.dispatchEvent(
        new CustomEvent('app:refresh-canvas', {
          detail: {
            canvasId,
            reason: 'image-generated-socket',
          },
        })
      )
    },
    [canvasId, sessionId]
  )

  const handleAllMessages = useCallback(
    (data: TEvents['Socket::Session::AllMessages']) => {
      if (data.session_id && data.session_id !== sessionId) {
        return
      }

      setMessages((prev) => {
        console.log('👇all_messages', data.messages)
        const mergedMessages = mergePendingToolCallsIntoMessages(
          data.messages,
          prev
        )
        return mergeToolCallResult(mergedMessages)
      })
      syncPendingToolConfirmations()
      scrollToBottom()
    },
    [
      sessionId,
      scrollToBottom,
      syncPendingToolConfirmations,
      mergePendingToolCallsIntoMessages,
    ]
  )

  const handleDone = useCallback(
    (data: TEvents['Socket::Session::Done']) => {
      if (data.session_id && data.session_id !== sessionId) {
        return
      }

      setPending(false)
      scrollToBottom()
    },
    [sessionId, scrollToBottom]
  )

  const handleError = useCallback((data: TEvents['Socket::Session::Error']) => {
    setPending(false)
    toast.error('Error: ' + data.error, {
      closeButton: true,
      duration: 3600 * 1000,
      style: { color: 'red' },
    })
  }, [])

  const handleInfo = useCallback((data: TEvents['Socket::Session::Info']) => {
    toast.info(data.info, {
      closeButton: true,
      duration: 10 * 1000,
    })
  }, [])

  const handleVideoGenerated = useCallback(
    (data: TEvents['Socket::Session::VideoGenerated']) => {
      if (
        data.canvas_id &&
        data.canvas_id !== canvasId &&
        data.session_id !== sessionId
      ) {
        return
      }

      console.log('🎥 Chat received video_generated', data)
      setPending(false)
      window.dispatchEvent(
        new CustomEvent('app:refresh-canvas', {
          detail: {
            canvasId,
            reason: 'video-generated-socket',
          },
        })
      )
    },
    [canvasId, sessionId]
  )

  useEffect(() => {
    const handleScroll = () => {
      if (scrollRef.current) {
        isAtBottomRef.current =
          scrollRef.current.scrollHeight - scrollRef.current.scrollTop <=
          scrollRef.current.clientHeight + 1
      }
    }
    const scrollEl = scrollRef.current
    scrollEl?.addEventListener('scroll', handleScroll)

    eventBus.on('Socket::Session::Delta', handleDelta)
    eventBus.on('Socket::Session::ToolCall', handleToolCall)
    eventBus.on(
      'Socket::Session::ToolCallPendingConfirmation',
      handleToolCallPendingConfirmation
    )
    eventBus.on('Socket::Session::ToolCallConfirmed', handleToolCallConfirmed)
    eventBus.on('Socket::Session::ToolCallCancelled', handleToolCallCancelled)
    eventBus.on('Socket::Session::ToolCallArguments', handleToolCallArguments)
    eventBus.on('Socket::Session::ToolCallResult', handleToolCallResult)
    eventBus.on('Socket::Session::ImageGenerated', handleImageGenerated)
    eventBus.on('Socket::Session::VideoGenerated', handleVideoGenerated)
    eventBus.on('Socket::Session::AllMessages', handleAllMessages)
    eventBus.on('Socket::Session::Done', handleDone)
    eventBus.on('Socket::Session::Error', handleError)
    eventBus.on('Socket::Session::Info', handleInfo)
    return () => {
      scrollEl?.removeEventListener('scroll', handleScroll)

      eventBus.off('Socket::Session::Delta', handleDelta)
      eventBus.off('Socket::Session::ToolCall', handleToolCall)
      eventBus.off(
        'Socket::Session::ToolCallPendingConfirmation',
        handleToolCallPendingConfirmation
      )
      eventBus.off(
        'Socket::Session::ToolCallConfirmed',
        handleToolCallConfirmed
      )
      eventBus.off(
        'Socket::Session::ToolCallCancelled',
        handleToolCallCancelled
      )
      eventBus.off(
        'Socket::Session::ToolCallArguments',
        handleToolCallArguments
      )
      eventBus.off('Socket::Session::ToolCallResult', handleToolCallResult)
      eventBus.off('Socket::Session::ImageGenerated', handleImageGenerated)
      eventBus.off('Socket::Session::VideoGenerated', handleVideoGenerated)
      eventBus.off('Socket::Session::AllMessages', handleAllMessages)
      eventBus.off('Socket::Session::Done', handleDone)
      eventBus.off('Socket::Session::Error', handleError)
      eventBus.off('Socket::Session::Info', handleInfo)
    }
  })

  const initChat = useCallback(async () => {
    if (!sessionId) {
      return
    }

    sessionIdRef.current = sessionId

    const resp = await fetch('/api/chat_session/' + sessionId)
    const data = await resp.json()
    const msgs = data?.length ? data : []

    setMessages(mergeToolCallResult(msgs))
    await syncPendingToolConfirmations()
    try {
      const [continuityResp, storyboardResp, videoBriefResp] = await Promise.all([
        getCurrentContinuity(canvasId),
        getCurrentStoryboardPlan(canvasId),
        getCurrentVideoBrief(canvasId),
      ])
      setCurrentContinuity(continuityResp?.item || null)
      setStoryboardPlan(storyboardResp?.item || null)
      setCurrentVideoBrief(videoBriefResp?.item || null)
    } catch (error) {
      console.warn('Failed to sync workflow state during chat init', {
        canvasId,
        sessionId,
        error,
      })
    }
    if (msgs.length > 0) {
      setInitCanvas(false)
    }

    scrollToBottom()
  }, [
    canvasId,
    sessionId,
    scrollToBottom,
    setCurrentContinuity,
    setStoryboardPlan,
    setCurrentVideoBrief,
    setInitCanvas,
    syncPendingToolConfirmations,
  ])

  useEffect(() => {
    initChat()
  }, [sessionId, initChat])

  useEffect(() => {
    if (!sessionId) {
      return
    }

    const timer = window.setInterval(() => {
      void syncPendingToolConfirmations()
    }, 1500)

    return () => {
      window.clearInterval(timer)
    }
  }, [sessionId, syncPendingToolConfirmations])

  const onSelectSession = (sessionId: string) => {
    setSession(sessionList.find((s) => s.id === sessionId) || null)
    window.history.pushState(
      {},
      '',
      `/canvas/${canvasId}?sessionId=${sessionId}`
    )
  }

  const onClickNewChat = () => {
      const newSession: Session = {
      id: nanoid(),
      title: t('chat:newChat'),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      model: session?.model || 'gpt-5.4',
      provider: session?.provider || 'apipodcode',
    }

    setSessionList((prev) => [...prev, newSession])
    onSelectSession(newSession.id)
  }

  const onSendMessages = useCallback(
    async (
      data: Message[],
      configs: { textModel: Model; toolList: ToolInfo[] }
    ) => {
      setPending('text')
      setMessages(data)

      try {
        await sendMessages({
          sessionId: sessionId!,
          canvasId: canvasId,
          newMessages: data,
          textModel: configs.textModel,
          toolList: configs.toolList,
          systemPrompt:
            localStorage.getItem('system_prompt') || DEFAULT_SYSTEM_PROMPT,
        })
      } catch (error) {
        console.error('Failed to send chat messages:', error)
        setPending(false)
        toast.error(String(error))
      }

      if (searchSessionId !== sessionId) {
        window.history.pushState(
          {},
          '',
          `/canvas/${canvasId}?sessionId=${sessionId}`
        )
      }

      scrollToBottom()
    },
    [canvasId, sessionId, searchSessionId, scrollToBottom]
  )

  const handleCancelChat = useCallback(() => {
    setPending(false)
  }, [])

  return (
    <PhotoProvider>
      <div className='flex flex-col h-screen relative'>
        {/* Chat messages */}

        <header className='flex items-center px-2 py-2 absolute top-0 z-1 w-full'>
          <div className='flex-1 min-w-0'>
            <SessionSelector
              session={session}
              sessionList={sessionList}
              onClickNewChat={onClickNewChat}
              onSelectSession={onSelectSession}
            />
          </div>
          <Blur className='absolute top-0 left-0 right-0 h-full -z-1' />
        </header>

        <ScrollArea className='h-[calc(100vh-45px)]' viewportRef={scrollRef}>
          {messages.length > 0 ? (
            <div className='flex flex-col flex-1 px-4 pb-50 pt-15'>
              {/* Messages */}
              {messages.map((message, idx) => (
                <div key={`${idx}`} className='flex flex-col gap-4 mb-2'>
                  {/* Regular message content */}
                  {typeof message.content == 'string' &&
                    (message.role !== 'tool' ? (
                      <MessageRegular
                        message={message}
                        content={message.content}
                      />
                    ) : message.tool_call_id &&
                      mergedToolCallIds.current.includes(
                        message.tool_call_id
                      ) ? (
                      <></>
                    ) : (
                      <ToolCallContent
                        expandingToolCalls={expandingToolCalls}
                        message={message}
                      />
                    ))}

                  {/* 混合内容消息的文本部分 - 显示在聊天框内 */}
                  {Array.isArray(message.content) && (
                    <>
                      <MixedContentImages
                        contents={message.content}
                      />
                      <MixedContentText
                        message={message}
                        contents={message.content}
                      />
                    </>
                  )}

                  {message.role === 'assistant' &&
                    message.tool_calls &&
                    message.tool_calls.at(-1)?.function.name != 'finish' &&
                    message.tool_calls.map((toolCall, i) => {
                      return (
                        <ToolCallTag
                          key={toolCall.id}
                          toolCall={toolCall}
                          isExpanded={expandingToolCalls.includes(toolCall.id)}
                          onToggleExpand={() => {
                            if (expandingToolCalls.includes(toolCall.id)) {
                              setExpandingToolCalls((prev) =>
                                prev.filter((id) => id !== toolCall.id)
                              )
                            } else {
                              setExpandingToolCalls((prev) => [
                                ...prev,
                                toolCall.id,
                              ])
                            }
                          }}
                          requiresConfirmation={pendingToolConfirmations.includes(
                            toolCall.id
                          )}
                          onConfirm={() => {
                            void submitToolConfirmation(toolCall.id, 'confirm')
                          }}
                          onCancel={() => {
                            void submitToolConfirmation(toolCall.id, 'cancel')
                          }}
                          onRevise={() => {
                            void submitToolConfirmation(toolCall.id, 'revise')
                          }}
                        />
                      )
                    })}
                </div>
              ))}
              {pending && <ChatSpinner pending={pending} />}
              {pending && sessionId && (
                <ToolcallProgressUpdate sessionId={sessionId} />
              )}
            </div>
          ) : (
            <motion.div className='flex flex-col h-full p-4 items-start justify-start pt-16 select-none'>
              <motion.span
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                className='text-muted-foreground text-3xl'
              >
                {t('home:title')}
              </motion.span>
              <motion.span
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6 }}
                className='text-muted-foreground text-2xl'
              >
                {t('home:subtitle')}
              </motion.span>
            </motion.div>
          )}
        </ScrollArea>

        <div className='p-2 gap-2 sticky bottom-0'>
          <ChatTextarea
            sessionId={sessionId!}
            pending={!!pending}
            messages={messages}
            onSendMessages={onSendMessages}
            onCancelChat={handleCancelChat}
          />
          <ChatCanvasVideoGenerator
            sessionId={sessionId || ''}
            canvasId={canvasId}
            messages={messages}
            setMessages={setMessages}
            setPending={setPending}
            scrollToBottom={scrollToBottom}
          />
          <ChatCanvasStoryboardGenerator
            sessionId={sessionId || ''}
            canvasId={canvasId}
            messages={messages}
            setMessages={setMessages}
            setPending={setPending}
            scrollToBottom={scrollToBottom}
          />
          <ChatCanvasMultiviewGenerator
            sessionId={sessionId || ''}
            canvasId={canvasId}
            messages={messages}
            setMessages={setMessages}
            setPending={setPending}
            scrollToBottom={scrollToBottom}
          />
        </div>
      </div>
    </PhotoProvider>
  )
}

export default ChatInterface
