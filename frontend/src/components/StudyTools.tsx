import React, { useState } from 'react'
import {
  Button,
  Card,
  Typography,
  Space,
  Input,
  Spin,
  Alert,
  Tabs,
  Tag,
  Radio,
} from 'antd'
import {
  FileTextOutlined,
  BulbOutlined,
  QuestionCircleOutlined,
  ReadOutlined,
  CompassOutlined,
  AimOutlined,
} from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import { formatMathMarkdown } from '../utils/math'
import {
  getFullSummary,
  getKeyPoints,
  explainConcept,
  getFlashcards,
  getQuestions,
} from '../services/api'
import type { FlashcardItem, QuestionItem } from '../types'

const { Text, Title } = Typography

interface StudyToolsProps {
  documentId: string
  onJumpToPage: (page: number) => void
}

export const StudyTools: React.FC<StudyToolsProps> = ({ documentId, onJumpToPage }) => {
  const [activeTab, setActiveTab] = useState('summary')

  // Summary State
  const [summary, setSummary] = useState<string>('')
  const [loadingSummary, setLoadingSummary] = useState(false)

  // Key Points State
  const [keyPoints, setKeyPoints] = useState<string>('')
  const [loadingKeyPoints, setLoadingKeyPoints] = useState(false)

  // Explain State
  const [concept, setConcept] = useState('')
  const [explanation, setExplanation] = useState('')
  const [loadingExplain, setLoadingExplain] = useState(false)

  // Flashcards State
  const [flashcards, setFlashcards] = useState<FlashcardItem[]>([])
  const [cardIdx, setCardIdx] = useState(0)
  const [showAnswer, setShowAnswer] = useState(false)
  const [loadingCards, setLoadingCards] = useState(false)

  // Questions State
  const [questions, setQuestions] = useState<QuestionItem[]>([])
  const [loadingQuestions, setLoadingQuestions] = useState(false)
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, string>>({})
  const [showExplanation, setShowExplanation] = useState<Record<number, boolean>>({})

  const handleFetchSummary = async () => {
    setLoadingSummary(true)
    try {
      const data = await getFullSummary(documentId)
      setSummary(data.content)
    } catch (e: any) {
      setSummary(`Lỗi: ${e.message}`)
    } finally {
      setLoadingSummary(false)
    }
  }

  const handleFetchKeyPoints = async () => {
    setLoadingKeyPoints(true)
    try {
      const data = await getKeyPoints(documentId)
      setKeyPoints(data.content)
    } catch (e: any) {
      setKeyPoints(`Lỗi: ${e.message}`)
    } finally {
      setLoadingKeyPoints(false)
    }
  }

  const handleExplain = async () => {
    if (!concept.trim()) return
    setLoadingExplain(true)
    try {
      const data = await explainConcept(documentId, concept)
      setExplanation(data.content)
    } catch (e: any) {
      setExplanation(`Lỗi: ${e.message}`)
    } finally {
      setLoadingExplain(false)
    }
  }

  const handleFetchCards = async () => {
    setLoadingCards(true)
    setShowAnswer(false)
    setCardIdx(0)
    try {
      const data = await getFlashcards(documentId)
      setFlashcards(data.flashcards)
    } catch {
      setFlashcards([])
    } finally {
      setLoadingCards(false)
    }
  }

  const handleFetchQuestions = async () => {
    setLoadingQuestions(true)
    setSelectedAnswers({})
    setShowExplanation({})
    try {
      const data = await getQuestions(documentId)
      setQuestions(data.questions)
    } catch {
      setQuestions([])
    } finally {
      setLoadingQuestions(false)
    }
  }

  return (
    <div style={{ padding: '12px 16px', height: '100%', overflowY: 'auto', background: '#fff' }}>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        size="small"
        items={[
          {
            key: 'summary',
            label: (
              <span>
                <FileTextOutlined /> Tóm tắt
              </span>
            ),
            children: (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <Text strong style={{ fontSize: 14 }}>
                    Tóm tắt toàn bộ tài liệu (Map-Reduce)
                  </Text>
                  <Button
                    type="primary"
                    size="small"
                    loading={loadingSummary}
                    onClick={handleFetchSummary}
                  >
                    {summary ? 'Tạo lại' : 'Bắt đầu tóm tắt'}
                  </Button>
                </div>
                {loadingSummary && (
                  <div style={{ textAlign: 'center', padding: 30 }}>
                    <Spin tip="Đang chạy Map-Reduce pipeline..." />
                  </div>
                )}
                {summary && (
                  <div className="markdown-content" style={{ padding: 12, background: '#fafafa', borderRadius: 8 }}>
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkMath]}
                      rehypePlugins={[rehypeKatex]}
                    >
                      {formatMathMarkdown(summary)}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
            ),
          },
          {
            key: 'keypoints',
            label: (
              <span>
                <BulbOutlined /> Ý chính
              </span>
            ),
            children: (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <Text strong style={{ fontSize: 14 }}>
                    Các điểm cốt lõi (Key Points)
                  </Text>
                  <Button
                    type="primary"
                    size="small"
                    loading={loadingKeyPoints}
                    onClick={handleFetchKeyPoints}
                  >
                    Trích xuất ý chính
                  </Button>
                </div>
                {loadingKeyPoints && (
                  <div style={{ textAlign: 'center', padding: 30 }}>
                    <Spin tip="Đang trích xuất các ý chính từ tài liệu..." />
                  </div>
                )}
                {keyPoints && (
                  <div className="markdown-content" style={{ padding: 12, background: '#fafafa', borderRadius: 8 }}>
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkMath]}
                      rehypePlugins={[rehypeKatex]}
                    >
                      {formatMathMarkdown(keyPoints)}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
            ),
          },
          {
            key: 'flashcards',
            label: (
              <span>
                <ReadOutlined /> Flashcards
              </span>
            ),
            children: (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                  <Text strong style={{ fontSize: 14 }}>
                    Thẻ ghi nhớ thông minh
                  </Text>
                  <Button size="small" type="primary" loading={loadingCards} onClick={handleFetchCards}>
                    {flashcards.length > 0 ? 'Tạo bộ thẻ mới' : 'Tạo Flashcards'}
                  </Button>
                </div>

                {loadingCards && (
                  <div style={{ textAlign: 'center', padding: 40 }}>
                    <Spin tip="Đang tạo flashcards từ tài liệu..." />
                  </div>
                )}

                {flashcards.length > 0 && (
                  <div>
                    <div style={{ textAlign: 'center', marginBottom: 8, fontSize: 12, color: '#888' }}>
                      Thẻ {cardIdx + 1} / {flashcards.length}
                    </div>

                    {/* Interactive Flashcard */}
                    <Card
                      hoverable
                      onClick={() => setShowAnswer(!showAnswer)}
                      style={{
                        minHeight: 180,
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'center',
                        alignItems: 'center',
                        textAlign: 'center',
                        cursor: 'pointer',
                        background: showAnswer ? '#f6ffed' : '#f0f5ff',
                        borderColor: showAnswer ? '#b7eb8f' : '#adc6ff',
                        transition: 'all 0.3s ease',
                        padding: 16,
                      }}
                    >
                      <Tag color={showAnswer ? 'success' : 'processing'} style={{ marginBottom: 12 }}>
                        {showAnswer ? 'ĐÁP ÁN' : 'CÂU HỎI (Click để lật thẻ)'}
                      </Tag>
                      <Title level={5} style={{ margin: 0, fontWeight: 500 }}>
                        {showAnswer ? flashcards[cardIdx].answer : flashcards[cardIdx].question}
                      </Title>

                      {showAnswer && flashcards[cardIdx].page && (
                        <div style={{ marginTop: 16 }}>
                          <Button
                            size="small"
                            type="link"
                            icon={<AimOutlined />}
                            onClick={(e) => {
                              e.stopPropagation()
                              onJumpToPage(flashcards[cardIdx].page!)
                            }}
                          >
                            Xem trang {flashcards[cardIdx].page} trong PDF
                          </Button>
                        </div>
                      )}
                    </Card>

                    {/* Navigation buttons */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 16 }}>
                      <Button
                        disabled={cardIdx <= 0}
                        onClick={() => {
                          setCardIdx(cardIdx - 1)
                          setShowAnswer(false)
                        }}
                      >
                        Thẻ trước
                      </Button>
                      <Button
                        type="dashed"
                        onClick={() => setShowAnswer(!showAnswer)}
                      >
                        {showAnswer ? 'Xem câu hỏi' : 'Lật xem đáp án'}
                      </Button>
                      <Button
                        disabled={cardIdx >= flashcards.length - 1}
                        onClick={() => {
                          setCardIdx(cardIdx + 1)
                          setShowAnswer(false)
                        }}
                      >
                        Thẻ tiếp
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            ),
          },
          {
            key: 'quiz',
            label: (
              <span>
                <QuestionCircleOutlined /> Ôn tập
              </span>
            ),
            children: (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                  <Text strong style={{ fontSize: 14 }}>
                    Bộ câu hỏi kiểm tra kiến thức
                  </Text>
                  <Button size="small" type="primary" loading={loadingQuestions} onClick={handleFetchQuestions}>
                    Tạo câu hỏi
                  </Button>
                </div>

                {loadingQuestions && (
                  <div style={{ textAlign: 'center', padding: 40 }}>
                    <Spin tip="Đang tạo bài kiểm tra..." />
                  </div>
                )}

                {questions.length > 0 && (
                  <Space orientation="vertical" style={{ width: '100%' }} size={16}>
                    {questions.map((q, idx) => (
                      <Card key={idx} size="small" style={{ borderRadius: 8 }}>
                        <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 8 }}>
                          {idx + 1}. {q.question}
                        </Text>

                        {q.options && q.options.length > 0 && (
                          <Radio.Group
                            style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 8 }}
                            value={selectedAnswers[idx]}
                            onChange={(e) =>
                              setSelectedAnswers((prev) => ({ ...prev, [idx]: e.target.value }))
                            }
                          >
                            {q.options.map((opt, oIdx) => (
                              <Radio key={oIdx} value={opt}>
                                {opt}
                              </Radio>
                            ))}
                          </Radio.Group>
                        )}

                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
                          <Button
                            size="small"
                            type="link"
                            onClick={() =>
                              setShowExplanation((prev) => ({ ...prev, [idx]: !prev[idx] }))
                            }
                          >
                            {showExplanation[idx] ? 'Ẩn đáp án' : 'Xem đáp án & Giải thích'}
                          </Button>
                          {q.page && (
                            <Button
                              size="small"
                              type="text"
                              icon={<AimOutlined />}
                              onClick={() => onJumpToPage(q.page!)}
                            >
                              Trang {q.page}
                            </Button>
                          )}
                        </div>

                        {showExplanation[idx] && (
                          <Alert
                            style={{ marginTop: 8 }}
                            type="info"
                            message={
                              <div>
                                <div><strong>Đáp án đúng:</strong> {q.answer}</div>
                                {q.explanation && <div style={{ marginTop: 4 }}><strong>Giải thích:</strong> {q.explanation}</div>}
                              </div>
                            }
                          />
                        )}
                      </Card>
                    ))}
                  </Space>
                )}
              </div>
            ),
          },
          {
            key: 'explain',
            label: (
              <span>
                <CompassOutlined /> Giải thích
              </span>
            ),
            children: (
              <div>
                <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 8 }}>
                  Giải thích khái niệm khó hiểu trong tài liệu
                </Text>
                <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                  <Input
                    placeholder="Nhập thuật ngữ, công thức hoặc đoạn nội dung..."
                    value={concept}
                    onChange={(e) => setConcept(e.target.value)}
                    onPressEnter={handleExplain}
                  />
                  <Button type="primary" loading={loadingExplain} onClick={handleExplain}>
                    Giải thích
                  </Button>
                </div>

                {loadingExplain && (
                  <div style={{ textAlign: 'center', padding: 30 }}>
                    <Spin tip="AI đang phân tích ngữ cảnh..." />
                  </div>
                )}

                {explanation && (
                  <div className="markdown-content" style={{ padding: 12, background: '#fafafa', borderRadius: 8 }}>
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkMath]}
                      rehypePlugins={[rehypeKatex]}
                    >
                      {formatMathMarkdown(explanation)}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
            ),
          },
        ]}
      />
    </div>
  )
}
