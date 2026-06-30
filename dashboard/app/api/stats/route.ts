import { NextResponse } from 'next/server'
export const maxDuration = 60;

export async function GET() {
  try {
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const res = await fetch(`${API_URL}/stats`, {
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
