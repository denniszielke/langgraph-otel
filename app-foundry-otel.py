import os
import sys
import logging
import random
from typing import TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, BaseMessage, SystemMessage
from langgraph.graph import StateGraph, END

# Load environment variables
load_dotenv()

# ---------------------------------------------------------------------------
# Azure Foundry Tracing Setup
# Follows: https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/
#          trace-agent-framework#configure-tracing-for-langchain-and-langgraph
# ---------------------------------------------------------------------------
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# azure-monitor-opentelemetry provides the Application Insights exporter
# and the configure_azure_monitor convenience helper
from azure.monitor.opentelemetry import configure_azure_monitor

# azure-ai-inference provides the AIInferenceInstrumentor which instruments
# all Azure AI Inference SDK calls (and langchain-azure-ai) with OTel spans
from azure.ai.inference.tracing import AIInferenceInstrumentor

# langchain-azure-ai: Azure AI Foundry-native LangChain chat model
from langchain_azure_ai.chat_models import AzureAIChatCompletionsModel

# azure-identity: DefaultAzureCredential for keyless authentication
from azure.identity import DefaultAzureCredential

logger = logging.getLogger("app")
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler(stream=sys.stdout))


def get_logger(module_name):
    return logging.getLogger(f"app.{module_name}")


# ---------------------------------------------------------------------------
# Environment variables
# Required for Azure AI Foundry tracing:
#   APPLICATIONINSIGHTS_CONNECTION_STRING  - Application Insights conn string
#                                            from your Azure AI Foundry project
# Required for the LLM:
#   AZURE_AI_FOUNDRY_ENDPOINT              - e.g. https://<hub>.services.ai.azure.com/models
#   AZURE_OPENAI_DEPLOYMENT_NAME           - model deployment name
# Optional:
#   AZURE_AI_FOUNDRY_API_KEY               - API key (if omitted, uses DefaultAzureCredential)
#   AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED - set to "true" to capture
#                                                     prompt/completion text in traces
# ---------------------------------------------------------------------------

appinsights_connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
azure_endpoint = os.getenv("AZURE_AI_FOUNDRY_ENDPOINT", "").strip()
api_key = os.getenv("AZURE_AI_FOUNDRY_API_KEY", "").strip()
azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")

if not azure_endpoint:
    logger.error("AZURE_AI_FOUNDRY_ENDPOINT environment variable is not set.")
    sys.exit(1)

# Use API key if provided, otherwise fall back to DefaultAzureCredential
credential = api_key if api_key else DefaultAzureCredential()
if api_key:
    logger.info("Using API key authentication.")
else:
    logger.info("No API key provided. Using DefaultAzureCredential.")


def setup_tracing():
    """Configure Azure Foundry / Application Insights tracing.

    Steps as per MS docs:
    1. Call configure_azure_monitor() to set up the OTel exporter pointed at
       the Application Insights resource linked to your Azure AI Foundry project.
    2. Call AIInferenceInstrumentor().instrument() to auto-instrument all
       azure-ai-inference (and langchain-azure-ai) calls.
    3. Optionally pass enable_content_recording=True to capture prompt /
       completion content in the traces (useful for debugging; be mindful of
       privacy / data-retention policies in production).
    """
    if appinsights_connection_string:
        # Route all OTel spans to Azure Monitor / Application Insights
        configure_azure_monitor(
            connection_string=appinsights_connection_string,
            resource=Resource.create(attributes={
                SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", "foundry-langgraph-demo")
            }),
        )
        logger.info("Azure Monitor tracing configured.")
    else:
        # Fallback: use a simple in-memory tracer so the app still runs
        logger.warning(
            "APPLICATIONINSIGHTS_CONNECTION_STRING not set. "
            "Traces will NOT be exported to Azure Foundry."
        )
        tracer_provider = TracerProvider(
            resource=Resource.create(attributes={
                SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", "foundry-langgraph-demo")
            })
        )
        trace.set_tracer_provider(tracer_provider)

    # Instrument all Azure AI Inference / langchain-azure-ai calls
    # enable_content_recording=True records prompt + completion text in spans
    enable_content = os.getenv("AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED", "false").lower() == "true"
    AIInferenceInstrumentor().instrument(enable_content_recording=enable_content)
    logger.info(f"AIInferenceInstrumentor active (content recording: {enable_content}).")

    return trace.get_tracer(__name__)

tracer = setup_tracing()

# ---------------------------------------------------------------------------
# LLM — use langchain-azure-ai's AzureAIChatCompletionsModel which is
# natively instrumented by AIInferenceInstrumentor
# ---------------------------------------------------------------------------
llm = AzureAIChatCompletionsModel(
    endpoint=azure_endpoint,
    credential=credential,
    model=azure_deployment,
)


# ---------------------------------------------------------------------------
# Agent graph (same three-agent majority-vote logic as app-grafana-otel.py)
# ---------------------------------------------------------------------------

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
    votes = {"agent1": 1, "agent2": 1}
    votes[state["agent3_agrees_with"]] += 1

    if votes["agent1"] > votes["agent2"]:
        winner = "agent1"
        winning_response = state["agent1_response"]
    else:
        winner = "agent2"
        winning_response = state["agent2_response"]

    logger.info(
        f"Majority vote result: {winner} wins with {votes[winner]} votes "
        f"(Agent1: {votes['agent1']}, Agent2: {votes['agent2']})"
    )
    logger.info(f"Agent 3 agreed with: {state['agent3_agrees_with']}")

    return {
        "final_answer": winning_response,
    }


def build_graph():
    graph_builder = StateGraph(State)

    graph_builder.add_node("agent1", agent1)
    graph_builder.add_node("agent2", agent2)
    graph_builder.add_node("agent3", agent3)
    graph_builder.add_node("determine_majority", determine_majority)

    graph_builder.set_entry_point("agent1")

    graph_builder.add_edge("agent1", "agent2")
    graph_builder.add_edge("agent2", "agent3")
    graph_builder.add_edge("agent3", "determine_majority")
    graph_builder.add_edge("determine_majority", END)

    return graph_builder.compile()


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
    logger.info("Starting three-agent majority consensus flow (Azure Foundry tracing)...")
    logger.info("=" * 60)

    try:
        with tracer.start_as_current_span("three_agent_consensus") as span:
            span.set_attribute("gen_ai.request.model", azure_deployment)
            span.set_attribute("llm.request.type", "chat")
            span.set_attribute("consensus.num_agents", 3)

            final_state = graph.invoke(initial_state)

            logger.info("=" * 60)
            logger.info("FINAL MAJORITY ANSWER:")
            logger.info("=" * 60)
            logger.info(final_state["final_answer"])

            span.set_attribute(
                "consensus.winner",
                "agent1" if final_state["agent3_agrees_with"] == "agent1" else "agent2",
            )
    except Exception as e:
        logger.error(f"Error running graph: {e}")
        print(e)

    logger.info("Graph run complete.")


if __name__ == "__main__":
    user_input = "What is the best programming language to learn in 2026?"
    run_graph(user_input)