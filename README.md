

# OpenTelemetry LangGraph Demo

A demo application showing OpenTelemetry tracing with LangGraph and Azure OpenAI.

## Setup

### 1. Create Virtual Environment

```bash
# Create venv
python -m venv .venv

# Activate venv
# macOS/Linux:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### Optionally install OpenTelemetry Distro

```bash
pip install opentelemetry-distro
opentelemetry-bootstrap -a install

opentelemetry-bootstrap python app.py
```

## Environment Configuration

Create a `.env` file in the project root. Choose one of the configurations below based on your tracing backend.

### Azure OpenAI (Required for Options A and B)

```bash
AZURE_OPENAI_API_KEY="your-api-key"
AZURE_OPENAI_DEPLOYMENT_NAME="gpt-5-mini"
AZURE_OPENAI_API_VERSION="2024-12-01-preview"
AZURE_OPENAI_ENDPOINT="https://<APIMENDPOINT>.azure-api.net"
```

---

### Option A: Local Jaeger (Container)

For local development with Jaeger as the tracing backend.

**Start Jaeger:**

```bash
docker run --rm --name jaeger \
  -p 16686:16686 \
  -p 4317:4317 \
  -p 4318:4318 \
  -p 5778:5778 \
  -p 9411:9411 \
  cr.jaegertracing.io/jaegertracing/jaeger:2.14.0
```

**Environment variables:**

```bash
OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
OTEL_SERVICE_NAME="otel-langgraph-demo"
```

**View traces:** Open http://localhost:16686/search

---

### Option B: Grafana Cloud

For production or cloud-based tracing with Grafana Cloud.

See: https://grafana.com/docs/grafana-cloud/monitor-applications/application-observability/setup/quickstart/

**Environment variables:**

```bash
OTEL_EXPORTER_OTLP_ENDPOINT="https://otlp-gateway-prod-<region>.grafana.net/otlp"
OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf"
OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic%20<base64-encoded-credentials>"
OTEL_SERVICE_NAME="otel-langgraph-demo"
```

**To get your credentials:**

1. Go to Grafana Cloud → **Application Observability** → **Setup**
2. Select **Python** as your language
3. Copy your OTLP endpoint (format: `https://otlp-gateway-prod-<region>.grafana.net/otlp`)
4. Generate an API token with `MetricsPublisher` role
5. Base64 encode `<instance-id>:<api-token>` and use in the headers with `Authorization=Basic%20` prefix

---

### Option C: Azure AI Foundry

For Azure-native observability using Azure AI Foundry and Application Insights.

See: https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/trace-agent-framework#configure-tracing-for-langchain-and-langgraph

**Environment variables:**

```bash
APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=<key>;IngestionEndpoint=https://<region>.in.applicationinsights.azure.com/"
AZURE_AI_FOUNDRY_ENDPOINT="https://<hub>.services.ai.azure.com/models"
AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4o-mini"
OTEL_SERVICE_NAME="foundry-langgraph-demo"

# Authentication (choose one):
AZURE_AI_FOUNDRY_API_KEY="your-foundry-api-key"  # Option 1: API key
# Or omit AZURE_AI_FOUNDRY_API_KEY to use DefaultAzureCredential (Option 2: keyless)
```

**Optional:** To capture prompt and completion text in traces (useful for debugging):

```bash
AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED="true"
```

**To set up Azure AI Foundry tracing:**

1. Create an **Azure AI Foundry** project in the Azure portal
2. Navigate to your project's **Application Insights** resource to get the `APPLICATIONINSIGHTS_CONNECTION_STRING`
3. Get your **Azure AI Foundry endpoint** from the project overview (format: `https://<hub>.services.ai.azure.com/models`)
4. Generate an **API key** from your Azure AI Foundry project, or use `DefaultAzureCredential` for keyless authentication
5. **View traces** in the Azure portal under your Application Insights resource → **Transaction search** or **End-to-end transaction details**

---

## Run the Application

Each tracing backend uses a dedicated application file. Set the required environment variables and run the corresponding file.

### Run with Local Jaeger (Option A)

```bash
# Azure OpenAI
export AZURE_OPENAI_API_KEY="<APIKEY>"
export AZURE_OPENAI_ENDPOINT="https://<APIMENDPOINT>.azure-api.net"
export AZURE_OPENAI_DEPLOYMENT_NAME="gpt-5-mini"

# OpenTelemetry (Jaeger)
export OTEL_SERVICE_NAME="otel-langgraph-demo"
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"

python app.py
```

### Run with Grafana Cloud (Option B)

```bash
# Azure OpenAI
export AZURE_OPENAI_API_KEY="<APIKEY>"
export AZURE_OPENAI_ENDPOINT="https://<APIMENDPOINT>.azure-api.net"
export AZURE_OPENAI_DEPLOYMENT_NAME="gpt-5-mini"

# OpenTelemetry (Grafana Cloud)
export OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true
export OTEL_EXPORTER_OTLP_ENDPOINT="https://otlp-gateway-prod-<region>.grafana.net/otlp"
export OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf"
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic%20<ACCESSKEY>"
export OTEL_SERVICE_NAME="otel-langgraph-demo"
export OTEL_RESOURCE_ATTRIBUTES=deployment.environment=dev,service.namespace=demo,service.version=1,service.instance.id=234

python app-grafana-otel.py
```

### Run with Azure AI Foundry (Option C)

```bash
# Azure AI Foundry
export AZURE_AI_FOUNDRY_ENDPOINT="https://<hub>.services.ai.azure.com/models"
export AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4o-mini"

# Authentication: set API key, or omit to use DefaultAzureCredential
export AZURE_AI_FOUNDRY_API_KEY="<APIKEY>"

# Application Insights tracing
export APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=<key>;IngestionEndpoint=https://<region>.in.applicationinsights.azure.com/"
export OTEL_SERVICE_NAME="foundry-langgraph-demo"

# Optional: capture prompt/completion text in traces
export AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED="true"

python app-foundry-otel.py
```

## Environment Variables Reference

### Azure OpenAI (used by `app.py` and `app-grafana-otel.py`)

| Variable | Description | Example |
|----------|-------------|---------|
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | `abc123...` |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Model deployment name | `gpt-5-mini` |
| `AZURE_OPENAI_API_VERSION` | API version | `2024-12-01-preview` |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | `https://<APIMENDPOINT>.azure-api.net` |

### OpenTelemetry (used by `app.py` and `app-grafana-otel.py`)

| Variable | Description | Example |
|----------|-------------|---------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector endpoint | `http://localhost:4318` |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | OTLP protocol | `http/protobuf` |
| `OTEL_EXPORTER_OTLP_HEADERS` | OTLP headers for authentication | `Authorization=Basic%20<base64>` |
| `OTEL_SERVICE_NAME` | Service name for traces | `otel-langgraph-demo` |
| `OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED` | Enable auto logging instrumentation | `true` |
| `OTEL_RESOURCE_ATTRIBUTES` | Resource attributes for traces | `deployment.environment=dev,service.namespace=demo,service.version=1,service.instance.id=234` |

### Azure AI Foundry (used by `app-foundry-otel.py`)

| Variable | Description | Example |
|----------|-------------|---------|
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Application Insights connection string from your Azure AI Foundry project | `InstrumentationKey=<key>;IngestionEndpoint=https://...` |
| `AZURE_AI_FOUNDRY_ENDPOINT` | Azure AI Foundry model endpoint | `https://<hub>.services.ai.azure.com/models` |
| `AZURE_AI_FOUNDRY_API_KEY` | Azure AI Foundry API key (optional — omit to use `DefaultAzureCredential`) | `abc123...` |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Model deployment name | `gpt-4o-mini` |
| `OTEL_SERVICE_NAME` | Service name for traces | `foundry-langgraph-demo` |
| `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED` | Enable prompt/completion text recording in traces | `true` |