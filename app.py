import os
import sys
import logging
from typing import Annotated, TypedDict
from wsgiref import headers

from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, BaseMessage
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


def chatbot(state: State):
    return {"messages": [llm.invoke(state["messages"])]}


def build_graph():
    # Build the graph
    graph_builder = StateGraph(State)
    graph_builder.add_node("chatbot", chatbot)
    graph_builder.set_entry_point("chatbot")
    graph_builder.add_edge("chatbot", END)

    graph = graph_builder.compile()
    return graph

graph = build_graph()

def run_graph(human_input: str):
    initial_state = {"messages": [HumanMessage(content=human_input)]}

    logger.info(f"User input : {human_input}")
    try:
        with tracer.start_as_current_span("call_open_ai") as span:
            span.set_attribute("gen_ai.request.model", azure_deployment)
            span.set_attribute("llm.request.type", "chat")

            for event in graph.stream(initial_state):
                for value in event.values():
                    logger.info(f"Assistant : {value['messages'][-1].content}")
    except Exception as e:
        logger.error(f"Error running graph: {e}")
        print(e)
    
    logger.info("Graph run complete.")


if __name__ == "__main__":
    user_input = "Tell me the your name and one interesting word about OpenTelemetry."
    run_graph(user_input)