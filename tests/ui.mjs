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
let cookie=''
globalThis.fetch=async(path,options={})=>{
  const result=await originalFetch(new URL(path,base),{...options,headers:{...options.headers,...(cookie?{Cookie:cookie}:{})}})
  if(result.headers.get('set-cookie')) cookie=result.headers.get('set-cookie').split(';')[0]
  return result
}
const {screen,waitFor,within}=require('@testing-library/react')
const user=require('@testing-library/user-event').default.setup({document:dom.window.document})
const compiled=new URL('../frontend/.ui-test-build.mjs',import.meta.url)
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
    await input('Кількість 1',quantity,'spinbutton'); await click('Провести надходження')
    await wait(()=>assert.ok(document.querySelector('.success')?.textContent.includes(String(quantity===17?17:37))))
    await click('До товарів')
    await wait(()=>assert.ok(document.querySelector('.stock-number')?.textContent.includes(String(quantity===17?17:37))))
  }
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
  console.log('PASS: React DOM + real API — login, Unicode search, empty state, product creation, receipts 17+20=37, excess writeoff rejection, preserved inputs, successful writeoff, history audit, archive, logout, manager roles.')
} catch(error) {
  console.error('UI state:',location.hash,[...document.querySelectorAll('h1,h2,.error')].map(e=>e.textContent));
  throw error
} finally {
  await unlink(compiled).catch(()=>{})
  dom.window.close()
}
