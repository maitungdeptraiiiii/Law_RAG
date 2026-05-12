'use client'

import { createContext, useContext } from 'react'
import type { RetrievalSettings } from '@/lib/types'

interface RetrievalSettingsContextValue {
  settings: RetrievalSettings
  setSettings: (settings: RetrievalSettings) => void
}

const RetrievalSettingsContext = createContext<RetrievalSettingsContextValue | null>(null)

export function RetrievalSettingsProvider({
  value,
  children,
}: {
  value: RetrievalSettingsContextValue
  children: React.ReactNode
}) {
  return (
    <RetrievalSettingsContext.Provider value={value}>
      {children}
    </RetrievalSettingsContext.Provider>
  )
}

export function useRetrievalSettings() {
  const context = useContext(RetrievalSettingsContext)
  if (!context) {
    throw new Error('useRetrievalSettings must be used within RetrievalSettingsProvider')
  }
  return context
}