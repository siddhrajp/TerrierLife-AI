interface Props {
  response: string;
  type: 'places' | 'resource' | 'events' | 'time_assistant';
}

const TYPE_LABELS: Record<Props['type'], string> = {
  places: 'Place Finder',
  resource: 'BU Resource Copilot',
  events: 'Event Recommendations',
  time_assistant: 'Time Between Classes',
};

const TYPE_COLORS: Record<Props['type'], string> = {
  places: 'bg-blue-50 border-blue-200 text-blue-700',
  resource: 'bg-green-50 border-green-200 text-green-700',
  events: 'bg-purple-50 border-purple-200 text-purple-700',
  time_assistant: 'bg-amber-50 border-amber-200 text-amber-700',
};

export default function RecommendationCard({ response, type }: Props) {
  return (
    <div className="bg-white rounded-xl shadow-md p-6 mb-6">
      <div className="flex items-center gap-2 mb-4">
        <span className={`text-xs font-semibold px-2 py-1 rounded-full border ${TYPE_COLORS[type]}`}>
          {TYPE_LABELS[type]}
        </span>
      </div>
      <div className="text-gray-800 whitespace-pre-wrap leading-relaxed">{response}</div>
    </div>
  );
}
