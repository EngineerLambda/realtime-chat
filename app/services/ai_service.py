import os
from typing import List, Optional, TypedDict, Literal, AsyncGenerator
from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, END
from langchain_community.tools.tavily_search import TavilySearchResults
from pydantic import BaseModel
from groq import AsyncGroq

# Load environment variables from .env file
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "openai/gpt-oss-20b")

if not GROQ_API_KEY or not TAVILY_API_KEY:
    print("Warning: GROQ_API_KEY or TAVILY_API_KEY not set. AI service will not work.")

client = AsyncGroq(api_key=GROQ_API_KEY)

# --- Intent Classification ---

class IntentOutput(BaseModel):
    purpose: Literal["chat", "web_search"]

intent_parser = PydanticOutputParser(pydantic_object=IntentOutput)

INTENT_PROMPT = """
Categorise the user's request as one of: 'chat' or 'web_search'.
- 'chat': For general conversation, greetings, or questions that don't require real-time information.
- 'web_search': When the user asks for current events, specific facts, or anything that requires up-to-date information from the internet.

{format_instructions}

User input: {user_input}
"""

intent_prompt = PromptTemplate(
    template=INTENT_PROMPT,
    input_variables=["user_input"],
    partial_variables={"format_instructions": intent_parser.get_format_instructions()},
)

async def classify_intent(text: str) -> IntentOutput:
    prompt = intent_prompt.format(user_input=text)
    completion = await client.chat.completions.create(
        model=LLM_MODEL_NAME,
        messages=[{"role": "user", "content": prompt}]
    )
    return intent_parser.parse(completion.choices[0].message.content)

# --- Graph State ---

class GraphState(TypedDict):
    user_input: str
    chat_history: List[BaseMessage]
    purpose: Optional[str]
    stream: Optional[AsyncGenerator[str, None]]

# --- Graph Nodes ---

async def intent_parser_node(state: GraphState) -> GraphState:
    try:
        result = await classify_intent(state["user_input"])
        state["purpose"] = result.purpose
    except Exception:
        state["purpose"] = "chat"  # Fallback to chat on error
    return state

async def chat_node(state: GraphState) -> GraphState:
    # The first message should have the 'system' role.
    system_prompt = {"role": "system", "content": "You are a helpful AI assistant. Respond to the user's query."}
    
    # Convert LangChain message history to API-compatible format
    history = []
    for msg in state["chat_history"]:
        role = "user" if isinstance(msg, HumanMessage) else "assistant"
        history.append({"role": role, "content": msg.content})

    messages = [system_prompt] + history + [{"role": "user", "content": state["user_input"]}]

    state["stream"] = await client.chat.completions.create(
        model=LLM_MODEL_NAME,
        messages=messages,
        stream=True
    )
    return state

async def web_search_node(state: GraphState) -> GraphState:
    tool = TavilySearchResults(max_results=3, api_key=TAVILY_API_KEY)
    results = await tool.ainvoke(state["user_input"])

    prompt = f"Based on these search results:\n{results}\n\nAnswer the user's query: {state['user_input']}"

    # Convert LangChain message history to API-compatible format
    history = []
    for msg in state["chat_history"]:
        role = "user" if isinstance(msg, HumanMessage) else "assistant"
        history.append({"role": role, "content": msg.content})

    messages = history + [{"role": "user", "content": prompt}]

    state["stream"] = await client.chat.completions.create(
        model=LLM_MODEL_NAME, messages=messages, stream=True
    )
    return state

# --- Graph Setup ---

def route_by_intent(state: GraphState) -> str:
    return state.get("purpose", "chat")

graph = StateGraph(GraphState)
graph.add_node("intent_parser", intent_parser_node)
graph.add_node("chat", chat_node)
graph.add_node("web_search", web_search_node)

graph.add_conditional_edges("intent_parser", route_by_intent, {"chat": "chat", "web_search": "web_search"})
graph.add_edge("chat", END)
graph.add_edge("web_search", END)
graph.set_entry_point("intent_parser")

ai_graph = graph.compile()

# --- Main Accessor ---

async def get_ai_response_stream(user_input: str, chat_history: List[dict] = None):
    """
    Gets a streaming response from the AI.
    chat_history: A list of dicts, e.g., [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    """
    history_messages = []
    if chat_history:
        for msg in chat_history:
            if msg.get("role") == "user":
                history_messages.append(HumanMessage(content=msg["content"]))
            elif msg.get("role") == "assistant":
                history_messages.append(AIMessage(content=msg["content"]))

    state = await ai_graph.ainvoke({"user_input": user_input, "chat_history": history_messages})

    stream = state.get("stream")
    if stream is None:
        raise RuntimeError("AI graph did not produce a stream.")

    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content