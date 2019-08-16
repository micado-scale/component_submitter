FROM python:3.6-slim

WORKDIR /var/lib/submitter

COPY . .

RUN pip3 install -r requirements.txt \
&& rm requirements.txt

ENV LC_ALL=C.UTF-8 LANG=C.UTF-8 PYTHONPATH=/var/lib/submitter FLASK_APP=api.py

ENTRYPOINT ["flask", "run"]
