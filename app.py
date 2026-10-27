#!/usr/bin/env python3
"""For Rent – estatus de clientes por asesor. Solo lee registro.json; escribe respuestas.json."""
import json, re, os, secrets, hmac, html, unicodedata, threading, datetime, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
BASE=os.path.dirname(os.path.abspath(__file__))
DATA_DIR=os.environ.get('DATA_DIR')  # modo Render: datos llegan por /sync/data
REMOTE=bool(DATA_DIR); SYNC_KEY=os.environ.get('SYNC_KEY','')
if REMOTE: os.makedirs(DATA_DIR,exist_ok=True)
_D=DATA_DIR or BASE
REG=os.path.join(DATA_DIR,'registro.json') if REMOTE else '/workspace/forrent/seguimiento_tg/registro.json'
CFG=os.path.join(DATA_DIR,'config.json') if REMOTE else '/workspace/forrent/seguimiento_tg/config.json'
TOK=os.path.join(_D,'tokens.json'); RESP=os.path.join(_D,'respuestas.json'); INMP=os.path.join(_D,'inmuebles_cache.json'); PORT=int(os.environ.get('PORT',18790))
LOCK=threading.Lock()
ESTATUS=["No contactado","No responde","Contactado","Visita agendada","Visita realizada","En oferta o negociación","Reserva agendada","Reserva firmada","Busca otra opción","Cerrado sin negocio"]
COLOR={"Sin estatus":("#d1d5db","#374151"),"No contactado":("#b45454","#fff"),"No responde":("#ef1c1c","#fff"),"Contactado":("#d6b656","#3a2c00"),"Visita agendada":("#ffd400","#2b2200"),"Visita realizada":("#5f9e6e","#fff"),"En oferta o negociación":("#16c60c","#062b00"),"Reserva agendada":("#5b7fb0","#fff"),"Reserva firmada":("#0a6cff","#fff"),"Busca otra opción":("#6b7280","#fff"),"Cerrado sin negocio":("#374151","#fff")}
def est_css(): return ''.join(f'.e{i}{{background:{b}!important;color:{t}!important;border-color:{b}!important}}.b{i}{{border-color:{b}!important}}' for i,(b,t) in enumerate(COLOR.values()))
ECLS={k:i for i,k in enumerate(COLOR)}
INTERES=["Con interés","Sin interés"]
MOTIVOS=["Inmueble no disponible","Propietario no autoriza visitas","Cliente no interesado","Descartado","Otro"]
SIT_OBLIG={"Contactado":"¿Qué espera el cliente? (obligatorio)","Busca otra opción":"¿Qué busca? (obligatorio)","Cerrado sin negocio":"Detalle del motivo (obligatorio)"}
def validar(d):
    e=d.get('estatus'); sit=(d.get('situacion') or '').strip()
    if e not in ESTATUS: return 'Elige un estatus'
    if e in SIT_OBLIG and not sit: return SIT_OBLIG[e]
    if e=='Visita agendada' and not re.match(r'^\d{4}-\d{2}-\d{2}',d.get('fecha_visita') or ''): return 'Indica la fecha de la visita'
    if e=='Visita realizada' and d.get('interes') not in INTERES: return 'Indica si quedó con interés o sin interés'
    if e=='En oferta o negociación':
        try:
            if float(str(d.get('monto')).replace(',','.'))<=0: raise ValueError
        except Exception: return 'Indica el monto en US$ (solo números)'
    if e=='Cerrado sin negocio' and d.get('motivo') not in MOTIVOS: return 'Elige el motivo del cierre'
    return None
def norm(s): return ''.join(c for c in unicodedata.normalize('NFD',s or '').lower() if unicodedata.category(c)!='Mn').strip()
PAUSA={'erika nunez de ornelas','luz jimenez'}
def load(p,d):
    try: return json.load(open(p,encoding='utf-8'))
    except Exception: return d
def clientes():
    r=load(REG,{}).get('clientes',{}); cf=load(CFG,{})
    ex=set(cf.get('excluir_contactos',[])); exa={norm(a) for a in cf.get('excluir_asesores',[])}-PAUSA  # pausa = solo asignación; siguen en seguimiento
    out={}
    for k,v in r.items():
        if k in ex or v.get('cerrado') or v.get('estado')!='ASIGNADO' or norm(v.get('asesor')) in exa: continue
        out.setdefault(v.get('asesor') or 'Sin asesor',[]).append(dict(v,contact_id=k))
    for l in out.values(): l.sort(key=lambda x:x.get('asignado_at') or '')
    return out
def tokens(ases):
    t=load(TOK,{}); ch=False
    if REMOTE:  # nunca generar tokens en Render; solo los que manda la caja
        t.setdefault('admin',secrets.token_urlsafe(32)); t.setdefault('asesores',{}); return t
    if 'admin' not in t: t['admin']=secrets.token_urlsafe(18); ch=True
    for a in ases:
        if a not in t.get('asesores',{}): t.setdefault('asesores',{})[a]=secrets.token_urlsafe(12); ch=True
    if ch: json.dump(t,open(TOK,'w'),ensure_ascii=False,indent=1)
    return t
def inmueble(v):
    ids=v.get('inmueble_ids') or {}
    t=v.get('inmueble') or v.get('propiedad_raw') or ''
    if 'http' in t or 'MLV' in t.upper() or 'mercadolibre' in t.lower(): t=''
    import re
    if re.search(r'[?=/]|www\.|\.com|dlrf',t,re.I): t=''
    t=t[:70]
    cod=f"Wasi {ids['wasi']}" if ids.get('wasi') else (f"Rex {ids['rex']}" if ids.get('rex') else '')
    if cod and (not t or t.replace(' ','').lower()==cod.replace(' ','').lower()): t=''
    d=_INM().get(str(ids.get('wasi'))) if ids.get('wasi') else (_INM().get('rex:'+str(ids.get('rex'))) if ids.get('rex') else None)
    if d:
        rich=_fmt_inm(d)
        if rich: t=rich
    t=_limpia(t)
    return t,cod
_INMC=[None,0]
def _INM():
    import os
    p=INMP
    try:
        m=os.path.getmtime(p)
        if _INMC[0] is None or m!=_INMC[1]: _INMC[0]=json.load(open(p)); _INMC[1]=m
    except Exception: _INMC[0]=_INMC[0] or {}
    return _INMC[0]
_TIPOS=['Apartamento','Penthouse','Townhouse','Casa','Quinta','Anexo','Local','Oficina','Galpón','Galpon','Terreno','Edificio','Consultorio','Fondo de comercio','Hotel','Finca']
def _fmt_inm(d):
    import re
    if 'fuente' in d:
        tipo=d.get('tipo') or ''; op=d.get('operacion') or ''; zona=d.get('zona') or ''; pr=d.get('precio')
        alq='alquiler' in op.lower()
    else:
        tit=d.get('title') or ''; tipo=''
        for k in _TIPOS:
            if re.search(r'\b'+k+r'\b',tit,re.I): tipo=k.replace('Galpon','Galpón'); break
        venta=d.get('for_sale')=='true'; alq=d.get('for_rent')=='true' and not venta
        op='Alquiler' if alq else ('Venta' if venta else '')
        z=d.get('zone_label') or ''; l=d.get('location_label') or ''
        zona=', '.join(x for x in [z,l] if x and x.lower()!=z.lower() or x==z) if z or l else ''
        if l and z and l.lower()==z.lower(): zona=z
        pr=float(d.get('rent_price') or 0) if alq else float(d.get('sale_price') or 0)
    a=' '.join(x for x in [tipo,op.lower() if tipo else op] if x)
    precio=''
    if pr:
        n=f"{pr:,.0f}".replace(',','.')
        precio=f"US$ {n}"+('/mes' if alq else '')
    out=' · '.join(x for x in [a,zona,precio] if x)
    if re.search(r'MLV|mercadolibre|http',out,re.I): return ''
    return out
def _limpia(t):
    import re
    if not t: return t
    s=t.strip()
    m=re.match(r'^(se\s+ofrece[n]?|ofrezco|ofrecemos)\s+',s,re.I)
    op=None
    if m: s=s[m.end():]
    else:
        m=re.match(r'^(vendo|se\s+vende[n]?|vendemos)\s+',s,re.I) or re.match(r'^(alquilo|se\s+alquila[n]?|alquilamos)\s+',s,re.I)
        if m:
            op='venta' if m.group(1).lower().find('vend')>=0 else 'alquiler'
            s=s[m.end():]
            if op not in s.lower():
                p=s.split(' ',1); s=p[0]+' en '+op+(' '+p[1] if len(p)>1 else '')
    return s[:1].upper()+s[1:] if s else t
def _ts(x): return (x or {}).get('at') or ''
def merge_resp(base,new):
    """Une respuestas: por cliente gana la más reciente; las demás van al historial (sin duplicar)."""
    out=dict(base)
    for k,n in (new or {}).items():
        o=out.get(k)
        if not o: out[k]=n; continue
        if _ts(n)==_ts(o) and len(n.get('historial',[]))<=len(o.get('historial',[])): continue
        allr={}
        for r in [o,n]+o.get('historial',[])+n.get('historial',[]):
            r=dict(r); r.pop('historial',None)
            if _ts(r): allr[_ts(r)]=r
        L=[allr[t] for t in sorted(allr)]
        cur=dict(L[-1]); cur['historial']=L[:-1][-10:]
        if not cur['historial']: cur.pop('historial')
        out[k]=cur
    return out
def _wj(path,obj):
    tmp=path+'.tmp'; json.dump(obj,open(tmp,'w'),ensure_ascii=False,indent=1); os.replace(tmp,path)
def mig(r):
    for v in r.values():
        if isinstance(v,dict):
            if v.get('estatus')=='Reserva o firma': v['estatus']='Reserva agendada'
            for h in v.get('historial',[]) or []:
                if h.get('estatus')=='Reserva o firma': h['estatus']='Reserva agendada'
    return r
def fecha(s):
    try: d=datetime.datetime.fromisoformat(s); return d.strftime('%d/%m/%Y')
    except Exception: return ''
CSS="""*{box-sizing:border-box}body{margin:0;font-family:Inter,'Helvetica Neue',Arial,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#f4f4f5;color:#111}
header{background:#fff;color:#111;padding:12px 16px;border-bottom:4px solid #E76108;text-align:center}header img{height:64px}header .tt{margin:4px 0 0;font-size:20px;font-weight:800;color:#111;letter-spacing:.2px}header p{margin:6px 0 0;color:#444;font-size:14px}main{max-width:720px;margin:0 auto;padding:12px}
.card{background:#fff;border-radius:14px;box-shadow:0 2px 8px rgba(0,0,0,.07);padding:14px;margin:12px 0;border-left:5px solid #E76108}
.card.ok{border-left-color:#1f9d55}.n{font-weight:700;font-size:17px}.meta{color:#5b6475;font-size:13px;margin:4px 0}
.inm{background:#f4f4f5;border-radius:8px;padding:8px;font-size:14px;margin:8px 0}.cod{display:inline-block;background:#111;color:#fff;border-radius:6px;padding:1px 7px;font-size:12px;margin-left:4px}
select:focus,textarea:focus{outline:2px solid #E76108;border-color:#E76108}select,input,textarea{width:100%;font:inherit;padding:10px;border:1px solid #cdd4e0;border-radius:9px;margin:5px 0;background:#fff}textarea{min-height:70px}
button{width:100%;background:#E76108;color:#fff;border:0;border-radius:9px;padding:12px;font-weight:700;font-size:15px}.msg{font-size:13px;color:#1f9d55;min-height:16px}
h2{font-size:17px;margin:22px 4px 4px;color:#111;border-bottom:2px solid #E76108;padding-bottom:4px}table{width:100%;border-collapse:collapse;font-size:13px;background:#fff}td,th{border-bottom:1px solid #e3e7ef;padding:6px;text-align:left}"""
JS="""const SO={"Contactado":"¿Qué espera el cliente? (obligatorio)","Busca otra opción":"¿Qué busca? (obligatorio)","Cerrado sin negocio":"Detalle del motivo (obligatorio)"};
function fv(s){const f=s.form,v=s.value;const sh=(c,on)=>{const x=f.querySelector(c);x.style.display=on?'block':'none';x.querySelectorAll('input,select').forEach(i=>i.required=on)};
sh('.x-fecha',v=='Visita agendada');sh('.x-int',v=='Visita realizada');sh('.x-monto',v=='En oferta o negociación');sh('.x-mot',v=='Cerrado sin negocio');
s.className=(window.EC&&EC[v]!=null)?'e'+EC[v]:'';const t=f.querySelector('textarea');t.required=!!SO[v];t.placeholder=SO[v]||'Situación del cliente (opcional)…'}
async function g(f,id){const d=new FormData(f);const b={id:id};['estatus','fecha_visita','interes','monto','motivo','situacion'].forEach(k=>b[k]=d.get(k)||'');
const m=f.querySelector('.msg');m.style.color='';m.textContent='Guardando…';const r=await fetch(location.pathname+'/guardar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});
const j=await r.json().catch(()=>({}));if(r.ok){m.textContent='✔ Guardado';f.closest('.card').classList.add('ok')}else{m.style.color='#c00';m.textContent=j.error||'Error al guardar'}return false}
document.querySelectorAll('select[name=estatus]').forEach(fv);"""
def page(title,sub,body):
    return f"<!doctype html><html lang=es><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Sistema de Seguimiento de Cliente · For Rent · {html.escape(title)}</title><style>{CSS}{est_css()}</style><script>var EC={json.dumps(ECLS,ensure_ascii=False)}</script><header><img src=/logo.jpg alt='For Rent Grupo Inmobiliario'><h1 class=tt>Sistema de Seguimiento de Cliente</h1><p>{sub}</p></header><main>{body}</main><script>{JS}</script></html>"
def card(v,resp):
    e=html.escape; t,cod=inmueble(v); r=resp.get(v['contact_id'],{})
    opts=''.join(f"<option class=e{ECLS[s]}{' selected' if r.get('estatus')==s else ''}>{s}</option>" for s in ESTATUS)
    tel=f" · 📞 {e(v['telefono'])}" if v.get('telefono') else ''
    fa=fecha(v.get('asignado_at')); 
    return f"""<div class="card{' ok' if r else ''}"><div class=n>{e(v.get('nombre') or 'Cliente')}</div>
<div class=meta>{('Asignado: '+fa) if fa else ''}{tel}{(' · '+e(v.get('tipo_lead'))) if v.get('tipo_lead') else ''}</div>
<div class=inm>🏠 {e(t) or ('Inmueble' if cod else 'Sin inmueble específico')}{f'<span class=cod>{e(cod)}</span>' if cod else ''}</div>
<form onsubmit="return g(this,'{e(v['contact_id'])}')"><select name=estatus onchange=fv(this) required><option value="">— Estatus —</option>{opts}</select>
<div class=x-fecha style=display:none><label class=meta>Fecha de la visita</label><input type=datetime-local name=fecha_visita value="{e(r.get('fecha_visita') or '')}"></div>
<div class=x-int style=display:none><select name=interes><option value="">— ¿Interés tras la visita? —</option>{''.join(f"<option{' selected' if r.get('interes')==x else ''}>{x}</option>" for x in INTERES)}</select></div>
<div class=x-monto style=display:none><input type=number min=1 step=any inputmode=decimal name=monto placeholder="Monto en US$" value="{e(str(r.get('monto') or ''))}"></div>
<div class=x-mot style=display:none><select name=motivo><option value="">— Motivo del cierre —</option>{''.join(f"<option{' selected' if r.get('motivo')==x else ''}>{x}</option>" for x in MOTIVOS)}</select></div>
<textarea name=situacion placeholder="Situación del cliente…">{e(r.get('situacion') or '')}</textarea><button>Guardar</button><div class=msg>{'Último guardado: '+e(r.get('at','')[:16].replace('T',' ')) if r else ''}</div></form></div>"""
class H(BaseHTTPRequestHandler):
    def ctx(self):
        p=urllib.parse.urlparse(self.path).path.rstrip('/').split('/')
        c=clientes(); t=tokens(c.keys()); inv={v:k for k,v in t['asesores'].items()}
        return p,c,t,inv
    def send(self,code,body,ct='text/html; charset=utf-8'):
        b=body.encode(); self.send_response(code); self.send_header('Content-Type',ct); self.send_header('Cache-Control','no-store'); self.send_header('X-Robots-Tag','noindex'); self.end_headers(); self.wfile.write(b)
    def sync_ok(self): return bool(SYNC_KEY) and hmac.compare_digest(self.headers.get('X-Sync-Key',''),SYNC_KEY)
    def do_HEAD(self): self.send_response(200); self.end_headers()
    def do_GET(self):
        if self.path=='/healthz': return self.send(200,'ok','text/plain')
        if self.path=='/sync/respuestas':
            if not self.sync_ok(): return self.send(403,'{}','application/json')
            with LOCK: return self.send(200,json.dumps(load(RESP,{}),ensure_ascii=False),'application/json')
        if self.path=='/logo.jpg':
            b=open(os.path.join(BASE,'logo.jpg'),'rb').read(); self.send_response(200); self.send_header('Content-Type','image/jpeg'); self.send_header('Cache-Control','max-age=86400'); self.end_headers(); return self.wfile.write(b)
        p,c,t,inv=self.ctx(); resp=mig(load(RESP,{}))
        if len(p)==3 and p[1]=='a' and p[2] in inv:
            a=inv[p[2]]; l=c.get(a,[])
            return self.send(200,page(a,f"Hola, {html.escape(a.split()[0])}. Tienes {len(l)} cliente(s) sin estatus. Cuéntanos la situación de cada uno.",''.join(card(v,resp) for v in l) or '<p>¡No tienes clientes pendientes! 🎉</p>'))
        if len(p)==3 and p[1]=='admin' and p[2]==t['admin']:
            import panel; return self.send(200,panel.render(page,resp))
        self.send(404,page('No encontrado','Enlace no válido','<p>Este enlace no es válido.</p>'))
    def do_POST(self):
        if self.path=='/sync/data':
            if not (REMOTE and self.sync_ok()): return self.send(403,'{}','application/json')
            try: d=json.loads(self.rfile.read(min(int(self.headers.get('Content-Length',0)),50_000_000)))
            except Exception: return self.send(400,'{}','application/json')
            with LOCK:
                for key,path in [('registro',REG),('config',CFG),('tokens',TOK),('inmuebles',INMP)]:
                    if key in d: _wj(path,d[key])
                if 'respuestas' in d: _wj(RESP,merge_resp(d['respuestas'],load(RESP,{})))
            return self.send(200,'{"ok":true}','application/json')
        p,c,t,inv=self.ctx()
        if not(len(p)==4 and p[1]=='a' and p[2] in inv and p[3]=='guardar'): return self.send(404,'{}','application/json')
        a=inv[p[2]]
        try: d=json.loads(self.rfile.read(min(int(self.headers.get('Content-Length',0)),20000)))
        except Exception: return self.send(400,'{}','application/json')
        if d.get('id') not in {v['contact_id'] for v in c.get(a,[])}: return self.send(400,'{"error":"Cliente no válido"}','application/json')
        err=validar(d)
        if err: return self.send(400,json.dumps({'error':err},ensure_ascii=False),'application/json')
        es=d['estatus']
        rec={'asesor':a,'estatus':es,'situacion':(d.get('situacion') or '')[:2000],'at':datetime.datetime.now().astimezone().isoformat(timespec='seconds')}
        if es=='Visita agendada': rec['fecha_visita']=d['fecha_visita'][:16]
        if es=='Visita realizada': rec['interes']=d['interes']
        if es=='En oferta o negociación': rec['monto']=float(str(d['monto']).replace(',','.'))
        if es=='Cerrado sin negocio': rec['motivo']=d['motivo']
        with LOCK:
            r=load(RESP,{}); old=r.get(d['id']); 
            if old: rec['historial']=(old.pop('historial',[])+[old])[-10:]
            r[d['id']]=rec; tmp=RESP+'.tmp'; json.dump(r,open(tmp,'w'),ensure_ascii=False,indent=1); os.replace(tmp,RESP)
        self.send(200,'{"ok":true}','application/json')
    def log_message(self,*a): pass
if __name__=='__main__':
    if REMOTE: ThreadingHTTPServer(('0.0.0.0',PORT),H).serve_forever()
    c=clientes(); t=tokens(c.keys())
    with open(os.path.join(BASE,'enlaces.txt'),'w') as f:
        f.write("BASE = URL pública (ver url_publica.txt) o http://127.0.0.1:%d\n\nADMIN: BASE/admin/%s\n\n"%(PORT,t['admin']))
        for a,l in sorted(c.items(),key=lambda x:-len(x[1])): f.write(f"{a} ({len(l)}): BASE/a/{t['asesores'][a]}\n")
    ThreadingHTTPServer(('0.0.0.0',PORT),H).serve_forever()
