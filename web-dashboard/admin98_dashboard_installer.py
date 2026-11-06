#!/usr/bin/env python3
# Admin98 OLT dashboard overlay v1 - read-only
import argparse
import ast
import datetime
import pathlib
import shutil
import sys

HTML = """<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>داشبورد OLT | Admin98</title>
<style>
:root{font-family:Tahoma,Arial,sans-serif;color:#21324c;background:#edf2fa}
*{box-sizing:border-box}body{margin:0}.layout{min-height:100vh;display:flex}
aside{background:#102c53;color:white;width:245px;padding:25px 18px;flex-shrink:0}
.brand{font-size:22px;font-weight:bold;margin-bottom:40px}.brand small{display:block;font-size:11px;opacity:.65;margin-top:8px}
.nav{width:100%;text-align:right;background:transparent;color:#d7e4f7;padding:14px;border:0;border-radius:10px;cursor:pointer;margin:4px 0;font-size:14px}
.nav.active,.nav:hover{background:#285c9d;color:white}
.logout{margin-top:28px}.logout button{width:100%;padding:12px;border-radius:10px;border:1px solid #5b769c;background:transparent;color:white;cursor:pointer}
main{flex:1;padding:30px;min-width:0}h1{margin:0 0 7px;font-size:25px}p{color:#8090a8}
.top{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.pill{background:#fff;padding:10px 17px;border-radius:40px;border:1px solid #e0e6ef;font-size:13px}
.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:26px 0}
.card,.panel{background:white;border:1px solid #e4eaf3;border-radius:16px;box-shadow:0 8px 25px #213c6810}
.card{padding:22px}.card label{display:block;color:#8291a6;font-size:13px;margin-bottom:15px}.card strong{font-size:23px;direction:ltr;unicode-bidi:plaintext;display:block}
.panel{padding:22px;margin-bottom:20px}h2{font-size:17px;margin:0 0 20px}
table{width:100%;border-collapse:collapse;text-align:right;font-size:13px}th,td{padding:13px;border-bottom:1px solid #eef1f5}th{color:#8190a5}
.tab{display:none}.tab.active{display:block}.muted{color:#8391a5}.error{color:#b32d43}
@media(max-width:1050px){.cards{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:650px){.layout{display:block}aside{width:100%;padding:14px}.brand{margin-bottom:12px}.nav{display:inline-block;width:auto;padding:8px;font-size:12px}main{padding:17px}.cards{grid-template-columns:1fr 1fr;gap:8px}.card{padding:13px}.card strong{font-size:18px}.panel{overflow-x:auto}}
</style></head><body>
<div class="layout"><aside><div class="brand">Admin98 OLT<small>Huawei MA5683T · مرکز پایش شبکه</small></div>
<button class="nav active" data-page="overview">نمای کلی</button>
<button class="nav" data-page="boards">بردها و اسلات‌ها</button>
<button class="nav" data-page="history">تاریخچه پایش</button>
<button class="nav" data-page="events">رویدادها</button>
<form class="logout" action="/logout" method="POST"><input type="hidden" name="csrf_token" value="{{ csrf }}"><button>خروج از سامانه</button></form></aside>
<main><div class="top"><div><h1>داشبورد مدیریت OLT</h1><p>مانیتورینگ خواندنی و مبتنی بر داده‌های واقعی دستگاه</p></div><span class="pill" id="state">در حال دریافت اطلاعات…</span></div>
<div class="cards">
<div class="card"><label>مدل دستگاه</label><strong id="product">—</strong></div>
<div class="card"><label>تعداد برد</label><strong id="board_count">—</strong></div>
<div class="card"><label>بردهای سالم</label><strong id="healthy_board_count">—</strong></div>
<div class="card"><label>بردهای دارای اختلال</label><strong id="abnormal_board_count">—</strong></div>
<div class="card"><label>Firmware</label><strong id="firmware">—</strong></div>
<div class="card"><label>Patch</label><strong id="patch">—</strong></div>
<div class="card"><label>Uptime</label><strong id="uptime">—</strong></div>
<div class="card"><label>آخرین جمع‌آوری موفق</label><strong id="last_success_at" style="font-size:13px">—</strong></div>
</div>
<section class="tab active" id="overview"><div class="panel"><h2>وضعیت اتصال</h2><div id="connection">—</div></div><div class="panel"><h2>بردهای شناسایی‌شده</h2><div id="board_summary">—</div></div></section>
<section class="tab" id="boards"><div class="panel"><h2>بردها و اسلات‌ها</h2><table><thead><tr><th>اسلات</th><th>مدل</th><th>وضعیت</th></tr></thead><tbody id="board_rows"></tbody></table></div></section>
<section class="tab" id="history"><div class="panel"><h2>۵۰ نمونه آخر پایش</h2><table><thead><tr><th>زمان</th><th>نتیجه</th><th>خطا</th></tr></thead><tbody id="history_rows"></tbody></table></div></section>
<section class="tab" id="events"><div class="panel"><h2>رویدادهای ثبت‌شده</h2><table><thead><tr><th>زمان</th><th>نوع</th><th>شدت</th><th>شرح</th></tr></thead><tbody id="event_rows"></tbody></table></div></section>
<p class="muted">به‌روزرسانی خودکار هر ۳۰ ثانیه · هیچ دستور تغییر کانفیگ به OLT ارسال نمی‌شود.</p></main></div>
<script>
'use strict';
const byId=(id)=>document.getElementById(id);
const value=(x)=>x===null||x===undefined||x===''?'—':String(x);
function set(id,x){byId(id).textContent=value(x)}
async function get(path){const r=await fetch(path,{credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}});if(r.status===401){location.href='/login';throw Error('ورود مجدد لازم است')}if(!r.ok)throw Error('HTTP '+r.status);return r.json()}
function cells(parent,rows,keys){parent.replaceChildren();for(const entry of rows){const tr=document.createElement('tr');for(const k of keys){const td=document.createElement('td');td.textContent=value(typeof k==='function'?k(entry):entry[k]);tr.append(td)}parent.append(tr)}if(!rows.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=keys.length;td.textContent='داده‌ای ثبت نشده است';tr.append(td);parent.append(tr)}}
async function status(){try{const s=await get('/api/status');set('state',s.state_label);for(const k of ['product','board_count','healthy_board_count','abnormal_board_count','firmware','patch','uptime','last_success_at'])set(k,s[k]);set('connection',s.error||s.state_label);set('board_summary',(s.boards||[]).map(b=>value(b.slot)+' - '+value(b.model)).join(' | ')||'اطلاعات برد موجود نیست');cells(byId('board_rows'),s.boards||[],['slot','model','status'])}catch(e){set('state','خطا در دریافت داده');set('connection',e.message)}}
async function history(){try{cells(byId('history_rows'),await get('/api/history'),['time',r=>r.success?'موفق':'ناموفق','error'])}catch(e){set('state',e.message)}}
async function events(){try{cells(byId('event_rows'),await get('/api/events'),['time','type','severity','message'])}catch(e){set('state',e.message)}}
document.querySelectorAll('.nav').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.nav,.tab').forEach(x=>x.classList.remove('active'));b.classList.add('active');byId(b.dataset.page).classList.add('active');if(b.dataset.page==='history')history();if(b.dataset.page==='events')events()}));
status();setInterval(()=>{status();if(byId('history').classList.contains('active'))history();if(byId('events').classList.contains('active'))events()},30000);
</script></body></html>"""

MARKER = '# ADMIN98_WEB_DASHBOARD_V1'
APPEND = '\n\n' + MARKER + '\nDASHBOARD_HTML = (Path(__file__).resolve().parent / "dashboard.html").read_text(encoding="utf-8")\n'

def main():
    p = argparse.ArgumentParser(description='Install Admin98 dashboard view on existing Flask app')
    p.add_argument('--target', default='/www/wwwroot/olt.admin98.ir')
    p.add_argument('--apply', action='store_true')
    args = p.parse_args()
    root = pathlib.Path(args.target).resolve()
    app = root / 'app.py'
    if not app.is_file():
        sys.exit('ERROR: app.py not found')
    source = app.read_text(encoding='utf-8')
    ast.parse(source)
    if MARKER in source:
        sys.exit('Already installed; no changes made')
    if any(key not in source for key in ('DASHBOARD_HTML', 'def api_status(', 'def login(')):
        sys.exit('ERROR: expected API or HTML markers missing')
    if not args.apply:
        print('DRY RUN OK: will back up app.py, write dashboard.html, and append a read-only template override.')
        return
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = root / ('app.py.backup-' + stamp)
    shutil.copy2(app, backup)
    html = root / 'dashboard.html'
    if html.exists():
        shutil.copy2(html, root / ('dashboard.html.backup-' + stamp))
    html.write_text(HTML, encoding='utf-8')
    try:
        updated = source + APPEND
        ast.parse(updated)
        app.write_text(updated, encoding='utf-8')
        import py_compile
        py_compile.compile(str(app), doraise=True)
    except Exception:
        shutil.copy2(backup, app)
        raise
    print('Installed. Backup:', backup)
    print('Restart only your Flask/Gunicorn web service after checking it.')

if __name__ == '__main__':
    main()
