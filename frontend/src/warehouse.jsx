import React, {useState} from 'react'
import {ArrowDownToLine, ArrowLeft, ArrowRight, Check, ClipboardList, DatabaseBackup, FileDown, FileUp, Pencil, Plus, Printer, Warehouse, X} from 'lucide-react'
import {allProducts, api, query} from './api'
import {DataState, Empty, ErrorBox, Field, Heading, Modal, PageNav, date, money, num, useData} from './ui'

export const movementLabels = {
  receipt:'Надходження', writeoff:'Списання', transfer_out:'Переміщення зі складу', transfer_in:'Переміщення на склад',
  adjustment_in:'Надлишок', adjustment_out:'Нестача', reversal_in:'Сторно · додано', reversal_out:'Сторно · списано',
}
const kinds = {receipt:'Надходження', writeoff:'Списання', transfer:'Переміщення', count:'Інвентаризація', reversal:'Сторно'}
const stages = {draft:'Чернетка', review:'На погодженні', posted:'Проведено', cancelled:'Скасовано', reversed:'Сторновано'}
const stageColor = {draft:'neutral', review:'amber', posted:'green', cancelled:'red', reversed:'neutral'}
const signed = value => (value > 0 ? '+' : '') + num(value)
const go = id => { location.hash = id ? 'documents/' + id : 'documents' }

function WarehouseOptions({items, exclude}) {
  return items.filter(w => w.id !== Number(exclude)).map(w => <option key={w.id} value={w.id}>{w.name} · {w.code}</option>)
}

function WarehouseForm({initial, onClose, onSaved}) {
  const [form,setForm] = useState({code:initial?.code || '', name:initial?.name || '', address:initial?.address || ''})
  const [busy,setBusy] = useState(false), [error,setError] = useState('')
  const field = key => ({value:form[key], onChange:e=>setForm({...form,[key]:e.target.value})})
  async function submit(event) {
    event.preventDefault(); setError(''); setBusy(true)
    try {
      await api('/warehouses'+(initial?'/'+initial.id:''), {method:initial?'PUT':'POST',body:form})
      onSaved(initial?'Дані складу оновлено.':'Новий склад додано.'); onClose()
    } catch (error) { setError(error.message) }
    finally { setBusy(false) }
  }
  return <Modal title={initial?'Редагувати склад':'Додати склад'} onClose={onClose}>
    <form onSubmit={submit}>
      <div className="form-body"><ErrorBox message={error}/>
        <Field label="Назва складу"><input required maxLength={100} {...field('name')}/></Field>
        <Field label="Код складу" hint="Унікальний код, наприклад WEST-01. Після створення код не змінюється."><input required maxLength={20} readOnly={!!initial} {...field('code')}/></Field>
        <Field label="Адреса або місце зберігання"><input maxLength={200} {...field('address')}/></Field>
      </div>
      <div className="modal-footer"><button type="button" className="btn" disabled={busy} onClick={onClose}>Скасувати</button><button className="btn primary" disabled={busy}><Check size={16}/>Зберегти</button></div>
    </form>
  </Modal>
}

export function Warehouses({resource, warehouseId, user, onSelect, onSaved}) {
  const [form,setForm] = useState(null)
  return <>
    <Heading eyebrow="СКЛАДСЬКИЙ ОБЛІК" title="Склади" description="Порівняйте запаси та виберіть склад для операцій і звітів." action={user.role==='admin'&&<button className="btn primary" onClick={()=>setForm({})}><Plus size={16}/>Додати склад</button>}/>
    <DataState resource={resource}>{data => <div className="phase-card-grid">{data.items.map(w => <article className={'panel warehouse-card'+(w.id===warehouseId?' warehouse-active':'')} key={w.id}>
      <div className="warehouse-card-top"><span className="product-icon"><Warehouse size={21}/></span><span className={'badge '+(w.id===warehouseId?'green':'neutral')}>{w.id===warehouseId?'Активний склад':w.code}</span></div>
      <h2>{w.name}</h2><p className="warehouse-address">{w.address || (w.is_main?'Склад для початкових залишків':'Адресу не вказано')}</p>
      <dl className="warehouse-metrics"><div><dt>Позиції в наявності</dt><dd>{num(w.positions)}</dd></div><div><dt>Одиниці</dt><dd>{num(w.units)}</dd></div><div><dt>За цінами каталогу</dt><dd>{money(w.value)}</dd></div></dl>
      <div className="phase-actions"><button className="btn" type="button" disabled={w.id===warehouseId} onClick={()=>onSelect(w.id)}>{w.id===warehouseId?'Вибрано':'Обрати склад'}</button>
        {user.role==='admin'&&<button className="icon-button" aria-label={'Редагувати '+w.name} onClick={()=>setForm({item:w})}><Pencil size={16}/></button>}
      </div>
    </article>)}</div>}</DataState>
    {form&&<WarehouseForm initial={form.item} onClose={()=>setForm(null)} onSaved={onSaved}/>}
  </>
}

function Status({status}) {
  return <span className={'badge '+stageColor[status]}><span className="dot"/>{stages[status]}</span>
}

function DocumentList({user, warehouseId, warehouseName, revision}) {
  const [kind,setKind] = useState(''), [status,setStatus] = useState(''), [page,setPage] = useState(1)
  const [activeOnly,setActiveOnly] = useState(false), [number,setNumber] = useState(''), [search,setSearch] = useState('')
  const scope = activeOnly ? warehouseId : undefined
  const resource=useData(()=>api('/documents'+query({warehouse_id:scope,kind,status,page,number:search})),[scope,kind,status,page,search,revision])
  return <>
    <Heading eyebrow="СКЛАДСЬКИЙ ОБЛІК" title="Складські документи" description="Підготуйте переміщення чи інвентаризацію та простежте, коли документ провели." action={user.role!=='manager'&&<a className="btn primary" href="#documents/new"><Plus size={16}/>Новий документ</a>}/>
    <section className="panel">
      <form className="filterbar phase-filters" onSubmit={e=>{e.preventDefault();setPage(1);setSearch(number.trim())}}>
        <div className="phase-search"><input aria-label="Номер документа" placeholder="СК-000001" value={number} onChange={e=>{setNumber(e.target.value);if(!e.target.value.trim()){setPage(1);setSearch('')}}}/><button className="btn">Знайти</button></div>
        <select aria-label="Тип документа" value={kind} onChange={e=>{setKind(e.target.value);setPage(1)}}><option value="">Усі типи</option>{Object.entries(kinds).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select>
        <select aria-label="Стан документа" value={status} onChange={e=>{setStatus(e.target.value);setPage(1)}}><option value="">Усі стани</option>{Object.entries(stages).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select>
        <label className="phase-check"><input type="checkbox" checked={activeOnly} onChange={e=>{setActiveOnly(e.target.checked);setPage(1)}}/> {warehouseName}</label>
      </form>
      <DataState resource={resource}>{d => d.items.length ? <>
        <div className="table-scroll"><table><thead><tr><th>Документ</th><th>Тип</th><th>Склад</th><th>Стан</th><th>Автор</th><th>Дата</th></tr></thead>
          <tbody>{d.items.map(doc => <tr key={doc.id}>
            <td><a href={'#documents/'+doc.id} className="phase-link">{doc.number}</a></td><td>{kinds[doc.kind]}</td>
            <td>{doc.warehouse}{doc.destination&&<small className="sku">→ {doc.destination}</small>}</td>
            <td><Status status={doc.status}/></td><td>{doc.author}</td><td className="nowrap">{date(doc.created_at)}</td>
          </tr>)}</tbody></table></div>
        <PageNav data={d} page={page} onChange={setPage}/>
      </> : <Empty title="Документів не знайдено" text="Змініть фільтри або створіть новий документ."/>}</DataState>
    </section>
  </>
}

const newLine = key => ({key, product_id:'', quantity:'', price:''})

function DocumentEditor({initial, warehouses, warehouseId, revision, onSaved, onClose}) {
  const [kind,setKind] = useState(initial?.kind || 'transfer')
  const [source,setSource] = useState(initial?.warehouse_id || warehouseId), [destination,setDestination] = useState(initial?.destination_id || '')
  const [note,setNote] = useState(initial?.note || ''), [supplier,setSupplier] = useState(initial?.supplier_id || '')
  const [lines,setLines] = useState(()=>initial?.items.map((p,i)=>({...p,key:i,price:p.price??''})) || [newLine(0)])
  const [error,setError] = useState(''), [busy,setBusy] = useState(false)
  const resources = useData(()=>Promise.all([allProducts(source),api('/suppliers')]),[source,revision])
  const isCount = kind==='count', isTransfer = kind==='transfer', isReceipt = kind==='receipt'
  function update(key, field, value) { setLines(rows=>rows.map(row=>row.key===key?{...row,[field]:value}:row)) }
  async function save(e) {
    e.preventDefault();setError('');setBusy(true)
    try {
      const payload={kind,warehouse_id:source,destination_id:destination,supplier_id:supplier,note,revision:initial?.revision,
        items:lines.map(row=>({product_id:row.product_id,quantity:row.quantity,...(isReceipt&&row.price!==''?{price:row.price}:{}),
          ...(isCount?{stock_revision:resources.data[0].find(p=>String(p.id)===String(row.product_id))?.stock_revision}:{})}))}
      const result=await api('/documents'+(initial?'/'+initial.id:''),{method:initial?'PUT':'POST',body:payload})
      onSaved('Чернетку збережено.'); if(initial) onClose(); else go(result.id)
    } catch (error) {setError(error.message)}
    finally {setBusy(false)}
  }
  return <>
    <button className="back-link" onClick={onClose}><ArrowLeft size={16}/>{initial?'До документа':'До документів'}</button>
    <Heading eyebrow="СКЛАДСЬКИЙ ДОКУМЕНТ" title={initial?'Редагувати '+initial.number:'Новий складський документ'} description="Чернетку можна змінити перед передачею на погодження."/>
    <section className="panel phase-editor">
      <DataState resource={resources}>{([products,suppliers])=><form onSubmit={save}>
        <div className="form-body">
          <ErrorBox message={error}/>
          <div className="form-grid">
            <Field label="Тип документа"><select value={kind} disabled={!!initial||busy} onChange={e=>setKind(e.target.value)}>{Object.entries(kinds).filter(([k])=>k!=='reversal').map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></Field>
            <Field label={isTransfer?'Склад відправлення':'Склад'}><select value={source} required onChange={e=>{setSource(Number(e.target.value));if(Number(destination)===Number(e.target.value))setDestination('')}}><WarehouseOptions items={warehouses}/></select></Field>
            {isTransfer&&<Field label="Склад призначення"><select required value={destination} onChange={e=>setDestination(e.target.value)}><option value="">Оберіть склад</option><WarehouseOptions items={warehouses} exclude={source}/></select></Field>}
            {isReceipt&&<Field label="Постачальник"><select value={supplier} onChange={e=>setSupplier(e.target.value)}><option value="">Постачальник першого товару</option>{suppliers.items.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></Field>}
          </div>
          {isCount&&<p className="phase-info">Введіть фактично пораховану кількість. Під час збереження фіксується обліковий залишок. Якщо він зміниться до проведення, система попросить зробити новий підрахунок.</p>}
          {isTransfer&&warehouses.length<2&&<p className="phase-info">Для переміщення <a className="phase-link" href="#warehouses">додайте другий склад</a>.</p>}
          {lines.map((row,i)=>{
            const product = products.find(p=>String(p.id)===String(row.product_id))
            return <fieldset className="phase-line" key={row.key}>
              <legend>Позиція {i+1}</legend>
              <div className="phase-line-fields">
                <Field label="Товар" hint={product&&`Обліковий залишок: ${product.quantity} ${product.unit}`}><select aria-label={'Товар '+(i+1)} required value={row.product_id} onChange={e=>update(row.key,'product_id',e.target.value)}><option value="">Оберіть товар</option>
                  {products.map(p=><option key={p.id} value={p.id} disabled={lines.some(r=>r.key!==row.key && String(r.product_id)===String(p.id))}>{p.sku} · {p.name}</option>)}
                </select></Field>
                <Field label={isCount?'Фактична кількість':'Кількість'}><input aria-label={(isCount?'Фактична кількість ':'Кількість ')+(i+1)} type="number" min={isCount?0:1} max={1000000000} step={1} required value={row.quantity} onChange={e=>update(row.key,'quantity',e.target.value)}/></Field>
                {isReceipt&&<Field label="Ціна, грн"><input aria-label={'Ціна '+(i+1)} type="number" min={0} max={10000000} step="0.01" value={row.price} placeholder={product?String(product.price):''} onChange={e=>update(row.key,'price',e.target.value)}/></Field>}
                {lines.length>1&&<button className="icon-button" type="button" aria-label={'Прибрати позицію '+(i+1)} onClick={()=>setLines(rows=>rows.filter(r=>r.key!==row.key))}><X size={17}/></button>}
              </div>
            </fieldset>
          })}
          <button className="btn add-row" type="button" disabled={lines.length>=50||lines.length>=products.length} onClick={()=>setLines(rows=>[...rows,newLine(Math.max(...rows.map(r=>r.key))+1)])}><Plus size={16}/>Додати позицію</button>
          <Field label={isCount?'Причина підрахунку':'Коментар'}><textarea required={isCount} rows={3} maxLength={500} value={note} onChange={e=>setNote(e.target.value)}/></Field>
        </div>
        <div className="modal-footer"><button className="btn" type="button" disabled={busy} onClick={onClose}>Скасувати</button><button className="btn primary" disabled={busy || resources.loading || !products.length}><Check size={16}/>Зберегти чернетку</button></div>
      </form>}</DataState>
    </section>
  </>
}

function DocumentView({id, user, revision, warehouseId, warehouses, onSaved}) {
  const resource=useData(()=>api('/documents/'+id),[id,revision])
  const [editing,setEditing] = useState(false), [action,setAction] = useState(null)
  const [busy,setBusy] = useState(false), [reason,setReason] = useState(''), [error,setError] = useState('')
  function choose(next) {setAction(next);setError('');setReason('')}
  async function perform(e, doc) {
    e.preventDefault();setBusy(true);setError('')
    try {
      const result=await api('/documents/'+doc.id+'/'+action,{method:'POST',body:{revision:doc.revision,note:reason}})
      setAction(null);onSaved(action==='reverse'?'Сторно проведено.':stages[result.status]+'.')
      if(action==='reverse')go(result.id)
    } catch (error) {setError(error.message)}
    finally {setBusy(false)}
  }
  const actionTitles = {submit:'Передати на погодження?', post:'Провести документ?', return:'Повернути в чернетку?', cancel:'Скасувати документ?', reverse:'Створити сторно?'}
  const actionDescriptions = {submit:'Адміністратор зможе перевірити позиції та провести документ.', post:'Після проведення залишки буде оновлено. Виправлення оформлюється окремим сторно.', return:'Автор зможе уточнити позиції та повторно подати документ.', cancel:'Документ залишиться в історії зі станом «Скасовано». Залишки не зміняться.', reverse:'Система створить окремий документ і зворотні рухи. Початковий запис збережеться.'}
  return <DataState resource={resource}>{doc => {
    if (editing) return <DocumentEditor initial={doc} warehouses={warehouses} warehouseId={warehouseId} revision={revision} onSaved={onSaved} onClose={()=>setEditing(false)}/>
    const admin=user.role==='admin', canEdit=admin||(user.role==='keeper'&&doc.created_by_id===user.id)
    return <>
      <button className="back-link phase-no-print" onClick={()=>go()}><ArrowLeft size={16}/>До документів</button>
      <div className="phase-no-print"><Heading eyebrow="СКЛАДСЬКИЙ ДОКУМЕНТ" title={doc.number+' · '+kinds[doc.kind]} description="Позиції, погодження та проведені зміни залишків." action={<button className="btn" onClick={()=>window.print()}><Printer size={16}/>Друк / PDF</button>}/></div>
      <article className="panel print-document">
        <div className="panel-title"><div><h2>{kinds[doc.kind]} · {doc.number}</h2><p>EasyStock</p></div><Status status={doc.status}/></div>
        <dl className="doc-meta">
          <div><dt>{doc.destination?'Зі складу':'Склад'}</dt><dd>{doc.warehouse}{doc.destination?' → '+doc.destination:''}</dd></div>
          {doc.supplier&&<div><dt>Постачальник</dt><dd>{doc.supplier}</dd></div>}
          <div><dt>Підготував</dt><dd>{doc.author} · {date(doc.created_at)}</dd></div>
          {doc.posted_by&&<div><dt>Провів</dt><dd>{doc.posted_by} · {date(doc.posted_at)}</dd></div>}
          {doc.cancelled_by&&<div><dt>Скасував</dt><dd>{doc.cancelled_by} · {date(doc.cancelled_at)}</dd></div>}
          {doc.original_id&&<div><dt>Початковий документ</dt><dd><a className="phase-link" href={'#documents/'+doc.original_id}>СК-{String(doc.original_id).padStart(6,'0')}</a></dd></div>}
          {doc.reversal_id&&<div><dt>Документ сторно</dt><dd><a className="phase-link" href={'#documents/'+doc.reversal_id}>СК-{String(doc.reversal_id).padStart(6,'0')}</a></dd></div>}
          {doc.note&&<div className="doc-note"><dt>Коментар</dt><dd>{doc.note}</dd></div>}
        </dl>
        <div className="table-scroll"><table>
          <thead><tr><th>Товар</th><th>SKU</th>{doc.kind==='count'&&<th className="right">За обліком</th>}<th className="right">{doc.kind==='count'?'Фактично':'Кількість'}</th>{doc.kind==='count'&&<th className="right">Різниця</th>}{doc.kind==='receipt'&&<th className="right">Ціна, грн</th>}</tr></thead>
          <tbody>{doc.items.map(row=><tr key={row.product_id}><td>{row.product}</td><td>{row.sku}</td>{doc.kind==='count'&&<td className="right">{num(row.expected_quantity)}</td>}<td className="right">{num(row.quantity)} {row.unit}</td>{doc.kind==='count'&&<td className="right">{signed(row.difference)}</td>}{doc.kind==='receipt'&&<td className="right">{money(row.price)}</td>}</tr>)}</tbody>
        </table></div>
        {doc.movements.length>0&&<><div className="panel-title"><h2>Проведені рухи</h2></div><div className="table-scroll"><table>
          <thead><tr><th>SKU</th><th>Склад</th><th>Рух</th><th className="right">Зміна</th><th className="right">Залишок після</th></tr></thead>
          <tbody>{doc.movements.map(row=><tr key={row.id}><td>{row.sku}</td><td>{row.warehouse}</td><td>{movementLabels[row.type]}</td><td className="right">{signed(row.delta)}</td><td className="right">{num(row.balance_after)}</td></tr>)}</tbody>
        </table></div></>}
      </article>
      <div className="phase-actions document-actions phase-no-print">
        {doc.status==='draft'&&canEdit&&<><button className="btn" onClick={()=>setEditing(true)}><Pencil size={16}/>Редагувати</button><button className="btn primary" onClick={()=>choose('submit')}>Передати на погодження<ArrowRight size={16}/></button></>}
        {doc.status==='review'&&admin&&<><button className="btn" onClick={()=>choose('return')}>Повернути в чернетку</button><button className="btn primary" onClick={()=>choose('post')}><Check size={16}/>Провести документ</button></>}
        {['draft','review'].includes(doc.status)&&canEdit&&<button className="btn" onClick={()=>choose('cancel')}>Скасувати документ</button>}
        {doc.status==='posted'&&doc.kind!=='reversal'&&doc.movements.length>0&&admin&&<button className="btn" onClick={()=>choose('reverse')}>Створити сторно</button>}
      </div>
      {action&&<Modal title={actionTitles[action]} onClose={()=>!busy&&setAction(null)}><form onSubmit={e=>perform(e,doc)}>
        <div className="form-body"><p className="muted phase-dialog-description">{actionDescriptions[action]}</p><ErrorBox message={error}/>
          {action==='reverse'&&<Field label="Причина сторнування"><textarea required maxLength={500} value={reason} onChange={e=>setReason(e.target.value)} rows={3}/></Field>}
        </div><div className="modal-footer"><button className="btn" type="button" disabled={busy} onClick={()=>setAction(null)}>Назад</button><button className="btn primary" disabled={busy}>Підтвердити</button></div>
      </form></Modal>}
    </>
  }}</DataState>
}

export function Documents(props) {
  if (props.id==='new') return props.user.role==='manager' ? <Empty title="Доступ обмежено" text="Менеджер може переглядати складські документи."/> : <DocumentEditor {...props} onClose={()=>go()}/>
  if (props.id) return <DocumentView {...props}/>
  return <DocumentList {...props}/>
}

export function DataExchange({user, warehouseId, warehouseName, onSaved}) {
  const [file,setFile] = useState(null), [preview,setPreview] = useState(null), [raw,setRaw] = useState('')
  const [error,setError] = useState(''), [busy,setBusy] = useState(false)
  const [fileVersion,setFileVersion] = useState(0)
  const isAdmin=user.role==='admin'
  async function analyze(e) {
    e.preventDefault();setError('');setPreview(null);setRaw('');setBusy(true)
    try {
      if (file.size>450000) throw new Error('Завантажте CSV до 450 КБ.')
      const bytes=await new Promise((resolve,reject)=>{
        const reader=new window.FileReader()
        reader.onload=()=>resolve(reader.result)
        reader.onerror=()=>reject(new Error('Не вдалося прочитати файл.'))
        reader.readAsArrayBuffer(file)
      })
      const csv = new TextDecoder('utf-8',{fatal:true}).decode(bytes)
      const result = await api('/data/catalog/preview',{method:'POST',body:{csv}})
      setPreview(result);setRaw(csv)
    } catch (error) {setError(error instanceof TypeError?'Не вдалося прочитати файл. Перевірте кодування UTF-8 або спробуйте ще раз.':error.message)}
    finally {setBusy(false)}
  }
  async function importFile() {
    setError('');setBusy(true)
    try {
      const result=await api('/data/catalog/import',{method:'POST',body:{csv:raw}})
      setPreview(null);setRaw('');setFile(null);setFileVersion(n=>n+1);onSaved(result.message)
    } catch (error) {setError(error.message+' Повторіть перевірку файлу.');setPreview(null)}
    finally {setBusy(false)}
  }
  return <>
    <Heading eyebrow="ДАНІ ТА ЗВІТИ" title="Імпорт, експорт і резервні копії" description="Обмін даними з електронними таблицями та збереження копії складу."/>
    <div className="phase-card-grid data-cards">
      <section className="panel data-card"><span className="product-icon"><FileDown size={22}/></span><h2>Експорт CSV</h2><p>Каталог цілої системи та складські звіти для «{warehouseName}». CSV можна відкрити в Excel.</p>
        <div className="phase-actions"><a className="btn" href="/api/data/catalog.csv">Каталог</a><a className="btn" href={'/api/data/stock.csv'+query({warehouse_id:warehouseId})}>Залишки</a><a className="btn" href={'/api/data/history.csv'+query({warehouse_id:warehouseId})}>Історія</a></div>
      </section>
      {isAdmin&&<section className="panel data-card"><span className="product-icon"><DatabaseBackup size={22}/></span><h2>Резервна копія SQLite</h2><p>Зберігає залишки, документи, користувачів і довідники. Активні сеанси не переносяться. Зберігайте файл у приватному місці.</p>
        <div className="phase-actions"><a className="btn" href="/api/data/backup"><ArrowDownToLine size={16}/>Завантажити копію</a></div>
      </section>}
    </div>
    {isAdmin&&<section className="panel phase-import">
      <div className="panel-title"><div><h2>Імпорт товарів</h2><p>До 500 нових позицій. Наявні товари та залишки не перезаписуються.</p></div><a className="btn" href="/api/data/catalog-template.csv"><FileDown size={16}/>Завантажити шаблон</a></div>
      <div className="form-body">
        <p className="phase-info">Збережіть таблицю у форматі CSV UTF-8. У колонці category використайте назву категорії з довідника. Початкові залишки оформіть надходженням або інвентаризацією.</p>
        <ErrorBox message={error}/>
        <form className="import-form" onSubmit={analyze}>
          <Field label="Файл CSV"><input key={fileVersion} type="file" accept=".csv,text/csv" disabled={busy} onChange={e=>{setFile(e.target.files[0]||null);setPreview(null);setError('')}}/></Field>
          {file&&<small className="selected-filename">{file.name}</small>}
          <button className="btn" disabled={!file||busy}><FileUp size={16}/>Перевірити файл</button>
        </form>
        {preview&&<div className="import-preview">
          <h3>Результат перевірки</h3><p role="status">Готові до імпорту: {preview.valid} з {preview.total}. Помилки: {preview.errors.length}.</p>
          {preview.errors.length>0&&<ul className="import-errors">{preview.errors.slice(0,20).map(e=><li key={e.line}>Рядок {e.line}: {e.message}</li>)}</ul>}
          {preview.items.length>0&&<div className="table-scroll"><table><thead><tr><th>SKU</th><th>Назва</th><th>Категорія</th><th className="right">Ціна</th></tr></thead><tbody>{preview.items.map(p=><tr key={p.sku}><td>{p.sku}</td><td>{p.name}</td><td>{p.category}</td><td className="right">{money(p.price_cents/100)}</td></tr>)}</tbody></table></div>}
          <button className="btn primary" disabled={busy||!!preview.errors.length} onClick={importFile}>Імпортувати товари</button>
        </div>}
      </div>
    </section>}
  </>
}
