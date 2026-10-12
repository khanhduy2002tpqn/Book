import React, { useState, useEffect } from 'react'
import {
  Modal,
  Upload,
  Typography,
  Progress,
  Steps,
  Alert,
  message,
  Button,
  Select,
  Tag,
  List,
} from 'antd'
import {
  InboxOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  FilePdfOutlined,
  DeleteOutlined,
} from '@ant-design/icons'
import { uploadDocument, batchUploadDocuments, getDocument } from '../services/api'
import type { DocumentItem, DocumentStatus } from '../types'

const { Dragger } = Upload
const { Text } = Typography

interface UploadModalProps {
  open: boolean
  onClose: () => void
  onUploadSuccess: (doc: DocumentItem) => void
}

const GRADE_CHOICES = [
  'Tự động',
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

const SUBJECT_CHOICES = [
  'Tự động',
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

export const UploadModal: React.FC<UploadModalProps> = ({
  open,
  onClose,
  onUploadSuccess,
}) => {
  const [fileList, setFileList] = useState<File[]>([])
  const [selectedGrade, setSelectedGrade] = useState('Tự động')
  const [selectedSubject, setSelectedSubject] = useState('Tự động')
  const [uploadProgress, setUploadProgress] = useState(0)
  const [isUploading, setIsUploading] = useState(false)
  const [processedDocs, setProcessedDocs] = useState<DocumentItem[]>([])
  const [activeDoc, setActiveDoc] = useState<DocumentItem | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  // Polling active document status while processing
  useEffect(() => {
    let timer: any = null
    if (activeDoc && activeDoc.status !== 'ready' && activeDoc.status !== 'failed') {
      timer = setInterval(async () => {
        try {
          const updated = await getDocument(activeDoc.id)
          setActiveDoc(updated)
          if (updated.status === 'ready') {
            message.success(`Sách "${updated.filename}" đã sẵn sàng!`)
            onUploadSuccess(updated)
          } else if (updated.status === 'failed') {
            setErrorMsg(updated.error_message || 'Xử lý tài liệu thất bại.')
          }
        } catch (e) {
          // ignore transient poll error
        }
      }, 1500)
    }
    return () => {
      if (timer) clearInterval(timer)
    }
  }, [activeDoc])

  const handleStartUpload = async () => {
    if (fileList.length === 0) return
    setIsUploading(true)
    setErrorMsg(null)
    setUploadProgress(0)

    try {
      if (fileList.length === 1) {
        const doc = await uploadDocument(
          fileList[0],
          selectedGrade,
          selectedSubject,
          (percent) => setUploadProgress(percent)
        )
        setActiveDoc(doc)
        setProcessedDocs([doc])
      } else {
        // Multi-file batch upload
        const docs = await batchUploadDocuments(
          fileList,
          selectedGrade,
          selectedSubject,
          (percent) => setUploadProgress(percent)
        )
        setProcessedDocs(docs)
        if (docs.length > 0) {
          setActiveDoc(docs[0])
          message.success(`Đã thêm ${docs.length} sách vào hàng đợi OCR & xử lý!`)
          docs.forEach((d) => onUploadSuccess(d))
        }
      }
    } catch (err: any) {
      setIsUploading(false)
      setErrorMsg(err.response?.data?.detail || err.message || 'Lỗi khi tải file lên.')
    }
  }

  const handleReset = () => {
    setFileList([])
    setUploadProgress(0)
    setIsUploading(false)
    setActiveDoc(null)
    setProcessedDocs([])
    setErrorMsg(null)
    setSelectedGrade('Tự động')
    setSelectedSubject('Tự động')
  }

  const getStepCurrent = (status?: DocumentStatus): number => {
    if (!status) return 0
    switch (status) {
      case 'uploaded':
        return 0
      case 'processing_pdf':
        return 1
      case 'extracting_text':
      case 'running_ocr':
        return 2
      case 'creating_embeddings':
      case 'indexing':
        return 3
      case 'ready':
        return 4
      case 'failed':
        return 2
      default:
        return 0
    }
  }

  const stepStatus = activeDoc?.status === 'failed' ? 'error' : undefined

  return (
    <Modal
      title="Tải lên Sách Giáo Khoa (Đơn lẻ hoặc Hàng loạt)"
      open={open}
      onCancel={() => {
        if (!isUploading || activeDoc?.status === 'ready' || activeDoc?.status === 'failed') {
          handleReset()
          onClose()
        }
      }}
      footer={null}
      width={650}
      destroyOnClose
    >
      <div style={{ padding: '12px 0' }}>
        {!activeDoc ? (
          <div>
            {/* Classification Selectors */}
            <div style={{ marginBottom: 16, background: '#f8fafc', padding: '12px 16px', borderRadius: 8, border: '1px solid #e2e8f0' }}>
              <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13, color: '#334155' }}>
                Phân loại tài liệu:
              </div>
              <div style={{ display: 'flex', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                    Khối lớp:
                  </Text>
                  <Select
                    value={selectedGrade}
                    onChange={setSelectedGrade}
                    style={{ width: '100%' }}
                    options={GRADE_CHOICES.map((g) => ({ label: g, value: g }))}
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                    Môn học:
                  </Text>
                  <Select
                    value={selectedSubject}
                    onChange={setSelectedSubject}
                    style={{ width: '100%' }}
                    options={SUBJECT_CHOICES.map((s) => ({ label: s, value: s }))}
                  />
                </div>
              </div>
              <div style={{ fontSize: 11, color: '#64748b', marginTop: 6 }}>
                💡 Nếu chọn "Tự động", hệ thống sẽ tự phân tích tên file để gán Khối lớp và Môn học chuẩn xác.
              </div>
            </div>

            <Dragger
              accept=".pdf"
              multiple={true}
              beforeUpload={(f) => {
                const isPdf = f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf')
                if (!isPdf) {
                  message.error(`File "${f.name}" không phải định dạng PDF!`)
                  return Upload.LIST_IGNORE
                }
                const isLt50M = f.size / 1024 / 1024 < 50
                if (!isLt50M) {
                  message.error(`File "${f.name}" vượt quá giới hạn 50MB!`)
                  return Upload.LIST_IGNORE
                }
                setFileList((prev) => [...prev, f])
                return false
              }}
              showUploadList={false}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined style={{ fontSize: 44, color: '#1677ff' }} />
              </p>
              <p className="ant-upload-text" style={{ fontSize: 15, fontWeight: 500 }}>
                Kéo thả nhiều file PDF vào đây, hoặc click để chọn hàng loạt
              </p>
              <p className="ant-upload-hint" style={{ color: '#888', fontSize: 12 }}>
                Hỗ trợ tải lên nhiều sách giáo khoa cùng lúc (tự động kích hoạt OCR trang scan). Tối đa 50MB/file.
              </p>
            </Dragger>

            {/* Selected Files List */}
            {fileList.length > 0 && (
              <div style={{ marginTop: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <Text strong style={{ fontSize: 13 }}>
                    Đã chọn {fileList.length} file:
                  </Text>
                  <Button type="link" size="small" onClick={() => setFileList([])} danger>
                    Xóa tất cả
                  </Button>
                </div>
                <div style={{ maxHeight: 150, overflowY: 'auto', border: '1px solid #f0f0f0', borderRadius: 6 }}>
                  <List
                    size="small"
                    dataSource={fileList}
                    renderItem={(f, idx) => (
                      <List.Item
                        actions={[
                          <Button
                            type="text"
                            size="small"
                            danger
                            icon={<DeleteOutlined />}
                            onClick={() => setFileList((prev) => prev.filter((_, i) => i !== idx))}
                          />,
                        ]}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, overflow: 'hidden' }}>
                          <FilePdfOutlined style={{ color: '#ff4d4f' }} />
                          <Text ellipsis style={{ maxWidth: 360, fontSize: 13 }}>
                            {f.name}
                          </Text>
                          <Tag style={{ fontSize: 10 }}>{(f.size / 1024 / 1024).toFixed(1)} MB</Tag>
                        </div>
                      </List.Item>
                    )}
                  />
                </div>
              </div>
            )}

            {errorMsg && (
              <Alert style={{ marginTop: 16 }} message={errorMsg} type="error" showIcon />
            )}

            <div style={{ marginTop: 20, textAlign: 'right' }}>
              <Button onClick={onClose} style={{ marginRight: 8 }} disabled={isUploading}>
                Hủy
              </Button>
              <Button
                type="primary"
                onClick={handleStartUpload}
                disabled={fileList.length === 0}
                loading={isUploading}
              >
                {fileList.length > 1 ? `Tải lên hàng loạt (${fileList.length} sách)` : 'Bắt đầu xử lý'}
              </Button>
            </div>
          </div>
        ) : (
          <div>
            {/* Progress and Steps Status */}
            {uploadProgress < 100 && (
              <div style={{ marginBottom: 20 }}>
                <Text>Đang tải tài liệu lên máy chủ...</Text>
                <Progress percent={uploadProgress} status="active" />
              </div>
            )}

            {processedDocs.length > 1 && (
              <div style={{ marginBottom: 16, background: '#f0fdf4', padding: '10px 14px', borderRadius: 6, border: '1px solid #bbf7d0' }}>
                <Text strong style={{ color: '#166534' }}>
                  Đã tiếp nhận {processedDocs.length} sách giáo khoa. Hệ thống đang tiến hành OCR và lập chỉ mục trong nền.
                </Text>
              </div>
            )}

            <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Text strong>Đang theo dõi:</Text>
              <Tag color="blue">{activeDoc.filename}</Tag>
              {activeDoc.grade && <Tag color="cyan">{activeDoc.grade}</Tag>}
              {activeDoc.subject && <Tag color="purple">{activeDoc.subject}</Tag>}
            </div>

            <Steps
              direction="vertical"
              size="small"
              current={getStepCurrent(activeDoc.status)}
              status={stepStatus}
              items={[
                {
                  title: 'Tải file lên máy chủ',
                  description: 'Xác thực định dạng & lưu trữ an toàn',
                },
                {
                  title: 'Phân tích cấu trúc PDF',
                  description: 'Xác định số trang, mục lục và tiêu đề chương',
                },
                {
                  title: 'Trích xuất văn bản & OCR',
                  description:
                    activeDoc.status === 'running_ocr'
                      ? 'Đang chạy OCR nhận diện ảnh...'
                      : 'Trích xuất text hoặc OCR cho trang scan',
                },
                {
                  title: 'Tạo Embeddings & Vector Index',
                  description: 'BAAI/bge-m3 local model & lưu chỉ mục vào Qdrant',
                },
                {
                  title: 'Hoàn tất & Sẵn sàng',
                  description: 'Có thể bắt đầu hỏi đáp và tóm tắt',
                },
              ]}
            />

            {activeDoc.status === 'ready' && (
              <Alert
                style={{ marginTop: 20 }}
                type="success"
                icon={<CheckCircleOutlined />}
                message="Tài liệu đã sẵn sàng!"
                description={`Đã trích xuất thành công ${activeDoc.page_count} trang và lập chỉ mục ngữ nghĩa BGE-M3.`}
              />
            )}

            {activeDoc.status === 'failed' && (
              <Alert
                style={{ marginTop: 20 }}
                type="error"
                icon={<CloseCircleOutlined />}
                message="Xử lý thất bại"
                description={activeDoc.error_message || errorMsg || 'Đã xảy ra lỗi khi xử lý tài liệu.'}
              />
            )}

            <div style={{ marginTop: 24, textAlign: 'right' }}>
              {(activeDoc.status === 'ready' || activeDoc.status === 'failed' || processedDocs.length > 1) && (
                <Button
                  type="primary"
                  onClick={() => {
                    handleReset()
                    onClose()
                  }}
                >
                  Hoàn tất & Đóng
                </Button>
              )}
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
}
