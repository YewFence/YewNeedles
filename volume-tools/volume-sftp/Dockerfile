FROM alpine:3.22

RUN apk add --no-cache openssh-server python3

COPY entrypoint.py /usr/local/bin/volume-sftp-entrypoint
RUN chmod +x /usr/local/bin/volume-sftp-entrypoint

EXPOSE 22

ENTRYPOINT ["volume-sftp-entrypoint"]
