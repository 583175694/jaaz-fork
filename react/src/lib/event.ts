import { ImageModelOption } from './imageModels'
import * as ISocket from '@/types/socket'
import mitt from 'mitt'

export type TCanvasAddImagesToChatEvent = {
  fileId: string
  canvasFileId?: string
  base64?: string
  width: number
  height: number
  x?: number
  y?: number
}[]

export type TCanvasImageRedrawEvent = {
  fileId: string
  base64: string
  width: number
  height: number
  timestamp: string
  selectedImageCount: number
  selectedElementCount: number
  selectedImageIds: string[]
  selectedImageBase64s: string[]
  selectedImagePositions: Array<{ fileId: string; x: number; y: number }>
  relationHint: 'single' | 'multi'
}

export type TCanvasGenerateVideoEvent = {
  selectedImages: TCanvasAddImagesToChatEvent
  userPrompt: string
  finalPrompt: string
  duration: number
  aspectRatio: string
  resolution: string
  videoModel: 'veo3-1-quality' | 'seedance-2.0-fast-i2v'
  selectionMode?: 'start_end_frames'
}

export type TCanvasGenerateStoryboardEvent = {
  selectedImage: TCanvasAddImagesToChatEvent[number]
  mainImageFileId?: string
  prompt: string
  shotCount: number
  aspectRatio: string
  imageModel: ImageModelOption
}

export type TCanvasGenerateMultiviewEvent = {
  selectedImage: TCanvasAddImagesToChatEvent[number]
  prompt: string
  presetName: string
  azimuth: number
  elevation: number
  framing: 'close' | 'medium' | 'full' | 'wide'
  aspectRatio: string
  imageModel: ImageModelOption
  previewOnly?: boolean
  replaceSource?: boolean
  mode?: 'multiview' | 'refinement'
}

export type TMaterialAddImagesToChatEvent = {
  filePath: string
  fileName: string
  fileType: string
  width?: number
  height?: number
}[]

export type TEvents = {
  // ********** Socket events - Start **********
  'Socket::Session::Error': ISocket.SessionErrorEvent
  'Socket::Session::Done': ISocket.SessionDoneEvent
  'Socket::Session::Info': ISocket.SessionInfoEvent
  'Socket::Session::JobQueued': ISocket.SessionJobQueuedEvent
  'Socket::Session::JobRunning': ISocket.SessionJobRunningEvent
  'Socket::Session::JobProgress': ISocket.SessionJobProgressEvent
  'Socket::Session::JobSucceeded': ISocket.SessionJobSucceededEvent
  'Socket::Session::JobFailed': ISocket.SessionJobFailedEvent
  'Socket::Session::ImageGenerated': ISocket.SessionImageGeneratedEvent
  'Socket::Session::VideoGenerated': ISocket.SessionVideoGeneratedEvent
  'Socket::Session::Delta': ISocket.SessionDeltaEvent
  'Socket::Session::ToolCall': ISocket.SessionToolCallEvent
  'Socket::Session::ToolCallArguments': ISocket.SessionToolCallArgumentsEvent
  'Socket::Session::ToolCallResult': ISocket.SessionToolCallResultEvent
  'Socket::Session::AllMessages': ISocket.SessionAllMessagesEvent
  'Socket::Session::ToolCallProgress': ISocket.SessionToolCallProgressEvent
  'Socket::Session::ToolCallPendingConfirmation': ISocket.SessionToolCallPendingConfirmationEvent
  'Socket::Session::ToolCallConfirmed': ISocket.SessionToolCallConfirmedEvent
  'Socket::Session::ToolCallCancelled': ISocket.SessionToolCallCancelledEvent
  // ********** Socket events - End **********

  // ********** Canvas events - Start **********
  'Canvas::AddImagesToChat': TCanvasAddImagesToChatEvent
  'Canvas::ImageRedraw': TCanvasImageRedrawEvent
  'Canvas::GenerateVideo': TCanvasGenerateVideoEvent
  'Canvas::GenerateStoryboard': TCanvasGenerateStoryboardEvent
  'Canvas::GenerateMultiview': TCanvasGenerateMultiviewEvent
  // ********** Canvas events - End **********

  // ********** Material events - Start **********
  'Material::AddImagesToChat': TMaterialAddImagesToChatEvent
  // ********** Material events - End **********
}

export const eventBus = mitt<TEvents>()
