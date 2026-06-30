'use client'

import { useState, useEffect } from 'react'

/* ─── Types ─── */
interface Step {
  step: number
  event_title: string
  source: string
  occurred_at: string
  finding: string
}

interface JiraTicket {
  title: string
  description: string
  priority: string
  labels: string[]
}

interface QueryResult {
  question: string
  reasoning_steps: Step[]
  root_cause: string
  suggested_fix: string
  confidence: string
  savings: string
  jira_ticket: JiraTicket
  generated_at: string
}

interface Stats {
  total_events: number
  total_edges: number
  sources: { github: number; slack: number; complaints: number }
  avg_compression: number
  compression_breakdown?: { github: number; slack: number; complaints: number }
  total_tokens_saved?: number
  query_history?: any[]
  total_remediations?: number
}

const SOURCE_STYLES: Record<string, string> = {
  'github':      'text-orange-400',
  'GITHUB_PR':   'text-orange-400', 
  'slack':       'text-purple-400',
  'SLACK_MESSAGE': 'text-purple-400',
  'complaints':  'text-red-400',
  'COMPLAINT':   'text-red-400',
}

const SOURCE_LABELS: Record<string, string> = {
  'github':        'GITHUB_PR',
  'GITHUB_PR':     'GITHUB_PR',
  'slack':         'SLACK_MESSAGE',
  'SLACK_MESSAGE': 'SLACK_MESSAGE',
  'complaints':    'COMPLAINT',
  'COMPLAINT':     'COMPLAINT',
}

/* ─── Main Page ─── */
export default function Dashboard() {
  const [question, setQuestion] = useState('')
  const [isQuerying, setIsQuerying] = useState(false)
  const [result, setResult] = useState<QueryResult | null>(null)
  const [stats, setStats] = useState<Stats | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isIngesting, setIsIngesting] = useState(false)
  const [lastFetch, setLastFetch] = useState<string | null>(null)
  const [isRemediating, setIsRemediating] = useState(false)
  const [prUrl, setPrUrl] = useState<string | null>(null)
  const [remediateError, setRemediateError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/stats')
      .then(r => r.json())
      .then(data => {
        if (!data.error) setStats(data)
      })
      .catch(() => {})
  }, [])

  const handleQuery = async () => {
    if (!question.trim() || isQuerying) return
    setIsQuerying(true)
    setError(null)
    setResult(null)

    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      if (!res.ok) {
        const err = await res.json()
        setError(err.detail || err.error || 'Something went wrong')
      } else {
        const data = await res.json()
        setResult(data)
        fetch('/api/stats').then(r => r.json()).then(d => {
          if (!d.error) setStats(d)
        })
      }
    } catch {
      setError('Cannot connect to the API server.')
    }
    setIsQuerying(false)
  }

  const handleIngest = async () => {
    setIsIngesting(true)
    try {
      await fetch('/api/ingest', { method: 'POST' })
      const s = await fetch('/api/stats').then(r => r.json())
      if (!s.error) setStats(s)
      setLastFetch(new Date().toLocaleTimeString('en-IN'))
    } catch {
      // silently fail
    }
    setIsIngesting(false)
  }

  const handleRemediate = async () => {
    if (!result || isRemediating) return
    setIsRemediating(true)
    setPrUrl(null)
    setRemediateError(null)
    try {
      const res = await fetch('/api/remediate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          root_cause: result.root_cause,
          suggested_fix: result.suggested_fix,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        setRemediateError(data.detail || 'Remediation failed')
      } else {
        setPrUrl(data.pr_url)
      }
    } catch {
      setRemediateError('Cannot connect to the API server.')
    }
    setIsRemediating(false)
  }

  return (
    <div className="min-h-screen bg-black text-white font-sans selection:bg-white selection:text-black">
      
      {/* 1. Top Navigation */}
      <header className="flex items-center justify-between px-6 lg:px-12 h-14 bg-transparent border-b border-[#262626]">
        <div className="text-xs font-mono uppercase tracking-[0.15em]">
          MENU
        </div>
        <div className="text-sm uppercase tracking-[0.2em] font-sans">
          EI-OS
        </div>
        <div className="text-right">
          {stats ? (
            <span className="text-xs text-gray-600 font-mono 
                             tracking-widest">
              {stats.total_events} EVENTS 
              &nbsp;·&nbsp; 
              {stats.total_edges} EDGES 
              &nbsp;·&nbsp; 
              {Math.round((stats.avg_compression || 0) * 100)}% COMPRESSED
            </span>
          ) : (
            <span className="text-xs text-gray-700 font-mono 
                             tracking-widest animate-pulse">
              CONNECTING...
            </span>
          )}
        </div>
      </header>

      <div className="h-px bg-gradient-to-r from-transparent 
                      via-amber-500/40 to-transparent" />

      {/* 2. Hero Search Band */}
      <section className="w-full py-32 px-6 flex flex-col items-center border-b border-[#262626]">
        <h1 className="text-5xl md:text-6xl uppercase tracking-[0.1em] font-sans text-center mb-16 leading-[1.1]">
          ENTERPRISE INTELLIGENCE
        </h1>
        
        <div className="w-full max-w-3xl flex flex-col md:flex-row gap-8 items-center">
          <input
            type="text"
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleQuery()}
            placeholder="Why did our cloud costs spike this month?"
            className="flex-1 w-full bg-transparent border-0 border-b border-white/20 focus:border-white focus:ring-0 text-lg text-white font-serif px-0 py-3 rounded-none placeholder-[#666666] transition-colors outline-none"
            id="query-input"
          />
          <button
            onClick={handleQuery}
            disabled={isQuerying || !question.trim()}
            className="px-8 py-3 rounded-full bg-transparent border border-white text-white uppercase font-mono tracking-[0.15em] text-sm hover:bg-[#141414] transition-colors disabled:opacity-30 disabled:cursor-not-allowed whitespace-nowrap flex items-center justify-center min-w-[160px]"
            id="analyze-button"
          >
            {isQuerying ? 'ANALYZING...' : 'ANALYZE'}
          </button>
        </div>
      </section>

      <main className="max-w-6xl mx-auto px-6 lg:px-12 py-24 space-y-32">

        {/* Results */}
        {result && !isQuerying && (
          <div className="space-y-32" id="results-container">
            
            {/* Root Cause & Fix */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-12 border-b border-[#262626] pb-24" id="result-summary">
              <div>
                <p className="text-[11px] uppercase tracking-[0.15em] text-[#999999] mb-4 font-mono">
                  ROOT CAUSE
                </p>
                <h2 className="text-2xl md:text-3xl tracking-[0.05em] uppercase leading-[1.3] font-sans">
                  {result.root_cause}
                </h2>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-[0.15em] text-[#999999] mb-4 font-mono">
                  SUGGESTED FIX
                </p>
                <p className="text-lg font-serif text-[#cccccc] leading-[1.5]">
                  {result.suggested_fix}
                </p>
                
                <div className="grid grid-cols-2 gap-8 mt-12 pt-12 border-t border-[#262626]">
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.15em] text-[#999999] mb-2 font-mono">
                      IMPACT
                    </p>
                    <p className="text-xl tracking-[0.05em] uppercase font-sans">
                      {result.savings}
                    </p>
                  </div>
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.15em] text-[#999999] mb-2 font-mono">
                      CONFIDENCE
                    </p>
                    <p className="text-xl tracking-[0.05em] uppercase font-mono">
                      {result.confidence}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Jira Ticket */}
            <div className="bg-[#141414] p-8 md:p-12 border-0 rounded-none">
              <div className="flex justify-between items-start mb-8">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.15em] text-[#999999] mb-2 font-mono">
                    ACTION ITEM
                  </p>
                  <h3 className="text-2xl tracking-[0.05em] uppercase font-sans">
                    {result.jira_ticket.title}
                  </h3>
                </div>
                <span className="text-[11px] uppercase tracking-[0.15em] font-mono text-[#cccccc] px-4 py-2 border border-[#3a3a3a]">
                  {result.jira_ticket.priority}
                </span>
              </div>
              <div className="mb-8">
                {result.jira_ticket.description.split('\n').map((line, i) => {
                  if (!line.trim()) return <div key={i} className="h-2" />
                  const boldLine = line.replace(
                    /\*\*(.*?)\*\*/g, 
                    '<strong>$1</strong>'
                  )
                  const bulletLine = boldLine.startsWith('- ')
                    ? '• ' + boldLine.slice(2)
                    : boldLine
                  return (
                    <p
                      key={i}
                      className="text-sm text-gray-300 leading-relaxed"
                      dangerouslySetInnerHTML={{ __html: bulletLine }}
                    />
                  )
                })}
              </div>
              <div className="flex gap-4">
                {result.jira_ticket.labels.map(label => (
                  <span key={label} className="text-[11px] uppercase tracking-[0.15em] text-[#666666] font-mono">
                    #{label}
                  </span>
                ))}
              </div>

              {/* ── AUTO-REMEDIATION PANEL ── */}
              <div className="mt-10 pt-10 border-t border-[#3a3a3a]">
                <div className="flex flex-col sm:flex-row gap-4 items-start">
                  <button
                    id="auto-draft-pr-button"
                    onClick={handleRemediate}
                    disabled={isRemediating}
                    className="px-6 py-3 bg-white text-black font-mono text-xs tracking-[0.2em] uppercase border-0 rounded-none hover:bg-[#e0e0e0] active:bg-[#c0c0c0] transition-colors disabled:bg-[#444] disabled:text-[#888] disabled:cursor-not-allowed whitespace-nowrap"
                  >
                    {isRemediating ? 'WRITING CODE...' : 'AUTO-DRAFT GITHUB PR'}
                  </button>
                  {prUrl && (
                    <a
                      href={prUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      id="pr-url-link"
                      className="font-mono text-xs text-[#aaaaaa] hover:text-white tracking-widest uppercase underline underline-offset-4 decoration-[#444] hover:decoration-white transition-colors break-all self-center"
                    >
                      ↗ {prUrl.replace('https://github.com/', '')}
                    </a>
                  )}
                </div>
                {remediateError && (
                  <p className="mt-3 text-[11px] font-mono uppercase tracking-widest text-[#d4a017]">
                    {remediateError}
                  </p>
                )}
              </div>
            </div>

            {/* Reasoning Trace */}
            <div>
              <p className="text-[11px] uppercase tracking-[0.15em] text-[#999999] mb-12 font-mono">
                CAUSAL CHAIN ({result.reasoning_steps.length} EVENTS)
              </p>
              <div className="space-y-0">
                {result.reasoning_steps.map((step, i) => (
                  <div key={i} className="py-8 border-b border-[#262626] flex flex-col md:flex-row gap-8 md:gap-16 items-start">
                    <div className="w-16 shrink-0 text-3xl font-sans text-[#666666]">
                      0{step.step}
                    </div>
                    <div className="flex-1">
                      <h4 className="text-xl tracking-[0.05em] uppercase mb-4 font-sans">
                        {step.event_title}
                      </h4>
                      <p className="text-base font-serif text-[#cccccc] leading-[1.5]">
                        {step.finding}
                      </p>
                    </div>
                    <div className="w-full md:w-48 shrink-0 text-right">
                      <div className="mb-1">
                        <span className={`text-xs font-mono tracking-widest
                          ${SOURCE_STYLES[step.source] || 'text-gray-500'}`}>
                          {SOURCE_LABELS[step.source] || step.source.toUpperCase()}
                        </span>
                      </div>
                      <p className="text-[11px] uppercase tracking-[0.15em] text-[#666666] font-mono">
                        {step.occurred_at}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-[#141414] p-8 border border-[#3a3a3a]">
            <p className="text-[11px] uppercase tracking-[0.15em] text-[#d4a017] mb-2 font-mono">
              SYSTEM FAULT
            </p>
            <p className="text-base font-serif text-[#cccccc]">{error}</p>
          </div>
        )}

        {/* Stats */}
        {stats && !result && !isQuerying && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-x-8 gap-y-16">
            <div className="border-t border-[#262626] pt-6">
              <p className="text-3xl tracking-[0.05em] uppercase mb-2 font-sans">
                {stats.total_events}
              </p>
              <p className="text-[11px] uppercase tracking-[0.15em] text-[#999999] font-mono">
                EVENTS INGESTED
              </p>
            </div>
            <div className="border-t border-[#262626] pt-6">
              <p className="text-3xl tracking-[0.05em] uppercase mb-2 font-sans">
                {stats.total_edges}
              </p>
              <p className="text-[11px] uppercase tracking-[0.15em] text-[#999999] font-mono">
                GRAPH EDGES
              </p>
            </div>
            <div className="border-t border-[#262626] pt-6">
              <p className="text-3xl tracking-[0.05em] uppercase mb-2 font-sans">
                {Math.round(stats.avg_compression * 100)}%
              </p>
              <p className="text-[11px] uppercase tracking-[0.15em] text-[#999999] font-mono">
                AVG COMPRESSION
              </p>
            </div>
            <div className="border-t border-[#262626] pt-6">
              <p className="text-3xl tracking-[0.05em] uppercase mb-2 font-sans">
                {stats.sources.github}
              </p>
              <p className="text-[11px] uppercase tracking-[0.15em] text-[#999999] font-mono">
                GITHUB PRS
              </p>
            </div>
            <div className="border-t border-[#262626] pt-6">
              <p className="text-3xl tracking-[0.05em] uppercase mb-2 font-sans">
                {stats.total_remediations || 0}
              </p>
              <p className="text-[11px] uppercase tracking-[0.15em] text-[#999999] font-mono">
                PRs auto-drafted
              </p>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-black border-t border-[#262626] py-16 px-6 lg:px-12 mt-32">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-center gap-8">
          <div className="text-[14px] uppercase tracking-[0.2em] font-sans text-[#666666]">
            EI-OS
          </div>
          <p className="text-[14px] font-serif text-[#666666]">
            Enterprise Intelligence Operating System v1.0
          </p>
        </div>
      </footer>
    </div>
  )
}
