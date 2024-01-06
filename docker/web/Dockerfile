FROM python:3 as stage1

COPY docker/entrypoint.sh /app/entrypoint.sh
ADD mayanmindee /app/mayanmindee
COPY setup.py /app
COPY README.md /app
RUN pip install --upgrade pip && python -m pip install /app

# Final image
FROM python:3

COPY --from=stage1 /app /app
RUN mkdir /logs

WORKDIR /app/mayanmindee
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["web"]
