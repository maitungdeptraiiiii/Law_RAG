'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { MessageSquare, Archive, Trash2, MoreHorizontal, Pencil, Pin } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { archiveSession, deleteSession, getSessions, updateSession } from '@/lib/api'
import type { Session } from '@/lib/types'
import { formatDistanceToNow } from 'date-fns'
import { vi } from 'date-fns/locale'
import { toast } from 'sonner'

export function SessionSidebar() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const [pendingActionId, setPendingActionId] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Session | null>(null)
  const [renameTarget, setRenameTarget] = useState<Session | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const pathname = usePathname()
  const router = useRouter()

  const loadSessions = useCallback(async () => {
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
  }, [])

  useEffect(() => {
    function handleSessionsUpdated() {
      void loadSessions()
    }

    loadSessions()
    window.addEventListener('law-rag:sessions-updated', handleSessionsUpdated)

    return () => {
      window.removeEventListener('law-rag:sessions-updated', handleSessionsUpdated)
    }
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
    <ScrollArea className="flex-1 min-h-0">
      <div className="space-y-1 p-2 pb-16">
        <p className="px-2 py-1.5 text-xs font-medium text-muted-foreground">
          Lịch sử hội thoại
        </p>
        {sessions.map((session) => (
          <SessionItem 
            key={session.id} 
            session={session} 
            isActive={pathname === `/chat/${session.id}`}
            isPending={pendingActionId === session.id}
            onArchive={async () => {
              setPendingActionId(session.id)
              try {
                const response = await archiveSession(session.id)
                if (!response.success) {
                  toast.error(response.error)
                  return
                }

                setSessions((prev) => prev.filter((item) => item.id !== session.id))
                window.dispatchEvent(new CustomEvent('law-rag:sessions-updated'))

                if (pathname === `/chat/${session.id}`) {
                  router.replace('/chat')
                }

                toast.success('Đã lưu trữ cuộc hội thoại')
              } finally {
                setPendingActionId(null)
              }
            }}
            onRename={() => {
              setRenameTarget(session)
              setRenameValue(session.title)
            }}
            onTogglePin={async () => {
              setPendingActionId(session.id)
              try {
                const response = await updateSession(session.id, { pinned: !session.pinned })
                if (!response.success) {
                  toast.error(response.error)
                  return
                }

                await loadSessions()
                window.dispatchEvent(new CustomEvent('law-rag:sessions-updated'))
                toast.success(response.data.pinned ? 'Đã ghim cuộc hội thoại' : 'Đã bỏ ghim cuộc hội thoại')
              } finally {
                setPendingActionId(null)
              }
            }}
            onDelete={() => setDeleteTarget(session)}
          />
        ))}
      </div>

      <AlertDialog open={deleteTarget !== null} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Xóa cuộc hội thoại?</AlertDialogTitle>
            <AlertDialogDescription>
              Hành động này sẽ xóa toàn bộ nội dung của cuộc hội thoại này khỏi lịch sử và không thể hoàn tác.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Hủy</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={async (event) => {
                event.preventDefault()
                if (!deleteTarget) return

                const target = deleteTarget
                setPendingActionId(target.id)
                try {
                  const response = await deleteSession(target.id)
                  if (!response.success) {
                    toast.error(response.error)
                    return
                  }

                  setSessions((prev) => prev.filter((item) => item.id !== target.id))
                  setDeleteTarget(null)
                  window.dispatchEvent(new CustomEvent('law-rag:sessions-updated'))

                  if (pathname === `/chat/${target.id}`) {
                    router.replace('/chat')
                  }

                  toast.success('Đã xóa cuộc hội thoại')
                } finally {
                  setPendingActionId(null)
                }
              }}
            >
              Xóa
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={renameTarget !== null} onOpenChange={(open) => !open && setRenameTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Đổi tên cuộc hội thoại</DialogTitle>
            <DialogDescription>
              Nhập tiêu đề mới để dễ tìm lại hội thoại này trong lịch sử.
            </DialogDescription>
          </DialogHeader>
          <Input
            value={renameValue}
            onChange={(event) => setRenameValue(event.target.value)}
            maxLength={120}
            placeholder="Nhập tiêu đề mới"
            autoFocus
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenameTarget(null)}>
              Hủy
            </Button>
            <Button
              disabled={!renameTarget || pendingActionId === renameTarget.id}
              onClick={async () => {
                if (!renameTarget) return

                const title = renameValue.trim()
                if (!title) {
                  toast.error('Tiêu đề không được để trống')
                  return
                }

                setPendingActionId(renameTarget.id)
                try {
                  const response = await updateSession(renameTarget.id, { title })
                  if (!response.success) {
                    toast.error(response.error)
                    return
                  }

                  setRenameTarget(null)
                  await loadSessions()
                  window.dispatchEvent(new CustomEvent('law-rag:sessions-updated'))
                  toast.success('Đã đổi tên cuộc hội thoại')
                } finally {
                  setPendingActionId(null)
                }
              }}
            >
              Lưu
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ScrollArea>
  )
}

function SessionItem({
  session,
  isActive,
  isPending,
  onArchive,
  onRename,
  onTogglePin,
  onDelete,
}: {
  session: Session
  isActive: boolean
  isPending: boolean
  onArchive: () => void
  onRename: () => void
  onTogglePin: () => void
  onDelete: () => void
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const timeAgo = formatDistanceToNow(new Date(session.updatedAt), { 
    addSuffix: true,
    locale: vi 
  })

  return (
    <div
      className={`group relative rounded-lg p-2.5 transition-colors ${
        isActive 
          ? 'bg-sidebar-accent text-sidebar-accent-foreground' 
          : 'hover:bg-sidebar-accent/50'
      }`}
    >
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-2">
        <Link href={`/chat/${session.id}`} className="col-start-1 row-span-3 min-w-0 overflow-hidden">
          <div className="flex min-w-0 items-center gap-1.5">
            <h4 className="min-w-0 flex-1 truncate text-sm font-medium">
              {session.title}
            </h4>
            {session.pinned && <Pin className="h-3.5 w-3.5 shrink-0 text-amber-600" />}
          </div>
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

        <DropdownMenu open={menuOpen} onOpenChange={setMenuOpen}>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              disabled={isPending}
              className={`col-start-2 row-start-1 mt-0.5 h-7 w-7 shrink-0 self-start rounded-md border border-transparent bg-background/95 shadow-sm transition-all hover:bg-sidebar-accent ${
                menuOpen ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0 group-hover:pointer-events-auto group-hover:opacity-100'
              }`}
            >
              <MoreHorizontal className="h-4 w-4" />
              <span className="sr-only">Tùy chọn</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-44">
            <DropdownMenuItem disabled={isPending} onClick={onRename}>
              <Pencil className="h-4 w-4 mr-2" />
              Đổi tên
            </DropdownMenuItem>
            <DropdownMenuItem disabled={isPending} onClick={onTogglePin}>
              <Pin className="h-4 w-4 mr-2" />
              {session.pinned ? 'Bỏ ghim' : 'Ghim lên đầu'}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem disabled={isPending} onClick={onArchive}>
              <Archive className="h-4 w-4 mr-2" />
              Lưu trữ
            </DropdownMenuItem>
            <DropdownMenuItem disabled={isPending} onClick={onDelete} variant="destructive">
              <Trash2 className="h-4 w-4 mr-2" />
              Xóa
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  )
}
