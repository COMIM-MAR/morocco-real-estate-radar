from __future__ import annotations
import re, requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from core.models import Event
HEADERS={"User-Agent":"Mozilla/5.0 MoroccoRealEstateIntelligence/3.0"}
DETAIL_MARKERS=("/a/","/pa/","/projet/","/projets/","/produits/projets/")
def clean(t): return re.sub(r"\s+"," ",t or "").strip()
def detail_like(url): return any(m in urlparse(url).path.lower() for m in DETAIL_MARKERS)
def fetch(url):
    r=requests.get(url,headers=HEADERS,timeout=20); r.raise_for_status()
    soup=BeautifulSoup(r.text,"lxml")
    for tag in soup(["script","style","svg","noscript"]): tag.decompose()
    parts=[]
    for sel in ["title", "h1", "h2"]:
        for n in soup.select(sel)[:5]: parts.append(clean(n.get_text(" ")))
    for meta in soup.find_all("meta"):
        if meta.get("content") and meta.get("name") in ("description",) or meta.get("property") in ("og:title","og:description"):
            parts.append(clean(meta.get("content")))
    parts.append(clean(soup.get_text(" ")))
    return soup, clean(" ".join(parts))[:9000]
def collect_source(channel, source):
    out=[]
    try: soup, base_text = fetch(source["url"])
    except Exception as e:
        print(f"WARN source failed: {source['name']} {source['url']} => {e}"); return out
    links=[]
    if detail_like(source["url"]): links.append((source["url"], base_text[:220]))
    for a in soup.find_all("a",href=True):
        u=urljoin(source["url"], a["href"]); t=clean(a.get_text(" "))
        if detail_like(u) and len(t)>8: links.append((u,t[:220]))
    seen=set()
    for u,t in links[:80]:
        if u in seen: continue
        seen.add(u)
        try: _, full=fetch(u)
        except Exception: full=t
        text=clean(f"{t} {full}")
        if len(text)<30: continue
        out.append(Event(channel=channel, source=source["name"], title=t or text[:180], url=u, text=text))
    return out
