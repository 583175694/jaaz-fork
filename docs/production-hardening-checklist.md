# Production Hardening Checklist

## 目标

本清单用于将当前项目收敛为可发生产版本，重点覆盖两类改造：

1. 去除所有 `Jaaz` 品牌、登录、云账号体系及相关残留。
2. 将模型能力收敛为内置固定模型，不允许用户切换或配置 provider。

当前目标模型组合：

- 文本：`apipodcode:gpt-5.4`
- 图片：`images-2` 对应的 APIPod 内部工具
- 视频：`veo3.1` 对应的 APIPod 内部工具

本文档是全量改造 checklist，不区分优先级，默认全部完成后再发生产。

---

## 模型与运行时收口

### 1. 后端强制固定模型

- [ ] 服务端忽略客户端传入的 `text_model`
- [ ] 服务端忽略非白名单 `tool_list`
- [ ] 文本模型统一强制为 `apipodcode:gpt-5.4`
- [ ] 图片工具统一强制为最终确认的 `images-2` APIPod 工具
- [ ] 视频工具统一强制为最终确认的 `veo3.1` APIPod 工具
- [ ] 历史 session 中保存的 `provider/model` 不再作为真实执行依据

重点排查文件：

- [server/services/chat_service.py](/Users/sz-0203017616/code/github/jaaz/server/services/chat_service.py:1)
- [server/services/direct_video_service.py](/Users/sz-0203017616/code/github/jaaz/server/services/direct_video_service.py:1)
- [server/services/ad_video_prompt_runtime.py](/Users/sz-0203017616/code/github/jaaz/server/services/ad_video_prompt_runtime.py:1)
- [server/services/langgraph_service/agent_service.py](/Users/sz-0203017616/code/github/jaaz/server/services/langgraph_service/agent_service.py:1)

### 2. 后端只暴露固定模型

- [ ] `/api/list_models` 只返回 1 个文本模型
- [ ] `/api/list_tools` 只返回允许的图片/视频工具
- [ ] 不再返回 `openai`、`ollama`、`replicate`、`volces`、`jaaz`、`comfyui` 的可选能力

重点排查文件：

- [server/routers/root_router.py](/Users/sz-0203017616/code/github/jaaz/server/routers/root_router.py:1)
- [server/services/tool_service.py](/Users/sz-0203017616/code/github/jaaz/server/services/tool_service.py:1)

### 3. 清理工具注册与 provider 回退

- [ ] 移除 Jaaz 工具在生产路径中的注册
- [ ] 移除 Replicate 工具在生产路径中的注册
- [ ] 移除 Volces 工具在生产路径中的注册
- [ ] 关闭 ComfyUI 作为生产默认工具来源
- [ ] 图片 fallback 不再落到 `replicate`、`volces`、`jaaz`
- [ ] 视频 fallback 不再落到 `jaaz` 或其他非目标 provider

重点排查文件：

- [server/services/tool_service.py](/Users/sz-0203017616/code/github/jaaz/server/services/tool_service.py:1)
- [server/tools/utils/image_generation_core.py](/Users/sz-0203017616/code/github/jaaz/server/tools/utils/image_generation_core.py:1)
- [server/tools/video_generation/video_generation_core.py](/Users/sz-0203017616/code/github/jaaz/server/tools/video_generation/video_generation_core.py:1)

### 4. 锁死分镜、多视角、参考图链路

- [ ] 分镜生成不能回退到 `*_jaaz`
- [ ] 多视角生成不能回退到 `*_jaaz`
- [ ] 参考图工具选择不能回退到 `*_jaaz`
- [ ] 只保留 APIPod 可用参考图工具
- [ ] 修改错误提示，不再出现 `Flux Kontext` / `Jaaz` 历史语义

重点排查文件：

- [server/services/direct_storyboard_service.py](/Users/sz-0203017616/code/github/jaaz/server/services/direct_storyboard_service.py:1)
- [react/src/components/chat/canvasGenerationUtils.ts](/Users/sz-0203017616/code/github/jaaz/react/src/components/chat/canvasGenerationUtils.ts:1)

### 5. 统一视频确认与视频模型限制逻辑

- [ ] 将工具确认逻辑迁移到 APIPod 视频工具名
- [ ] 检查视频生成流程中的确认/跳过确认行为是否一致
- [ ] 检查多图参考限制是否与最终模型一致
- [ ] 视频确认链路不能再使用 `generate_video_by_veo3_fast_jaaz`

重点排查文件：

- [server/services/langgraph_service/StreamProcessor.py](/Users/sz-0203017616/code/github/jaaz/server/services/langgraph_service/StreamProcessor.py:1)
- [react/src/components/canvas/pop-bar/CanvasVideoGenerator.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/components/canvas/pop-bar/CanvasVideoGenerator.tsx:1)
- [server/tools/video_providers/apipod_provider.py](/Users/sz-0203017616/code/github/jaaz/server/tools/video_providers/apipod_provider.py:1)

---

## 前端交互与配置收口

### 6. 关闭模型切换

- [ ] 移除聊天区模型选择器 UI
- [ ] 移除文本模型选择交互
- [ ] 移除图片/视频工具选择交互
- [ ] 不再依赖 `localStorage.text_model`
- [ ] 不再依赖 `localStorage.disabled_tool_ids`

重点排查文件：

- [react/src/components/chat/ModelSelectorV3.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/components/chat/ModelSelectorV3.tsx:1)
- [react/src/components/chat/ModelSelectorV2.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/components/chat/ModelSelectorV2.tsx:1)
- [react/src/components/chat/ChatTextarea.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/components/chat/ChatTextarea.tsx:1)
- [react/src/contexts/configs.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/contexts/configs.tsx:1)

### 7. 关闭 Provider 配置能力

- [ ] 设置页不再允许新增 provider
- [ ] 设置页不再允许编辑 provider
- [ ] 设置页不再允许删除 provider
- [ ] `/api/config` 禁止模型/provider/api_key 写入
- [ ] 必要时 `/api/config` 改为只读或仅允许保存非模型类设置
- [ ] 处理旧 `config.toml`
- [ ] 忽略旧 provider 残留
- [ ] 启动时自动回正到生产固定配置

重点排查文件：

- [react/src/components/settings/dialog/providers.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/components/settings/dialog/providers.tsx:1)
- [react/src/components/settings/CommonSetting.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/components/settings/CommonSetting.tsx:1)
- [react/src/components/settings/AddProviderDialog.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/components/settings/AddProviderDialog.tsx:1)
- [server/routers/config_router.py](/Users/sz-0203017616/code/github/jaaz/server/routers/config_router.py:1)
- [react/src/api/config.ts](/Users/sz-0203017616/code/github/jaaz/react/src/api/config.ts:1)
- [server/services/config_service.py](/Users/sz-0203017616/code/github/jaaz/server/services/config_service.py:1)

### 8. 重构设置页定位

- [ ] 从 “Providers” 改成 “应用设置”
- [ ] 保留语言/主题/代理等仍需用户控制的选项
- [ ] 移除 provider / api key / model 管理能力
- [ ] 关闭本地模型相关设置入口

重点排查文件：

- [react/src/components/settings/dialog/index.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/components/settings/dialog/index.tsx:1)
- [react/src/components/settings/dialog/sidebar.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/components/settings/dialog/sidebar.tsx:1)
- [react/src/i18n/locales/en/settings.json](/Users/sz-0203017616/code/github/jaaz/react/src/i18n/locales/en/settings.json:1)
- [react/src/i18n/locales/zh-CN/settings.json](/Users/sz-0203017616/code/github/jaaz/react/src/i18n/locales/zh-CN/settings.json:1)
- [react/src/components/settings/ComfyuiSetting.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/components/settings/ComfyuiSetting.tsx:1)

---

## 登录、账户与云端能力移除

### 9. 移除登录体系

- [ ] 下线 `LoginDialog`
- [ ] 下线顶部登录入口
- [ ] 下线 `device auth` 登录流程
- [ ] 下线 refresh token 流程
- [ ] 移除 `jaaz_access_token`
- [ ] 移除 `jaaz_user_info`
- [ ] 不再在启动时自动探测 Jaaz 登录态

重点排查文件：

- [react/src/components/auth/LoginDialog.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/components/auth/LoginDialog.tsx:1)
- [react/src/components/auth/UserMenu.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/components/auth/UserMenu.tsx:1)
- [react/src/contexts/AuthContext.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/contexts/AuthContext.tsx:1)
- [react/src/api/auth.ts](/Users/sz-0203017616/code/github/jaaz/react/src/api/auth.ts:1)
- [react/src/App.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/App.tsx:1)

### 10. 移除充值与余额体系

- [ ] 下线余额查询
- [ ] 下线充值入口
- [ ] 下线余额不足拦截
- [ ] 移除所有 `billing` 跳转
- [ ] 移除所有 “credits / recharge / 充值” 文案

重点排查文件：

- [react/src/hooks/use-balance.ts](/Users/sz-0203017616/code/github/jaaz/react/src/hooks/use-balance.ts:1)
- [react/src/api/billing.ts](/Users/sz-0203017616/code/github/jaaz/react/src/api/billing.ts:1)
- [react/src/components/chat/ChatTextarea.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/components/chat/ChatTextarea.tsx:1)
- [react/src/components/auth/UserMenu.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/components/auth/UserMenu.tsx:1)
- [react/src/components/auth/PointsDisplay.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/components/auth/PointsDisplay.tsx:1)

### 11. 移除 Jaaz 云端模板能力

- [ ] 下线模板分享入口
- [ ] 下线 `${BASE_API_URL}/api/template/create` 依赖
- [ ] 下线对 `jaaz_access_token` 的模板接口鉴权依赖
- [ ] 若保留模板功能，替换为自有模板服务

重点排查文件：

- [react/src/components/chat/ShareTemplateDialog.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/components/chat/ShareTemplateDialog.tsx:1)
- [react/src/components/chat/Chat.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/components/chat/Chat.tsx:1)

### 12. 处理 Magic 功能去留

- [ ] 确认保留还是下线 `magic`
- [ ] 若保留，统一为当前生产方案并白标
- [ ] 若下线，删除前端入口、API、事件、文案
- [ ] 清理旧 `jaaz_magic_agent` 相关路径

重点排查文件：

- [server/services/magic_service.py](/Users/sz-0203017616/code/github/jaaz/server/services/magic_service.py:1)
- [server/routers/chat_router.py](/Users/sz-0203017616/code/github/jaaz/server/routers/chat_router.py:55)
- [react/src/components/chat/ChatMagicGenerator.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/components/chat/ChatMagicGenerator.tsx:1)
- [react/src/components/canvas/pop-bar/CanvasMagicGenerator.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/components/canvas/pop-bar/CanvasMagicGenerator.tsx:1)
- [server/services/OpenAIAgents_service/jaaz_magic_agent.py](/Users/sz-0203017616/code/github/jaaz/server/services/OpenAIAgents_service/jaaz_magic_agent.py:1)

---

## 品牌、名称与文案替换

### 13. 去品牌主入口

- [ ] 替换首页标题
- [ ] 替换首页副标题
- [ ] 替换顶部产品名
- [ ] 替换浏览器标题
- [ ] 替换 favicon
- [ ] 替换 Logo
- [ ] 替换欢迎语
- [ ] 替换登录相关品牌文案

重点排查文件：

- [react/index.html](/Users/sz-0203017616/code/github/jaaz/react/index.html:1)
- [react/src/routes/index.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/routes/index.tsx:1)
- [react/src/components/TopMenu.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/components/TopMenu.tsx:1)
- [react/src/constants.ts](/Users/sz-0203017616/code/github/jaaz/react/src/constants.ts:1)
- [react/src/i18n/locales/zh-CN/home.json](/Users/sz-0203017616/code/github/jaaz/react/src/i18n/locales/zh-CN/home.json:1)
- [react/src/i18n/locales/en/home.json](/Users/sz-0203017616/code/github/jaaz/react/src/i18n/locales/en/home.json:1)
- [react/src/i18n/locales/zh-CN/common.json](/Users/sz-0203017616/code/github/jaaz/react/src/i18n/locales/zh-CN/common.json:1)
- [react/src/i18n/locales/en/common.json](/Users/sz-0203017616/code/github/jaaz/react/src/i18n/locales/en/common.json:1)

### 14. 替换桌面端品牌信息

- [ ] 修改 `package.json.name`
- [ ] 修改 `package.json.appId`
- [ ] 修改 `package.json.productName`
- [ ] 替换 macOS 图标
- [ ] 替换 Windows 图标
- [ ] 替换 Electron 主窗口标题相关内容
- [ ] 替换预览窗口标题
- [ ] 替换日志文件名

重点排查文件：

- [package.json](/Users/sz-0203017616/code/github/jaaz/package.json:1)
- [electron/main.js](/Users/sz-0203017616/code/github/jaaz/electron/main.js:1)
- [scripts/notarize.js](/Users/sz-0203017616/code/github/jaaz/scripts/notarize.js:1)

### 15. 移除 Jaaz 域名与远程品牌资源 fallback

- [ ] 清理 `https://jaaz.app` 默认值
- [ ] 清理所有外链、下载地址、billing 地址
- [ ] 清理 logo/favicon 远程地址

重点排查文件：

- [react/src/constants.ts](/Users/sz-0203017616/code/github/jaaz/react/src/constants.ts:1)
- [electron/main.js](/Users/sz-0203017616/code/github/jaaz/electron/main.js:1)
- [README.md](/Users/sz-0203017616/code/github/jaaz/README.md:1)
- [README_zh.md](/Users/sz-0203017616/code/github/jaaz/README_zh.md:1)

### 16. 统一错误提示与用户可见文案

- [ ] 不再出现 Jaaz 品牌名
- [ ] 不再出现 “去 Settings -> Providers 更新 API key”
- [ ] 不再出现旧 provider 名称作为用户指引
- [ ] 清理所有 “login to Jaaz / recharge / cloud AI models” 类文案

重点排查文件：

- [server/services/langgraph_service/agent_service.py](/Users/sz-0203017616/code/github/jaaz/server/services/langgraph_service/agent_service.py:1)
- [react/src/i18n/locales/en/common.json](/Users/sz-0203017616/code/github/jaaz/react/src/i18n/locales/en/common.json:1)
- [react/src/i18n/locales/zh-CN/common.json](/Users/sz-0203017616/code/github/jaaz/react/src/i18n/locales/zh-CN/common.json:1)

---

## 本地能力、旧服务与残留系统清理

### 17. 下线旧 Jaaz service

- [ ] 清理 `jaaz_service.py`
- [ ] 清理 `jaaz_magic_agent.py`
- [ ] 清理所有 `generate_*_jaaz.py` 在主链路中的依赖
- [ ] 确认删除后不影响现有保留功能

重点排查文件：

- [server/services/jaaz_service.py](/Users/sz-0203017616/code/github/jaaz/server/services/jaaz_service.py:1)
- [server/services/OpenAIAgents_service/jaaz_magic_agent.py](/Users/sz-0203017616/code/github/jaaz/server/services/OpenAIAgents_service/jaaz_magic_agent.py:1)
- [server/services/OpenAIAgents_service/__init__.py](/Users/sz-0203017616/code/github/jaaz/server/services/OpenAIAgents_service/__init__.py:1)

### 18. 关闭本地模型入口

- [ ] 关闭 Ollama 探测
- [ ] 关闭 ComfyUI 自动启动
- [ ] 关闭本地模型相关设置入口
- [ ] 关闭本地模型相关文案

重点排查文件：

- [server/routers/root_router.py](/Users/sz-0203017616/code/github/jaaz/server/routers/root_router.py:1)
- [react/src/App.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/App.tsx:1)
- [react/src/components/settings/ComfyuiSetting.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/components/settings/ComfyuiSetting.tsx:1)

### 19. 全局替换内部命名

- [ ] 替换 `jaaz:refresh-canvas`
- [ ] 替换 `jaaz_access_token`
- [ ] 替换 `jaaz_user_info`
- [ ] 替换 `jaaz-log.txt`
- [ ] 替换 `/tmp/jaaz-last-openai-payload.json`
- [ ] 替换 `subfolder='jaaz'`
- [ ] 替换 `Jaaz-App/1.0.0`
- [ ] 替换 `autoSaveId="jaaz-chat-panel"`

重点排查文件：

- [react/src/routes/assets.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/routes/assets.tsx:1)
- [react/src/routes/canvas.$id.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/routes/canvas.$id.tsx:1)
- [react/src/contexts/canvas.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/contexts/canvas.tsx:1)
- [electron/main.js](/Users/sz-0203017616/code/github/jaaz/electron/main.js:1)
- [electron/comfyUIInstaller.js](/Users/sz-0203017616/code/github/jaaz/electron/comfyUIInstaller.js:1)
- [server/routers/comfyui_execution.py](/Users/sz-0203017616/code/github/jaaz/server/routers/comfyui_execution.py:359)
- [server/services/langgraph_service/agent_service.py](/Users/sz-0203017616/code/github/jaaz/server/services/langgraph_service/agent_service.py:205)

### 20. 清理包与构建命名

- [ ] 替换 `@jaaz/agent-ui`
- [ ] 替换 Vite lib build 名称
- [ ] 替换构建产物中 Jaaz 相关标识

重点排查文件：

- [react/package.json](/Users/sz-0203017616/code/github/jaaz/react/package.json:1)
- [react/vite.config.ts](/Users/sz-0203017616/code/github/jaaz/react/vite.config.ts:1)

---

## 状态迁移、文档与法务清理

### 21. 前端状态迁移

- [ ] 清理 `localStorage` 中旧 token
- [ ] 清理 `text_model`
- [ ] 清理 `disabled_tool_ids`
- [ ] 必要时清理 IndexedDB query cache
- [ ] 设计升级后的兼容迁移逻辑

重点排查文件：

- [react/src/contexts/configs.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/contexts/configs.tsx:1)
- [react/src/App.tsx](/Users/sz-0203017616/code/github/jaaz/react/src/App.tsx:1)

### 22. 清理 README、docs、scripts

- [ ] 清理 README 中 Jaaz 品牌与下载地址
- [ ] 清理 docs 中 Jaaz 场景描述
- [ ] 清理脚本 help 与注释中的 Jaaz 语义

重点排查文件：

- [README.md](/Users/sz-0203017616/code/github/jaaz/README.md:1)
- [README_zh.md](/Users/sz-0203017616/code/github/jaaz/README_zh.md:1)
- [README-zh.md](/Users/sz-0203017616/code/github/jaaz/README-zh.md:1)
- [docs/README.md](/Users/sz-0203017616/code/github/jaaz/docs/README.md:1)
- [scripts/probe_zenlayer_veo_models.py](/Users/sz-0203017616/code/github/jaaz/scripts/probe_zenlayer_veo_models.py:1)

### 23. 法务与商标文本

- [ ] 处理 `LICENSE` 中的 Jaaz 名称
- [ ] 处理商标与品牌归属声明
- [ ] 评估是否需要替换为新的许可证文本

重点排查文件：

- [LICENSE](/Users/sz-0203017616/code/github/jaaz/LICENSE:1)

---

## 验收标准

- [ ] 首次启动无需登录，用户一打开即可直接使用
- [ ] UI 中看不到模型切换
- [ ] UI 中看不到 provider / API key / model 管理
- [ ] UI 中看不到登录 / 充值 / 账户 / 余额
- [ ] 文本始终走 `gpt-5.4`
- [ ] 图片始终走最终确认的 `images-2` 对应 APIPod 工具
- [ ] 视频始终走最终确认的 `veo3.1` 对应 APIPod 工具
- [ ] 分镜、多视角、参考图、Magic、视频生成等二级能力不会回退到 Jaaz 或其他 provider
- [ ] 断网、缺 key、接口报错时，不出现 Jaaz 文案或 Jaaz 域名
- [ ] `rg -n "Jaaz|jaaz|JAAZ"` 结果只剩明确接受保留的历史内容，理想情况为 0

---

## 发版前必须确认

- [ ] 新产品名
- [ ] 新 Logo / favicon / 桌面端图标
- [ ] 新 `appId`
- [ ] 新包名
- [ ] `images-2` 的准确内部模型标识
- [ ] `images-2` 对应的准确工具名
- [ ] `veo3.1` 最终固定 `quality` 还是 `fast`
- [ ] APIPod key 采用本地内置还是服务端中转
- [ ] `模板分享` 保留还是下线
- [ ] `Magic 重绘` 保留还是下线

---

## 建议执行顺序

1. 后端固定模型，锁 `/api/config`，移除登录充值，移除模型切换。
2. 清理分镜/视频/参考图等二级回退链路，统一到 APIPod。
3. 替换品牌、图标、包名、域名与文案。
4. 清理缓存迁移、内部命名、文档、脚本和许可证残留。
5. 做完整回归测试后再发版。
