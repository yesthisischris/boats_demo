FROM mcr.microsoft.com/devcontainers/python:3.10

RUN apt-get update && \
    apt-get install -y docker.io docker-compose postgresql-client && \
    rm -rf /var/lib/apt/lists/*
