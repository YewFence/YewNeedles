FROM alpine:3.22

RUN apk add --no-cache coreutils rsync

COPY entrypoint.sh /usr/local/bin/volume-copy-entrypoint
RUN chmod +x /usr/local/bin/volume-copy-entrypoint

ENTRYPOINT ["volume-copy-entrypoint"]
