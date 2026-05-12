'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { Scale, Send, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import { AnswerCard } from '@/components/chat/answer-card'
import { SourceEvidencePanel } from '@/components/chat/source-evidence-panel'
import { askQuestion, getConversation } from '@/lib/api'
import type { Message, RetrievedSource, RetrievalSettings } from '@/lib/types'
import useSWR from 'swr'

const defaultSettings: RetrievalSettings = {
  mode: 'hybrid',
  vectorBackend: 'faiss',
  topK: 5,
  queryRewrite: true,
}

export default function SessionChatPage() {
  const params = useParams()
  const sessionId = params.sessionId as string
  
  const { data: conversationData, mutate } = useSWR(
    sessionId ? ['conversation', sessionId] : null,
    () => getConversation(sessionId).then(res => res.success ? res.data : null)
  )
  
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [selectedSources, setSelectedSources] = useState<RetrievedSource[] | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Load conversation messages when data arrives
  useEffect(() => {
    if (conversationData?.messages) {
      setMessages(conversationData.messages)
    }
  }, [conversationData])

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
        sessionId: sessionId,
        settings: defaultSettings,
      })

      if (response.success) {
        const assistantMessage: Message = {
          id: response.data.messageId,
          role: 'assistant',
          content: response.data.answer,
          timestamp: new Date(),
          sources: response.data.sources,
          metadata: response.data.metadata,
        }
        setMessages((prev) => [...prev, assistantMessage])
        mutate() // Refresh conversation data
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
    <div className="flex h-full">
      {/* Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {messages.length === 0 ? (
          // Empty/Loading State
          <div className="flex-1 flex items-center justify-center p-8">
            <div className="max-w-lg text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary/10 mb-6">
                <Scale className="h-8 w-8 text-primary" />
              </div>
              <h2 className="text-xl font-semibold mb-3">
                Đang tải cuộc hội thoại...
              </h2>
              <p className="text-muted-foreground">
                Vui lòng đợi trong giây lát
              </p>
            </div>
          </div>
        ) : (
          // Messages
          <ScrollArea className="flex-1">
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
