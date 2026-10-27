"""Panel admin de José (solo lectura)."""
import json, html
from app import load, REG, CFG, PAUSA, norm, inmueble, fecha, ESTATUS, ECLS, SITS, mig, desde, horas, actual, color_key, cierre_url
def datos(resp,admin=''):
    resp=mig(resp)
    r=load(REG,{}).get('clientes',{}); cf=load(CFG,{}); ex=set(cf.get('excluir_contactos',[]))
    exa={norm(a) for a in cf.get('excluir_asesores',[])}-PAUSA
    out=[]
    for k,v in r.items():
        if k in ex or norm(v.get('asesor')) in exa: continue
        t,cod=inmueble(v); rr=resp.get(k,{}); st=actual(v,rr)
        ds,dsrc=desde(v,rr); cont=st.get('estado')=='Nuevo' and st.get('situacion')=='Contactado'; hh=horas(ds) if cont else None
        out.append(dict(hc=round(hh,1) if hh is not None else None,vc=bool(hh and hh>72 and not v.get('cerrado')),dsrc=dsrc,id=k,n=v.get('nombre') or 'Cliente',a=v.get('asesor') or 'Sin asesor',p=norm(v.get('asesor')) in PAUSA,
            tl=v.get('tipo_lead') or '',f=fecha(v.get('asignado_at')),fs=v.get('asignado_at') or '',inm=t,cod=cod,
            e=st.get('estado'),si=st.get('situacion',''),fe=fecha(st.get('fecha')) if st.get('fecha') else '',mo=st.get('motivo',''),co=st.get('comentario',''),
            ck=color_key(st),cu=(cierre_url({**v,'contact_id':k}) if st.get('situacion')=='Reserva firmada' else ''),doc=(f"/admin/{admin}/doc/{rr['doc']}" if rr.get('doc') and admin else ''),
            src=st.get('src'),tg=(v.get('estado') or '').capitalize(),at=rr.get('at',''),
            cer=bool(v.get('cerrado')),ok=st.get('estado')!='Sin estatus' or bool(v.get('cerrado')),
            h=[dict(e=' · '.join(x for x in [o.get('estado'),o.get('situacion'),fecha(o.get('fecha')) if o.get('fecha') else '',o.get('motivo')] if x),s=o.get('comentario',''),at=o.get('at','')) for o in rr.get('historial',[])]))
    return out
CSS="""main{max-width:1240px!important}
.wrap{max-width:1200px;margin:0 auto;padding:12px}.kp{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:10px}
td.vx{background:#fee2e2;color:#b91c1c;font-weight:bold}.vb{display:inline-block;background:#dc2626;color:#fff;border-radius:6px;padding:1px 7px;font-size:11px;font-weight:bold;margin-left:4px}.k.alr{background:#dc2626;color:#fff;border-top-color:#7f1d1d}.k.alr span{color:#fee2e2}
.k{background:#fff;border-radius:12px;padding:12px;box-shadow:0 1px 5px rgba(0,0,0,.07);cursor:pointer;border-top:4px solid #e5e7eb}
.k b{display:block;font-size:26px}.k span{font-size:12px;color:#555}.k.big{border-top-color:#E76108;background:#111;color:#fff}.k.big span{color:#ddd}.k.on{outline:2px solid #E76108}
.bar{height:8px;background:#eee;border-radius:5px;overflow:hidden}.bar i{display:block;height:100%;background:#E76108}
.f{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}.f>*{flex:1 1 180px;width:auto;margin:0}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden;font-size:13px}th{background:#111;color:#fff;cursor:pointer;white-space:nowrap}
th,td{padding:8px;border-bottom:1px solid #eee;text-align:left}tr.as{cursor:pointer}tr.pz-row{opacity:.6}tr.as:hover,tr.sel{background:#fff3ea}.tw{overflow-x:auto}.chip{display:inline-block;background:#fff3ea;color:#9a3d04;border-radius:5px;padding:1px 6px;font-size:11px;margin:1px;white-space:nowrap}.chip.no{background:#f1f1f1;color:#555}
.pz{background:#fde68a;color:#78350f;border-radius:6px;padding:1px 6px;font-size:11px;margin-left:4px}.est{display:inline-block;border-radius:6px;padding:2px 8px;font-size:12px;background:#E76108;color:#fff}
.est.no{background:#e5e7eb;color:#333}.cl{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px;margin-top:10px}
.c{background:#fff;border-radius:12px;padding:12px;border-left:5px solid #E76108;box-shadow:0 1px 5px rgba(0,0,0,.07);font-size:14px}.c.no{border-left-color:#ccc}
.m{color:#666;font-size:12px}.cod{background:#111;color:#fff;border-radius:5px;padding:1px 6px;font-size:11px}details{font-size:12px;color:#555;margin-top:6px}h2{font-size:17px;margin:20px 0 6px}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px;vertical-align:middle;border:1px solid rgba(0,0,0,.15)}.k.on{outline:3px solid #111}.sb{font-size:11px;color:#333;margin-top:3px;cursor:pointer}"""
JS=r"""
const E=__EST__,SI=__SITS__,ec=e=>' e'+EC[e],bc=e=>' b'+EC[e],ALL=__DATA__,D=ALL.filter(d=>!d.cer);const hx=h=>h<48?Math.round(h)+'h':Math.floor(h/24)+' días';let fvv=false,fsi='',fe='',fa='',q='',sk='rank',sd=1;const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function kp(){const all=D.length,con=D.filter(d=>d.e!='Sin estatus').length;let h=`<div class="k big" onclick="se('')"><b>${Math.round(100*con/all)}%</b><span>con estatus (${con} de ${all})</span><div class=bar><i style="width:${100*con/all}%"></i></div></div>`;
const nv=D.filter(d=>d.vc).length;h+=`<div class="k alr ${fvv?'on':''}" onclick="tv()"><b>${nv}</b><span>⚠ Contactado vencido (+72h)</span></div>`;
for(const e of ['Sin estatus',...E]){const X=D.filter(d=>d.e==e),n=X.length;const br=(SI[e]||[]).map(si=>{const m=X.filter(d=>d.si==si).length;return `<div class=sb onclick="event.stopPropagation();ss('${e}','${si}')" style="${fsi==si?'font-weight:bold;text-decoration:underline':''}"><i class="dot${ec(si)}"></i>${si}: <b>${m}</b></div>`}).join('');h+=`<div class="k${bc(e)} ${fe==e&&!fsi?'on':''}" style="border-top-width:8px" onclick="se('${e}')"><b>${n}</b><span><i class="dot${ec(e)}"></i>${e}</span>${br}</div>`}$('#kp').innerHTML=h}
function tv(){fvv=!fvv;$('#fvv').checked=fvv;go()}
function ss(e,si){fsi=fsi==si?'':si;fe=fsi?e:fe;$('#fe').value=fe;go()}
function se(e){fe=fe==e&&!fsi?'':e;fsi='';$('#fe').value=fe;go()}
function rows(){const m={};for(const d of ALL){const r=m[d.a]??={a:d.a,p:d.p,tot:0,ab:0,sin:0,con:0,vc:0,ult:'',c:{}};r.tot++;d.ok?r.con++:r.sin++;if(!d.cer){r.ab++;if(d.vc)r.vc++;r.c[d.e]=(r.c[d.e]||0)+1}if(d.at>r.ult)r.ult=d.at}
const L=Object.values(m);L.forEach(r=>r.pct=Math.round(100*r.con/r.tot));L.sort((x,y)=>(y.pct-x.pct)||(x.sin-y.sin)||x.a.localeCompare(y.a));L.forEach((r,i)=>r.rank=i+1);if(sk!='rank')L.sort((x,y)=>(x[sk]>y[sk]?1:x[sk]<y[sk]?-1:0)*sd);return L}
function srt(k){sd=sk==k?-sd:-1;sk=k;tab()}
function tab(){let h='<tr>'+[['rank','#'],['a','Asesor'],['tot','Total'],['ab','Abiertos'],['con','Con estatus'],['sin','Sin estatus'],['pct','% seguimiento'],['vc','Vencidos +72h'],['ult','Última act. página']].map(([k,t])=>`<th onclick="srt('${k}')">${t}${sk==k?(sd>0?' ▲':' ▼'):''}</th>`).join('')+'<th>Estados (abiertos)</th></tr>';
for(const r of rows())h+=`<tr class="as ${fa==r.a?'sel':''} " onclick="sa('${esc(r.a)}')"><td><b style="font-size:16px;color:#E76108">${r.rank}</b></td><td style="white-space:nowrap"><b>${esc(r.a)}</b>${r.p?'<span class=pz>pausada de asignaciones</span>':''}</td><td>${r.tot}</td><td>${r.ab}</td><td>${r.con}</td><td>${r.sin}</td><td><div style="display:flex;align-items:center;gap:6px;min-width:150px"><div class=bar style="flex:1"><i style="width:${r.pct}%"></i></div><b>${r.pct}%</b></div></td><td class="${r.vc?'vx':''}" style="text-align:center">${r.vc||'·'}</td><td>${r.ult?r.ult.slice(0,16).replace('T',' '):'—'}</td>`+'<td>'+Object.entries(r.c).sort((x,y)=>EC[x[0]]-EC[y[0]]).map(([e,n])=>`<span class="chip${ec(e)}">${esc(e)} ${n}</span>`).join(' ')+'</td></tr>';$('#tb').innerHTML=h}
function mx(){const S=['Sin estatus',...E],L=rows().slice().sort((x,y)=>x.rank-y.rank),T={};let h='<tr><th>Asesor</th>'+S.map(e=>`<th class="${ec(e)}" style="white-space:normal;min-width:78px;font-size:11px">${e}</th>`).join('')+'<th style="background:#dc2626">Vencidos +72h</th><th>Total</th></tr>';let TV=0;
for(const r of L){let t=0;h+=`<tr><td style="white-space:nowrap"><b>${esc(r.a)}</b></td>`+S.map(e=>{const n=r.c[e]||0;t+=n;T[e]=(T[e]||0)+n;return `<td style="text-align:center;cursor:${n?'pointer':'default'}" onclick="fx('${esc(r.a)}','${e}')">${n?'<b>'+n+'</b>':'<span style=color:#bbb>·</span>'}</td>`}).join('')+`<td class="${r.vc?'vx':''}" style="text-align:center;cursor:pointer" onclick="fx('${esc(r.a)}','',1)">${r.vc||'·'}</td><td style="text-align:center"><b>${t}</b></td></tr>`;TV+=r.vc}
h+='<tr style="background:#f4f4f5"><td><b>Total</b></td>'+S.map(e=>`<td style="text-align:center;cursor:pointer" onclick="fx('','${e}')"><b>${T[e]||0}</b></td>`).join('')+`<td class=vx style="text-align:center;cursor:pointer" onclick="fx('','',1)">${TV}</td><td style="text-align:center"><b>${D.length}</b></td></tr>`;$('#mx').innerHTML=h}
function fx(a,e,v){fa=a;fe=e;fsi='';fvv=!!v;$('#fvv').checked=fvv;$('#fa').value=fa;$('#fe').value=fe;go();$('#cl').scrollIntoView({behavior:'smooth'})}
function sa(a){fa=fa==a?'':a;$('#fa').value=fa;go();$('#cl').scrollIntoView({behavior:'smooth'})}
function cl(){const L=D.filter(d=>(!fvv||d.vc)&&(!fe||d.e==fe)&&(!fsi||d.si==fsi)&&(!fa||d.a==fa)&&(!q||d.n.toLowerCase().includes(q)));L.sort((x,y)=>x.a.localeCompare(y.a)||x.fs.localeCompare(y.fs));
$('#ct').textContent=`${L.length} cliente(s)`+(fa?' · '+fa:'')+(fe?' · '+fe:'')+(fsi?' · '+fsi:'')+(fvv?' · Vencidos +72h':'');
$('#cl').innerHTML=L.map(d=>`<div class="c${bc(d.ck)}"><b>${esc(d.n)}</b> <span class="est${ec(d.ck)}">${esc(d.e)}${d.si?' · '+esc(d.si):''}${d.fe?' ('+d.fe+')':''}${d.src=='tg'&&d.e!='Sin estatus'?' (Telegram)':''}</span>${d.vc?'<span class=vb>Vencido +72h</span>':''}
${d.hc!=null?`<div class=m style="color:${d.vc?'#b91c1c':'#666'};font-weight:${d.vc?'bold':'normal'}">Contactado hace ${hx(d.hc)}${d.dsrc=='asignacion'?' (desde asignación)':d.dsrc=='primer_contacto'?' (desde primer contacto)':''}</div>`:''}
<div class=m>${esc(d.a)}${d.p?' <span class=pz>pausada de asignaciones</span>':''}${d.tl?' · '+esc(d.tl):''}${d.f?' · Asignado '+d.f:''}</div>
<div style="margin:6px 0">🏠 ${esc(d.inm)||(d.cod?'Inmueble':'Sin inmueble específico')} ${d.cod?'<span class=cod>'+esc(d.cod)+'</span>':''}</div>
${d.mo?'<div><b>Motivo:</b> '+esc(d.mo)+'</div>':''}${d.co?'<div>📝 '+esc(d.co)+'</div>':''}${d.doc?'<div>📎 <a href="'+esc(d.doc)+'" target=_blank>Documento de reserva</a></div>':''}${d.cu?'<div><a class=cierre href="'+esc(d.cu)+'" target=_blank'+(d.cu=='#'?' onclick="alert(\'Próximamente — Sistema Contable de For Rent\');return false"':'')+'>Reportar Cierre</a></div>':''}
${d.src=='tg'?'<div class=m>Seguimiento Telegram: '+esc(d.tg)+'</div>':'<div class=m>Actualizado '+d.at.slice(0,16).replace('T',' ')+' · Telegram: '+esc(d.tg)+'</div>'}
${d.h.length?'<details><summary>Historial ('+d.h.length+')</summary>'+d.h.map(h=>`<div>${h.at.slice(0,16).replace('T',' ')} · ${esc(h.e)} ${esc(h.s)}</div>`).join('')+'</details>':''}</div>`).join('')}
function go(){kp();tab();mx();cl()}
$('#fe').innerHTML='<option value="">Todos los estados</option>'+['Sin estatus',...E].map(e=>`<option>${e}</option>`).join('');
$('#fa').innerHTML='<option value="">Todos los asesores</option>'+[...new Set(D.map(d=>d.a))].sort().map(a=>`<option>${esc(a)}</option>`).join('');
$('#fe').onchange=e=>{fe=e.target.value;go()};$('#fa').onchange=e=>{fa=e.target.value;go()};$('#fvv').onchange=e=>{fvv=e.target.checked;go()};$('#q').oninput=e=>{q=e.target.value.toLowerCase();cl()};go();"""
def render(page,resp,admin=''):
    d=datos(resp,admin); dj=json.dumps(d,ensure_ascii=False).replace('</','<\\/')
    body=f"""<style>{CSS}</style><div class=wrap><div id=kp class=kp></div><div class=f><select id=fe></select><select id=fa></select><label style="display:flex;align-items:center;gap:6px;background:#fee2e2;color:#991b1b;border-radius:8px;padding:6px 10px;font-weight:bold;flex:0 1 auto"><input type=checkbox id=fvv style="width:auto;margin:0"> Solo vencidos +72h</label><input id=q placeholder="Buscar cliente por nombre…"></div>
<div class=m>Regla: un cliente en «Nuevo · Contactado» tiene 72 horas para pasar a En proceso (visita agendada/realizada), En espera, Negociación o Perdido. El tiempo se cuenta desde que entró a Contactado (página del asesor, o cambio de estado en Telegram).</div><h2>Ranking por asesor</h2><div class=m style="margin:-2px 0 6px">% seguimiento = clientes con algún estado (página o Telegram), sobre todos sus clientes del registro (incluye cerrados).</div><div class=tw><table id=tb></table></div><h2>Clientes por estatus por asesor</h2><div class=m style="margin:-2px 0 6px">Clientes abiertos. Toca un número para ver esos clientes.</div><div class=tw><table id=mx></table></div><h2 id=ct></h2><div id=cl class=cl></div></div>
<script>{JS.replace('__EST__',json.dumps(ESTATUS,ensure_ascii=False)).replace('__SITS__',json.dumps(SITS,ensure_ascii=False)).replace('__DATA__',dj)}</script>"""
    return page('Panel',f"Panel de control · {len(d)} clientes abiertos",body)
