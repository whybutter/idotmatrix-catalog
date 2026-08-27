#!/usr/bin/env python3
"""Snapshot the official iDotMatrix app's cloud catalog to disk.

Downloads every image and animation across all categories and panel sizes,
decodes the CDN's obfuscated asset envelope into real PNG/GIF files, and writes
a manifest.json. Idempotent: existing files are skipped, so re-runs only fetch
new assets.

Protocol reference: https://github.com/whybutter/idotmatrix/blob/main/docs/cloud-catalog.md
Only dependency: `cryptography` (pip install -r requirements.txt).
"""
import base64, hashlib, json, os, random, string, time, urllib.parse, urllib.request
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

APP_KEY = b"Jy47rzJAgKMfrcc92PamyyukQqB7wmFu"
IV = b"0000000000000000"
API = "https://manage.heaton.com.cn/api/rm/getMaterialUnderCategory"
UA = "okhttp/5.1.0"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# (chinese_tab, slug, English)
CATEGORIES = [
    ("日常", "daily", "Daily"),
    ("节日", "holiday", "Holiday"),
    ("表情", "emoji", "Emoji"),
    ("创意", "creative", "Creative"),
    ("商业", "business", "Business"),
]
# (chinese_type, slug, extension)
TYPES = [("图片", "image", "png"), ("动画", "animation", "gif")]
SIZES = [16, 32, 64]
PACE = 0.2  # seconds between requests (be polite)


def java_url_encode(s):
    out = []
    for b in s.encode("utf-8"):
        c = chr(b)
        if c.isascii() and (c.isalnum() or c in ".*-_"):
            out.append(c)
        elif c == " ":
            out.append("+")
        else:
            out.append("%%%02X" % b)
    return "".join(out).replace("%26", "&").replace("%3D", "=").replace("%3F", "?")


def sorted_q(p):
    return "&".join(f"{k}={p[k]}" for k in sorted(p))


def _aes():
    return Cipher(algorithms.AES(APP_KEY), modes.CBC(IV))


def enc(plain):
    pad = padding.PKCS7(128).padder()
    d = pad.update(plain.encode("utf-8")) + pad.finalize()
    e = _aes().encryptor()
    return base64.b64encode(e.update(d) + e.finalize()).decode("ascii")


def dec(b64):
    x = _aes().decryptor()
    raw = x.update(base64.b64decode(b64)) + x.finalize()
    u = padding.PKCS7(128).unpadder()
    return (u.update(raw) + u.finalize()).decode("utf-8")


def api_call(params):
    rnd = "".join(random.choices(string.ascii_letters + string.digits, k=8))
    ts = str(int(time.time() * 1000))
    signed = {**params, "random": rnd, "timestamp": ts, "app_key": APP_KEY.decode()}
    sign = hashlib.md5(java_url_encode(sorted_q(signed)).encode()).hexdigest().lower()
    body = enc(java_url_encode(sorted_q(params)))
    url = f"{API}?sign={sign}&timestamp={ts}&random={rnd}"
    req = urllib.request.Request(
        url, data=body.encode(),
        headers={"Content-Type": "text/plain; charset=utf-8", "User-Agent": UA},
        method="POST")
    text = urllib.request.urlopen(req, timeout=30).read().decode()
    return json.loads(dec(text.strip())).get("data") or {}


def list_page(category_cn, type_cn, size, page, count=50):
    return api_call({
        "appid": "140", "sort": "1", "page": str(page), "count": str(count),
        "category_name": f"{category_cn}_IDM", "type": type_cn,
        "width": str(size), "height": str(size),
        "label": "ALL", "filter_tags": "ALL", "file_lang": "none,cn",
    })


def decode_asset(text):
    if len(text) <= 64:
        return None
    s = text[32:len(text) - 32].replace("+", " ")
    s = urllib.parse.unquote(s, encoding="utf-8", errors="replace")
    s = s[::-1].strip().replace("\r", "").replace("\n", "")
    try:
        return base64.b64decode(s)
    except Exception:
        return None


def fetch_asset(file_path):
    req = urllib.request.Request(file_path, headers={"User-Agent": UA, "Connection": "close"})
    text = urllib.request.urlopen(req, timeout=30).read().decode("latin1")
    return decode_asset(text)


def asset_id(file_path):
    return file_path.rstrip("/").split("/")[-1]


def main():
    manifest = []
    counts = {}
    for size in SIZES:
        for cat_cn, cat_slug, cat_en in CATEGORIES:
            for type_cn, type_slug, ext in TYPES:
                page = 1
                total_pages = None
                got = 0
                while total_pages is None or page <= total_pages:
                    try:
                        data = list_page(cat_cn, type_cn, size, page)
                    except Exception as e:
                        print(f"  ! list {cat_slug}/{type_slug}/{size}px p{page}: {e}")
                        time.sleep(1.0)
                        continue
                    if total_pages is None:
                        total = int(data.get("totalCount", 0))
                        total_pages = int(data.get("totalPage", 0))
                        if total == 0:
                            break
                    for rec in data.get("records", []):
                        fp = rec.get("file_path")
                        if not fp:
                            continue
                        fmt = rec.get("format", ext)
                        aid = asset_id(fp)
                        rel = os.path.join(f"{size}px", cat_slug, type_slug, f"{aid}.{fmt}")
                        dest = os.path.join(OUT, rel)
                        entry = {
                            "id": aid, "category": cat_slug, "category_cn": cat_cn,
                            "category_en": cat_en, "type": type_slug, "format": fmt,
                            "size": size, "path": os.path.join("assets", rel),
                            "source_url": fp,
                        }
                        if os.path.exists(dest):
                            entry["bytes"] = os.path.getsize(dest)
                            manifest.append(entry)
                            got += 1
                            continue
                        try:
                            b = fetch_asset(fp)
                        except Exception as e:
                            print(f"    ! fetch {aid}: {e}")
                            b = None
                        if not b:
                            continue
                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                        with open(dest, "wb") as f:
                            f.write(b)
                        entry["bytes"] = len(b)
                        manifest.append(entry)
                        got += 1
                        time.sleep(PACE)
                    page += 1
                    time.sleep(PACE)
                counts[f"{size}px/{cat_slug}/{type_slug}"] = got
                print(f"[{size}px] {cat_en} {type_slug}: {got}")
    manifest.sort(key=lambda x: (x["size"], x["category"], x["type"], x["id"]))
    with open(os.path.join(os.path.dirname(OUT), "manifest.json"), "w") as f:
        json.dump({"generated_from": "manage.heaton.com.cn appid 140",
                   "total": len(manifest), "counts": counts,
                   "assets": manifest}, f, indent=2, ensure_ascii=False)
    print(f"\nDONE. {len(manifest)} assets. manifest.json written.")


if __name__ == "__main__":
    main()
