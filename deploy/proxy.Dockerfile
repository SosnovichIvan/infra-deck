FROM alpine:3.23
RUN apk add --no-cache openssh-client netcat-openbsd \
    && addgroup -g 65532 infradeck \
    && adduser -D -H -u 65532 -G infradeck infradeck
USER 65532:65532
ENTRYPOINT ["ssh"]
