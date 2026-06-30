"""
Token Reducer Proxy — 3-pass compression pipeline.

Pass 1: Clean (strip noise, normalize whitespace, remove boilerplate)
Pass 2: TF-IDF sentence scoring (keep top-K informative sentences)
Pass 3: Entity extraction (pull named entities for knowledge graph)

Usage:
    python token_reducer/proxy.py
"""

import re
import math
from collections import Counter


# ──────────────────────────────────────────────────────
# Pass 1: Cleaning
# ──────────────────────────────────────────────────────

def clean_text(raw: str) -> str:
    """Strip noise, normalize whitespace, remove boilerplate patterns."""
    text = raw.strip()
    # Collapse multiple newlines / whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    # Remove common boilerplate
    boilerplate = [
        r'<!--.*?-->',                      # HTML comments
        r'Signed-off-by:.*',                # Git sign-offs
        r'Co-authored-by:.*',               # Co-author tags
        r'https?://\S+',                    # URLs (captured separately in entities)
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # emails
    ]
    for pattern in boilerplate:
        text = re.sub(pattern, '', text, flags=re.DOTALL)
    # Final whitespace cleanup
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()


# ──────────────────────────────────────────────────────
# Pass 2: TF-IDF Sentence Scoring
# ──────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Simple word tokenizer."""
    return re.findall(r'\b[a-z][a-z0-9_]*\b', text.lower())


def _sentence_split(text: str) -> list[str]:
    """Split text into sentences."""
    sentences = re.split(r'(?<=[.!?])\s+|\n\n', text)
    return [s.strip() for s in sentences if len(s.strip()) > 10]


def tfidf_compress(text: str, keep_ratio: float = 0.4) -> tuple[str, list[float]]:
    """
    Score sentences by TF-IDF relevance and keep the top ones.
    Returns (compressed_text, scores).
    """
    sentences = _sentence_split(text)
    if len(sentences) <= 2:
        return text, [1.0] * len(sentences)

    # Compute term frequency per sentence
    doc_freq = Counter()
    sent_tokens = []
    for sent in sentences:
        tokens = set(_tokenize(sent))
        sent_tokens.append(tokens)
        for t in tokens:
            doc_freq[t] += 1

    n_docs = len(sentences)
    scores = []
    for tokens in sent_tokens:
        score = 0.0
        for t in tokens:
            tf = 1  # binary TF
            idf = math.log((n_docs + 1) / (doc_freq[t] + 1)) + 1
            score += tf * idf
        # Normalize by sentence length to avoid long-sentence bias
        scores.append(score / max(len(tokens), 1))

    # Keep top-K sentences (in original order)
    n_keep = max(2, int(len(sentences) * keep_ratio))
    threshold = sorted(scores, reverse=True)[min(n_keep - 1, len(scores) - 1)]
    kept = [s for s, sc in zip(sentences, scores) if sc >= threshold]

    return '\n'.join(kept[:n_keep]), scores


# ──────────────────────────────────────────────────────
# Pass 3: Entity Extraction
# ──────────────────────────────────────────────────────

# Patterns that commonly indicate named entities in engineering text
ENTITY_PATTERNS = [
    (r'\b(?:PR|pr)\s*#?\d+', 'PULL_REQUEST'),
    (r'\b(?:JIRA|TICKET)-\d+', 'TICKET'),
    (r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)+\b', 'PERSON_OR_PROPER'),
    (r'\b(?:users?_\w+|documents?_\w+|\w+_table)\b', 'DB_TABLE'),
    (r'\b(?:GET|POST|PUT|DELETE|PATCH)\s+/\S+', 'API_ENDPOINT'),
    (r'\b\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}Z?)?\b', 'TIMESTAMP'),
    (r'\b(?:SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)\s', 'SQL_KEYWORD'),
    (r'\b(?:timeout|latency|OOM|crash|error|exception|5\d{2})\b', 'INCIDENT_SIGNAL'),
    (r'\b(?:v\d+\.\d+(?:\.\d+)?)\b', 'VERSION'),
    (r'\b[a-z_]+\.(?:py|js|ts|sql|json|csv)\b', 'FILE_REF'),
]


def extract_entities(text: str) -> list[dict]:
    """
    Extract named entities from text using pattern matching.
    Returns list of {value, type, span} dicts.
    """
    entities = []
    seen = set()
    for pattern, etype in ENTITY_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            val = match.group().strip()
            key = (val.lower(), etype)
            if key not in seen:
                seen.add(key)
                entities.append({
                    'value': val,
                    'type': etype,
                    'span': (match.start(), match.end()),
                })
    return entities


# ──────────────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────────────

def reduce(raw_text: str, keep_ratio: float = 0.4) -> dict:
    """
    Full 3-pass reduction pipeline.
    Returns dict with cleaned, compressed, entities, and stats.
    """
    # Pass 1
    cleaned = clean_text(raw_text)
    # Pass 2
    compressed, scores = tfidf_compress(cleaned, keep_ratio)
    # Pass 3
    entities = extract_entities(cleaned)

    original_tokens = len(raw_text.split())
    compressed_tokens = len(compressed.split())
    ratio = (1 - compressed_tokens / max(original_tokens, 1)) * 100

    return {
        'cleaned': cleaned,
        'compressed': compressed,
        'entities': entities,
        'stats': {
            'original_tokens': original_tokens,
            'compressed_tokens': compressed_tokens,
            'reduction_ratio': round(ratio, 1),
            'entities_found': len(entities),
        }
    }


class _TokenReducerProxyResult:
    def __init__(self, original_tokens, reduction_ratio, entities, compressed_text):
        self.original_tokens = original_tokens
        self.reduction_ratio = reduction_ratio
        self.entities = entities
        self.compressed_text = compressed_text

class TokenReducerProxy:
    def __init__(self, compression_ratio=0.4):
        self.compression_ratio = compression_ratio

    def reduce(self, raw_text: str, source: str = None):
        res_dict = reduce(raw_text, self.compression_ratio)
        return _TokenReducerProxyResult(
            original_tokens=res_dict['stats']['original_tokens'],
            reduction_ratio=res_dict['stats']['reduction_ratio'] / 100.0,
            entities=res_dict['entities'],
            compressed_text=res_dict['compressed']
        )


# ──────────────────────────────────────────────────────
# Demo / self-test
# ──────────────────────────────────────────────────────

SAMPLE_INPUT = """
PR #218 — Add user activity logging

This pull request introduces a new `users_activity` table that records all document
reads and writes across the Folio platform. Every API call that touches a document
will now emit an activity row.

Changes:
- Created migration 042_add_users_activity.sql with columns: id, user_id, document_id,
  action_type (READ|WRITE), timestamp, metadata JSONB.
- Added three new queries to the documents service:
  1. INSERT into users_activity on every GET /api/v2/documents/:id
  2. INSERT into users_activity on every PUT /api/v2/documents/:id
  3. Batch INSERT for bulk export operations via POST /api/v2/documents/export
- Updated the DocumentService class to call ActivityLogger.log() after each operation.
- Added unit tests covering read logging, write logging, and bulk operations.

Signed-off-by: Priya Sharma <priya@folio.dev>
Co-authored-by: Jake Torres <jake@folio.dev>

Note: No schema-level indexes were added for the activity table — we will evaluate
query patterns in production before optimizing.

Reviewers: @sarah_chen @dev_lead
Merged: 2026-06-22T23:22:00Z
"""


def main():
    """Run the 3-pass pipeline on sample PR text and print results."""
    print("=" * 60)
    print("  TOKEN REDUCER PROXY — 3-Pass Compression Demo")
    print("=" * 60)

    result = reduce(SAMPLE_INPUT)
    stats = result['stats']

    print(f"\n📊  Compression Stats")
    print(f"    Original tokens:   {stats['original_tokens']}")
    print(f"    Compressed tokens: {stats['compressed_tokens']}")
    print(f"    Reduction ratio:   {stats['reduction_ratio']}%")
    print(f"    Entities found:    {stats['entities_found']}")

    print(f"\n🔗  Extracted Entities:")
    for ent in result['entities']:
        print(f"    [{ent['type']:20s}]  {ent['value']}")

    print(f"\n📝  Compressed Output:")
    print("-" * 60)
    for line in result['compressed'].split('\n'):
        print(f"    {line}")
    print("-" * 60)

    print(f"\n✅  Pipeline OK — reduction ratio: {stats['reduction_ratio']}%")
    return result


if __name__ == '__main__':
    main()
