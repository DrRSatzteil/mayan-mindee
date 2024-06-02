from flask import Flask
from flask import request
import os
import redis
import rq

from worker import process_standard, process_custom

__all__ = []

redis_conn = redis.from_url(os.getenv("REDIS_URL", "redis://localhost"))
# no args implies the default queue
q = rq.Queue("mayanmindee", connection=redis_conn)

app = Flask("MAYANMINDEE")

@app.route("/general/<int:document_id>", methods=["GET", "POST"])
def trigger_general(document_id):
    overwrite = request.args.get('overwrite', default=False, type=bool)
    q.enqueue(process_standard, document_id, "ProofOfAddressV1", overwrite)
    return "OK"

@app.route("/invoice/<int:document_id>", methods=["GET", "POST"])
def trigger_invoice(document_id):
    overwrite = request.args.get('overwrite', default=False, type=bool)
    q.enqueue(process_standard, document_id, "InvoiceV4", overwrite)
    return "OK"

@app.route("/custom/<api_name>/<int:document_id>", methods=["GET", "POST"])
def trigger_custom(api_name, document_id):
    synchronous = request.args.get('synchronous', default=False, type=bool)
    overwrite = request.args.get('overwrite', default=False, type=bool)
    q.enqueue(process_custom, document_id, api_name, synchronous, overwrite)
    return "OK"
