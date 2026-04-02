import axios from 'axios';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface QueryRequest {
  message: string;
  location?: string;
  time_available?: number;
  interests?: string[];
}

export interface QueryResponse {
  response: string;
  type: 'places' | 'resource' | 'events' | 'time_assistant';
}

export async function sendQuery(req: QueryRequest): Promise<QueryResponse> {
  const { data } = await axios.post(`${API_BASE}/api/query`, req);
  return data;
}
