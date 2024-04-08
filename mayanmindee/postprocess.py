from schwifty import IBAN


def replace(result, parsed_doc, *args):
    if result:
        return result.replace(args[0], args[1])


def format(result, parsed_doc, *args):
    if result:
        try:
            if isinstance(result, str):
                result = float(result)
            return args[0].format(result)
        except:
            return result


def append(result, parsed_doc, *args):
    if result:
        return result + args[0]


def schwifty(result, parsed_doc, *args):
    if result:
        return result
    else:
        try:
            if not parsed_doc.document.supplier_payment_details[0].swift:
                if parsed_doc.document.supplier_payment_details[0].iban:
                    iban = IBAN(parsed_doc.document.supplier_payment_details[0].iban)
                    if iban.bic:
                        return iban.bic.formatted.replace(" ", "")
        except Exception:
            print("Could not determine BIC")
