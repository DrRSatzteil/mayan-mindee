#!/bin/bash

if [ "$1" == "rq" ]; then
    echo "rq mode"
    rq worker mayanmindee --path /app/mayanmindee -vvv --url $REDIS_URL
fi

if [ "$1" == "web" ]; then
    echo "web mode"
    gunicorn service:app --chdir /app/mayanmindee --error-logfile - -b '0.0.0.0:8000'
fi
