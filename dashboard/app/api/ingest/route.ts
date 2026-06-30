import { NextResponse } from 'next/server'

export async function POST() {
  try {
    const res = await fetch('http://localhost:8000/ingest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
    if (!res.ok) {
      const err = await res.json()
      return NextResponse.json(err, { status: res.status })
    }
    const data = await res.json()
    return NextResponse.json(data)
  } catch {
    return NextResponse.json(
      { error: 'Cannot connect to API server.' },
      { status: 502 }
    )
  }
}
