FROM python:3.13.5-slim

WORKDIR /app

# System dependencies for llama.cpp
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    wget \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Copy entire project (not only src/)
COPY . /app

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Create models folder
RUN mkdir -p /app/models

RUN mkdir -p /app/models && \
    wget -O /app/models/gemma-2b-it.Q4_K_M.gguf \
    https://huggingface.co/ggml-org/gemma-2b-it-GGUF/resolve/main/gemma-2b-it.Q4_K_M.gguf


# Expose Streamlit port
EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "src/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
