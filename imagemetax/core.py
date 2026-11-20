"""Image acquisition and metadata extraction. No image is uploaded to a third party."""
from __future__ import annotations
import hashlib, ipaddress, json, mimetypes, os, re, socket, struct, tempfile
from pathlib import Path
from urllib.parse import urlparse, urljoin
from urllib.request import url2pathname

import requests
from bs4 import BeautifulSoup
from PIL import Image, ExifTags

MAX_DOWNLOAD = 40 * 1024 * 1024
TIMEOUT = (8, 25)
USER_AGENT = "ImageMetaX/1.0 (+local metadata inspection)"

def _public_http_url(url: str) -> str:
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError("Only valid http:// and https:// URLs are accepted.")
    host = p.hostname
    if host.lower() in ("localhost",) or host.endswith((".local", ".internal")):
        raise ValueError("Local/private network addresses are blocked for safety.")
    try:
        addresses = socket.getaddrinfo(host, p.port or (443 if p.scheme == "https" else 80))
        for item in addresses:
            ip = ipaddress.ip_address(item[4][0])
            if not ip.is_global:
                raise ValueError("URLs resolving to private, local, or reserved IP addresses are blocked.")
    except socket.gaierror as e:
        raise ValueError(f"Could not resolve host: {e}") from e
    return url

def _safe_get(url: str, stream=False):
    current = url
    for _ in range(5):
        _public_http_url(current)
        response = requests.get(current, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT,
                                stream=stream, allow_redirects=False)
        if response.is_redirect or response.is_permanent_redirect:
            loc = response.headers.get("Location")
            response.close()
            if not loc:
                raise ValueError("Redirect response had no Location header.")
            current = urljoin(current, loc)
            continue
        response.raise_for_status()
        return response, current
    raise ValueError("Too many redirects.")

def _read_limited(response) -> bytes:
    length = response.headers.get("Content-Length")
    if length and int(length) > MAX_DOWNLOAD:
        raise ValueError(f"Image exceeds the {MAX_DOWNLOAD // (1024*1024)} MB download limit.")
    chunks, total = [], 0
    for chunk in response.iter_content(1024 * 128):
        if not chunk:
            continue
        total += len(chunk)
        if total > MAX_DOWNLOAD:
            raise ValueError(f"Image exceeds the {MAX_DOWNLOAD // (1024*1024)} MB download limit.")
        chunks.append(chunk)
    return b"".join(chunks)

def acquire(source: str, is_url: bool = False) -> tuple[bytes, dict]:
    """Return image bytes and source details. A URL may be a direct image or webpage."""
    if not is_url:
        path = Path(source).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        if path.stat().st_size > MAX_DOWNLOAD:
            raise ValueError(f"File exceeds the {MAX_DOWNLOAD // (1024*1024)} MB size limit.")
        data = path.read_bytes()
        return data, {"input_type": "local_file", "source": str(path.resolve()), "downloaded_bytes": len(data)}

    response, final_url = _safe_get(source, stream=False)
    content_type = response.headers.get("Content-Type", "").split(";")[0].lower()
    data = response.content
    # Direct image response, even if its extension is unusual.
    if content_type.startswith("image/") or _looks_like_image(data):
        if len(data) > MAX_DOWNLOAD:
            raise ValueError(f"Image exceeds the {MAX_DOWNLOAD // (1024*1024)} MB download limit.")
        return data, {"input_type": "image_url", "source": source, "final_url": final_url,
                      "content_type": content_type, "downloaded_bytes": len(data)}

    # HTML page: resolve common social/OpenGraph image references.
    if "html" not in content_type and not data.lstrip().lower().startswith((b"<!doctype html", b"<html")):
        raise ValueError(f"URL did not return an image or an HTML page (Content-Type: {content_type or 'unknown'}).")
    soup = BeautifulSoup(data[:5 * 1024 * 1024], "html.parser")
    candidates = []
    for selector, attr in [
        ('meta[property="og:image"]', "content"),
        ('meta[property="og:image:secure_url"]', "content"),
        ('meta[name="twitter:image"]', "content"),
        ('meta[name="twitter:image:src"]', "content"),
    ]:
        for tag in soup.select(selector):
            if tag.get(attr): candidates.append(tag[attr])
    for tag in soup.find_all("img"):
        src = tag.get("src") or tag.get("data-src")
        if src: candidates.append(src)
    page_title = soup.title.get_text(" ", strip=True) if soup.title else ""
    last_error = "No image URL was found on the webpage."
    for candidate in candidates:
        candidate_url = urljoin(final_url, candidate.strip())
        try:
            img_response, image_final = _safe_get(candidate_url, stream=True)
            img_data = _read_limited(img_response)
            img_type = img_response.headers.get("Content-Type", "").split(";")[0].lower()
            img_response.close()
            if _looks_like_image(img_data):
                return img_data, {"input_type": "webpage", "source": source, "page_url": final_url,
                                  "page_title": page_title, "image_url": candidate_url,
                                  "final_image_url": image_final, "content_type": img_type,
                                  "downloaded_bytes": len(img_data)}
            last_error = f"Candidate was not a recognized image: {candidate_url}"
        except Exception as e:
            last_error = str(e)
    raise ValueError(last_error)

def _looks_like_image(data: bytes) -> bool:
    return (data.startswith(b"\xff\xd8\xff") or data.startswith(b"\x89PNG\r\n\x1a\n")
            or data.startswith((b"GIF87a", b"GIF89a")) or data.startswith(b"BM")
            or data.startswith(b"II*\x00") or data.startswith(b"MM\x00*")
            or data.startswith(b"RIFF") and data[8:12] == b"WEBP"
            or data[4:12] == b"ftypheic" or data[4:12] == b"ftypheix"
            or data[4:12] == b"ftypmif1")

def _json_safe(value):
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (tuple, list)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k,v in value.items()}
    try:
        return str(value)
    except Exception:
        return repr(value)

def _jpeg_segments(data: bytes):
    """Extract JPEG APP/COM segment sizes and selected textual metadata."""
    result, pos = [], 2
    if not data.startswith(b"\xff\xd8"):
        return result
    while pos + 4 <= len(data) and data[pos] == 0xFF:
        marker = data[pos + 1]
        pos += 2
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            if marker == 0xD9: break
            continue
        if pos + 2 > len(data): break
        size = int.from_bytes(data[pos:pos+2], "big")
        if size < 2 or pos + size > len(data): break
        payload = data[pos+2:pos+size]
        label = {0xE0:"APP0/JFIF",0xE1:"APP1/EXIF-or-XMP",0xE2:"APP2/ICC",0x13:"APP19",0xED:"APP13/IPTC",0xFE:"COM"}.get(marker, f"APP/marker 0x{marker:02X}")
        item = {"marker": f"0x{marker:02X}", "label": label, "segment_bytes": size}
        if marker == 0xFE:
            item["comment"] = payload.decode("utf-8", "replace").strip("\x00")
        if marker == 0xE1 and payload.startswith(b"http://ns.adobe.com/xap/1.0/\x00"):
            item["xmp_preview"] = payload.split(b"\x00",1)[1][:2000].decode("utf-8","replace")
        result.append(item)
        pos += size
        if marker == 0xDA: break
    return result


def _gps_decimal(gps):
    """Convert EXIF GPS DMS values to decimal degrees when available."""
    try:
        def rational(x):
            if hasattr(x, "numerator") and hasattr(x, "denominator"):
                return float(x.numerator) / float(x.denominator)
            if isinstance(x, (tuple, list)) and len(x) == 2:
                return float(x[0]) / float(x[1])
            return float(x)
        def dms(values):
            return rational(values[0]) + rational(values[1]) / 60 + rational(values[2]) / 3600
        lat = dms(gps["GPSLatitude"])
        lon = dms(gps["GPSLongitude"])
        if str(gps.get("GPSLatitudeRef", "N")).upper() == "S": lat = -lat
        if str(gps.get("GPSLongitudeRef", "E")).upper() == "W": lon = -lon
        return {"latitude": round(lat, 8), "longitude": round(lon, 8),
                "map_url": f"https://www.openstreetmap.org/?mlat={lat:.8f}&mlon={lon:.8f}#map=16/{lat:.8f}/{lon:.8f}"}
    except Exception:
        return None

def extract_metadata(data: bytes, source_info: dict | None = None) -> dict:
    """Extract standard metadata and optionally enrich with ExifTool."""
    source_info = source_info or {}
    result = {"tool": "ImageMetaX", "source": source_info, "metadata": {}}
    md = result["metadata"]
    md["file"] = {
        "byte_size": len(data), "size_human": _human_size(len(data)),
        "sha256": hashlib.sha256(data).hexdigest(),
        "md5": hashlib.md5(data).hexdigest(),
        "mime_type_guess": mimetypes.guess_type(source_info.get("source",""))[0],
        "signature_hex": data[:32].hex(),
        "header_ascii_preview": "".join(chr(b) if 32 <= b < 127 else "." for b in data[:32])
    }
    try:
        import io
        image = Image.open(io.BytesIO(data))
        image.load()
        md["image"] = {
            "format": image.format, "format_description": Image.MIME.get(image.format),
            "width": image.width, "height": image.height,
            "aspect_ratio": round(image.width / image.height, 6) if image.height else None,
            "mode": image.mode, "bands": list(image.getbands()),
            "frames": getattr(image, "n_frames", 1), "animated": bool(getattr(image, "is_animated", False)),
            "has_transparency": "A" in image.getbands() or "transparency" in image.info,
            "dpi": _json_safe(image.info.get("dpi")),
            "icc_profile_bytes": len(image.info.get("icc_profile", b"")) if isinstance(image.info.get("icc_profile"), bytes) else None,
            "image_info": {str(k): _json_safe(v) for k,v in image.info.items() if k not in ("icc_profile",)}
        }
        exif = image.getexif()
        exif_data = {}
        gps_data = {}
        for tag_id, value in exif.items():
            name = ExifTags.TAGS.get(tag_id, str(tag_id))
            if name == "GPSInfo":
                try:
                    gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
                    gps_data = {ExifTags.GPSTAGS.get(k, str(k)): _json_safe(v) for k,v in gps_ifd.items()}
                except Exception:
                    gps_data = _json_safe(value)
            else:
                exif_data[name] = _json_safe(value)
        md["exif"] = exif_data
        md["gps"] = gps_data
        md["gps_decimal"] = _gps_decimal(gps_data) if gps_data else None
        md["jpeg_segments"] = _jpeg_segments(data) if image.format == "JPEG" else []
        # Optional ExifTool provides broader maker-note/IPTC/XMP support.
        try:
            import exiftool
            with tempfile.NamedTemporaryFile(suffix="." + (image.format or "img").lower()) as tmp:
                tmp.write(data); tmp.flush()
                with exiftool.ExifToolHelper() as et:
                    rows = et.get_metadata(tmp.name)
                result["exiftool"] = rows[0] if rows else {}
        except Exception as e:
            result["exiftool"] = {"available": False, "note": "Install ExifTool and PyExifTool for expanded maker-note/IPTC/XMP coverage.", "detail": str(e)}
    except Exception as e:
        result["image_error"] = str(e)
        result["note"] = "The file could not be decoded by Pillow. Try installing ExifTool and optional format support."
    return result

def _human_size(n):
    for unit in ("B","KB","MB","GB"):
        if n < 1024 or unit == "GB": return f"{n:.2f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
