import logging
import os

from mindee import Client, product

__all__ = []

def ocr_standard(pdf_bytes, document_name, document_type):
    client = Client(api_key=os.getenv("MINDEE_API_KEY"))
    doc = client.doc_from_bytes(pdf_bytes, document_name)
    parsed_doc = doc.parse(getattr(product, document_type))
    return parsed_doc


def ocr_custom(pdf_bytes, document_name, account_name, endpoint_name):
    client = Client(api_key=os.getenv("MINDEE_API_KEY")).create_endpoint(
        account_name=account_name,
        endpoint_name=endpoint_name,
    )
    doc = client.doc_from_bytes(pdf_bytes, document_name)
    parsed_doc = doc.parse(product.TypeCustomV1, endpoint_name=endpoint_name)
    return parsed_doc
