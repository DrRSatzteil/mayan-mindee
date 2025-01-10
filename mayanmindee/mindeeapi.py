import logging
import os

from mindee import Client, product

__all__ = []

def ocr_standard(pdf_bytes, document_name, document_type):
    api_key = os.getenv("MINDEE_API_KEY");
    if not apikey:
        with open(os.getenv("MINDEE_API_KEY_FILE"), "r") as file:
            apikey = file.read().rstrip()
    client = Client(api_key=api_key)
    doc = client.source_from_bytes(pdf_bytes, document_name)
    parsed_doc = client.parse(getattr(product, document_type), doc)
    return parsed_doc


def ocr_custom(pdf_bytes, document_name, account_name, endpoint_name, model_version, synchronous=False):
    client = Client(api_key=os.getenv("MINDEE_API_KEY"))
    custom_endpoint = client.create_endpoint(
        account_name=account_name,
        endpoint_name=endpoint_name,
        version=model_version
    )
    doc = client.source_from_bytes(pdf_bytes, document_name)
    if synchronous:
        parsed_doc = client.parse(product.CustomV1, input_source=doc, include_words=True, endpoint=custom_endpoint)
    else:
        parsed_doc = client.enqueue_and_parse(product.GeneratedV1, input_source=doc, include_words=True, endpoint=custom_endpoint)
    return parsed_doc
