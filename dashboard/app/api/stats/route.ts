import { NextResponse } from 'next/server'

export async function GET() {
  try {
    const res = await fetch('http://localhost:8000/stats', {
      cache: 'no-store',
    })
    if (!res.ok) {
      return NextResponse.json({ error: 'API unavailable' }, { status: 502 })
    }
    const data = await res.json()
    return NextResponse.json(data)
  } catch {
    return NextResponse.json(
      { error: 'Cannot connect to API server. Is it running on :8000?' },
      { status: 502 }
    )
  }
}
