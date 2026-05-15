'use client'

import { useEffect, useRef } from 'react'
import { createChart, IChartApi, ISeriesApi, ColorType, CrosshairMode } from 'lightweight-charts'

interface StockChartProps {
  symbol: string
  data?: any[]
}

export default function StockChart({ symbol, data: propData }: StockChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)

  useEffect(() => {
    if (!chartContainerRef.current) return

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#d1d5db',
      },
      grid: {
        vertLines: { color: '#374151' },
        horzLines: { color: '#374151' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      rightPriceScale: {
        borderColor: '#374151',
      },
      timeScale: {
        borderColor: '#374151',
        timeVisible: true,
      },
    })

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderDownColor: '#ef4444',
      borderUpColor: '#22c55e',
      wickDownColor: '#ef4444',
      wickUpColor: '#22c55e',
    })

    chartRef.current = chart
    seriesRef.current = candlestickSeries

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: 400,
        })
      }
    }

    window.addEventListener('resize', handleResize)
    handleResize()

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [])

  useEffect(() => {
    if (!seriesRef.current || !propData) return

    const formattedData = propData.map((item: any) => ({
      time: item.date,
      open: item.open,
      high: item.high,
      low: item.low,
      close: item.close,
    }))

    seriesRef.current.setData(formattedData)
  }, [propData])

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <h2 className="text-xl font-bold mb-4">{symbol} Chart</h2>
      <div ref={chartContainerRef} className="w-full" />
    </div>
  )
}
