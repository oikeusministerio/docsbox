FROM ubuntu:20.04
ENV TZ Europe/Helsinki

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone

# Install prequisites
RUN apt-get -qq update \
    && apt-get -qq install \
        curl \
        locales \
        software-properties-common \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get -qq clean

# Set locales
RUN locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8

# Install Libreoffice
# Latest "fresh"
#RUN add-apt-repository ppa:libreoffice/ppa

# Previous "still"
#RUN add-apt-repository ppa:libreoffice/libreoffice-still

# "Old still"
#RUN add-apt-repository ppa:libreoffice/old-still

# 7.2
# Does not have packages for the new Ubuntu LTS, after upgrading LO version, upgrade to the new LTS
RUN add-apt-repository ppa:wasta-linux/libreoffice-7-2

# Define fonts
RUN echo debconf debconf/frontend select Noninteractive | debconf-set-selections \
    && echo ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true | debconf-set-selections

# Install LO, fetch dependencies, hyphenations and fonts
RUN apt-get -qq update \
    && apt-get -qq install \
        cabextract \
        fontforge \
        fonts-3270 \
        fonts-bpg-georgian \
        fonts-dejavu-extra \
        fonts-dejavu-extra \
        fonts-dustin \
        fonts-fanwood \
        fonts-font-awesome \
        fonts-freefont-otf \
        fonts-freefont-ttf \
        fonts-lmodern \
        fonts-lyx \
        fonts-opensymbol \
        fonts-sil-gentium \
        hyphen-de \
        hyphen-en-us \
        hyphen-fi \
        hyphen-fr \
        hyphen-it \
        hyphen-pl \
        hyphen-ru \
        hyphen-sv \
        libreoffice \
        libreoffice-script-provider-python \
        libreofficekit-dev \
        texlive-fonts-recommended \
        texlive-latex-extra \
        texlive-plain-generic \
        ttf-mscorefonts-installer \
    && RUN curl -sL https://gist.github.com/maxwelleite/10774746/raw/ttf-vista-fonts-installer.sh | bash \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get -qq clean
