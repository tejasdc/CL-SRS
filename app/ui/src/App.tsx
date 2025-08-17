import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { BookOpen, Plus, GitBranch, Menu, X } from 'lucide-react'
import { ReviewScreen } from '@/components/ReviewScreen'
import { InputScreen } from '@/components/InputScreen'
import { GraphScreen } from '@/components/GraphScreen'
import { cn } from '@/lib/utils'

type Screen = 'review' | 'input' | 'graph'

function App() {
  const [currentScreen, setCurrentScreen] = useState<Screen>('review')
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const navigationItems = [
    { id: 'review', label: 'Review', icon: BookOpen },
    { id: 'input', label: 'Add Content', icon: Plus },
    { id: 'graph', label: 'Knowledge Graph', icon: GitBranch },
  ]

  const renderScreen = () => {
    switch (currentScreen) {
      case 'review':
        return <ReviewScreen />
      case 'input':
        return <InputScreen />
      case 'graph':
        return <GraphScreen />
      default:
        return <ReviewScreen />
    }
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Navigation Bar */}
      <nav className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <div className="flex items-center">
              <h1 className="text-xl font-bold bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
                CL-SRS
              </h1>
            </div>

            {/* Desktop Navigation */}
            <div className="hidden md:flex items-center space-x-1">
              {navigationItems.map((item) => {
                const Icon = item.icon
                const isActive = currentScreen === item.id
                
                return (
                  <button
                    key={item.id}
                    onClick={() => setCurrentScreen(item.id as Screen)}
                    className={cn(
                      "flex items-center gap-2 px-4 py-2 rounded-lg transition-all",
                      isActive 
                        ? "bg-primary text-primary-foreground" 
                        : "hover:bg-muted text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <Icon className="w-4 h-4" />
                    <span className="font-medium">{item.label}</span>
                  </button>
                )
              })}
            </div>

            {/* Mobile menu button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 rounded-lg hover:bg-muted"
            >
              {mobileMenuOpen ? (
                <X className="w-5 h-5" />
              ) : (
                <Menu className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>

        {/* Mobile Navigation */}
        <AnimatePresence>
          {mobileMenuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="md:hidden border-t"
            >
              <div className="px-4 py-2 space-y-1">
                {navigationItems.map((item) => {
                  const Icon = item.icon
                  const isActive = currentScreen === item.id
                  
                  return (
                    <button
                      key={item.id}
                      onClick={() => {
                        setCurrentScreen(item.id as Screen)
                        setMobileMenuOpen(false)
                      }}
                      className={cn(
                        "flex items-center gap-2 w-full px-4 py-2 rounded-lg transition-all",
                        isActive 
                          ? "bg-primary text-primary-foreground" 
                          : "hover:bg-muted text-muted-foreground hover:text-foreground"
                      )}
                    >
                      <Icon className="w-4 h-4" />
                      <span className="font-medium">{item.label}</span>
                    </button>
                  )
                })}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </nav>

      {/* Main Content */}
      <main>
        <AnimatePresence mode="wait">
          <motion.div
            key={currentScreen}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.2 }}
          >
            {renderScreen()}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  )
}

export default App