FROM python:3.11-bookworm

WORKDIR /workspace

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy application code after dependencies
COPY . .

EXPOSE 8080

# CMD ["python", "-m", "app.py", "--dev", "--log-level=DEBUG"]

CMD ["python", "app.py", "--processes=1", "--workers=4", "--log-level=DEBUG"]
