FROM postgres:15

ENV POSTGRES_USER=rowboat
ENV POSTGRES_HOST_AUTH_METHOD=trust

COPY initdb.sh /docker-entrypoint-initdb.d/

