import json
from .config import load_config, DATA_DIR
from .scoring import score
from .storage import is_new
from .notifier import notify
from .dashboard import build
from collectors.web import collect_source
from collectors.meta_ads import collect as collect_meta

def run():
    cfg=load_config(); DATA_DIR.mkdir(exist_ok=True)
    events=[]
    for s in cfg.get("sources",{}).get("promoters",[]): events += collect_source("promoter", s)
    for s in cfg.get("sources",{}).get("listings",[]): events += collect_source("listing", s)
    events += collect_meta(cfg)
    scored=[score(e,cfg) for e in events]
    scored=sorted(scored,key=lambda e:e.total_score,reverse=True)
    (DATA_DIR/"all_events.json").write_text(json.dumps([e.to_dict() for e in scored],ensure_ascii=False,indent=2),encoding="utf-8")
    build(scored[:100])
    min_score=cfg["alerts"]["min_score_immediate"]; max_items=cfg["alerts"]["max_items_per_email"]
    alerts=[]
    for e in scored:
        if e.total_score < min_score: continue
        if cfg["alerts"].get("suppress_seen_urls",True) and not is_new(e.channel,e.url): continue
        alerts.append(e)
        if len(alerts)>=max_items: break
    if alerts: notify(alerts)
    else: print("No new high-quality signal to email")
    (DATA_DIR/"latest_alerts.json").write_text(json.dumps([e.to_dict() for e in alerts],ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Collected={len(events)} Scored={len(scored)} Alerts={len(alerts)}")
