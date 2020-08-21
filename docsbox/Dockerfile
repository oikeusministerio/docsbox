FROM ubuntu:18.04

RUN apt-get -y upgrade 
RUN apt-get -y update
RUN apt-get -y install software-properties-common dialog apt-utils libffi-dev libmagic-dev libmagickwand-dev libexempi3 exempi
RUN add-apt-repository -y ppa:libreoffice/libreoffice-6-3
RUN apt-get -y update
RUN apt-get install -y libreoffice libreofficekit-dev hyphen-fr hyphen-de hyphen-en-us hyphen-it hyphen-pl hyphen-ru
RUN echo debconf debconf/frontend select Noninteractive | debconf-set-selections
RUN echo ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true | debconf-set-selections
RUN apt-get install -y ttf-mscorefonts-installer
RUN apt-get install -y fonts-dejavu-extra fonts-freefont-otf fonts-freefont-ttf fonts-lmodern fonts-lyx fonts-sil-gentium fonts-dustin fonts-fanwood fonts-3270 fonts-font-awesome fonts-bpg-georgian
RUN apt-get install -y python3-dev python3-pip python3-cffi python3-distutils python3-pkg-resources python3-reportlab git

RUN apt-get clean && apt-get -y update && apt-get install -y locales && locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

ADD . /home/docsbox
WORKDIR /home/
RUN pip3 install --upgrade pip
RUN pip3 install -r docsbox/requirements.txt
COPY ./config/registrymodifications.xcu /root/.config/libreoffice/4/user/