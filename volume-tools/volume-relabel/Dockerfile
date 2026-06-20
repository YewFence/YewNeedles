FROM alpine:3.24

RUN apk add --no-cache coreutils docker-cli python3 rsync

COPY entrypoint.py /usr/local/bin/volume-relabel-entrypoint
RUN chmod +x /usr/local/bin/volume-relabel-entrypoint

ENTRYPOINT ["volume-relabel-entrypoint"]
