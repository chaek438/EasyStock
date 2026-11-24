import React, {useEffect, useRef, useState} from 'react'
import {AlertTriangle, Boxes, ChevronLeft, ChevronRight, LoaderCircle, RefreshCw, X} from 'lucide-react'

export const money = value => new Intl.NumberFormat('uk-UA', {style:'currency', currency:'UAH', maximumFractionDigits:2}).format(value)
export const num = value => new Intl.NumberFormat('uk-UA').format(value)
export const date = value => new Date(value).toLocaleString('uk-UA', {day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit'})

export function useData(loader, dependencies) {
  const [state, set] = useState({data:null, loading:true, error:''})
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    let current = true
    set(s => ({...s, loading:true, error:''}))
    loader().then(data => current && set({data, loading:false, error:''})).catch(error => current && set({data:null, loading:false, error:error.message}))
    return () => { current = false }
  }, [...dependencies, retry])
  return {...state, retry:() => setRetry(n => n + 1)}
}

export function Loading() { return <div className="state"><LoaderCircle className="spin" size={24}/><p>Завантаження даних…</p></div> }

export function ErrorBox({message}) { return message ? <div className="error" role="alert"><AlertTriangle size={18}/><span>{message}</span></div> : null }

export function Empty({title='Нічого не знайдено', text='Спробуйте змінити пошук або очистити фільтри.', action}) { return <div className="state"><div className="empty-icon"><Boxes size={30}/></div><h3>{title}</h3><p>{text}</p>{action}</div> }

export function DataState({resource, children}) {
  if(resource.loading && !resource.data) return <Loading/>
  if(resource.error) return <div className="state"><ErrorBox message={resource.error}/><button className="btn" onClick={resource.retry}><RefreshCw size={16}/>Спробувати ще</button></div>
  return children(resource.data)
}

export function Field({label, children, hint}) { return <label className="field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label> }

export function Heading({eyebrow='ВАШ СКЛАД', title, description, action}) { return <div className="page-heading"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{action}</div> }

export function PageNav({data, page, onChange}) { return <div className="pagination"><span>{data.total ? `${(page - 1) * data.per_page + 1}–${Math.min(page * data.per_page, data.total)} із ${num(data.total)}` : '0 записів'}</span><div><button className="icon-button" aria-label="Попередня сторінка" disabled={page === 1} onClick={() => onChange(page - 1)}><ChevronLeft size={18}/></button><span>Сторінка {page}</span><button className="icon-button" aria-label="Наступна сторінка" disabled={page * data.per_page >= data.total} onClick={() => onChange(page + 1)}><ChevronRight size={18}/></button></div></div> }

export function Modal({title, onClose, children}) {
  const ref = useRef(null)
  useEffect(() => {
    const previous = document.activeElement
    const el = ref.current
    el.querySelector('input,select,button')?.focus()
    const key = e => {
      if(e.key === 'Escape') onClose()
      if(e.key === 'Tab') {
        const nodes = [...el.querySelectorAll('button,input,select,textarea,a[href]')].filter(n => !n.disabled)
        if(e.shiftKey && document.activeElement === nodes[0]) {e.preventDefault(); nodes.at(-1)?.focus()}
        if(!e.shiftKey && document.activeElement === nodes.at(-1)) {e.preventDefault(); nodes[0]?.focus()}
      }
    }
    document.addEventListener('keydown', key)
    return () => { document.removeEventListener('keydown', key); previous?.focus() }
  }, [])
  return <div className="modal-backdrop" onMouseDown={e => e.target === e.currentTarget && onClose()}><section ref={ref} className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div className="modal-header"><h2 id="modal-title">{title}</h2><button aria-label="Закрити" className="icon-button" onClick={onClose}><X size={20}/></button></div>{children}</section></div>
}
