import axios from 'axios';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface QueryRequest {
  message: string;
  location?: string;
  time_available?: number;
  interests?: string[];
  session_id?: string;
}

export interface ToolCall {
  tool: string;
  args: Record<string, unknown>;
}

export interface QueryResponse {
  response: string;
  type: 'places' | 'resource' | 'events' | 'time_assistant';
  tool_calls?: ToolCall[];
}

const SESSION_KEY = 'terrierlife_session_id';

/**
 * Stable per-browser session id, so follow-up questions resolve against
 * earlier turns. Falls back to a throwaway id when storage is unavailable
 * (private windows, blocked site data) — the request still works, it just
 * won't carry history.
 */
export function getSessionId(): string {
  try {
    let id = localStorage.getItem(SESSION_KEY);
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem(SESSION_KEY, id);
    }
    return id;
  } catch {
    return crypto.randomUUID();
  }
}

export async function clearSession(): Promise<void> {
  try {
    const id = localStorage.getItem(SESSION_KEY);
    if (id) {
      await axios.delete(`${API_BASE}/api/query/history/${id}`);
      localStorage.removeItem(SESSION_KEY);
    }
  } catch {
    // Clearing is best-effort; a failure here shouldn't block the user.
  }
}

export async function sendQuery(req: QueryRequest): Promise<QueryResponse> {
  const { data } = await axios.post(`${API_BASE}/api/query`, {
    ...req,
    session_id: req.session_id ?? getSessionId(),
  });
  return data;
}
