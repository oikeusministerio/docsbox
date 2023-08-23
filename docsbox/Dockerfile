FROM 10.188.13.135:5000/ork/sampo/python-libreoffice:7.2

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
