FROM ubuntu:20.04
ENV TZ Europe/Helsinki

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \ 
    && apt-get -y update \
    && apt-get install -y --no-install-recommends locales build-essential \
    software-properties-common dialog apt-utils libffi-dev libmagic-dev libmagickwand-dev \
    libexempi8 exempi autoconf automake libtool ghostscript icc-profiles-free \
    liblept5 libleptonica-dev libxml2 pngquant tesseract-ocr zlib1g zlib1g-dev ocrmypdf git \
    python3-dev python3-pip python3-cffi python3-reportlab python3-distutils python3-pkg-resources \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

RUN echo 'sudo deb-src http://ppa.launchpad.net/libreoffice/libreoffice-7-0/ubuntu focal main -y' \
    && apt-get -y update \
    && apt-get install -y libreoffice libreofficekit-dev hyphen-fi \
    hyphen-fr hyphen-de hyphen-en-us hyphen-it hyphen-pl hyphen-ru

RUN echo debconf debconf/frontend select Noninteractive | debconf-set-selections \
    && echo ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true | debconf-set-selections \
    && apt-get install -y --no-install-recommends \
    ttf-mscorefonts-installer fonts-dejavu-extra fonts-freefont-otf fonts-freefont-ttf \ 
    fonts-lmodern fonts-lyx fonts-sil-gentium fonts-dustin fonts-fanwood \
    fonts-3270 fonts-font-awesome fonts-bpg-georgian fonts-opensymbol \
    && fc-cache -vr \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

RUN locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8

ADD . /home/docsbox
WORKDIR /home/
RUN pip3 install --upgrade pip \
    && pip3 install -r docsbox/requirements.txt
COPY ./config/registrymodifications.xcu /root/.config/libreoffice/4/user/registrymodifications.xcu