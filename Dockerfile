FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# install dependencies first so Docker can cache this layer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pytest.ini .
COPY config ./config
COPY controls_monitor ./controls_monitor
COPY tests ./tests
COPY docker ./docker

# Windows checkouts can turn line endings into CRLF, which breaks a shell script
RUN sed -i 's/\r$//' docker/demo.sh

CMD ["sh", "docker/demo.sh"]