# Aurai gateway image: the LiteLLM proxy plus the Aurai guardrail package.
# Verify the base image tag against the current LiteLLM stable release before building.
ARG LITELLM_IMAGE=ghcr.io/berriai/litellm:v1.105.5
FROM ${LITELLM_IMAGE}

WORKDIR /opt/aurai-gateway
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# LiteLLM loads custom_guardrail.py from the directory that holds config.yaml. The Helm chart mounts
# both at /etc/litellm; this copy supports running the image directly with a mounted config.yaml.
COPY config/custom_guardrail.py /app/custom_guardrail.py

LABEL org.opencontainers.image.title="aurai-gateway" \
      org.opencontainers.image.description="Aurai AI gateway (LiteLLM with tiered PII guardrail)" \
      org.opencontainers.image.licenses="MIT"
