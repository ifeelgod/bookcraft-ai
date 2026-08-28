FROM python:3.11-slim

# Install Node.js, curl, and build tools
RUN apt-get update && apt-get install -y curl build-essential \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy the entire project
COPY . .

# Build Frontend
WORKDIR /app/frontend
RUN npm ci
RUN npm run build

# Install Backend dependencies
WORKDIR /app/backend
RUN pip install --no-cache-dir -r requirements.txt

# Environment variables
ENV PORT=8000
ENV NEXT_PUBLIC_API_URL=""
# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Start FastAPI serving both backend API and static frontend out/ folder
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
