FROM alpine:latest

RUN apk --update --no-cache add \
        python3 \
        py3-pip \
        git

RUN pip3 install --no-cache-dir \
#    PyP100>=0.0.18 \
    git+https://github.com/almottier/TapoP100.git@main \
    prometheus-client>=0.13.1 \
    click>=8.0.4 \
    loguru>=0.6.0 \
    PyYAML>=6.0

WORKDIR /app
COPY main.py collector.py /app

ENV TAPO_USER_EMAIL ""
ENV TAPO_USER_PASSWORD ""
ENV TAPO_MONITOR_CONFIG "/etc/tapo-exporter.yml"

ENTRYPOINT [ "python3", "main.py" ]
