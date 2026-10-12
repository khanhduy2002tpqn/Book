export type DocumentStatus =
  | 'uploaded'
  | 'processing_pdf'
  | 'extracting_text'
  | 'running_ocr'
  | 'creating_embeddings'
  | 'indexing'
  | 'ready'
  | 'failed'

export interface DocumentItem {
  id: string
  filename: string
  file_size: number
  page_count: number
  status: DocumentStatus
  grade?: string | null
  subject?: string | null
  error_message?: string | null
  created_at: string
  updated_at?: string
}

export interface CitationSource {
  page: number
  chunk_id: string
  score: number
  chapter?: string | null
  text?: string | null
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: CitationSource[]
  created_at: string
}

export interface FlashcardItem {
  question: string
  answer: string
  page?: number
}

export interface QuestionItem {
  question: string
  options?: string[] | null
  answer: string
  explanation?: string | null
  page?: number
}

export interface PageData {
  id: string
  document_id: string
  page_number: number
  text: string
  ocr_used: boolean
  chapter?: string | null
}
