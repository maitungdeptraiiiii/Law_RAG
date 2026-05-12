'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { MessageSquare, Archive, Trash2, MoreHorizontal } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { getSessions } from '@/lib/api'
import type { Session } from '@/lib/types'
import { formatDistanceToNow } from 'date-fns'
import { vi } from 'date-fns/locale'

export function SessionSidebar() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const pathname = usePathname()

  useEffect(() => {
    async function loadSessions() {
      try {
        const response = await getSessions()
        if (response.success) {
          setSessions(response.data.filter(s => !s.archived))
        }
      } catch (error) {
        console.error('[v0] Error loading sessions:', error)
      } finally {
        setLoading(false)
      }
    }
    loadSessions()
  }, [])

  if (loading) {
    return (
      <div className="flex-1 p-4">
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 rounded-lg bg-sidebar-accent/50 animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  if (sessions.length === 0) {
    return (
      <div className="flex-1 p-4">
        <div className="text-center py-8">
          <MessageSquare className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">
            Chưa có cuộc hội thoại nào
          </p>
        </div>
      </div>
    )
  }

  return (
    <ScrollArea className="flex-1">
      <div className="p-2 space-y-1">
        <p className="px-2 py-1.5 text-xs font-medium text-muted-foreground">
          Lịch sử hội thoại
        </p>
        {sessions.map((session) => (
          <SessionItem 
            key={session.id} 
            session={session} 
            isActive={pathname === `/chat/${session.id}`}
          />
        ))}
      </div>
    </ScrollArea>
  )
}

function SessionItem({ session, isActive }: { session: Session; isActive: boolean }) {
  const timeAgo = formatDistanceToNow(new Date(session.updatedAt), { 
    addSuffix: true,
    locale: vi 
  })

  return (
    <div
      className={`group relative flex items-start gap-3 p-2.5 rounded-lg transition-colors ${
        isActive 
          ? 'bg-sidebar-accent text-sidebar-accent-foreground' 
          : 'hover:bg-sidebar-accent/50'
      }`}
    >
      <Link href={`/chat/${session.id}`} className="flex-1 min-w-0">
        <h4 className="text-sm font-medium truncate pr-8">{session.title}</h4>
        {session.preview && (
          <p className="text-xs text-muted-foreground truncate mt-0.5">
            {session.preview}
          </p>
        )}
        <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
          <span>{timeAgo}</span>
          <span>•</span>
          <span>{session.messageCount} tin nhắn</span>
        </div>
      </Link>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-1 top-1 h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <MoreHorizontal className="h-4 w-4" />
            <span className="sr-only">Tùy chọn</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-40">
          <DropdownMenuItem>
            <Archive className="h-4 w-4 mr-2" />
            Lưu trữ
          </DropdownMenuItem>
          <DropdownMenuItem className="text-destructive focus:text-destructive">
            <Trash2 className="h-4 w-4 mr-2" />
            Xóa
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
