export interface QuickScannerProps {
  loading?: boolean
}

export interface FilterPresetProps {
  name: string
  description: string
  count: number
  isActive: boolean
  onClick: () => void
}
