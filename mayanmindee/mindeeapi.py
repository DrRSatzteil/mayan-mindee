import logging
import os

from mindee import Client, product

__all__ = []

def ocr_standard(pdf_bytes, document_name, document_type):
    client = Client(api_key=os.getenv("MINDEE_API_KEY"))
    doc = client.source_from_bytes(pdf_bytes, document_name)
    parsed_doc = client.parse(getattr(product, document_type), doc)
    return parsed_doc


def ocr_custom(pdf_bytes, document_name, account_name, endpoint_name):
    client = Client(api_key=os.getenv("MINDEE_API_KEY"))
    custom_endpoint = client.create_endpoint(
        account_name=account_name,
        endpoint_name=endpoint_name,
    )
    doc = client.source_from_bytes(pdf_bytes, document_name)
    parsed_doc = client.parse(product.CustomV1, input_source=doc, endpoint=custom_endpoint)
    return parsed_doc
