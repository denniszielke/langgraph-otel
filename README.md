

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

### Azure OpenAI (Required)

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

## Run the Application

```bash
# Azure OpenAI
export AZURE_OPENAI_API_KEY="<APIKEY>"
export AZURE_OPENAI_ENDPOINT="https://<APIMENDPOINT>.azure-api.net"
export AZURE_OPENAI_DEPLOYMENT_NAME="gpt-5-mini"

# OpenTelemetry
export OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true
export OTEL_EXPORTER_OTLP_ENDPOINT="https://otlp-gateway-dedicated-64-prod-eu-west-5.grafana.net/otlp"
export OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf"
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic%20<ACCESSKEY>"
export OTEL_SERVICE_NAME="otel-langgraph-demo"
export OTEL_RESOURCE_ATTRIBUTES=deployment.environment=dev,service.namespace=demo,service.version=1,service.instance.id=234

python app.py
```

## Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | `abc123...` |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Model deployment name | `gpt-5-mini` |
| `AZURE_OPENAI_API_VERSION` | API version | `2024-12-01-preview` |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | `https://<APIMENDPOINT>.azure-api.net` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector endpoint | `http://localhost:4318` |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | OTLP protocol | `http/protobuf` |
| `OTEL_EXPORTER_OTLP_HEADERS` | OTLP headers for authentication | `Authorization=Basic%20<base64>` |
| `OTEL_SERVICE_NAME` | Service name for traces | `otel-langgraph-demo` |
| `OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED` | Enable auto logging instrumentation | `true` | 
| `OTEL_RESOURCE_ATTRIBUTES` | Resource attributes for traces | `deployment.environment=dev,service.namespace=demo,service.version=1,service.instance.id=234` |