# iDotMatrix Cloud Catalog — Preserved Snapshot

A preserved copy of the pixel-art **images** and **animations** from the official
iDotMatrix app's cloud catalog ("Cloud assets"), plus the scraper that produces
it. Kept here so the art survives even if the upstream API changes or disappears.

Companion to the Home Assistant integration
[**whybutter/idotmatrix**](https://github.com/whybutter/idotmatrix); the catalog
protocol is documented in
[its `docs/cloud-catalog.md`](https://github.com/whybutter/idotmatrix/blob/main/docs/cloud-catalog.md).

## Layout

```
assets/<size>px/<category>/<type>/<id>.<png|gif>
manifest.json     # every asset: id, category, type, size, format, path, source_url
scrape.py         # regenerates the snapshot (idempotent)
```

- **sizes:** 16px, 32px, 64px (the asset is authored per panel resolution)
- **categories:** daily, holiday, emoji, creative, business
- **types:** image (PNG), animation (GIF)

## Regenerating / updating

```bash
pip install -r requirements.txt
python3 scrape.py
```

The scraper signs + AES-encrypts each catalog request, paginates every
category × type × size, downloads each asset, and **decodes the CDN's obfuscated
text envelope** into the real PNG/GIF (strip a 32-char nonce off each end,
`+`→space, URL-decode, reverse the string, Base64-decode). It is idempotent —
existing files are skipped, so re-runs only fetch newly added assets.

## Attribution & use

These assets originate from the iDotMatrix app's cloud service. They are archived
here for **preservation and interoperability** with hardware owners already use.
Copyright in the individual artworks belongs to their original creators / the app
vendor. This repository claims no ownership of the artwork; if you are a rights
holder and want something removed, open an issue.
