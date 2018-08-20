ARG label_arch=x64
ARG image_label=azogue/py36_base:${label_arch}

FROM $image_label

LABEL maintainer="eugenio.panadero@gmail.com"
LABEL maintainer_name="Eugenio Panadero"

ARG label_arch=rpi3
RUN if [ "$label_arch" = "x64" ] ; then apk add supervisor freetype libpng-dev; else apt-get install libfreetype6-dev libpng12-dev pkg-config supervisor ; fi

ADD ./requirements.txt .
RUN pip install -r requirements.txt

RUN if [ "$label_arch" = "rpi3" ] ; then groupadd nobody; fi
RUN mkdir /var/run/celery
RUN chown -R nobody:nobody /var/run/celery/

RUN mkdir psychrocam
COPY supervisord.conf psychrocam/
COPY ./psychrodata psychrocam/psychrodata
COPY ./psychrocam psychrocam/psychrocam
COPY ./psychrochartmaker psychrocam/psychrochartmaker

WORKDIR /psychrocam
ENV PYTHONPATH /psychrocam

CMD ["/usr/bin/supervisord", "-c", "/psychrocam/supervisord.conf"]
