import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const WS_URL = API_URL.replace(/^http/, 'ws')

export function getTimeAgo(timestamp: string): string {
  const diffMs = Date.now() - new Date(timestamp).getTime()
  const diffMins = Math.floor(diffMs / 60000)
  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  return `${Math.floor(diffHours / 24)}d ago`
}

export function getSeverityColor(severity: string): string {
  const map: Record<string, string> = {
    positive: 'bg-green-500/20 border-green-500/30',
    neutral:  'bg-blue-500/20 border-blue-500/30',
    negative: 'bg-orange-500/20 border-orange-500/30',
    critical: 'bg-red-500/20 border-red-500/30',
  }
  return map[severity] ?? 'bg-slate-500/20 border-slate-500/30'
}

export function getSeverityText(severity: string): string {
  const map: Record<string, string> = {
    positive: 'text-green-400',
    neutral:  'text-blue-400',
    negative: 'text-orange-400',
    critical: 'text-red-400',
  }
  return map[severity] ?? 'text-slate-400'
}

export function getHealthColor(score: number): string {
  if (score >= 0.6) return 'text-green-400'
  if (score >= 0.4) return 'text-yellow-400'
  return 'text-red-400'
}

export function getHealthBarColor(score: number): string {
  if (score >= 0.6) return 'bg-green-500'
  if (score >= 0.4) return 'bg-yellow-500'
  return 'bg-red-500'
}
