#input_type_name: DbQueryInput
#output_type_name: DbQueryOutput
#function_name: db-query-bridge

import os
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from lemma_sdk import FunctionContext

class DbQueryInput(BaseModel):
    type: str

class DbQueryOutput(BaseModel):
    status: Optional[str] = None
    data: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None

async def db_query_bridge(ctx: FunctionContext, data: DbQueryInput) -> DbQueryOutput:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    try:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            return DbQueryOutput(error="DATABASE_URL not found in environment.")

        event_type = data.type
        if not event_type:
            return DbQueryOutput(error="Missing 'type' in event payload. Expected 'critical_anomalies' or 'recent_slack'.")

        conn = psycopg2.connect(db_url)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        if event_type == "critical_anomalies":
            query = "SELECT * FROM incident_telemetry ORDER BY timestamp DESC LIMIT 10;"
        elif event_type == "recent_slack":
            query = "SELECT * FROM slack_messages ORDER BY timestamp DESC LIMIT 10;"
        else:
            return DbQueryOutput(error=f"Unknown event type '{event_type}'. Expected 'critical_anomalies' or 'recent_slack'.")

        cursor.execute(query)
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        results = []
        for row in rows:
            record = dict(row)
            if 'timestamp' in record and record['timestamp']:
                record['timestamp'] = record['timestamp'].isoformat()
            if 'text_embedding' in record and record['text_embedding']:
                record['text_embedding'] = str(record['text_embedding'])
            results.append(record)

        return DbQueryOutput(status="success", data=results)

    except Exception as e:
        return DbQueryOutput(error=str(e))
