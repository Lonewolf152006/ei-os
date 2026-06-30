import { NextResponse } from 'next/server'
export const maxDuration = 60;

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const res = await fetch(`${API_URL}/remediate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        root_cause: body.root_cause,
        suggested_fix: body.suggested_fix,
      }),
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
