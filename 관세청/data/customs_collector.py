"""
관세청 시도별 수출입실적 -> 정리된 CSV 자동 생성
  엔드포인트: https://apis.data.go.kr/1220000/sidotrade/getSidotradeList
  응답 item: cmtrBlncAmt, expCnt, expUsdAmt, impCnt, impUsdAmt, priodTitle, sidoNm

동작:
  1) 연 단위로 호출(1년 제한 회피)
  2) priodTitle='총계' 행 자동 제거 (sidoNm 있는 실데이터만)
  3) 콤마/공백 숫자 정리
  4) 파생지표(억USD, 건당금액, 증가율) 계산
  5) CSV 2개 저장:
       - daejeon_sido_clean.csv : 대전만, 파생지표 포함
       - all_sido_by_year.csv   : 전국 17개 시도 원자료(연도별)
       - daejeon_share.csv      : 대전의 전국 대비 비중/순위

[실행 전] SERVICE_KEY 에 디코딩키만 넣으면 끝.
"""

import csv
import xml.etree.ElementTree as ET
import requests
import pandas as pd

# ===================== CONFIG =====================
SERVICE_KEY = "idvXkYzNjlTLAs1qoXh+6VKegxyaz6x4o/Pc9MehBIQF3YZDyBlSxTB+ibiO6v7DWVbz6gTr8G1sJUL/lG696Q=="      # <-- 이 줄만 교체
YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
URL = "https://apis.data.go.kr/1220000/sidotrade/getSidotradeList"
# ==================================================

NUM_COLS = ["cmtrBlncAmt", "expCnt", "expUsdAmt", "impCnt", "impUsdAmt"]
COL_KR = {
    "sidoNm": "시도", "priodTitle": "연도",
    "expCnt": "수출건수", "expUsdAmt": "수출액_천USD",
    "impCnt": "수입건수", "impUsdAmt": "수입액_천USD",
    "cmtrBlncAmt": "무역수지_천USD",
}


def to_num(s):
    return int(str(s).replace(",", "").replace(" ", "") or 0)


def fetch_year(year, sido_cd=None):
    params = {"serviceKey": SERVICE_KEY,
              "strtYymm": f"{year}01", "endYymm": f"{year}12"}
    if sido_cd:
        params["sidoCd"] = sido_cd
    r = requests.get(URL, params=params, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    code = root.findtext(".//resultCode")
    if code and code.strip() not in ("00", "0"):
        raise RuntimeError(f"{year}: {root.findtext('.//resultMsg')}")

    out = []
    for it in root.findall(".//item"):
        row = {c.tag: (c.text or "").strip() for c in it}
        if not row.get("sidoNm"):        # '총계' 행 스킵
            continue
        rec = {"연도": year, "시도": row["sidoNm"]}
        for k in NUM_COLS:
            rec[COL_KR[k]] = to_num(row.get(k, 0))
        out.append(rec)
    return out


def main():
    # ---- 전국(모든 시도) 수집 ----
    all_rows = []
    for y in YEARS:
        rows = fetch_year(y)            # sidoCd 없이 -> 전체 시도
        all_rows.extend(rows)
        print(f"  {y}: {len(rows)}개 시도")
    df = pd.DataFrame(all_rows)
    df.to_csv("all_sido_by_year.csv", index=False, encoding="utf-8-sig")

    # ---- 대전만 + 파생지표 ----
    dj = df[df["시도"] == "대전광역시"].sort_values("연도").reset_index(drop=True)
    dj["수입액_억USD"] = (dj["수입액_천USD"] / 100000).round(2)
    dj["수입건수_만건"] = (dj["수입건수"] / 10000).round(1)
    dj["수입건당_USD"] = (dj["수입액_천USD"] * 1000 / dj["수입건수"]).round(0).astype(int)
    dj["수입건수_증가율%"] = (dj["수입건수"].pct_change() * 100).round(1)
    dj.to_csv("daejeon_sido_clean.csv", index=False, encoding="utf-8-sig")

    # ---- 대전 전국대비 비중/순위 ----
    share = []
    for y in YEARS:
        sub = df[df["연도"] == y].copy()
        nat_cnt = sub["수입건수"].sum()
        nat_amt = sub["수입액_천USD"].sum()
        djr = sub[sub["시도"] == "대전광역시"].iloc[0]
        sub["건수순위"] = sub["수입건수"].rank(ascending=False).astype(int)
        share.append({
            "연도": y,
            "대전수입건수": int(djr["수입건수"]),
            "전국수입건수": int(nat_cnt),
            "건수비중%": round(djr["수입건수"] / nat_cnt * 100, 2),
            "건수_전국순위": int(sub[sub["시도"] == "대전광역시"]["건수순위"].iloc[0]),
            "금액비중%": round(djr["수입액_천USD"] / nat_amt * 100, 2),
        })
    sh = pd.DataFrame(share)
    sh.to_csv("daejeon_share.csv", index=False, encoding="utf-8-sig")

    # ---- 콘솔 요약 ----
    print("\n[대전 수입 추세]")
    print(dj[["연도", "수입액_억USD", "수입건수_만건", "수입건수_증가율%", "수입건당_USD"]].to_string(index=False))
    print("\n[대전 전국대비 비중/순위]")
    print(sh.to_string(index=False))
    print("\n저장: all_sido_by_year.csv / daejeon_sido_clean.csv / daejeon_share.csv")


if __name__ == "__main__":
    main()