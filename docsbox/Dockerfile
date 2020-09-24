FROM ubuntu:20.04
ENV TZ=Europe/Helsinki
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apt-get -y upgrade 
RUN apt-get -y update --fix-missing
RUN apt-get -y install software-properties-common dialog apt-utils libffi-dev libmagic-dev libmagickwand-dev libexempi8 exempi
RUN echo 'sudo deb-src http://ppa.launchpad.net/libreoffice/libreoffice-7-0/ubuntu focal main -y'
RUN apt-get -y update
RUN apt-get install -y libreoffice libreofficekit-dev hyphen-fi hyphen-fr hyphen-de hyphen-en-us hyphen-it hyphen-pl hyphen-ru
RUN echo debconf debconf/frontend select Noninteractive | debconf-set-selections
RUN echo ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true | debconf-set-selections
RUN apt-get install -y ttf-mscorefonts-installer
RUN apt-get install -y texlive-fonts-extra fonts-dejavu-extra fonts-freefont-otf fonts-freefont-ttf fonts-lmodern fonts-lyx fonts-sil-gentium fonts-dustin fonts-fanwood fonts-3270 fonts-font-awesome fonts-bpg-georgian fonts-opensymbol
RUN fc-cache -vr
RUN apt-get -y update
RUN apt-get install -y git python3-dev python3-pip python3-cffi python3-pkg-resources python3-reportlab python3-distutils python3-pkg-resources python3-reportlab ocrmypdf

RUN apt-get clean && apt-get -y update && apt-get install -y locales && locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

ADD . /home/docsbox
WORKDIR /home/
RUN pip3 install --upgrade pip
RUN pip3 install -r docsbox/requirements.txt --use-feature=2020-resolver
COPY ./config/registrymodifications.xcu /root/.config/libreoffice/4/user/registrymodifications.xcu