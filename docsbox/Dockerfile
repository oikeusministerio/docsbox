FROM 10.188.13.135:5000/ork/sampo/dcs-libreoffice:24.2

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
        pngquant \
        ocrmypdf \
        python3-cffi \
        python3-dev \
        python3-distutils \
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
ARG EXIF_TOOL_VERSION=12.77
RUN curl --remote-name https://exiftool.org/Image-ExifTool-$EXIF_TOOL_VERSION.tar.gz \
    && gzip -dc Image-ExifTool-$EXIF_TOOL_VERSION.tar.gz | tar -xf - \
    && cd Image-ExifTool-$EXIF_TOOL_VERSION \
    && perl Makefile.PL && make install \
    && cd .. \
    && rm Image-ExifTool-$EXIF_TOOL_VERSION.tar.gz

# Install dcs
ADD requirements.txt /home/docsbox/requirements.txt
RUN pip3 install -r /home/docsbox/requirements.txt
COPY ./config/registrymodifications.xcu /root/.config/libreoffice/4/user/registrymodifications.xcu
COPY ./config/msooxml.txt /etc/magic
ADD . /home/docsbox

WORKDIR /home
