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
    q.enqueue(process_standard, document_id, "TypeProofOfAddressV1")
    return "OK"

@app.route("/invoice/<int:document_id>", methods=["GET", "POST"])
def trigger_invoice(document_id):
    q.enqueue(process_standard, document_id, "TypeInvoiceV4")
    return "OK"

@app.route("/payroll/<int:document_id>", methods=["GET", "POST"])
def trigger_payroll(document_id):
    q.enqueue(process_custom, document_id, "Payroll")
    return "OK"
