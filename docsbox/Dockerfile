FROM 10.188.13.135:5000/ork/sampo/dcs-libreoffice:26.1

# Fetch dependencies
RUN apt-get -qq update \
    && apt-get -qq install \
        autoconf \
        automake \
        build-essential \
        exempi \
        ghostscript \
        ghostscript-x \
        icc-profiles-free \
        img2pdf \
        libexempi8 \
        libffi-dev \
        liblept5 \
        libleptonica-dev \
        libmagic-dev \
        libmagickwand-dev \
        libtool \
        libxml2 \
        mupdf-tools \
        pngquant \
        ocrmypdf \
        poppler-data \
        poppler-utils \
        python3-cffi \
        python3-dev \
        python3-setuptools \
        python3-magic \
        python3-pip \
        python3-pkg-resources \
        python3-reportlab \
        python3-uno \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-fin \
        tesseract-ocr-swe \
        unpaper \
        zlib1g \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get -qq clean

# Install exif tool
# https://exiftool.sourceforge.net/history.html
# The most recent production release is Version 13.59
# curl -L https://sourceforge.net/projects/exiftool/files/Image-ExifTool-13.59.tar.gz/download -o Image-ExifTool-13.59.tar.gz
ARG EXIFTOOL_VERSION=13.59
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
WORKDIR /tmp
COPY ./Image-ExifTool-$EXIFTOOL_VERSION.tar.gz .
RUN gzip -dc Image-ExifTool-$EXIFTOOL_VERSION.tar.gz | tar -xf - \
    && cd Image-ExifTool-$EXIFTOOL_VERSION \
    && perl Makefile.PL && make install \
    && cd .. \
    && rm Image-ExifTool-$EXIFTOOL_VERSION.tar.gz

# Install dcs
COPY requirements.txt /home/docsbox/requirements.txt
RUN pip3 install --break-system-packages -r /home/docsbox/requirements.txt
COPY ./config/registrymodifications.xcu /root/.config/libreoffice/4/user/registrymodifications.xcu
COPY ./config/msooxml.txt /etc/magic
COPY ./config/cidfmap /tmp/cidfmap
RUN GHOSTSCRIPT_VERSION=$(ghostscript -v | grep -Po "\d+\.\d+\.\d+") && \
    cp /tmp/cidfmap /usr/share/ghostscript/$GHOSTSCRIPT_VERSION/Resource/Init/cidfmap
COPY __init__.py /home/docsbox/
COPY ./logs /home/docsbox/logs
COPY ./docs /home/docsbox/docs
COPY ./config /home/docsbox/config
COPY ./cleaner /home/docsbox/cleaner

WORKDIR /home
