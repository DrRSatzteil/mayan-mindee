import io
import json
import logging
import operator
import os
import re
from collections import defaultdict
from logging.config import fileConfig
from typing import Any

import postprocess
from mayanapi import Mayan
from mindeeapi import ocr_custom, ocr_standard
from PyPDF2 import PdfReader, PdfWriter
from thefuzz import fuzz

__all__ = ["process_custom", "process_standard"]

fileConfig("/app/mayanmindee/config/logging.ini", disable_existing_loggers=False)
_logger = logging.getLogger(__name__)


def get_mayan_options() -> dict:
    _logger.info("Retrieve initial mayan configuration from environment")
    options = {}
    options["username"] = os.getenv("MAYAN_USER")
    options["password"] = os.getenv("MAYAN_PASSWORD")
    options["url"] = os.getenv("MAYAN_URL")
    return options


def get_mayan() -> Mayan:
    options = get_mayan_options()
    m = Mayan(options["url"])
    m.login(options["username"], options["password"])
    _logger.info("Load meta informations from mayan")
    m.load()
    return m


def load_document_metadata(m: Mayan, document: dict):
    document_metadata = {
        x["metadata_type"]["name"]: x
        for x in m.all(m.ep("metadata", base=document["url"]))
    }
    return document_metadata


def load_document(m: Mayan, document_id):
    _logger.info("Loading document %s", document_id)

    # Check if document exists
    # TODO check MIMETYPE
    document, status = m.get(m.ep(f"documents/{str(document_id)}"))
    if not isinstance(document, dict) or status != 200:
        _logger.error("Could not retrieve document")
        return None

    # Load document pdf
    pdf_bytes = m.downloadfile(document["file_latest"]["download_url"])

    return document, pdf_bytes


def add_metadata(
    m: Mayan, document: dict, metadata_name: str, metadata_value: str, overwrite: bool
):
    for meta in m.document_types[document["document_type"]["label"]]["metadatas"]:
        meta_name = meta["metadata_type"]["name"]
        if meta_name == metadata_name:
            document_metadata = load_document_metadata(m, document)
            if meta_name not in document_metadata:
                _logger.info(
                    "Add metadata %s (value: %s) to %s",
                    meta_name,
                    metadata_value,
                    document["url"],
                )
                data = {
                    "metadata_type_id": meta["metadata_type"]["id"],
                    "value": metadata_value,
                }
                result = m.post(m.ep("metadata", base=document["url"]), json_data=data)
            else:
                if overwrite:
                    data = {"value": metadata_value}
                    result = m.put(
                        m.ep(
                            "metadata/{}".format(document_metadata[meta_name]["id"]),
                            base=document["url"],
                        ),
                        json_data=data,
                    )
            break


def add_tags(m: Mayan, document: dict, tags):
    tags.append("MAM")
    for t in tags:
        if t not in m.tags:
            _logger.info("Tag %s not defined in system", t)
        else:
            data = {"tag": m.tags[t]["id"]}
            _logger.debug(
                "Trying to attach Tag "
                + t
                + " with tag id "
                + str(data["tag"])
                + " to document"
            )
            result = m.post(m.ep("tags/attach", base=document["url"]), json_data=data)


def is_similar(seq1, seq2, confidence):
    return fuzz.partial_ratio(seq1.lower(), seq2.lower()) >= confidence


def getattritem(obj, attr: str):
    steps = list(filter(None, re.split(r"\[(\d+)\]", attr)))
    a = iter(steps)
    pairs = zip(a, a)
    for pair in pairs:
        obj = operator.itemgetter(int(pair[1]))(
            operator.attrgetter(pair[0].lstrip("."))(obj)
        )
    if len(steps) % 2 > 0:
        obj = operator.attrgetter(steps[-1].lstrip("."))(obj)
    return obj


def post_processing(result: Any, parsed_doc, processing_steps: list):
    for step in processing_steps:
        result = getattr(postprocess, step["action"])(result, parsed_doc, *step["args"])
    return result


def cut_pages(pdf_bytes, pagelimit):
    infile = PdfReader(io.BytesIO(pdf_bytes))
    output = PdfWriter()
    if pagelimit < len(infile.pages):
        for i in range(pagelimit):
            p = infile.pages[i]
            output.add_page(p)
        with io.BytesIO() as f:
            output.write(f)
            f.flush()
            return f.getvalue()
    else:
        return pdf_bytes


def process_standard(document_id, document_type: str):
    with open("/app/mayanmindee/config/api.json", "r") as f:
        config = json.load(f)

    apis = {api["documenttype"]: api for api in config["standard"]}
    if document_type not in apis:
        raise Exception("No config found for document type " + document_type)

    m = get_mayan()
    document, pdf_bytes = load_document(m, document_id)

    file = cut_pages(pdf_bytes, pagelimit=apis[document_type]["pagelimit"])

    parsed_doc = ocr_standard(file, str(document_id) + ".pdf", document_type)

    required_fields = defaultdict(list)
    for metadata, mapping in apis[document_type]["metadata"].items():
        required_fields[mapping["fieldname"]].append(
            (metadata, apis[document_type]["metadata"][metadata])
        )

    for field_name, metadata_mappings in required_fields.items():
        try:
            result = getattritem(parsed_doc.document, field_name)
        except:
            print("Could not retrieve property " + field_name)

        for metadata_mapping in metadata_mappings:
            if "postprocess" in metadata_mapping[1]:
                result = post_processing(
                    result, parsed_doc, metadata_mapping[1]["postprocess"]
                )
            if result:
                add_metadata(
                    m,
                    document,
                    metadata_mapping[0],
                    result,
                    metadata_mapping[1]["overwrite"],
                )
        result = None

    tags = []
    required_fields = defaultdict(list)
    for tag, mapping in apis[document_type]["tags"].items():
        required_fields[mapping["fieldname"]].append(
            (tag, apis[document_type]["tags"][tag])
        )

    for field_name, tag_mappings in required_fields.items():
        result = getattritem(parsed_doc.document, field_name)
        if result:
            for tag_mapping in tag_mappings:
                if is_similar(
                    result, tag_mapping[1]["match"], tag_mapping[1]["confidence"]
                ):
                    tags.insert(0, tag_mapping[0])
        result = None
    add_tags(m, document, tags)


def process_custom(document_id, document_type: str):
    # TODO: This is ok for the docker container but actually should not be an absolute path...
    with open("/app/mayanmindee/config/api.json", "r") as f:
        config = json.load(f)

    apis = {api["documenttype"]: api for api in config["custom"]}
    if document_type not in apis:
        raise Exception("No config found for document type " + document_type)

    account_name = apis[document_type]["account"]
    endpoint_name = apis[document_type]["endpoint"]

    m = get_mayan()
    document, pdf_bytes = load_document(m, document_id)

    file = cut_pages(pdf_bytes, pagelimit=apis[document_type]["pagelimit"])

    parsed_doc = ocr_custom(
        file, str(document_id) + ".pdf", account_name, endpoint_name
    )

    required_fields = defaultdict(list)
    for metadata, mapping in apis[document_type]["metadata"].items():
        required_fields[mapping["fieldname"]].append(
            (metadata, apis[document_type]["metadata"][metadata])
        )

    for field_name, metadata_mappings in required_fields.items():
        result = parsed_doc.document.fields[field_name].contents_string()
        for metadata_mapping in metadata_mappings:
            if "postprocess" in metadata_mapping[1]:
                result = post_processing(
                    result, parsed_doc, metadata_mapping[1]["postprocess"]
                )
            if result:
                add_metadata(
                    m,
                    document,
                    metadata_mapping[0],
                    result,
                    metadata_mapping[1]["overwrite"],
                )
        result = None

    tags = []
    required_fields = defaultdict(list)
    for tag, mapping in apis[document_type]["tags"].items():
        required_fields[mapping["fieldname"]].append(
            (tag, apis[document_type]["tags"][tag])
        )

    for field_name, tag_mappings in required_fields.items():
        result = parsed_doc.document.fields[field_name].contents_string()
        if result:
            for tag_mapping in tag_mappings:
                if is_similar(
                    result, tag_mapping[1]["match"], tag_mapping[1]["confidence"]
                ):
                    tags.insert(0, tag_mapping[0])
        result = None
    add_tags(m, document, tags)