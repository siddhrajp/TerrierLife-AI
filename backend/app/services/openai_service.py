import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from app.services.places_service import search_places
from app.services.rag_service import search_bu_resources
from app.services.events_service import search_events

load_dotenv()

llm = ChatOpenAI(model="gpt-4o", temperature=0)

SYSTEM_PROMPT = """You are TerrierLife AI, a smart campus assistant for Boston University students.

Your job is to help students:
1. Make good use of time between classes (study, food, print, get help)
2. Find campus places that match their needs
3. Answer BU resource/policy questions with citations
4. Discover relevant campus events

When you respond:
- Be practical and concise
- Always include why you're recommending something
- For places, mention approximate walking time
- For resources, always cite official BU sources
- For events, explain why it's relevant to the student

Use the available tools to get real data before answering."""


async def handle_query(
    message: str,
    location: str | None,
    time_available: int | None,
    interests: list | None,
    db,
) -> dict:

    @tool
    async def get_nearby_places(location: str, place_type: str, features: list[str] = None, max_walk_minutes: int = 10) -> str:
        """Find campus places (study spots, dining, printers, libraries) near a location.
        place_type must be one of: study, dining, printer, library, support, any.
        features is an optional list like ['quiet', 'outlets', 'coffee']."""
        result = await search_places(
            db=db,
            location=location,
            place_type=place_type,
            features=features or [],
            max_walk_minutes=max_walk_minutes,
        )
        return json.dumps(result)

    @tool
    async def search_bu_resource(query: str) -> str:
        """Answer questions about BU services, policies, advising, career center,
        international students (OPT/CPT), health services, financial aid, housing, etc."""
        result = await search_bu_resources(db=db, query=query)
        return json.dumps(result)

    @tool
    async def get_events(interests: list[str], days_ahead: int = 7) -> str:
        """Get personalized event recommendations based on student interests.
        interests is a list of topics like ['AI', 'career', 'startup', 'wellness']."""
        result = await search_events(db=db, interests=interests, days_ahead=days_ahead)
        return json.dumps(result)

    tools = [get_nearby_places, search_bu_resource, get_events]

    agent = create_react_agent(llm, tools)

    # Build context-aware input
    context_parts = [f"Student query: {message}"]
    if location:
        context_parts.append(f"Current location: {location}")
    if time_available:
        context_parts.append(f"Time available: {time_available} minutes")
    if interests:
        context_parts.append(f"Interests: {', '.join(interests)}")

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content="\n".join(context_parts)),
    ]

    result = await agent.ainvoke({"messages": messages})

    # Last message in the result is the final AI response
    final_message = result["messages"][-1]

    tool_calls = [
        {"tool": tc["name"], "args": tc["args"]}
        for msg in result["messages"]
        if getattr(msg, "tool_calls", None)
        for tc in msg.tool_calls
    ]

    return {
        "response": final_message.content,
        "type": detect_response_type(message),
        "tool_calls": tool_calls,
    }


def detect_response_type(message: str) -> str:
    msg = message.lower()
    if any(w in msg for w in ["event", "attend", "this week", "hackathon", "fair"]):
        return "events"
    if any(
        w in msg
        for w in ["how do i", "where can i get", "advising", "cpt", "opt", "drop class", "tutoring"]
    ):
        return "resource"
    if any(w in msg for w in ["minutes", "time", "before class", "between class"]):
        return "time_assistant"
    return "places"
