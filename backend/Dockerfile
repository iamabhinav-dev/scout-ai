FROM python:3.13-slim

# Pin Playwright browser path so build and runtime agree on the location
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium and all its OS-level dependencies in one step
RUN playwright install chromium --with-deps

COPY . .

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
