import React, { useState, useEffect } from 'react'
import {
  ConfigProvider,
  theme as antdTheme,
  Tabs,
  Drawer,
  Empty,
  Button,
  message,
} from 'antd'
import {
  MessageOutlined,
  ReadOutlined,
  UploadOutlined,
  FilePdfOutlined,
} from '@ant-design/icons'

import { Navbar } from './components/Navbar'
import { DocumentList } from './components/DocumentList'
import { PDFViewer } from './components/PDFViewer'
import { ChatPanel } from './components/ChatPanel'
import { StudyTools } from './components/StudyTools'
import { UploadModal } from './components/UploadModal'

import { useDocuments } from './hooks/useDocuments'
import { useChat } from './hooks/useChat'
import { reindexDocument } from './services/api'

export const App: React.FC = () => {
  const [isDarkMode, setIsDarkMode] = useState(false)
  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false)

  // PDF Viewer navigation state
  const [targetPage, setTargetPage] = useState<number>(1)
  const [highlightText, setHighlightText] = useState<string | undefined>(undefined)

  // Mobile layout tab
  const [mobileTab, setMobileTab] = useState<'pdf' | 'chat' | 'tools'>('chat')
  const [isMobile, setIsMobile] = useState<boolean>(window.innerWidth < 992)

  const [rightPanelTab, setRightPanelTab] = useState<'chat' | 'tools'>('chat')

  const {
    documents,
    selectedDoc,
    loading: docsLoading,
    refreshDocuments,
    deleteDocument,
    selectDocument,
    setSelectedDoc,
  } = useDocuments()

  const {
    messages,
    loading: chatLoading,
    topK,
    setTopK,
    sendMessage,
    clearChat,
  } = useChat(selectedDoc?.id)

  // Screen resize listener
  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < 992)
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  // Sync dark theme with document element
  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.setAttribute('data-theme', 'dark')
    } else {
      document.documentElement.removeAttribute('data-theme')
    }
  }, [isDarkMode])

  const handleCitationClick = (page: number, text?: string) => {
    setTargetPage(page)
    setHighlightText(text)
    if (isMobile) {
      setMobileTab('pdf')
    }
  }

  const handleJumpToPage = (page: number) => {
    setTargetPage(page)
    setHighlightText(undefined)
    if (isMobile) {
      setMobileTab('pdf')
    }
  }

  const handleReindexDocument = async (id: string) => {
    try {
      message.loading({ content: 'Đang bắt đầu quét OCR và lập chỉ mục lại...', key: 'reindex' })
      await reindexDocument(id)
      message.success({ content: 'Đã kích hoạt xử lý nền!', key: 'reindex' })
      refreshDocuments()
    } catch (err: any) {
      message.error({ content: err.response?.data?.detail || 'Lỗi khi kích hoạt xử lý lại.', key: 'reindex' })
    }
  }

  return (
    <ConfigProvider
      theme={{
        algorithm: isDarkMode ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
        token: {
          colorPrimary: '#1677ff',
          borderRadius: 8,
          fontFamily: "'Inter', sans-serif",
        },
      }}
    >
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          height: '100vh',
          width: '100vw',
          overflow: 'hidden',
          background: isDarkMode ? '#141414' : '#f5f5f5',
        }}
      >
        {/* Top Navbar */}
        <Navbar
          currentDocumentTitle={selectedDoc?.filename}
          isDarkMode={isDarkMode}
          onToggleDarkMode={() => setIsDarkMode(!isDarkMode)}
          onToggleSidebar={() => setIsMobileDrawerOpen(true)}
          isMobile={isMobile}
        />

        {/* Main Content Area */}
        <div style={{ display: 'flex', flex: 1, height: 'calc(100vh - 56px)', overflow: 'hidden' }}>
          {/* Desktop Left Sidebar: Documents */}
          {!isMobile && (
            <div
              style={{
                width: 300,
                minWidth: 260,
                borderRight: isDarkMode ? '1px solid #303030' : '1px solid #e8e8e8',
                background: isDarkMode ? '#1f1f1f' : '#ffffff',
                height: '100%',
              }}
            >
              <DocumentList
                documents={documents}
                selectedDocId={selectedDoc?.id}
                onSelectDocument={(doc) => {
                  selectDocument(doc)
                  setTargetPage(1)
                  setHighlightText(undefined)
                }}
                onDeleteDocument={deleteDocument}
                onReindexDocument={handleReindexDocument}
                onOpenUpload={() => setIsUploadOpen(true)}
                loading={docsLoading}
              />
            </div>
          )}

          {/* Center & Right Content */}
          <div style={{ flex: 1, display: 'flex', height: '100%', overflow: 'hidden' }}>
            {!selectedDoc ? (
              <div
                style={{
                  flex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: 24,
                }}
              >
                <Empty
                  image={<FilePdfOutlined style={{ fontSize: 64, color: '#1677ff' }} />}
                  description={
                    <div>
                      <h3 style={{ marginTop: 16, color: isDarkMode ? '#fff' : '#1f1f1f' }}>
                        Chưa chọn tài liệu nào
                      </h3>
                      <p style={{ color: '#888', marginTop: 4 }}>
                        Hãy chọn một tài liệu ở cột bên trái hoặc tải lên tài liệu PDF mới để bắt đầu.
                      </p>
                    </div>
                  }
                >
                  <Button
                    type="primary"
                    icon={<UploadOutlined />}
                    size="large"
                    onClick={() => setIsUploadOpen(true)}
                    style={{ marginTop: 12 }}
                  >
                    Tải lên PDF ngay
                  </Button>
                </Empty>
              </div>
            ) : isMobile ? (
              /* Mobile Tabs View */
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%' }}>
                <div style={{ padding: '4px 8px', background: isDarkMode ? '#1f1f1f' : '#fff' }}>
                  <Tabs
                    activeKey={mobileTab}
                    onChange={(k) => setMobileTab(k as any)}
                    centered
                    items={[
                      { key: 'pdf', label: 'PDF Viewer' },
                      { key: 'chat', label: 'AI Chat' },
                      { key: 'tools', label: 'Công cụ học tập' },
                    ]}
                  />
                </div>
                <div style={{ flex: 1, overflow: 'hidden' }}>
                  {mobileTab === 'pdf' && (
                    <PDFViewer
                      documentId={selectedDoc.id}
                      filename={selectedDoc.filename}
                      targetPage={targetPage}
                      highlightText={highlightText}
                      onPageChange={setTargetPage}
                    />
                  )}
                  {mobileTab === 'chat' && (
                    <ChatPanel
                      documentId={selectedDoc.id}
                      messages={messages}
                      loading={chatLoading}
                      topK={topK}
                      onTopKChange={setTopK}
                      onSendMessage={sendMessage}
                      onClearChat={clearChat}
                      onCitationClick={handleCitationClick}
                    />
                  )}
                  {mobileTab === 'tools' && (
                    <StudyTools
                      documentId={selectedDoc.id}
                      onJumpToPage={handleJumpToPage}
                    />
                  )}
                </div>
              </div>
            ) : (
              /* Desktop 2-Column Split: Center PDF Viewer + Right AI Panel */
              <>
                {/* Center Column: PDF Viewer */}
                <div
                  style={{
                    flex: 1,
                    height: '100%',
                    padding: 8,
                    background: isDarkMode ? '#141414' : '#f0f2f5',
                    overflow: 'hidden',
                  }}
                >
                  <PDFViewer
                    documentId={selectedDoc.id}
                    filename={selectedDoc.filename}
                    targetPage={targetPage}
                    highlightText={highlightText}
                    onPageChange={setTargetPage}
                  />
                </div>

                {/* Right Column: AI Assistant & Tools Panel */}
                <div
                  style={{
                    width: 440,
                    minWidth: 380,
                    maxWidth: 520,
                    height: '100%',
                    borderLeft: isDarkMode ? '1px solid #303030' : '1px solid #e8e8e8',
                    background: isDarkMode ? '#1f1f1f' : '#ffffff',
                    display: 'flex',
                    flexDirection: 'column',
                    overflow: 'hidden',
                  }}
                >
                  {/* Top Switcher: Chat vs Study Tools */}
                  <div
                    style={{
                      padding: '4px 16px',
                      background: isDarkMode ? '#141414' : '#fafafa',
                      borderBottom: isDarkMode ? '1px solid #303030' : '1px solid #f0f0f0',
                    }}
                  >
                    <Tabs
                      activeKey={rightPanelTab}
                      onChange={(k) => setRightPanelTab(k as any)}
                      size="middle"
                      style={{ marginBottom: 0 }}
                      items={[
                        {
                          key: 'chat',
                          label: (
                            <span>
                              <MessageOutlined /> Trò chuyện AI
                            </span>
                          ),
                        },
                        {
                          key: 'tools',
                          label: (
                            <span>
                              <ReadOutlined /> Công cụ học tập & Tóm tắt
                            </span>
                          ),
                        },
                      ]}
                    />
                  </div>

                  {/* Panel Content */}
                  <div style={{ flex: 1, overflow: 'hidden' }}>
                    {rightPanelTab === 'chat' ? (
                      <ChatPanel
                        documentId={selectedDoc.id}
                        messages={messages}
                        loading={chatLoading}
                        topK={topK}
                        onTopKChange={setTopK}
                        onSendMessage={sendMessage}
                        onClearChat={clearChat}
                        onCitationClick={handleCitationClick}
                      />
                    ) : (
                      <StudyTools
                        documentId={selectedDoc.id}
                        onJumpToPage={handleJumpToPage}
                      />
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Mobile Drawer for Document List */}
        <Drawer
          title="Tài liệu của bạn"
          placement="left"
          onClose={() => setIsMobileDrawerOpen(false)}
          open={isMobileDrawerOpen}
          styles={{ body: { padding: 0 } }}
        >
          <DocumentList
            documents={documents}
            selectedDocId={selectedDoc?.id}
            onSelectDocument={(doc) => {
              selectDocument(doc)
              setIsMobileDrawerOpen(false)
            }}
            onDeleteDocument={deleteDocument}
            onReindexDocument={handleReindexDocument}
            onOpenUpload={() => {
              setIsMobileDrawerOpen(false)
              setIsUploadOpen(true)
            }}
            loading={docsLoading}
          />
        </Drawer>

        {/* Upload Modal */}
        <UploadModal
          open={isUploadOpen}
          onClose={() => setIsUploadOpen(false)}
          onUploadSuccess={(newDoc) => {
            refreshDocuments()
            setSelectedDoc(newDoc)
            setIsUploadOpen(false)
          }}
        />
      </div>
    </ConfigProvider>
  )
}

export default App
