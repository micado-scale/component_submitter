FROM python:3.6-slim

WORKDIR /var/lib/submitter

COPY . .

RUN apt update \
&& apt install -y curl lsof libltdl7 \
&& rm -rf /var/lib/apt/lists/* \
&& pip3 install --upgrade pip \
&& pip3 install -r requirements.txt \
&& rm requirements.txt

ENV LC_ALL=C.UTF-8 LANG=C.UTF-8 PYTHONPATH=/var/lib/submitter FLASK_APP=api.py

ENTRYPOINT ["flask", "run"]

HEALTHCHECK --interval=120s --timeout=180s  --retries=3 CMD python3.6 /healthcheck.py || exit 1
