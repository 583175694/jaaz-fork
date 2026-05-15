export type ImageModelOption = 'gpt-image-2' | 'nano-banana-pro'

export const DEFAULT_IMAGE_MODEL: ImageModelOption = 'nano-banana-pro'

export const IMAGE_MODEL_OPTIONS: Array<{
  value: ImageModelOption
  label: string
}> = [
  {
    value: 'nano-banana-pro',
    label: 'Nano Banana',
  },
  {
    value: 'gpt-image-2',
    label: 'Image-2',
  },
]
