'use client';

import { useState } from 'react';
import { sendQuery, QueryResponse } from '@/lib/api';

const EXAMPLE_PROMPTS = [
  'I have 25 mins before class near CDS, what should I do?',
  'Find me a quiet study spot near CAS with outlets',
  'How do I get resume help at BU?',
  'What events should I attend this week for AI?',
  'Where can I print something near GSU?',
  'What is OPT and how do I apply as an F-1 student?',
];

interface QueryBarProps {
  onResult: (response: QueryResponse) => void;
}

export default function QueryBar({ onResult }: QueryBarProps) {
  const [query, setQuery] = useState('');
  const [location, setLocation] = useState('');
  const [timeAvailable, setTimeAvailable] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError('');
    try {
      const result = await sendQuery({
        message: query,
        location: location || undefined,
        time_available: timeAvailable ? parseInt(timeAvailable) : undefined,
      });
      onResult(result);
    } catch {
      setError('Something went wrong. Is the backend running?');
    }
    setLoading(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      handleSubmit();
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-md p-6 mb-6">
      <textarea
        className="w-full border border-gray-300 rounded-lg p-3 text-lg resize-none focus:outline-none focus:ring-2 focus:ring-red-500"
        rows={3}
        placeholder="What do you need help with today?"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
      />

      <div className="flex gap-3 mt-3">
        <input
          className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
          placeholder="Current location (e.g. CDS, CAS, GSU)"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
        />
        <input
          className="w-36 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
          placeholder="Minutes free"
          type="number"
          min={1}
          value={timeAvailable}
          onChange={(e) => setTimeAvailable(e.target.value)}
        />
      </div>

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      <button
        className="mt-4 w-full bg-red-700 text-white py-3 rounded-lg font-semibold hover:bg-red-800 disabled:opacity-50 transition"
        onClick={handleSubmit}
        disabled={loading || !query.trim()}
      >
        {loading ? 'Thinking…' : 'Ask TerrierLife AI'}
      </button>

      <p className="text-xs text-gray-400 mt-2 text-center">Cmd+Enter to submit</p>

      <div className="mt-5">
        <p className="text-sm text-gray-500 mb-2">Try asking:</p>
        <div className="flex flex-col gap-2">
          {EXAMPLE_PROMPTS.map((p, i) => (
            <button
              key={i}
              className="text-left text-sm bg-white border border-gray-200 rounded-lg px-4 py-2 hover:bg-red-50 hover:border-red-300 transition"
              onClick={() => setQuery(p)}
            >
              "{p}"
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
