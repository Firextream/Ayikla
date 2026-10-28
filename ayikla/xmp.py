"""Surgical UTF-8 XMP updates. Unknown metadata and packet formatting survive."""

import re
from xml.parsers import expat

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
XMP = "http://ns.adobe.com/xap/1.0/"
DM = "http://ns.adobe.com/xmp/1.0/DynamicMedia/"
TAG = re.compile(rb'''<(?:[^>"']|"[^"]*"|'[^']*')*>''')


def merge(original: bytes | None, rating: int) -> bytes:
    if rating not in (-1, 1, 3):
        raise ValueError("Unsupported XMP rating.")
    if original is None:
        original = (f'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
                    f'<rdf:RDF xmlns:rdf="{RDF}"></rdf:RDF></x:xmpmeta>').encode()
    # Do not silently transcode an existing packet or resolve external entities.
    original.decode("utf-8-sig")
    if b"<!DOCTYPE" in original.upper() or b"<!ENTITY" in original.upper():
        raise ValueError("XMP with DTD/entities cannot be safely merged.")
    wanted = {(XMP, "Rating"): str(rating).encode(),
              (DM, "pick"): b"-1" if rating == -1 else b"1"}
    found, changes, stack = set(), [], []
    rdf = None
    parser = expat.ParserCreate(namespace_separator="|")
    parser.namespace_prefixes = True

    def parts(name):
        bits = name.split("|")
        return (bits[0], bits[1]) if len(bits) > 1 else ("", bits[0])

    def qualified(name):
        bits = name.split("|")
        return ((bits[2] + ":") if len(bits) > 2 else "") + bits[1]

    def start(name, attrs):
        nonlocal rdf
        offset = parser.CurrentByteIndex
        match = TAG.match(original, offset)
        if not match:
            raise ValueError("Unsupported XMP encoding.")
        token = match.group()
        if parts(name) == (RDF, "RDF"):
            if rdf is not None:
                raise ValueError("Multiple RDF packets cannot be safely merged.")
            rdf = (qualified(name), offset, match.end(), token.rstrip().endswith(b"/>"))
        for attr in attrs:
            field = parts(attr)
            if field in wanted:
                attr_name = qualified(attr).encode()
                pattern = re.compile(rb'(?<![\w:.-])' + re.escape(attr_name) + rb'''\s*=\s*(["'])(.*?)\1''', re.S)
                value = pattern.search(token)
                if not value:
                    raise ValueError("Could not locate XMP property.")
                changes.append((offset + value.start(2), offset + value.end(2), wanted[field]))
                found.add(field)
        stack.append((name, offset, match.end(), token.rstrip().endswith(b"/>")))

    def end(name):
        opened, offset, content, empty = stack.pop()
        field = parts(opened)
        if field in wanted:
            if empty:
                token = original[offset:content]
                replacement = token[:token.rfind(b"/>")] + b">" + wanted[field] + b"</" + qualified(opened).encode() + b">"
                changes.append((offset, content, replacement))
            else:
                closing = parser.CurrentByteIndex
                if b"<" in original[content:closing]:
                    raise ValueError("Complex rating/pick properties cannot be safely merged.")
                changes.append((content, closing, wanted[field]))
            found.add(field)

    parser.StartElementHandler, parser.EndElementHandler = start, end
    try:
        parser.Parse(original, True)
    except expat.ExpatError as error:
        raise ValueError("Existing XMP is invalid; no files changed.") from error
    if rdf is None:
        raise ValueError("Existing XMP has no RDF packet; no files changed.")
    missing = wanted.keys() - found
    if missing:
        qname, offset, content, empty = rdf
        prefix = qname.rsplit(":", 1)[0] + ":" if ":" in qname else ""
        properties = b" ".join((b"xmp:Rating" if f == (XMP, "Rating") else b"xmpDM:pick") + b'="' + wanted[f] + b'"'
                               for f in sorted(missing))
        addition = (f'<{prefix}Description xmlns:xmp="{XMP}" xmlns:xmpDM="{DM}" '.encode()
                    + properties + b"/>")
        if empty:
            token = original[offset:content]
            changes.append((offset, content, token[:token.rfind(b"/>")] + b">" + addition + f"</{qname}>".encode()))
        else:
            changes.append((content, content, addition))
    result = original
    for begin, finish, replacement in sorted(changes, reverse=True):
        result = result[:begin] + replacement + result[finish:]
    expat.ParserCreate().Parse(result, True)
    return result
