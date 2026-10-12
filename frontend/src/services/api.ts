import axios from 'axios'
import type {
  DocumentItem,
  CitationSource,
  FlashcardItem,
  QuestionItem,
  PageData,
} from '../types'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000, // 2 minutes for heavy ML/Gemini operations
})

export const getDocuments = async (grade?: string, subject?: string): Promise<DocumentItem[]> => {
  const params: any = {}
  if (grade && grade !== 'Tất cả') params.grade = grade
  if (subject && subject !== 'Tất cả') params.subject = subject
  const res = await api.get('/documents', { params })
  return res.data
}

export const getDocument = async (id: string): Promise<DocumentItem> => {
  const res = await api.get(`/documents/${id}`)
  return res.data
}

export const uploadDocument = async (
  file: File,
  grade?: string,
  subject?: string,
  onUploadProgress?: (progressPercent: number) => void
): Promise<DocumentItem> => {
  const formData = new FormData()
  formData.append('file', file)
  if (grade && grade !== 'Tự động') formData.append('grade', grade)
  if (subject && subject !== 'Tự động') formData.append('subject', subject)

  const res = await api.post('/documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (progressEvent) => {
      if (progressEvent.total && onUploadProgress) {
        const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        onUploadProgress(percent)
      }
    },
  })
  return res.data
}

export const batchUploadDocuments = async (
  files: File[],
  grade?: string,
  subject?: string,
  onUploadProgress?: (progressPercent: number) => void
): Promise<DocumentItem[]> => {
  const formData = new FormData()
  files.forEach((file) => {
    formData.append('files', file)
  })
  if (grade && grade !== 'Tự động') formData.append('grade', grade)
  if (subject && subject !== 'Tự động') formData.append('subject', subject)

  const res = await api.post('/documents/batch-upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (progressEvent) => {
      if (progressEvent.total && onUploadProgress) {
        const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        onUploadProgress(percent)
      }
    },
  })
  return res.data
}

export const updateDocument = async (
  id: string,
  data: { grade?: string; subject?: string }
): Promise<DocumentItem> => {
  const res = await api.patch(`/documents/${id}`, data)
  return res.data
}

export const deleteDocument = async (id: string): Promise<void> => {
  await api.delete(`/documents/${id}`)
}

export const reindexDocument = async (id: string): Promise<DocumentItem> => {
  const res = await api.post(`/documents/${id}/reindex`)
  return res.data
}

export const getPage = async (id: string, pageNumber: number): Promise<PageData> => {
  const res = await api.get(`/documents/${id}/pages/${pageNumber}`)
  return res.data
}

export const getPdfFileUrl = (id: string): string => {
  return `/api/documents/${id}/file`
}

export interface ChatResponseData {
  conversation_id: string
  answer: string
  sources: CitationSource[]
}

export const chatWithDocument = async (
  documentId: string,
  message: string,
  conversationId?: string,
  topK: number = 5
): Promise<ChatResponseData> => {
  const res = await api.post(`/documents/${documentId}/chat`, {
    message,
    conversation_id: conversationId,
    top_k: topK,
  })
  return res.data
}

export const getConversation = async (conversationId: string): Promise<any> => {
  const res = await api.get(`/conversations/${conversationId}`)
  return res.data
}

export const deleteConversation = async (conversationId: string): Promise<void> => {
  await api.delete(`/conversations/${conversationId}`)
}

export const getFullSummary = async (documentId: string): Promise<{ content: string; from_cache: boolean }> => {
  const res = await api.post(`/documents/${documentId}/summary`)
  return res.data
}

export const getChapterSummary = async (
  documentId: string,
  chapter: string
): Promise<{ content: string; from_cache: boolean }> => {
  const res = await api.post(`/documents/${documentId}/chapters/${encodeURIComponent(chapter)}/summary`)
  return res.data
}

export const getKeyPoints = async (documentId: string): Promise<{ content: string; from_cache: boolean }> => {
  const res = await api.post(`/documents/${documentId}/key-points`)
  return res.data
}

export const explainConcept = async (documentId: string, concept: string): Promise<{ content: string }> => {
  const res = await api.post(`/documents/${documentId}/explain`, { concept })
  return res.data
}

export const getFlashcards = async (documentId: string): Promise<{ flashcards: FlashcardItem[] }> => {
  const res = await api.post(`/documents/${documentId}/flashcards`)
  return res.data
}

export const getQuestions = async (documentId: string): Promise<{ questions: QuestionItem[] }> => {
  const res = await api.post(`/documents/${documentId}/questions`)
  return res.data
}
