FROM alpine:latest

RUN apk update \
&& apk --no-cache add git gcc docker python3 \
&& pip3 install docker==3.3.0 ruamel.yaml==0.14 flask==1.0.2 \
&& git clone https://github.com/jaydesl/tosca-parser /tmp/toscaparser \
&& cd /tmp/toscaparser \
&& pip3 install -r requirements.txt \
&& python3 setup.py install \
&& rm -r /tmp/toscaparser \
&& apk del gcc git

WORKDIR /var/lib/submitter

COPY . .

ENV LC_ALL=C.UTF-8 LANG=C.UTF-8 PYTHONPATH=/var/lib/submitter FLASK_APP=api.py

ENTRYPOINT ["flask", "run"]
