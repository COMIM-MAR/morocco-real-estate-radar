from __future__ import annotations
import re
from core.models import Event
RENTAL=["à louer","a louer","location","par mois","/mois","mensuel"]
SALE=["à vendre","a vendre","vente","vendre","lotissement","projet","commercialisation","lancement","réservation","reservation","pré-commercialisation","pre-commercialisation"]
EARLY=["lancement","pré-commercialisation","pre-commercialisation","réservation","reservation","ouverture des ventes","commercialisation","nouveau projet","lotissement","permis de construire","permis de lotir"]
def has(t, arr): return any(x.lower() in t for x in arr)
def price(text):
    patterns=[r"(\d+(?:[.,]\d+)?)\s*(?:mdh|million|millions)", r"(\d[\d\s.,]{4,})\s*(?:dh|dhs|mad|dirhams)", r"(?:prix|à partir de|a partir de)\s*(?:de)?\s*(\d[\d\s.,]{4,})"]
    for p in patterns:
        for m in re.finditer(p,text,re.I):
            raw=m.group(1); full=m.group(0).lower()
            if "mdh" in full or "million" in full:
                try: return int(float(raw.replace(",","."))*1_000_000)
                except: pass
            val=int(re.sub(r"\D","",raw) or 0)
            if 100000 <= val <= 30000000: return val
    return None
def classify_asset(title, text, prefs):
    s=(title+" "+text).lower(); tt=title.lower()
    checks=[("villa",r"\b(villa|villas)\b"),("land_r4_plus",r"\b(r\+4|r4|r\+5|r5|terrain|lotissement|lot de terrain|lots de terrain|immeuble)\b"),("penthouse",r"\bpenthouse\b"),("apartment_3_bed",r"\b(3 chambres|3ch|3 ch|f4|4 pièces|4 pieces)\b"),("apartment_2_bed",r"\b(2 chambres|2ch|2 ch|f3|3 pièces|3 pieces)\b"),("studio",r"\bstudio\b")]
    for name,rx in checks:
        if re.search(rx,tt): return name,prefs.get(name,0)
    for name,rx in checks:
        if re.search(rx,s): return name,prefs.get(name,0)
    if re.search(r"\b(appartement|appart|résidence|residence)\b",tt): return "apartment_unknown",35
    return None,0
def city_zone(ev, cfg):
    scope=f"{ev.source} {ev.title} {ev.url}".lower(); best=(None,None,0)
    for ck,c in cfg["cities"].items():
        if ck in scope or c["label"].lower() in scope: best=(ck,best[1],best[2])
        for z in c.get("zones",[]):
            if z.lower() in scope: best=(ck,z,90)
    return best
def score(ev: Event, cfg):
    t=(ev.title+" "+ev.text).lower(); reasons=[]
    if has(t, RENTAL): ev.total_score=0; ev.reasons=["exclu: location"]; return ev
    if ev.channel=="listing" and not has(t, SALE): ev.total_score=0; ev.reasons=["exclu: pas un signal vente/projet"]; return ev
    ev.city,ev.zone,zw=city_zone(ev,cfg)
    if ev.city: reasons.append(f"ville: {cfg['cities'][ev.city]['label']}")
    if ev.zone: reasons.append(f"zone: {ev.zone}")
    ev.asset_type, aw=classify_asset(ev.title, ev.text, cfg["asset_preferences"])
    if ev.asset_type: reasons.append(f"type: {ev.asset_type}")
    ev.price_mad=price(t)
    if ev.price_mad: reasons.append(f"prix détecté: {ev.price_mad} MAD")
    opp=0; conf=0
    if ev.city: opp += round(cfg["cities"][ev.city]["priority"]*0.15)
    if ev.zone: opp += 12
    if ev.asset_type: opp += round(aw*0.22)
    if ev.price_mad:
        if ev.price_mad <= cfg["profile"]["cash_ready"]: opp += 12
        elif ev.price_mad <= cfg["profile"]["max_budget"]: opp += 8
        else: opp -= 25
    hits=[x for x in EARLY if x in t]
    if hits: conf += 35; reasons.append("signal lancement: "+", ".join(hits[:3]))
    if ev.channel=="promoter": conf += 30
    if ev.channel=="meta_ads_watch": conf += 40
    if ev.channel=="listing": conf += 12
    ev.opportunity_score=max(0,min(100,opp)); ev.launch_confidence=max(0,min(100,conf+ev.launch_confidence)); ev.total_score=max(0,min(100,round(ev.opportunity_score*0.65+ev.launch_confidence*0.35)))
    ev.reasons=reasons+ev.reasons
    return ev
