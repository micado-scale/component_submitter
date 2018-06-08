FROM alpine:latest

RUN apk update && \
apk --no-cache add gcc docker python3 && \
pip3 install tosca-parser ruamel.yaml==0.14 flask && \
apk del gcc

WORKDIR /var/lib/submitter

COPY . .

ENV LC_ALL=C.UTF-8 LANG=C.UTF-8 PYTHONPATH=/var/lib/submitter FLASK_APP=api.py

ENTRYPOINT ["flask", "run"]
