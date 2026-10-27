"""Panel admin de José (solo lectura)."""
import json, html
from app import load, REG, CFG, PAUSA, norm, inmueble, fecha, ESTATUS
def datos(resp):
    r=load(REG,{}).get('clientes',{}); cf=load(CFG,{}); ex=set(cf.get('excluir_contactos',[]))
    exa={norm(a) for a in cf.get('excluir_asesores',[])}-PAUSA
    out=[]
    for k,v in r.items():
        if k in ex or norm(v.get('asesor')) in exa: continue
        t,cod=inmueble(v); rr=resp.get(k,{})
        extra=' · '.join(x for x in [('Visita: '+rr['fecha_visita'].replace('T',' ')) if rr.get('fecha_visita') else '', rr.get('interes',''),
              (f"US$ {rr['monto']:,.0f}".replace(',','.')) if rr.get('monto') else '', rr.get('motivo','')] if x)
        out.append(dict(id=k,n=v.get('nombre') or 'Cliente',a=v.get('asesor') or 'Sin asesor',p=norm(v.get('asesor')) in PAUSA,
            tl=v.get('tipo_lead') or '',f=fecha(v.get('asignado_at')),fs=v.get('asignado_at') or '',inm=t,cod=cod,
            e=rr.get('estatus') or 'Sin estatus',tg=(v.get('estado') or '').capitalize(),x=extra,s=rr.get('situacion',''),at=rr.get('at',''),
            cer=bool(v.get('cerrado')),ok=bool(rr) or (v.get('estado') or '')!='ASIGNADO' or bool(v.get('cerrado')),h=[dict(e=o.get('estatus'),s=o.get('situacion',''),at=o.get('at','')) for o in rr.get('historial',[])]))
    return out
CSS="""main{max-width:1240px!important}
.wrap{max-width:1200px;margin:0 auto;padding:12px}.kp{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:10px}
.k{background:#fff;border-radius:12px;padding:12px;box-shadow:0 1px 5px rgba(0,0,0,.07);cursor:pointer;border-top:4px solid #e5e7eb}
.k b{display:block;font-size:26px}.k span{font-size:12px;color:#555}.k.big{border-top-color:#E76108;background:#111;color:#fff}.k.big span{color:#ddd}.k.on{outline:2px solid #E76108}
.bar{height:8px;background:#eee;border-radius:5px;overflow:hidden}.bar i{display:block;height:100%;background:#E76108}
.f{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}.f>*{flex:1 1 180px;width:auto;margin:0}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden;font-size:13px}th{background:#111;color:#fff;cursor:pointer;white-space:nowrap}
th,td{padding:8px;border-bottom:1px solid #eee;text-align:left}tr.as{cursor:pointer}tr.pz-row{opacity:.6}tr.as:hover,tr.sel{background:#fff3ea}.tw{overflow-x:auto}.chip{display:inline-block;background:#fff3ea;color:#9a3d04;border-radius:5px;padding:1px 6px;font-size:11px;margin:1px;white-space:nowrap}.chip.no{background:#f1f1f1;color:#555}
.pz{background:#fde68a;color:#78350f;border-radius:6px;padding:1px 6px;font-size:11px;margin-left:4px}.est{display:inline-block;border-radius:6px;padding:2px 8px;font-size:12px;background:#E76108;color:#fff}
.est.no{background:#e5e7eb;color:#333}.cl{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px;margin-top:10px}
.c{background:#fff;border-radius:12px;padding:12px;border-left:5px solid #E76108;box-shadow:0 1px 5px rgba(0,0,0,.07);font-size:14px}.c.no{border-left-color:#ccc}
.m{color:#666;font-size:12px}.cod{background:#111;color:#fff;border-radius:5px;padding:1px 6px;font-size:11px}details{font-size:12px;color:#555;margin-top:6px}h2{font-size:17px;margin:20px 0 6px}"""
JS=r"""
const E=__EST__,ALL=__DATA__,D=ALL.filter(d=>!d.cer);let fe='',fa='',q='',sk='rank',sd=1;const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function kp(){const all=D.length,con=D.filter(d=>d.e!='Sin estatus').length;let h=`<div class="k big" onclick="se('')"><b>${Math.round(100*con/all)}%</b><span>con estatus (${con} de ${all})</span><div class=bar><i style="width:${100*con/all}%"></i></div></div>`;
for(const e of ['Sin estatus',...E]){const n=D.filter(d=>d.e==e).length;h+=`<div class="k ${fe==e?'on':''}" onclick="se('${e}')"><b>${n}</b><span>${e}</span></div>`}$('#kp').innerHTML=h}
function se(e){fe=fe==e?'':e;$('#fe').value=fe;go()}
function rows(){const m={};for(const d of ALL){const r=m[d.a]??={a:d.a,p:d.p,tot:0,ab:0,sin:0,con:0,ult:'',c:{}};r.tot++;d.ok?r.con++:r.sin++;if(!d.cer){r.ab++;r.c[d.e]=(r.c[d.e]||0)+1}if(d.at>r.ult)r.ult=d.at}
const L=Object.values(m);L.forEach(r=>r.pct=Math.round(100*r.con/r.tot));L.sort((x,y)=>(x.p-y.p)||(y.pct-x.pct)||(x.sin-y.sin)||x.a.localeCompare(y.a));L.forEach((r,i)=>r.rank=i+1);if(sk!='rank')L.sort((x,y)=>(x.p-y.p)||(x[sk]>y[sk]?1:x[sk]<y[sk]?-1:0)*sd);return L}
function srt(k){sd=sk==k?-sd:-1;sk=k;tab()}
function tab(){let h='<tr>'+[['rank','#'],['a','Asesor'],['tot','Total'],['ab','Abiertos'],['con','Con estatus'],['sin','Sin estatus'],['pct','% seguimiento'],['ult','Última act. página']].map(([k,t])=>`<th onclick="srt('${k}')">${t}${sk==k?(sd>0?' ▲':' ▼'):''}</th>`).join('')+'<th>Estatus en página (abiertos)</th></tr>';
for(const r of rows())h+=`<tr class="as ${fa==r.a?'sel':''} ${r.p?'pz-row':''}" onclick="sa('${esc(r.a)}')"><td><b style="font-size:16px;color:#E76108">${r.p?'—':r.rank}</b></td><td style="white-space:nowrap"><b>${esc(r.a)}</b>${r.p?'<span class=pz>en pausa</span>':''}</td><td>${r.tot}</td><td>${r.ab}</td><td>${r.con}</td><td>${r.sin}</td><td><div style="display:flex;align-items:center;gap:6px;min-width:150px"><div class=bar style="flex:1"><i style="width:${r.pct}%"></i></div><b>${r.pct}%</b></div></td><td>${r.ult?r.ult.slice(0,16).replace('T',' '):'—'}</td>`+'<td>'+Object.entries(r.c).map(([e,n])=>`<span class="chip ${e=='Sin estatus'?'no':''}">${esc(e)} ${n}</span>`).join(' ')+'</td></tr>';$('#tb').innerHTML=h}
function sa(a){fa=fa==a?'':a;$('#fa').value=fa;go();$('#cl').scrollIntoView({behavior:'smooth'})}
function cl(){const L=D.filter(d=>(!fe||d.e==fe)&&(!fa||d.a==fa)&&(!q||d.n.toLowerCase().includes(q)));L.sort((x,y)=>x.a.localeCompare(y.a)||x.fs.localeCompare(y.fs));
$('#ct').textContent=`${L.length} cliente(s)`+(fa?' · '+fa:'')+(fe?' · '+fe:'');
$('#cl').innerHTML=L.map(d=>`<div class="c ${d.e=='Sin estatus'?'no':''}"><b>${esc(d.n)}</b> <span class="est ${d.e=='Sin estatus'?'no':''}">${esc(d.e)}</span>
<div class=m>${esc(d.a)}${d.p?' <span class=pz>en pausa</span>':''}${d.tl?' · '+esc(d.tl):''}${d.f?' · Asignado '+d.f:''}</div>
<div style="margin:6px 0">🏠 ${esc(d.inm)||(d.cod?'Inmueble':'Sin inmueble específico')} ${d.cod?'<span class=cod>'+esc(d.cod)+'</span>':''}</div>
${d.x?'<div><b>'+esc(d.x)+'</b></div>':''}${d.s?'<div>📝 '+esc(d.s)+'</div>':''}
${d.e=='Sin estatus'?'<div class=m>Seguimiento Telegram: '+esc(d.tg)+'</div>':'<div class=m>Actualizado '+d.at.slice(0,16).replace('T',' ')+' · Telegram: '+esc(d.tg)+'</div>'}
${d.h.length?'<details><summary>Historial ('+d.h.length+')</summary>'+d.h.map(h=>`<div>${h.at.slice(0,16).replace('T',' ')} · ${esc(h.e)} ${esc(h.s)}</div>`).join('')+'</details>':''}</div>`).join('')}
function go(){kp();tab();cl()}
$('#fe').innerHTML='<option value="">Todos los estatus</option>'+['Sin estatus',...E].map(e=>`<option>${e}</option>`).join('');
$('#fa').innerHTML='<option value="">Todos los asesores</option>'+[...new Set(D.map(d=>d.a))].sort().map(a=>`<option>${esc(a)}</option>`).join('');
$('#fe').onchange=e=>{fe=e.target.value;go()};$('#fa').onchange=e=>{fa=e.target.value;go()};$('#q').oninput=e=>{q=e.target.value.toLowerCase();cl()};go();"""
def render(page,resp):
    d=datos(resp); dj=json.dumps(d,ensure_ascii=False).replace('</','<\\/')
    body=f"""<style>{CSS}</style><div class=wrap><div id=kp class=kp></div><div class=f><select id=fe></select><select id=fa></select><input id=q placeholder="Buscar cliente por nombre…"></div>
<h2>Ranking por asesor</h2><div class=m style="margin:-2px 0 6px">% seguimiento = clientes con respuesta en la página o con estado de Telegram distinto de «asignado», sobre todos sus clientes del registro (incluye cerrados).</div><div class=tw><table id=tb></table></div><h2 id=ct></h2><div id=cl class=cl></div></div>
<script>{JS.replace('__EST__',json.dumps(ESTATUS,ensure_ascii=False)).replace('__DATA__',dj)}</script>"""
    return page('Panel',f"Panel de control · {len(d)} clientes abiertos",body)
