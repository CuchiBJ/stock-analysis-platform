'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import DataHealthBanner from './DataHealthBanner'

interface DashboardLayoutProps {
  children: React.ReactNode
}

const navItems = [
  { href: '/dashboard',   label: 'Dashboard'   },
  { href: '/queue',       label: 'Queue'       },
  { href: '/calibration', label: 'Calibration' },
  { href: '/guide',       label: 'Guide'       },
]

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const pathname = usePathname()

  return (
    <div className="min-h-screen bg-background">
      <DataHealthBanner />
      {/* Header */}
      <nav className="border-b border-border bg-card">
        <div className="container mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <Link href="/" className="text-xl font-bold text-foreground">
              Stock Analysis
            </Link>
            <div className="flex gap-6">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'text-sm font-medium transition-colors',
                    pathname === item.href
                      ? 'text-foreground'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                >
                  {item.label}
                </Link>
              ))}
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-6">
        {children}
      </main>
    </div>
  )
}
