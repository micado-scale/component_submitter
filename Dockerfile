FROM python:3.8-slim

COPY requirements.txt /requirements.txt

RUN pip3 install -r /requirements.txt \
&& rm -rf /root/.cache \
&& rm /requirements.txt

WORKDIR /var/lib/micado/submitter

COPY submitter .

ENV LC_ALL=C.UTF-8 LANG=C.UTF-8 PYTHONPATH=/var/lib/micado

ENTRYPOINT ["gunicorn", "submitter.api:app", "--timeout", "600", "--workers", "1"]