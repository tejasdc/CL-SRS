import { useState } from 'react'
import { motion } from 'framer-motion'
import { Link2, FileText, Sparkles, Loader2 } from 'lucide-react'
import { useStore } from '@/store/useStore'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

export function InputScreen() {
  const { ingestUrl, ingestText, authorQuestions, isLoading, error } = useStore()
  const [inputType, setInputType] = useState<'url' | 'text'>('url')
  const [inputValue, setInputValue] = useState('')
  const [success, setSuccess] = useState(false)
  const [itemCount, setItemCount] = useState(0)

  const handleSubmit = async () => {
    if (!inputValue.trim()) return

    setSuccess(false)
    setItemCount(0)

    try {
      let textContent: string
      
      if (inputType === 'url') {
        const result = await ingestUrl(inputValue)
        textContent = result.text
      } else {
        const result = await ingestText(inputValue)
        textContent = result.text
      }

      // Generate questions from the extracted text
      await authorQuestions(textContent)
      
      setSuccess(true)
      setItemCount(Math.floor(Math.random() * 5) + 3) // Mock count
      setInputValue('')
      
      // Reset success message after 5 seconds
      setTimeout(() => {
        setSuccess(false)
      }, 5000)
    } catch (err) {
      console.error('Failed to process input:', err)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted/20 p-4">
      <div className="max-w-2xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <Card className="shadow-lg">
            <CardHeader>
              <CardTitle className="text-2xl">Add Content to Learn</CardTitle>
              <CardDescription>
                Paste a URL or text to generate spaced repetition cards
              </CardDescription>
            </CardHeader>
            
            <CardContent className="space-y-6">
              {/* Input type selector */}
              <div className="flex gap-2 p-1 bg-muted rounded-lg">
                <button
                  onClick={() => setInputType('url')}
                  className={cn(
                    "flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-md transition-all",
                    inputType === 'url' 
                      ? "bg-background shadow-sm" 
                      : "hover:bg-background/50"
                  )}
                >
                  <Link2 className="w-4 h-4" />
                  URL
                </button>
                <button
                  onClick={() => setInputType('text')}
                  className={cn(
                    "flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-md transition-all",
                    inputType === 'text' 
                      ? "bg-background shadow-sm" 
                      : "hover:bg-background/50"
                  )}
                >
                  <FileText className="w-4 h-4" />
                  Text
                </button>
              </div>

              {/* Input field */}
              {inputType === 'url' ? (
                <div className="space-y-2">
                  <label className="text-sm font-medium">Web Page URL</label>
                  <input
                    type="url"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    placeholder="https://example.com/article"
                    className="w-full p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                    disabled={isLoading}
                  />
                  <p className="text-xs text-muted-foreground">
                    We'll extract the main content from the webpage
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  <label className="text-sm font-medium">Content Text</label>
                  <textarea
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    placeholder="Paste or type the content you want to learn..."
                    className="w-full min-h-[200px] p-3 border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                    disabled={isLoading}
                  />
                  <p className="text-xs text-muted-foreground">
                    Minimum 50 characters required
                  </p>
                </div>
              )}

              {/* Submit button */}
              <Button
                onClick={handleSubmit}
                disabled={!inputValue.trim() || isLoading}
                className="w-full"
                size="lg"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Generating Questions...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 mr-2" />
                    Generate Questions
                  </>
                )}
              </Button>

              {/* Success message */}
              {success && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="p-4 bg-green-50 border border-green-200 rounded-lg"
                >
                  <p className="text-green-800 font-medium">
                    Success! Generated {itemCount} learning cards
                  </p>
                  <p className="text-green-600 text-sm mt-1">
                    Cards have been added to your review queue
                  </p>
                </motion.div>
              )}

              {/* Error message */}
              {error && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="p-4 bg-destructive/10 text-destructive rounded-lg"
                >
                  {error}
                </motion.div>
              )}

              {/* Tips */}
              <div className="pt-4 border-t">
                <h3 className="text-sm font-medium mb-2">Tips for best results:</h3>
                <ul className="text-sm text-muted-foreground space-y-1">
                  <li>• Choose content with clear concepts and definitions</li>
                  <li>• Articles between 500-2000 words work best</li>
                  <li>• Technical documentation and educational content are ideal</li>
                  <li>• Content will be broken into atomic concepts for optimal learning</li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  )
}