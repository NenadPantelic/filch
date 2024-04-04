#!/usr/bin/zsh

# for testing
docker run --name hogwarts -e POSTGRES_USER=hogwarts -e POSTGRES_PASSWORD=pass123 -e POSTGRES_DB=hogwarts -p 5450:5432 -d postgres:13.0