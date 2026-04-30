# Use a lightweight Python base
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set the working directory
WORKDIR /app

# Enable bytecode compilation and copy dependency files
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Final Stage
FROM python:3.12-slim

WORKDIR /app

# Copy the virtual environment from the builder
COPY --from=builder /app/.venv /app/.venv
COPY . .

# Place the venv at the front of the PATH
ENV PATH="/app/.venv/bin:$PATH"

# Expose the port used by Cloud Run
EXPOSE 8080

# Run the function using the Functions Framework
# Replace 'hello_world' with your actual function name
CMD ["functions-framework", "--target=hello_world"]