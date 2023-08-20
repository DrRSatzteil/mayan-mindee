FROM python:3

COPY docker/entrypoint.sh /entrypoint.sh
ADD mayanmindee /app/mayanmindee
COPY setup.py /app
COPY README.md /app
RUN mkdir /logs

RUN pip install --upgrade pip && python -m pip install /app

WORKDIR /app/mayanmindee
ENTRYPOINT ["/entrypoint.sh"]
CMD ["web"]
