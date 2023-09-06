FROM postgres:15
ENV POSTGRES_USER=rowboat
ENV POSTGRES_DB=rowboat
ENV POSTGRES_HOST_AUTH_METHOD=trust
COPY postgres-healthcheck.sh /usr/local/bin/
COPY initdb.sh /docker-entrypoint-initdb.d/
HEALTHCHECK CMD ["bash", "/usr/local/bin/postgres-healthcheck.sh"]
