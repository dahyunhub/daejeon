"""
관세청 시도별 품목별 수출입실적 -> 대전 품목 구조 CSV
  엔드포인트: https://apis.data.go.kr/1220000/sidoitemtrade/getSidoitemtradeList
  응답 item: hsSgn, korePrlstNm, impLnCnt, impUsdAmt, expLnCnt, expUsdAmt, cmtrBlncAmt, priodTitle
  * priodTitle='총계' 행은 hsSgn 없음 -> 제외
  * 중량(kg) 컬럼은 이 오퍼레이션에 없음

출력:
  daejeon_item_by_year.csv : 연도×HS품목 원자료(대전)
  daejeon_item_summary.csv : HS품목별 6년 합계 + 건수비중 + 건당금액 + 소비재/산업재 태그
"""
import csv, xml.etree.ElementTree as ET
from pathlib import Path
import requests, pandas as pd

# ===== CONFIG =====
SERVICE_KEY = "idvXkYzNjlTLAs1qoXh+6VKegxyaz6x4o/Pc9MehBIQF3YZDyBlSxTB+ibiO6v7DWVbz6gTr8G1sJUL/lG696Q=="
SIDO_CD = "30"                 # 대전
YEARS = [2020,2021,2022,2023,2024,2025]
URL = "https://apis.data.go.kr/1220000/sidoitemtrade/getSidoitemtradeList"
# ==================

# 소비재성 HS 2단위 (식품·화장품·의류·잡화·생활용품 계열)
CONSUMER_HS = {"04","09","16","17","18","19","20","21","22","30","33","34",
               "42","43","57","61","62","63","64","65","66","67","91","92","95","96","97"}

def to_num(s): return int(str(s).replace(",","").replace(" ","") or 0)

def fetch(year):
    p = {"serviceKey":SERVICE_KEY,"strtYymm":f"{year}01","endYymm":f"{year}12","sidoCd":SIDO_CD}
    r = requests.get(URL, params=p, timeout=60); r.raise_for_status()
    root = ET.fromstring(r.content)
    code = root.findtext(".//resultCode")
    if code and code.strip() not in ("00","0"):
        raise RuntimeError(f"{year}: {root.findtext('.//resultMsg')}")
    out=[]
    for it in root.findall(".//item"):
        d={c.tag:(c.text or "").strip() for c in it}
        if not d.get("hsSgn"): continue      # 총계행 skip
        out.append({
            "연도":year,"HS":d["hsSgn"],"품목명":d.get("korePrlstNm",""),
            "수입건수":to_num(d.get("impLnCnt",0)),"수입액_천USD":to_num(d.get("impUsdAmt",0)),
        })
    return out

def main():
    rows=[]
    for y in YEARS:
        r=fetch(y); rows+=r; print(f"  {y}: {len(r)}개 품목")
    df=pd.DataFrame(rows)
    df.to_csv("daejeon_item_by_year.csv",index=False,encoding="utf-8-sig")

    g=df.groupby(["HS","품목명"],as_index=False).agg(수입건수=("수입건수","sum"),수입액_천USD=("수입액_천USD","sum"))
    tot=g["수입건수"].sum()
    g["건수비중%"]=(g["수입건수"]/tot*100).round(1)
    g["건당USD"]=(g["수입액_천USD"]*1000/g["수입건수"].replace(0,1)).round(0).astype(int)
    g["구분"]=g["HS"].apply(lambda h:"소비재" if h in CONSUMER_HS else "산업재")
    g=g.sort_values("수입건수",ascending=False)
    g.to_csv("daejeon_item_summary.csv",index=False,encoding="utf-8-sig")

    print("\n[대전 수입 건수 TOP 10 품목 (6년 누적)]")
    print(g.head(10)[["HS","품목명","수입건수","건수비중%","건당USD","구분"]].to_string(index=False))
    cc=g[g["구분"]=="소비재"]["수입건수"].sum()
    print(f"\n소비재 건수 비중: {cc/tot*100:.0f}%")

if __name__=="__main__":
    main()
