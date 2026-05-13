interface ElectronAPI {
  publishPost: (data: {
    channel: string
    title: string
    content: string
    images: string[]
    video: string
  }) => Promise<{ success?: boolean; error?: string }>
  pickImage: () => Promise<string[] | null>
  pickVideo: () => Promise<string | null>
  // Auto-updater methods
  checkForUpdates: () => Promise<{ message: string }>
  restartAndInstall: () => Promise<void>
  onUpdateDownloaded: (callback: (info: UpdateInfo) => void) => void
  removeUpdateDownloadedListener: () => void
  // Auth methods
  openBrowserUrl: (url: string) => Promise<{ success: boolean; error?: string }>
}

interface UpdateInfo {
  version: string
  files: unknown[]
  path: string
  sha512: string
  releaseDate: string
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI
  }
}

export {}
