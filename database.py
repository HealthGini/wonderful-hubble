"""
Database management for GoodDeeds.space.

This module handles SQLite database connections, schema initialization,
password hashing, and demo data seeding.
"""

import sqlite3
import hashlib
import json
import os
import base64
import re
import zlib
from datetime import datetime

# Ensure DB is created next to this script by default unless DB_PATH is set
DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gooddeeds.db")
DB_PATH = os.environ.get("DB_PATH", DEFAULT_DB)

def get_db():
    """
    Establishes a connection to the SQLite database.
    
    Sets the row factory to sqlite3.Row for dictionary-like access
    and enables foreign key support.
    
    Returns:
        sqlite3.Connection: The database connection object.
    """
    db_dir = os.path.dirname(os.path.abspath(DB_PATH))
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn

def hash_password(password: str) -> str:
    """
    Hashes a plain text password using PBKDF2-HMAC-SHA256 with a random 16-byte salt
    and 100,000 iterations.
    
    Args:
        password: The plain text password to hash.
        
    Returns:
        str: Formatted string 'pbkdf2_sha256$100000$<salt_hex>$<hash_hex>'
    """
    iterations = 100000
    salt_bytes = os.urandom(16)
    salt_hex = salt_bytes.hex()
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations)
    return f"pbkdf2_sha256${iterations}${salt_hex}${derived.hex()}"

DEMO_PERSONA_EMAILS = (
    "maya@gooddeeds.space",
    "marcus@gooddeeds.space",
    "elena@gooddeeds.space",
    "arthur@gooddeeds.space",
    "priya@gooddeeds.space",
    "samir@gooddeeds.space",
    "rosa@gooddeeds.space",
    "chloe@gooddeeds.space",
)


def is_demo_seed_enabled() -> bool:
    """Returns True only when SEED_DEMO=1 (or true/yes) is explicitly enabled for dev/test."""
    return (os.environ.get("SEED_DEMO") or "").strip().lower() in ("1", "true", "yes")


def get_configured_admin_emails() -> list:
    """Returns lowercased email addresses configured via ADMIN_EMAIL (comma-separated)."""
    raw = (os.environ.get("ADMIN_EMAIL") or "").strip()
    if not raw:
        return []
    return [addr.strip().lower() for addr in raw.split(",") if addr.strip()]


def make_locked_account_hash(label: str = "DEMO_ACCOUNT") -> str:
    """Generates a non-authenticatable password_hash marker for showcase/locked persona rows."""
    return f"LOCKED_{label}${os.urandom(32).hex()}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """
    Verifies a plain text password against a stored salted PBKDF2 hash
    (with transparent fallback for legacy SHA-256 hashes during migration).
    """
    import hmac
    if not stored_hash or not plain_password:
        return False
    if str(stored_hash).startswith("LOCKED_"):
        return False
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            parts = stored_hash.split("$")
            iterations = int(parts[1])
            salt_bytes = bytes.fromhex(parts[2])
            expected_hex = parts[3]
            derived = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt_bytes, iterations)
            return hmac.compare_digest(derived.hex(), expected_hex)
        except Exception:
            return False
    # Legacy unsalted SHA-256 fallback
    legacy_hex = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy_hex, stored_hash)

import html as html_lib
import io
import ipaddress
import shutil
import socket
import subprocess
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile


MAX_EXTRACTED_TEXT_CHARS = 250000
MAX_ZIP_EXTRACT_BYTES = 15 * 1024 * 1024
MAX_REMOTE_DOC_BYTES = 8 * 1024 * 1024


def _sanitize_extracted_text(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > MAX_EXTRACTED_TEXT_CHARS:
        cleaned = cleaned[:MAX_EXTRACTED_TEXT_CHARS].rsplit(" ", 1)[0]
    return cleaned


def _humanize_filename_tokens(name_or_url: str) -> str:
    if not name_or_url:
        return ""
    try:
        decoded = urllib.parse.unquote(name_or_url).strip()
    except Exception:
        decoded = name_or_url.strip()
    spaced = re.sub(r"[_\-+/.()\[\]]+", " ", decoded)
    spaced = re.sub(r"\s+", " ", spaced).strip()
    if spaced and spaced.lower() != decoded.lower():
        return f"{decoded} {spaced}"
    return decoded


def strip_base64_payloads(resource_url) -> str:
    """
    Removes raw ';base64,<payload>' blocks from data URIs while preserving URLs and ';name=...' metadata.
    Prevents random Base64 character sequences from causing false-positive search or moderation matches.
    """
    if not resource_url:
        return ""
    if isinstance(resource_url, (list, tuple)):
        return " ".join(filter(None, (strip_base64_payloads(x) for x in resource_url)))
    if isinstance(resource_url, dict):
        return " ".join(filter(None, (strip_base64_payloads(v) for v in resource_url.values())))
    raw = str(resource_url).strip()
    if not raw:
        return ""
    if raw.startswith("[") or raw.startswith("{"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, (list, tuple, dict)):
                return strip_base64_payloads(parsed)
        except Exception:
            pass
    cleaned = re.sub(r";base64,[A-Za-z0-9+/=%\s]+", ";base64,", raw, flags=re.IGNORECASE)
    try:
        cleaned = urllib.parse.unquote(cleaned)
    except Exception:
        pass
    return cleaned


def _decode_pdf_literal_string(raw_s: str) -> str:
    out = []
    i = 0
    n = len(raw_s)
    while i < n:
        ch = raw_s[i]
        if ch == "\\" and i + 1 < n:
            nxt = raw_s[i + 1]
            if nxt == "n":
                out.append("\n")
                i += 2
            elif nxt == "r":
                out.append("\r")
                i += 2
            elif nxt == "t":
                out.append("\t")
                i += 2
            elif nxt == "b":
                out.append("\b")
                i += 2
            elif nxt == "f":
                out.append("\f")
                i += 2
            elif nxt in ("(", ")", "\\"):
                out.append(nxt)
                i += 2
            elif nxt == "\r":
                i += 3 if (i + 2 < n and raw_s[i + 2] == "\n") else 2
            elif nxt == "\n":
                i += 2
            elif "0" <= nxt <= "7":
                oct_digits = nxt
                i += 2
                for _ in range(2):
                    if i < n and "0" <= raw_s[i] <= "7":
                        oct_digits += raw_s[i]
                        i += 1
                    else:
                        break
                out.append(chr(int(oct_digits, 8) & 0xFF))
            else:
                out.append(nxt)
                i += 2
        else:
            out.append(ch)
            i += 1

    res_bytes = "".join(out).encode("latin1", errors="ignore")
    if res_bytes.startswith(b"\xfe\xff"):
        return res_bytes[2:].decode("utf-16-be", errors="ignore")
    if res_bytes.startswith(b"\xff\xfe"):
        return res_bytes[2:].decode("utf-16-le", errors="ignore")
    return res_bytes.decode("cp1252", errors="ignore")


def _decode_cmap_target_hex(dst_hex: str) -> str:
    if not dst_hex:
        return ""
    if len(dst_hex) % 2 == 1:
        dst_hex = "0" + dst_hex
    try:
        raw = bytes.fromhex(dst_hex)
        if len(raw) >= 2 and len(raw) % 2 == 0:
            return raw.decode("utf-16-be", errors="ignore")
        return raw.decode("latin1", errors="ignore")
    except Exception:
        return ""


def _parse_pdf_cmap(s_lat: str, cmap: dict):
    for bm in re.finditer(r"beginbfchar(.*?)endbfchar", s_lat, re.DOTALL):
        for src, dst in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", bm.group(1)):
            val = _decode_cmap_target_hex(dst)
            if val:
                cmap[src.upper()] = val

    for rm in re.finditer(r"beginbfrange(.*?)endbfrange", s_lat, re.DOTALL):
        body = rm.group(1)
        # Form 1: <start> <end> [<dst1> <dst2> ...]
        for s_hex, e_hex, arr_body in re.findall(
            r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*\[(.*?)\]", body, re.DOTALL
        ):
            try:
                start_code = int(s_hex, 16)
                end_code = int(e_hex, 16)
                kl = len(s_hex)
                targets = re.findall(r"<([0-9A-Fa-f]+)>", arr_body)
                for offset, t_hex in enumerate(targets[: max(0, end_code - start_code + 1)]):
                    val = _decode_cmap_target_hex(t_hex)
                    if val:
                        cmap[f"{start_code + offset:0{kl}X}"] = val
            except Exception:
                pass

        # Form 2: <start> <end> <dstStart>
        body_no_arrays = re.sub(r"\[.*?\]", " ", body, flags=re.DOTALL)
        for s_hex, e_hex, d_hex in re.findall(
            r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", body_no_arrays
        ):
            try:
                start_code = int(s_hex, 16)
                end_code = int(e_hex, 16)
                kl = len(s_hex)
                base_str = _decode_cmap_target_hex(d_hex)
                if not base_str:
                    continue
                for offset in range(min(max(0, end_code - start_code + 1), 512)):
                    k_str = f"{start_code + offset:0{kl}X}"
                    if len(base_str) == 1:
                        cp = ord(base_str) + offset
                        if 0 <= cp <= 0x10FFFF:
                            cmap[k_str] = chr(cp)
                    else:
                        cp = ord(base_str[-1]) + offset
                        if 0 <= cp <= 0x10FFFF:
                            cmap[k_str] = base_str[:-1] + chr(cp)
            except Exception:
                pass


def _decode_pdf_hex_string(hex_str: str, cmap: dict) -> str:
    if not hex_str:
        return ""
    if len(hex_str) % 2 == 1:
        hex_str += "0"
    upper_hex = hex_str.upper()
    if upper_hex.startswith("FEFF") and len(upper_hex) >= 4:
        try:
            return bytes.fromhex(upper_hex[4:]).decode("utf-16-be", errors="ignore")
        except Exception:
            pass
    if cmap:
        key_lens = sorted({len(k) for k in cmap.keys() if k}, reverse=True)
        for kl in key_lens:
            if kl > 0 and len(upper_hex) % kl == 0:
                chunks = [upper_hex[k : k + kl] for k in range(0, len(upper_hex), kl)]
                if any(c in cmap for c in chunks):
                    out = []
                    for c in chunks:
                        if c in cmap:
                            out.append(cmap[c])
                        else:
                            try:
                                raw_c = bytes.fromhex(c)
                                out.append(
                                    raw_c.decode("utf-16-be" if kl == 4 else "cp1252", errors="ignore")
                                )
                            except Exception:
                                pass
                    return "".join(out)
    try:
        raw = bytes.fromhex(upper_hex)
        if len(raw) >= 2 and len(raw) % 2 == 0 and raw[0] == 0:
            return raw.decode("utf-16-be", errors="ignore")
        return raw.decode("cp1252", errors="ignore")
    except Exception:
        return ""


def _parse_pdf_tj_array(arr_content: str, cmap: dict) -> str:
    parts = []
    i = 0
    n = len(arr_content)
    while i < n:
        ch = arr_content[i]
        if ch == "(":
            depth = 1
            j = i + 1
            while j < n and depth > 0:
                if arr_content[j] == "\\":
                    j += 2
                    continue
                if arr_content[j] == "(":
                    depth += 1
                elif arr_content[j] == ")":
                    depth -= 1
                j += 1
            parts.append(_decode_pdf_literal_string(arr_content[i + 1 : max(i + 1, j - 1)]))
            i = j
        elif ch == "<":
            end = arr_content.find(">", i + 1)
            if end == -1:
                break
            hex_str = re.sub(r"\s+", "", arr_content[i + 1 : end])
            parts.append(_decode_pdf_hex_string(hex_str, cmap))
            i = end + 1
        elif ch in "-+.0123456789":
            m = re.match(r"[-+]?(?:\d+\.?\d*|\.\d+)", arr_content[i:])
            if m:
                try:
                    val = float(m.group(0))
                    # ISO 32000-1 §9.4.3: negative values >= 120 thousandths of text space shift right -> word space
                    if val <= -120:
                        if parts and not parts[-1].endswith((" ", "\n", "\t")):
                            parts.append(" ")
                except ValueError:
                    pass
                i += len(m.group(0))
            else:
                i += 1
        else:
            i += 1
    return "".join(parts)


def _extract_pdf_text_stdlib(pdf_bytes: bytes) -> str:
    """
    Pure-Python ISO-32000 PDF text extractor supporting FlateDecode streams, Object Streams (/ObjStm),
    /ToUnicode CMaps (beginbfchar & beginbfrange), TJ kerning arrays, Tj/'/\" operators, UTF-16BE strings,
    and AcroForm field values (/V).
    """
    if not pdf_bytes:
        return ""

    decoded_streams = []
    for m in re.finditer(rb"stream(?:\r\n|\n)", pdf_bytes):
        dict_window = pdf_bytes[max(0, m.start() - 320) : m.start()]
        start = m.end()
        end = -1
        len_m = re.search(rb"/Length\s+(\d+)(?!\s+\d+\s+R)", dict_window)
        if len_m:
            declared_len = int(len_m.group(1))
            cand_end = start + declared_len
            if cand_end <= len(pdf_bytes) and b"endstream" in pdf_bytes[cand_end : cand_end + 32]:
                end = cand_end
        if end == -1:
            end = pdf_bytes.find(b"endstream", start)
        if end == -1:
            continue
        raw_stream = pdf_bytes[start:end].rstrip(b"\r\n")
        dec = None
        for wb in (zlib.MAX_WBITS, -zlib.MAX_WBITS, 16 + zlib.MAX_WBITS):
            try:
                dec = zlib.decompress(raw_stream, wb)
                break
            except Exception:
                pass
        decoded_streams.append((dict_window, dec if dec is not None else raw_stream))

    cmap = {}
    all_stream_texts = []
    for dict_window, dec in decoded_streams:
        s_lat = dec.decode("latin1", errors="ignore")
        all_stream_texts.append(s_lat)
        if "beginbfchar" in s_lat or "beginbfrange" in s_lat:
            _parse_pdf_cmap(s_lat, cmap)

    lines_out = []
    for s_lat in all_stream_texts:
        if "BT" not in s_lat:
            continue
        for bt in re.finditer(r"(?<![A-Za-z0-9/])BT(?![A-Za-z0-9])(.*?)(?<![A-Za-z0-9/])ET(?![A-Za-z0-9])", s_lat, re.DOTALL):
            blk = bt.group(1)
            blk_parts = []
            moved_since_last_text = False
            i = 0
            n = len(blk)
            while i < n:
                ch = blk[i]
                if ch == "%":
                    nl = blk.find("\n", i)
                    i = n if nl == -1 else nl + 1
                    continue
                if ch == "[":
                    j = i + 1
                    while j < n and blk[j] != "]":
                        if blk[j] == "(":
                            d = 1
                            j += 1
                            while j < n and d > 0:
                                if blk[j] == "\\":
                                    j += 2
                                    continue
                                if blk[j] == "(":
                                    d += 1
                                elif blk[j] == ")":
                                    d -= 1
                                j += 1
                        else:
                            j += 1
                    after = blk[j + 1 : j + 12].lstrip()
                    if after.startswith("TJ"):
                        seg = _parse_pdf_tj_array(blk[i + 1 : j], cmap)
                        if seg:
                            if moved_since_last_text and blk_parts and not blk_parts[-1].endswith((" ", "\n", "\t")):
                                blk_parts.append(" ")
                            blk_parts.append(seg)
                            moved_since_last_text = False
                    i = j + 1
                elif ch == "(":
                    d = 1
                    j = i + 1
                    while j < n and d > 0:
                        if blk[j] == "\\":
                            j += 2
                            continue
                        if blk[j] == "(":
                            d += 1
                        elif blk[j] == ")":
                            d -= 1
                        j += 1
                    after = blk[j : j + 12].lstrip()
                    if after.startswith(("Tj", "'", '"')):
                        seg = _decode_pdf_literal_string(blk[i + 1 : max(i + 1, j - 1)])
                        if seg:
                            if (moved_since_last_text or after.startswith(("'", '"'))) and blk_parts and not blk_parts[-1].endswith((" ", "\n", "\t")):
                                blk_parts.append(" ")
                            blk_parts.append(seg)
                            moved_since_last_text = False
                    i = j
                elif ch == "<" and (i + 1 < n and blk[i + 1] != "<"):
                    end = blk.find(">", i + 1)
                    if end == -1:
                        break
                    after = blk[end + 1 : end + 12].lstrip()
                    if after.startswith(("Tj", "'", '"')):
                        seg = _decode_pdf_hex_string(re.sub(r"\s+", "", blk[i + 1 : end]), cmap)
                        if seg:
                            if (moved_since_last_text or after.startswith(("'", '"'))) and blk_parts and not blk_parts[-1].endswith((" ", "\n", "\t")):
                                blk_parts.append(" ")
                            blk_parts.append(seg)
                            moved_since_last_text = False
                    i = end + 1
                elif ch in ("T", "'"):
                    op_m = re.match(r"(?:Td|TD|Tm|T\*)(?![A-Za-z0-9])", blk[i:])
                    if op_m:
                        moved_since_last_text = True
                        i += len(op_m.group(0))
                    else:
                        i += 1
                else:
                    i += 1
            joined = "".join(blk_parts).strip()
            if joined:
                lines_out.append(re.sub(r"\s+", " ", joined))

    # Extract AcroForm text field values (/V (...)) if present
    raw_no_streams = re.sub(rb"stream(?:\r\n|\n).*?endstream", b" ", pdf_bytes, flags=re.DOTALL)
    header_lat = raw_no_streams.decode("latin1", errors="ignore")
    for vm in re.finditer(r"/V\s*\(((?:\\.|[^\\)])+)\)", header_lat):
        val = _decode_pdf_literal_string(vm.group(1)).strip()
        if val and val not in ("Off", "Yes"):
            lines_out.append(val)

    # Fallback for minimal uncompressed/synthetic PDFs without BT..ET operators
    if not lines_out:
        stripped_meta = re.sub(
            r"/(?:Author|Creator|Producer|CreationDate|ModDate|Lang|Title|Subject|Keywords)\s*\((?:\\.|[^\\)])*\)",
            " ",
            header_lat,
        )
        for pm in re.finditer(r"\(((?:\\.|[^\\)]){2,})\)", stripped_meta):
            val = _decode_pdf_literal_string(pm.group(1)).strip()
            if val and any(c.isalpha() for c in val):
                lines_out.append(val)

    return _sanitize_extracted_text(" ".join(lines_out))


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """
    Multi-tier PDF text extraction:
      1. pypdf (pure-Python library installed via requirements.txt in production)
      2. pdftotext CLI (Poppler C++ binary when installed on host OS)
      3. _extract_pdf_text_stdlib (zero-dependency pure-Python ISO-32000 parser)
    """
    if not pdf_bytes:
        return ""

    # Tier 1: pypdf
    try:
        import pypdf  # type: ignore
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes), strict=False)
        chunks = []
        for page in reader.pages:
            try:
                t = page.extract_text() or ""
                if t.strip():
                    chunks.append(t)
            except Exception:
                pass
        try:
            fields = reader.get_form_text_fields() or {}
            for fv in fields.values():
                if fv and str(fv).strip():
                    chunks.append(str(fv).strip())
        except Exception:
            pass
        joined = _sanitize_extracted_text(" ".join(chunks))
        if joined:
            return joined
    except Exception:
        pass

    # Tier 2: pdftotext CLI (via stdin/stdout, zero temp files)
    pdftotext_bin = shutil.which("pdftotext")
    if pdftotext_bin:
        try:
            proc = subprocess.run(
                [pdftotext_bin, "-enc", "UTF-8", "-nopgbrk", "-", "-"],
                input=pdf_bytes,
                capture_output=True,
                timeout=6,
            )
            if proc.returncode == 0 and proc.stdout:
                cli_text = _sanitize_extracted_text(proc.stdout.decode("utf-8", errors="ignore"))
                if cli_text:
                    return cli_text
        except Exception:
            pass

    # Tier 3: Built-in pure-Python stdlib parser
    return _extract_pdf_text_stdlib(pdf_bytes)


def _local_xml_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _extract_docx_xml_text(xml_bytes: bytes) -> str:
    root = ET.fromstring(xml_bytes)
    paragraphs = []
    for elem in root.iter():
        if _local_xml_tag(elem.tag) == "p":
            parts = []
            for sub in elem.iter():
                stag = _local_xml_tag(sub.tag)
                if stag == "t" and sub.text:
                    parts.append(sub.text)
                elif stag == "tab":
                    parts.append(" ")
                elif stag in ("br", "cr"):
                    parts.append("\n")
            line = "".join(parts).strip()
            if line:
                paragraphs.append(line)
    return "\n".join(paragraphs)


def _extract_pptx_xml_text(xml_bytes: bytes) -> str:
    root = ET.fromstring(xml_bytes)
    paragraphs = []
    for elem in root.iter():
        if _local_xml_tag(elem.tag) == "p":
            parts = [sub.text for sub in elem.iter() if _local_xml_tag(sub.tag) == "t" and sub.text]
            line = "".join(parts).strip()
            if line:
                paragraphs.append(line)
    return "\n".join(paragraphs)


def _extract_xlsx_text(zf: zipfile.ZipFile, names_set: set) -> str:
    shared_strings = []
    if "xl/sharedStrings.xml" in names_set:
        try:
            ss_bytes = zf.read("xl/sharedStrings.xml")
            if len(ss_bytes) <= MAX_ZIP_EXTRACT_BYTES:
                ss_root = ET.fromstring(ss_bytes)
                for si in ss_root:
                    if _local_xml_tag(si.tag) == "si":
                        val = "".join(t.text for t in si.iter() if _local_xml_tag(t.tag) == "t" and t.text)
                        shared_strings.append(val)
        except Exception:
            pass

    sheet_names = sorted(
        n for n in names_set if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")
    )
    rows_out = []
    total_read = 0
    for sname in sheet_names:
        try:
            info = zf.getinfo(sname)
            if total_read + info.file_size > MAX_ZIP_EXTRACT_BYTES:
                break
            total_read += info.file_size
            s_root = ET.fromstring(zf.read(sname))
            for row_el in s_root.iter():
                if _local_xml_tag(row_el.tag) != "row":
                    continue
                row_vals = []
                for c_el in row_el:
                    if _local_xml_tag(c_el.tag) != "c":
                        continue
                    c_type = c_el.attrib.get("t", "")
                    if c_type == "inlineStr":
                        txt = "".join(t.text for t in c_el.iter() if _local_xml_tag(t.tag) == "t" and t.text)
                        if txt.strip():
                            row_vals.append(txt.strip())
                    else:
                        v_text = ""
                        for ch in c_el:
                            if _local_xml_tag(ch.tag) == "v" and ch.text:
                                v_text = ch.text.strip()
                                break
                        if v_text:
                            if c_type == "s" and v_text.isdigit():
                                idx = int(v_text)
                                if 0 <= idx < len(shared_strings) and shared_strings[idx].strip():
                                    row_vals.append(shared_strings[idx].strip())
                            else:
                                row_vals.append(v_text)
                if row_vals:
                    rows_out.append(" ".join(row_vals))
        except Exception:
            pass

    if not rows_out and shared_strings:
        rows_out.extend(s for s in shared_strings if s.strip())
    return "\n".join(rows_out)


def _extract_zip_document_text(zip_bytes: bytes, filename: str = "", mime_type: str = "") -> str:
    """
    Extracts searchable text from ZIP-packaged Office & OpenDocument files
    (.docx, .xlsx, .pptx, .odt, .ods, .odp) as well as plain .zip archives of documents.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            names_set = set(names)
            chunks = []

            # 1. Microsoft Word (.docx)
            if "word/document.xml" in names_set:
                docx_parts = ["word/document.xml"] + sorted(
                    n for n in names
                    if n.startswith(("word/header", "word/footer", "word/footnotes", "word/endnotes", "word/comments"))
                    and n.endswith(".xml")
                )
                total = 0
                for part in docx_parts:
                    info = zf.getinfo(part)
                    if total + info.file_size > MAX_ZIP_EXTRACT_BYTES:
                        break
                    total += info.file_size
                    try:
                        txt = _extract_docx_xml_text(zf.read(part))
                        if txt:
                            chunks.append(txt)
                    except Exception:
                        pass
                return _sanitize_extracted_text("\n".join(chunks))

            # 2. Microsoft Excel (.xlsx)
            if any(n.startswith("xl/") for n in names):
                return _sanitize_extracted_text(_extract_xlsx_text(zf, names_set))

            # 3. Microsoft PowerPoint (.pptx)
            if any(n.startswith("ppt/slides/slide") and n.endswith(".xml") for n in names):
                slide_parts = sorted(
                    (n for n in names if (n.startswith("ppt/slides/slide") or n.startswith("ppt/notesSlides/notesSlide")) and n.endswith(".xml")),
                    key=lambda s: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", s)],
                )
                total = 0
                for part in slide_parts:
                    info = zf.getinfo(part)
                    if total + info.file_size > MAX_ZIP_EXTRACT_BYTES:
                        break
                    total += info.file_size
                    try:
                        txt = _extract_pptx_xml_text(zf.read(part))
                        if txt:
                            chunks.append(txt)
                    except Exception:
                        pass
                return _sanitize_extracted_text("\n".join(chunks))

            # 4. OpenDocument (.odt, .ods, .odp)
            if "content.xml" in names_set:
                info = zf.getinfo("content.xml")
                if info.file_size <= MAX_ZIP_EXTRACT_BYTES:
                    root = ET.fromstring(zf.read("content.xml"))
                    odt_blocks = []
                    for elem in root.iter():
                        if _local_xml_tag(elem.tag) in ("p", "h"):
                            t = "".join(elem.itertext()).strip()
                            if t:
                                odt_blocks.append(t)
                    if odt_blocks:
                        return _sanitize_extracted_text("\n".join(odt_blocks))
                    return _sanitize_extracted_text(" ".join(root.itertext()))

            # 5. Plain .zip archive containing readable documents/text files
            total = 0
            for member in names[:15]:
                if member.endswith("/"):
                    continue
                low_m = member.lower()
                if low_m.endswith((".txt", ".md", ".csv", ".tsv", ".json", ".html", ".htm", ".rtf", ".pdf", ".docx", ".xlsx", ".pptx", ".odt")):
                    info = zf.getinfo(member)
                    if total + info.file_size > MAX_ZIP_EXTRACT_BYTES:
                        break
                    total += info.file_size
                    sub_txt = _extract_text_from_bytes(zf.read(member), filename=member)
                    if sub_txt:
                        chunks.append(sub_txt)
            return _sanitize_extracted_text("\n".join(chunks))
    except Exception:
        return ""


def _extract_rtf_text(rtf_bytes: bytes) -> str:
    raw = rtf_bytes.decode("latin1", errors="ignore")
    skip_dests = {
        "fonttbl", "colortbl", "stylesheet", "info", "pict", "object",
        "fldinst", "header", "footer", "themedata", "colorschememapping",
        "datastore", "latentstyles", "xmlopen",
    }
    out = []
    stack = []
    ignorable = False
    uc_skip = 1
    skip_chars = 0
    i = 0
    n = len(raw)
    while i < n:
        ch = raw[i]
        if ch == "{":
            stack.append((ignorable, uc_skip))
            i += 1
        elif ch == "}":
            if stack:
                ignorable, uc_skip = stack.pop()
            i += 1
        elif ch == "\\":
            i += 1
            if i >= n:
                break
            nxt = raw[i]
            if nxt in ("\\", "{", "}"):
                if not ignorable and skip_chars == 0:
                    out.append(nxt)
                i += 1
            elif nxt == "*":
                ignorable = True
                i += 1
            elif nxt in ("~", "_"):
                if not ignorable and skip_chars == 0:
                    out.append(" " if nxt == "~" else "-")
                i += 1
            elif nxt == "'" and i + 2 < n:
                hex_pair = raw[i + 1 : i + 3]
                i += 3
                if skip_chars > 0:
                    skip_chars -= 1
                elif not ignorable:
                    try:
                        out.append(bytes.fromhex(hex_pair).decode("cp1252", errors="ignore"))
                    except Exception:
                        pass
            elif nxt in ("\r", "\n"):
                if not ignorable:
                    out.append("\n")
                i += 1
            else:
                m = re.match(r"([a-zA-Z]+)(-?\d*) ?", raw[i:])
                if m:
                    word = m.group(1).lower()
                    arg = m.group(2)
                    i += len(m.group(0))
                    if word in skip_dests:
                        ignorable = True
                    elif word == "uc" and arg.lstrip("-").isdigit():
                        uc_skip = max(0, int(arg))
                    elif word == "u" and arg.lstrip("-").isdigit():
                        if not ignorable:
                            code = int(arg)
                            if code < 0:
                                code += 65536
                            if 0 <= code <= 0x10FFFF:
                                out.append(chr(code))
                        skip_chars = uc_skip
                    elif not ignorable:
                        if word in ("par", "pard", "sect", "page", "line", "row"):
                            out.append("\n")
                        elif word in ("tab", "cell"):
                            out.append(" ")
                else:
                    i += 1
        elif ch in ("\r", "\n"):
            i += 1
        else:
            if skip_chars > 0:
                skip_chars -= 1
            elif not ignorable:
                out.append(ch)
            i += 1
    return _sanitize_extracted_text("".join(out))


def _extract_html_text(html_bytes: bytes) -> str:
    raw = html_bytes.decode("utf-8", errors="ignore")
    raw = re.sub(r"<(script|style|noscript)\b[^>]*>.*?</\1>", " ", raw, flags=re.IGNORECASE | re.DOTALL)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return _sanitize_extracted_text(html_lib.unescape(raw))


def _is_non_text_binary(data_bytes: bytes, mime_type: str = "", filename: str = "") -> bool:
    mime_l = (mime_type or "").lower()
    fn_l = (filename or "").lower()
    if mime_l.startswith(("image/", "audio/", "video/", "font/")) and "svg" not in mime_l:
        return True
    if fn_l.endswith((
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".tiff",
        ".mp3", ".wav", ".ogg", ".mp4", ".mov", ".webm", ".avi",
        ".woff", ".woff2", ".ttf", ".otf", ".exe", ".dll", ".bin", ".dmg",
    )):
        return True
    head = data_bytes[:16]
    if head.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"BM", b"\x00\x00\x01\x00", b"wOFF", b"wOF2")):
        return True
    if head.startswith(b"RIFF") and b"WEBP" in head:
        return True
    if data_bytes.startswith((b"\xfe\xff", b"\xff\xfe")):
        return False
    sample = data_bytes[:2048]
    if not sample:
        return True
    null_or_ctrl = sum(
        1 for b in sample if b == 0 or (b < 32 and b not in (9, 10, 13, 12))
    )
    return (null_or_ctrl / len(sample)) > 0.10


def _extract_legacy_doc_strings(doc_bytes: bytes) -> str:
    """Best-effort printable ASCII & UTF-16LE run extraction for legacy binary .doc/.xls/.ppt OLE2 files."""
    chunks = []
    for m in re.finditer(rb"(?:[\x20-\x7e]\x00){5,}", doc_bytes):
        txt = m.group(0).decode("utf-16-le", errors="ignore").strip()
        if txt and any(c.isalpha() for c in txt):
            chunks.append(txt)
    for m in re.finditer(rb"[\x20-\x7e\r\n\t]{8,}", doc_bytes):
        txt = m.group(0).decode("latin1", errors="ignore").strip()
        if txt and any(c.isalpha() for c in txt) and not txt.startswith(("Root Entry", "WordDocument", "CompObj")):
            chunks.append(txt)
    return _sanitize_extracted_text(" ".join(chunks))


def _extract_text_from_bytes(data_bytes: bytes, mime_type: str = "", filename: str = "") -> str:
    if not data_bytes:
        return ""
    mime_l = (mime_type or "").lower()
    fn_l = (filename or "").lower()

    # 1. PDF Document (ISO 32000-1 §7.5.2: PDF header '%PDF-' within first 1024 bytes)
    if b"%PDF-" in data_bytes[:1024]:
        return _extract_pdf_text(data_bytes)

    # 2. ZIP-based Office / OpenDocument (.docx, .xlsx, .pptx, .odt, .ods, .odp, .zip)
    if data_bytes[:4] == b"PK\x03\x04":
        return _extract_zip_document_text(data_bytes, filename=filename, mime_type=mime_type)

    # 3. Legacy OLE2 binary Office (.doc, .xls, .ppt)
    if data_bytes[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return _extract_legacy_doc_strings(data_bytes)

    # 4. Rich Text Format (.rtf)
    if data_bytes.lstrip()[:5].startswith(b"{\\rtf") or "rtf" in mime_l or fn_l.endswith(".rtf"):
        return _extract_rtf_text(data_bytes)

    # 5. HTML / SVG
    head_ascii = data_bytes[:512].lstrip().lower()
    if (
        "html" in mime_l
        or fn_l.endswith((".html", ".htm"))
        or head_ascii.startswith((b"<!doctype html", b"<html", b"<body"))
    ):
        return _extract_html_text(data_bytes)

    # 6. Skip binary images/audio/video/executables cleanly (never dump raw binary garbage!)
    if _is_non_text_binary(data_bytes, mime_type=mime_type, filename=filename):
        return ""

    # 7. Plain Text / CSV / TSV / Markdown / JSON
    if data_bytes.startswith(b"\xef\xbb\xbf"):
        decoded = data_bytes[3:].decode("utf-8", errors="ignore")
    elif data_bytes.startswith(b"\xfe\xff"):
        decoded = data_bytes[2:].decode("utf-16-be", errors="ignore")
    elif data_bytes.startswith(b"\xff\xfe"):
        decoded = data_bytes[2:].decode("utf-16-le", errors="ignore")
    else:
        try:
            decoded = data_bytes.decode("utf-8")
        except UnicodeDecodeError:
            decoded = data_bytes.decode("cp1252", errors="ignore")

    if fn_l.endswith(".json") or "json" in mime_l or decoded.lstrip().startswith(("{", "[")):
        try:
            parsed_j = json.loads(decoded)
            if isinstance(parsed_j, (list, dict)):
                return _sanitize_extracted_text(json.dumps(parsed_j, ensure_ascii=False))
        except Exception:
            pass
    return _sanitize_extracted_text(decoded)


class _SafePublicRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _is_safe_public_doc_url(newurl, check_extension=False):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _is_safe_public_doc_url(url: str, check_extension: bool = True) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = (parsed.hostname or "").strip().lower()
        if not host or host in ("localhost", "example.com", "example.org", "example.net"):
            return False
        if host.endswith((".localhost", ".local", ".internal", ".test", ".invalid", ".example.com", ".example.org")):
            return False
        if check_extension:
            path_l = (parsed.path or "").lower()
            if not path_l.endswith((".pdf", ".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp", ".rtf", ".txt", ".csv", ".tsv", ".md")):
                return False
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
        if not infos:
            return False
        for info in infos:
            ip_obj = ipaddress.ip_address(info[4][0])
            if not ip_obj.is_global:
                return False
        return True
    except Exception:
        return False


def _fetch_remote_document_text(url: str) -> str:
    if os.environ.get("GOODDEEDS_DISABLE_REMOTE_DOC_FETCH") == "1":
        return ""
    if not _is_safe_public_doc_url(url, check_extension=True):
        return ""
    try:
        opener = urllib.request.build_opener(_SafePublicRedirectHandler)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "GoodDeedsSpace-DocIndexer/1.0"},
            method="GET",
        )
        with opener.open(req, timeout=3.5) as resp:
            ctype = resp.headers.get("Content-Type", "") or ""
            raw = resp.read(MAX_REMOTE_DOC_BYTES + 1)
            if len(raw) > MAX_REMOTE_DOC_BYTES:
                return ""
            fn = urllib.parse.urlparse(url).path.rsplit("/", 1)[-1]
            return _extract_text_from_bytes(raw, mime_type=ctype, filename=fn)
    except Exception:
        return ""


def extract_resource_text(resource_url, allow_remote_fetch: bool = False) -> str:
    """
    Extracts searchable text content from attached documents and resource URLs:
    - JSON arrays/objects of attachments or URLs
    - Base64 Data URIs (.pdf, .docx, .xlsx, .pptx, .odt, .rtf, .html, .csv, .txt, .md, .json)
    - Decoded attachment filenames (;name=...) and URL path tokens
    - Optional SSRF-guarded remote public document URLs when allow_remote_fetch=True
    Never outputs raw Base64 strings or unparsed binary headers (e.g. '%PDF-1.5', 'PK\\x03\\x04').
    """
    if not resource_url:
        return ""

    if isinstance(resource_url, (list, tuple)):
        sub_texts = [extract_resource_text(item, allow_remote_fetch=allow_remote_fetch) for item in resource_url]
        return " ".join([t for t in sub_texts if t]).strip()
    if isinstance(resource_url, dict):
        sub_texts = [extract_resource_text(v, allow_remote_fetch=allow_remote_fetch) for v in resource_url.values()]
        return " ".join([t for t in sub_texts if t]).strip()
    if not isinstance(resource_url, str):
        return str(resource_url)

    url = resource_url.strip()
    if not url:
        return ""

    if url.startswith("[") or url.startswith("{"):
        try:
            parsed = json.loads(url)
            if isinstance(parsed, (list, tuple, dict)):
                return extract_resource_text(parsed, allow_remote_fetch=allow_remote_fetch)
        except Exception:
            pass

    if "\n" in url and not url.startswith("data:"):
        lines = [ln.strip() for ln in url.splitlines() if ln.strip()]
        if len(lines) > 1:
            return extract_resource_text(lines, allow_remote_fetch=allow_remote_fetch)

    # Case 1: Base64 / inline Data URI ('data:<mime>;name=<fn>;base64,<payload>')
    if url.startswith("data:"):
        parts = url.split(",", 1)
        if len(parts) != 2:
            return ""
        header, payload = parts[0], parts[1]
        header_body = header[5:]  # after 'data:'
        header_tokens = [tok.strip() for tok in header_body.split(";") if tok.strip()]
        mime_type = header_tokens[0] if header_tokens and "=" not in header_tokens[0] else ""
        filename = ""
        is_base64 = False
        for tok in header_tokens:
            low_tok = tok.lower()
            if low_tok == "base64":
                is_base64 = True
            elif low_tok.startswith("name=") or low_tok.startswith("filename="):
                filename = urllib.parse.unquote(tok.split("=", 1)[1].strip().strip('"\''))

        data_bytes = b""
        if is_base64:
            compact = re.sub(r"\s+", "", payload)
            pad = len(compact) % 4
            if pad:
                compact += "=" * (4 - pad)
            try:
                data_bytes = base64.b64decode(compact)
            except Exception:
                try:
                    data_bytes = base64.urlsafe_b64decode(compact)
                except Exception:
                    data_bytes = b""
        else:
            try:
                data_bytes = urllib.parse.unquote_to_bytes(payload)
            except Exception:
                data_bytes = payload.encode("utf-8", errors="ignore")

        chunks = []
        if filename:
            chunks.append(_humanize_filename_tokens(filename))
        doc_text = _extract_text_from_bytes(data_bytes, mime_type=mime_type, filename=filename)
        if doc_text:
            chunks.append(doc_text)
        return _sanitize_extracted_text(" ".join(chunks))

    # Case 2: Standard Web / Path URL ('https://...', 'http://...', '/...')
    if url.startswith(("http://", "https://", "/")):
        chunks = [_humanize_filename_tokens(url)]
        if allow_remote_fetch and url.startswith(("http://", "https://")):
            remote_txt = _fetch_remote_document_text(url)
            if remote_txt:
                chunks.append(remote_txt)
        return _sanitize_extracted_text(" ".join(chunks))

    # Case 3: Raw Base64 string without 'data:' prefix
    if len(url) >= 16 and re.fullmatch(r"[A-Za-z0-9+/=\s]+", url):
        try:
            compact = re.sub(r"\s+", "", url)
            pad = len(compact) % 4
            if pad:
                compact += "=" * (4 - pad)
            raw_b = base64.b64decode(compact, validate=True)
            doc_text = _extract_text_from_bytes(raw_b)
            if doc_text:
                return doc_text
        except Exception:
            pass

    return _sanitize_extracted_text(url)

def init_db():
    """
    Initializes the database schema.
    
    Creates all necessary tables if they do not exist.
    If the users table is empty after creation, it automatically
    triggers data seeding.
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        phone TEXT,
        avatar_url TEXT,
        bio TEXT,
        is_site_admin INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        oauth_provider TEXT NULL,
        oauth_id TEXT NULL,
        email_verified INTEGER DEFAULT 0,
        email_prefs TEXT NULL,
        unsubscribe_token TEXT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN is_site_admin INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN oauth_provider TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN oauth_id TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER DEFAULT 0")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN email_prefs TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN unsubscribe_token TEXT")
    except Exception:
        pass

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        expires_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN expires_at DATETIME")
    except Exception:
        pass
    try:
        cursor.execute("""
            UPDATE sessions
            SET expires_at = datetime(COALESCE(created_at, CURRENT_TIMESTAMP), '+30 days')
            WHERE expires_at IS NULL OR TRIM(expires_at) = ''
        """)
        cursor.execute("""
            DELETE FROM sessions
            WHERE (expires_at IS NOT NULL AND expires_at <= datetime('now'))
               OR created_at <= datetime('now', '-30 days')
        """)
    except Exception:
        pass

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        themes TEXT,
        icon_url TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS group_members (
        group_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        is_admin INTEGER DEFAULT 0,
        joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (group_id, user_id),
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS group_resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        url TEXT NOT NULL,
        resource_type TEXT DEFAULT 'URL',
        theme TEXT DEFAULT 'Community Resources',
        event_date TEXT,
        event_time TEXT,
        added_by INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
        FOREIGN KEY (added_by) REFERENCES users(id) ON DELETE SET NULL
    )
    """)
    try:
        cursor.execute("ALTER TABLE group_resources ADD COLUMN event_date TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE group_resources ADD COLUMN event_time TEXT")
    except Exception:
        pass

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS group_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        is_broadcast INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)
    try:
        cursor.execute("ALTER TABLE group_messages ADD COLUMN is_broadcast INTEGER DEFAULT 0")
    except Exception:
        pass

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feed_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_type TEXT NOT NULL,
        author_id INTEGER NOT NULL,
        recipient_id INTEGER,
        title TEXT,
        content TEXT NOT NULL,
        theme TEXT,
        resource_url TEXT,
        post_subtype TEXT,
        event_date TEXT,
        event_time TEXT,
        target_audience TEXT,
        target_geography TEXT,
        contact_info TEXT,
        category TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (recipient_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)
    try:
        cursor.execute("ALTER TABLE feed_items ADD COLUMN post_subtype TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE feed_items ADD COLUMN event_date TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE feed_items ADD COLUMN event_time TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE feed_items ADD COLUMN extracted_text TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE feed_items ADD COLUMN target_audience TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE feed_items ADD COLUMN target_geography TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE feed_items ADD COLUMN contact_info TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE feed_items ADD COLUMN category TEXT")
    except Exception:
        pass
    try:
        cursor.execute("UPDATE feed_items SET category = 'Health & Wellness' WHERE id = 2 AND (category IS NULL OR category = '')")
        cursor.execute("UPDATE feed_items SET category = 'Education & Tutoring' WHERE id = 4 AND (category IS NULL OR category = '')")
        cursor.execute("UPDATE feed_items SET event_time = '2:00 PM' WHERE id = 4 AND (event_time IS NULL OR event_time = '')")
        cursor.execute("UPDATE feed_items SET category = 'Food & Mutual Aid' WHERE id = 5 AND (category IS NULL OR category = '')")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE group_resources ADD COLUMN extracted_text TEXT")
    except Exception:
        pass

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS item_groups (
        item_id INTEGER NOT NULL,
        group_id INTEGER NOT NULL,
        PRIMARY KEY (item_id, group_id),
        FOREIGN KEY (item_id) REFERENCES feed_items(id) ON DELETE CASCADE,
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        emoji TEXT NOT NULL,
        UNIQUE(item_id, user_id, emoji),
        FOREIGN KEY (item_id) REFERENCES feed_items(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (item_id) REFERENCES feed_items(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS email_outbox (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipient_email TEXT NOT NULL,
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        html_body TEXT,
        template_key TEXT DEFAULT 'general',
        reply_to TEXT,
        sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'SENT'
    )
    """)
    try:
        cursor.execute("ALTER TABLE email_outbox ADD COLUMN html_body TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE email_outbox ADD COLUMN template_key TEXT DEFAULT 'general'")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE email_outbox ADD COLUMN reply_to TEXT")
    except Exception:
        pass

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS auth_email_tokens (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        token_type TEXT NOT NULL,
        expires_at DATETIME NOT NULL,
        used INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customer_service_inquiries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        subject TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS group_invitations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        sender_id INTEGER NOT NULL,
        recipient_username TEXT NOT NULL,
        message TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'PENDING',
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
        FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS site_invitations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER,
        sender_name TEXT,
        recipient_email TEXT NOT NULL,
        message TEXT,
        status TEXT DEFAULT 'PENDING',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE SET NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS group_bans (
        group_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        banned_by INTEGER,
        reason TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (group_id, user_id),
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS content_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_type TEXT NOT NULL,
        target_id INTEGER NOT NULL,
        reporter_id INTEGER NOT NULL,
        reason TEXT NOT NULL,
        notes TEXT,
        status TEXT DEFAULT 'PENDING',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (reporter_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        actor_id INTEGER,
        notif_type TEXT NOT NULL,
        target_id INTEGER,
        message TEXT NOT NULL,
        link_hash TEXT,
        is_read INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS passkeys (
        credential_id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        public_key BLOB NOT NULL,
        sign_count INTEGER NOT NULL DEFAULT 0,
        device_name TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS webauthn_challenges (
        challenge TEXT PRIMARY KEY,
        user_id INTEGER,
        state BLOB NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS signup_email_otps (
        email TEXT PRIMARY KEY,
        otp_hash TEXT NOT NULL,
        expires_at DATETIME NOT NULL,
        attempts INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("SELECT COUNT(*) as count FROM users")
    if cursor.fetchone()["count"] == 0 and is_demo_seed_enabled():
        seed_data(cursor)

    # When SEED_DEMO is off, automatically lock any pre-existing demo persona accounts,
    # strip demo Site Admin privileges, and revoke any active demo sessions/tokens.
    admin_emails = get_configured_admin_emails()
    if not is_demo_seed_enabled():
        try:
            placeholders = ",".join("?" for _ in DEMO_PERSONA_EMAILS)
            cursor.execute(
                f"SELECT id, email, password_hash, is_site_admin FROM users WHERE LOWER(email) IN ({placeholders})",
                tuple(e.lower() for e in DEMO_PERSONA_EMAILS),
            )
            for demo_row in cursor.fetchall():
                demo_email_l = str(demo_row["email"] or "").strip().lower()
                if demo_email_l in admin_emails:
                    continue
                pw_h = str(demo_row["password_hash"] or "")
                needs_lock = (
                    not pw_h.startswith("LOCKED_")
                    or demo_row["is_site_admin"] == 1
                )
                if needs_lock:
                    cursor.execute(
                        "UPDATE users SET password_hash = ?, is_site_admin = 0 WHERE id = ?",
                        (make_locked_account_hash("DEMO_ACCOUNT"), demo_row["id"]),
                    )
                cursor.execute("DELETE FROM sessions WHERE user_id = ?", (demo_row["id"],))
                cursor.execute("UPDATE auth_email_tokens SET used = 1 WHERE user_id = ? AND used = 0", (demo_row["id"],))
        except Exception:
            pass

    if admin_emails:
        try:
            adm_placeholders = ",".join("?" for _ in admin_emails)
            cursor.execute(
                f"UPDATE users SET is_site_admin = 1 WHERE LOWER(email) IN ({adm_placeholders}) AND COALESCE(is_banned, 0) = 0",
                tuple(admin_emails),
            )
        except Exception:
            pass

    # Startup re-indexing step for feed_items and group_resources
    try:
        cursor.execute("SELECT id, title, resource_url, extracted_text FROM feed_items WHERE resource_url IS NOT NULL AND TRIM(resource_url) != ''")
        for row in cursor.fetchall():
            row_id = row["id"]
            title = row["title"] or "Document"
            clean_title = re.sub(r'[^\w\s.-]', '', title).strip().replace(' ', '_')
            res_url = row["resource_url"]
            if res_url and ("data:" in res_url) and ("name=" not in res_url):
                def _guess_data_ext(uri_str: str) -> str:
                    head_l = uri_str[:120].lower()
                    if "pdf" in head_l:
                        return ".pdf"
                    if "wordprocessingml" in head_l:
                        return ".docx"
                    if "spreadsheetml" in head_l:
                        return ".xlsx"
                    if "presentationml" in head_l:
                        return ".pptx"
                    if "rtf" in head_l:
                        return ".rtf"
                    if "csv" in head_l:
                        return ".csv"
                    if "html" in head_l:
                        return ".html"
                    if "text/plain" in head_l:
                        return ".txt"
                    return ".dat"
                try:
                    if res_url.startswith("["):
                        u_list = json.loads(res_url)
                        for i in range(len(u_list)):
                            if "data:" in u_list[i] and "name=" not in u_list[i]:
                                ext = _guess_data_ext(u_list[i])
                                fn = clean_title + ext if not clean_title.endswith(ext) else clean_title
                                u_list[i] = re.sub(r'data:([^;,]+)', rf'data:\1;name={fn}', u_list[i])
                        cursor.execute("UPDATE feed_items SET resource_url = ? WHERE id = ?", (json.dumps(u_list), row_id))
                        res_url = json.dumps(u_list)
                    else:
                        ext = _guess_data_ext(res_url)
                        fn = clean_title + ext if not clean_title.endswith(ext) else clean_title
                        res_url = re.sub(r'data:([^;,]+)', rf'data:\1;name={fn}', res_url)
                        cursor.execute("UPDATE feed_items SET resource_url = ? WHERE id = ?", (res_url, row_id))
                except Exception:
                    pass
            ext_str = str(row["extracted_text"] or "").strip()
            new_text = extract_resource_text(res_url)
            if new_text != ext_str and (new_text or "data:" in str(res_url)):
                cursor.execute("UPDATE feed_items SET extracted_text = ? WHERE id = ?", (new_text, row_id))
    except Exception:
        pass

    try:
        cursor.execute("PRAGMA table_info(group_resources)")
        cols = [r["name"] for r in cursor.fetchall()]
        url_col = "resource_url" if "resource_url" in cols else "url"
        cursor.execute(f"SELECT id, title, {url_col} as r_url, extracted_text FROM group_resources WHERE {url_col} IS NOT NULL AND TRIM({url_col}) != ''")
        for row in cursor.fetchall():
            row_id = row["id"]
            res_url = row["r_url"]
            title = row["title"] or ""
            ext_str = str(row["extracted_text"] or "").strip()
            new_text = extract_resource_text(res_url)
            if not new_text or len(new_text) < 15:
                if "grounding" in res_url.lower() or "grounding" in title.lower():
                    new_text = "Practical grounding techniques, breathing exercises, and emotional regulation steps for managing acute anxiety."
                elif "mindfulness" in res_url.lower() or "mindfulness" in title.lower():
                    new_text = "Curated web resource offering guided mindfulness sessions, audio meditations, and daily wellness practices."
                elif "resume" in res_url.lower() or "resume" in title.lower():
                    new_text = "Step-by-step resume building templates, career transition advice, and mentorship networking strategies."
                elif "volunteer" in res_url.lower() or "volunteer" in title.lower():
                    new_text = "Interactive community map and volunteer coordination directory for local food pantries and mutual aid."
                elif "kindness" in res_url.lower() or "kindness" in title.lower():
                    new_text = "Actionable strategies and community insights on fostering daily kindness and breaking negative cycles."
                elif res_url.startswith("http"):
                    new_text = f"Curated online web resource providing community guides and references for {title}."
                else:
                    new_text = f"Downloadable community reference document and guide for {title}."
            if new_text and new_text != ext_str:
                cursor.execute("UPDATE group_resources SET extracted_text = ? WHERE id = ?", (new_text, row_id))
    except Exception:
        pass

    try:
        cursor.execute("""
            DELETE FROM group_invitations
            WHERE status = 'PENDING'
              AND EXISTS (
                SELECT 1 FROM group_members gm
                JOIN users u ON gm.user_id = u.id
                WHERE gm.group_id = group_invitations.group_id
                  AND (LOWER(u.username) = LOWER(group_invitations.recipient_username)
                       OR LOWER(u.email) = LOWER(group_invitations.recipient_username))
              )
        """)
        cursor.execute("""
            UPDATE feed_items
            SET target_audience = 'All Community Members, Youth & Adults',
                target_geography = 'Citywide & Online (Global)',
                contact_info = 'Elena Wellness — elena@gooddeeds.space | (555) 010-3000'
            WHERE id = 2 AND (target_audience IS NULL OR target_audience = '')
        """)
        cursor.execute("""
            UPDATE feed_items
            SET target_audience = 'High School & College Students, Volunteer Mentors',
                target_geography = 'Bay Area, CA & Virtual (Zoom)',
                contact_info = 'Maya Lin (Event Coordinator) — maya@gooddeeds.space | (555) 010-1000'
            WHERE id = 4 AND (target_audience IS NULL OR target_audience = '')
        """)
        cursor.execute("""
            UPDATE feed_items
            SET target_audience = 'Local Neighbors, Families & Seniors',
                target_geography = 'Oakwood District & Greater Metro Area',
                contact_info = 'Marcus Vance — marcus@gooddeeds.space | (555) 010-2000'
            WHERE id = 5 AND (target_audience IS NULL OR target_audience = '')
        """)
        cursor.execute("""
            UPDATE feed_items
            SET target_audience = COALESCE(NULLIF(TRIM(target_audience), ''), 'All Community Members'),
                target_geography = COALESCE(NULLIF(TRIM(target_geography), ''), 'Local & Online Community'),
                contact_info = COALESCE(
                    NULLIF(TRIM(contact_info), ''),
                    (SELECT u.username || ' — ' || u.email FROM users u WHERE u.id = feed_items.author_id),
                    'Community Organizer — support@gooddeeds.space'
                )
            WHERE item_type = 'POST'
              AND (target_audience IS NULL OR TRIM(target_audience) = ''
                   OR target_geography IS NULL OR TRIM(target_geography) = ''
                   OR contact_info IS NULL OR TRIM(contact_info) = '')
        """)
        cursor.execute("SELECT id, content FROM feed_items WHERE content LIKE '📅 Event Date:%'")
        for r in cursor.fetchall():
            cleaned_c = re.sub(r'^📅\s*Event Date:[^\n]*\n+', '', str(r["content"] or "")).strip()
            if cleaned_c and cleaned_c != r["content"]:
                cursor.execute("UPDATE feed_items SET content = ? WHERE id = ?", (cleaned_c, r["id"]))
        cursor.execute("UPDATE users SET email_verified = 1 WHERE email IN ('maya@gooddeeds.space', 'marcus@gooddeeds.space', 'elena@gooddeeds.space', 'arthur@gooddeeds.space') AND COALESCE(email_verified, 0) = 0")
    except Exception:
        pass

    # One-time security migration: rotate/invalidate any pre-existing unused reset/verification tokens
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                key TEXT PRIMARY KEY,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        mig_key = "2026_11_02_rotate_auth_email_tokens_v1"
        cursor.execute("SELECT 1 FROM schema_migrations WHERE key = ?", (mig_key,))
        if not cursor.fetchone():
            cursor.execute("UPDATE auth_email_tokens SET used = 1 WHERE used = 0")
            cursor.execute("INSERT INTO schema_migrations (key) VALUES (?)", (mig_key,))
    except Exception:
        pass

    conn.commit()
    conn.close()

def seed_data(cursor):
    pw_hash = hash_password("password123")

    users = [
        ("maya@gooddeeds.space", "Maya_Lin", pw_hash, "555-0101", "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=200&q=80", "Youth mentor & software engineer (28). Passionate about closing the STEM education gap and promoting community mental health wellness.", 1),
        ("marcus@gooddeeds.space", "Marcus_Vance", pw_hash, "555-0102", "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=200&q=80", "Neighborhood organizer and father of 3 (42). Organizing local weekend cleanups, community food pantries, and mutual aid networks.", 0),
        ("elena@gooddeeds.space", "Elena_Wellness", pw_hash, "555-0103", "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=200&q=80", "Licensed mental health counselor (35). Hosting free weekly grounding circles and destigmatizing emotional support for all ages.", 0),
        ("arthur@gooddeeds.space", "Arthur_74", pw_hash, "", "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=200&q=80", "Retired history teacher (74) leading our senior center bootstrap pilot. Partnering with young volunteers for intergenerational friendship.", 0)
    ]
    cursor.executemany("INSERT INTO users (email, username, password_hash, phone, avatar_url, bio, is_site_admin) VALUES (?, ?, ?, ?, ?, ?, ?)", users)

    groups = [
        ("🌱 Mental Health & Peer Listening", "A safe, confidential space for emotional encouragement, stress reduction, and mental health wellness across all walks of life.", json.dumps(["Mental Health", "Community Resources"]), "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?auto=format&fit=crop&w=200&q=80"),
        ("🎓 Education, Tutoring & Skill Share", "Connecting experienced professionals, students, and retirees for academic tutoring, career advice, and mutual skill exchange.", json.dumps(["Education", "Events"]), "https://images.unsplash.com/photo-1517486808906-6ca8b3f04846?auto=format&fit=crop&w=200&q=80"),
        ("🤝 Community Action & Mutual Aid", "Local mutual aid network organizing neighborhood cleanups, food pantries, senior center visits, and volunteer assistance.", json.dumps(["General", "Inspiring Stories"]), "https://images.unsplash.com/photo-1593113598332-cd288d649433?auto=format&fit=crop&w=200&q=80")
    ]
    cursor.executemany("INSERT INTO groups (name, description, themes, icon_url) VALUES (?, ?, ?, ?)", groups)

    members = [
        (1, 3, 1),
        (1, 1, 0),
        (1, 2, 0),
        (1, 4, 0),
        (2, 1, 1),
        (2, 4, 0),
        (2, 2, 0),
        (3, 2, 1),
        (3, 1, 0),
        (3, 3, 0),
        (3, 4, 0),
    ]
    cursor.executemany("INSERT INTO group_members (group_id, user_id, is_admin) VALUES (?, ?, ?)", members)

    resources = [
        (1, "Mental Health First Aid & Grounding Handbook", "https://example.com/grounding_guide.pdf", "PDF", "Mental Health", 3, "Practical grounding techniques, breathing exercises, and emotional regulation steps for managing acute anxiety."),
        (1, "Free Online Mindfulness & Audio Meditations", "https://example.com/mindfulness", "URL", "Mental Health", 3, "Curated web resource offering guided mindfulness sessions, audio meditations, and daily wellness practices."),
        (2, "Comprehensive Resume & Career Mentorship Guide", "https://example.com/resume_guide.pdf", "PDF", "Education", 1, "Step-by-step resume building templates, career transition advice, and mentorship networking strategies."),
        (3, "Local Mutual Aid Network & Volunteer Map", "https://example.com/volunteer_map.pdf", "PDF", "General", 2, "Interactive community map and volunteer coordination directory for local food pantries and mutual aid.")
    ]
    cursor.executemany("INSERT INTO group_resources (group_id, title, url, resource_type, theme, added_by, extracted_text) VALUES (?, ?, ?, ?, ?, ?, ?)", resources)

    chat_msgs = [
        (1, 3, "Welcome everyone to our confidential listening space. Remember that asking for support is a courageous step toward becoming your best self."),
        (1, 1, "Thank you Elena! Your grounding audio guide helped me so much before my big presentation yesterday."),
        (2, 1, "Looking for a volunteer coding tutor for a motivated high school sophomore this Saturday!"),
        (2, 4, "I would love to help tutor in writing and history, Maya. Intergenerational learning is wonderful!"),
        (3, 2, "Reminder: Weekend neighborhood cleanup and food pantry restock starts tomorrow at 10 AM. All ages welcome!")
    ]
    cursor.executemany("INSERT INTO group_messages (group_id, user_id, message) VALUES (?, ?, ?)", chat_msgs)

    items = [
        ("KUDOS", 1, 2, None, "Massive thank you to Marcus for organizing our neighborhood food pantry restock! Your dedication brings connection, positivity, and goodness to our block every single day.", None, None, "GENERAL", None, None, None, None, None, None),
        ("POST", 3, None, "Promoting Goodness: Breaking the Cycle of Negativity", "Far too often we are inundated with news of division, stress, and hardship. It makes it easy to forget the intrinsic kindness inside every human being. By choosing to do one good deed today—whether listening to a friend, tutoring a student, or helping a neighbor—we ripple positivity outward. Let's promote goodness and help everyone become the best possible version of themselves.", "Mental Health", "https://example.com/kindness_guide.pdf", "RESOURCE", None, None, "All Community Members, Youth & Adults", "Citywide & Online (Global)", "Elena Wellness — elena@gooddeeds.space | (555) 010-3000", "Health & Wellness"),
        ("KUDOS", 4, 3, None, "Heartfelt kudos to Elena for hosting free weekly mental health listening circles. Your empathy and practical grounding tips have helped people of all ages find peace and resilience!", None, None, "GENERAL", None, None, None, None, None, None),
        ("POST", 1, None, "Test Post: Free Online Tutoring & Mentorship Fair This Saturday", "Join us this Saturday at 2 PM for our intergenerational skill share! Whether you need academic tutoring, career advice, or want to volunteer your expertise across education and tech, there is a welcoming place for you.", "Educational", "https://example.com/mentorship_fair.pdf", "EVENT", "2026-07-15", "2:00 PM", "High School & College Students, Volunteer Mentors", "Bay Area, CA & Virtual (Zoom)", "Maya Lin (Event Coordinator) — maya@gooddeeds.space | (555) 010-1000", "Education & Tutoring"),
        ("POST", 2, None, "How Small Acts of Mutual Aid Transformed Our Neighborhood", "Last month, a few neighbors set up a shared tool library and community pantry. What started as a simple shelf has turned into daily collaboration between college students, busy parents, and retired neighbors. Promote goodness—one good deed at a time!", "Inspiring Story", "", "GENERAL", None, None, "Local Neighbors, Families & Seniors", "Oakwood District & Greater Metro Area", "Marcus Vance — marcus@gooddeeds.space | (555) 010-2000", "Food & Mutual Aid")
    ]
    cursor.executemany("INSERT INTO feed_items (item_type, author_id, recipient_id, title, content, theme, resource_url, post_subtype, event_date, event_time, target_audience, target_geography, contact_info, category) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", items)

    item_groups = [
        (1, 3),
        (2, 1),
        (3, 1),
        (4, 2),
        (5, 3)
    ]
    cursor.executemany("INSERT INTO item_groups (item_id, group_id) VALUES (?, ?)", item_groups)

    reactions = [
        (1, 3, "👍"), (1, 4, "👏"), (1, 1, "🌟"),
        (2, 1, "❤️"), (2, 2, "❤️"), (2, 4, "🤗"), (2, 2, "🌟"),
        (3, 1, "👏"), (3, 2, "🎉"),
        (4, 3, "❤️"), (4, 4, "🌟"),
        (5, 1, "❤️"), (5, 3, "👏"), (5, 4, "🌟")
    ]
    cursor.executemany("INSERT INTO reactions (item_id, user_id, emoji) VALUES (?, ?, ?)", reactions)

    comments = [
        (1, 3, "Marcus truly embodies community leadership!"),
        (2, 1, "Beautiful reminder Elena. One good deed at a time really makes a difference."),
        (2, 4, "Wonderful wisdom. Glad to be part of this safe space."),
        (3, 2, "Elena's listening circles have been a blessing for my entire family."),
        (4, 4, "Count me in for Saturday! I will bring history books.")
    ]
    cursor.executemany("INSERT INTO comments (item_id, user_id, content) VALUES (?, ?, ?)", comments)

    emails = [
        ("marcus@gooddeeds.space", "🌟 You received new Kudos from Maya_Lin!", "Maya_Lin gave you public Kudos on gooddeeds.space:\n\n\"Massive thank you to Marcus for organizing our neighborhood food pantry restock!...\"\n\nView and celebrate your full Kudos here: /#/kudos/1"),
        ("elena@gooddeeds.space", "🌟 You received new Kudos from Arthur_74!", "Arthur_74 gave you public Kudos on gooddeeds.space:\n\n\"Heartfelt kudos to Elena for hosting free weekly mental health listening circles!...\"\n\nView and celebrate your full Kudos here: /#/kudos/3")
    ]
    cursor.executemany("INSERT INTO email_outbox (recipient_email, subject, body) VALUES (?, ?, ?)", emails)

    invites = [
        (1, 2, "Maya_Lin", "Join Marcus and our family in Mental Health & Peer Listening!", "ACCEPTED"),
        (2, 3, "Maya_Lin", "Elena invited you to join Education, Tutoring & Skill Share!", "ACCEPTED"),
        (3, 4, "Marcus_Vance", "Arthur invited you to join Community Action & Mutual Aid!", "ACCEPTED")
    ]
    cursor.executemany("INSERT INTO group_invitations (group_id, sender_id, recipient_username, message, status) VALUES (?, ?, ?, ?, ?)", invites)

def format_last_active_date(dt_str: str) -> str:
    if not dt_str:
        return "Never"
    try:
        clean_str = str(dt_str).replace("Z", "").split(".")[0]
        if " " in clean_str:
            dt = datetime.strptime(clean_str, "%Y-%m-%d %H:%M:%S")
        elif "T" in clean_str:
            dt = datetime.strptime(clean_str, "%Y-%m-%dT%H:%M:%S")
        else:
            dt = datetime.strptime(clean_str, "%Y-%m-%d")
        return f"{dt.strftime('%B')} {dt.day}, {dt.year}"
    except Exception:
        return str(dt_str)

def get_user_stats(user_id: int) -> dict:
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as cnt FROM feed_items WHERE recipient_id = ? AND item_type = 'KUDOS'", (user_id,))
    kudos_received = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) as cnt FROM feed_items WHERE recipient_id = ? AND item_type = 'KUDOS' AND created_at >= datetime('now', '-1 year')", (user_id,))
    kudos_year = cursor.fetchone()["cnt"]
    avg_kudos_year = round(kudos_year / 12.0, 1)

    cursor.execute("SELECT COUNT(*) as cnt FROM feed_items WHERE author_id = ? AND item_type = 'KUDOS'", (user_id,))
    kudos_given = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(DISTINCT author_id) as cnt FROM feed_items WHERE recipient_id = ? AND item_type = 'KUDOS'", (user_id,))
    unique_givers = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) as cnt FROM feed_items WHERE author_id = ? AND item_type = 'POST'", (user_id,))
    posts_authored = cursor.fetchone()["cnt"]

    cursor.execute("""
        SELECT COUNT(r.id) as cnt
        FROM reactions r
        JOIN feed_items f ON r.item_id = f.id
        WHERE f.author_id = ? AND f.item_type = 'POST'
    """, (user_id,))
    total_post_reactions = cursor.fetchone()["cnt"]
    avg_reactions = round(float(total_post_reactions) / posts_authored, 1) if posts_authored > 0 else 0.0

    cursor.execute("""
        SELECT MAX(dt) as max_dt FROM (
            SELECT created_at AS dt FROM users WHERE id = ?
            UNION ALL
            SELECT created_at AS dt FROM feed_items WHERE author_id = ? OR recipient_id = ?
            UNION ALL
            SELECT created_at AS dt FROM comments WHERE user_id = ?
            UNION ALL
            SELECT created_at AS dt FROM group_messages WHERE user_id = ?
            UNION ALL
            SELECT created_at AS dt FROM group_resources WHERE added_by = ?
            UNION ALL
            SELECT joined_at AS dt FROM group_members WHERE user_id = ?
            UNION ALL
            SELECT created_at AS dt FROM sessions WHERE user_id = ?
        )
    """, (user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id))
    row = cursor.fetchone()
    max_dt = row["max_dt"] if row and row["max_dt"] else None
    if not max_dt:
        cursor.execute("SELECT created_at FROM users WHERE id = ?", (user_id,))
        u_row = cursor.fetchone()
        if u_row:
            max_dt = u_row["created_at"]

    last_active_formatted = format_last_active_date(max_dt)
    conn.close()

    return {
        "kudos_received": kudos_received,
        "avg_kudos_year": avg_kudos_year,
        "kudos_given": kudos_given,
        "unique_kudos_givers": unique_givers,
        "unique_givers": unique_givers,
        "posts_authored": posts_authored,
        "avg_reactions_per_post": avg_reactions,
        "avg_reactions": avg_reactions,
        "last_active_date": last_active_formatted,
        "last_active": last_active_formatted
    }

def get_platform_stats() -> dict:
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as cnt FROM feed_items WHERE item_type = 'KUDOS'")
    acts_of_kindness = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) as cnt FROM users")
    community_members = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) as cnt FROM groups")
    active_spaces = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) as cnt FROM feed_items WHERE item_type = 'POST'")
    total_posts = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) as cnt FROM reactions")
    total_reactions = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) as cnt FROM comments")
    total_comments = cursor.fetchone()["cnt"]

    conn.close()

    return {
        "acts_of_kindness": acts_of_kindness,
        "community_members": community_members,
        "active_spaces": active_spaces,
        "total_posts": total_posts,
        "total_reactions": total_reactions,
        "total_comments": total_comments
    }

if __name__ == "__main__":
    init_db()
    print(f"Database initialized successfully at {DB_PATH}.")

