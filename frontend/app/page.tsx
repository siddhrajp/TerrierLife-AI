'use client';

import { useState } from 'react';
import QueryBar from '@/components/QueryBar';
import RecommendationCard from '@/components/RecommendationCard';
import { QueryResponse } from '@/lib/api';

export default function Home() {
  const [result, setResult] = useState<QueryResponse | null>(null);

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-red-700 text-white py-6 px-8">
        <h1 className="text-3xl font-bold">TerrierLife AI</h1>
        <p className="text-red-200 mt-1">Your smart BU campus assistant</p>
      </header>

      <div className="max-w-2xl mx-auto py-12 px-4">
        <QueryBar onResult={setResult} />

        {result && (
          <RecommendationCard response={result.response} type={result.type} />
        )}
      </div>
    </main>
  );
}
