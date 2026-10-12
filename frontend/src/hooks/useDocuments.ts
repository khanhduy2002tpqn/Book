import { useState, useEffect, useCallback } from 'react'
import { message } from 'antd'
import { getDocuments, deleteDocument as apiDeleteDoc } from '../services/api'
import type { DocumentItem } from '../types'

export const useDocuments = () => {
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [selectedDoc, setSelectedDoc] = useState<DocumentItem | null>(null)
  const [loading, setLoading] = useState(false)

  const fetchDocs = useCallback(async () => {
    try {
      setLoading(true)
      const data = await getDocuments()
      setDocuments(data)
      if (data.length > 0 && !selectedDoc) {
        setSelectedDoc(data[0])
      } else if (selectedDoc) {
        const currentInList = data.find((d) => d.id === selectedDoc.id)
        if (currentInList) setSelectedDoc(currentInList)
      }
    } catch {
      // silent on initial load failure if server is booting
    } finally {
      setLoading(false)
    }
  }, [selectedDoc])

  useEffect(() => {
    fetchDocs()
  }, [])

  // Poll for background indexing completion
  useEffect(() => {
    const hasProcessing = documents.some(
      (d) => d.status !== 'ready' && d.status !== 'failed'
    )
    if (!hasProcessing) return

    const interval = setInterval(async () => {
      try {
        const data = await getDocuments()
        setDocuments(data)
        if (selectedDoc) {
          const updated = data.find((d) => d.id === selectedDoc.id)
          if (updated) setSelectedDoc(updated)
        }
      } catch {
        // ignore polling err
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [documents, selectedDoc])

  const handleDelete = async (id: string) => {
    try {
      await apiDeleteDoc(id)
      message.success('Đã xóa tài liệu.')
      setDocuments((prev) => prev.filter((d) => d.id !== id))
      if (selectedDoc?.id === id) {
        const remaining = documents.filter((d) => d.id !== id)
        setSelectedDoc(remaining.length > 0 ? remaining[0] : null)
      }
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'Không thể xóa tài liệu.')
    }
  }

  const handleSelect = (doc: DocumentItem) => {
    setSelectedDoc(doc)
  }

  return {
    documents,
    selectedDoc,
    loading,
    refreshDocuments: fetchDocs,
    deleteDocument: handleDelete,
    selectDocument: handleSelect,
    setSelectedDoc,
  }
}
