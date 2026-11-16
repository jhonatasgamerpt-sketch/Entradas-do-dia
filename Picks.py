import os, json, html, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

BASE = "https://api.the-odds-api.com/v4"
PREF = ["basketball_nba", "soccer_uefa_nations_league", "soccer_uefa_champs_league",
        "soccer_portugal_primeira_liga", "soccer_epl", "soccer_spain_la_liga",
        "soccer_italy_serie_a", "soccer_germany_bundesliga", "soccer_france_ligue_one"]
MAX_SPORTS = 6  # cada desporto gasta 1 crédito por dia
TIERS = [("low", "Risco baixo", 0.65, 1.01, 1.15),
         ("mid", "Risco médio", 0.45, 0.65, 1.50),
         ("high", "Risco alto", 0.20, 0.45, 2.50)]  # classe, nome, prob. mín., prob. máx., odd mín.


def get(path, **params):
    params["apiKey"] = os.environ["ODDS_API_KEY"]
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def candidates(keys, now):
    out = []
    for key in keys:
        try:
            events = get(f"/sports/{key}/odds/", regions="eu", markets="h2h", oddsFormat="decimal")
        except Exception as e:
            print("Erro em", key, e)
            continue
        for ev in events:
            t = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
            if not (now < t < now + timedelta(hours=36)):
                continue
            probs, best, books = {}, {}, 0
            for bk in ev["bookmakers"]:
                mk = next((m for m in bk["markets"] if m["key"] == "h2h"), None)
                if not mk:
                    continue
                books += 1
                tot = sum(1 / o["price"] for o in mk["outcomes"])  # tira a margem da casa
                for o in mk["outcomes"]:
                    probs.setdefault(o["name"], []).append(1 / o["price"] / tot)
                    if o["price"] > best.get(o["name"], (0, ""))[0]:
                        best[o["name"]] = (o["price"], bk["title"])
            if books < 4:
                continue
            for name, ps in probs.items():
                p = sum(ps) / len(ps)
                odd, book = best[name]
                out.append(dict(
                    game=f'{ev["home_team"]} – {ev["away_team"]}',
                    pick="Empate" if name == "Draw" else name + " vence",
                    p=p, odd=odd, book=book, ev=p * odd - 1,
                    when=t.astimezone(ZoneInfo("Europe/Lisbon")).strftime("%d/%m %H:%M")))
    return out


def choose(cands):
    picks, used = [], set()
    for cls, name, lo, hi, min_odd in TIERS:
        pool = [c for c in cands if lo <= c["p"] < hi and c["odd"] >= min_odd and c["game"] not in used]
        if pool:
            c = max(pool, key=lambda c: c["ev"])
            used.add(c["game"])
            picks.append(dict(c, cls=cls, tier=name))
    return picks


CSS = """:root{--bg:#F1F4F7;--card:#fff;--ink:#0F1B2D;--mut:#566475;--line:#D3DAE1;--low:#0E7C66;--mid:#A86400;--high:#B42318}
@media(prefers-color-scheme:dark){:root{--bg:#0E1620;--card:#162231;--ink:#E8EEF4;--mut:#9DB0C1;--line:#2B3B4C;--low:#3FBF9E;--mid:#E8A33D;--high:#F27C70}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,sans-serif}
main{max-width:520px;margin:0 auto;padding:22px 16px 44px}h1{font-size:32px;margin:0 0 6px}.s{color:var(--mut);font-size:15px}
.slip{--c:var(--low);background:var(--card);border-radius:14px;border-left:7px solid var(--c);margin:16px 0}
.mid{--c:var(--mid)}.high{--c:var(--high)}.m{padding:14px 16px}.r{color:var(--c)}h2{font-size:24px;margin:2px 0}
.m p{margin:2px 0;color:var(--mut);font-size:15px}.st{border-top:2px dashed var(--line);padding:10px 16px;display:flex;justify-content:space-between;align-items:center}
.o{font-size:36px;font-weight:700;color:var(--c)}.st span{font-size:14px;color:var(--mut);text-align:right}
textarea{width:100%;min-height:170px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink);padding:10px;font:15px/1.4 system-ui}
button{margin-top:10px;width:100%;padding:12px;border:0;border-radius:10px;background:var(--low);color:#fff;font:600 16px system-ui}
footer{color:var(--mut);font-size:13px;margin-top:18px}"""
ICON = {"low": "🟢", "mid": "🟡", "high": "🔴"}


def page(picks, stamp):
    cards, lines = "", []
    for c in picks:
        e = html.escape
        cards += (f'<article class="slip {c["cls"]}"><div class="m"><b class="r">{c["tier"]}</b><h2>{e(c["pick"])}</h2>'
                  f'<p>{e(c["game"])} · {c["when"]}</p><p>Melhor preço em {e(c["book"])}</p></div>'
                  f'<div class="st"><div class="o">{c["odd"]:.2f}</div>'
                  f'<span>chance segundo o mercado: {c["p"]:.0%}<br>vs. média do mercado: {c["ev"]:+.0%}</span></div></article>')
        lines.append(f'{ICON[c["cls"]]} {c["tier"]}: {c["pick"]} ({c["game"]}, {c["when"]}), odd {c["odd"]:.2f}')
    if not picks:
        cards = '<p class="s">Hoje não há entradas que cumpram os critérios.</p>'
    msg = ("Entradas de hoje\n\n" + "\n".join(lines) +
           "\n\nOdds de várias casas, confirma na tua. Sem garantias de lucro. Stake de 1 a 2% da banca. +18")
    return (f'<!doctype html><html lang="pt-PT"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>Entradas do dia</title>'
            f'<style>{CSS}</style></head><body><main><h1>Entradas do dia</h1>'
            f'<p class="s">Atualizado a {stamp} (Lisboa)</p>{cards}'
            f'<h3>Mensagem para o grupo</h3><textarea id="t" readonly>{html.escape(msg)}</textarea>'
            f'<button onclick="var t=document.getElementById(\'t\');t.select();document.execCommand(\'copy\');this.textContent=\'Copiado\'">Copiar mensagem</button>'
            f'<footer>As chances vêm da média de várias casas, sem a margem. A vantagem é face a essa média e não garante lucro. '
            f'Aposta só o que podes perder. Só para maiores de 18 anos.</footer></main></body></html>')


def main():
    now = datetime.now(timezone.utc)
    active = {s["key"] for s in get("/sports/") if s["active"]}
    extra = [k for k in sorted(active) if "nations" in k or "friendl" in k]
    keys = [k for k in dict.fromkeys(PREF[:2] + extra + PREF[2:]) if k in active][:MAX_SPORTS]
    picks = choose(candidates(keys, now))
    stamp = now.astimezone(ZoneInfo("Europe/Lisbon")).strftime("%d/%m/%Y %H:%M")
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(page(picks, stamp))
    with open("picks.json", "w", encoding="utf-8") as f:
        json.dump(picks, f, ensure_ascii=False, indent=1)
    print(len(picks), "entradas")


if __name__ == "__main__":
    main()
