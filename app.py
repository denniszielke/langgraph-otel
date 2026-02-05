import os
import sys
import logging
import random
from typing import Annotated, TypedDict
from wsgiref import headers

from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, BaseMessage, SystemMessage
from langgraph.graph import StateGraph, END

# Load environment variables
load_dotenv()

from opentelemetry.sdk.resources import SERVICE_NAME, Resource

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.langchain import LangchainInstrumentor

logger = logging.getLogger("app")
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler(stream=sys.stdout))

def get_logger(module_name):
    return logging.getLogger(f"app.{module_name}")

otel_resource = Resource.create(attributes={
    SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", "otel-langgraph-demo")
})

def setup_tracing():
    tracer_provider = TracerProvider(resource=otel_resource)
    trace.set_tracer_provider(tracer_provider)
    tracer = trace.get_tracer(__name__)
    LangchainInstrumentor().instrument()
    return tracer

tracer = setup_tracing()

azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5-mini")
api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
api_key=os.getenv("AZURE_OPENAI_API_KEY", "").strip()

if not azure_endpoint:
    logger.error("AZURE_OPENAI_ENDPOINT environment variable is not set.")
    sys.exit(1)

if not api_key:
    logger.error("AZURE_OPENAI_API_KEY environment variable is not set.")
    sys.exit(1)

llm = AzureChatOpenAI(
    azure_deployment=azure_deployment,
    api_version=api_version,
    azure_endpoint=azure_endpoint,
    api_key=api_key,
    max_tokens=16384,
    default_headers={"Ocp-Apim-Subscription-Key": api_key},
)

class State(TypedDict):
    messages: list[BaseMessage]
    agent1_response: str
    agent2_response: str
    agent3_response: str
    agent3_agrees_with: str  # "agent1" or "agent2"
    final_answer: str


def agent1(state: State):
    """First agent: generates an initial response to the user's question."""
    response = llm.invoke(state["messages"])
    logger.info(f"Agent 1 response: {response.content}")
    return {
        "agent1_response": response.content,
    }


def agent2(state: State):
    """Second agent: always provides a different/contrarian perspective."""
    messages = state["messages"] + [
        SystemMessage(content=f"""You must provide a DIFFERENT and CONTRARIAN response to the user's question.
Another agent already responded with: "{state['agent1_response']}"

You MUST disagree or provide a completely different perspective. Do NOT agree with the previous response.
Give a substantive alternative answer that takes a different viewpoint or approach.""")
    ]
    response = llm.invoke(messages)
    logger.info(f"Agent 2 response (contrarian): {response.content}")
    return {
        "agent2_response": response.content,
    }


def agent3(state: State):
    """Third agent: randomly agrees with either agent 1 or agent 2."""
    agrees_with = random.choice(["agent1", "agent2"])
    
    if agrees_with == "agent1":
        chosen_response = state["agent1_response"]
        other_response = state["agent2_response"]
    else:
        chosen_response = state["agent2_response"]
        other_response = state["agent1_response"]
    
    messages = state["messages"] + [
        SystemMessage(content=f"""Two agents have provided different responses to the user's question.

Response A: "{chosen_response}"
Response B: "{other_response}"

You agree with Response A. Explain why you support this response and provide your endorsement of it.
Keep your response concise but make it clear you're supporting Response A's position.""")
    ]
    response = llm.invoke(messages)
    logger.info(f"Agent 3 agrees with {agrees_with}: {response.content}")
    return {
        "agent3_response": response.content,
        "agent3_agrees_with": agrees_with,
    }


def determine_majority(state: State):
    """Determines the majority consensus and returns the final answer."""
    # Count votes: Agent 1 always votes for agent1, Agent 2 always votes for agent2
    # Agent 3's vote is random (stored in agent3_agrees_with)
    votes = {"agent1": 1, "agent2": 1}  # Each agent votes for their own response
    votes[state["agent3_agrees_with"]] += 1  # Agent 3's deciding vote
    
    if votes["agent1"] > votes["agent2"]:
        winner = "agent1"
        winning_response = state["agent1_response"]
    else:
        winner = "agent2"
        winning_response = state["agent2_response"]
    
    logger.info(f"Majority vote result: {winner} wins with {votes[winner]} votes (Agent1: {votes['agent1']}, Agent2: {votes['agent2']})")
    logger.info(f"Agent 3 agreed with: {state['agent3_agrees_with']}")
    
    return {
        "final_answer": winning_response,
    }


def build_graph():
    # Build the graph with three agents and majority consensus
    graph_builder = StateGraph(State)
    
    # Add nodes
    graph_builder.add_node("agent1", agent1)
    graph_builder.add_node("agent2", agent2)
    graph_builder.add_node("agent3", agent3)
    graph_builder.add_node("determine_majority", determine_majority)
    
    # Set entry point
    graph_builder.set_entry_point("agent1")
    
    # Define edges: agent1 -> agent2 -> agent3 -> determine_majority -> END
    graph_builder.add_edge("agent1", "agent2")
    graph_builder.add_edge("agent2", "agent3")
    graph_builder.add_edge("agent3", "determine_majority")
    graph_builder.add_edge("determine_majority", END)

    graph = graph_builder.compile()
    return graph

graph = build_graph()

def run_graph(human_input: str):
    initial_state = {
        "messages": [HumanMessage(content=human_input)],
        "agent1_response": "",
        "agent2_response": "",
        "agent3_response": "",
        "agent3_agrees_with": "",
        "final_answer": "",
    }

    logger.info(f"User input: {human_input}")
    logger.info("=" * 60)
    logger.info("Starting three-agent majority consensus flow...")
    logger.info("=" * 60)
    
    try:
        with tracer.start_as_current_span("three_agent_consensus") as span:
            span.set_attribute("gen_ai.request.model", azure_deployment)
            span.set_attribute("llm.request.type", "chat")
            span.set_attribute("consensus.num_agents", 3)

            # Use invoke to get the complete final state
            final_state = graph.invoke(initial_state)
            
            logger.info("=" * 60)
            logger.info("FINAL MAJORITY ANSWER:")
            logger.info("=" * 60)
            logger.info(final_state["final_answer"])
            
            span.set_attribute("consensus.winner", "agent1" if final_state["agent3_agrees_with"] == "agent1" else "agent2")
    except Exception as e:
        logger.error(f"Error running graph: {e}")
        print(e)
    
    logger.info("Graph run complete.")


if __name__ == "__main__":
    user_input = "What is the best programming language to learn in 2026?"
    run_graph(user_input)