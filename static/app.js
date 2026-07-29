const STROBE_LABELS = ['1/1','1/2','1/4','1/8','1/16','1/32'];
const FADER_NAMES = ['Algorithm','Beat React','Rhythm','Speed','Hue','Saturation',
                     'Colour Spread','Scale','Direction','Symmetry','Contrast','Blur/Glow'];
const CC_NUMS = [24,25,26,27,28,29,30,31,32,33,34,35];

let ws, state = {}, selectedPreset = null, selectedFixture = null, selectedGroup = null;
let fixtures = [], canvasSize = {width:200, height:100};

function connect() {
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = e => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'fixtures_reload') {
      canvasSize = msg.canvas;
      fixtures = msg.fixtures;
      selectedFixture = null;
      selectedGroup = null;
      document.getElementById('fixture-form').style.display = 'none';
      document.getElementById('group-form').style.display = 'none';
      document.getElementById('canvas-w').value = canvasSize.width;
      document.getElementById('canvas-h').value = canvasSize.height;
      drawGrid();
    } else {
      applyState(msg);
    }
  };
  ws.onclose = () => setTimeout(connect, 2000);
}

function send(msg) { if (ws.readyState===1) ws.send(JSON.stringify(msg)); }
function sendCC(type, value) { send({type, value: +value}); }

function showPage(name, btn) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  btn.classList.add('active');
  if (name === 'midi') buildMidiTable(state.assignments || {});
}

function applyState(s) {
  state = s;
  document.getElementById('bpm-val').textContent = (s.bpm||120).toFixed(1);
  document.getElementById('clock-dot').classList.toggle('active', !!s.midi_clock_active);
  document.getElementById('master-fader').value = Math.round((s.master??1)*127);
  document.getElementById('blend-fader').value = Math.round((s.blend||0)*127);

  const fc = document.getElementById('faders');
  if (!fc.children.length) buildFaders(fc);
  (s.faders||[]).forEach((v,i) => {
    const el = document.getElementById('fader-'+i);
    if (el) el.value = Math.round(v*127);
  });

  const algoCount = s.algo_count || 1;
  buildAlgoThumbnails(algoCount);
  const activeAlgoIdx = Math.min(Math.floor((s.faders?.[0]||0) * algoCount), algoCount - 1);
  document.querySelectorAll('.algo-thumb').forEach((el, i) => {
    el.classList.toggle('active', i === activeAlgoIdx);
  });

  document.querySelectorAll('.preset-btn').forEach((btn,i) => {
    btn.classList.toggle('active', s.active_preset === i);
  });

  buildClips(s.clips||[]);
  populateSetupSelects(s.setups||[]);

  document.getElementById('strobe-rate').value = s.strobe_rate_index??2;
  document.getElementById('strobe-depth').value = Math.round((s.strobe_depth??1)*127);
  document.getElementById('strobe-duty').value = Math.round((s.strobe_duty??0.5)*127);
  document.getElementById('strobe-rate-display').textContent = STROBE_LABELS[s.strobe_rate_index??2];
  document.getElementById('strobe-bpm-display').textContent = `@ ${(s.bpm||120).toFixed(0)} BPM`;
  const sec = document.getElementById('strobe-section');
  sec.classList.toggle('on', !!s.strobe_active);
  const strobBtn = document.getElementById('strobe-toggle');
  strobBtn.textContent = s.strobe_active ? 'Strobe ON' : 'Strobe OFF';
  strobBtn.classList.toggle('primary', !!s.strobe_active);

  // Sync learn state with server: midi_input clears learn_target after a
  // successful learn, so the "Listening…" button must reset here too.
  learningTarget = s.learn_target ?? null;

  if (document.getElementById('page-midi').classList.contains('active')) {
    buildMidiTable(s.assignments||{});
  }
}

function buildFaders(container) {
  container.innerHTML = '';
  FADER_NAMES.forEach((name, i) => {
    if (i === 0) return;  // algorithm select now lives in the thumbnail grid
    const col = document.createElement('div');
    col.className = 'fader-col';
    col.innerHTML = `
      <input type="range" id="fader-${i}" min="0" max="127" value="64"
             oninput="send({type:'set_fader',index:${i},value:this.value/127})">
      <div class="fname">${name}</div>
      <div class="fcc">CC${CC_NUMS[i]}</div>`;
    container.appendChild(col);
  });
}

// ── Algorithm thumbnail grid ────────────────────────────────────────────────────
let algoThumbsBuilt = 0;   // count the grid was last built for; 0 until the real count is known
let algoPollStarted = false;

function buildAlgoThumbnails(count) {
  const c = document.getElementById('algo-thumbs');
  if (algoThumbsBuilt !== count) {
    algoThumbsBuilt = count;
    c.innerHTML = '';
    for (let i = 0; i < count; i++) {
      const img = document.createElement('img');
      img.className = 'algo-thumb';
      img.dataset.idx = i;
      img.style = 'width:64px;height:32px;object-fit:cover;border:1px solid #444;cursor:pointer;background:#111';
      img.onerror = () => { img.style.display = 'none'; };
      img.onload = () => { img.style.display = ''; };
      img.onclick = () => {
        send({type:'set_fader', index:0, value:(i+0.5)/count});
      };
      c.appendChild(img);
    }
  }
  if (!algoPollStarted) {
    algoPollStarted = true;
    setInterval(() => {
      document.querySelectorAll('.algo-thumb').forEach(img => {
        img.src = `/algo_thumbnail/${img.dataset.idx}?` + Date.now();
      });
    }, 2000);
  }
}

function buildPresets() {
  const c = document.getElementById('presets');
  c.innerHTML = '';
  for (let i = 0; i < 24; i++) {
    const btn = document.createElement('button');
    btn.className = 'preset-btn';
    btn.textContent = i+1;
    btn.onclick = () => { selectedPreset = i; updatePresetUI(); };
    c.appendChild(btn);
  }
}

function updatePresetUI() {
  document.querySelectorAll('.preset-btn').forEach((b,i) =>
    b.classList.toggle('selected', i === selectedPreset));
}

function savePreset() {
  if (selectedPreset === null) return;
  send({type:'save_preset', slot: selectedPreset});
  const btn = document.getElementById('save-preset-btn');
  btn.textContent = 'Saved!';
  btn.classList.add('save-flash');
  setTimeout(() => { btn.textContent = 'Save to selected'; btn.classList.remove('save-flash'); }, 1000);
}

function buildClips(clips) {
  const c = document.getElementById('clip-list');
  c.innerHTML = '';
  clips.forEach((name, i) => {
    const btn = document.createElement('div');
    btn.className = 'clip-btn' + (name ? ' occupied' : '') + (state.active_clip===i ? ' active' : '');
    btn.textContent = name ? `${i}: ${name}` : `${i}`;
    if (name) {
      btn.style.cursor = 'pointer';
      btn.onclick = () => {
        if (state.active_clip === i) {
          send({type: 'clip_stop', slot: i});
        } else {
          send({type: 'clip_trigger', slot: i});
        }
      };
    }
    c.appendChild(btn);
  });
}

// ── Fixture Editor ────────────────────────────────────────────────────────────
const gridCanvas = document.getElementById('canvas-grid');
const ctx = gridCanvas.getContext('2d');

function applyCanvas() {
  canvasSize = {
    width: +document.getElementById('canvas-w').value,
    height: +document.getElementById('canvas-h').value
  };
  drawGrid();
}

function drawGrid() {
  const scale = 600 / canvasSize.width;
  gridCanvas.width = 600;
  gridCanvas.height = Math.round(canvasSize.height * scale);
  ctx.fillStyle = '#111';
  ctx.fillRect(0, 0, gridCanvas.width, gridCanvas.height);
  ctx.strokeStyle = '#222';
  ctx.lineWidth = 1;
  for (let x = 0; x <= canvasSize.width; x += 10) {
    ctx.beginPath(); ctx.moveTo(x*scale, 0); ctx.lineTo(x*scale, gridCanvas.height); ctx.stroke();
  }
  for (let y = 0; y <= canvasSize.height; y += 10) {
    ctx.beginPath(); ctx.moveTo(0, y*scale); ctx.lineTo(gridCanvas.width, y*scale); ctx.stroke();
  }
  fixtures.forEach((f, idx) => drawFixture(f, idx === selectedFixture || (selectedGroup !== null && f.group === selectedGroup), scale));
}

const ORIENTATIONS = ['H', 'H180', 'V', 'V180'];
function isHorizontal(orientation) { return orientation === 'H' || orientation === 'H180'; }

// 90-degree-clockwise orientation cycle for whole-group rotation -- derived from
// rotating each orientation's pixel-0-to-last-pixel direction vector 90deg CW.
// Deliberately a different cycle than the single-fixture '#' key above, which
// never repositions anything so its cycle order is arbitrary.
const ROTATE_CW = {H: 'V180', V180: 'H180', H180: 'V', V: 'H'};

function groupBoundingBox(members) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  members.forEach(f => {
    const len = f.length || 40;
    const horiz = isHorizontal(f.orientation);
    const w = horiz ? len : 4;
    const h = horiz ? 4 : len;
    minX = Math.min(minX, f.x);
    minY = Math.min(minY, f.y);
    maxX = Math.max(maxX, f.x + w);
    maxY = Math.max(maxY, f.y + h);
  });
  return {cx: (minX + maxX) / 2, cy: (minY + maxY) / 2};
}

function drawFixture(f, selected, scale) {
  const len = f.length || 40;
  const horiz = isHorizontal(f.orientation);
  const x = f.x * scale, y = f.y * scale;
  const w = horiz ? len * scale : 4;
  const h = horiz ? 4 : len * scale;
  ctx.fillStyle = selected ? '#0af' : '#f80';
  ctx.fillRect(x, y, w, h);

  // Pixel-0 marker (green) and last-pixel marker (red), placed per orientation.
  const markerSize = 6;
  let firstX = x, firstY = y, lastX = x, lastY = y;
  if (f.orientation === 'H') { lastX = x + w - markerSize; }
  else if (f.orientation === 'H180') { firstX = x + w - markerSize; }
  else if (f.orientation === 'V') { firstY = y + h - markerSize; }
  else if (f.orientation === 'V180') { lastY = y + h - markerSize; }
  ctx.fillStyle = '#2ecc40';
  ctx.fillRect(firstX, firstY, markerSize, markerSize);
  ctx.fillStyle = '#ff4136';
  ctx.fillRect(lastX, lastY, markerSize, markerSize);

  ctx.fillStyle = '#fff';
  ctx.font = '9px monospace';
  ctx.fillText(f.name || `f${fixtures.indexOf(f)}`, x+2, y+10);
}

gridCanvas.onclick = e => {
  const scale = 600 / canvasSize.width;
  const rx = e.offsetX / scale, ry = e.offsetY / scale;
  let hit = -1;
  fixtures.forEach((f, i) => {
    const len = f.length || 40;
    const horiz = isHorizontal(f.orientation);
    const fx2 = f.x + (horiz ? len : 4/scale);
    const fy2 = f.y + (horiz ? 4/scale : len);
    if (rx >= f.x && rx <= fx2 && ry >= f.y && ry <= fy2) hit = i;
  });
  if (hit >= 0) {
    selectedGroup = null;
    selectedFixture = hit;
    showFixtureForm(fixtures[hit]);
    drawGrid();
  }
};

function addStrip() {
  fixtures.push({name: `strip_${fixtures.length+1}`, group:'', x:0, y:0,
                 orientation:'V', length:40, universe:0, start_channel:0});
  selectedGroup = null;
  selectedFixture = fixtures.length - 1;
  showFixtureForm(fixtures[selectedFixture]);
  drawGrid();
}

function copyFixture() {
  if (selectedFixture === null) return;
  const src = fixtures[selectedFixture];
  fixtures.push({...src, name: `strip_${fixtures.length+1}`});
  selectedFixture = fixtures.length - 1;
  showFixtureForm(fixtures[selectedFixture]);
  drawGrid();
}

function deleteStrip() {
  if (selectedFixture !== null) {
    fixtures.splice(selectedFixture, 1);
    selectedFixture = null;
    document.getElementById('fixture-form').style.display = 'none';
    drawGrid();
  }
}

function showFixtureForm(f) {
  document.getElementById('group-form').style.display = 'none';
  document.getElementById('fixture-form').style.display = 'grid';
  document.getElementById('f-name').value = f.name || '';
  document.getElementById('f-group').value = f.group || '';
  document.getElementById('f-x').value = f.x;
  document.getElementById('f-y').value = f.y;
  document.getElementById('f-orient').value = f.orientation || 'H';
  document.getElementById('f-universe').value = f.universe;
  document.getElementById('f-ch').value = f.start_channel;

  const btn = document.getElementById('select-group-btn');
  if (f.group) {
    const count = fixtures.filter(x => x.group === f.group).length;
    btn.textContent = `Select Group (${count})`;
    btn.style.display = 'block';
  } else {
    btn.style.display = 'none';
  }
}

function selectGroupOfCurrent() {
  if (selectedFixture === null) return;
  const g = fixtures[selectedFixture].group;
  if (!g) return;
  selectGroup(g);
}

function selectGroup(g) {
  selectedGroup = g;
  selectedFixture = null;
  document.getElementById('fixture-form').style.display = 'none';
  showGroupForm(g);
  drawGrid();
}

function showGroupForm(g) {
  const members = fixtures.filter(f => f.group === g);
  document.getElementById('group-form').style.display = 'block';
  document.getElementById('group-name-display').textContent = `${g} (${members.length})`;
  document.getElementById('group-members').textContent = members.map(f => f.name).join(', ');
}

function ungroupSelected() {
  if (selectedGroup === null) return;
  fixtures.forEach(f => { if (f.group === selectedGroup) f.group = ''; });
  selectedGroup = null;
  document.getElementById('group-form').style.display = 'none';
  drawGrid();
}

function bulkSetLength() {
  if (selectedGroup === null) return;
  const len = +document.getElementById('g-length').value;
  fixtures.forEach(f => { if (f.group === selectedGroup) f.length = len; });
  drawGrid();
  showGroupForm(selectedGroup);
}

function bulkSetUniverse() {
  if (selectedGroup === null) return;
  const u = +document.getElementById('g-universe').value;
  fixtures.forEach(f => { if (f.group === selectedGroup) f.universe = u; });
  showGroupForm(selectedGroup);
}

function bulkSetNamePrefix() {
  if (selectedGroup === null) return;
  const prefix = document.getElementById('g-name-prefix').value.trim();
  if (!prefix) return;
  let i = 0;
  fixtures.forEach(f => { if (f.group === selectedGroup) { i++; f.name = `${prefix}_${i}`; } });
  showGroupForm(selectedGroup);
}

function rotateGroup() {
  if (selectedGroup === null) return;
  const members = fixtures.filter(f => f.group === selectedGroup);
  const {cx, cy} = groupBoundingBox(members);

  members.forEach(f => {
    const len = f.length || 40;
    const horiz = isHorizontal(f.orientation);
    const w = horiz ? len : 4;
    const h = horiz ? 4 : len;
    const centerX = f.x + w / 2, centerY = f.y + h / 2;

    // Screen-space 90deg clockwise point rotation around (cx, cy): (dx,dy) -> (-dy,dx)
    const newCenterX = cx - (centerY - cy);
    const newCenterY = cy + (centerX - cx);

    f.orientation = ROTATE_CW[f.orientation];
    const newHoriz = isHorizontal(f.orientation);
    const newW = newHoriz ? len : 4;
    const newH = newHoriz ? 4 : len;
    f.x = Math.round(newCenterX - newW / 2);
    f.y = Math.round(newCenterY - newH / 2);
  });

  drawGrid();
  showGroupForm(selectedGroup);
}

function uniqueGroupName(base) {
  const existing = new Set(fixtures.map(f => f.group).filter(g => g));
  let candidate = `${base}_copy`;
  let n = 2;
  while (existing.has(candidate)) {
    candidate = `${base}_copy${n}`;
    n++;
  }
  return candidate;
}

function copyGroup() {
  if (selectedGroup === null) return;
  const members = fixtures.filter(f => f.group === selectedGroup);
  const newGroupName = uniqueGroupName(selectedGroup);
  const copies = members.map(f => ({...f, name: `${f.name}_copy`, group: newGroupName, universe: f.universe + 1}));
  fixtures.push(...copies);
  selectGroup(newGroupName);
}

function applyFixture() {
  if (selectedFixture === null) return;
  fixtures[selectedFixture] = {
    name: document.getElementById('f-name').value,
    group: document.getElementById('f-group').value.trim(),
    x: +document.getElementById('f-x').value,
    y: +document.getElementById('f-y').value,
    orientation: document.getElementById('f-orient').value,
    length: fixtures[selectedFixture].length ?? 40,
    universe: +document.getElementById('f-universe').value,
    start_channel: +document.getElementById('f-ch').value,
  };
  drawGrid();
}

function saveFixtures() {
  send({type:'save_fixtures', canvas: canvasSize, fixtures});
}

document.addEventListener('keydown', e => {
  if (!document.getElementById('page-fixtures').classList.contains('active')) return;
  if (['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)) return;

  if (e.key === '+') { e.preventDefault(); addStrip(); return; }
  if (e.key === 'Delete') { e.preventDefault(); deleteStrip(); return; }

  if (e.key === 'Tab') {
    e.preventDefault();
    if (fixtures.length === 0) return;
    selectedGroup = null;
    selectedFixture = selectedFixture === null ? 0 : (selectedFixture + 1) % fixtures.length;
    showFixtureForm(fixtures[selectedFixture]);
    drawGrid();
    return;
  }

  if (e.key === 'Escape') {
    e.preventDefault();
    selectedFixture = null;
    selectedGroup = null;
    document.getElementById('fixture-form').style.display = 'none';
    document.getElementById('group-form').style.display = 'none';
    drawGrid();
    return;
  }

  const step = e.shiftKey ? 10 : 1;

  if (selectedGroup !== null) {
    if (e.key === 'ArrowUp')         { e.preventDefault(); fixtures.forEach(f => { if (f.group === selectedGroup) f.y -= step; }); }
    else if (e.key === 'ArrowDown')  { e.preventDefault(); fixtures.forEach(f => { if (f.group === selectedGroup) f.y += step; }); }
    else if (e.key === 'ArrowLeft')  { e.preventDefault(); fixtures.forEach(f => { if (f.group === selectedGroup) f.x -= step; }); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); fixtures.forEach(f => { if (f.group === selectedGroup) f.x += step; }); }
    else return;
    drawGrid();
    return;
  }

  if (selectedFixture === null) return;
  const f = fixtures[selectedFixture];

  if (e.key === '#') {
    e.preventDefault();
    const idx = ORIENTATIONS.indexOf(f.orientation);
    f.orientation = ORIENTATIONS[(idx + 1) % ORIENTATIONS.length];
  }
  else if (e.key === 'ArrowUp')    { e.preventDefault(); f.y -= step; }
  else if (e.key === 'ArrowDown')  { e.preventDefault(); f.y += step; }
  else if (e.key === 'ArrowLeft')  { e.preventDefault(); f.x -= step; }
  else if (e.key === 'ArrowRight') { e.preventDefault(); f.x += step; }
  else return;

  showFixtureForm(f);
  drawGrid();
});

// ── MIDI Routing ──────────────────────────────────────────────────────────────
let localAssignments = {};
let learningTarget = null;

function buildMidiTable(assignments) {
  localAssignments = JSON.parse(JSON.stringify(assignments));
  const tbody = document.getElementById('midi-tbody');
  tbody.innerHTML = '';
  Object.entries(assignments).forEach(([name, asgn]) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${name}</td>
      <td>${asgn.type}</td>
      <td>${asgn.number}</td>
      <td>${asgn.channel}</td>
      <td><button class="learn-btn ${learningTarget===name?'learning':''}"
          onclick="startLearn('${name}',this)">${learningTarget===name?'Listening…':'Learn'}</button></td>`;
    tbody.appendChild(tr);
  });
}

function startLearn(target, btn) {
  learningTarget = target;
  document.querySelectorAll('.learn-btn').forEach(b => b.classList.remove('learning'));
  btn.classList.add('learning');
  send({type:'learn_start', target});
}

function toggleStrobe() {
  send({type: 'set_strobe', active: !state.strobe_active});
}

function saveAssignments() {
  send({type:'save_assignments', assignments: localAssignments});
}

function resetAssignments() {
  send({type:'save_assignments', assignments: {}});
}

function saveSetup(tab) {
  const name = document.getElementById('setup-name-'+tab).value.trim();
  if (!name) return;
  send({type:'save_setup', name, canvas: canvasSize, fixtures, assignments: state.assignments||{}});
}

function loadSetup(tab) {
  const sel = document.getElementById('setup-select-'+tab);
  if (!sel.value) return;
  send({type:'load_setup', name: sel.value});
}

let lastSetupNames = null;
function populateSetupSelects(names) {
  const serialized = JSON.stringify(names);
  if (lastSetupNames !== null && serialized === lastSetupNames) return;
  lastSetupNames = serialized;
  ['fixtures','midi'].forEach(tab => {
    const sel = document.getElementById('setup-select-'+tab);
    if (!sel) return;
    const current = sel.value;
    sel.innerHTML = '';
    names.forEach(n => {
      const opt = document.createElement('option');
      opt.value = n; opt.textContent = n;
      sel.appendChild(opt);
    });
    if (names.includes(current)) sel.value = current;
  });
}

// ── Init ──────────────────────────────────────────────────────────────────────
buildPresets();
drawGrid();
connect();
setInterval(() => {
  const img = document.getElementById('preview');
  img.src = '/preview?' + Date.now();
}, 100);
