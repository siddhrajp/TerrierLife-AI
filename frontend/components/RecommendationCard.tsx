import { ToolCall } from '@/lib/api';

interface Props {
  response: string;
  type: 'places' | 'resource' | 'events' | 'time_assistant';
  toolCalls?: ToolCall[];
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

// What the agent actually did, in the student's terms rather than function names.
const TOOL_LABELS: Record<string, string> = {
  get_nearby_places: 'Searched campus places',
  search_bu_resource: 'Checked official BU resources',
  get_events: 'Looked up campus events',
};

export default function RecommendationCard({ response, type, toolCalls }: Props) {
  const steps = (toolCalls ?? []).map((t) => TOOL_LABELS[t.tool] ?? t.tool);
  const uniqueSteps = Array.from(new Set(steps));

  return (
    <div className="bg-white rounded-xl shadow-md p-6">
      <div className="flex items-center gap-2 mb-4">
        <span className={`text-xs font-semibold px-2 py-1 rounded-full border ${TYPE_COLORS[type]}`}>
          {TYPE_LABELS[type]}
        </span>
      </div>

      <div className="text-gray-800 whitespace-pre-wrap leading-relaxed">{response}</div>

      {uniqueSteps.length > 0 && (
        <div className="mt-5 pt-4 border-t border-gray-100">
          <p className="text-xs text-gray-400 mb-1.5">How this was answered</p>
          <ul className="flex flex-wrap gap-2">
            {uniqueSteps.map((step) => (
              <li
                key={step}
                className="text-xs text-gray-600 bg-gray-50 border border-gray-200 rounded-full px-3 py-1"
              >
                {step}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
