'use client'

import { useEffect, useRef } from 'react'
import { createChart, ColorType, CrosshairMode, UTCTimestamp } from 'lightweight-charts'

interface MiniChartProps {
  data: number[]
  color?: 'green' | 'red' | 'neutral'
  height?: number
}

export default function MiniChart({ data, color = 'neutral', height = 40 }: MiniChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<any>(null)

  useEffect(() => {
    if (!chartContainerRef.current || data.length < 2) return

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: 'transparent',
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { visible: false },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { visible: false },
        horzLine: { visible: false },
      },
      rightPriceScale: { visible: false },
      timeScale: { visible: false },
      handleScroll: false,
      handleScale: false,
    })

    const lineSeries = chart.addAreaSeries({
      lineColor: color === 'green' ? '#22c55e' : color === 'red' ? '#ef4444' : '#737373',
      topColor: color === 'green' ? 'rgba(34, 197, 94, 0.4)' : color === 'red' ? 'rgba(239, 68, 68, 0.4)' : 'rgba(115, 115, 115, 0.4)',
      bottomColor: color === 'green' ? 'rgba(34, 197, 94, 0)' : color === 'red' ? 'rgba(239, 68, 68, 0)' : 'rgba(115, 115, 115, 0)',
      lineWidth: 1,
    })

    const chartData = data.map((value, index) => ({
      time: (index * 86400) as UTCTimestamp,
      value,
    }))

    lineSeries.setData(chartData)
    chart.timeScale().fitContent()

    chartRef.current = chart

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth })
      }
    }

    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [data, color, height])

  return <div ref={chartContainerRef} className="w-full" />
}
