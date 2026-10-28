// 공통 유틸: HTML 이스케이프, JSON POST, 이미지 업로드, 토스트, 드래그 정렬
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
async function postJSON(url, body) {
  try {
    const r = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    const j = await r.json().catch(() => ({}));
    if (!r.ok) return {ok: false, detail: j.detail || r.statusText};
    return j;
  } catch (e) { return {ok: false, detail: String(e)}; }
}
async function uploadImage(url, file) {
  const fd = new FormData(); fd.append('file', file);
  try {
    const r = await fetch(url, {method: 'POST', body: fd});
    const j = await r.json().catch(() => ({}));
    if (!r.ok) return {detail: j.detail || r.statusText};
    return j;
  } catch (e) { return {detail: String(e)}; }
}
function toast(msg, ms = 2200) {
  let t = document.getElementById('toast');
  if (!t) { t = document.createElement('div'); t.id = 'toast'; document.body.appendChild(t); }
  t.textContent = msg; t.classList.add('show');
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('show'), ms);
}
// 표 행(tr) 드래그 정렬 + ▲▼/✕ 버튼
function makeSortable(tbody) {
  let dragging = null;
  tbody.addEventListener('dragstart', e => { dragging = e.target.closest('tr'); e.dataTransfer.effectAllowed = 'move'; });
  tbody.addEventListener('dragover', e => {
    e.preventDefault(); const tr = e.target.closest('tr'); if (!tr || tr === dragging) return;
    const r = tr.getBoundingClientRect();
    tbody.insertBefore(dragging, (e.clientY - r.top) > r.height / 2 ? tr.nextSibling : tr);
  });
  tbody.addEventListener('click', e => {
    const tr = e.target.closest('tr'); if (!tr) return;
    if (e.target.classList.contains('del')) { if (confirm('이 행을 삭제할까요?')) tr.remove(); }
    else if (e.target.classList.contains('up') && tr.previousElementSibling) tbody.insertBefore(tr, tr.previousElementSibling);
    else if (e.target.classList.contains('down') && tr.nextElementSibling) tbody.insertBefore(tr.nextElementSibling, tr);
  });
}
// 블록(div) 드래그 정렬. 드롭 후 onDrop() 호출
function makeSortableBlocks(container, onDrop) {
  let dragging = null;
  container.addEventListener('dragstart', e => {
    const blk = e.target.closest('[draggable="true"]');
    if (!blk || e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') { e.preventDefault(); return; }
    dragging = blk; e.dataTransfer.effectAllowed = 'move';
  });
  container.addEventListener('dragover', e => {
    e.preventDefault(); const blk = e.target.closest('[draggable="true"]'); if (!blk || blk === dragging || !dragging) return;
    const r = blk.getBoundingClientRect();
    container.insertBefore(dragging, (e.clientY - r.top) > r.height / 2 ? blk.nextSibling : blk);
  });
  container.addEventListener('drop', e => { e.preventDefault(); if (dragging) { dragging = null; onDrop(); } });
  container.addEventListener('dragend', () => { if (dragging) { dragging = null; onDrop(); } });
}
