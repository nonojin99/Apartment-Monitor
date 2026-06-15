# -*- coding: utf-8 -*-
"""seed.py — 단지별 샘플 실거래 (전용 84㎡, 만원). 7억 전후 타겟 검증용."""
import sqlite3, datetime, os
import config as C

# (지역, 단지명): [최근 실거래 몇 건] — 7억 전후가 섞이도록 구성
SEED = {
    ("동탄","동탄역롯데캐슬"):        [205000, 198000, 208000],   # 예산밖(고가)
    ("동탄","동탄2신도시푸르지오"):   [82000, 79000, 84000],      # 예산 상단
    ("동탄","시범한빛마을"):          [73000, 71000, 75000],      # 예산 핵심
    ("동탄","숲속마을자연앤"):        [68000, 66000, 70000],      # 예산 핵심
    ("수원_망포","망포역반도유보라"): [76000, 74000, 78000],      # 예산 핵심
    ("수원_망포","힐스테이트영통"):   [88000, 86000],             # 예산밖(약간 위)
    ("수원_영통","영통아이파크캐슬"): [79000, 77000, 81000],      # 예산 상단
    ("수원_영통","황골마을주공"):     [64000, 62000, 66000],      # 예산 하단
    ("용인_수지","수지구청역롯데캐슬"):[83000, 80000, 85000],     # 예산 상단
    ("용인_수지","성복역롯데캐슬"):   [105000, 102000],           # 예산밖
    ("용인_처인이동","역북서희스타힐스"):[56000, 54000, 58000],   # 예산 아래(저평가)
    ("용인_처인이동","용인행정타운두산위브"):[67000, 65000, 69000], # 예산 핵심
    ("평택_고덕지제","고덕신도시자연앤자이"):[72000, 70000, 74000],# 예산 핵심
    ("평택_고덕지제","지제역더샵센트럴시티"):[78000, 76000, 80000],# 예산 상단
    ("평택_고덕지제","고덕국제신도시제일풍경채"):[64000, 62000, 66000],# 예산 하단
}

os.makedirs("data", exist_ok=True)
con = sqlite3.connect(C.DB_PATH)
con.execute("""CREATE TABLE IF NOT EXISTS trades(
    region TEXT, apt TEXT, area REAL, floor INT, price INT,
    deal_ym TEXT, deal_d INT, source TEXT, ingested TEXT,
    UNIQUE(region, apt, area, floor, price, deal_ym, deal_d, source))""")
today = datetime.date.today()
for (region, apt), prices in SEED.items():
    for i, p in enumerate(prices):
        ym = (today.replace(day=1) - datetime.timedelta(days=30*i)).strftime("%Y%m")
        con.execute("INSERT OR IGNORE INTO trades VALUES(?,?,?,?,?,?,?,?,?)",
            (region, apt, 84.9, 12+i, p, ym, 10+i, "csv", today.isoformat()))
# 호가 샘플
for region, apt, price in [("동탄","시범한빛마을",75000),("평택_고덕지제","고덕신도시자연앤자이",73500)]:
    con.execute("INSERT OR IGNORE INTO trades VALUES(?,?,?,?,?,?,?,?,?)",
        (region, apt, 84.9, 20, price, today.strftime("%Y%m"), today.day, "manual_listing", today.isoformat()))
con.commit(); con.close()
print("\ub2e8\uc9c0\ubcc4 \uc2dc\ub4dc \ub370\uc774\ud130 \uc801\uc7ac \uc644\ub8cc")
