import {chromium} from 'playwright';
import {existsSync} from 'node:fs';
import {mkdir} from 'node:fs/promises';
const base=process.env.INNOVA_URL||'http://127.0.0.1:8017';
const mac='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const browser=await chromium.launch({headless:true,...(existsSync(mac)?{executablePath:mac}:{})});
const errors=[];await mkdir('artifacts',{recursive:true});
try {
  for(const [width,height] of [[1440,1000],[390,844],[844,390],[320,720]]) {
    const page=await browser.newPage({viewport:{width,height}});
    page.on('pageerror',error=>errors.push(error.message));
    await page.goto(base);await page.locator('#videos button').first().waitFor();
    await page.locator('#videos button').first().click();
    await page.locator('#runs button').first().waitFor();
    const buttons=page.locator('#runs button');
    let completed;
    for(let i=0;i<await buttons.count();i++) if((await buttons.nth(i).innerText()).includes('Завершён')){completed=buttons.nth(i);break;}
    if(!completed) throw Error('Seed a completed run before UI verification');
    await completed.click();await page.locator('#report').waitFor();
    if(await page.locator('body').innerText().then(text=>text.includes('Не удалось открыть интерфейс')))throw Error('React boundary failure');
    const size=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));
    if(size.scroll>size.width+1)throw Error(`Horizontal overflow ${JSON.stringify(size)}`);
    if(width===1440) {
      await page.locator('#lighting').selectOption('night');await page.locator('#nightModel').waitFor();
      await page.locator('#profile').selectOption('ensemble');if(await page.locator('#sampleFpsControl').count())throw Error('Ensemble sampling should be hidden');
      await page.locator('#profile').selectOption('fast');
      await page.locator('#manual').click();await page.locator('#eventDialog').waitFor();
      await page.locator('#eventTime').fill('2');await page.locator('#eventCategory').selectOption('pedestrian');
      await page.locator('#eventSave').click();await page.locator('#eventDialog').waitFor({state:'detached'});
      await page.locator('#events tr').filter({hasText:'Пешеходы'}).first().waitFor();
      const download=await page.request.get(new URL(await page.locator('#xlsx').getAttribute('href'),base).href);
      if(!download.ok()||(await download.body()).subarray(0,2).toString()!=='PK')throw Error('XLSX export failed');
      await page.locator('#manualMode').click();await page.locator('[data-tool="entry"]').click();
      await page.locator('#lineName').fill('Въезд A');await page.locator('#pointX').fill('20');await page.locator('#pointY').fill('10');await page.locator('#addPoint').click();await page.locator('#pointY').fill('90');await page.locator('#addPoint').click();
      await page.locator('[data-tool="exit"]').click();await page.locator('#lineName').fill('Выезд B');await page.locator('#pointX').fill('80');await page.locator('#pointY').fill('10');await page.locator('#addPoint').click();await page.locator('#pointY').fill('90');await page.locator('#addPoint').click();
      await page.locator('#saveScene').click();await page.locator('#notice').filter({hasText:'Зона сохранена'}).waitFor();
      const scenes=await page.request.get(`${base}/api/scenes`);if(!(await scenes.json()).some(s=>s.geometry.entries?.some(e=>e.name==='Въезд A')))throw Error('Scene was not saved');
    }
    await page.screenshot({path:`artifacts/react-${width}.png`,fullPage:true});
    console.log(`PASS ${width}x${height}: report, controls, responsive layout`);
    await page.close();
  }
  if(errors.length)throw Error(errors.join('\n'));
} finally {await browser.close();}
