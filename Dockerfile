FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies before copying code — cache-friendly layer order
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the embedding model so the container runs fully offline
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Copy application code and input data
COPY . .

# Run Prefect in ephemeral mode — no server needed inside the container
ENV PREFECT_API_URL=""

# Default: full pipeline — Prefect validation flow, then FAISS index build
# Override a single step: docker run sayfit-data python flows/build_food_reference_data.py
CMD ["sh", "-c", "python flows/build_food_reference_data.py && python scripts/build_faiss_index.py"]
