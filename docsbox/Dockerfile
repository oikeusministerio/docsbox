FROM ubuntu:20.04
ENV TZ Europe/Helsinki

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone

# Install prequisited
RUN apt-get update && apt-get install -y \
    software-properties-common debconf wget curl \
    locales build-essential dialog apt-utils \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install Libreoffice
RUN add-apt-repository ppa:libreoffice/ppa
# Define fonts
RUN echo debconf debconf/frontend select Noninteractive | debconf-set-selections \
    && echo ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true | debconf-set-selections
RUN apt-get update \
    && apt-get install -y fontforge cabextract fonts-dejavu-extra \
    && wget https://gist.github.com/maxwelleite/10774746/raw/ttf-vista-fonts-installer.sh -q -O - | bash \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean


# Fetch dependencies
RUN apt-get update \
    && apt-get -y install libffi-dev libmagic-dev libmagickwand-dev \
    libexempi8 exempi autoconf automake libtool ghostscript ghostscript-x icc-profiles-free \
    liblept5 libleptonica-dev libxml2 pngquant unpaper tesseract-ocr tesseract-ocr-eng \
    tesseract-ocr-fin tesseract-ocr-swe zlib1g zlib1g-dev ocrmypdf img2pdf git \
    python3-dev python3-pip python3-cffi python3-reportlab python3-distutils python3-pkg-resources python3-magic \
    libreoffice libreofficekit-dev libreoffice-script-provider-python python3-uno \
    hyphen-fi hyphen-sv hyphen-fr hyphen-de hyphen-en-us hyphen-it hyphen-pl hyphen-ru \
    ttf-mscorefonts-installer fonts-dejavu-extra fonts-freefont-otf fonts-freefont-ttf \
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
RUN curl --remote-name https://exiftool.org/Image-ExifTool-12.62.tar.gz \
    && gzip -dc Image-ExifTool-12.62.tar.gz | tar -xf - \
    && cd Image-ExifTool-12.62 \
    && perl Makefile.PL && make install \
    && cd .. \
    && rm Image-ExifTool-12.62.tar.gz

# Install docsbox
ADD requirements.txt /home/docsbox/requirements.txt
RUN pip3 install -r /home/docsbox/requirements.txt
ADD . /home/docsbox
COPY ./config/registrymodifications.xcu /root/.config/libreoffice/4/user/registrymodifications.xcu
COPY ./config/msooxml.txt /etc/magic
WORKDIR /home
