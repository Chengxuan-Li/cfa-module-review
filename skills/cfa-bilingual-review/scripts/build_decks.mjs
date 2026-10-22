import fs from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import path from 'node:path';

const [planPath, outputPath, modulePath] = process.argv.slice(2);
if (!modulePath) throw new Error('Usage: node build_decks.mjs PLAN OUTPUT ARTIFACT_TOOL_MODULE');
const { Presentation, PresentationFile } = await import(pathToFileURL(path.resolve(modulePath)).href);
const plan = JSON.parse(await fs.readFile(planPath, 'utf8'));
await fs.mkdir(outputPath, { recursive: true });
for (const variant of ['concise', 'expanded']) {
  const presentation = Presentation.create({slideSize: {width: 1280, height: 720}});
  presentation.theme.defaultFont = plan.font_family;
  for (const item of plan[variant]) {
    const slide = presentation.slides.add();
    slide.background.fill = plan.theme.background;
    // Rules separate reading regions; the neutral equation band groups mathematical content.
    const bilingual = item.language_profile === 'bilingual-knowledge-english-examples';
    const rules = bilingual ? [['header-rule',48,148,1180,3,'#225B64']] : item.layout === 'objectives' ? [
      ['header-rule',60,148,1156,2,plan.theme.rule],
      ['example-rule',60,item.balance_sheet?326:477,1156,1,plan.theme.rule],
      ['trap-rule',60,656,1156,1,plan.theme.rule],
    ] : [
      ['header-rule',60,145,1160,2,plan.theme.rule],
      ['equation-band',60,340,item.formula_width,91,plan.theme.equation_background],
      ['condition-rule',60,510,item.formula_width,1,plan.theme.rule],
      ['trap-rule',60,583,item.formula_width,1,plan.theme.rule],
      ...(item.expanded ? [['example-divider',695,165,1,495,plan.theme.rule]] : []),
    ];
    for (const [name,x,y,w,h,fill] of rules) slide.shapes.add({name,geometry:'rect',position:{left:x,top:y,width:w,height:h},fill,line:{fill:'none',width:0}});
    for (const card of item.cards ?? []) {
      slide.shapes.add({name:`${card.name}-boundary`,geometry:'rect',
        position:{left:card.x,top:card.y,width:card.w,height:card.h},
        fill:card.name==='trap'?'#FFF7E9':'#FFFFFF',line:{fill:'#4E6C78',width:2}});
      for (const [name,x,y,h] of [
        ...(card.label_divider ? [['label-divider',card.label_divider,card.y+2,card.h-4]]:[]),
        ...(card.language_divider ? [['language-divider',card.language_divider,card.language_y,card.language_h]]:[]),
      ]) if(h>0)slide.shapes.add({name:`${card.name}-${name}`,geometry:'rect',
        position:{left:x,top:y,width:1.5,height:h},fill:'#78919A',line:{fill:'none',width:0}});
    }
    for (const box of item.boxes) {
      const shape = slide.shapes.add({geometry: 'textbox', name: box.name,
        position: {left: box.x, top: box.y, width: box.w, height: box.h},
        fill: 'none', line: {fill: 'none', width: 0}});
      shape.text = [box.runs.map(run => ({run:run.text,style:{color:run.color,typeface:plan.font_family,fontSize:`${box.size}px`,bold:box.bold ?? false}}))];
      shape.text.insets = 0;
      shape.text.style = {typeface: plan.font_family, fontSize: box.size,
        bold: box.bold ?? false, verticalAlignment: 'top', autoFit: 'none', wrap: 'none'};
    }
    if (item.balance_sheet) {
      const sheet = item.balance_sheet;
      const values = [[bilingual?'Item':item.layout==='objectives'?'项目':'Item / 项目',sheet.unit], ...sheet.rows.map(r => [r.label,String(r.amount)])];
      const geometry = bilingual ? {left:680,top:405,width:528,height:246,columnWidths:[398,130]} : item.layout==='objectives' ? {left:680,top:377,width:536,height:258,columnWidths:[406,130]} : {left:728,top:365,width:492,height:222,columnWidths:[382,110]};
      const table = slide.tables.add({rows:values.length,columns:2,...geometry,values});
      table.borders.assign({fill:bilingual?'#65818D':plan.theme.rule,width:bilingual?1.25:0.5,style:'solid'});
      for (let r=0;r<values.length;r++) {
        table.rows[r].height = geometry.height/values.length;
        for (let c=0;c<2;c++) {
          const cell = table.getCell(r,c);
          const row = sheet.rows[r-1];
          cell.fill = r===0 ? '#E8EEF2' : (row.components ? '#F2F6F8' : '#FFFFFF');
          cell.text.style = {typeface:plan.font_family,fontSize:24,color:r===0 ? plan.theme.ink : plan.theme.roles[row.role],
            bold:r===0 || Boolean(row.components),alignment:c===1?'right':'left',verticalAlignment:'middle',insets:{left:8,right:8,top:2,bottom:2}};
        }
      }
    }
    slide.speakerNotes.text = item.notes;
  }
  await (await PresentationFile.exportPptx(presentation)).save(path.join(outputPath, `review-${variant}.pptx`));
  console.log(`Exported ${variant}: ${presentation.slides.items.length} slides`);
}
