FROM sgtdck/python-plot

RUN apk update
RUN apk add supervisor

RUN mkdir /var/run/celery
RUN chown -R nobody:nobody /var/run/celery/

ADD ./requirements.txt .
ADD ./supervisord.conf .
RUN mkdir psychrocam
COPY . psychrocam

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

WORKDIR /psychrocam
ENV PYTHONPATH /psychrocam

CMD ["/usr/bin/supervisord", "-c", "/supervisord.conf"]
