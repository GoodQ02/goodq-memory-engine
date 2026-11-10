// Exercise the shipped scene inspector with a minimal DOM; no network or boot.
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

class Element {
  constructor(tag) { this.tagName = tag; this.children = []; this.attrs = {}; this.dataset = {}; this.classList = { add() {} }; }
  appendChild(child) { this.children.push(child); return child; }
  get firstChild() { return this.children[0]; }
  removeChild(child) { this.children.splice(this.children.indexOf(child), 1); }
  set textContent(text) { this.children = []; this.text = String(text); }
  get textContent() { return [this.text || '', ...this.children.map(x => x.textContent)].filter(Boolean).join('\n'); }
  setAttribute(key, value) { this.attrs[key] = value; }
  addEventListener() {}
}
const panels = Object.fromEntries(['scene-detail-panel', 'scene-modality-panel', 'scene-schema-panel'].map(id => ['#' + id, new Element('div')]));
const context = { document: { querySelector: s => panels[s], createElement: t => new Element(t), addEventListener() {} }, window: {}, URL, URLSearchParams, console };
const source = fs.readFileSync(path.join(__dirname, '../../ui/operator_console_v1/static/js/app.js'), 'utf8');
const registration = 'document.addEventListener("DOMContentLoaded", init);';
if (!source.includes(registration)) throw Error('Console boot registration changed');
vm.runInNewContext(source.replace(registration, 'window.renderInspector = renderSceneInspector;'), context);
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const state = context.window.GoodQOperatorConsole.state;
state.data.timeline = { segments: input };
function walk(node) { return [node, ...node.children.flatMap(walk)]; }
const output = input.map((segment, index) => {
  state.selectedSceneKey = String(segment.scene_id ?? index);
  context.window.renderInspector();
  const detail = panels['#scene-detail-panel'];
  const modality = panels['#scene-modality-panel'];
  const rows = walk(modality).filter(x => x.className === 'scene-signal-row');
  return { detail: detail.textContent, modality: modality.textContent,
    temporal: rows.find(x => x.children[0].children[0].textContent === 'Temporal hints').textContent,
    summary: walk(detail).find(x => x.className?.startsWith('scene-signal-chip ') && x.textContent.startsWith('Temporal hints')).textContent,
  };
});
process.stdout.write(JSON.stringify(output));
