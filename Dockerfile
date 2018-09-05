FROM alpine:latest

RUN apk update \
&& apk --no-cache add docker python3 \
&& pip3 install -r requirements.txt

WORKDIR /var/lib/submitter

COPY . .

ENV LC_ALL=C.UTF-8 LANG=C.UTF-8 PYTHONPATH=/var/lib/submitter FLASK_APP=api.py

ENTRYPOINT ["flask", "run"]
