from core.models import Event
from urllib.parse import quote

def collect(config):
    # Public Meta Ad Library search links. API scraping requires Meta access token; this creates watch events and dashboard shortcuts.
    out=[]
    for q in config.get("sources",{}).get("meta_ad_library_searches",[]):
        url="https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=MA&media_type=all&search_type=keyword_unordered&q="+quote(q)
        out.append(Event(channel="meta_ads_watch", source="Meta Ad Library", title=f"Meta Ads watch: {q}", url=url, text=q, launch_confidence=40, reasons=["surveillance publicité Meta à vérifier"]))
    return out
