import { useEffect, useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Mic, MicOff, ChevronRight, ChevronLeft, CheckCircle, XCircle, AlertCircle } from 'lucide-react'
import { useStore } from '@/store/useStore'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

export function ReviewScreen() {
  const {
    dueItems,
    currentItemIndex,
    isLoading,
    error,
    lastGradeResult,
    isRecording,
    fetchDueCards,
    gradeAttempt,
    nextCard,
    previousCard,
    setRecording
  } = useStore()

  const [showAnswer, setShowAnswer] = useState(false)
  const [userAnswer, setUserAnswer] = useState('')
  const [startTime, setStartTime] = useState<number>(0)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  useEffect(() => {
    fetchDueCards()
  }, [])

  const currentItem = dueItems[currentItemIndex]

  const handleStartRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream)
      mediaRecorderRef.current = mediaRecorder
      chunksRef.current = []

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data)
        }
      }

      mediaRecorder.onstop = async () => {
        // const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' })
        // In a real app, we'd send this to ASR service
        // For now, we'll use text input
        stream.getTracks().forEach(track => track.stop())
      }

      mediaRecorder.start()
      setRecording(true)
      setStartTime(Date.now())
    } catch (err) {
      console.error('Failed to start recording:', err)
    }
  }

  const handleStopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      setRecording(false)
    }
  }

  const handleSubmit = async () => {
    if (!currentItem || !userAnswer.trim()) return

    const latencyMs = Date.now() - startTime
    await gradeAttempt(currentItem.item_id, userAnswer, latencyMs)
    setShowAnswer(true)
  }

  const handleNext = () => {
    setShowAnswer(false)
    setUserAnswer('')
    nextCard()
  }

  const handlePrevious = () => {
    setShowAnswer(false)
    setUserAnswer('')
    previousCard()
  }

  if (isLoading && dueItems.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-pulse-slow text-muted-foreground">Loading cards...</div>
      </div>
    )
  }

  if (dueItems.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-screen p-4">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6">
            <div className="text-center space-y-4">
              <CheckCircle className="w-16 h-16 mx-auto text-green-500" />
              <h2 className="text-2xl font-semibold">You're all caught up!</h2>
              <p className="text-muted-foreground">
                No cards due for review right now. Check back later or add new content to study.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted/20 p-4">
      <div className="max-w-2xl mx-auto">
        {/* Progress indicator */}
        <div className="mb-6">
          <div className="flex justify-between text-sm text-muted-foreground mb-2">
            <span>Card {currentItemIndex + 1} of {dueItems.length}</span>
            <span className="font-mono">{currentItem?.kc}</span>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-primary"
              initial={{ width: 0 }}
              animate={{ width: `${((currentItemIndex + 1) / dueItems.length) * 100}%` }}
              transition={{ duration: 0.3 }}
            />
          </div>
        </div>

        {/* Main card */}
        <AnimatePresence mode="wait">
          <motion.div
            key={currentItem?.item_id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
          >
            <Card className="shadow-lg">
              <CardHeader>
                <CardTitle className="text-xl">
                  {currentItem?.prompt}
                </CardTitle>
              </CardHeader>
              
              <CardContent className="space-y-4">
                {/* Answer input area */}
                <div className="space-y-4">
                  <textarea
                    value={userAnswer}
                    onChange={(e) => setUserAnswer(e.target.value)}
                    placeholder="Type your answer here or use the microphone..."
                    className="w-full min-h-[100px] p-3 border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                    disabled={showAnswer}
                  />
                  
                  {/* Voice recording button */}
                  <div className="flex justify-center">
                    <Button
                      size="lg"
                      variant={isRecording ? "destructive" : "default"}
                      className={cn(
                        "rounded-full w-20 h-20 transition-all",
                        isRecording && "animate-pulse"
                      )}
                      onClick={isRecording ? handleStopRecording : handleStartRecording}
                      disabled={showAnswer}
                    >
                      {isRecording ? (
                        <MicOff className="w-8 h-8" />
                      ) : (
                        <Mic className="w-8 h-8" />
                      )}
                    </Button>
                  </div>
                </div>

                {/* Grade result */}
                {showAnswer && lastGradeResult && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className={cn(
                      "p-4 rounded-lg border-2",
                      lastGradeResult.outcome === 'success' && "bg-green-50 border-green-300",
                      lastGradeResult.outcome === 'partial' && "bg-yellow-50 border-yellow-300",
                      lastGradeResult.outcome === 'fail' && "bg-red-50 border-red-300"
                    )}
                  >
                    <div className="flex items-start space-x-3">
                      {lastGradeResult.outcome === 'success' && (
                        <CheckCircle className="w-6 h-6 text-green-600 mt-0.5" />
                      )}
                      {lastGradeResult.outcome === 'partial' && (
                        <AlertCircle className="w-6 h-6 text-yellow-600 mt-0.5" />
                      )}
                      {lastGradeResult.outcome === 'fail' && (
                        <XCircle className="w-6 h-6 text-red-600 mt-0.5" />
                      )}
                      <div className="flex-1">
                        <p className="font-medium">
                          {lastGradeResult.outcome === 'success' && 'Correct!'}
                          {lastGradeResult.outcome === 'partial' && 'Partially Correct'}
                          {lastGradeResult.outcome === 'fail' && 'Incorrect'}
                        </p>
                        <p className="text-sm mt-1">{lastGradeResult.explanation_for_user}</p>
                        <p className="text-xs text-muted-foreground mt-2">
                          Next review: {new Date(lastGradeResult.next_review_eta).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                  </motion.div>
                )}
              </CardContent>

              <CardFooter className="flex justify-between">
                <Button
                  variant="outline"
                  onClick={handlePrevious}
                  disabled={currentItemIndex === 0}
                >
                  <ChevronLeft className="w-4 h-4 mr-1" />
                  Previous
                </Button>

                {!showAnswer ? (
                  <Button
                    onClick={handleSubmit}
                    disabled={!userAnswer.trim() || isLoading}
                  >
                    Submit Answer
                  </Button>
                ) : (
                  <Button
                    onClick={handleNext}
                    disabled={currentItemIndex === dueItems.length - 1}
                  >
                    Next
                    <ChevronRight className="w-4 h-4 ml-1" />
                  </Button>
                )}
              </CardFooter>
            </Card>
          </motion.div>
        </AnimatePresence>

        {/* Error display */}
        {error && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mt-4 p-4 bg-destructive/10 text-destructive rounded-lg"
          >
            {error}
          </motion.div>
        )}
      </div>
    </div>
  )
}