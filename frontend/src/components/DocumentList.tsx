import React, { useState } from 'react'
import {
  List,
  Typography,
  Tag,
  Button,
  Popconfirm,
  Input,
  Empty,
  Tooltip,
  Select,
} from 'antd'
import {
  FilePdfOutlined,
  DeleteOutlined,
  PlusOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  CloseCircleOutlined,
  SearchOutlined,
  ReloadOutlined,
  FilterOutlined,
} from '@ant-design/icons'
import type { DocumentItem, DocumentStatus } from '../types'

const { Text } = Typography

interface DocumentListProps {
  documents: DocumentItem[]
  selectedDocId?: string
  onSelectDocument: (doc: DocumentItem) => void
  onDeleteDocument: (docId: string) => void
  onReindexDocument?: (docId: string) => void
  onOpenUpload: () => void
  loading?: boolean
}

const GRADE_OPTIONS = [
  'Tất cả',
  'Lớp 12',
  'Lớp 11',
  'Lớp 10',
  'Lớp 9',
  'Lớp 8',
  'Lớp 7',
  'Lớp 6',
  'Lớp 5',
  'Lớp 4',
  'Lớp 3',
  'Lớp 2',
  'Lớp 1',
  'Đại học',
  'Chung',
]

const SUBJECT_OPTIONS = [
  'Tất cả',
  'Toán',
  'Ngữ văn',
  'Tiếng Anh',
  'Vật lí',
  'Hóa học',
  'Sinh học',
  'Lịch sử',
  'Địa lí',
  'Tin học',
  'GDCD',
  'Khoa học tự nhiên',
  'Khác',
]

export const DocumentList: React.FC<DocumentListProps> = ({
  documents,
  selectedDocId,
  onSelectDocument,
  onDeleteDocument,
  onReindexDocument,
  onOpenUpload,
  loading = false,
}) => {
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedGrade, setSelectedGrade] = useState('Tất cả')
  const [selectedSubject, setSelectedSubject] = useState('Tất cả')

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const renderStatusTag = (status: DocumentStatus) => {
    switch (status) {
      case 'ready':
        return (
          <Tag color="success" icon={<CheckCircleOutlined />}>
            Sẵn sàng
          </Tag>
        )
      case 'failed':
        return (
          <Tag color="error" icon={<CloseCircleOutlined />}>
            Lỗi
          </Tag>
        )
      case 'uploaded':
        return <Tag color="default">Đã tải lên</Tag>
      case 'processing_pdf':
        return (
          <Tag color="processing" icon={<SyncOutlined spin />}>
            Đang phân tích
          </Tag>
        )
      case 'extracting_text':
        return (
          <Tag color="processing" icon={<SyncOutlined spin />}>
            Trích xuất text
          </Tag>
        )
      case 'running_ocr':
        return (
          <Tag color="warning" icon={<SyncOutlined spin />}>
            Đang OCR
          </Tag>
        )
      case 'creating_embeddings':
        return (
          <Tag color="purple" icon={<SyncOutlined spin />}>
            Tạo embedding
          </Tag>
        )
      case 'indexing':
        return (
          <Tag color="cyan" icon={<SyncOutlined spin />}>
            Lập chỉ mục
          </Tag>
        )
      default:
        return <Tag color="default">{status}</Tag>
    }
  }

  const getSubjectColor = (subject?: string | null): string => {
    switch (subject) {
      case 'Toán':
        return 'blue'
      case 'Ngữ văn':
        return 'magenta'
      case 'Tiếng Anh':
        return 'volcano'
      case 'Vật lí':
        return 'geekblue'
      case 'Hóa học':
        return 'purple'
      case 'Sinh học':
        return 'green'
      case 'Lịch sử':
        return 'gold'
      case 'Địa lí':
        return 'orange'
      case 'Tin học':
        return 'cyan'
      default:
        return 'default'
    }
  }

  const filteredDocs = documents.filter((d) => {
    const matchesSearch = d.filename.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesGrade = selectedGrade === 'Tất cả' || d.grade === selectedGrade
    const matchesSubject = selectedSubject === 'Tất cả' || d.subject === selectedSubject
    return matchesSearch && matchesGrade && matchesSubject
  })

  // Thống kê số lượng sách theo khối
  const gradeCounts = documents.reduce<Record<string, number>>((acc, d) => {
    const g = d.grade || 'Chung'
    acc[g] = (acc[g] || 0) + 1
    return acc
  }, {})

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Search and Upload Header */}
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0' }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={onOpenUpload}
          block
          style={{ marginBottom: 12, fontWeight: 500, height: 38 }}
        >
          Upload / Thêm Sách Mới
        </Button>

        <Input
          placeholder="Tìm kiếm sách giáo khoa..."
          prefix={<SearchOutlined style={{ color: '#aaa' }} />}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          allowClear
          size="middle"
          style={{ marginBottom: 10 }}
        />

        {/* Filters: Khối Lớp & Môn Học */}
        <div style={{ display: 'flex', gap: 8 }}>
          <Select
            value={selectedGrade}
            onChange={setSelectedGrade}
            style={{ flex: 1 }}
            size="small"
            prefix={<FilterOutlined style={{ color: '#1677ff', marginRight: 4 }} />}
            options={GRADE_OPTIONS.map((g) => ({
              label: g === 'Tất cả' ? 'Tất cả khối' : `${g}${gradeCounts[g] ? ` (${gradeCounts[g]})` : ''}`,
              value: g,
            }))}
          />
          <Select
            value={selectedSubject}
            onChange={setSelectedSubject}
            style={{ flex: 1 }}
            size="small"
            options={SUBJECT_OPTIONS.map((s) => ({
              label: s === 'Tất cả' ? 'Tất cả môn' : s,
              value: s,
            }))}
          />
        </div>
      </div>

      {/* Document List */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 12px' }}>
        {filteredDocs.length === 0 ? (
          <Empty
            description={documents.length === 0 ? 'Chưa có tài liệu nào' : 'Không tìm thấy sách phù hợp'}
            style={{ marginTop: 40 }}
          />
        ) : (
          <List
            loading={loading}
            dataSource={filteredDocs}
            renderItem={(doc) => {
              const isSelected = doc.id === selectedDocId
              return (
                <div
                  key={doc.id}
                  onClick={() => onSelectDocument(doc)}
                  style={{
                    padding: '12px 14px',
                    marginBottom: 8,
                    borderRadius: 8,
                    cursor: 'pointer',
                    background: isSelected ? '#e6f4ff' : '#ffffff',
                    border: isSelected ? '1px solid #1677ff' : '1px solid #f0f0f0',
                    transition: 'all 0.2s ease',
                    boxShadow: isSelected ? '0 2px 8px rgba(22, 119, 255, 0.15)' : 'none',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                    <div style={{ display: 'flex', gap: 10, flex: 1, minWidth: 0 }}>
                      <FilePdfOutlined style={{ fontSize: 24, color: '#ff4d4f', marginTop: 2, flexShrink: 0 }} />
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <Tooltip title={doc.filename}>
                          <Text
                            strong
                            ellipsis
                            style={{
                              display: 'block',
                              fontSize: 14,
                              color: isSelected ? '#1677ff' : 'inherit',
                            }}
                          >
                            {doc.filename}
                          </Text>
                        </Tooltip>

                        {/* Badges for Grade & Subject */}
                        <div style={{ display: 'flex', gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
                          <Tag color="blue" style={{ margin: 0, fontSize: 11, padding: '0 6px' }}>
                            {doc.grade || 'Chung'}
                          </Tag>
                          <Tag color={getSubjectColor(doc.subject)} style={{ margin: 0, fontSize: 11, padding: '0 6px' }}>
                            {doc.subject || 'Khác'}
                          </Tag>
                        </div>

                        <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 12, color: '#888' }}>
                          <span>{doc.page_count > 0 ? `${doc.page_count} trang` : '...'}</span>
                          <span>•</span>
                          <span>{formatFileSize(doc.file_size)}</span>
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                      {/* Reindex action if not ready */}
                      {onReindexDocument && doc.status !== 'ready' && (
                        <Tooltip title="Quét lại OCR / Lập chỉ mục lại">
                          <Button
                            type="text"
                            size="small"
                            icon={<ReloadOutlined style={{ color: '#1677ff' }} />}
                            onClick={(e) => {
                              e.stopPropagation()
                              onReindexDocument(doc.id)
                            }}
                          />
                        </Tooltip>
                      )}

                      {/* Delete action */}
                      <Popconfirm
                        title="Xóa tài liệu này?"
                        description="Hành động này sẽ xóa file và toàn bộ vector embeddings."
                        onConfirm={(e) => {
                          e?.stopPropagation()
                          onDeleteDocument(doc.id)
                        }}
                        onCancel={(e) => e?.stopPropagation()}
                        okText="Xóa"
                        cancelText="Hủy"
                        okButtonProps={{ danger: true }}
                      >
                        <Button
                          type="text"
                          size="small"
                          danger
                          icon={<DeleteOutlined />}
                          onClick={(e) => e.stopPropagation()}
                        />
                      </Popconfirm>
                    </div>
                  </div>

                  <div style={{ marginTop: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    {renderStatusTag(doc.status)}
                    {doc.error_message && doc.status === 'failed' && (
                      <Tooltip title={doc.error_message}>
                        <Text type="danger" style={{ fontSize: 11 }}>
                          Xem lỗi
                        </Text>
                      </Tooltip>
                    )}
                    {doc.error_message && doc.status !== 'failed' && (
                      <Text style={{ fontSize: 11, color: '#fa8c16', fontWeight: 500 }}>
                        {doc.error_message}
                      </Text>
                    )}
                  </div>
                </div>
              )
            }}
          />
        )}
      </div>
    </div>
  )
}
