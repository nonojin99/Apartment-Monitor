# -*- coding: utf-8 -*-
"""
collect.py — 실거래 데이터 수집 및 DB 적재
- 기본: 국토부에서 받은 월별 CSV를 data/ 에 넣고 적재 (키 불필요, 지금 바로 사용)
- 옵션: config.API_KEY 입력 시 API 자동수집 활성화

사용법:
  python collect.py test                  # ★먼저 키 검증 (1회 호출)
  python collect.py csv                    # data/*.csv 전부 적재
  python collect.py api 202501 202506      # API로 기간 수집 (키 필요)
  python collect.py manual                 # 매물 호가 수동 한 줄 입력
"""
import sqlite3, sys, glob, os, csv, datetime
import config as C

def db():
    os.makedirs(os.path.dirname(C.DB_PATH), exist_ok=True)
    con = sqlite3.connect(C.DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS trades(
        region TEXT, apt TEXT, area REAL, floor INT,
        price INT,            -- 만원 단위
        deal_ym TEXT,         -- YYYYMM
        deal_d INT,
        source TEXT,          -- 'csv' | 'api' | 'manual_listing'
        ingested TEXT,
        UNIQUE(region, apt, area, floor, price, deal_ym, deal_d, source)
    )""")
    return con

# ── 국토부 월별 CSV 적재 ────────────────────────────────────────
# 국토부 실거래가 공개시스템(rt.molit.go.kr)에서 시군구별 월별 CSV 직접 다운로드 가능.
# CSV 컬럼은 다운로드 시점에 따라 다르므로, 아래 매핑을 실제 헤더에 맞춰 조정.
CSV_MAP = {  # 표준 한글 헤더 → 내부 필드
    "단지명": "apt", "전용면적(㎡)": "area", "층": "floor",
    "거래금액(만원)": "price", "계약년월": "deal_ym", "계약일": "deal_d",
}

def load_csv():
    con = db(); n = 0
    files = glob.glob("data/*.csv")
    if not files:
        print("data/ 폴더에 국토부 CSV가 없습니다. rt.molit.go.kr에서 받아 넣어주세요.")
        return
    # 파일명 앞부분(별칭) → config 지역 키 매핑.
    # CSV 파일명을 자유롭게 지어도 인식되도록 별칭을 넓게 둠.
    ALIAS = {
        "동탄": "동탄",
        "평택": "평택_고덕지제", "고덕": "평택_고덕지제", "지제": "평택_고덕지제",
        "영통": "수원_영통",
        "망포": "수원_망포",
        "처인": "용인_처인이동", "이동": "용인_처인이동",
        "수지": "용인_수지",
    }
    for f in files:
        # 파일명 앞부분(첫 _ 또는 . 이전)을 별칭으로 사용: 예) 평택_2026.csv → 평택
        head = os.path.basename(f).split("_")[0].split(".")[0]
        region = ALIAS.get(head) or (head if head in C.REGIONS else None)
        if region is None:
            print(f"  [skip] {f}: '{head}'을(를) 인식 못함. 파일명 앞을 {list(ALIAS)} 중 하나로.")
            continue
        with open(f, encoding="cp949", errors="ignore") as fh:
            # 국토부 CSV는 상단에 안내문구가 있어 헤더 줄을 찾아 건너뜀
            lines = fh.readlines()
        hdr_idx = next((i for i,l in enumerate(lines) if "단지명" in l), 0)
        header = next(csv.reader([lines[hdr_idx]]))
        # 컬럼 인덱스 확보 (헤더 이름 기준)
        def col(name):
            return next((i for i,h in enumerate(header) if name in h), None)
        i_apt, i_area = col("단지명"), col("전용면적")
        i_floor, i_price = col("층"), col("거래금액")
        i_ym, i_day = col("계약년월"), col("계약일")
        if i_price is None:
            print(f"  [skip] {f}: '거래금액' 컬럼을 못 찾음. 헤더 확인 필요.")
            continue
        for line in lines[hdr_idx+1:]:
            if not line.strip():
                continue
            try:
                cells = next(csv.reader([line]))   # 따옴표 안 콤마 정상 처리
                def cell(idx):
                    return cells[idx].strip() if idx is not None and idx < len(cells) else ""
                price = int(cell(i_price).replace(",", "") or 0)
                if price <= 0:
                    continue
                area = float(cell(i_area) or 0)
                con.execute("""INSERT OR IGNORE INTO trades VALUES(?,?,?,?,?,?,?,?,?)""",
                    (region, cell(i_apt), area,
                     int(cell(i_floor) or 0), price,
                     cell(i_ym), int(cell(i_day) or 0),
                     "csv", datetime.date.today().isoformat()))
                n += 1
            except (ValueError, TypeError, StopIteration, IndexError):
                continue
    con.commit(); con.close()
    print(f"CSV 적재 완료: {n}건")

# ── API 자동수집 (키 발급 후) ──────────────────────────────────
def _get_with_retry(requests, params, name, ym, tries=3, timeout=60):
    """타임아웃/일시 오류 시 점진적 백오프로 재시도."""
    import time
    for attempt in range(1, tries + 1):
        try:
            return requests.get(C.API_URL, params=params, timeout=timeout)
        except Exception as e:
            if attempt < tries:
                wait = attempt * 3
                print(f"  [재시도 {attempt}/{tries-1}] {name} {ym}: {type(e).__name__} → {wait}초 후 다시")
                time.sleep(wait)
            else:
                print(f"  [실패] {name} {ym}: {e}")
    return None

def load_api(start_ym, end_ym):
    if not C.API_KEY:
        print("config.API_KEY가 비어있습니다. 공공데이터포털 키 입력 후 사용하세요.")
        return
    import requests, xml.etree.ElementTree as ET, time
    con = db(); n = 0
    yms = _month_range(start_ym, end_ym)
    # 같은 LAWD_CD를 쓰는 지역(수원 망포/영통)은 한 번만 호출하고 데이터 공유
    seen_codes = {}
    first_call = True
    for name, meta in C.REGIONS.items():
        code = meta["lawd_cd"]
        for ym in yms:
            params = {"serviceKey": C.API_KEY, "LAWD_CD": code,
                      "DEAL_YMD": ym, "numOfRows": 500}
            r = _get_with_retry(requests, params, name, ym)
            if r is None:
                continue

            # 첫 호출에서 인증/키 문제를 명확히 진단
            body = r.text
            if first_call:
                first_call = False
                if "SERVICE_KEY_IS_NOT_REGISTERED" in body or "SERVICE KEY IS NOT REGISTERED" in body:
                    print("✗ 키가 아직 등록 안 됨. 승인 후 1~2시간 기다렸다 다시 시도하세요.")
                    con.close(); return
                if "errMsg" in body and "NORMAL" not in body:
                    snippet = body[:300].replace("\n", " ")
                    print(f"✗ API 오류 응답: {snippet}")
                    print("  → 키 값/엔드포인트를 확인하세요. (config.API_KEY, config.API_URL)")
                    con.close(); return
                if not body.lstrip().startswith("<"):
                    print(f"✗ 예상치 못한 응답(첫 200자): {body[:200]}")
                    con.close(); return
                print("✓ 첫 호출 응답 정상 — 수집 시작")

            try:
                root = ET.fromstring(r.content)
            except ET.ParseError as e:
                print(f"  [파싱오류] {name} {ym}: {e}"); continue

            got = 0
            for item in root.iter("item"):
                g = lambda t: (item.findtext(t) or "").strip()
                try:
                    price = int(g("dealAmount").replace(",", "") or 0)
                except ValueError:
                    continue
                con.execute("INSERT OR IGNORE INTO trades VALUES(?,?,?,?,?,?,?,?,?)",
                    (name, g("aptNm"), float(g("excluUseAr") or 0),
                     int(g("floor") or 0), price, ym, int(g("dealDay") or 0),
                     "api", datetime.date.today().isoformat()))
                n += 1; got += 1
            time.sleep(0.2)   # 포털 호출 예의 (과도호출 차단 방지)
        seen_codes[code] = True
    con.commit(); con.close()
    print(f"API 수집 완료: {n}건")
    if n == 0:
        print("  ⚠ 0건입니다. 키는 정상이나 해당 기간 거래가 없거나 LAWD_CD를 확인하세요.")

def _month_range(s, e):
    out=[]; y,m=int(s[:4]),int(s[4:]); ey,em=int(e[:4]),int(e[4:])
    while (y,m)<=(ey,em):
        out.append(f"{y}{m:02d}"); m+=1
        if m>12: m=1; y+=1
    return out

# ── 매물 호가 수동 입력 ────────────────────────────────────────
def manual_listing():
    con = db()
    print("매물 호가 입력 (네이버부동산/호갱노노에서 본 값). 빈 줄 입력 시 종료.")
    print("형식: 지역,단지명,전용면적,층,호가(만원)")
    print("예:   동탄,동탄역롯데캐슬,84,39,208000")
    while True:
        line = input("> ").strip()
        if not line: break
        try:
            region, apt, area, floor, price = [x.strip() for x in line.split(",")]
            con.execute("INSERT OR IGNORE INTO trades VALUES(?,?,?,?,?,?,?,?,?)",
                (region, apt, float(area), int(floor), int(price),
                 datetime.date.today().strftime("%Y%m"),
                 datetime.date.today().day, "manual_listing",
                 datetime.date.today().isoformat()))
            con.commit(); print("  저장됨")
        except ValueError:
            print("  형식 오류. 다시 입력하세요.")
    con.close()

def test_key():
    """키 1회 검증 — 평택(41220) 최근월 한 건만 호출해 응답 확인."""
    if not C.API_KEY:
        print("config.API_KEY가 비어있습니다."); return
    import requests, datetime
    ym = (datetime.date.today().replace(day=1) - datetime.timedelta(days=20)).strftime("%Y%m")
    params = {"serviceKey": C.API_KEY, "LAWD_CD": "41220", "DEAL_YMD": ym, "numOfRows": 5}
    try:
        r = requests.get(C.API_URL, params=params, timeout=60)
    except Exception as e:
        print(f"✗ 네트워크 오류: {e}"); return
    b = r.text
    if "NORMAL" in b and "<item>" in b:
        cnt = b.count("<item>")
        print(f"✓ 키 정상 작동. 평택 {ym} 샘플 {cnt}건 확인됨. 이제 'python collect.py api 202501 202506' 실행 가능.")
    elif "NOT_REGISTERED" in b.upper():
        print("✗ 키 미등록 상태. 승인 후 1~2시간 기다렸다 다시 시도하세요.")
    else:
        print(f"✗ 비정상 응답(첫 300자):\n{b[:300]}")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "csv"
    if cmd == "csv": load_csv()
    elif cmd == "api": load_api(sys.argv[2], sys.argv[3])
    elif cmd == "manual": manual_listing()
    elif cmd == "test": test_key()
    else: print(__doc__)
