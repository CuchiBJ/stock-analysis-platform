'use client'

import { useEffect, useRef } from 'react'
import { createChart, ColorType, UTCTimestamp } from 'lightweight-charts'

interface SparklineProps {
  data: number[]
  color?: string
  width?: number
  height?: number
}

export default function Sparkline({ data, color = '#22c55e', width = 100, height = 30 }: SparklineProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<any>(null)

  useEffect(() => {
    if (!chartContainerRef.current || data.length < 2) return

    const chart = createChart(chartContainerRef.current, {
      width,
      height,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: 'transparent',
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { visible: false },
      },
      rightPriceScale: { visible: false },
      timeScale: { visible: false },
      handleScroll: false,
      handleScale: false,
    })

    const lineSeries = chart.addLineSeries({
      color,
      lineWidth: 2 as any,
    })

    const chartData = data.map((value, index) => ({
      time: (index * 86400) as UTCTimestamp,
      value,
    }))

    lineSeries.setData(chartData)
    chart.timeScale().fitContent()

    chartRef.current = chart

    return () => {
      chart.remove()
    }
  }, [data, color, width, height])

  return <div ref={chartContainerRef} />
}
