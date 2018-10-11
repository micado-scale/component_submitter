FROM python:3.6-slim

COPY . .

RUN apt update \
&& apt  install -y docker curl\
&& rm -rf /var/lib/apt/lists/*\
&& pip3 install --upgrade pip \
&& pip3 install -r requirements.txt

WORKDIR /var/lib/submitter


ENV LC_ALL=C.UTF-8 LANG=C.UTF-8 PYTHONPATH=/ FLASK_APP=api.py

ENTRYPOINT ["flask", "run"]


HEALTHCHECK --interval=120s --timeout=180s  --retries=3 CMD curl localhost:5050/v1.0/list_app

