FROM ubuntu:20.04
ENV TZ Europe/Helsinki

# install prequisited
RUN apt-get update && apt-get install -y software-properties-common \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Define fonts
RUN echo debconf debconf/frontend select Noninteractive | debconf-set-selections \
    && echo ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true | debconf-set-selections
RUN add-apt-repository ppa:libreoffice/ppa
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone

# Fetch dependencies
RUN apt-get update \
    && apt-get -y install locales build-essential \
    software-properties-common dialog apt-utils libffi-dev libmagic-dev libmagickwand-dev \
    libexempi8 exempi autoconf automake libtool ghostscript ghostscript-x icc-profiles-free \
    liblept5 libleptonica-dev libxml2 pngquant unpaper tesseract-ocr tesseract-ocr-eng \ 
    tesseract-ocr-fin tesseract-ocr-swe zlib1g zlib1g-dev ocrmypdf img2pdf git \
    python3-dev python3-pip python3-cffi python3-reportlab python3-distutils python3-pkg-resources python3-magic \
    libreoffice libreofficekit-dev hyphen-fi hyphen-sv hyphen-fr hyphen-de hyphen-en-us hyphen-it hyphen-pl hyphen-ru \
    curl ttf-mscorefonts-installer fonts-dejavu-extra fonts-freefont-otf fonts-freefont-ttf \ 
    fonts-lmodern fonts-lyx fonts-sil-gentium fonts-dustin fonts-fanwood \
    fonts-3270 fonts-font-awesome fonts-bpg-georgian fonts-opensymbol \
    texlive-fonts-recommended texlive-plain-generic texlive-latex-extra \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set locales
RUN locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8

# Install and build ExifTool 
RUN curl --remote-name https://exiftool.org/Image-ExifTool-12.58.tar.gz \
    && gzip -dc Image-ExifTool-12.58.tar.gz | tar -xf - \
    && cd Image-ExifTool-12.58 \
    && perl Makefile.PL && make install \
    && cd .. \
    && rm Image-ExifTool-12.58.tar.gz

# Install docsbox
ADD . /home/docsbox
WORKDIR /home/
RUN pip3 install --upgrade pip \
    && pip3 install -r docsbox/requirements.txt
COPY ./config/registrymodifications.xcu /root/.config/libreoffice/4/user/registrymodifications.xcu
