FROM alpine:3.23
RUN apk add --no-cache openssh-client netcat-openbsd
USER 65532:65532
ENTRYPOINT ["ssh"]
