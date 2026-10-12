import { useState, useCallback, useEffect } from 'react'
import { message } from 'antd'
import { chatWithDocument } from '../services/api'
import type { ChatMessage } from '../types'

export const useChat = (documentId?: string) => {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [conversationId, setConversationId] = useState<string | undefined>(undefined)
  const [loading, setLoading] = useState(false)
  const [topK, setTopK] = useState(5)

  // Reset conversation when document changes
  useEffect(() => {
    setMessages([])
    setConversationId(undefined)
  }, [documentId])

  const sendMessage = useCallback(
    async (userText: string) => {
      if (!documentId || !userText.trim()) return

      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: userText,
        created_at: new Date().toISOString(),
      }

      setMessages((prev) => [...prev, userMsg])
      setLoading(true)

      try {
        const res = await chatWithDocument(documentId, userText, conversationId, topK)
        setConversationId(res.conversation_id)

        const assistantMsg: ChatMessage = {
          id: `ai-${Date.now()}`,
          role: 'assistant',
          content: res.answer,
          sources: res.sources,
          created_at: new Date().toISOString(),
        }

        setMessages((prev) => [...prev, assistantMsg])
      } catch (err: any) {
        const errorDetail =
          err.response?.data?.detail || err.message || 'Không thể nhận phản hồi từ AI.'
        message.error(errorDetail)
        const errorMsg: ChatMessage = {
          id: `err-${Date.now()}`,
          role: 'assistant',
          content: `⚠️ **Lỗi:** ${errorDetail}`,
          created_at: new Date().toISOString(),
        }
        setMessages((prev) => [...prev, errorMsg])
      } finally {
        setLoading(false)
      }
    },
    [documentId, conversationId, topK]
  )

  const clearChat = useCallback(() => {
    setMessages([])
    setConversationId(undefined)
  }, [])

  return {
    messages,
    loading,
    topK,
    setTopK,
    sendMessage,
    clearChat,
  }
}
