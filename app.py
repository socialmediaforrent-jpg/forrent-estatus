#!/usr/bin/env python3
"""For Rent – estatus de clientes por asesor. Solo lee registro.json; escribe respuestas.json."""
import json, re, os, base64, mimetypes, secrets, hmac, html, unicodedata, threading, datetime, urllib.parse
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
# ===== Modelo ESTADO + SITUACIÓN + COMENTARIO (aprobado por José, 27-oct) =====
# estado -> lista de (situación, pide_fecha, fecha_obligatoria); 'motivo' = texto obligatorio
ESTADOS={
 "Nuevo":{"sits":[("Contactado",0,0),("No contactado",0,0)]},
 "En proceso":{"sits":[("Visita agendada",1,1),("Visita realizada",1,1)]},
 "Negociación":{"sits":[("Oferta realizada",1,1),("Oferta aceptada",1,1),("Reserva agendada",1,1),("Reserva firmada",1,1)]},
 "Perfeccionado":{"sits":[("Documento privado",1,1),("Documento notariado",1,1),("Documento registrado",1,0)]},
 "Inmueble entregado":{"sits":[("Inmueble entregado",1,1)]},
 "En espera":{"motivo":"Motivo de la espera (obligatorio)"},
 "Recuperado":{},
 "Perdido":{"motivo":"Motivo de pérdida (obligatorio)"},
}
ESTATUS=list(ESTADOS)
SITS={e:[s[0] for s in d.get('sits',[])] for e,d in ESTADOS.items()}
COLOR_HEX={"Sin estatus":"#cccccc","No contactado":"#b45454","Contactado":"#d6b656","Visita agendada":"#ffd400","Visita realizada":"#5f9e6e",
 "Oferta realizada":"#16c60c","Oferta aceptada":"#0fa30f","Reserva agendada":"#5b7fb0","Reserva firmada":"#0a6cff",
 "Documento privado":"#8e6cc7","Documento notariado":"#7a3fd1","Documento registrado":"#5b1fb8","Inmueble entregado":"#c9a227",
 "En espera":"#e08a2e","Recuperado":"#2aa198","Perdido":"#444444",
 # color representativo de cada estado (encabezados/tarjetas)
 "Nuevo":"#d6b656","En proceso":"#5f9e6e","Negociación":"#16c60c","Perfeccionado":"#7a3fd1"}
def _txt(h):
    r,g,b=(int(h[i:i+2],16) for i in (1,3,5)); return '#1f1a00' if (0.299*r+0.587*g+0.114*b)>150 else '#fff'
COLOR={k:(v,_txt(v)) for k,v in COLOR_HEX.items()}
CIERRE_URL=os.environ.get('CIERRE_URL','#')  # Sistema Contable de For Rent (lo construye Contabilidad)
EQP=os.path.join(_D,'equipos.json')  # {lider:[miembros]} (código, no datos sensibles)
OUTBOX=os.path.join(_D,'outbox_lideres.json')  # avisos pendientes a líderes; NO se envían sin OK de José
def equipos():
    try: return {k:[m for m in v if not m.startswith('?')] for k,v in json.load(open(EQP)).items() if not k.startswith('_')}
    except Exception: return {}
def lider_de(a):
    for l,m in equipos().items():
        if a==l or a in m: return l
    return ''
def cierre_url(v):
    q=urllib.parse.urlencode({'cliente_id':v['contact_id'],'cliente':v.get('nombre') or '','asesor':v.get('asesor') or ''})
    return (CIERRE_URL+('&' if '?' in CIERRE_URL else '?')+q) if CIERRE_URL!='#' else '#'
def cierre_btn(v):
    tip='' if CIERRE_URL!='#' else " title='Próximamente — Sistema Contable de For Rent' onclick='alert(this.title);return false'"
    return f"<a class=cierre href=\"{html.escape(cierre_url(v))}\" target=_blank{tip}>Reportar Cierre</a>"
UPL=os.path.join(_D,'uploads'); DOC_EXT={'.pdf','.jpg','.jpeg','.png','.webp','.heic'}; DOC_MAX=10_000_000
def color_key(st): return st.get('situacion') if st.get('situacion') in COLOR else (st.get('estado') or 'Sin estatus')
def est_css(): return ''.join(f'.e{i}{{background:{b}!important;color:{t}!important;border-color:{b}!important}}.b{i}{{border-color:{b}!important}}' for i,(b,t) in enumerate(COLOR.values()))
ECLS={k:i for i,k in enumerate(COLOR)}
def sit_def(e,s):
    for x in ESTADOS.get(e,{}).get('sits',[]):
        if x[0]==s: return x
    return None
def validar(d):
    e=d.get('estado'); s=(d.get('situacion') or '').strip(); f=d.get('fecha') or ''
    if e not in ESTADOS: return 'Elige un estado'
    cfg=ESTADOS[e]
    if cfg.get('sits'):
        sd=sit_def(e,s)
        if not sd: return 'Elige la situación'
        if sd[2] and not re.match(r'^\d{4}-\d{2}-\d{2}',f): return f'Indica la fecha ({s})'
    if cfg.get('motivo') and not (d.get('motivo') or '').strip(): return cfg['motivo']
    return None
# Migración: estados de Telegram/registro y etiquetas viejas de la página
TGMAP={'CONTACTADO':('Nuevo','Contactado',''),'INTERESADO':('Nuevo','Contactado',''),'NO RESPONDE':('Nuevo','No contactado','No responde'),
 'NO CONTACTADO':('Nuevo','No contactado',''),'VISITA AGENDADA':('En proceso','Visita agendada',''),'VISITA REALIZADA':('En proceso','Visita realizada',''),
 'VISITA CONCRETADA':('En proceso','Visita realizada',''),'OFERTA':('Negociación','Oferta realizada',''),'EN OFERTA':('Negociación','Oferta realizada',''),
 'ACEPTADA':('Negociación','Oferta aceptada',''),'RESERVA':('Negociación','Reserva agendada',''),'RESERVA AGENDADA':('Negociación','Reserva agendada',''),
 'FIRMADO':('Negociación','Reserva firmada',''),'FIRMADA':('Negociación','Reserva firmada',''),
 'BUSCANDO OTRA PROPIEDAD':('Perdido','','Busca otra opción'),'NO INTERESADO':('Perdido','','No interesado'),
 'CERRADO':('Perdido','','Cerrado sin negocio'),'PERDIDO':('Perdido','','Perdido')}
OLDMAP={'No contactado':('Nuevo','No contactado',''),'No responde':('Nuevo','No contactado','No responde'),'Contactado':('Nuevo','Contactado',''),
 'Visita agendada':('En proceso','Visita agendada',''),'Visita realizada':('En proceso','Visita realizada',''),
 'En oferta o negociación':('Negociación','Oferta realizada',''),'Reserva o firma':('Negociación','Reserva agendada',''),
 'Reserva agendada':('Negociación','Reserva agendada',''),'Reserva firmada':('Negociación','Reserva firmada',''),
 'Busca otra opción':('Perdido','','Busca otra opción'),'Cerrado sin negocio':('Perdido','','Cerrado sin negocio')}
def conv(r):
    """Registro de página (nuevo o viejo) -> dict nuevo modelo (sin historial)."""
    if not r: return {}
    if r.get('estado') in ESTADOS: return {k:r.get(k) for k in ('estado','situacion','fecha','motivo','comentario','doc','at','asesor') if r.get(k)}
    o=r.get('estatus')
    if o not in OLDMAP: return {}
    e,s,x=OLDMAP[o]; out={'estado':e,'at':r.get('at',''),'asesor':r.get('asesor','')}
    if s: out['situacion']=s
    f=(r.get('fecha_visita') or '')[:10] if o=='Visita agendada' else (r.get('at') or '')[:10]
    if s and f: out['fecha']=f
    com=[c for c in [r.get('situacion'),r.get('interes'),(f"Monto US$ {r['monto']:,.0f}".replace(',','.') if r.get('monto') else '')] if c]
    if e=='Perdido': out['motivo']=r.get('motivo') or x
    elif x: com.insert(0,x)
    if com: out['comentario']=' · '.join(com)
    return out
def mig(resp):
    out={}
    for k,r in (resp or {}).items():
        if not isinstance(r,dict): continue
        c=conv(r)
        if not c: continue
        c['historial']=[h for h in (conv(x) for x in r.get('historial',[]) or []) if h]
        out[k]=c
    return out
def actual(v,r):
    """Estado vigente del cliente: página (si hay) o Telegram. -> dict con src."""
    r=r or {}
    if r.get('estado') in ESTADOS: return dict(r,src='web')
    t=TGMAP.get((v.get('estado') or '').upper().strip())
    if not t: return {'estado':'Sin estatus','src':'tg'}
    e,s,x=t; f=(v.get('estado_desde') or v.get('primer_contacto_at') or '')[:10]
    out={'estado':e,'src':'tg','at':v.get('estado_desde') or ''}
    if s: out['situacion']=s; out['fecha']=f if sit_def(e,s) and sit_def(e,s)[1] else ''
    if e=='Perdido': out['motivo']=x
    elif x: out['comentario']=x
    return out
def norm(s): return ''.join(c for c in unicodedata.normalize('NFD',s or '').lower() if unicodedata.category(c)!='Mn').strip()
PAUSA={'erika nunez de ornelas','luz jimenez'}
def load(p,d):
    try: return json.load(open(p,encoding='utf-8'))
    except Exception: return d
def clientes():
    r=load(REG,{}).get('clientes',{}); cf=load(CFG,{})
    ex=set(cf.get('excluir_contactos',[])); exa={norm(a) for a in cf.get('excluir_asesores',[])}-PAUSA  # pausa = solo asignación; siguen en seguimiento
    out={}; rs=load(RESP,{})
    for k,v in r.items():
        if k in ex or v.get('cerrado') or norm(v.get('asesor')) in exa: continue
        if v.get('estado')!='ASIGNADO' and not vencido(v,rs.get(k)): continue  # ASIGNADO o Nuevo/Contactado vencido  # + Contactado vencidos (+72h)
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
def fecha(s):
    try: d=datetime.datetime.fromisoformat((s or '')[:19]); return d.strftime('%d/%m/%Y')
    except Exception: return ''
CSS="""*{box-sizing:border-box}body{margin:0;font-family:Inter,'Helvetica Neue',Arial,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#f4f4f5;color:#111}
header{background:#fff;color:#111;padding:12px 16px;border-bottom:4px solid #E76108;text-align:center}header img{height:64px}header .tt{margin:4px 0 0;font-size:20px;font-weight:800;color:#111;letter-spacing:.2px}header p{margin:6px 0 0;color:#444;font-size:14px}main{max-width:720px;margin:0 auto;padding:12px}
.card{background:#fff;border-radius:14px;box-shadow:0 2px 8px rgba(0,0,0,.07);padding:14px;margin:12px 0;border-left:5px solid #E76108}
.card.ok{border-left-color:#1f9d55}.n{font-weight:700;font-size:17px}.meta{color:#5b6475;font-size:13px;margin:4px 0}
.inm{background:#f4f4f5;border-radius:8px;padding:8px;font-size:14px;margin:8px 0}.cod{display:inline-block;background:#111;color:#fff;border-radius:6px;padding:1px 7px;font-size:12px;margin-left:4px}
select:focus,textarea:focus{outline:2px solid #E76108;border-color:#E76108}select,input,textarea{width:100%;font:inherit;padding:10px;border:1px solid #cdd4e0;border-radius:9px;margin:5px 0;background:#fff}textarea{min-height:70px}
button{width:100%;background:#E76108;color:#fff;border:0;border-radius:9px;padding:12px;font-weight:700;font-size:15px}.msg{font-size:13px;color:#1f9d55;min-height:16px}
.pill{display:inline-block;border-radius:6px;padding:1px 7px;font-size:12px}.cierre{display:block;text-align:center;background:#0a6cff;color:#fff;border-radius:9px;padding:11px;font-weight:700;text-decoration:none;margin:6px 0}
h2{font-size:17px;margin:22px 4px 4px;color:#111;border-bottom:2px solid #E76108;padding-bottom:4px}table{width:100%;border-collapse:collapse;font-size:13px;background:#fff}td,th{border-bottom:1px solid #e3e7ef;padding:6px;text-align:left}"""
JS="""const SX=window.ESTCFG||{};
function fv(s,keep){const f=s.form,v=s.value,c=SX[v]||{},sits=c.sits||[];const sh=(q,on)=>{const x=f.querySelector(q);x.style.display=on?'block':'none';return x};
const ss=f.querySelector('select[name=situacion]');const prev=keep?f.dataset.sit:ss.value;
ss.innerHTML='<option value="">— Situación —</option>'+sits.map(x=>`<option${x[0]==prev?' selected':''}>${x[0]}</option>`).join('');ss.required=sits.length>0;
sh('.x-sit',sits.length>0);const m=sh('.x-mot',!!c.motivo).querySelector('input');m.required=!!c.motivo;m.placeholder=c.motivo||'';
s.className=(window.EC&&EC[v]!=null)?'e'+EC[v]:'';fs(ss)}
function fs(ss){const f=ss.form,e=f.querySelector('select[name=estado]').value,sits=(SX[e]||{}).sits||[],d=sits.find(x=>x[0]==ss.value);
const fx=f.querySelector('.x-fecha');fx.style.display=d&&d[1]?'block':'none';const fi=fx.querySelector('input');fi.required=!!(d&&d[2]);fx.querySelector('.x-fl').textContent=d?'('+d[0]+(d[2]?'':', opcional')+')':'';
f.querySelector('.x-doc').style.display=ss.value=='Reserva firmada'?'block':'none';ss.className=(window.EC&&EC[ss.value]!=null)?'e'+EC[ss.value]:''}
const b64=file=>new Promise((ok,ko)=>{const r=new FileReader();r.onload=()=>ok(String(r.result).split(',')[1]);r.onerror=ko;r.readAsDataURL(file)});
async function g(f,id){const d=new FormData(f);const b={id:id};['estado','situacion','fecha','motivo','comentario'].forEach(k=>b[k]=d.get(k)||'');
const m=f.querySelector('.msg');m.style.color='';const fl=f.querySelector('input[name=doc]');
if(b.situacion=='Reserva firmada'&&fl.files.length){const x=fl.files[0];if(x.size>10e6){m.style.color='#c00';m.textContent='El documento pasa de 10 MB';return false}m.textContent='Subiendo documento…';b.doc={name:x.name,data:await b64(x)}}
m.textContent='Guardando…';const r=await fetch(location.pathname+'/guardar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});
const j=await r.json().catch(()=>({}));if(r.ok){m.textContent='✔ Guardado';f.closest('.card').classList.add('ok');fl.value=''}else{m.style.color='#c00';m.textContent=j.error||'Error al guardar'}return false}
document.querySelectorAll('select[name=estado]').forEach(s=>fv(s,1));"""

def page(title,sub,body):
    return f"<!doctype html><html lang=es><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Sistema de Seguimiento de Cliente · For Rent · {html.escape(title)}</title><style>{CSS}{est_css()}</style><script>var EC={json.dumps(ECLS,ensure_ascii=False)},ESTCFG={json.dumps(ESTADOS,ensure_ascii=False)}</script><header><img src=/logo.jpg alt='For Rent Grupo Inmobiliario'><h1 class=tt>Sistema de Seguimiento de Cliente</h1><p>{sub}</p></header><main>{body}</main><script>{JS}</script></html>"
def desde(v,r):
    """Fecha en que el cliente entró a su estado+situación actual: (iso, fuente)."""
    r=r or {}
    if r.get('estado') in ESTADOS:
        key=(r.get('estado'),r.get('situacion')); t=r.get('at','')
        for o in reversed(r.get('historial',[]) or []):
            if (o.get('estado'),o.get('situacion'))==key and o.get('at'): t=o['at']
            else: break
        return t,'pagina'
    for k,s in (('estado_desde','telegram'),('primer_contacto_at','primer_contacto'),('asignado_at','asignacion')):
        if v.get(k): return v[k],s
    return '',''
def horas(iso):
    try: return (datetime.datetime.now().astimezone()-datetime.datetime.fromisoformat(iso)).total_seconds()/3600
    except Exception: return None
def contactado(v,r):
    a=actual(v,r); return a.get('estado')=='Nuevo' and a.get('situacion')=='Contactado'
def vencido(v,r):
    r=conv_full(r)
    if v.get('cerrado') or not contactado(v,r): return False
    h=horas(desde(v,r)[0]); return h is not None and h>72
def conv_full(r):
    if not r: return {}
    if r.get('estado') in ESTADOS and all(h.get('estado') in ESTADOS for h in r.get('historial',[]) or []): return r
    return mig({'x':r}).get('x',{})
def doc_name(p): return os.path.basename(p or '').split('_',1)[-1]
def card(v,resp,tok='',lider=False):
    e=html.escape; t,cod=inmueble(v); r=resp.get(v['contact_id'],{}); a=actual(v,r)
    cur_e=r.get('estado') or ''; cur_s=r.get('situacion') or ''
    if not cur_e and a.get('estado')!='Sin estatus': cur_e=a['estado']; cur_s=a.get('situacion') or ''
    opts=''.join(f"<option class=e{ECLS[x if x in ECLS else 'Sin estatus']}{' selected' if cur_e==x else ''}>{x}</option>" for x in ESTATUS)
    tel=f" · 📞 {e(v['telefono'])}" if v.get('telefono') else ''
    fa=fecha(v.get('asignado_at')); vb=''
    if vencido(v,r):
        hh=horas(desde(v,r)[0])
        vb=f"<div style='margin:6px 0;padding:6px 8px;background:#fee2e2;border-radius:8px;color:#991b1b;font-size:13px'><span style='background:#dc2626;color:#fff;border-radius:6px;padding:1px 7px;font-weight:bold'>Vencido +72h</span> Contactado hace {int(hh//24)} días · Tienes 72 horas para actualizar este cliente</div>"
    cid=e(v['contact_id'])
    docl=f"<div class=meta>📎 Documento actual: <a href='/a/{e(tok)}/doc/{cid}/{e(os.path.basename(r['doc']))}' target=_blank>{e(doc_name(r['doc']))}</a></div>" if r.get('doc') else ''
    act=''
    if a.get('estado')!='Sin estatus':
        act=f"<div class=meta>Actual: <span class='pill e{ECLS[color_key(a)]}'>{e(a['estado'])}{(' · '+e(a['situacion'])) if a.get('situacion') else ''}{(' ('+e(fecha(a['fecha']))+')') if a.get('fecha') else ''}</span>{' (Telegram)' if a.get('src')=='tg' else ''}</div>"
    return f"""<div class="card{' ok' if r else ''}"><div class=n>{e(v.get('nombre') or 'Cliente')}</div>
<div class=meta>{('Asignado: '+fa) if fa else ''}{tel}{(' · '+e(v.get('tipo_lead'))) if v.get('tipo_lead') else ''}</div>
{vb}<div class=inm>🏠 {e(t) or ('Inmueble' if cod else 'Sin inmueble específico')}{f'<span class=cod>{e(cod)}</span>' if cod else ''}</div>{act}
<form onsubmit="return g(this,'{cid}')" data-sit="{e(cur_s)}"><label class=meta>Estado</label><select name=estado onchange=fv(this) required><option value="">— Estado —</option>{opts}</select>
<div class=x-sit style=display:none><label class=meta>Situación</label><select name=situacion onchange=fs(this)></select></div>
<div class=x-fecha style=display:none><label class=meta>Fecha <span class=x-fl></span></label><input type=date name=fecha value="{e((r.get('fecha') or a.get('fecha') or '')[:10])}"></div>
<div class=x-mot style=display:none><input name=motivo maxlength=500 value="{e(r.get('motivo') or '')}"></div>
<div class=x-doc style=display:none><label class=meta>Documento de reserva (PDF o imagen, máx. 10 MB)</label><input type=file name=doc accept=".pdf,image/*">{docl}
{cierre_btn(v) if lider else "<div class=meta>Tu líder reportará el cierre en el Sistema Contable.</div>"}</div>
<label class=meta>Comentario</label><textarea name=comentario maxlength=2000 placeholder="Comentario (opcional)…">{e(r.get('comentario') or '')}</textarea><button>Guardar</button><div class=msg>{'Último guardado: '+e(r.get('at','')[:16].replace('T',' ')) if r else ''}</div></form></div>"""
def safe_upl(rel):
    rel=(rel or '').replace('\\','/')
    if not re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9._-]+',rel) or '..' in rel: return None
    return os.path.join(UPL,rel)
def save_upl(rel,raw):
    fp=safe_upl(rel)
    if not fp: return None
    os.makedirs(os.path.dirname(fp),exist_ok=True); tmp=fp+'.tmp'; open(tmp,'wb').write(raw); os.replace(tmp,fp); return fp
def uploads_list():
    out={}
    if os.path.isdir(UPL):
        for c in os.listdir(UPL):
            for f in os.listdir(os.path.join(UPL,c)):
                if not f.endswith('.tmp'): out[c+'/'+f]=os.path.getsize(os.path.join(UPL,c,f))
    return out
class H(BaseHTTPRequestHandler):
    def ctx(self):
        p=urllib.parse.urlparse(self.path).path.rstrip('/').split('/')
        c=clientes(); t=tokens(c.keys()); inv={v:k for k,v in t['asesores'].items()}
        return p,c,t,inv
    def send(self,code,body,ct='text/html; charset=utf-8'):
        b=body.encode(); self.send_response(code); self.send_header('Content-Type',ct); self.send_header('Cache-Control','no-store'); self.send_header('X-Robots-Tag','noindex'); self.end_headers(); self.wfile.write(b)
    def file(self,fp):
        if not fp or not os.path.isfile(fp): return self.send(404,'No encontrado','text/plain')
        ct=mimetypes.guess_type(fp)[0] or 'application/octet-stream'; b=open(fp,'rb').read()
        self.send_response(200); self.send_header('Content-Type',ct); self.send_header('Cache-Control','no-store'); self.send_header('X-Robots-Tag','noindex'); self.end_headers(); self.wfile.write(b)
    def sync_ok(self): return bool(SYNC_KEY) and hmac.compare_digest(self.headers.get('X-Sync-Key',''),SYNC_KEY)
    def do_HEAD(self): self.send_response(200); self.end_headers()
    def do_GET(self):
        if self.path=='/healthz': return self.send(200,'ok','text/plain')
        if self.path=='/sync/respuestas':
            if not self.sync_ok(): return self.send(403,'{}','application/json')
            with LOCK: return self.send(200,json.dumps(load(RESP,{}),ensure_ascii=False),'application/json')
        if self.path=='/logo.jpg':
            b=open(os.path.join(BASE,'logo.jpg'),'rb').read(); self.send_response(200); self.send_header('Content-Type','image/jpeg'); self.send_header('Cache-Control','max-age=86400'); self.end_headers(); return self.wfile.write(b)
        if self.path=='/sync/uploads':
            if not self.sync_ok(): return self.send(403,'{}','application/json')
            return self.send(200,json.dumps(uploads_list()),'application/json')
        if self.path.startswith('/sync/upload?'):
            if not self.sync_ok(): return self.send(403,'{}','application/json')
            rel=urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('p',[''])[0]; fp=safe_upl(rel)
            if not fp or not os.path.isfile(fp): return self.send(404,'{}','application/json')
            return self.send(200,json.dumps({'p':rel,'data':base64.b64encode(open(fp,'rb').read()).decode()}),'application/json')
        p,c,t,inv=self.ctx(); resp=mig(load(RESP,{}))
        if len(p)==6 and p[3]=='doc' and ((p[1]=='a' and p[2] in inv and p[4] in {v['contact_id'] for v in c.get(inv[p[2]],[])}) or (p[1]=='admin' and p[2]==t['admin'])):
            return self.file(safe_upl(p[4]+'/'+p[5]))
        if len(p)==3 and p[1]=='a' and p[2] in inv:
            a=inv[p[2]]; l=c.get(a,[]); eq=equipos(); ld=a in eq
            body=''.join(card(v,resp,p[2],ld) for v in l) or '<p>¡No tienes clientes pendientes! 🎉</p>'
            if ld:
                pend=[v for m in eq[a] for v in c.get(m,[]) if actual(v,resp.get(v['contact_id'],{})).get('situacion')=='Reserva firmada']
                if pend: body=f"<h2 style='color:#E76108'>Cierres por reportar de tu equipo ({len(pend)})</h2>"+''.join(f"<div class='card ok'><div class=n>{html.escape(v.get('nombre') or 'Cliente')}</div><div class=meta>Asesor: {html.escape(v.get('asesor') or '')} · Negociación · Reserva firmada</div><div class=inm>🏠 {html.escape(inmueble(v)[0] or '')}</div>{cierre_btn(v)}</div>" for v in pend)+'<h2>Tus clientes</h2>'+body
            return self.send(200,page(a,f"Hola, {html.escape(a.split()[0])}. Tienes {len(l)} cliente(s) por actualizar. Cuéntanos la situación de cada uno.",body))
        if len(p)==3 and p[1]=='admin' and p[2]==t['admin']:
            import panel; return self.send(200,panel.render(page,resp,t['admin']))
        self.send(404,page('No encontrado','Enlace no válido','<p>Este enlace no es válido.</p>'))
    def do_POST(self):
        if self.path=='/sync/data':
            if not (REMOTE and self.sync_ok()): return self.send(403,'{}','application/json')
            try: d=json.loads(self.rfile.read(min(int(self.headers.get('Content-Length',0)),50_000_000)))
            except Exception: return self.send(400,'{}','application/json')
            with LOCK:
                for key,path in [('registro',REG),('config',CFG),('tokens',TOK),('inmuebles',INMP),('equipos',EQP)]:
                    if key in d: _wj(path,d[key])
                if 'respuestas' in d: _wj(RESP,merge_resp(d['respuestas'],load(RESP,{})))
                for rel,b in (d.get('uploads') or {}).items(): save_upl(rel,base64.b64decode(b))
            return self.send(200,'{"ok":true}','application/json')
        p,c,t,inv=self.ctx()
        if not(len(p)==4 and p[1]=='a' and p[2] in inv and p[3]=='guardar'): return self.send(404,'{}','application/json')
        a=inv[p[2]]
        try: d=json.loads(self.rfile.read(min(int(self.headers.get('Content-Length',0)),15_000_000)))
        except Exception: return self.send(400,'{}','application/json')
        if d.get('id') not in {v['contact_id'] for v in c.get(a,[])}: return self.send(400,'{"error":"Cliente no válido"}','application/json')
        err=validar(d)
        if err: return self.send(400,json.dumps({'error':err},ensure_ascii=False),'application/json')
        es=d['estado']; now=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
        rec={'asesor':a,'estado':es,'at':now}
        if SITS.get(es): rec['situacion']=d['situacion'].strip()
        sd=sit_def(es,rec.get('situacion'))
        if sd and sd[1] and re.match(r'^\d{4}-\d{2}-\d{2}$',(d.get('fecha') or '')[:10]): rec['fecha']=d['fecha'][:10]
        if ESTADOS[es].get('motivo'): rec['motivo']=d['motivo'].strip()[:500]
        if (d.get('comentario') or '').strip(): rec['comentario']=d['comentario'].strip()[:2000]
        with LOCK:
            r=load(RESP,{}); old=conv_full(r.get(d['id']))
            if rec.get('situacion')=='Reserva firmada':
                doc=d.get('doc')
                if isinstance(doc,dict) and doc.get('data'):
                    ext=os.path.splitext(doc.get('name') or '')[1].lower()
                    if ext not in DOC_EXT: return self.send(400,'{"error":"Solo PDF o imagen"}','application/json')
                    try: raw=base64.b64decode(doc['data'])
                    except Exception: return self.send(400,'{"error":"Archivo inválido"}','application/json')
                    if len(raw)>DOC_MAX: return self.send(400,'{"error":"El documento pasa de 10 MB"}','application/json')
                    nm=re.sub(r'[^A-Za-z0-9._-]+','-',os.path.basename(doc.get('name') or 'reserva'))[-80:] or 'reserva'+ext
                    rel=d['id']+'/'+now[:19].replace(':','').replace('-','')+'_'+nm; save_upl(rel,raw); rec['doc']=rel
                elif old.get('doc'): rec['doc']=old['doc']
            if old:
                h=old.pop('historial',[]) or []; rec['historial']=(h+[old])[-10:]
            r[d['id']]=rec; _wj(RESP,r)
            if rec.get('situacion')=='Reserva firmada' and old.get('situacion')!='Reserva firmada':
                ld=lider_de(a); v=next(x for x in c[a] if x['contact_id']==d['id'])
                ob=load(OUTBOX,[]); ob.append({'cliente_id':d['id'],'cliente':v.get('nombre') or '','asesor':a,'lider':ld or '(sin líder asignado)','url':cierre_url(v),'at':now,'enviado':False}); _wj(OUTBOX,ob)
        self.send(200,'{"ok":true}','application/json')
    def log_message(self,*a): pass
if __name__=='__main__':
    if REMOTE: ThreadingHTTPServer(('0.0.0.0',PORT),H).serve_forever()
    c=clientes(); t=tokens(c.keys())
    with open(os.path.join(BASE,'enlaces.txt'),'w') as f:
        f.write("BASE = URL pública (ver url_publica.txt) o http://127.0.0.1:%d\n\nADMIN: BASE/admin/%s\n\n"%(PORT,t['admin']))
        for a,l in sorted(c.items(),key=lambda x:-len(x[1])): f.write(f"{a} ({len(l)}): BASE/a/{t['asesores'][a]}\n")
    ThreadingHTTPServer(('0.0.0.0',PORT),H).serve_forever()
