const state = { mode: 'state', imageData: null, imageMime: null };
const $ = (id) => document.getElementById(id);

function setMode(mode) {
  state.mode = mode;
  document.querySelectorAll('.mode-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.mode === mode));
  $('statePanel').classList.toggle('hidden', mode !== 'state');
  $('transferPanel').classList.toggle('hidden', mode !== 'transfer');
  $('imagePanel').classList.toggle('hidden', mode !== 'image');
  $('status').textContent = '';
  $('status').className = 'status';
}

document.querySelectorAll('.mode-btn').forEach(btn => btn.addEventListener('click', () => setMode(btn.dataset.mode)));

$('imageFile').addEventListener('change', (e) => {
  const file = e.target.files?.[0];
  if (!file) {
    state.imageData = null;
    state.imageMime = null;
    $('previewWrap').classList.add('hidden');
    return;
  }
  state.imageMime = file.type || 'image/png';
  const reader = new FileReader();
  reader.onload = () => {
    state.imageData = String(reader.result).split(',')[1];
    $('imagePreview').src = String(reader.result);
    $('previewWrap').classList.remove('hidden');
  };
  reader.readAsDataURL(file);
});

function renderLatex(el, latex, display = true) {
  if (!window.katex) {
    setTimeout(() => renderLatex(el, latex, display), 50);
    return;
  }
  katex.render(latex, el, { throwOnError: false, displayMode: display });
}

function clearResults() {
  $('emptyState').classList.add('hidden');
  $('results').classList.remove('hidden');
}

function factorCard(name, latex) {
  const node = $('factorTemplate').content.cloneNode(true);
  node.querySelector('.factor-name').textContent = `${name}(s)：`;
  renderLatex(node.querySelector('.factor-latex'), latex);
  return node;
}

function verifyCard(title, latex) {
  const article = document.createElement('article');
  article.className = 'verify-card card';
  const t = document.createElement('div');
  t.className = 'verify-title';
  t.textContent = title;
  const body = document.createElement('div');
  renderLatex(body, latex);
  article.append(t, body);
  return article;
}

function showResult(data) {
  clearResults();
  const d = data.dimensions;
  $('dimensionText').textContent = `系統維度：${d.state_order} 階 × ${d.inputs} 輸入 × ${d.outputs} 輸出`;
  $('recognizedText').classList.toggle('hidden', !data.recognized_g);
  if (data.recognized_g) $('recognizedText').textContent = `AI 辨識結果：${data.recognized_g}`;

  renderLatex($('fLatex'), data.F_latex, false);
  renderLatex($('lLatex'), data.L_latex, false);

  const rf = $('rightFactors');
  const lf = $('leftFactors');
  rf.replaceChildren();
  lf.replaceChildren();
  [['M',data.factors.M],['N',data.factors.N],['X',data.factors.X],['Y',data.factors.Y]].forEach(([n,l]) => rf.appendChild(factorCard(n,l)));
  [['X̃',data.factors.X_tilde],['Ỹ',data.factors.Y_tilde],['Ñ',data.factors.N_tilde],['M̃',data.factors.M_tilde]].forEach(([n,l]) => lf.appendChild(factorCard(n,l)));

  renderLatex($('identityEq'), String.raw`\begin{bmatrix} \tilde{X}(s) & \tilde{Y}(s) \\ \tilde{N}(s) & \tilde{M}(s) \end{bmatrix} \begin{bmatrix} M(s) & Y(s) \\ N(s) & X(s) \end{bmatrix} = \begin{bmatrix} I & 0 \\ 0 & I \end{bmatrix}`);
  const eqs = $('equations');
  eqs.replaceChildren();
  eqs.appendChild(verifyCard('1. 左上項：X̃M + ỸN =', data.equations.eq1));
  eqs.appendChild(verifyCard('2. 右上項：X̃Y + ỸX =', data.equations.eq2));
  eqs.appendChild(verifyCard('3. 左下項：ÑM + M̃N =', data.equations.eq3));
  eqs.appendChild(verifyCard('4. 右下項：ÑY + M̃X =', data.equations.eq4));
  window.scrollTo({ top: $('results').offsetTop - 20, behavior: 'smooth' });
}

$('calculateBtn').addEventListener('click', async () => {
  const button = $('calculateBtn');
  const status = $('status');
  button.disabled = true;
  button.textContent = state.mode === 'image' ? 'AI 辨識與計算中…' : '計算中…';
  status.textContent = '';
  status.className = 'status';

  const payload = {
    mode: state.mode,
    pole_text: $('poles').value,
    A: $('A').value,
    B: $('B').value,
    C: $('C').value,
    D: $('D').value,
    g_str: $('gstr').value,
    image_base64: state.imageData,
    image_mime: state.imageMime,
    api_key: $('apiKey').value,
  };

  try {
    const res = await fetch('/api/calculate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '計算失敗。');
    showResult(data);
    status.textContent = '計算完成。';
    status.className = 'status success';
  } catch (err) {
    status.textContent = `❌ ${err.message}`;
    status.className = 'status error';
  } finally {
    button.disabled = false;
    button.textContent = state.mode === 'image' ? '開始 AI 辨識並計算' : '開始計算';
  }
});

setMode('state');
