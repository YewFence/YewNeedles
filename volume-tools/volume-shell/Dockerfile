FROM debian:stable-slim

ARG EXTRA_APT_PACKAGES=""

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    bash \
    git \
    rsync \
    ca-certificates \
    coreutils \
    curl \
    file \
    findutils \
    grep \
    less \
    nano \
    sed \
    tar \
    tree \
    util-linux \
    vim \
    wget \
    ${EXTRA_APT_PACKAGES} \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /volume

CMD ["/bin/bash"]
