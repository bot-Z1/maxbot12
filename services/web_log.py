import os
import json
import traceback
import requests
from datetime import datetime, timezone

WEBHOOK_CACHE = {"url": "", "time": 0}


def _get_db_webhook_url():
    import psycopg2
    dsn = os.getenv("DATABASE_URL", "")
    if not dsn:
        return ""
    try:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute("SELECT value FROM bot_config WHERE key = 'webhook_url'")
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row[0] if row else ""
    except Exception:
        return ""


def get_webhook_url():
    now = datetime.now(timezone.utc).timestamp()
    if now - WEBHOOK_CACHE["time"] > 60 or not WEBHOOK_CACHE["url"]:
        WEBHOOK_CACHE["url"] = _get_db_webhook_url()
        WEBHOOK_CACHE["time"] = now
    return WEBHOOK_CACHE["url"]


def _build_embed(color, title, description, fields, thumbnail=None):
    e = {
        "color": color,
        "title": title[:256],
        "description": description[:4096],
        "fields": [{"name": f["name"][:256], "value": f["value"][:1024], "inline": f.get("inline", False)} for f in fields],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if thumbnail:
        e["thumbnail"] = {"url": thumbnail}
    return e


def send_webhook(webhook_url, embed):
    if not webhook_url:
        return False
    try:
        r = requests.post(webhook_url, json={"embeds": [embed]}, timeout=10,
                          headers={"Content-Type": "application/json"})
        return r.ok
    except Exception:
        return False


def build_info_embed(path, ip, user_name, user_id, user_agent, referer, time_on_page, screen, geo_city, geo_country, geo_org, platform, browser):
    fields = [
        {"name": "👤  المستخدم", "value": f"الاسم: {user_name or 'زائر'}\nالمعرف: {user_id or '—'}", "inline": True},
        {"name": "🌐  الجهاز", "value": f"IP: {ip or '—'}\nالموقع: {geo_city or '—'}, {geo_country or '—'}\nالمزود: {geo_org or '—'}", "inline": True},
        {"name": "📱  النظام", "value": f"المتصفح: {browser or '—'}\nالنظام: {platform or '—'}", "inline": True},
        {"name": "📄  الصفحة", "value": f"المسار: {path or '—'}\nالمرجع: {referer or '—'}\nالمدة: {time_on_page or '—'}", "inline": False},
    ]
    if screen:
        fields.insert(2, {"name": "📐  الشاشة", "value": screen, "inline": True})
    embed = _build_embed(
        color=0x5865F2,
        title=f"📋  معلومات — {path}",
        description=f"زيارة من {user_name or 'زائر'}",
        fields=fields,
    )
    return embed


def build_error_embed(status_code, path, ip, user_name, user_agent, details=None, referer=None):
    if status_code == 404:
        color = 0xFEE75C
        title = f"⚠️  404 — الصفحة غير موجودة"
        desc = f"المسار `{path}` غير موجود"
    elif status_code == 500:
        color = 0xED4245
        title = f"🔴  500 — خطأ داخلي في الخادم"
        desc = f"حدث خطأ في `{path}`"
    else:
        color = 0xED4245
        title = f"❌  خطأ {status_code}"
        desc = f"خطأ في `{path}`"

    fields = [
        {"name": "📄  الصفحة", "value": path or "—", "inline": True},
        {"name": "🖥️  IP", "value": f"{ip or '—'}  •  {user_name or 'زائر'}", "inline": True},
        {"name": "📱  الجهاز", "value": user_agent or "—", "inline": False},
    ]
    if referer:
        fields.append({"name": "🔗  المرجع", "value": referer, "inline": False})
    if details:
        short = details[:1000]
        fields.append({"name": "📋  التفاصيل", "value": f"```{short}```", "inline": False})

    embed = _build_embed(color=color, title=title, description=desc, fields=fields)
    return embed


def build_suspicion_embed(fp, score, verdict, checks, ip, user_name, user_id, path, platform, browser, geo_city, geo_country, geo_org, prev_hacks):
    if score >= 19:
        color = 0xED4245
        level = "🔴  خطر — مؤكد هاكر / بوت"
    elif score >= 9:
        color = 0xFEE75C
        level = "🟡  مشبوه جداً"
    else:
        color = 0xF1C40F
        level = "🟠  مشبوه قليلاً"

    checks_text = "\n".join(checks[:15])
    if len(checks) > 15:
        checks_text += f"\n...و {len(checks) - 15} فحص آخر"

    device_hash = fp.get("device_hash", "—")
    gpu = (fp.get("gpu_renderer", "—") or "—")[:50]
    ram = fp.get("ram_size", "?")
    cpu = fp.get("cpu_cores", "?")
    screen = fp.get("screen", "—")
    time_on_page = fp.get("time_on_page", 0)
    incognito = "🟢 لا" if not fp.get("incognito") else "🔴 نعم"

    fields = [
        {"name": "👤  المستخدم", "value": f"الاسم: {user_name or 'زائر'}\nالمعرف: {user_id or '—'}", "inline": True},
        {"name": "🖥️  الموقع", "value": f"IP: {ip or '—'}\nالموقع: {geo_city or '—'}, {geo_country or '—'}\nالمزود: {geo_org or '—'}", "inline": True},
        {"name": "📱  الجهاز", "value": f"المتصفح: {browser or '—'}\nالنظام: {platform or '—'}\nالشاشة: {screen}", "inline": True},
        {"name": "🔍  المواصفات", "value": f"GPU: {gpu}\nRAM: {ram}GB\nCPU: {cpu} cores", "inline": True},
        {"name": "🕶️  التصفح الخفي", "value": incognito, "inline": True},
        {"name": "⏱  الوقت على الصفحة", "value": f"{time_on_page}ms", "inline": True},
        {"name": "🔬  تحليل البصمة (Score: {}/30)".format(score), "value": f"```{checks_text}```", "inline": False},
        {"name": "📄  الصفحة", "value": path or "—", "inline": True},
        {"name": "🆔  بصمة الجهاز", "value": f"`{device_hash[:20]}...`", "inline": True},
    ]
    if prev_hacks:
        fields.append({"name": "⚠️  سجل سابق", "value": f"تم القبض عليه {len(prev_hacks)} مرة سابقة", "inline": False})

    embed = _build_embed(
        color=color,
        title=f"⚠️  نشاط مشبوه — تقرير أمني | {level}",
        description=f"Score: {score}/30 — {verdict}",
        fields=fields,
    )
    return embed


def send_info(webhook_url, path, ip, user_name=None, user_id=None, user_agent=None, referer=None, time_on_page=None, screen=None, geo_city=None, geo_country=None, geo_org=None, platform=None, browser=None):
    embed = build_info_embed(path, ip, user_name, user_id, user_agent, referer, time_on_page, screen, geo_city, geo_country, geo_org, platform, browser)
    return send_webhook(webhook_url, embed)


def send_error(webhook_url, status_code, path, ip, user_name=None, user_agent=None, details=None, referer=None):
    embed = build_error_embed(status_code, path, ip, user_name, user_agent, details, referer)
    return send_webhook(webhook_url, embed)


def send_suspicion(webhook_url, fp, score, verdict, checks, ip, user_name=None, user_id=None, path=None, platform=None, browser=None, geo_city=None, geo_country=None, geo_org=None, prev_hacks=None):
    embed = build_suspicion_embed(fp, score, verdict, checks, ip, user_name, user_id, path, platform, browser, geo_city, geo_country, geo_org, prev_hacks or [])
    return send_webhook(webhook_url, embed)
