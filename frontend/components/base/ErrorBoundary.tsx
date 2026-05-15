'use client'

import { Component, ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button' // Assuming you have a button component

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error?: Error
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: any) {
    console.error('ErrorBoundary caught an error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }
      
      return (
        <div className="flex flex-col items-center justify-center p-8 bg-card border border-border rounded-lg">
          <AlertTriangle className="w-12 h-12 text-red-500 mb-4" />
          <h3 className="text-lg font-bold text-foreground mb-2">Something went wrong</h3>
          <p className="text-muted-foreground text-sm mb-4">
            {this.state.error?.message || 'An unexpected error occurred'}
          </p>
          <Button
            onClick={() => window.location.reload()}
            variant="outline"
            size="sm"
          >
            Reload Page
          </Button>
        </div>
      )
    }

    return this.props.children
  }
}
