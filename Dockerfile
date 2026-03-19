FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y python3 python3-pip python3-venv git curl build-essential libxml2-dev libxslt-dev libjpeg-dev zlib1g-dev libffi-dev locales && \
    locale-gen C.UTF-8 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt --break-system-packages -i https://pypi.yandex-team.ru/simple/ || pip3 install --no-cache-dir -r requirements.txt --break-system-packages -i https://mirror.yandex.ru/pypi/simple/
RUN pip3 install --no-cache-dir maigret sherlock-project --break-system-packages -i https://mirror.yandex.ru/pypi/simple/ || true
RUN playwright install --with-deps chromium || true
COPY . .
RUN mkdir -p /app/data /app/data/leaks /app/data/demo /app/app/static/uploads /app/app/static/reports /app/app/static/identity_cards
EXPOSE 5000
CMD ["python3", "-m", "gunicorn", "run:app", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "300"]
