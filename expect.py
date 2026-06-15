# -*- coding: utf-8 -*-
"""
expect.py — 기대가격 엔진 (단지 단위)
지역이 아니라 (지역, 단지명) 단위로 현 시세·기대가격을 산출하고,
예산 타겟존(config.TARGET_BUDGET)에 드는 단지만 추려 '여력 높은 순'으로 정렬.
※ 최고가가 아니라 '최근 실거래 중앙값'을 현 시세로 사용 → 고점 추종 방지.
"""
import sqlite3, statistics
import config as C

def complex_rows(con):
    """(지역,단지) 단위 최근 실거래 중앙값. 전용 84㎡대, 호가 제외."""
    amin, amax = C.TARGET_AREA
    rows = con.execute("""
        SELECT region, apt, price, deal_ym, deal_d FROM trades
        WHERE area BETWEEN ? AND ? AND source!='manual_listing'
        ORDER BY deal_ym DESC, deal_d DESC
    """, (amin, amax)).fetchall()
    buckets = {}
    for region, apt, price, ym, d in rows:
        if price <= 0: continue
        buckets.setdefault((region, apt), []).append((ym, price))
    out = {}
    for key, lst in buckets.items():
        prices = [p for _, p in lst[:12]]          # 단지당 최근 12건까지
        out[key] = {
            "median": round(statistics.median(prices)),
            "low":    min(prices),                 # 단지 내 최근 저가 (협상 기준)
            "n":      len(prices),
            "last_ym": lst[0][0],
        }
    return out

def listing_for(con, region, apt):
    amin, amax = C.TARGET_AREA
    rows = con.execute("""SELECT price FROM trades
        WHERE region=? AND apt=? AND area BETWEEN ? AND ? AND source='manual_listing'""",
        (region, apt, amin, amax)).fetchall()
    ps = [r[0] for r in rows if r[0] > 0]
    return statistics.median(ps) if ps else None

def pattern_weight(region):
    st = C.REGION_STATE.get(region, {})
    w  = C.STAGE_FACTORS.get(st.get("stage", "없음"), 0)
    w += C.FAB_FACTORS.get(st.get("fab", "없음"), 0)
    w += C.UNSOLD_FACTORS.get(st.get("unsold", "보합"), 0)
    return w

def location_score(region, apt, cur, region_currents):
    """단지 입지점수(0~100). 여력과 분리된 별도 지표.
    수동(LOCATION_SCORES) 입력이 있으면 4개 항목 가중평균, 없으면 지역 내 시세 백분위로 자동추정."""
    manual = C.LOCATION_SCORES.get((region, apt))
    if manual:
        score = round(sum(manual.get(k, 50) * w for k, w in C.LOCATION_WEIGHTS.items()))
        return max(0, min(100, score)), "manual", manual
    arr = region_currents.get(region, [])
    if len(arr) < 2:
        return 50, "auto", None
    # 같은 지역 안에서 현 시세 백분위 (싼쪽 0 ~ 비싼쪽 100). 비쌀수록 입지 우위로 간주.
    rank = sum(1 for v in arr if v < cur)
    pct = round(100 * rank / (len(arr) - 1))
    return max(0, min(100, pct)), "auto", None

def evaluate(con, budget_only=True):
    """단지별 기대가격 산출 → 예산 안 단지를 여력순으로 정렬해 반환."""
    lo, hi = C.TARGET_BUDGET
    comps = complex_rows(con)
    # 입지점수 자동추정용: 지역별 현 시세 분포 (MIN_TRADES 통과 단지만)
    region_currents = {}
    for (region, apt), m in comps.items():
        if m["n"] >= C.MIN_TRADES:
            region_currents.setdefault(region, []).append(m["median"])
    for region in region_currents:
        region_currents[region].sort()
    out = []
    for (region, apt), m in comps.items():
        if m["n"] < C.MIN_TRADES:        # 거래 너무 적은 단지 제외(노이즈)
            continue
        cur = m["median"]
        w = pattern_weight(region)
        base = cur * (1 + w)
        bands = {k: round(base * (1 + b)) for k, b in C.SCENARIO_BANDS.items()}
        in_budget = lo <= cur <= hi
        loc, loc_src, loc_sub = location_score(region, apt, cur, region_currents)
        out.append({
            "region": region, "apt": apt, "tag": C.REGIONS[region]["tag"],
            "current": cur, "low": m["low"], "n": m["n"], "last_ym": m["last_ym"],
            "listing": listing_for(con, region, apt),
            "\ubcf4\uc218": bands["\ubcf4\uc218"], "\uc911\ub9bd": bands["\uc911\ub9bd"], "\ub099\uad00": bands["\ub099\uad00"],
            "upside": round((bands["\uc911\ub9bd"]/cur - 1) * 100, 1),
            "loc": loc, "loc_src": loc_src, "loc_sub": loc_sub,
            "in_budget": in_budget,
        })
    if budget_only:
        out = [o for o in out if o["in_budget"]]
    # 핵심 정렬: 예산 안에서 여력(중립 상승률) 높은 순
    out.sort(key=lambda x: x["upside"], reverse=True)
    return out

if __name__ == "__main__":
    con = sqlite3.connect(C.DB_PATH)
    rows = evaluate(con)
    con.close()
    lo, hi = C.TARGET_BUDGET
    print(f"\uc608\uc0b0 {lo/10000:.1f}~{hi/10000:.1f}\uc5b5 \u00b7 \uc804\uc6a9 84\u33a1 \u00b7 \uc5ec\ub825 \ub192\uc740 \uc21c\n")
    for r in rows:
        print(f"{(r['region']+'\u00b7'+r['apt'])[:27]:28s}"
              f"{r['current']/10000:7.1f}\uc5b5 \u2192 \uc911\ub9bd{r['\uc911\ub9bd']/10000:6.1f}\uc5b5"
              f"{r['upside']:+6.1f}%  [{r['tag']}]")
    if not rows:
        print("\uc608\uc0b0 \uc548\uc5d0 \ub4dc\ub294 \ub2e8\uc9c0\uac00 \uc5c6\uc2b5\ub2c8\ub2e4. config.TARGET_BUDGET \ud655\uc778.")
