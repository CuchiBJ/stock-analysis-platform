'use client'

import { useRef, useState, useEffect } from 'react'

interface VirtualizedTableProps<T> {
  data: T[]
  renderItem: (item: T, index: number) => React.ReactNode
  itemHeight: number
  height?: number
}

export default function VirtualizedTable<T>({
  data,
  renderItem,
  itemHeight,
  height = 600,
}: VirtualizedTableProps<T>) {
  const [scrollTop, setScrollTop] = useState(0)
  const [containerHeight, setContainerHeight] = useState(height)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (containerRef.current) {
      setContainerHeight(containerRef.current.clientHeight)
    }
  }, [height])

  const startIndex = Math.floor(scrollTop / itemHeight)
  const endIndex = Math.min(
    startIndex + Math.ceil(containerHeight / itemHeight) + 5,
    data.length
  )

  const visibleItems = data.slice(Math.max(0, startIndex - 5), endIndex)

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop)
  }

  return (
    <div
      ref={containerRef}
      style={{ height, overflow: 'auto' }}
      onScroll={handleScroll}
    >
      <div style={{ height: `${data.length * itemHeight}px`, position: 'relative' }}>
        {visibleItems.map((item, index) => {
          const actualIndex = Math.max(0, startIndex - 5) + index
          return (
            <div
              key={actualIndex}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: `${itemHeight}px`,
                transform: `translateY(${actualIndex * itemHeight}px)`,
              }}
            >
              {renderItem(item, actualIndex)}
            </div>
          )
        })}
      </div>
    </div>
  )
}
