# -*- coding: utf-8 -*-
"""dashboard.py — 단지별 기대가격 + 입지점수 + 예산 타겟존(실시간) + watchlist 대시보드 생성"""
import sqlite3, json, datetime, webbrowser, os, statistics
import config as C
from expect import evaluate

def trend_by_complex(con, region, apt):
    amin, amax = C.TARGET_AREA
    rows = con.execute("""SELECT deal_ym, price FROM trades
        WHERE region=? AND apt=? AND area BETWEEN ? AND ? AND source!='manual_listing'
        ORDER BY deal_ym""", (region, apt, amin, amax)).fetchall()
    by={}
    for ym,p in rows: by.setdefault(ym,[]).append(p)
    return {ym: round(statistics.median(v)) for ym,v in by.items()}

def build():
    con = sqlite3.connect(C.DB_PATH)
    # 예산 판정을 브라우저(슬라이더)에서 하므로 전체 단지를 넘긴다.
    items = evaluate(con, budget_only=False)
    trends = {f"{r['region']}|{r['apt']}": trend_by_complex(con, r['region'], r['apt']) for r in items}
    con.close()
    payload = json.dumps({
        "items": items, "trends": trends,
        "budget": C.TARGET_BUDGET,
        "title": C.PROJECT_TITLE, "eyebrow": C.PROJECT_EYEBROW,
        "locw": C.LOCATION_WEIGHTS, "nregion": len(set(r["region"] for r in items)),
        "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }, ensure_ascii=False)
    html = TEMPLATE.replace("/*__DATA__*/", payload)
    with open("dashboard.html","w",encoding="utf-8") as f: f.write(html)
    nin = sum(1 for r in items if r["in_budget"])
    print(f"dashboard.html 생성 완료 (전체 {len(items)}단지 · 초기예산 안 {nin}단지)")
    try: webbrowser.open("file://"+os.path.abspath("dashboard.html"))
    except Exception: pass

TEMPLATE = r"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>단지 모니터</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@700;900&family=Noto+Sans+KR:wght@400;500;700&family=JetBrains+Mono:wght@600;700&display=swap');
:root{--ink:#15140f;--paper:#f3efe6;--card:#fbf9f3;--line:#cdc4b0;--gold:#b08948;--jade:#2f6b4f;--crimson:#a8321f;--slate:#3a4654;--muted:#6e6857;--budget:rgba(47,107,79,.10)}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--paper);color:var(--ink);font-family:'Noto Sans KR',sans-serif;line-height:1.6}
.wrap{max-width:1080px;margin:0 auto;padding:0 22px}
.wrap-wide{max-width:1320px;margin:0 auto;padding:0 22px}
header{padding:46px 0 26px;border-bottom:3px solid var(--ink)}
.eyebrow{font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:.3em;color:var(--crimson);font-weight:700;text-transform:uppercase}
h1{font-family:'Noto Serif KR',serif;font-weight:900;font-size:clamp(26px,4.5vw,42px);margin:12px 0 6px;line-height:1.12}
.gen{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--muted)}
.budget-pill{display:inline-block;background:var(--ink);color:var(--paper);font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;padding:5px 13px;border-radius:20px;margin-top:14px}
section{padding:34px 0;border-bottom:1px solid #ddd5c4}
h2{font-family:'Noto Serif KR',serif;font-size:21px;font-weight:900;margin-bottom:6px}
.lead{color:var(--muted);font-size:14px;margin-bottom:20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:5px;padding:22px;box-shadow:4px 4px 0 #e9e3d5}
.chart-box{position:relative;height:660px}.chart-box.sm{height:320px}
.controls{display:flex;gap:18px;align-items:center;flex-wrap:wrap;margin-bottom:14px}
.controls label{font-size:13px;color:var(--muted);display:flex;align-items:center;gap:7px;font-weight:500}
.controls .sel{margin-bottom:0}
.chk input{width:15px;height:15px;accent-color:var(--jade);cursor:pointer}
.chk{cursor:pointer}
.cnt{font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--muted);margin-left:auto}
.budget-box{background:var(--card);border:1px solid var(--line);border-radius:5px;padding:14px 18px;margin-bottom:18px;display:grid;grid-template-columns:auto 1fr auto;gap:10px 16px;align-items:center}
.budget-box .bl{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;color:var(--jade);white-space:nowrap}
.budget-box input[type=range]{width:100%;accent-color:var(--jade);cursor:pointer}
.budget-box .bv{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;color:var(--ink);white-space:nowrap;text-align:right;min-width:58px}
.budget-box .breset{grid-column:1/-1;justify-self:end;font-family:'Noto Sans KR';font-size:12px;color:var(--muted);background:none;border:1px solid var(--line);border-radius:4px;padding:4px 10px;cursor:pointer}
.budget-box .breset:hover{border-color:var(--gold);color:var(--ink)}
.complex-list{display:grid;gap:10px}
.cx{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center;background:var(--card);border:1px solid var(--line);border-left:5px solid var(--line);border-radius:5px;padding:14px 18px;cursor:pointer;transition:transform .12s,box-shadow .12s}
.cx:hover{transform:translateX(3px);box-shadow:-4px 4px 0 #e9e3d5}
.cx.안전축{border-left-color:var(--jade)}.cx.성장축{border-left-color:var(--gold)}.cx.기회{border-left-color:var(--crimson)}.cx.회복{border-left-color:var(--slate)}
.cx-name{font-weight:700;font-size:15px}
.cx-meta{font-size:12px;color:var(--muted);margin-top:2px}
.cx-tag{display:inline-block;font-size:10px;font-weight:700;padding:1px 7px;border-radius:3px;color:#fff;margin-right:6px}
.tag-안전축{background:var(--jade)}.tag-성장축{background:var(--gold)}.tag-기회{background:var(--crimson)}.tag-회복{background:var(--slate)}
.loc-badge{display:inline-block;font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;padding:1px 6px;border-radius:3px;background:#e3dccb;color:var(--slate);margin-left:6px}
.loc-badge.m{background:var(--slate);color:#fff}
.cx-nums{text-align:right;font-family:'JetBrains Mono',monospace;white-space:nowrap}
.cx-cur{font-size:18px;font-weight:700;color:var(--ink)}
.cx-up{font-size:13px;color:var(--jade);font-weight:700}
.cx-exp{font-size:11px;color:var(--muted)}
.star{font-size:18px;color:var(--line);cursor:pointer;user-select:none;margin-left:4px}
.star.on{color:var(--gold)}
.more{display:block;width:100%;margin-top:14px;padding:11px;background:var(--card);border:1px dashed var(--line);border-radius:5px;font-family:'Noto Sans KR';font-size:13px;font-weight:700;color:var(--muted);cursor:pointer}
.more:hover{border-color:var(--gold);color:var(--ink)}
.muted-note{font-size:12px;color:var(--muted);margin-top:14px;line-height:1.7}
table{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px}
thead th{background:#e3dccb;color:var(--ink);padding:9px 11px;text-align:right;font-size:11.5px;white-space:nowrap}
thead th:first-child{text-align:left}
tbody td{padding:8px 11px;border-bottom:1px solid #e8e1d0;text-align:right;font-family:'JetBrains Mono',monospace;color:var(--muted)}
tbody td:first-child{text-align:left;font-family:'Noto Sans KR'}
.sel{font-family:'Noto Sans KR';font-size:13px;padding:6px 10px;border:1px solid var(--line);border-radius:4px;background:var(--card);margin-bottom:14px}
.empty{padding:40px;text-align:center;color:var(--muted);font-size:14px}
@media(max-width:720px){.chart-box{height:640px}.cx{grid-template-columns:1fr}.cx-nums{text-align:left}.cnt{margin-left:0}}
</style></head><body>
<header><div class="wrap">
<div class="eyebrow" id="eyebrow"></div>
<h1 id="title"></h1>
<div class="gen" id="gen"></div>
<div class="budget-pill" id="bpill"></div>
</div></header>

<section><div class="wrap-wide">
<h2>예산 타겟존 시각화</h2>
<p class="lead">세로축 = 지역, 가로축 = 현 실거래 중앙값(억). <b>초록 띠 안</b>이 내 예산존이고 점 하나가 단지입니다.
점 <b>크기 = 입지점수</b>(클수록 입지 우위), 같은 지역에서 <b>왼쪽일수록 같은 호재를 더 싸게</b> 사는 셈.
특정 지역을 고르면 현 시세→중립 기대를 <b>선으로 연결</b>해 상승 여력을 보여줍니다.</p>
<div class="budget-box">
  <span class="bl">예산 하한</span><input type="range" id="bMinR"><span class="bv" id="bMinV"></span>
  <span class="bl">예산 상한</span><input type="range" id="bMaxR"><span class="bv" id="bMaxV"></span>
  <button class="breset" id="bReset">기본값으로</button>
</div>
<div class="controls">
  <label>지역 <select id="regionSel" class="sel"></select></label>
  <label class="chk"><input type="checkbox" id="expToggle"> 중립 기대(◆) 같이 보기</label>
  <span class="cnt" id="mainCnt"></span>
</div>
<div class="card"><div class="chart-box"><canvas id="main"></canvas></div></div>
</div></section>

<section><div class="wrap">
<h2>관심 단지 (★ 눌러 watchlist 등록)</h2>
<p class="lead">위 예산·지역 필터가 함께 적용됩니다. 카드를 누르면 아래 추이 차트에 표시. ★은 1년 추적용 즐겨찾기(이 세션 한정).</p>
<div class="controls">
  <label>정렬 <select id="sortSel" class="sel">
    <option value="upside">여력 높은 순</option>
    <option value="cheap">현 시세 낮은 순</option>
    <option value="loc">입지점수 높은 순</option>
  </select></label>
  <span class="cnt" id="listCnt"></span>
</div>
<div class="complex-list" id="list"></div>
<button class="more" id="moreBtn" style="display:none"></button>
<div class="muted-note">
※ <b>여력(%)</b>은 지역 단위 호재(교통·팹·미분양)에서 나오므로 같은 지역이면 동일합니다.
단지별 차등은 <b>입지점수</b>(교통·학군·인프라·주차)로 따로 봅니다 — 기본은 지역 내 시세 백분위 자동추정,
config.LOCATION_SCORES에 단지를 입력하면 4개 항목 가중평균으로 대체됩니다.
같은 예산·같은 지역이라면 <b>현 시세가 낮을수록 저평가, 입지점수가 높을수록 우량</b>입니다.
</div>
</div></section>

<section><div class="wrap">
<h2>단지별 실거래 추이</h2>
<p class="lead">1년간 누적하면 이 선으로 매수 타이밍을 잡습니다. 단지를 선택하세요. (지역 필터 적용)</p>
<div class="card"><select class="sel" id="trendSel"></select><div class="chart-box sm"><canvas id="trend"></canvas></div></div>
</div></section>

<section style="border:none"><div class="wrap">
<h2>참고: 예산 밖 단지</h2>
<p class="lead">현재 예산을 벗어났지만 조정 시 진입 가능할 수 있어 참고용. (예산·지역 필터 적용)</p>
<div class="card" style="overflow-x:auto"><table id="overtbl"></table><div class="muted-note" id="overNote"></div></div>
</div></section>

<script>
const P=/*__DATA__*/;
const C={ink:'#15140f',gold:'#b08948',jade:'#2f6b4f',crimson:'#a8321f',slate:'#3a4654',muted:'#6e6857'};
const eok=v=>v/10000, tagColor={'안전축':C.jade,'성장축':C.gold,'기회':C.crimson,'회복':C.slate};
if(typeof Chart!=='undefined'){Chart.defaults.font.family="'Noto Sans KR',sans-serif";Chart.defaults.color=C.muted;}
const hasChart=typeof Chart!=='undefined';
function warnNoChart(id){var e=document.getElementById(id);if(e&&e.parentNode){var d=document.createElement('div');d.style.cssText='color:#a8321f;font-size:13px;padding:30px;text-align:center';d.textContent='차트 라이브러리를 불러오지 못했습니다. 인터넷 연결 상태에서 다시 열어주세요.';e.parentNode.replaceChild(d,e);}}

document.getElementById('eyebrow').textContent=P.eyebrow;
document.title=P.title;
document.getElementById('title').textContent=P.title;
document.getElementById('gen').textContent='업데이트: '+P.generated+' · '+P.nregion+'개 지역';

const ALL=P.items; ALL.forEach((r,i)=>r._gi=i);
const [defLo,defHi]=P.budget;
let curLo=defLo, curHi=defHi, curRegion='all', listSort='upside', listAll=false;

const inB=r=>curLo<=r.current&&r.current<=curHi;
const budgetRows=()=>ALL.filter(inB);
const regionRows=()=>{const rs=budgetRows();return curRegion==='all'?rs:rs.filter(r=>r.region===curRegion);};

// ── 지역 레인 좌표 (전체 단지 기준, 안정적) ────────────────────
const REGIONS_ORDER=[...new Set(ALL.map(r=>r.region))];
const regIdx=Object.fromEntries(REGIONS_ORDER.map((r,i)=>[r,i]));
function jit(i){const x=Math.sin(i*12.9898)*43758.5453;return ((x-Math.floor(x))-0.5)*0.62;}
const laneY=r=>regIdx[r.region]+jit(r._gi);
const locR=r=>4+(r.loc/100)*6;   // 입지점수 → 점 반지름 4~10

const regionSel=document.getElementById('regionSel');
regionSel.innerHTML='<option value="all">전체 지역</option>'+REGIONS_ORDER.map(r=>`<option value="${r}">${r}</option>`).join('');

// ── 예산 슬라이더 ──────────────────────────────────────────────
const dataMin=Math.min(...ALL.map(r=>r.current)), dataMax=Math.max(...ALL.map(r=>r.current));
const SMIN=Math.max(20000,Math.floor(dataMin/5000)*5000), SMAX=Math.ceil(dataMax/5000)*5000, STEP=2500;
const bMinR=document.getElementById('bMinR'), bMaxR=document.getElementById('bMaxR');
[bMinR,bMaxR].forEach(s=>{s.min=SMIN;s.max=SMAX;s.step=STEP;});
bMinR.value=curLo; bMaxR.value=curHi;
function updatePill(){
  document.getElementById('bpill').textContent='예산존 '+eok(curLo).toFixed(2)+'억 ~ '+eok(curHi).toFixed(2)+'억 · 전용 84㎡';
  document.getElementById('bMinV').textContent=eok(curLo).toFixed(2)+'억';
  document.getElementById('bMaxV').textContent=eok(curHi).toFixed(2)+'억';
}
let rfTimer;
function refresh(){clearTimeout(rfTimer);rfTimer=setTimeout(()=>{drawMain();renderList();renderOver();},50);}
function onBudget(){
  curLo=+bMinR.value; curHi=+bMaxR.value;
  if(curLo>curHi){ if(document.activeElement===bMinR)curHi=curLo,bMaxR.value=curHi; else curLo=curHi,bMinR.value=curLo; }
  listAll=false; updatePill(); refresh();
}
bMinR.addEventListener('input',onBudget);
bMaxR.addEventListener('input',onBudget);
document.getElementById('bReset').addEventListener('click',()=>{curLo=defLo;curHi=defHi;bMinR.value=defLo;bMaxR.value=defHi;listAll=false;updatePill();refresh();});

// ── 메인: 지역 레인 산점도 + 예산존 띠 + 연결선 ────────────────
const budgetBandV={id:'bbv',beforeDraw(chart){
  const {ctx,chartArea:a,scales:{x}}=chart;
  const x1=Math.max(a.left,x.getPixelForValue(eok(curLo))),x2=Math.min(a.right,x.getPixelForValue(eok(curHi)));
  ctx.save();
  ctx.fillStyle='rgba(47,107,79,.12)';ctx.fillRect(x1,a.top,x2-x1,a.bottom-a.top);
  ctx.strokeStyle='rgba(47,107,79,.5)';ctx.setLineDash([4,3]);ctx.lineWidth=1;
  ctx.strokeRect(x1,a.top,x2-x1,a.bottom-a.top);ctx.setLineDash([]);
  ctx.fillStyle='rgba(47,107,79,.9)';ctx.font="700 11px 'JetBrains Mono',monospace";ctx.textAlign='center';
  ctx.fillText('내 예산존',(x1+x2)/2,a.top+14);
  ctx.restore();
}};
// 특정 지역 선택 시: 현 시세 → 중립 기대를 선으로 연결
const connectLines={id:'conn',beforeDatasetsDraw(chart){
  if(curRegion==='all')return;
  const {ctx,scales:{x,y}}=chart;
  ctx.save();ctx.lineWidth=1.4;
  regionRows().forEach(r=>{
    const yp=y.getPixelForValue(laneY(r));
    const xc=x.getPixelForValue(eok(r.current)), xe=x.getPixelForValue(eok(r['중립']));
    ctx.strokeStyle=tagColor[r.tag]+'70';
    ctx.beginPath();ctx.moveTo(xc,yp);ctx.lineTo(xe,yp);ctx.stroke();
  });
  ctx.restore();
}};
function mainDatasets(rows,showExp){
  const tags=['안전축','성장축','기회','회복'];
  const ds=tags.map(t=>({label:t,
    data:rows.filter(r=>r.tag===t).map(r=>({x:eok(r.current),y:laneY(r),r})),
    backgroundColor:tagColor[t],borderColor:'#fff',borderWidth:1,
    pointRadius:c=>locR(c.raw.r),pointHoverRadius:c=>locR(c.raw.r)+3,pointStyle:'circle'})).filter(d=>d.data.length);
  if(showExp)ds.push({label:'중립 기대',
    data:rows.map(r=>({x:eok(r['중립']),y:laneY(r),r})),
    backgroundColor:'rgba(21,20,15,.5)',borderColor:'#fff',borderWidth:1,
    pointStyle:'rectRot',pointRadius:5,pointHoverRadius:8});
  return ds;
}
let mainChart;
function drawMain(){
  if(!hasChart){warnNoChart('main');return;}
  const rows=regionRows();
  const showExp=curRegion!=='all' ? true : document.getElementById('expToggle').checked;
  const lanes=curRegion==='all'?REGIONS_ORDER.map((_,i)=>i):[regIdx[curRegion]];
  const ymin=Math.min(...lanes)-0.6, ymax=Math.max(...lanes)+0.6;
  document.getElementById('mainCnt').textContent='예산 안 '+rows.length+'개 단지';
  if(mainChart)mainChart.destroy();
  mainChart=new Chart(document.getElementById('main'),{
    type:'scatter',
    data:{datasets:mainDatasets(rows,showExp)},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{position:'top',labels:{usePointStyle:true,font:{size:12}}},
        tooltip:{callbacks:{
          title:items=>{const r=items[0].raw.r;return r.region+'·'+r.apt;},
          label:ctx=>{const r=ctx.raw.r;return ['현 시세 '+eok(r.current).toFixed(1)+'억 · 거래 '+r.n+'건',
            '중립 기대 '+eok(r['중립']).toFixed(1)+'억 (여력 +'+r.upside+'%)',
            '입지점수 '+r.loc+' ('+(r.loc_src==='manual'?'수동':'시세기반 자동')+')'];}}}},
      scales:{
        x:{title:{display:true,text:'현 시세 중앙값 (억원)'},grid:{color:'rgba(205,196,176,.5)'},
          suggestedMin:eok(curLo)-0.8,suggestedMax:eok(curHi)+1.2},
        y:{min:ymin,max:ymax,grid:{color:'rgba(205,196,176,.5)'},
          afterBuildTicks:ax=>{ax.ticks=lanes.map(v=>({value:v}));},
          ticks:{callback:v=>REGIONS_ORDER[v]||'',font:{size:12}}}}},
    plugins:[budgetBandV,connectLines]
  });
}

// ── 관심 단지 리스트 ───────────────────────────────────────────
const watch=new Set();
const list=document.getElementById('list');
const TOPN=30;
function listRows(){
  const rows=regionRows().slice();
  if(listSort==='cheap')rows.sort((a,b)=>a.current-b.current);
  else if(listSort==='loc')rows.sort((a,b)=>b.loc-a.loc||b.upside-a.upside);
  else rows.sort((a,b)=>b.upside-a.upside||a.current-b.current);
  return rows;
}
function renderList(){
  const rows=listRows();
  const shown=listAll?rows:rows.slice(0,TOPN);
  document.getElementById('listCnt').textContent=rows.length+'개 중 '+shown.length+'개 표시';
  if(!rows.length){list.innerHTML='<div class="empty">이 조건(예산·지역)에 드는 단지가 없습니다.</div>';}
  else list.innerHTML=shown.map(r=>{
    const i=r._gi;
    const lst=r.listing?('호가 '+eok(r.listing).toFixed(1)+'억'):'호가 —';
    const lb=`<span class="loc-badge ${r.loc_src==='manual'?'m':''}">입지 ${r.loc}</span>`;
    return `<div class="cx ${r.tag}" data-i="${i}">
      <div><div class="cx-name"><span class="cx-tag tag-${r.tag}">${r.tag}</span>${r.apt}${lb}
        <span class="star ${watch.has(i)?'on':''}" data-star="${i}">★</span></div>
        <div class="cx-meta">${r.region} · 거래 ${r.n}건 · ${r.last_ym} · ${lst}</div></div>
      <div class="cx-nums"><div class="cx-cur">${eok(r.current).toFixed(1)}억</div>
        <div class="cx-up">여력 +${r.upside}%</div>
        <div class="cx-exp">기대 ${eok(r['보수']).toFixed(1)}~${eok(r['낙관']).toFixed(1)}억</div></div></div>`;
  }).join('');
  const more=document.getElementById('moreBtn');
  if(rows.length>TOPN){more.style.display='';more.textContent=listAll?`접기 (상위 ${TOPN}개만 보기)`:`더 보기 (총 ${rows.length}개)`;}
  else more.style.display='none';
}
list.addEventListener('click',e=>{
  const s=e.target.closest('[data-star]');
  if(s){const i=+s.dataset.star; watch.has(i)?watch.delete(i):watch.add(i); renderList(); e.stopPropagation(); return;}
  const cx=e.target.closest('.cx'); if(cx){const r=ALL[+cx.dataset.i]; sel.value=r.region+'|'+r.apt; drawTrend(sel.value);
    document.getElementById('trend').scrollIntoView({behavior:'smooth',block:'center'});}
});
document.getElementById('moreBtn').addEventListener('click',()=>{listAll=!listAll;renderList();});
document.getElementById('sortSel').addEventListener('change',e=>{listSort=e.target.value;listAll=false;renderList();});
document.getElementById('expToggle').addEventListener('change',drawMain);

// ── 추이 (지역 필터만 적용, 예산과 무관하게 안정적) ─────────────
const sel=document.getElementById('trendSel');
function fillTrend(){
  const rows=(curRegion==='all'?ALL:ALL.filter(r=>r.region===curRegion)).slice().sort((a,b)=>a.current-b.current);
  sel.innerHTML=rows.map(r=>`<option value="${r.region}|${r.apt}">${r.region}·${r.apt}</option>`).join('');
  if(rows.length)drawTrend(rows[0].region+'|'+rows[0].apt);
}
let tc;
function drawTrend(key){
  if(!hasChart){warnNoChart('trend');return;}
  const h=P.trends[key]||{}; const labels=Object.keys(h).sort(); const vals=labels.map(k=>eok(h[k]));
  const r=ALL.find(x=>x.region+'|'+x.apt===key);
  if(tc)tc.destroy();
  tc=new Chart(document.getElementById('trend'),{type:'line',
    data:{labels:labels.length?labels:['데이터 누적 전'],
      datasets:[{label:key.replace('|','·')+' 실거래',data:vals.length?vals:[0],
        borderColor:tagColor[r?r.tag:'성장축'],backgroundColor:'rgba(47,107,79,.08)',fill:true,tension:.25,pointRadius:4}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},
      scales:{y:{title:{display:true,text:'억원'},grid:{color:'rgba(205,196,176,.5)'}},x:{grid:{display:false}}}},
    plugins:[{id:'bb2',beforeDraw(chart){const {ctx,chartArea:a,scales:{y}}=chart;
      const y1=y.getPixelForValue(eok(curHi)),y2=y.getPixelForValue(eok(curLo));
      ctx.save();ctx.fillStyle='rgba(47,107,79,.08)';ctx.fillRect(a.left,y1,a.right-a.left,y2-y1);ctx.restore();}}]});
}
sel.addEventListener('change',e=>drawTrend(e.target.value));

// ── 예산 밖 표 ─────────────────────────────────────────────────
function renderOver(){
  let rows=ALL.filter(r=>!inB(r));
  if(curRegion!=='all')rows=rows.filter(r=>r.region===curRegion);
  rows=rows.slice().sort((a,b)=>a.current-b.current);
  const cap=50, shown=rows.slice(0,cap);
  document.getElementById('overtbl').innerHTML=
    `<thead><tr><th>단지</th><th>현 시세</th><th>예산까지</th><th>입지</th><th>구분</th></tr></thead><tbody>`+
    shown.map(r=>{const gap=r.current>curHi?('+'+eok(r.current-curHi).toFixed(1)+'억 초과'):('−'+eok(curLo-r.current).toFixed(1)+'억 미달');
      return `<tr><td>${r.region}·${r.apt}</td><td>${eok(r.current).toFixed(1)}억</td>
      <td>${gap}</td><td>${r.loc}</td><td>${r.tag}</td></tr>`;}).join('')+`</tbody>`;
  document.getElementById('overNote').textContent=rows.length>cap?`예산 밖 ${rows.length}개 중 시세 낮은 ${cap}개만 표시`:`예산 밖 ${rows.length}개`;
}

// ── 지역 필터: 전 영역 동기화 ──────────────────────────────────
regionSel.addEventListener('change',e=>{
  curRegion=e.target.value; listAll=false;
  drawMain(); renderList(); fillTrend(); renderOver();
});

// 초기 렌더 — 차트는 마지막에
updatePill();
renderList();
renderOver();
drawMain();
fillTrend();
</script></body></html>"""

if __name__ == "__main__":
    build()
