import { useEffect, useRef, useState } from 'react'
import { Network, DataSet } from 'vis-network/standalone'
import { motion } from 'framer-motion'
import { Info, GitBranch } from 'lucide-react'
import { useStore } from '@/store/useStore'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { format } from 'date-fns'

interface ConceptNode {
  id: string
  title: string
  description: string
  stability_s?: number
  next_review_at?: string
  last_outcome?: string
}

export function GraphScreen() {
  const { concepts, fetchConcepts } = useStore()
  const networkRef = useRef<HTMLDivElement>(null)
  const [selectedNode, setSelectedNode] = useState<ConceptNode | null>(null)
  // const [network, setNetwork] = useState<Network | null>(null)

  useEffect(() => {
    fetchConcepts()
  }, [])

  useEffect(() => {
    if (networkRef.current && concepts.length > 0) {
      // Create nodes
      const nodes = new DataSet(
        concepts.map(concept => ({
          id: concept.id,
          label: concept.title,
          title: concept.description,
          color: getNodeColor(concept),
          font: { color: '#ffffff' },
          borderWidth: 2,
          borderWidthSelected: 3,
        }))
      )

      // Create edges from prerequisites and relations
      const edgeData: any[] = []
      concepts.forEach(concept => {
          
        // Add prerequisite edges
        if (concept.prereqs) {
          concept.prereqs.forEach(prereq => {
            edgeData.push({
              id: `${prereq}-${concept.id}`,
              from: prereq,
              to: concept.id,
              arrows: 'to',
              color: { color: '#94a3b8' },
              smooth: { type: 'curvedCW', roundness: 0.2 }
            })
          })
        }
        
        // Add contrast edges
        if (concept.relations) {
          concept.relations
            .filter(rel => rel.type === 'contrasts_with')
            .forEach(rel => {
              edgeData.push({
                id: `${concept.id}-${rel.concept_id}`,
                from: concept.id,
                to: rel.concept_id,
                dashes: true,
                color: { color: '#fbbf24' },
                smooth: { type: 'curvedCW', roundness: 0.2 }
              })
            })
        }
          
      })
      const edges = new DataSet(edgeData)

      const options = {
        physics: {
          enabled: true,
          solver: 'forceAtlas2Based',
          forceAtlas2Based: {
            gravitationalConstant: -50,
            centralGravity: 0.01,
            springLength: 100,
            springConstant: 0.08,
            damping: 0.4,
            avoidOverlap: 1
          },
          stabilization: {
            enabled: true,
            iterations: 100,
            updateInterval: 25
          }
        },
        interaction: {
          hover: true,
          tooltipDelay: 200,
          zoomView: true,
          dragView: true
        },
        nodes: {
          shape: 'dot',
          size: 20,
          font: {
            size: 14,
            strokeWidth: 3,
            strokeColor: '#000000'
          }
        },
        edges: {
          width: 2,
          smooth: {
            enabled: true,
            type: 'dynamic',
            roundness: 0.5
          }
        }
      }

      const net = new Network(networkRef.current, { nodes, edges }, options)
      
      // Handle node selection
      net.on('selectNode', (params) => {
        if (params.nodes.length > 0) {
          const nodeId = params.nodes[0]
          const concept = concepts.find(c => c.id === nodeId)
          if (concept) {
            setSelectedNode({
              id: concept.id,
              title: concept.title,
              description: concept.description,
              stability_s: concept.scheduler_state?.stability_s,
              next_review_at: concept.scheduler_state?.next_review_at,
              last_outcome: concept.scheduler_state?.last_outcome
            })
          }
        }
      })

      net.on('deselectNode', () => {
        setSelectedNode(null)
      })

      // setNetwork(net)

      return () => {
        net.destroy()
      }
    }
  }, [concepts])

  const getNodeColor = (concept: any) => {
    if (!concept.scheduler_state) return '#64748b' // slate-500
    
    const outcome = concept.scheduler_state.last_outcome
    if (outcome === 'success') return '#10b981' // emerald-500
    if (outcome === 'partial') return '#f59e0b' // amber-500
    if (outcome === 'fail') return '#ef4444' // red-500
    
    return '#3b82f6' // blue-500
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted/20 p-4">
      <div className="max-w-7xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="grid grid-cols-1 lg:grid-cols-3 gap-6"
        >
          {/* Graph visualization */}
          <div className="lg:col-span-2">
            <Card className="h-[600px] shadow-lg">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <GitBranch className="w-5 h-5" />
                  Knowledge Graph
                </CardTitle>
                <CardDescription>
                  Visualizing concept relationships and prerequisites
                </CardDescription>
              </CardHeader>
              <CardContent className="relative h-[calc(100%-5rem)]">
                <div ref={networkRef} className="w-full h-full" />
                
                {concepts.length === 0 && (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <p className="text-muted-foreground">
                      No concepts yet. Add content to see your knowledge graph.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Node details panel */}
          <div>
            <Card className="h-[600px] shadow-lg">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Info className="w-5 h-5" />
                  Concept Details
                </CardTitle>
              </CardHeader>
              <CardContent>
                {selectedNode ? (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="space-y-4"
                  >
                    <div>
                      <h3 className="font-semibold text-lg">{selectedNode.title}</h3>
                      <p className="text-sm text-muted-foreground mt-1">
                        {selectedNode.description}
                      </p>
                    </div>

                    <div className="space-y-2 pt-4 border-t">
                      {selectedNode.stability_s && (
                        <div className="flex justify-between text-sm">
                          <span className="text-muted-foreground">Stability:</span>
                          <span className="font-mono">
                            {selectedNode.stability_s.toFixed(1)} days
                          </span>
                        </div>
                      )}
                      
                      {selectedNode.next_review_at && (
                        <div className="flex justify-between text-sm">
                          <span className="text-muted-foreground">Next Review:</span>
                          <span>
                            {format(new Date(selectedNode.next_review_at), 'MMM d')}
                          </span>
                        </div>
                      )}
                      
                      {selectedNode.last_outcome && (
                        <div className="flex justify-between text-sm">
                          <span className="text-muted-foreground">Last Result:</span>
                          <span className={`capitalize font-medium ${
                            selectedNode.last_outcome === 'success' ? 'text-green-600' :
                            selectedNode.last_outcome === 'partial' ? 'text-yellow-600' :
                            'text-red-600'
                          }`}>
                            {selectedNode.last_outcome}
                          </span>
                        </div>
                      )}
                    </div>

                    <div className="pt-4 border-t">
                      <p className="text-xs text-muted-foreground">
                        Click on a concept to filter your next review session
                      </p>
                    </div>
                  </motion.div>
                ) : (
                  <div className="text-center text-muted-foreground">
                    <p>Select a concept node to view details</p>
                    <p className="text-sm mt-2">
                      • Solid arrows show prerequisites
                    </p>
                    <p className="text-sm">
                      • Dashed lines show contrasts
                    </p>
                    <p className="text-sm mt-3">
                      Node colors indicate performance:
                    </p>
                    <div className="flex justify-center gap-4 mt-2">
                      <span className="flex items-center gap-1">
                        <div className="w-3 h-3 rounded-full bg-green-500" />
                        <span className="text-xs">Success</span>
                      </span>
                      <span className="flex items-center gap-1">
                        <div className="w-3 h-3 rounded-full bg-yellow-500" />
                        <span className="text-xs">Partial</span>
                      </span>
                      <span className="flex items-center gap-1">
                        <div className="w-3 h-3 rounded-full bg-red-500" />
                        <span className="text-xs">Fail</span>
                      </span>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </motion.div>

        {/* Legend */}
        <Card className="mt-6 shadow-lg">
          <CardContent className="pt-6">
            <div className="flex flex-wrap items-center justify-center gap-6 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-12 h-0.5 bg-slate-400" />
                <span>Prerequisite</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-12 h-0.5 border-t-2 border-dashed border-yellow-500" />
                <span>Contrasts With</span>
              </div>
              <div className="text-muted-foreground">
                Zoom: Scroll | Pan: Drag | Select: Click
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}