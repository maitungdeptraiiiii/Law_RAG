'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { Scale, Send, Loader2, ChevronRight, ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import { AnswerCard } from '@/components/chat/answer-card'
import { useRetrievalSettings } from '@/components/chat/retrieval-settings-context'
import { SourceEvidencePanel } from '@/components/chat/source-evidence-panel'
import { askQuestion } from '@/lib/api'
import type { Message, RetrievedSource, RetrievalSettings } from '@/lib/types'

export default function ChatPage() {
  const router = useRouter()
  const { settings } = useRetrievalSettings()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [selectedSources, setSelectedSources] = useState<RetrievedSource[] | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      const response = await askQuestion({
        question: userMessage.content,
        sessionId: sessionId || undefined,
        settings,
      })

      if (response.success) {
        window.dispatchEvent(new CustomEvent('law-rag:sessions-updated'))

        if (!sessionId) {
          router.replace(`/chat/${response.data.sessionId}`)
          return
        }

        const assistantMessage: Message = {
          id: response.data.messageId,
          role: 'assistant',
          content: response.data.answer,
          timestamp: new Date(),
          sources: response.data.sources,
          metadata: response.data.metadata,
        }
        setMessages((prev) => [...prev, assistantMessage])
        setSessionId(response.data.sessionId)
      }
    } catch (error) {
      console.error('[v0] Error asking question:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const handleViewSources = (sources: RetrievedSource[]) => {
    setSelectedSources(sources)
  }

  const handleCloseSources = () => {
    setSelectedSources(null)
  }

  return (
    <div className="flex h-full min-h-0">
      {/* Chat Area */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0">
        {messages.length === 0 ? (
          // Empty State
          <div className="flex-1 flex items-center justify-center p-8">
            <div className="max-w-lg text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary/10 mb-6">
                <Scale className="h-8 w-8 text-primary" />
              </div>
              <h2 className="text-2xl font-semibold mb-3">
                Hỏi đáp pháp luật Việt Nam
              </h2>
              <p className="text-muted-foreground mb-8 leading-relaxed">
                Đặt câu hỏi về pháp luật Việt Nam. Mỗi câu trả lời sẽ được trích dẫn 
                nguồn từ các văn bản pháp quy chính thức.
              </p>
              
              <div className="grid gap-3">
                <SuggestedQuestion 
                  question="Thủ tục đăng ký kinh doanh hộ cá thể cần những giấy tờ gì?"
                  onClick={(q) => setInput(q)}
                />
                <SuggestedQuestion 
                  question="Quyền thừa kế của con nuôi theo pháp luật Việt Nam?"
                  onClick={(q) => setInput(q)}
                />
                <SuggestedQuestion 
                  question="Thuế thu nhập cá nhân khi bán nhà được tính như thế nào?"
                  onClick={(q) => setInput(q)}
                />
              </div>
            </div>
          </div>
        ) : (
          // Messages
          <ScrollArea className="flex-1 min-h-0">
            <div className="max-w-3xl mx-auto py-6 px-4">
              <AnimatePresence initial={false}>
                {messages.map((message) => (
                  <motion.div
                    key={message.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="mb-6"
                  >
                    {message.role === 'user' ? (
                      <UserMessage content={message.content} />
                    ) : (
                      <AnswerCard 
                        message={message} 
                        onViewSources={handleViewSources}
                      />
                    )}
                  </motion.div>
                ))}
              </AnimatePresence>
              
              {isLoading && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex items-center gap-3 text-muted-foreground"
                >
                  <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                  </div>
                  <span className="text-sm">Đang tìm kiếm và phân tích văn bản pháp luật...</span>
                </motion.div>
              )}
              
              <div ref={messagesEndRef} />
            </div>
          </ScrollArea>
        )}

        {/* Input Area */}
        <div className="border-t border-border bg-card p-4">
          <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
            <div className="relative">
              <Textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Nhập câu hỏi pháp luật của bạn..."
                className="min-h-[52px] max-h-32 pr-12 resize-none bg-background"
                disabled={isLoading}
              />
              <Button
                type="submit"
                size="icon"
                disabled={!input.trim() || isLoading}
                className="absolute right-2 bottom-2 h-8 w-8"
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
                <span className="sr-only">Gửi câu hỏi</span>
              </Button>
            </div>
            <p className="mt-2 text-xs text-muted-foreground text-center">
              Nhấn Enter để gửi, Shift + Enter để xuống dòng
            </p>
          </form>
        </div>
      </div>

      {/* Sources Panel */}
      <AnimatePresence>
        {selectedSources && (
          <SourceEvidencePanel 
            sources={selectedSources} 
            onClose={handleCloseSources}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

function UserMessage({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] bg-primary text-primary-foreground rounded-2xl rounded-br-md px-4 py-3">
        <p className="text-sm whitespace-pre-wrap">{content}</p>
      </div>
    </div>
  )
}

function SuggestedQuestion({ 
  question, 
  onClick 
}: { 
  question: string
  onClick: (question: string) => void 
}) {
  return (
    <button
      onClick={() => onClick(question)}
      className="flex items-center gap-3 w-full p-3 rounded-lg border border-border bg-card hover:bg-accent/50 transition-colors text-left group"
    >
      <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors flex-shrink-0" />
      <span className="text-sm">{question}</span>
    </button>
  )
}
