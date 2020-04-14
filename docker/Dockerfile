FROM postgres:9.6.17
ENV POSTGRES_USER=rowboat
ENV POSTGRES_HOST_AUTH_METHOD=trust
COPY postgres-healthcheck.sh /usr/local/bin/
COPY initdb.sh /docker-entrypoint-initdb.d/
HEALTHCHECK CMD ["postgres-healthcheck.sh"]
