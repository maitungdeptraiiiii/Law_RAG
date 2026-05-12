'use client'

import { useState, useCallback } from 'react'
import Link from 'next/link'
import { Scale, PanelLeftClose, PanelLeft, Settings2, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { RetrievalSettingsProvider } from '@/components/chat/retrieval-settings-context'
import { SessionSidebar } from '@/components/chat/session-sidebar'
import { RetrievalSettingsDrawer } from '@/components/chat/retrieval-settings-drawer'
import type { RetrievalSettings } from '@/lib/types'

const defaultSettings: RetrievalSettings = {
  mode: 'hybrid',
  vectorBackend: 'faiss',
  topK: 5,
  queryRewrite: true,
}

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [settings, setSettings] = useState<RetrievalSettings>(defaultSettings)

  const handleNewChat = useCallback(() => {
    // Navigate to fresh chat - in real app, this would clear the current session
    window.location.href = '/chat'
  }, [])

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Sidebar */}
      <aside
        className={`${
          sidebarOpen ? 'w-72' : 'w-0'
        } flex-shrink-0 border-r border-border bg-sidebar transition-all duration-300 overflow-hidden`}
      >
        <div className="flex flex-col h-full w-72">
          {/* Sidebar Header */}
          <div className="flex items-center justify-between h-14 px-4 border-b border-sidebar-border">
            <Link href="/" className="flex items-center gap-2">
              <Scale className="h-5 w-5 text-sidebar-primary" />
              <span className="font-semibold text-sm">Law RAG</span>
            </Link>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setSidebarOpen(false)}
            >
              <PanelLeftClose className="h-4 w-4" />
              <span className="sr-only">Ẩn thanh bên</span>
            </Button>
          </div>

          {/* New Chat Button */}
          <div className="p-3">
            <Button 
              onClick={handleNewChat} 
              className="w-full justify-start"
              variant="outline"
            >
              <Plus className="h-4 w-4 mr-2" />
              Cuộc hội thoại mới
            </Button>
          </div>

          {/* Sessions List */}
          <SessionSidebar />
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0">
        {/* Top Bar */}
        <header className="flex items-center justify-between h-14 px-4 border-b border-border bg-card">
          <div className="flex items-center gap-2">
            {!sidebarOpen && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => setSidebarOpen(true)}
              >
                <PanelLeft className="h-4 w-4" />
                <span className="sr-only">Hiện thanh bên</span>
              </Button>
            )}
            {!sidebarOpen && (
              <Link href="/" className="flex items-center gap-2 ml-2">
                <Scale className="h-5 w-5 text-primary" />
                <span className="font-semibold text-sm hidden sm:inline">Law RAG</span>
              </Link>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSettingsOpen(true)}
              className="text-muted-foreground"
            >
              <Settings2 className="h-4 w-4 mr-2" />
              <span className="hidden sm:inline">Cài đặt truy xuất</span>
            </Button>
          </div>
        </header>

        {/* Chat Content */}
        <RetrievalSettingsProvider value={{ settings, setSettings }}>
          <main className="flex-1 overflow-hidden min-h-0">
            {children}
          </main>
        </RetrievalSettingsProvider>
      </div>

      {/* Settings Drawer */}
      <RetrievalSettingsDrawer
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        settings={settings}
        onSettingsChange={setSettings}
      />
    </div>
  )
}
