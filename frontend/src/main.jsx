import React, {useState, useEffect, useRef} from 'react'
import {createRoot} from 'react-dom/client'
import {Package, LayoutDashboard, Boxes, ArrowDownToLine, ArrowUpFromLine, History, Tags, Truck, Users, Search, Plus, ArrowRight, ArrowLeft, ChevronRight, LogOut, X, Check, AlertTriangle, Pencil, Trash2, Menu, ShieldCheck, Layers, Eye, EyeOff, LoaderCircle, Warehouse, ClipboardList, DatabaseBackup} from 'lucide-react'
import {api, setCsrf, query, allProducts} from './api'
import {money, num, date, useData, Loading, ErrorBox, Empty, DataState, Field, Heading, PageNav, Modal} from './ui'
import {Warehouses, Documents, DataExchange, movementLabels} from './warehouse'
import './styles.css'
import './warehouse.css'

const roles = {admin:'Адміністратор', keeper:'Комірник', manager:'Менеджер'}
function go(path) { location.hash = path }
function useRoute() {
  const [route, setRoute] = useState(location.hash.slice(1) || 'dashboard')
  useEffect(() => { const handle = () => setRoute(location.hash.slice(1) || 'dashboard'); window.addEventListener('hashchange', handle); return () => window.removeEventListener('hashchange', handle) }, [])
  return route.split('/')
}
function Badge({product}) { return <span className={'badge ' + (product.quantity === 0 ? 'red' : product.low_stock ? 'amber' : 'green')}><span className="dot"/>{product.quantity === 0 ? 'Немає на складі' : product.low_stock ? 'Низький залишок' : 'В наявності'}</span> }
function EntityForm({kind, initial, categories=[], suppliers=[], onClose, onSaved}) {
  const defaults = kind === 'products' ? {name:'', sku:'', category_id:categories[0]?.id || '', supplier_id:'', price:'0', min_stock:5, unit:'шт.'} : kind === 'users' ? {name:'', email:'', password:'', role:'keeper', active:true} : {name:'', phone:'', email:''}
  const [form, setForm] = useState({...defaults, ...initial})
  const [error, setError] = useState(''), [busy, setBusy] = useState(false)
  const update = e => setForm({...form, [e.target.name]:e.target.type === 'checkbox' ? e.target.checked : e.target.value})
  const input = (name, type='text', attrs={}) => <input name={name} type={type} value={form[name] ?? ''} onChange={update} {...attrs}/>
  const titles = {products:'товар', categories:'категорію', suppliers:'постачальника', users:'користувача'}
  async function save(e) {
    e.preventDefault(); setError(''); setBusy(true)
    try { await api('/' + kind + (initial?.id ? '/' + initial.id : ''), {method:initial?.id ? 'PUT' : 'POST', body:form}); onSaved(initial?.id ? 'Зміни збережено.' : 'Запис створено.'); onClose() } catch(e) {setError(e.message)} finally {setBusy(false)}
  }
  return <Modal title={(initial?.id ? 'Редагувати ' : 'Додати ') + titles[kind]} onClose={onClose}><form onSubmit={save}><div className="form-body"><ErrorBox message={error}/><Field label="Назва / ім’я">{input('name','text',{required:true,maxLength:kind === 'products' ? 200 : 100})}</Field>
    {kind === 'products' && <><div className="form-grid"><Field label="Артикул (SKU)">{input('sku','text',{required:true,maxLength:50,pattern:'[A-Za-z0-9][A-Za-z0-9._-]*',placeholder:'SSD-480'})}</Field><Field label="Одиниця виміру">{input('unit','text',{required:true,maxLength:20})}</Field></div><Field label="Категорія"><select name="category_id" value={form.category_id} onChange={update} required><option value="">Оберіть категорію</option>{categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field><Field label="Постачальник"><select name="supplier_id" value={form.supplier_id || ''} onChange={update}><option value="">Не вказано</option>{suppliers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field><div className="form-grid"><Field label="Ціна, грн">{input('price','number',{required:true,min:0,step:0.01,max:10000000})}</Field><Field label="Мінімальний залишок">{input('min_stock','number',{required:true,min:0,step:1,max:1000000000})}</Field></div>{!initial?.id && <p className="muted">Новий товар має нульовий залишок. Додайте кількість через надходження.</p>}</>}
    {(kind === 'users' || kind === 'suppliers') && <Field label="Електронна адреса">{input('email','email',{required:kind === 'users',maxLength:200})}</Field>}
    {kind === 'suppliers' && <Field label="Телефон">{input('phone','tel',{maxLength:40})}</Field>}
    {kind === 'users' && <><Field label={initial?.id ? 'Новий пароль (необов’язково)' : 'Пароль'}>{input('password','password',{required:!initial?.id,minLength:8,maxLength:256,autoComplete:'new-password'})}</Field><Field label="Роль"><select name="role" value={form.role} onChange={update}>{Object.entries(roles).map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select></Field>{initial?.id && <label className="checkbox"><input type="checkbox" name="active" checked={form.active} onChange={update}/>Активний обліковий запис</label>}</>}
    </div><div className="modal-footer"><button className="btn" type="button" onClick={onClose}>Скасувати</button><button className="btn primary" disabled={busy}>{busy ? <LoaderCircle className="spin" size={16}/> : <Check size={16}/>}Зберегти</button></div></form></Modal>
}
function Confirm({kind, item, onClose, onSaved}) {
  const [error,setError] = useState(''), [busy,setBusy] = useState(false)
  async function remove() {setBusy(true); try {const result=await api(`/${kind}/${item.id}`,{method:'DELETE'});onSaved(result.message);onClose()} catch(e) {setError(e.message)} finally {setBusy(false)}}
  return <Modal title={kind === 'products' ? 'Архівувати товар?' : 'Видалити запис?'} onClose={onClose}><div className="form-body"><p>«{item.name}»</p><p className="muted">{kind === 'products' ? 'Історія операцій залишиться доступною. Архівація можлива лише при нульовому залишку на всіх складах.' : 'Видалення можливе, якщо запис не використовується іншими даними.'}</p><ErrorBox message={error}/></div><div className="modal-footer"><button className="btn" onClick={onClose}>Скасувати</button><button className="btn danger" disabled={busy} onClick={remove}>{kind === 'products' ? 'Архівувати' : 'Видалити'}</button></div></Modal>
}
function MovementTable({items, compact=false}) {
  if (!items.length) return <Empty title="Операцій ще немає" text="Проведені зміни залишків з’являться тут."/>
  return <div className="table-scroll"><table>
    <thead><tr><th>Товар</th><th>Операція</th><th className="right">Кількість</th>{!compact && <th className="right">Залишок після</th>}<th>Автор</th><th>Дата</th>{!compact && <th>Коментар</th>}</tr></thead>
    <tbody>{items.map(m => {
      const inbound = m.delta > 0, style = inbound ? 'receipt' : 'writeoff'
      return <tr key={m.id}>
        <td><button className="text-button product-name" onClick={() => go('products/' + m.product_id)}>{m.product}</button>
          <small className="sku">{m.sku} · {m.warehouse}</small>
          {m.document_id ? <a className="phase-link" href={'#documents/' + m.document_id}>СК-{String(m.document_id).padStart(6, '0')}</a> : m.receipt_id ? <small className="sku">НД-{String(m.receipt_id).padStart(4, '0')}</small> : null}</td>
        <td><span className={'movement-type ' + style}>{inbound ? <ArrowDownToLine size={14}/> : <ArrowUpFromLine size={14}/>}<span>{movementLabels[m.type]}</span></span></td>
        <td className={'right amount ' + style}>{inbound ? '+' : '−'}{num(m.quantity)}</td>
        {!compact && <td className="right">{num(m.balance_after)}</td>}
        <td><div className="author"><span className="tiny-avatar">{m.author[0]}</span>{m.author}</div></td>
        <td className="nowrap muted">{date(m.created_at)}</td>{!compact && <td className="note-cell">{m.note || '—'}</td>}
      </tr>
    })}</tbody>
  </table></div>
}
function Dashboard({revision,user,warehouseId,warehouseName}) {
  const resource = useData(() => api('/dashboard' + query({warehouse_id:warehouseId})), [warehouseId, revision])
  return <><Heading title="Огляд складу" description={warehouseName + ' · Залишки та останні зміни'} action={user.role !== 'manager' && <button className="btn primary" onClick={() => go('receipt')}><Plus size={17}/>Нове надходження</button>}/><DataState resource={resource}>{d => <><div className="stats-grid">{[[Boxes,'Товарних позицій',num(d.products),'У вашому каталозі',''],[Layers,'Одиниць на складі',num(d.units),'Актуальний залишок',''],[Package,'Вартість запасів',money(d.value),'За поточними цінами',''],[AlertTriangle,'Потребують поповнення',num(d.low_count),'На рівні мінімуму або нижче','warning']].map(([Icon,label,value,caption,cls]) => <div className={'stat-card ' + cls} key={label}><div className="stat-label">{label}<Icon size={19}/></div><strong>{value}</strong><small>{caption}</small></div>)}</div><div className="dashboard-grid"><section className="panel activity-panel"><div className="panel-title"><div><h2>Рух товарів</h2><p>Надходження та списання за останні 7 днів · UTC</p></div><span className="period">7 днів</span></div><div className="legend"><span><i className="receipt-dot"/>Надходження</span><span><i className="writeoff-dot"/>Списання</span></div><div className="bar-chart" role="img" aria-label="Рух товарів за 7 днів">{d.activity.map(day => {const maximum=Math.max(1,...d.activity.flatMap(x=>[x.receipt,x.writeoff]));return <div className="chart-column" key={day.date}><div className="bar-pair"><div className="bar receipt-bar" title={`Надходження: ${day.receipt}`} style={{height:`${day.receipt/maximum*100}%`}}><span>{day.receipt || ''}</span></div><div className="bar writeoff-bar" title={`Списання: ${day.writeoff}`} style={{height:`${day.writeoff/maximum*100}%`}}><span>{day.writeoff || ''}</span></div></div><small>{new Date(day.date+'T12:00:00Z').toLocaleDateString('uk-UA',{weekday:'short',timeZone:'UTC'})}</small></div>})}</div></section><section className="panel low-panel"><div className="panel-title"><div><h2>Час поповнити</h2><p>Товари з низьким залишком</p></div><span className="count-pill">{d.low_count}</span></div>{d.low_products.length ? <div className="low-list">{d.low_products.map(p => <button key={p.id} onClick={() => go('products/' + p.id)}><span className="product-icon"><Package size={19}/></span><span className="low-info"><strong>{p.name}</strong><small>{p.sku} · мін. {p.min_stock}</small></span><span className={'low-number '+(!p.quantity?'red-text':'')}>{p.quantity}<small>{p.unit}</small></span></button>)}</div> : <Empty title="Запасів достатньо" text="Усі товари вище мінімального залишку."/>}<button className="panel-link" onClick={() => go('products?low')}>Переглянути товари<ArrowRight size={16}/></button></section></div><section className="panel"><div className="panel-title"><div><h2>Останні операції</h2><p>Історія змін вашого складу</p></div><button className="text-button" onClick={() => go('history')}>Уся історія<ArrowRight size={16}/></button></div><MovementTable items={d.recent} compact/></section></>}</DataState></>
}
function Products({revision,user,onSaved,warehouseId,warehouseName,low=false}) {
  const [search,setSearch]=useState(''), [category,setCategory]=useState(''), [status,setStatus]=useState(low?'low':''), [page,setPage]=useState(1), [modal,setModal]=useState(null)
  const resource=useData(()=>api('/products'+query({warehouse_id:warehouseId,q:search,category_id:category,status,page})),[warehouseId,search,category,status,page,revision])
  const refs=useData(()=>Promise.all([api('/categories'),api('/suppliers')]),[revision])
  const change=fn=>e=>{fn(e.target.value);setPage(1)}
  const reset=()=>{setSearch('');setCategory('');setStatus('');setPage(1)}
  return <><Heading title="Товари" description={warehouseName + ' · Каталог, ціни та актуальні залишки'} action={user.role==='admin' && <button className="btn primary" onClick={()=>setModal({type:'edit'})} disabled={!refs.data}><Plus size={17}/>Додати товар</button>}/><section className="panel"><div className="filterbar"><div className="search-field"><Search size={18}/><input aria-label="Пошук товарів" placeholder="Пошук за назвою або SKU…" value={search} onChange={change(setSearch)}/>{search && <button className="icon-button" aria-label="Очистити пошук" onClick={()=>{setSearch('');setPage(1)}}><X size={15}/></button>}</div><select aria-label="Категорія" value={category} onChange={change(setCategory)}><option value="">Усі категорії</option>{refs.data?.[0].items.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select><select aria-label="Статус залишку" value={status} onChange={change(setStatus)}><option value="">Усі залишки</option><option value="available">В наявності</option><option value="low">Низький залишок</option><option value="empty">Немає на складі</option></select></div>{refs.error && <ErrorBox message={refs.error}/>}<DataState resource={resource}>{d=>d.items.length ? <><div className="table-scroll"><table className="products-table"><thead><tr><th>Товар / SKU</th><th>Категорія</th><th className="right">Ціна</th><th className="right">Залишок</th><th>Статус</th><th aria-label="Дії"/></tr></thead><tbody>{d.items.map(p=><tr key={p.id}><td><div className="product-cell"><span className="product-icon"><Package size={20}/></span><div><button className="text-button product-name" onClick={()=>go('products/'+p.id)}>{p.name}</button><small className="sku">{p.sku}</small></div></div></td><td><span className="category-label">{p.category}</span></td><td className="right nowrap">{money(p.price)}</td><td className="right"><strong className={p.low_stock?'amber-text':''}>{num(p.quantity)}</strong><small className="unit-inline"> {p.unit}</small><small className="sku">мін. {p.min_stock}</small></td><td><Badge product={p}/></td><td><div className="row-actions">{user.role==='admin' && <button className="icon-button" aria-label={'Редагувати '+p.name} onClick={()=>setModal({type:'edit',item:p})}><Pencil size={16}/></button>}<button className="icon-button" aria-label={'Відкрити '+p.name} onClick={()=>go('products/'+p.id)}><ChevronRight size={18}/></button></div></td></tr>)}</tbody></table></div><PageNav data={d} page={page} onChange={setPage}/></> : <Empty action={<button className="btn" onClick={reset}>Очистити фільтри</button>}/>}</DataState></section>{modal && <EntityForm kind="products" initial={modal.item} categories={refs.data?.[0].items} suppliers={refs.data?.[1].items} onClose={()=>setModal(null)} onSaved={onSaved}/>}</>
}
function ProductDetails({id,revision,user,onSaved,warehouseId,warehouseName}) {
  const resource=useData(()=>Promise.all([api('/products/'+id+query({warehouse_id:warehouseId})),api('/stock/history'+query({warehouse_id:warehouseId,product_id:id,per_page:10})),api('/categories'),api('/suppliers')]),[id,warehouseId,revision])
  const [modal,setModal]=useState(null)
  return <><button className="back-link" onClick={()=>go('products')}><ArrowLeft size={16}/>До каталогу товарів</button><DataState resource={resource}>{([p,h,c,s])=><><Heading eyebrow={p.sku} title={p.name} description={p.archived?'Товар архівовано. Історія операцій збережена.':warehouseName + ' · Деталі товару та історія руху'} action={user.role==='admin'&&!p.archived&&<button className="btn" onClick={()=>setModal('edit')}><Pencil size={16}/>Редагувати</button>}/><div className="detail-grid"><section className="panel stock-card"><div className="stock-top"><span className="product-icon big"><Package size={35}/></span><Badge product={p}/></div><span className="muted">Поточний залишок</span><div className="stock-number">{num(p.quantity)}<span>{p.unit}</span></div><div className="stock-meter"><div style={{width:`${Math.min(100,p.quantity/Math.max(1,p.min_stock*3)*100)}%`}}/></div><p className="muted">Мінімальний запас: {p.min_stock} {p.unit}</p>{user.role!=='manager'&&!p.archived&&<div className="stock-buttons"><button className="btn primary" onClick={()=>go('receipt/'+id)}><ArrowDownToLine size={17}/>Надходження</button><button className="btn" onClick={()=>go('writeoff/'+id)}><ArrowUpFromLine size={17}/>Списання</button></div>}</section><section className="panel detail-card"><h2>Інформація про товар</h2><dl>{[['Артикул',p.sku],['Категорія',p.category],['Постачальник',p.supplier||'Не вказано'],['Ціна за одиницю',money(p.price)],['Вартість залишку',money(p.price*p.quantity)],['Одиниця виміру',p.unit]].map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>{user.role==='admin'&&!p.archived&&<button className="text-button danger-text" onClick={()=>setModal('delete')}><Trash2 size={15}/>Архівувати товар</button>}</section></div><section className="panel"><div className="panel-title"><h2>Історія товару</h2><button className="text-button" onClick={()=>go('history/'+id)}>Усі операції<ArrowRight size={16}/></button></div><MovementTable items={h.items}/></section>{modal==='edit'&&<EntityForm kind="products" initial={p} categories={c.items} suppliers={s.items} onClose={()=>setModal(null)} onSaved={onSaved}/>} {modal==='delete'&&<Confirm kind="products" item={p} onClose={()=>setModal(null)} onSaved={onSaved}/>}</>}</DataState></>
}
function Operation({type,productId,revision,onSaved,warehouseId,warehouseName}) {
  const incoming=type==='receipt'
  const resource=useData(()=>Promise.all([allProducts(warehouseId),api('/suppliers')]),[warehouseId,revision])
  const [rows,setRows]=useState([{product_id:productId||'',quantity:'',price:''}]), [supplier,setSupplier]=useState(''), [note,setNote]=useState(''), [error,setError]=useState(''), [busy,setBusy]=useState(false), [success,setSuccess]=useState(null)
  const retryRequest=useRef(null)
  function updateRow(index,key,value,products) {setSuccess(null);setRows(rows.map((row,i)=>i===index?{...row,[key]:value,...(key==='product_id'?{price:products.find(p=>String(p.id)===value)?.price??''}:{})}:row))}
  async function submit(e) {
    e.preventDefault();setError('');setSuccess(null);setBusy(true)
    try {
      const payload=incoming?{warehouse_id:warehouseId,items:rows.map(r=>({...r,...(r.price===''?{price:resource.data[0].find(p=>String(p.id)===String(r.product_id))?.price}: {})})),supplier_id:supplier,note}:{...rows[0],warehouse_id:warehouseId,note}
      const signature=JSON.stringify(payload)
      if(retryRequest.current?.signature!==signature) retryRequest.current={signature,key:crypto.randomUUID()}
      const result=await api('/stock/'+type,{method:'POST',body:payload,headers:{'Idempotency-Key':retryRequest.current.key}})
      retryRequest.current=null;setSuccess(result);onSaved(result.message)
    } catch(e) {setError(e.status?e.message:'Не вдалося отримати підтвердження від сервера. Повторіть операцію з тими самими даними.')} finally {setBusy(false)}
  }
  return <><Heading eyebrow="СКЛАДСЬКІ ОПЕРАЦІЇ" title={incoming?'Нове надходження':'Списання товару'} description={warehouseName + (incoming?' · Приймання поставки':' · Списання з перевіркою кількості')}/><DataState resource={resource}>{([products,suppliers])=>products.length ? <div className="operation-layout"><section className="panel operation-form"><div className="panel-title"><h2>{incoming?'Деталі поставки':'Деталі списання'}</h2><span className={'operation-icon '+(incoming?'green':'amber')}>{incoming?<ArrowDownToLine size={22}/>:<ArrowUpFromLine size={22}/>}</span></div><form onSubmit={submit}><div className="form-body"><ErrorBox message={error}/>{success && <div className="success" role="status"><Check size={20}/><div><strong>{success.message}</strong>{success.items.map(item=><p key={item.product_id}>{products.find(p=>p.id===item.product_id)?.name}: новий залишок <b>{item.quantity}</b></p>)}<button type="button" className="text-button" onClick={()=>go('history')}>Перейти до історії<ArrowRight size={15}/></button>{success.document_id && <a className="operation-document-link" href={'#documents/'+success.document_id}>Відкрити документ</a>}</div></div>}{rows.map((row,index)=>{const selected=products.find(p=>String(p.id)===String(row.product_id));return <div className="operation-row" key={index}><div className="row-label"><span>Позиція {index+1}</span>{rows.length>1&&<button type="button" className="icon-button" aria-label={'Прибрати позицію '+(index+1)} onClick={()=>{setRows(rows.filter((_,i)=>i!==index));setSuccess(null)}}><X size={16}/></button>}</div><Field label="Товар"><select required aria-label={'Товар '+(index+1)} value={row.product_id} onChange={e=>updateRow(index,'product_id',e.target.value,products)}><option value="">Оберіть товар</option>{products.map(p=><option key={p.id} value={p.id} disabled={rows.some((r,i)=>i!==index&&String(r.product_id)===String(p.id))}>{p.name} · {p.sku}</option>)}</select></Field>{selected&&<div className="balance-hint"><Package size={16}/><span>На складі: <b>{selected.quantity} {selected.unit}</b></span><Badge product={selected}/></div>}<div className="form-grid"><Field label="Кількість"><input aria-label={'Кількість '+(index+1)} required type="number" min="1" step="1" max="1000000000" placeholder="Наприклад, 20" value={row.quantity} onChange={e=>updateRow(index,'quantity',e.target.value,products)}/></Field>{incoming&&<Field label="Закупівельна ціна, грн"><input aria-label={'Ціна '+(index+1)} type="number" required min="0" max="10000000" step="0.01" value={row.price==='' ? (selected?.price??'') : row.price} onChange={e=>updateRow(index,'price',e.target.value,products)}/></Field>}</div></div>})}{incoming&&<><button type="button" className="btn add-row" disabled={rows.length>=50||rows.length>=products.length} onClick={()=>{setRows([...rows,{product_id:'',quantity:'',price:''}]);setSuccess(null)}}><Plus size={16}/>Додати позицію</button><Field label="Постачальник"><select value={supplier} onChange={e=>{setSupplier(e.target.value);setSuccess(null)}}><option value="">Постачальник першого товару</option>{suppliers.items.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></Field></>}<Field label={incoming?'Коментар (необов’язково)':'Причина списання / коментар'}><textarea rows="3" maxLength="500" placeholder={incoming?'Номер накладної або примітка до поставки':'Наприклад, продаж, брак або пошкодження'} value={note} onChange={e=>{setNote(e.target.value);setSuccess(null)}}/></Field></div><div className="modal-footer"><button className="btn" type="button" onClick={()=>go(productId?'products/'+productId:'products')}>До товарів</button><button className="btn primary" disabled={busy||Boolean(success)}>{busy?<LoaderCircle size={16} className="spin"/>:<Check size={16}/>}Провести {incoming?'надходження':'списання'}</button></div></form></section><aside className="operation-guide"><div className="guide-symbol"><ShieldCheck size={30}/></div><h2>Кожна зміна під контролем</h2><p>{incoming?'Кількість додається до поточного залишку. Документ поставки та історія створюються разом.':'Система перевіряє доступний залишок перед списанням. Перевищення кількості буде відхилено.'}</p><div className="guide-step"><span>01</span><div><strong>Оберіть товар</strong><p>Перевірте його поточний залишок.</p></div></div><div className="guide-step"><span>02</span><div><strong>Вкажіть кількість</strong><p>Лише ціле додатне число.</p></div></div><div className="guide-step"><span>03</span><div><strong>Підтвердьте операцію</strong><p>Автор, час і результат потраплять в історію.</p></div></div></aside></div> : <section className="panel"><Empty title="Спочатку додайте товар" text="Для складської операції потрібен хоча б один товар у каталозі." action={<button className="btn" onClick={()=>go('products')}>Відкрити каталог</button>}/></section>}</DataState></>
}
function HistoryPage({id,revision,warehouseId,warehouseName}) {
  const [search,setSearch]=useState(''), [type,setType]=useState(''), [from,setFrom]=useState(''), [to,setTo]=useState(''), [page,setPage]=useState(1)
  const filters = {warehouse_id:warehouseId,product_id:id,q:search,type,from,to}
  const resource=useData(()=>api('/stock/history'+query({...filters,page})),[warehouseId,id,search,type,from,to,page,revision])
  const change=fn=>e=>{fn(e.target.value);setPage(1)}
  return <>
    <Heading title="Історія операцій" description={warehouseName + ' · Хто, коли та як змінив залишки'} action={
      <div className="phase-actions">
        {id&&<button className="btn" onClick={()=>go('history')}>Усі товари</button>}
        <a className="btn" href={'/api/data/history.csv'+query(filters)}>Експорт CSV</a>
      </div>
    }/>
    <section className="panel">
      <div className="filterbar history-filters">
        <div className="search-field"><Search size={18}/><input aria-label="Пошук в історії" placeholder="Назва товару або SKU…" value={search} onChange={change(setSearch)}/></div>
        <select aria-label="Тип операції" value={type} onChange={change(setType)}><option value="">Усі операції</option>{Object.entries(movementLabels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select>
        <label className="date-filter">З (UTC)<input aria-label="Дата початку" type="date" value={from} onChange={change(setFrom)}/></label>
        <label className="date-filter">До (UTC)<input aria-label="Дата завершення" type="date" value={to} min={from} onChange={change(setTo)}/></label>
        <button className="icon-button" aria-label="Очистити фільтри історії" onClick={()=>{setSearch('');setType('');setFrom('');setTo('');setPage(1)}}><X size={18}/></button>
      </div>
      <DataState resource={resource}>{d=><><MovementTable items={d.items}/><PageNav data={d} page={page} onChange={setPage}/></>}</DataState>
    </section>
  </>
}
function Directory({kind,revision,user,onSaved}) {
  const [modal,setModal]=useState(null)
  const resource=useData(()=>api('/'+kind),[kind,revision])
  const config={categories:['Категорії','Зручна структура вашого каталогу.','Додати категорію',Tags],suppliers:['Постачальники','Контакти та джерела ваших поставок.','Додати постачальника',Truck],users:['Користувачі','Ролі та доступ до складської системи.','Додати користувача',Users]}[kind]
  const Icon=config[3]
  return <><Heading title={config[0]} description={config[1]} action={user.role==='admin'&&<button className="btn primary" onClick={()=>setModal({type:'edit'})}><Plus size={17}/>{config[2]}</button>}/><DataState resource={resource}>{d=>d.items.length?<section className="panel"><div className="table-scroll"><table><thead><tr><th>{kind==='users'?'Користувач':'Назва'}</th>{kind==='suppliers'&&<><th>Телефон</th><th>Email</th></>}{kind==='users'&&<><th>Email</th><th>Роль</th><th>Статус</th></>}<th aria-label="Дії"/></tr></thead><tbody>{d.items.map(item=><tr key={item.id}><td><div className="product-cell"><span className="product-icon"><Icon size={20}/></span><strong>{item.name}</strong></div></td>{kind==='suppliers'&&<><td>{item.phone||'—'}</td><td>{item.email||'—'}</td></>}{kind==='users'&&<><td>{item.email}</td><td><span className="category-label">{roles[item.role]}</span></td><td><span className={'badge '+(item.active?'green':'red')}><span className="dot"/>{item.active?'Активний':'Заблокований'}</span></td></>}<td><div className="row-actions">{user.role==='admin'&&<><button className="icon-button" aria-label={'Редагувати '+item.name} onClick={()=>setModal({type:'edit',item})}><Pencil size={16}/></button>{kind!=='users'&&<button className="icon-button danger-text" aria-label={'Видалити '+item.name} onClick={()=>setModal({type:'delete',item})}><Trash2 size={16}/></button>}</>}</div></td></tr>)}</tbody></table></div><div className="directory-footer">Усього записів: {d.items.length}</div></section>:<section className="panel"><Empty title="Записів ще немає" text={user.role==='admin'?'Додайте перший запис за допомогою кнопки вгорі.':'Адміністратор може додати записи до довідника.'}/></section>}</DataState>{modal?.type==='edit'&&<EntityForm kind={kind} initial={modal.item} onClose={()=>setModal(null)} onSaved={onSaved}/>} {modal?.type==='delete'&&<Confirm kind={kind} item={modal.item} onClose={()=>setModal(null)} onSaved={onSaved}/>}</>
}
function Login({onLogin}) {
  const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[visible,setVisible]=useState(false),[error,setError]=useState(''),[busy,setBusy]=useState(false)
  async function submit(e) {e.preventDefault();setBusy(true);setError('');try {const data=await api('/auth/login',{method:'POST',body:{email,password}});setCsrf(data.csrf_token);onLogin(data.user);go('dashboard')} catch(e) {setError(e.message)} finally {setBusy(false)}}
  return <div className="login-layout"><section className="login-brand"><a className="brand" href="#"><span className="brand-icon"><Package size={25}/></span>EasyStock<span className="brand-period">.</span></a><div className="login-story"><span className="eyebrow">ПРОСТИЙ ОБЛІК. ПОВНИЙ КОНТРОЛЬ.</span><h1>Ваш склад.<br/>Усе на своїх<br/><em>місцях.</em></h1><p>Від першої поставки до останньої одиниці — керуйте товарами без зайвих таблиць.</p><div className="warehouse-art" aria-hidden="true"><div className="art-grid"/><div className="art-box b1"><Package size={64}/></div><div className="art-box b2"><Package size={49}/></div><div className="art-box b3"><Package size={35}/></div><div className="art-status"><span className="dot"/>Залишки актуальні<Check size={16}/></div></div></div><div className="login-brand-footer"><ShieldCheck size={16}/>Облік, якому можна довіряти</div></section><section className="login-right"><div className="login-form"><span className="login-icon"><Boxes size={28}/></span><h2>Раді бачити вас</h2><p className="muted">Увійдіть, щоб перейти до свого складу.</p><form onSubmit={submit}><ErrorBox message={error}/><Field label="Електронна адреса"><input type="email" autoComplete="username" required maxLength="200" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@company.com"/></Field><Field label="Пароль"><div className="password-input"><input type={visible?'text':'password'} autoComplete="current-password" required maxLength="256" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Введіть пароль"/><button type="button" className="icon-button" aria-label={visible?'Приховати пароль':'Показати пароль'} onClick={()=>setVisible(!visible)}>{visible?<EyeOff size={18}/>:<Eye size={18}/>}</button></div></Field><button className="btn primary login-submit" disabled={busy}>{busy?<LoaderCircle className="spin" size={17}/>:<>Увійти в систему<ArrowRight size={17}/></>}</button></form><div className="demo-box"><span className="eyebrow">НАВЧАЛЬНА ДЕМОНСТРАЦІЯ</span><p>Оберіть роль для демонстраційної бази:</p><div className="demo-roles">{Object.entries(roles).map(([key,label])=><button type="button" key={key} onClick={()=>{setEmail(key+'@easystock.local');setPassword('DemoStock2026!');setError('')}}>{label}</button>)}</div><small>Демоакаунти доступні після запуску seed-demo.</small></div></div><footer>EasyStock © {new Date().getFullYear()} · Проєктний практикум</footer></section></div>
}
function App() {
  const [user,setUser]=useState(null), [initializing,setInitializing]=useState(true)
  const [revision,setRevision]=useState(0), [toast,setToast]=useState(''), [mobile,setMobile]=useState(false)
  const [warehouseId,setWarehouseId]=useState(1)
  const [rawPage,id]=useRoute()
  const page=rawPage.split('?')[0]
  const warehouseResource=useData(()=>user ? api('/warehouses') : Promise.resolve({items:[]}),[user?.id,revision])
  const warehouses=warehouseResource.data?.items || []
  const warehouseName=warehouses.find(w=>w.id===warehouseId)?.name || 'Основний склад'

  useEffect(()=>{
    api('/auth/me').then(d=>{setCsrf(d.csrf_token);setUser(d.user)}).catch(()=>{}).finally(()=>setInitializing(false))
    const expired=()=>{setUser(null);setCsrf('');setWarehouseId(1)}
    window.addEventListener('session-expired',expired)
    return()=>window.removeEventListener('session-expired',expired)
  },[])
  useEffect(()=>{if(!toast)return;const timer=setTimeout(()=>setToast(''),5000);return()=>clearTimeout(timer)},[toast])
  useEffect(()=>setMobile(false),[rawPage,id])
  const saved=message=>{setRevision(n=>n+1);setToast(message)}
  async function logout() {
    try {
      await api('/auth/logout',{method:'POST'})
      setUser(null);setCsrf('');setWarehouseId(1)
    } catch(e) {setToast(e.message)}
  }
  if(initializing) return <Loading/>
  if(!user) return <Login onLogin={setUser}/>

  const navigation=[
    [LayoutDashboard,'dashboard','Огляд складу'],[Boxes,'products','Товари'],
    [ArrowDownToLine,'receipt','Надходження'],[ArrowUpFromLine,'writeoff','Списання'],
    [ClipboardList,'documents','Документи'],[History,'history','Історія операцій'],
  ].filter(([,key])=>user.role!=='manager'||!['receipt','writeoff'].includes(key))
  const directory=[
    [Warehouse,'warehouses','Склади'],[Tags,'categories','Категорії'],[Truck,'suppliers','Постачальники'],
    ...(user.role==='admin'?[[Users,'users','Користувачі']]:[]),[DatabaseBackup,'data','Імпорт і резервні копії'],
  ]
  const denied=(user.role==='manager'&&['receipt','writeoff'].includes(page))||(user.role!=='admin'&&page==='users')
  const props={warehouseId,warehouseName,revision,user,onSaved:saved}
  const navLink=([Icon,key,label])=><a className={page===key?'active':''} aria-current={page===key?'page':undefined} href={'#'+key} key={key}><Icon size={19}/><span>{label}</span>{page===key&&<span className="active-dot"/>}</a>
  let content
  if(denied) content=<Empty title="Доступ обмежено" text="Ваша роль не має дозволу на цю сторінку."/>
  else if(page==='dashboard') content=<Dashboard key={warehouseId} {...props}/>
  else if(page==='products'&&id) content=<ProductDetails key={warehouseId+'/'+id} id={id} {...props}/>
  else if(page==='products') content=<Products key={warehouseId+'/'+rawPage} low={rawPage.includes('?low')} {...props}/>
  else if(['receipt','writeoff'].includes(page)) content=<Operation key={warehouseId+'/'+page+'/'+(id||'')} type={page} productId={id} {...props}/>
  else if(page==='history') content=<HistoryPage key={warehouseId+'/'+(id||'all')} id={id} {...props}/>
  else if(page==='warehouses') content=<Warehouses {...props} resource={warehouseResource} onSelect={setWarehouseId}/>
  else if(page==='documents') content=<Documents key={id||'list'} id={id} warehouses={warehouses} {...props}/>
  else if(page==='data') content=<DataExchange {...props}/>
  else if(['categories','suppliers','users'].includes(page)) content=<Directory key={page} kind={page} {...props}/>
  else content=<Empty title="Сторінку не знайдено" action={<button className="btn" onClick={()=>go('dashboard')}>На головну</button>}/>

  return <div className="app-layout">
    {mobile&&<div className="sidebar-overlay" onClick={()=>setMobile(false)}/>}
    <aside className={'sidebar '+(mobile?'open':'')}>
      <a className="brand" href="#dashboard"><span className="brand-icon"><Package size={25}/></span>EasyStock<span className="brand-period">.</span></a>
      <div className="workspace"><span className="workspace-icon"><Warehouse size={19}/></span><div><strong>{warehouseName}</strong><small>Активний склад</small></div><span className="workspace-dot"/></div>
      <div className="nav-label">РОБОЧИЙ ПРОСТІР</div><nav aria-label="Основна навігація">{navigation.map(navLink)}</nav>
      <div className="nav-label directory-label">ДОВІДНИКИ ТА ДАНІ</div><nav aria-label="Довідники та дані">{directory.map(navLink)}</nav>
      <div className="sidebar-bottom"><div className="profile">
        <span className="avatar">{user.name.split(' ').map(s=>s[0]).slice(0,2).join('')}</span>
        <div><strong>{user.name}</strong><small>{roles[user.role]}</small></div>
        <button aria-label="Вийти із системи" onClick={logout}><LogOut size={18}/></button>
      </div></div>
    </aside>
    <div className="main-area">
      <header className="topbar">
        <div><button aria-label="Відкрити меню" className="icon-button mobile-menu" onClick={()=>setMobile(!mobile)}><Menu size={22}/></button>
          <span className="breadcrumb">Робочий простір<ChevronRight size={14}/><strong>{[...navigation,...directory].find(([,key])=>key===page)?.[2]||'Сторінка'}</strong></span>
        </div>
        <div className="topbar-right"><label className="warehouse-switch"><Warehouse size={15}/><span>Склад</span>
          <select aria-label="Активний склад" value={warehouseId} onChange={e=>setWarehouseId(Number(e.target.value))}>
            {(warehouses.length ? warehouses : [{id:1,name:'Основний склад'}]).map(w=><option key={w.id} value={w.id}>{w.name}</option>)}
          </select>
        </label></div>
      </header>
      <main>{warehouseResource.error&&page!=='warehouses'&&<ErrorBox message={warehouseResource.error}/>}
        {content}
      </main>
      <footer className="app-footer"><span>EasyStock · Облік без зайвого</span><span>Практика · v1.1</span></footer>
    </div>
    {toast&&<div className="toast" role="status"><Check size={19}/><span>{toast}</span><button className="icon-button" aria-label="Закрити повідомлення" onClick={()=>setToast('')}><X size={16}/></button></div>}
  </div>
}
createRoot(document.getElementById('root')).render(<App/>)
