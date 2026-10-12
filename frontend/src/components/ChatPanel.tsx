import React, { useState, useRef, useEffect } from 'react'
import {
  Input,
  Button,
  Typography,
  Space,
  Tag,
  Spin,
  Tooltip,
  Slider,
  Popover,
  Empty,
  Switch,
  Select,
  Divider,
} from 'antd'
import {
  SendOutlined,
  ClearOutlined,
  SettingOutlined,
  RobotOutlined,
  UserOutlined,
  BookOutlined,
  AimOutlined,
  AudioOutlined,
  SoundOutlined,
  PauseCircleOutlined,
  CustomerServiceOutlined,
} from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { formatMathMarkdown } from '../utils/math'
import type { ChatMessage } from '../types'
import { useVoiceAssistant } from '../hooks/useVoiceAssistant'

const { TextArea } = Input
const { Text } = Typography

interface ChatPanelProps {
  documentId?: string
  messages: ChatMessage[]
  loading: boolean
  topK: number
  onTopKChange: (val: number) => void
  onSendMessage: (msg: string) => void
  onClearChat: () => void
  onCitationClick: (page: number, text?: string) => void
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  messages,
  loading,
  topK,
  onTopKChange,
  onSendMessage,
  onClearChat,
  onCitationClick,
}) => {
  const [inputMessage, setInputMessage] = useState('')
  const [autoSendVoice, setAutoSendVoice] = useState(true)
  const lastSpokenMessageIdRef = useRef<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const {
    isListening,
    interimTranscript,
    isSpeaking,
    currentSpeakingId,
    isRecognitionSupported,
    autoReadResponse,
    setAutoReadResponse,
    speechRate,
    setSpeechRate,
    availableVoices,
    selectedVoice,
    setSelectedVoice,
    toggleListening,
    stopListening,
    speakText,
    stopSpeaking,
  } = useVoiceAssistant({
    lang: 'vi-VN',
    onFinalTranscript: (finalText) => {
      if (!finalText.trim()) return
      if (autoSendVoice) {
        onSendMessage(finalText.trim())
        setInputMessage('')
      } else {
        setInputMessage((prev) => (prev ? `${prev} ${finalText.trim()}` : finalText.trim()))
      }
    },
  })

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, loading])

  // Auto-read newest assistant response if enabled
  useEffect(() => {
    if (!autoReadResponse || loading || messages.length === 0) return

    const lastMessage = messages[messages.length - 1]
    if (lastMessage.role === 'assistant' && lastMessage.id !== lastSpokenMessageIdRef.current) {
      lastSpokenMessageIdRef.current = lastMessage.id
      speakText(lastMessage.content, lastMessage.id)
    }
  }, [messages, loading, autoReadResponse, speakText])

  const handleClearChat = () => {
    stopSpeaking()
    onClearChat()
  }

  const handleSend = () => {
    if (!inputMessage.trim() || loading) return
    onSendMessage(inputMessage.trim())
    setInputMessage('')
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const quickPrompts = [
    'Tài liệu này nói về chủ đề gì?',
    'Tóm tắt các điểm chính trong tài liệu',
    'Giải thích các thuật ngữ quan trọng nhất',
  ]

  const settingsContent = (
    <div style={{ width: 280, padding: 4 }}>
      <div style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
          <Text strong style={{ fontSize: 13 }}>
            Đoạn trích RAG (Top-K): {topK}
          </Text>
        </div>
        <Slider min={3} max={10} value={topK} onChange={onTopKChange} />
        <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
          Số đoạn văn liên quan trong PDF được gửi cho Gemini.
        </Text>
      </div>

      <Divider style={{ margin: '10px 0' }} />

      <div style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <Space size={6}>
            <CustomerServiceOutlined style={{ color: '#1677ff' }} />
            <Text strong style={{ fontSize: 13 }}>
              Tự động đọc câu trả lời
            </Text>
          </Space>
          <Switch size="small" checked={autoReadResponse} onChange={setAutoReadResponse} />
        </div>
        <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
          AI sẽ tự động phát âm thanh đọc câu trả lời ngay khi phản hồi xong.
        </Text>
      </div>

      <div style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <Space size={6}>
            <AudioOutlined style={{ color: '#52c41a' }} />
            <Text strong style={{ fontSize: 13 }}>
              Tự động gửi khi nói xong
            </Text>
          </Space>
          <Switch size="small" checked={autoSendVoice} onChange={setAutoSendVoice} />
        </div>
        <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
          Tự động gửi câu hỏi ngay sau khi nhận diện giọng nói từ micro.
        </Text>
      </div>

      <div style={{ marginBottom: 8 }}>
        <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 4 }}>
          Tốc độ đọc giọng nói: {speechRate}x
        </Text>
        <Slider
          min={0.8}
          max={1.5}
          step={0.1}
          value={speechRate}
          onChange={setSpeechRate}
        />
      </div>

      {availableVoices.length > 0 && (
        <div>
          <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 4 }}>
            Giọng đọc:
          </Text>
          <Select
            size="small"
            style={{ width: '100%' }}
            value={selectedVoice?.name}
            onChange={(name) => {
              const v = availableVoices.find((item) => item.name === name)
              if (v) setSelectedVoice(v)
            }}
            options={availableVoices
              .filter((v) => v.lang.includes('vi') || v.lang.includes('en'))
              .slice(0, 8)
              .map((v) => ({
                label: `${v.name} (${v.lang})`,
                value: v.name,
              }))}
          />
        </div>
      )}
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#fcfcfc' }}>
      {/* Chat Header */}
      <div
        style={{
          padding: '10px 16px',
          background: '#ffffff',
          borderBottom: '1px solid #f0f0f0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Space>
          <RobotOutlined style={{ color: '#1677ff', fontSize: 18 }} />
          <Text strong style={{ fontSize: 15 }}>
            Hỏi đáp AI
          </Text>
          <Tag color="blue" style={{ fontSize: 11 }}>
            Anti-Hallucination
          </Tag>
          {autoReadResponse && (
            <Tag color="green" icon={<SoundOutlined />} style={{ fontSize: 11 }}>
              Auto-Voice ON
            </Tag>
          )}
        </Space>

        <Space size={4}>
          <Popover content={settingsContent} title="Cấu hình RAG & Giọng nói" trigger="click" placement="bottomRight">
            <Tooltip title="Cài đặt RAG & Giọng nói">
              <Button type="text" icon={<SettingOutlined />} size="small" />
            </Tooltip>
          </Popover>
          <Tooltip title="Xóa lịch sử chat">
            <Button
              type="text"
              icon={<ClearOutlined />}
              size="small"
              onClick={handleClearChat}
              disabled={messages.length === 0}
            />
          </Tooltip>
        </Space>
      </div>

      {/* Messages Scroll Area */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
        {messages.length === 0 ? (
          <div style={{ textAlign: 'center', marginTop: 40, padding: '0 20px' }}>
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <div>
                  <Text strong style={{ fontSize: 14 }}>
                    Đặt câu hỏi về nội dung tài liệu
                  </Text>
                  <p style={{ color: '#888', fontSize: 12, marginTop: 4 }}>
                    Bạn có thể gõ phím hoặc <strong>bấm vào biểu tượng Micro 🎙️</strong> để hỏi bằng giọng nói!
                  </p>
                </div>
              }
            />

            <div style={{ marginTop: 24 }}>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
                Gợi ý câu hỏi nhanh:
              </Text>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {quickPrompts.map((q, idx) => (
                  <Button
                    key={idx}
                    type="dashed"
                    size="small"
                    onClick={() => onSendMessage(q)}
                    style={{ textAlign: 'left', whiteSpace: 'normal', height: 'auto', padding: '6px 12px' }}
                  >
                    💡 {q}
                  </Button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                marginBottom: 16,
                display: 'flex',
                flexDirection: 'column',
                alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
              }}
            >
              {/* Sender label & Voice controls */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  marginBottom: 4,
                  fontSize: 12,
                  color: '#888',
                }}
              >
                {msg.role === 'user' ? (
                  <>
                    <span>Bạn</span>
                    <UserOutlined />
                  </>
                ) : (
                  <>
                    <RobotOutlined style={{ color: '#1677ff' }} />
                    <span style={{ color: '#1677ff', fontWeight: 500 }}>AI Assistant</span>
                    {/* TTS Speaker Play/Stop Button */}
                    <Tooltip
                      title={
                        isSpeaking && currentSpeakingId === msg.id
                          ? 'Dừng đọc âm thanh'
                          : 'Nghe AI đọc câu trả lời'
                      }
                    >
                      <Button
                        type="text"
                        size="small"
                        onClick={() => speakText(msg.content, msg.id)}
                        style={{
                          height: 22,
                          padding: '0 6px',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 4,
                          color: isSpeaking && currentSpeakingId === msg.id ? '#1677ff' : '#8c8c8c',
                          background: isSpeaking && currentSpeakingId === msg.id ? '#e6f4ff' : 'transparent',
                          borderRadius: 4,
                        }}
                      >
                        {isSpeaking && currentSpeakingId === msg.id ? (
                          <>
                            <PauseCircleOutlined style={{ color: '#1677ff', fontSize: 13 }} />
                            <span className="sound-wave-container">
                              <span className="sound-bar" />
                              <span className="sound-bar" />
                              <span className="sound-bar" />
                              <span className="sound-bar" />
                            </span>
                            <span style={{ fontSize: 11, color: '#1677ff' }}>Đang đọc</span>
                          </>
                        ) : (
                          <>
                            <SoundOutlined style={{ fontSize: 13 }} />
                            <span style={{ fontSize: 11 }}>Đọc</span>
                          </>
                        )}
                      </Button>
                    </Tooltip>
                  </>
                )}
              </div>

              {/* Message Bubble */}
              <div
                style={{
                  maxWidth: '92%',
                  padding: '12px 16px',
                  borderRadius: msg.role === 'user' ? '14px 14px 2px 14px' : '14px 14px 14px 2px',
                  background: msg.role === 'user' ? '#1677ff' : '#ffffff',
                  color: msg.role === 'user' ? '#ffffff' : '#1f1f1f',
                  border: msg.role === 'user' ? 'none' : '1px solid #e8e8e8',
                  boxShadow: '0 2px 6px rgba(0,0,0,0.04)',
                  fontSize: 14,
                  lineHeight: 1.6,
                }}
              >
                {msg.role === 'user' ? (
                  <span style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</span>
                ) : (
                  <div className="markdown-content">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkMath]}
                      rehypePlugins={[rehypeKatex]}
                    >
                      {formatMathMarkdown(msg.content)}
                    </ReactMarkdown>
                  </div>
                )}

                {/* Sources / Citations */}
                {msg.sources && msg.sources.length > 0 && (
                  <div
                    style={{
                      marginTop: 12,
                      paddingTop: 10,
                      borderTop: '1px solid #f0f0f0',
                      fontSize: 12,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, color: '#666' }}>
                      <BookOutlined style={{ color: '#1677ff' }} />
                      <strong style={{ color: '#333' }}>Nguồn tham chiếu:</strong>
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {msg.sources.map((src, i) => (
                        <Tooltip
                          key={i}
                          title={
                            <div>
                              <div><strong>Độ tương đồng:</strong> {(src.score * 100).toFixed(0)}%</div>
                              {src.chapter && <div><strong>Chương:</strong> {src.chapter}</div>}
                              {src.text && <div style={{ marginTop: 4, fontStyle: 'italic' }}>"{src.text.slice(0, 100)}..."</div>}
                              <div style={{ marginTop: 4, color: '#91caff' }}>Nhấp để mở trang này trong PDF</div>
                            </div>
                          }
                        >
                          <Tag
                            color="blue"
                            style={{
                              cursor: 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 4,
                              padding: '2px 8px',
                              borderRadius: 4,
                            }}
                            onClick={() => onCitationClick(src.page, src.text || '')}
                          >
                            <AimOutlined />
                            <span>Trang {src.page}</span>
                            {src.chapter && <span style={{ opacity: 0.8 }}>({src.chapter.slice(0, 15)})</span>}
                          </Tag>
                        </Tooltip>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {/* Loading Indicator */}
        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', color: '#1677ff' }}>
            <Spin size="small" />
            <Text type="secondary" style={{ fontSize: 13 }}>
              AI đang tìm kiếm tài liệu và suy luận...
            </Text>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Voice Recording Active Banner */}
      {isListening && (
        <div
          style={{
            margin: '0 16px 8px 16px',
            padding: '8px 14px',
            background: '#fff1f0',
            border: '1px solid #ffa39e',
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 2px 8px rgba(255, 77, 79, 0.1)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, overflow: 'hidden' }}>
            <AudioOutlined style={{ color: '#ff4d4f', fontSize: 16 }} />
            <div>
              <Text strong style={{ color: '#cf1322', fontSize: 12, display: 'block' }}>
                Đang lắng nghe giọng nói của bạn...
              </Text>
              <Text style={{ color: '#434343', fontSize: 13, fontStyle: interimTranscript ? 'normal' : 'italic' }}>
                {interimTranscript || 'Hãy nói câu hỏi của bạn vào micro...'}
              </Text>
            </div>
          </div>
          <Button
            size="small"
            type="primary"
            danger
            onClick={stopListening}
            style={{ borderRadius: 6, fontSize: 12 }}
          >
            Dừng nói
          </Button>
        </div>
      )}

      {/* Input Box */}
      <div
        style={{
          padding: '12px 16px',
          background: '#ffffff',
          borderTop: '1px solid #f0f0f0',
        }}
      >
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          {/* Microphone button */}
          <Tooltip
            title={
              !isRecognitionSupported
                ? 'Trình duyệt chưa hỗ trợ Voice Recognition (Khuyên dùng Chrome/Edge)'
                : isListening
                ? 'Đang nghe... Nhấp để dừng'
                : 'Bấm để hỏi bằng giọng nói (Micro)'
            }
          >
            <Button
              type={isListening ? 'primary' : 'default'}
              danger={isListening}
              className={isListening ? 'mic-recording-active' : ''}
              icon={<AudioOutlined style={{ fontSize: 16 }} />}
              onClick={toggleListening}
              disabled={loading || !isRecognitionSupported}
              style={{
                height: 38,
                width: 44,
                borderRadius: 8,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.3s ease',
              }}
            />
          </Tooltip>

          <TextArea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Hỏi về nội dung tài liệu... (hoặc bấm Micro 🎙️ để nói)"
            autoSize={{ minRows: 1, maxRows: 4 }}
            disabled={loading}
            style={{ borderRadius: 8, resize: 'none' }}
          />

          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            loading={loading}
            disabled={!inputMessage.trim()}
            style={{ height: 38, width: 44, borderRadius: 8 }}
          />
        </div>
      </div>
    </div>
  )
}
