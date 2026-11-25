"""Build small photo, PDF, and Office files with known metadata dates for tests."""

import io
import struct
import zipfile

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject


def jpeg_with_exif(
    date_text: str, offset_text: str | None = None, *, digitized_text: str | None = None
) -> bytes:
    """Return a minimal JPEG whose Exif IFD holds DateTimeOriginal and the optional date tags."""
    entries: list[tuple[int, bytes]] = [(0x9003, date_text.encode() + b"\0")]
    if digitized_text:
        entries.append((0x9004, digitized_text.encode() + b"\0"))
    if offset_text is not None:
        entries.append((0x9011, offset_text.encode() + b"\0"))
    ifd0_offset = 8
    exif_ifd_offset = ifd0_offset + 2 + 12 + 4
    data_offset = exif_ifd_offset + 2 + 12 * len(entries) + 4
    exif_ifd = struct.pack("<H", len(entries))
    data = b""
    for tag, value in entries:
        exif_ifd += struct.pack("<HHII", tag, 2, len(value), data_offset + len(data))
        data += value
    exif_ifd += struct.pack("<I", 0)
    tiff = b"II*\0" + struct.pack("<I", ifd0_offset)
    tiff += (
        struct.pack("<H", 1)
        + struct.pack("<HHII", 0x8769, 4, 1, exif_ifd_offset)
        + struct.pack("<I", 0)
    )
    tiff += exif_ifd + data
    app1 = b"Exif\0\0" + tiff
    return b"\xff\xd8\xff\xe1" + struct.pack(">H", len(app1) + 2) + app1 + b"\xff\xd9"


def pdf_with_creation_date(creation_date: str, *, password: str | None = None) -> bytes:
    """Return a one-page PDF whose document info holds `creation_date`."""
    writer = PdfWriter()
    writer.add_blank_page(width=10, height=10)
    writer.add_metadata({"/CreationDate": creation_date})
    if password:
        writer.encrypt(user_password=password)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def pdf_with_xmp(
    create_date: str, *, info_creation_date: str | None = None, stream_filter: str | None = None
) -> bytes:
    """Return a one-page PDF whose XMP metadata holds `create_date`, with an optional info date and stream filter."""
    writer = PdfWriter()
    writer.add_blank_page(width=10, height=10)
    if info_creation_date is not None:
        writer.add_metadata({"/CreationDate": info_creation_date})
    xmp = DecodedStreamObject()
    xmp.set_data(
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/">'
        + f"<xmp:CreateDate>{create_date}</xmp:CreateDate>".encode()
        + b"</rdf:Description></rdf:RDF></x:xmpmeta>"
    )
    xmp[NameObject("/Type")] = NameObject("/Metadata")
    xmp[NameObject("/Subtype")] = NameObject("/XML")
    if stream_filter is not None:
        xmp[NameObject("/Filter")] = NameObject(stream_filter)
    writer.root_object[NameObject("/Metadata")] = writer._add_object(xmp)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def heic_with_open_ended_box() -> bytes:
    """Return a HEIC header followed by a box whose size of 0 means it runs to the end of the file."""
    ftyp = struct.pack(">L", 24) + b"ftypheic" + b"\0\0\0\0" + b"mif1heic"
    return ftyp + struct.pack(">L", 0) + b"meta" + b"\0" * 32


def zip_bytes(members: dict[str, str]) -> bytes:
    """Return a zip archive holding `members`, keyed by archive path."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        for name, text in members.items():
            archive.writestr(zinfo_or_arcname=name, data=text)
    return buffer.getvalue()


def office_with_created(created: str) -> bytes:
    """Return an Office-style zip whose core properties hold `created`."""
    core_xml = (
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"'
        ' xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>'
        "</cp:coreProperties>"
    )
    return zip_bytes({"docProps/core.xml": core_xml})
