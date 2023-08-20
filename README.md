# mayan-mindee
This is an add-on for the Mayan EDMS document management system.
It adds metadata to your invoices based on any api provided by mindee (https://platform.mindee.com/). 

Credits go to m42e and the great mayan-automatic-metadata addon from which I used the mayan API implementation and the architectural blueprint.

# About Mayan Mindee

I've been using the Mayan MAM addon by m42e for a long time now. It uses a regex based approach which works well for any known documents but obviuosly does not work too well for new documents that you have not created a plugin for.
In addition to that, maintaining the plugin configurations can be a bit cumbersome.
Mayan Mindee instead relies solely on the APIs provided by mindee which use AI to extract key information from your documents.

This brings the following advantages:
- It can deal with any document, even those that you've never seen before
- Only an initial configuration for every API you want to use is required (an example configuration is provided in mayanmindee/config/api.json), no separate configurations for different document issuers
- Dates and numeric amounts are extracted very reliably compared to a regexp that gets easily confused by small OCR errors.

There is also a downside as compared to the regexp based approach:
- Text values like issuer or recipient names of documents are delivered as "guessed" by mindee. This means that they are generally provided all in upper case, German umlauts are usually not recognized and there is a high possibility that two different documents of the same type (e.g. two invoices of the same company) will be delivered with slightly different issuer names.

Therefore I still rely on the regexp based approach as a first stage and use the mindee api to only fill in the metadata that was not added by Mayan MAM in the second stage.

## HowTo

Requirements:

- Running Mayan EDMS, accessible from the node you run this on, and vice versa (for the webhook)
- A user in mayan, which is allowed to access metadata configuration, documents incl. downloading documents
- An account at mindee https://platform.mindee.com/login

Add the web and worker services to the docker-compose file to the one you are using for mayan already. See example below:

```
services:
  
  mayan-mindee-worker:
    image: drrsatzteil/mayan-mindee-worker:latest
    restart: unless-stopped
    profiles:
      - mindee
    networks:
      - mayan
    environment:
      REDIS_URL: redis://:${MAYAN_REDIS_PASSWORD:-mayanredispassword}@redis:6379/4
      MAYAN_USER: ${MAYAN_MAM_USER}
      MAYAN_PASSWORD: ${MAYAN_MAM_PASS}
      MAYAN_URL: http://app:8000/api/v4/
      MINDEE_API_KEY: ${MINDEE_API_KEY}
    volumes:
      - ./mindee/api.json:/app/mayanmindee/config/api.json
      - /etc/timezone:/etc/timezone:ro
      - /etc/localtime:/etc/localtime:ro

  mayan-mindee-web:
    image: drrsatzteil/mayan-mindee-web:latest
    restart: unless-stopped
    profiles:
      - mindee
    networks:
      - mayan
    environment:
      REDIS_URL: redis://:${MAYAN_REDIS_PASSWORD:-mayanredispassword}@redis:6379/4
    volumes:
      - /etc/timezone:/etc/timezone:ro
      - /etc/localtime:/etc/localtime:ro
```

Note that the volume mount of /app/mayanmindee/config/api.json is required as the config that is provided in this repository is only an example and needs to fine tuning for your installation.

Mayan Mindee consists of two services:

### 1. mayan-mindee-web

This service only triggers tasks for the worker.

**The following environment variables are relevant:**
- `REDIS_URL`: provide a proper redis url for the task queuing

Please note that right now it is not enough to create a new config in the api.json file but you also need to add a new endpoint in the mayanmindee/service.py file.
This might be changed in a future release so that you can add new apis only by adjusting the config file.

Currently the following endpoints (in brackets the corresponding mindee apis) are provided:
`http://mayam-mindee-web:8000/general/<document_id>` (https://platform.mindee.com/mindee/proof_of_address)
`http://mayam-mindee-web:8000/invoice/<document_id>` (https://platform.mindee.com/mindee/invoices)

The payroll endpoint is an example for a custom api and cannot be directly used by you. Instead, create and train your own api over at mindee and use this endpoint as a blueprint for your implementation.

### 2. mayan-comdirect-worker

This service receives tasks queued by the web service.

**The following environment variables are relevant:**
- `REDIS_URL`: provide a proper redis url for the task queuing
- `MAYAN_USER`: User to access Mayan EDMS
- `MAYAN_PASSWORD`: Password for MAYAN_USER
- `MAYAN_URL`: URL of the Mayan EDMS instance. Should be `http://app:8000/api/v4/` (Note that the trailing `/` is required) if on the same docker network with default service names and Mayan EDMS version v4.X.
- `MINDEE_API_KEY`: Api key from your mindee account

## Configuration

Mayan Mindee requires some configurations to be able to map the api results to the metadata in your mayan instance. To change configuration you should copy the `mayanmindee/config/api.json` file to your host machine, make your changes and mount this file as `/app/mayanmindee/config/api.json` in your worker container.

The config file has separate sections for custom apis (self-created) and standard apis (provided by mindee).
The provision of postprocess actions is optional and provided as example below.
See mayanmindee/postprocess.py for available postprocessing actions.
See full example of config file in mayanmindee/config/api.json.

```
{
    "custom": [
        {
            "documenttype": <String: Can be anything but must be unique>,
            "account": <String: Mindee account, see documentation over at mindee>,
            "endpoint": <String: Name of the endpoint as defined over at mindee>,
            "pagelimit": <Integer: Limits the number of pages sent to mindee (see api limits and it may be used to save you cost). All pages exeeding the limit will be removed before the documents gets sent>,
            "metadata": {
                <String: Label of your 1st metadata type in mayan>: {
                    "fieldname": <String: Name of the field in the mindee api, equals the name of the field in the api. For standard apis (see below) this gets a bit more complicated, please see api documentation at mindee or debug an api response to see the exact fields>,
                    "overwrite": <Boolean: true -> Overwrite existing metadata value in mayan, false -> don't overwrite>
                },
                <String: Label of your 2nd metadata type in mayan>: {
                    "fieldname": <See above>,
                    "overwrite": <See above>,
                    "postprocess": [
                        {
                            "action": "replace",
                            "args": [",", ""]
                        },
                        {
                            "action": "replace",
                            "args": [".", ","]
                        },
                        {
                            "action": "append",
                            "args": ["€"]
                        }
                    ]
                },
            },
            "tags": {
                <String: Label of the tag in mayan>: {
                    "fieldname": <See above>,
                    "match": <String: String that should be matched (see partial ratio section in https://pypi.org/project/thefuzz/)>,
                    "confidence": <Integer: Minimum ratio for match in the range 0-100, 0: Always write tag, 100 only exact match writes tag>
                }
            }
        }
    ],
    "standard": [
        {
            "documenttype": "TypeInvoiceV4",
            "pagelimit": 10,
            "metadata": {
                "receiptdate": {
                    "fieldname": "invoice_date.value",
                    "overwrite": false
                },
                "issuer": {
                    "fieldname": "supplier_name.value",
                    "overwrite": false
                },
                "invoicenumber": {
                    "fieldname": "invoice_number.value",
                    "overwrite": false
                },
                "invoiceamount": {
                    "fieldname": "total_amount.value",
                    "overwrite": false,
                    "postprocess": [
                        {
                            "action": "format",
                            "args": ["{:.2f}"]
                        },
                        {
                            "action": "replace",
                            "args": [",", ""]
                        },
                        {
                            "action": "replace",
                            "args": [".", ","]
                        },
                        {
                            "action": "append",
                            "args": ["€"]
                        }
                    ]
                },
                "iban": {
                    "fieldname": "supplier_payment_details[0].iban",
                    "overwrite": false
                },
                "bic": {
                    "fieldname": "supplier_payment_details[0].swift",
                    "overwrite": false,
                    "postprocess": [
                        {
                            "action": "schwifty",
                            "args": []
                        }
                    ]
                }
            },
            "tags": {
                "Augustus": {
                    "fieldname": "customer_name",
                    "match": "augustus gloop",
                    "confidence": 85
                },
                "Violet": {
                    "fieldname": "customer_name",
                    "match": "violet beauregarde",
                    "confidence": 85
                },
                "Rechnung": {
                    "fieldname": "customer_name",
                    "match": "",
                    "confidence": 0
                }
            }
        },
        {
            "documenttype": "TypeProofOfAddressV1",
            "pagelimit": 3,
            "metadata": {
                "receiptdate": {
                    "fieldname": "date.value",
                    "overwrite": false
                },
                "issuer": {
                    "fieldname": "issuer_name.value",
                    "overwrite": false
                }
            },
            "tags": {
                "Joe": {
                    "fieldname": "recipient_name.value",
                    "match": "granpa joe",
                    "confidence": 85
                },
                "Josephine": {
                    "fieldname": "recipient_name.value",
                    "match": "grandma josephine",
                    "confidence": 85
                },
                "General": {
                    "fieldname": "recipient_name.value",
                    "match": "",
                    "confidence": 0
                }
            }
        }
    ]
}

```