/**
 * Settings API - 设置相关的API接口
 *
 * 该模块提供了与后端设置服务交互的所有API函数，包括：
 * - 设置文件存在性检查
 * - 获取和更新设置
 * - 代理配置管理
 * - 代理连接测试
 */

export async function getSettingsFileExists(): Promise<{ exists: boolean }> {
  const response = await fetch('/api/settings/exists')
  return await response.json()
}

export async function getSettings(): Promise<Record<string, unknown>> {
  const response = await fetch('/api/settings')
  return await response.json()
}

export async function updateSettings(
  settings: Record<string, unknown>
): Promise<{
  status: string
  message: string
}> {
  const response = await fetch('/api/settings', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(settings),
  })
  return await response.json()
}

export async function getProxySettings(): Promise<Record<string, unknown>> {
  const response = await fetch('/api/settings/proxy')
  return await response.json()
}

export async function updateProxySettings(
  proxyConfig: Record<string, unknown>
): Promise<{
  status: string
  message: string
}> {
  const response = await fetch('/api/settings/proxy', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(proxyConfig),
  })
  return await response.json()
}

// 文件系统浏览相关的API
export const browseFolderApi = async (path: string = '') => {
  const response = await fetch(
    `/api/browse_filesystem?path=${encodeURIComponent(path)}`
  )
  if (!response.ok) {
    throw new Error('Failed to browse folder')
  }
  return response.json()
}

export const getMediaFilesApi = async (path: string) => {
  const response = await fetch(
    `/api/get_media_files?path=${encodeURIComponent(path)}`
  )
  if (!response.ok) {
    throw new Error('Failed to get media files')
  }
  return response.json()
}

export const openFolderInExplorer = async (path: string) => {
  const response = await fetch('/api/open_folder_in_explorer', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ path }),
  })
  if (!response.ok) {
    throw new Error('Failed to open folder in explorer')
  }
  return response.json()
}

export const getFileThumbnailApi = async (filePath: string) => {
  const response = await fetch(
    `/api/get_file_thumbnail?file_path=${encodeURIComponent(filePath)}`
  )
  if (!response.ok) {
    throw new Error('Failed to get file thumbnail')
  }
  return response.json()
}

// 获取文件服务URL
export const getFileServiceUrl = (filePath: string) => {
  return `/api/serve_file?file_path=${encodeURIComponent(filePath)}`
}

// 获取文件详细信息
export const getFileInfoApi = async (filePath: string) => {
  const response = await fetch(
    `/api/get_file_info?file_path=${encodeURIComponent(filePath)}`
  )
  if (!response.ok) {
    throw new Error('Failed to get file info')
  }
  return response.json()
}

// 获取用户的My Assets目录路径
export const getMyAssetsDirPath = async () => {
  const response = await fetch('/api/settings/my_assets_dir_path')
  const result = await response.json()
  return result
}

// PNG metadata 现在通过前端直接读取 (readPNGMetadata in @/utils/pngMetadata)
// 这样更快，避免了后端处理的开销
