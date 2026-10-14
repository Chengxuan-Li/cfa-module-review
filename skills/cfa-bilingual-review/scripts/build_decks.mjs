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
    slide.background.fill = '#FFFFFF';
    for (const box of item.boxes) {
      const shape = slide.shapes.add({geometry: 'textbox', name: box.name,
        position: {left: box.x, top: box.y, width: box.w, height: box.h},
        fill: 'none', line: {fill: 'none', width: 0}});
      shape.text = box.text;
      shape.text.insets = 0;
      shape.text.style = {typeface: plan.font_family, fontSize: box.size,
        color: box.color, bold: box.bold ?? false, verticalAlignment: 'top', autoFit: 'none', wrap: 'none'};
    }
    slide.speakerNotes.text = item.notes;
  }
  await (await PresentationFile.exportPptx(presentation)).save(path.join(outputPath, `review-${variant}.pptx`));
  console.log(`Exported ${variant}: ${presentation.slides.items.length} slides`);
}
