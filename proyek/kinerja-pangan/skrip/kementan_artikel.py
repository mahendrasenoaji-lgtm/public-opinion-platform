"""Judul dan tanggal 20 artikel terbaru pertanian.go.id (Kementan), untuk unggahan CSV situs resmi.

Halaman daftar berita Kementan tidak menampilkan tanggal, jadi pembaca otomatis platform tidak
bisa memakainya. Keputusan peneliti 18 Nov 2026 (perluasan pengecualian 15 Nov, khusus Kementan):
halaman artikel boleh dibuka, paling banyak 20, hanya judul (og:title) dan tanggal terbit yang
diambil; isi artikel tidak disimpan. Identitas jujur (USER_AGENT platform), robots.txt dipatuhi
(Allow: /, hanya /admin/ dan /writable/ dilarang), jeda 1 detik antar-permintaan.

Pakai: python3 -I skrip/kementan_artikel.py data/situs_kementan_YYYY-MM-DD.csv
"""
import csv
import re
import sys
import time
import urllib.request

UA = "AIPublicOpinionPlatform/0.1 (+feed reader; contact via platform admin)"
MAX_ARTICLES = 20
LIST_PAGES = ["https://pertanian.go.id/index.php/news/all/0", "https://www.pertanian.go.id/news/all/2"]


def get(url):
    time.sleep(1)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


ids = []
for page in LIST_PAGES:
    for i in re.findall(r"news/view/(\d+)", get(page)):
        if i not in ids:
            ids.append(i)
    if len(ids) >= MAX_ARTICLES:
        break
ids = sorted(ids, key=int, reverse=True)
# Halaman daftar hanya memuat 8 tautan; ID artikel berurutan, jadi sisa jatah diisi ID sebelumnya.
while ids and len(ids) < MAX_ARTICLES:
    ids.append(str(int(ids[-1]) - 1))
ids = ids[:MAX_ARTICLES]

rows = []
for i in ids:
    url = f"https://pertanian.go.id/news/view/{i}"
    s = get(url)
    titles = re.findall(r'<meta property="og:title" content="([^"]*)"', s)
    title = next((t for t in titles if t != "Kementerian Pertanian Republik Indonesia"), "")
    m = re.search(r"fa-calendar-days[^<]*</i>\s*(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", s)
    if not m:
        print("tanpa tanggal:", url, file=sys.stderr)
        continue
    stamp = m.group(1).replace(" ", "T") + "+07:00"  # tampil di situs tanpa zona; dibaca sebagai WIB
    rows.append(dict(url=url, title=title, published_at=stamp, category="berita"))

with open(sys.argv[1], "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["url", "title", "published_at", "category"])
    w.writeheader()
    w.writerows(rows)
print(f"{len(rows)} artikel; {len(ids) + 2} permintaan maksimal", file=sys.stderr)
