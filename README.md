## AI Studio

AI Studio is a local-first creative desktop app for storyboard, image, and video generation.

### Runtime

- Text model: `apipodcode:gpt-5.4`
- Image tool: `generate_image_by_gpt_image_2_edit_apipod` using APIPod `nano-banana-pro`
- Video tool: `generate_video_by_veo3_apipod` with APIPod `veo3-1-quality` by default and `seedance-2.0-fast-i2v` selectable in advanced options

This production build uses a fixed built-in provider set. Text remains fixed, while image uses the built-in APIPod image model and video can switch between the built-in APIPod video models in advanced options.

### Desktop App

- Product name: `AI Studio`
- Platforms: macOS, Windows
- Branding asset: `react/public/app-logo.svg`

### Development

Requirements:

- Python `>= 3.12`
- Node.js compatible with the current frontend toolchain

Run locally:

```bash
cd react
npm install --force
npm run dev

cd ../server
pip install -r requirements.txt
python3 main.py
```
