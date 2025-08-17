import { create } from 'zustand'
import axios from 'axios'

// Use /api prefix to go through Vite proxy in development
const API_URL = import.meta.env.VITE_API_URL || '/api'

interface Item {
  item_id: string
  concept_id: string
  prompt: string
  kc: string
}

interface Concept {
  id: string
  title: string
  description: string
  item_ids: string[]
  prereqs?: string[]
  relations?: Array<{
    type: string
    concept_id: string
  }>
  scheduler_state?: {
    stability_s: number
    next_review_at: string
    last_outcome?: string
  }
}

interface GradeResult {
  outcome: 'success' | 'partial' | 'fail'
  score_adj: number
  explanation_for_user: string
  next_review_eta: string
}

interface Store {
  // State
  dueItems: Item[]
  currentItemIndex: number
  isLoading: boolean
  error: string | null
  lastGradeResult: GradeResult | null
  isRecording: boolean
  audioBlob: Blob | null
  concepts: Concept[]
  
  // Actions
  fetchDueCards: () => Promise<void>
  gradeAttempt: (itemId: string, text: string, latencyMs: number) => Promise<void>
  nextCard: () => void
  previousCard: () => void
  setRecording: (isRecording: boolean) => void
  setAudioBlob: (blob: Blob | null) => void
  ingestUrl: (url: string) => Promise<{ text: string; meta: any }>
  ingestText: (text: string) => Promise<{ text: string; meta: any }>
  authorQuestions: (text: string) => Promise<void>
  fetchConcepts: () => Promise<void>
}

export const useStore = create<Store>((set, get) => ({
  // Initial state
  dueItems: [],
  currentItemIndex: 0,
  isLoading: false,
  error: null,
  lastGradeResult: null,
  isRecording: false,
  audioBlob: null,
  concepts: [],

  // Fetch due cards
  fetchDueCards: async () => {
    set({ isLoading: true, error: null })
    try {
      const response = await axios.get(`${API_URL}/due_cards`)
      set({ 
        dueItems: response.data.items,
        currentItemIndex: 0,
        isLoading: false 
      })
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || 
                      error.message || 
                      'Failed to fetch due cards. Please check if the API server is running.'
      set({ 
        error: errorMsg,
        isLoading: false 
      })
    }
  },

  // Grade an attempt
  gradeAttempt: async (itemId: string, text: string, latencyMs: number) => {
    set({ isLoading: true, error: null })
    try {
      const response = await axios.post(`${API_URL}/grade_attempt`, {
        item_id: itemId,
        text,
        latency_ms: latencyMs
      })
      
      set({ 
        lastGradeResult: response.data,
        isLoading: false 
      })
      
      // Refresh due cards after grading
      setTimeout(() => {
        get().fetchDueCards()
      }, 2000)
      
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || 
                      error.message || 
                      'Failed to grade attempt. Please check your connection.'
      set({ 
        error: errorMsg,
        isLoading: false 
      })
    }
  },

  // Navigation
  nextCard: () => {
    const { currentItemIndex, dueItems } = get()
    if (currentItemIndex < dueItems.length - 1) {
      set({ 
        currentItemIndex: currentItemIndex + 1,
        lastGradeResult: null 
      })
    }
  },

  previousCard: () => {
    const { currentItemIndex } = get()
    if (currentItemIndex > 0) {
      set({ 
        currentItemIndex: currentItemIndex - 1,
        lastGradeResult: null 
      })
    }
  },

  // Recording
  setRecording: (isRecording: boolean) => {
    set({ isRecording })
  },

  setAudioBlob: (blob: Blob | null) => {
    set({ audioBlob: blob })
  },

  // Ingestion
  ingestUrl: async (url: string) => {
    set({ isLoading: true, error: null })
    try {
      const response = await axios.post(`${API_URL}/ingest_url`, { url })
      set({ isLoading: false })
      return response.data
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || 
                      error.response?.data?.error ||
                      error.message || 
                      'Failed to ingest URL. Please check if the API server is running.'
      set({ 
        error: errorMsg,
        isLoading: false 
      })
      throw error
    }
  },

  ingestUrl: async (url: string) => {
    set({ isLoading: true, error: null })
    try {
      const response = await axios.post(`${API_URL}/ingest_url`, { url })
      set({ isLoading: false })
      return response.data
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || 
                      error.response?.data?.error ||
                      error.message || 
                      'Failed to process URL. Please check the URL and try again.'
      set({ 
        error: errorMsg,
        isLoading: false 
      })
      throw error
    }
  },

  ingestText: async (text: string) => {
    set({ isLoading: true, error: null })
    try {
      const response = await axios.post(`${API_URL}/ingest_text`, { text })
      set({ isLoading: false })
      return response.data
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || 
                      error.response?.data?.error ||
                      error.message || 
                      'Failed to process text. Please check if the API server is running.'
      set({ 
        error: errorMsg,
        isLoading: false 
      })
      throw error
    }
  },

  // Authoring
  authorQuestions: async (text: string) => {
    set({ isLoading: true, error: null })
    try {
      await axios.post(`${API_URL}/author_questions`, { text })
      set({ isLoading: false })
      
      // Refresh due cards after authoring
      await get().fetchDueCards()
      
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || 
                      error.response?.data?.error ||
                      error.message || 
                      'Failed to generate questions. Please check if the API server is running and your OpenAI API key is configured.'
      set({ 
        error: errorMsg,
        isLoading: false 
      })
      throw error
    }
  },

  // Fetch concepts
  fetchConcepts: async () => {
    try {
      const response = await axios.get(`${API_URL}/concepts`)
      set({ concepts: response.data.concepts })
    } catch (error: any) {
      console.error('Failed to fetch concepts:', error.response?.data?.detail || error.message)
    }
  }
}))