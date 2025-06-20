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

SUPPORTED_MIMETYPES = ["application/pdf"]

__all__ = ["process_custom", "process_standard"]

fileConfig("/app/mayanmindee/config/logging.ini", disable_existing_loggers=False)
_logger = logging.getLogger(__name__)


def get_mayan_options() -> dict:
    _logger.info("Retrieve initial mayan configuration from environment")
    options = {}
    options["username"] = os.getenv("MAYAN_USER")
    options["password"] = os.getenv("MAYAN_PASSWORD")
    options["url"] = os.getenv("MAYAN_URL")
    options["oidc_url"] = os.getenv("OIDC_URL")
    if options["oidc_url"]:
        options["oidc_user"] = os.getenv("OIDC_USER")
        options["oidc_password"] = os.getenv("OIDC_PASSWORD")
        if not options["oidc_password"]:
            with open(os.getenv("OIDC_PASSWORD_FILE"), "r") as file:
                options["oidc_password"] = file.read().rstrip()
        options["oidc_client_id"] = os.getenv("OIDC_CLIENT_ID")
        options["oidc_client_secret"] = os.getenv("OIDC_CLIENT_SECRET")
        if not options["oidc_client_secret"]:
            with open(os.getenv("OIDC_CLIENT_SECRET_FILE"), "r") as file:
                options["oidc_client_secret"] = file.read().rstrip()
        options["oidc_scope"] = os.getenv("OIDC_SCOPE")
    return options


def get_mayan() -> Mayan:
    options = get_mayan_options()
    m = Mayan(options["url"])
    if options["oidc_url"]:
        m.oidcLogin(
            options["oidc_url"],
            options["oidc_user"],
            options["oidc_password"],
            options["oidc_client_id"],
            options["oidc_client_secret"],
            options["oidc_scope"],
        )
    else:
        m.login(options["username"], options["password"])
    _logger.info("Load meta informations from mayan")
    m.load()
    return m


def load_document_metadata(m: Mayan, document: dict) -> dict:
    document_metadata = {
        x["metadata_type"]["name"]: x
        for x in m.all(m.ep("metadata", base=document["url"]))
    }
    return document_metadata


def load_document(m: Mayan, document_id) -> tuple[dict, bytes]:
    _logger.info("Loading document %s", document_id)

    # Check if document exists
    document, status = m.get(m.ep(f"documents/{str(document_id)}"))
    if not isinstance(document, dict) or status != 200:
        _logger.error("Could not retrieve document")
        return None

    mimetype = document["file_latest"]["mimetype"]
    if mimetype not in SUPPORTED_MIMETYPES:
        raise Exception(
            "Mimetype "
            + mimetype
            + " is not supported. Supported mimetypes: "
            + ", ".join(SUPPORTED_MIMETYPES)
            + "."
        )

    # Load document pdf
    pdf_bytes = m.downloadfile(document["file_latest"]["url"] + "download/")

    return document, pdf_bytes


def add_metadata(
    m: Mayan, document: dict, metadata_name: str, metadata_value: str, overwrite: bool
) -> None:
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


def add_tags(m: Mayan, document: dict, tags) -> None:
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


def is_similar(seq1, seq2, confidence) -> bool:
    return fuzz.partial_token_sort_ratio(seq1.lower(), seq2.lower()) >= confidence


def post_processing(result: Any, parsed_doc, processing_steps: list) -> str:
    for step in processing_steps:
        result = getattr(postprocess, step["action"])(result, parsed_doc, *step["args"])
    return result


def cut_pages(pdf_bytes, pagelimit) -> bytes:
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


def load_config(document_type, config_type) -> dict:
    with open("/app/mayanmindee/config/api.json", "r") as f:
        config = json.load(f)

    apis = {api["documenttype"]: api for api in config[config_type]}
    if document_type not in apis:
        raise Exception("No config found for document type " + document_type)

    return apis

def getattritem(obj, attr: str) -> Any:
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

def process_standard(document_id: int, document_type: str, overwrite: bool) -> None:
    apis = load_config(document_type, "standard")

    m = get_mayan()
    document, pdf_bytes = load_document(m, document_id)
    file = cut_pages(pdf_bytes, pagelimit=apis[document_type]["pagelimit"])

    parsed_doc = ocr_standard(file, str(document_id) + ".pdf", document_type)

    if "storeocr" in apis[document_type]:
        storeocr = apis[document_type]["storeocr"]
        if storeocr:
            prediction = json.dumps(json.loads(parsed_doc.raw_http)["document"]["inference"]["prediction"])
            add_metadata(
                m,
                document,
                storeocr,
                prediction,
                True,
            )

    required_fields = defaultdict(list)
    for metadata, mapping in apis[document_type]["metadata"].items():
        required_fields[mapping["fieldname"]].append(
            (metadata, apis[document_type]["metadata"][metadata])
        )

    for field_name, metadata_mappings in required_fields.items():
        result = getattritem(parsed_doc.document.inference.prediction, field_name)
        for metadata_mapping in metadata_mappings:
            if "postprocess" in metadata_mapping[1]:
                result = post_processing(
                    result, parsed_doc, metadata_mapping[1]["postprocess"]
                )
            if result:
                if (metadata_mapping[1]["overwrite"]):
                    overwrite = metadata_mapping[1]["overwrite"];
                add_metadata(
                    m,
                    document,
                    metadata_mapping[0],
                    result,
                    overwrite
                )
        result = None

    tags = []
    required_fields = defaultdict(list)
    for tag, mapping in apis[document_type]["tags"].items():
        required_fields[mapping["fieldname"]].append(
            (tag, apis[document_type]["tags"][tag])
        )

    for field_name, tag_mappings in required_fields.items():
        result = getattritem(parsed_doc.document.inference.prediction, field_name)
        if result:
            for tag_mapping in tag_mappings:
                if is_similar(
                    result, tag_mapping[1]["match"], tag_mapping[1]["confidence"]
                ):
                    tags.insert(0, tag_mapping[0])
        result = None
    add_tags(m, document, tags)


def process_custom(document_id: int, document_type: str, synchronous: False, overwrite: bool) -> None:
    apis = load_config(document_type, "custom")

    account_name = apis[document_type]["account"]
    endpoint_name = apis[document_type]["endpoint"]
    model_version = apis[document_type]["model"]

    m = get_mayan()
    document, pdf_bytes = load_document(m, document_id)

    file = cut_pages(pdf_bytes, pagelimit=apis[document_type]["pagelimit"])

    parsed_doc = ocr_custom(
        file, str(document_id) + ".pdf", account_name, endpoint_name, model_version, synchronous
    )

    if "storeocr" in apis[document_type]:
        storeocr = apis[document_type]["storeocr"]
        if storeocr:
            prediction = json.dumps(json.loads(parsed_doc.raw_http)["document"]["inference"]["prediction"])
            add_metadata(
                m,
                document,
                storeocr,
                prediction,
                True,
            )

    required_fields = defaultdict(list)
    for metadata, mapping in apis[document_type]["metadata"].items():
        required_fields[mapping["fieldname"]].append(
            (metadata, apis[document_type]["metadata"][metadata])
        )

    for field_name, metadata_mappings in required_fields.items():
        try:
            field = parsed_doc.document.inference.prediction.fields[field_name]
        except:
            field = parsed_doc.document.inference.prediction.classifications[field_name]
        
        if hasattr(field, "value"):
            result = field.value
        else:
            result = field.contents_string()
        
        for metadata_mapping in metadata_mappings:
            if "postprocess" in metadata_mapping[1]:
                result = post_processing(
                    result, parsed_doc, metadata_mapping[1]["postprocess"]
                )
            if result:
                if metadata_mapping[1]["overwrite"]:
                    overwrite = metadata_mapping[1]["overwrite"]
                add_metadata(
                    m,
                    document,
                    metadata_mapping[0],
                    result,
                    overwrite
                )
        result = None

    tags = []
    required_fields = defaultdict(list)
    for tag, mapping in apis[document_type]["tags"].items():
        required_fields[mapping["fieldname"]].append(
            (tag, apis[document_type]["tags"][tag])
        )

    for field_name, tag_mappings in required_fields.items():
        try:
            field = parsed_doc.document.inference.prediction.fields[field_name]
        except:
            field = parsed_doc.document.inference.prediction.classifications[field_name]

        if hasattr(field, "value"):
            result = field.value
        else:
            result = field.contents_string()

        if result:
            for tag_mapping in tag_mappings:
                if is_similar(
                    result, tag_mapping[1]["match"], tag_mapping[1]["confidence"]
                ):
                    tags.insert(0, tag_mapping[0])
        result = None
    add_tags(m, document, tags)
