// React DOM integration against a real running API; does not test browser layout.
import {createRequire} from 'node:module'
import {unlink} from 'node:fs/promises'
import assert from 'node:assert/strict'
const require=createRequire(new URL('../frontend/package.json',import.meta.url))
console.log('UI test: loading DOM');
const {JSDOM}=require('jsdom'), {build}=require('esbuild')
const productName='React DOM '+Date.now()
const base=process.env.EASYSTOCK_URL || 'http://127.0.0.1:5000'
const dom=new JSDOM('<html><body><div id="root"></div></body></html>',{url:base,pretendToBeVisual:true})
for(const key of ['window','document','location','HTMLElement','Element','Node','Event','MouseEvent','KeyboardEvent','HTMLInputElement','HTMLSelectElement','MutationObserver']) globalThis[key]=dom.window[key]
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
const originalFetch=globalThis.fetch
let cookie='', loseNextStockReply=false
const stockRequestKeys=[]
globalThis.fetch=async(path,options={})=>{
  const result=await originalFetch(new URL(path,base),{...options,headers:{...options.headers,...(cookie?{Cookie:cookie}:{})}})
  if(result.headers.get('set-cookie')) cookie=result.headers.get('set-cookie').split(';')[0]
  if(path==='/api/stock/receipt' && options.method==='POST') {
    stockRequestKeys.push(options.headers?.['Idempotency-Key'])
    if(loseNextStockReply && result.ok) {
      loseNextStockReply=false
      throw new TypeError('Simulated response loss after server commit')
    }
  }
  return result
}
const {screen,waitFor,within}=require('@testing-library/react')
const user=require('@testing-library/user-event').default.setup({document:dom.window.document})
const compiled=new URL(`../frontend/.ui-test-build-${process.pid}.mjs`,import.meta.url)
console.log('UI test: compiling entry');
await build({entryPoints:[new URL('../frontend/src/main.jsx',import.meta.url).pathname],outfile:compiled.pathname,bundle:true,format:'esm',packages:'external',loader:{'.css':'empty'}})
const wait=fn=>waitFor(fn,{timeout:10000})
const click=async(name,role='button')=>user.click(screen.getByRole(role,{name,exact:true}))
const input=async(name,value,role='textbox')=>{const el=screen.getByRole(role,{name,exact:true});await user.clear(el);await user.type(el,String(value))}
try {
  console.log('UI test: mounting React');
  await import(compiled.href+'?'+Date.now())
  await wait(()=>assert.ok(screen.getByRole('heading',{name:'Раді бачити вас'})))
  console.log('UI test: login');
  await click('Адміністратор'); await click('Увійти в систему')
  await wait(()=>assert.ok(screen.getByRole('heading',{name:'Останні операції'})))
  console.log('UI test: search');
  await click('Товари','link')
  await wait(()=>assert.ok(screen.getByRole('button',{name:'SSD Kingston A400 480 GB',exact:true})))
  await input('Пошук товарів','КЛАВІАТУРА')
  await wait(()=>assert.equal(document.querySelectorAll('tbody tr').length,1))
  assert.ok(screen.getByRole('button',{name:'Клавіатура Logitech K120',exact:true}))
  await input('Пошук товарів','NOT-FOUND-TEST')
  await wait(()=>assert.ok(screen.getByRole('heading',{name:'Нічого не знайдено'})))
  await click('Очистити фільтри')
  await wait(()=>assert.ok(screen.getByRole('button',{name:'SSD Kingston A400 480 GB',exact:true})))
  console.log('UI test: create product');
  await click('Додати товар')
  const dialog=within(screen.getByRole('dialog'))
  await user.type(dialog.getByLabelText('Назва / ім’я'),productName)
  await user.type(dialog.getByLabelText('Артикул (SKU)'),'UI-'+Date.now())
  await user.clear(dialog.getByLabelText('Ціна, грн')); await user.type(dialog.getByLabelText('Ціна, грн'),'1450')
  await user.click(dialog.getByRole('button',{name:'Зберегти',exact:true}))
  await wait(()=>assert.ok(screen.queryByRole('dialog')===null))
  await wait(()=>assert.ok(screen.getByRole('button',{name:productName,exact:true})))
  await click(productName)
  await wait(()=>assert.ok(screen.getByRole('heading',{name:productName,exact:true})))
  assert.ok(document.querySelector('.stock-number').textContent.includes('0'))
  const identifier=location.hash.split('/').at(-1)
  console.log('UI test: stock operations');
  for(const quantity of [17,20]) {
    await click('Надходження')
    await wait(()=>assert.ok(screen.getByRole('spinbutton',{name:'Кількість 1'})))
    await input('Кількість 1',quantity,'spinbutton')
    if(quantity===17) loseNextStockReply=true
    await click('Провести надходження')
    if(quantity===17) {
      await wait(()=>assert.ok(screen.getByRole('alert').textContent.includes('Повторіть операцію')))
      assert.equal(screen.getByRole('spinbutton',{name:'Кількість 1'}).value,'17')
      await click('Провести надходження')
      await wait(()=>assert.equal(stockRequestKeys.length,2))
      assert.ok(stockRequestKeys[0])
      assert.equal(stockRequestKeys[0],stockRequestKeys[1])
    }
    await wait(()=>assert.ok(document.querySelector('.success')?.textContent.includes(String(quantity===17?17:37))))
    await click('До товарів')
    await wait(()=>assert.ok(document.querySelector('.stock-number')?.textContent.includes(String(quantity===17?17:37))))
  }
  assert.notEqual(stockRequestKeys[1],stockRequestKeys[2])
  await click('Списання')
  await wait(()=>assert.ok(screen.getByRole('spinbutton',{name:'Кількість 1'})))
  await input('Кількість 1',40,'spinbutton'); await input('Причина списання / коментар','Збережений коментар')
  await click('Провести списання')
  await wait(()=>assert.ok(screen.getByRole('alert').textContent.includes('Недостатньо товару')))
  assert.equal(screen.getByRole('spinbutton',{name:'Кількість 1'}).value,'40')
  assert.equal(screen.getByRole('textbox',{name:'Причина списання / коментар'}).value,'Збережений коментар')
  assert.ok(document.querySelector('.balance-hint').textContent.includes('37'))
  await input('Кількість 1',37,'spinbutton'); await click('Провести списання')
  await wait(()=>assert.ok(document.querySelector('.success')?.textContent.includes('новий залишок 0')))
  await click('Перейти до історії')
  await wait(()=>assert.ok(document.querySelector('tbody tr')?.textContent.includes(productName)))
  assert.ok(document.querySelector('tbody tr').textContent.includes('Сергій Бондаренко'))
  location.hash='products/'+identifier
  await wait(()=>assert.ok(screen.getByRole('heading',{name:productName,exact:true})))
  await click('Архівувати товар')
  await user.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Архівувати',exact:true}))
  await wait(()=>assert.ok(screen.getByText('Товар архівовано. Історія операцій збережена.',{exact:true})))
  await click('Вийти із системи')
  await wait(()=>assert.ok(screen.getByRole('heading',{name:'Раді бачити вас'})))
  await click('Менеджер'); await click('Увійти в систему')
  await wait(()=>assert.ok(screen.getByRole('heading',{name:'Огляд складу',exact:true})))
  assert.ok(screen.queryByRole('link',{name:'Надходження',exact:true})===null)
  assert.ok(screen.queryByRole('link',{name:'Користувачі',exact:true})===null)
  location.hash='receipt'
  await wait(()=>assert.ok(screen.getByRole('heading',{name:'Доступ обмежено'})))
  console.log('PASS: React DOM + real API — login, Unicode search, empty state, product creation, lost response after commit and safe retry, receipts 17+20=37, excess writeoff rejection, preserved inputs, successful writeoff, history audit, archive, logout, manager roles.')

  location.hash='documents/new'
  await wait(()=>assert.ok(screen.getByText('Менеджер може переглядати складські документи.')))
  await click('Вийти із системи'); await wait(()=>assert.ok(screen.getByRole('button',{name:'Адміністратор',exact:true})))
  await click('Адміністратор'); await click('Увійти в систему')
  await wait(()=>assert.ok(screen.getByRole('link',{name:'Склади',exact:true})))
  await click('Склади','link')
  await wait(()=>assert.ok(screen.getByRole('heading',{name:'Резервний склад'})))
  await click('Додати склад')
  const warehouseForm=within(screen.getByRole('dialog'))
  await user.type(warehouseForm.getByLabelText('Назва складу'),'Склад UI')
  await user.type(warehouseForm.getByLabelText(/^Код складу/),'UI-DEPOT')
  await user.click(warehouseForm.getByRole('button',{name:'Зберегти'}))
  await wait(()=>assert.ok(screen.getByRole('heading',{name:'Склад UI'})))

  await click('Документи','link'); await wait(()=>assert.ok(screen.getByRole('link',{name:'Новий документ'})))
  await click('Новий документ','link')
  await wait(()=>assert.ok(screen.getByRole('combobox',{name:'Склад призначення'})))
  const destinationField=screen.getByLabelText('Склад призначення')
  const destination=within(destinationField).getByRole('option',{name:'Склад UI · UI-DEPOT'}).value
  await user.selectOptions(destinationField,destination)
  await user.selectOptions(screen.getByRole('combobox',{name:'Товар 1'}),'1')
  await input('Кількість 1',5,'spinbutton'); await click('Зберегти чернетку')
  await wait(()=>assert.ok(screen.getByText('Чернетка',{exact:true})))
  async function confirm(label) {
    await click(label)
    await user.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Підтвердити'}))
  }
  await confirm('Передати на погодження')
  await wait(()=>assert.ok(screen.getByRole('button',{name:'Провести документ'})))
  await confirm('Провести документ')
  await wait(()=>assert.ok(screen.getByRole('heading',{name:'Проведені рухи'})))
  assert.ok(within(document.querySelector('.print-document')).getByText('Проведено',{exact:true}))
  assert.ok(within(document.querySelector('.print-document')).getByText('Переміщення на склад',{exact:true}))

  await user.selectOptions(screen.getByLabelText('Активний склад'),destination)
  location.hash='products/1'
  await wait(()=>assert.match(document.querySelector('.stock-number')?.textContent || '',/^5/))
  await click('Документи','link');await wait(()=>assert.ok(screen.getByRole('link',{name:'Новий документ'})))
  await click('Новий документ','link')
  await wait(()=>assert.ok(screen.getByLabelText('Тип документа')))
  await user.selectOptions(screen.getByLabelText('Тип документа'),'count')
  await user.selectOptions(screen.getByRole('combobox',{name:'Товар 1'}),'1')
  await input('Фактична кількість 1',4,'spinbutton')
  await input('Причина підрахунку','Перерахунок під час перевірки')
  await click('Зберегти чернетку')
  await wait(()=>assert.ok(screen.getByRole('columnheader',{name:'Різниця'})))
  await confirm('Передати на погодження')
  await wait(()=>assert.ok(screen.getByRole('button',{name:'Провести документ'})))
  await confirm('Провести документ')
  await wait(()=>assert.ok(screen.getByText('Нестача',{exact:true})))
  location.hash='products/1'
  await wait(()=>assert.match(document.querySelector('.stock-number')?.textContent || '',/^4/))

  await click('Імпорт і резервні копії','link')
  await wait(()=>assert.ok(screen.getByRole('link',{name:'Завантажити копію'})))
  const csvFile=new dom.window.File(['sku;name;category;price;min_stock;unit\nUI-CSV;Тест імпорту;Накопичувачі;15;2;шт.'], 'catalog.csv',{type:'text/csv'})
  await user.upload(screen.getByLabelText('Файл CSV'),csvFile)
  await click('Перевірити файл')
  await wait(()=>assert.ok(screen.getByText('Готові до імпорту: 1 з 1. Помилки: 0.')))
  await click('Імпортувати товари')
  await wait(()=>assert.ok(screen.getByText('Додано товарів: 1.')))
  console.log('PASS: Warehouse UI — creation, scoped stock, transfer, inventory approval, CSV preview/import, backup link, read-only manager role.')
} catch(error) {
  console.error('UI state:',location.hash,[...document.querySelectorAll('h1,h2,.error')].map(e=>e.textContent));
  throw error
} finally {
  await unlink(compiled).catch(()=>{})
  dom.window.close()
}
