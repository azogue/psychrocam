FROM sgtdck/python-plot

RUN apk update
RUN apk add supervisor

RUN mkdir /var/run/celery
RUN chown -R nobody:nobody /var/run/celery/

RUN mkdir psychrocam
COPY . psychrocam

RUN pip install --upgrade pip
RUN pip install -r /psychrocam/requirements.txt

WORKDIR /psychrocam
ENV PYTHONPATH /psychrocam

CMD ["/usr/bin/supervisord", "-c", "/psychrocam/supervisord.conf"]
