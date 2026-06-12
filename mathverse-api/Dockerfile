FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
# Tencent mirror — the prod box is Tencent Cloud (internal route, fast); direct
# PyPI from mainland China intermittently fails ("from versions: none").
RUN pip install --no-cache-dir -i https://mirrors.cloud.tencent.com/pypi/simple -r requirements.txt
COPY . .
EXPOSE 8002
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
