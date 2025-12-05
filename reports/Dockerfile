# Report Generator - Dockerfile
FROM python:3.11-slim-bookworm

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    pandas \
    numpy \
    matplotlib \
    jinja2

# Copy scripts
COPY generate.py ./
COPY templates ./templates

# Create output directory
RUN mkdir -p /app/assets

CMD ["python", "generate.py"]
