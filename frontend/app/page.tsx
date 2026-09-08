'use client';

import { useState } from 'react';
import QueryBar from '@/components/QueryBar';
import RecommendationCard from '@/components/RecommendationCard';
import { QueryResponse, clearSession } from '@/lib/api';

interface Turn {
  question: string;
  result: QueryResponse;
}

export default function Home() {
  const [turns, setTurns] = useState<Turn[]>([]);

  const handleResult = (question: string, result: QueryResponse) => {
    setTurns((prev) => [...prev, { question, result }]);
  };

  const handleNewConversation = async () => {
    await clearSession();
    setTurns([]);
  };

  return (
    <main className="min-h-screen bg-gray-50">
      <header className="bg-red-700 text-white py-6 px-8">
        <div className="max-w-2xl mx-auto flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">TerrierLife AI</h1>
            <p className="text-red-200 mt-1">Your smart BU campus assistant</p>
          </div>
          {turns.length > 0 && (
            <button
              onClick={handleNewConversation}
              className="text-sm bg-red-800 hover:bg-red-900 px-3 py-2 rounded-lg transition whitespace-nowrap"
            >
              New conversation
            </button>
          )}
        </div>
      </header>

      <div className="max-w-2xl mx-auto py-12 px-4">
        <QueryBar onResult={handleResult} />

        {turns.length > 0 && (
          <>
            <p className="text-xs text-gray-500 mb-3">
              Follow-up questions remember this conversation — try &ldquo;what about closer to
              Questrom?&rdquo;
            </p>
            <div className="flex flex-col gap-4">
              {turns.map((turn, i) => (
                <div key={i}>
                  <p className="text-sm text-gray-500 mb-2 px-1">You asked: {turn.question}</p>
                  <RecommendationCard
                    response={turn.result.response}
                    type={turn.result.type}
                    toolCalls={turn.result.tool_calls}
                  />
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </main>
  );
}
