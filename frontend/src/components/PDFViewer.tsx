import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Button,
  Tooltip,
  InputNumber,
  Badge,
  Alert,
  Space,
  Modal,
  Spin,
} from 'antd'
import {
  LeftOutlined,
  RightOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
  DownloadOutlined,
  FileTextOutlined,
  HighlightOutlined,
  ColumnWidthOutlined,
} from '@ant-design/icons'
import * as pdfjsLib from 'pdfjs-dist'
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import axios from 'axios'

import { getPdfFileUrl, getPage } from '../services/api'
import type { PageData } from '../types'

// Setup pdfjs worker
pdfjsLib.GlobalWorkerOptions.workerSrc =
  pdfjsWorker ||
  `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.mjs`

interface PDFViewerProps {
  documentId: string
  filename: string
  targetPage: number
  highlightText?: string
  onPageChange?: (page: number) => void
}

export const PDFViewer: React.FC<PDFViewerProps> = ({
  documentId,
  filename,
  targetPage,
  highlightText,
  onPageChange,
}) => {
  const [pdfDoc, setPdfDoc] = useState<pdfjsLib.PDFDocumentProxy | null>(null)
  const [currentPage, setCurrentPage] = useState<number>(targetPage || 1)
  const [totalPages, setTotalPages] = useState<number>(1)
  const [scale, setScale] = useState<number>(1.25)
  const [loadingDoc, setLoadingDoc] = useState<boolean>(true)
  const [renderingPage, setRenderingPage] = useState<boolean>(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  // Extracted text modal state
  const [showTextModal, setShowTextModal] = useState<boolean>(false)
  const [pageData, setPageData] = useState<PageData | null>(null)
  const [loadingText, setLoadingText] = useState<boolean>(false)

  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const renderTaskRef = useRef<any>(null)

  // 1. Fetch PDF binary via ArrayBuffer and parse via PDF.js
  // (ArrayBuffer AJAX requests completely bypass Neat Download Manager / IDM hijackers!)
  useEffect(() => {
    let isCancelled = false
    const loadPdfDocument = async () => {
      setLoadingDoc(true)
      setErrorMsg(null)
      try {
        const fileUrl = getPdfFileUrl(documentId)
        const response = await axios.get(fileUrl, {
          responseType: 'arraybuffer',
        })

        if (isCancelled) return

        const loadingTask = pdfjsLib.getDocument({
          data: response.data,
          cMapUrl: 'https://cdn.jsdelivr.net/npm/pdfjs-dist/cmaps/',
          cMapPacked: true,
        })

        const doc = await loadingTask.promise
        if (isCancelled) return

        setPdfDoc(doc)
        setTotalPages(doc.numPages)
        const initialPage = Math.min(Math.max(1, targetPage || 1), doc.numPages)
        setCurrentPage(initialPage)
      } catch (err: any) {
        if (!isCancelled) {
          setErrorMsg(err.message || 'Không thể tải tài liệu PDF.')
        }
      } finally {
        if (!isCancelled) {
          setLoadingDoc(false)
        }
      }
    }

    loadPdfDocument()

    return () => {
      isCancelled = true
    }
  }, [documentId])

  // 2. Render current page on canvas
  const renderCurrentPage = useCallback(
    async (pageNum: number, currentScale: number) => {
      if (!pdfDoc || !canvasRef.current) return

      try {
        setRenderingPage(true)

        // Cancel previous render if in progress
        if (renderTaskRef.current) {
          renderTaskRef.current.cancel()
        }

        const page = await pdfDoc.getPage(pageNum)
        const canvas = canvasRef.current
        const context = canvas.getContext('2d')
        if (!context) return

        const viewport = page.getViewport({ scale: currentScale })
        const outputScale = window.devicePixelRatio || 1

        canvas.width = Math.floor(viewport.width * outputScale)
        canvas.height = Math.floor(viewport.height * outputScale)
        canvas.style.width = `${Math.floor(viewport.width)}px`
        canvas.style.height = `${Math.floor(viewport.height)}px`

        const transform = outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : undefined

        const renderContext = {
          canvasContext: context,
          transform,
          viewport,
        }

        const renderTask = page.render(renderContext as any)
        renderTaskRef.current = renderTask
        await renderTask.promise
      } catch (err: any) {
        if (err.name !== 'RenderingCancelledException') {
          console.error('Lỗi khi render trang PDF:', err)
        }
      } finally {
        setRenderingPage(false)
      }
    },
    [pdfDoc]
  )

  // Trigger render when page or scale changes
  useEffect(() => {
    if (pdfDoc && currentPage) {
      renderCurrentPage(currentPage, scale)
    }
  }, [pdfDoc, currentPage, scale, renderCurrentPage])

  // Sync when targetPage changes from outside (e.g. Citation click)
  useEffect(() => {
    if (targetPage && targetPage !== currentPage && totalPages >= targetPage) {
      setCurrentPage(targetPage)
      if (containerRef.current) {
        containerRef.current.scrollTop = 0
      }
    }
  }, [targetPage, totalPages])

  const goToPage = (page: number) => {
    const valid = Math.max(1, Math.min(page, totalPages))
    setCurrentPage(valid)
    onPageChange?.(valid)
    if (containerRef.current) {
      containerRef.current.scrollTop = 0
    }
  }

  const handleZoomIn = () => {
    setScale((prev) => Math.min(Math.round((prev + 0.25) * 100) / 100, 3.0))
  }

  const handleZoomOut = () => {
    setScale((prev) => Math.max(Math.round((prev - 0.25) * 100) / 100, 0.5))
  }

  const handleFitWidth = () => {
    if (containerRef.current && pdfDoc) {
      const containerWidth = containerRef.current.clientWidth - 48
      pdfDoc.getPage(currentPage).then((page) => {
        const viewport = page.getViewport({ scale: 1.0 })
        const newScale = Math.max(0.5, Math.min(containerWidth / viewport.width, 2.5))
        setScale(Math.round(newScale * 100) / 100)
      })
    }
  }

  const handleViewExtractedText = async () => {
    setLoadingText(true)
    setShowTextModal(true)
    try {
      const data = await getPage(documentId, currentPage)
      setPageData(data)
    } catch {
      setPageData(null)
    } finally {
      setLoadingText(false)
    }
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: '#141414',
        borderRadius: 8,
        overflow: 'hidden',
        border: '1px solid #303030',
      }}
    >
      {/* Top Toolbar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '8px 16px',
          background: '#1f1f1f',
          borderBottom: '1px solid #303030',
          flexWrap: 'wrap',
          gap: 8,
          zIndex: 5,
        }}
      >
        {/* Page Navigation */}
        <Space size={6}>
          <Tooltip title="Trang trước">
            <Button
              type="text"
              icon={<LeftOutlined />}
              onClick={() => goToPage(currentPage - 1)}
              disabled={currentPage <= 1 || loadingDoc}
              style={{ color: '#fff' }}
            />
          </Tooltip>

          <span style={{ color: '#aaa', fontSize: 13 }}>Trang</span>
          <InputNumber
            min={1}
            max={totalPages}
            value={currentPage}
            onChange={(val) => val && goToPage(val)}
            size="small"
            style={{ width: 64 }}
            disabled={loadingDoc}
          />
          <span style={{ color: '#aaa', fontSize: 13 }}>/ {totalPages}</span>

          <Tooltip title="Trang tiếp theo">
            <Button
              type="text"
              icon={<RightOutlined />}
              onClick={() => goToPage(currentPage + 1)}
              disabled={currentPage >= totalPages || loadingDoc}
              style={{ color: '#fff' }}
            />
          </Tooltip>
        </Space>

        {/* Zoom & Utilities */}
        <Space size={6}>
          <Tooltip title="Thu nhỏ">
            <Button
              type="text"
              icon={<ZoomOutOutlined />}
              onClick={handleZoomOut}
              disabled={scale <= 0.5 || loadingDoc}
              style={{ color: '#fff' }}
            />
          </Tooltip>

          <span style={{ color: '#ddd', fontSize: 13, minWidth: 46, textAlign: 'center' }}>
            {Math.round(scale * 100)}%
          </span>

          <Tooltip title="Phóng to">
            <Button
              type="text"
              icon={<ZoomInOutlined />}
              onClick={handleZoomIn}
              disabled={scale >= 3.0 || loadingDoc}
              style={{ color: '#fff' }}
            />
          </Tooltip>

          <Tooltip title="Vừa chiều rộng">
            <Button
              type="text"
              icon={<ColumnWidthOutlined />}
              onClick={handleFitWidth}
              disabled={loadingDoc}
              style={{ color: '#fff' }}
            />
          </Tooltip>

          <Tooltip title="Xem nội dung văn bản / OCR của trang này">
            <Button
              type="default"
              size="small"
              icon={<FileTextOutlined />}
              onClick={handleViewExtractedText}
            >
              Văn bản trang
            </Button>
          </Tooltip>

          <Tooltip title="Tải xuống PDF gốc">
            <Button
              type="text"
              icon={<DownloadOutlined />}
              href={getPdfFileUrl(documentId)}
              target="_blank"
              download={filename}
              style={{ color: '#fff' }}
            />
          </Tooltip>
        </Space>
      </div>

      {/* Citation highlight alert banner */}
      {highlightText && (
        <Alert
          message={
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <HighlightOutlined style={{ color: '#faad14' }} />
              <span>
                <strong>Đang xem trích dẫn (Trang {currentPage}):</strong>{' '}
                <em>"{highlightText.slice(0, 140)}..."</em>
              </span>
            </div>
          }
          type="warning"
          showIcon={false}
          closable
          style={{ borderRadius: 0, padding: '4px 16px', fontSize: 13 }}
        />
      )}

      {/* Main Canvas Scroll Area */}
      <div
        ref={containerRef}
        style={{
          flex: 1,
          overflow: 'auto',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'flex-start',
          padding: 24,
          background: '#262626',
          position: 'relative',
        }}
      >
        {loadingDoc ? (
          <div style={{ margin: 'auto', textAlign: 'center', padding: 60 }}>
            <Spin size="large" tip="Đang nạp dữ liệu PDF..." />
          </div>
        ) : errorMsg ? (
          <div style={{ margin: 'auto', maxWidth: 450 }}>
            <Alert
              type="error"
              message="Lỗi nạp PDF"
              description={errorMsg}
              showIcon
            />
          </div>
        ) : (
          <div
            style={{
              position: 'relative',
              boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
              borderRadius: 4,
              overflow: 'hidden',
              background: '#ffffff',
            }}
          >
            {renderingPage && (
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  background: 'rgba(255,255,255,0.4)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  zIndex: 2,
                }}
              >
                <Spin size="small" />
              </div>
            )}
            <canvas ref={canvasRef} style={{ display: 'block' }} />
          </div>
        )}
      </div>

      {/* Extracted Text & OCR Details Modal */}
      <Modal
        title={`Văn bản trích xuất - Trang ${currentPage}`}
        open={showTextModal}
        onCancel={() => setShowTextModal(false)}
        footer={null}
        width={700}
      >
        {loadingText ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin tip="Đang tải dữ liệu trang..." />
          </div>
        ) : pageData ? (
          <div>
            <div style={{ marginBottom: 12, display: 'flex', gap: 12 }}>
              <Badge
                status={pageData.ocr_used ? 'warning' : 'success'}
                text={pageData.ocr_used ? 'Nhận dạng bằng OCR' : 'Trích xuất văn bản gốc'}
              />
              {pageData.chapter && (
                <span style={{ color: '#1677ff' }}>
                  <strong>Chương:</strong> {pageData.chapter}
                </span>
              )}
            </div>
            <div
              style={{
                maxHeight: 450,
                overflowY: 'auto',
                whiteSpace: 'pre-wrap',
                background: '#fafafa',
                padding: 16,
                borderRadius: 6,
                border: '1px solid #d9d9d9',
                fontFamily: 'monospace',
                fontSize: 13,
                lineHeight: 1.6,
                color: '#333',
              }}
            >
              {pageData.text || 'Trang này không có nội dung văn bản.'}
            </div>
          </div>
        ) : (
          <p>Không tìm thấy dữ liệu trang.</p>
        )}
      </Modal>
    </div>
  )
}
