## AI Studio

AI Studio 是一个本地优先的创意桌面应用，聚焦分镜、图片与视频生成。

### 当前生产内置能力

- 文本模型：`apipodcode:gpt-5.4`
- 图片工具：`generate_image_by_gpt_image_2_edit_apipod`，默认走 APIPod `nano-banana-pro`
- 视频工具：`generate_video_by_veo3_apipod`，默认走 APIPod `veo3-1-quality`，并可在高级选项切换到 `seedance-2.0-fast-i2v`

当前生产版本使用固定内置 provider 集合。文本模型固定，图片走内置 APIPod 图片模型，视频可在高级选项里切换内置 APIPod 视频模型。

### 桌面应用信息

- 产品名：`AI Studio`
- 平台：macOS、Windows
- 品牌资源：`react/public/app-logo.svg`

### 本地开发

要求：

- Python `>= 3.12`
- 与当前前端工具链兼容的 Node.js

运行方式：

```bash
cd react
npm install --force
npm run dev

cd ../server
pip install -r requirements.txt
python3 main.py
```
