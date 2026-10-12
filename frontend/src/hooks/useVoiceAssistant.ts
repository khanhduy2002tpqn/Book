import { useState, useEffect, useRef, useCallback } from 'react'
import { message } from 'antd'

// Polyfill interfaces for Web Speech API
interface IWindow extends Window {
  SpeechRecognition?: any
  webkitSpeechRecognition?: any
}

export interface UseVoiceAssistantOptions {
  onFinalTranscript?: (transcript: string) => void
  lang?: string
}

export function cleanMarkdownForSpeech(markdown: string): string {
  if (!markdown) return ''

  return markdown
    // Remove code blocks
    .replace(/```[\s\S]*?```/g, 'đoạn mã')
    // Remove inline code
    .replace(/`([^`]+)`/g, '$1')
    // Replace citations like [Trang 5] or [Trang 2, Trang 4] with silence
    .replace(/\[\s*Trang\s*(\d+)(?:,\s*Trang\s*(\d+))*\s*\]/gi, '')
    // Remove markdown image/link syntax [text](url) -> text
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    // Mathematical LaTeX replacements for smooth natural speech
    .replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, '$1 chia cho $2')
    .replace(/\\frac\s*(\d+)\s*(\d+)/g, '$1 phần $2')
    .replace(/\\mathbb\{R\}/g, 'tập số thực R')
    .replace(/\\mathbb\{Z\}/g, 'tập số nguyên Z')
    .replace(/\\mathbb\{N\}/g, 'tập số tự nhiên N')
    .replace(/\\mathbb\{Q\}/g, 'tập số hữu tỉ Q')
    .replace(/\\setminus/g, 'loại trừ')
    .replace(/\\subset/g, 'tập con của')
    .replace(/\\cap/g, 'giao')
    .replace(/\\cup/g, 'hợp')
    .replace(/\\in/g, 'thuộc')
    .replace(/\\notin/g, 'không thuộc')
    .replace(/\\pi/g, 'pi')
    .replace(/\\alpha/g, 'an-pha')
    .replace(/\\beta/g, 'bê-ta')
    .replace(/\\theta/g, 'thê-ta')
    .replace(/\\pm/g, 'cộng trừ')
    .replace(/\\neq|\\ne/g, 'khác')
    .replace(/\\leq|\\le/g, 'nhỏ hơn hoặc bằng')
    .replace(/\\geq|\\ge/g, 'lớn hơn hoặc bằng')
    .replace(/\\approx/g, 'xấp xỉ')
    .replace(/\\sqrt\{([^{}]+)\}/g, 'căn bậc hai của $1')
    .replace(/\\sin/g, 'sin')
    .replace(/\\cos/g, 'cốt')
    .replace(/\\tan/g, 'tan')
    .replace(/\\cot/g, 'cô-tan')
    .replace(/\\mid/g, 'sao cho')
    .replace(/\\times/g, 'nhân')
    .replace(/\\cdot/g, 'nhân')
    .replace(/\\infty/g, 'vô cực')
    // Remove remaining LaTeX delimiters & backslashes
    .replace(/(\$\$|\$|\\\[|\\\]|\\\(|\\\))/g, ' ')
    .replace(/[{}]/g, '')
    // Remove markdown headers #, ##, etc.
    .replace(/^#{1,6}\s+/gm, '')
    // Remove bold/italic markers
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/_([^_]+)_/g, '$1')
    // Replace bullet points with brief pauses
    .replace(/^\s*[-*+]\s+/gm, '')
    // Replace numbered lists with natural numbering
    .replace(/^\s*\d+\.\s+/gm, '')
    // Remove HTML tags
    .replace(/<[^>]*>/g, '')
    // Condense multiple newlines or spaces
    .replace(/\n\s*\n/g, '. ')
    .replace(/\n/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export const useVoiceAssistant = (options?: UseVoiceAssistantOptions) => {
  const [isListening, setIsListening] = useState(false)
  const [interimTranscript, setInterimTranscript] = useState('')
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [currentSpeakingId, setCurrentSpeakingId] = useState<string | null>(null)
  const [autoReadResponse, setAutoReadResponse] = useState<boolean>(false)
  const [speechRate, setSpeechRate] = useState<number>(1.0)
  const [selectedVoice, setSelectedVoice] = useState<SpeechSynthesisVoice | null>(null)
  const [availableVoices, setAvailableVoices] = useState<SpeechSynthesisVoice[]>([])

  const recognitionRef = useRef<any>(null)
  const speechUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null)

  const isRecognitionSupported = typeof window !== 'undefined' &&
    !!((window as unknown as IWindow).SpeechRecognition || (window as unknown as IWindow).webkitSpeechRecognition)

  const isSynthesisSupported = typeof window !== 'undefined' && 'speechSynthesis' in window

  // Load and filter voices
  useEffect(() => {
    if (!isSynthesisSupported) return

    const updateVoices = () => {
      const voices = window.speechSynthesis.getVoices()
      setAvailableVoices(voices)

      // Find best Vietnamese voice
      const viVoice = voices.find((v) => v.lang.toLowerCase().includes('vi'))
      if (viVoice) {
        setSelectedVoice(viVoice)
      } else if (voices.length > 0) {
        setSelectedVoice(voices[0])
      }
    }

    updateVoices()
    if (window.speechSynthesis.onvoiceschanged !== undefined) {
      window.speechSynthesis.onvoiceschanged = updateVoices
    }
  }, [isSynthesisSupported])

  // Stop synthesis on unmount
  useEffect(() => {
    return () => {
      if (isSynthesisSupported) {
        window.speechSynthesis.cancel()
      }
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort()
        } catch {
          // ignore
        }
      }
    }
  }, [isSynthesisSupported])

  // Start Speech-to-Text
  const startListening = useCallback(() => {
    if (!isRecognitionSupported) {
      message.warning('Trình duyệt của bạn chưa hỗ trợ nhận diện giọng nói (Khuyến nghị dùng Google Chrome hoặc Microsoft Edge).')
      return
    }

    try {
      const SpeechRecognitionClass =
        (window as unknown as IWindow).SpeechRecognition ||
        (window as unknown as IWindow).webkitSpeechRecognition

      const recognition = new SpeechRecognitionClass()
      recognition.lang = options?.lang || 'vi-VN'
      recognition.continuous = false
      recognition.interimResults = true
      recognition.maxAlternatives = 1

      recognition.onstart = () => {
        setIsListening(true)
        setInterimTranscript('')
      }

      recognition.onresult = (event: any) => {
        let interim = ''
        let final = ''

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const trans = event.results[i][0].transcript
          if (event.results[i].isFinal) {
            final += trans
          } else {
            interim += trans
          }
        }

        if (interim) {
          setInterimTranscript(interim)
        }

        if (final) {
          setInterimTranscript('')
          if (options?.onFinalTranscript) {
            options.onFinalTranscript(final.trim())
          }
        }
      }

      recognition.onerror = (event: any) => {
        console.error('Speech recognition error:', event.error)
        setIsListening(false)
        setInterimTranscript('')
        if (event.error === 'not-allowed') {
          message.error('Vui lòng cấp quyền truy cập Microphone trong trình duyệt để sử dụng tính năng này.')
        } else if (event.error === 'no-speech') {
          // silence, do not spam
        } else {
          message.warning(`Không nhận diện được giọng nói (${event.error}).`)
        }
      }

      recognition.onend = () => {
        setIsListening(false)
        setInterimTranscript('')
      }

      recognitionRef.current = recognition
      recognition.start()
    } catch (err) {
      console.error('Failed to start speech recognition:', err)
      setIsListening(false)
      message.error('Không thể khởi động micro.')
    }
  }, [isRecognitionSupported, options])

  // Stop Speech-to-Text
  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop()
      } catch {
        // ignore
      }
    }
    setIsListening(false)
    setInterimTranscript('')
  }, [])

  const toggleListening = useCallback(() => {
    if (isListening) {
      stopListening()
    } else {
      startListening()
    }
  }, [isListening, startListening, stopListening])

  // Stop Text-to-Speech
  const stopSpeaking = useCallback(() => {
    if (!isSynthesisSupported) return
    window.speechSynthesis.cancel()
    setIsSpeaking(false)
    setCurrentSpeakingId(null)
  }, [isSynthesisSupported])

  // Speak Text
  const speakText = useCallback(
    (rawText: string, messageId?: string) => {
      if (!isSynthesisSupported) {
        message.warning('Trình duyệt của bạn không hỗ trợ tính năng phát âm thanh (SpeechSynthesis).')
        return
      }

      // If currently speaking this exact message, stop it (toggle behavior)
      if (isSpeaking && currentSpeakingId === messageId) {
        stopSpeaking()
        return
      }

      // Stop previous utterance
      window.speechSynthesis.cancel()

      const cleanedText = cleanMarkdownForSpeech(rawText)
      if (!cleanedText) return

      const utterance = new SpeechSynthesisUtterance(cleanedText)
      utterance.lang = options?.lang || 'vi-VN'
      utterance.rate = speechRate
      utterance.pitch = 1.0

      if (selectedVoice) {
        utterance.voice = selectedVoice
      }

      utterance.onstart = () => {
        setIsSpeaking(true)
        if (messageId) setCurrentSpeakingId(messageId)
      }

      utterance.onend = () => {
        setIsSpeaking(false)
        setCurrentSpeakingId(null)
      }

      utterance.onerror = (e) => {
        console.error('SpeechSynthesis error:', e)
        setIsSpeaking(false)
        setCurrentSpeakingId(null)
      }

      speechUtteranceRef.current = utterance
      window.speechSynthesis.speak(utterance)
    },
    [isSynthesisSupported, isSpeaking, currentSpeakingId, options?.lang, speechRate, selectedVoice, stopSpeaking]
  )

  return {
    // STT
    isListening,
    interimTranscript,
    isRecognitionSupported,
    startListening,
    stopListening,
    toggleListening,

    // TTS
    isSpeaking,
    currentSpeakingId,
    isSynthesisSupported,
    autoReadResponse,
    setAutoReadResponse,
    speechRate,
    setSpeechRate,
    availableVoices,
    selectedVoice,
    setSelectedVoice,
    speakText,
    stopSpeaking,
  }
}
