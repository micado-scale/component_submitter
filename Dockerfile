FROM python:3.6-slim

COPY requirements.txt /requirements.txt

RUN pip3 install -r /requirements.txt \
&& rm -rf /root/.cache \
&& rm /requirements.txt

WORKDIR /var/lib/micado/submitter

COPY submitter .

ENV LC_ALL=C.UTF-8 LANG=C.UTF-8 PYTHONPATH=/var/lib/micado FLASK_APP=api.py

ENTRYPOINT ["flask", "run"]
