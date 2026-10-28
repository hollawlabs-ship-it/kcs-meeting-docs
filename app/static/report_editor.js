// 연구회 활동보고 편집기: 상태(state)를 폼에 그리고, 저장 시 JSON으로 전송
(function () {
  const R = window.REPORT;
  const state = R.data;
  for (const h of ['past', 'plan']) {
    state[h] = state[h] || {intro: '', items: [], images: []};
    state[h].items = state[h].items || []; state[h].images = state[h].images || [];
  }
  let dirty = false;
  const markDirty = () => { dirty = true; };

  const TYPE_LABEL = {conference: '정기학술대회 세션', event: '세미나·워크숍·특강', publication: '출판·저술', other: '기타 활동'};

  document.getElementById('f-chair').value = state.chair || '';
  document.getElementById('f-secs').value = state.secretaries || '';
  document.getElementById('f-noreport').checked = !!state.no_report;

  function talkRow(t, si, ti) {
    return `<div class="talk" data-si="${si}" data-ti="${ti}">
      <span class="talk-no">발제 ${ti + 1}</span>
      <input class="t-title" placeholder="발표 제목" value="${esc(t.title || '')}">
      <input class="t-presenter" placeholder="발표자(소속)" value="${esc(t.presenter || '')}">
      <input class="t-discussant" placeholder="토론자(소속)" value="${esc(t.discussant || '')}">
      <button class="btn btn-sm del-talk" title="발제 삭제">✕</button></div>`;
  }
  function sessionBlock(s, si) {
    return `<div class="session" data-si="${si}">
      <div class="session-head">
        <input class="s-name" placeholder="세션명 (예: 1부, 세션 1)" value="${esc(s.name || '')}">
        <input class="s-mod" placeholder="사회(소속)" value="${esc(s.moderator || '')}">
        <button class="btn btn-sm del-session" title="세션 삭제">세션 삭제</button>
      </div>
      <div class="talks">${(s.talks || []).map((t, ti) => talkRow(t, si, ti)).join('')}</div>
      <button class="btn btn-sm add-talk">+ 발제 추가</button>
      <input class="s-round" placeholder="종합토론 / 라운드테이블 (선택)" value="${esc(s.roundtable || '')}">
    </div>`;
  }
  function itemHtml(it, i) {
    let fields = '';
    if (it.type === 'conference') {
      fields = `
        <div class="row2">
          <input class="f-date" placeholder="일시 (예: 2026년 10월 17일(토))" value="${esc(it.date || '')}">
          <input class="f-place" placeholder="장소 (예: ○○대학교)" value="${esc(it.place || '')}">
        </div>
        <div class="sessions">${(it.sessions || []).map(sessionBlock).join('')}</div>
        <button class="btn btn-sm add-session">+ 세션(부) 추가</button>
        <textarea class="f-desc" rows="2" placeholder="비고·추가 설명 (선택)">${esc(it.desc || '')}</textarea>`;
    } else if (it.type === 'event') {
      fields = `
        <div class="row2">
          <input class="f-date" placeholder="일시" value="${esc(it.date || '')}">
          <input class="f-place" placeholder="장소" value="${esc(it.place || '')}">
        </div>
        <div class="row3">
          <input class="f-moderator" placeholder="사회" value="${esc(it.moderator || '')}">
          <input class="f-presenters" placeholder="발제·발표자" value="${esc(it.presenters || '')}">
          <input class="f-discussants" placeholder="토론자" value="${esc(it.discussants || '')}">
        </div>
        <textarea class="f-desc" rows="3" placeholder="주제·내용 설명 (선택, 줄바꿈 가능)">${esc(it.desc || '')}</textarea>`;
    } else if (it.type === 'publication') {
      fields = `
        <div class="row3">
          <input class="f-authors" placeholder="저자" value="${esc(it.authors || '')}">
          <input class="f-publisher" placeholder="출판사" value="${esc(it.publisher || '')}">
          <input class="f-date" placeholder="출간일 (예: 2026.9.24 / 예정)" value="${esc(it.date || '')}">
        </div>
        <textarea class="f-desc" rows="3" placeholder="내용 소개 (선택)">${esc(it.desc || '')}</textarea>`;
    } else {
      fields = `
        <div class="row2">
          <input class="f-date" placeholder="일시 (선택)" value="${esc(it.date || '')}">
          <input class="f-place" placeholder="장소 (선택)" value="${esc(it.place || '')}">
        </div>
        <textarea class="f-desc" rows="4" placeholder="내용 (줄바꿈·'- ' 목록 사용 가능)">${esc(it.desc || '')}</textarea>`;
    }
    return `<div class="ritem" data-i="${i}" draggable="true">
      <div class="ritem-head">
        <span class="drag">☰</span>
        <span class="badge">${TYPE_LABEL[it.type] || '기타'}</span>
        <input class="f-title" placeholder="${it.type === 'conference' ? '예: 2026년 가을철 정기학술대회 연구회 세션' : it.type === 'publication' ? '도서·논문 제목' : '활동명'}" value="${esc(it.title || '')}">
        <span class="actions"><button class="btn btn-sm up">▲</button><button class="btn btn-sm down">▼</button><button class="btn btn-sm del">✕</button></span>
      </div>
      <div class="ritem-body">${fields}</div>
    </div>`;
  }
  function imagesHtml(imgs) {
    return imgs.map((im, j) => `<div class="img-chip"><img src="/uploads/${esc(im.file)}">
      <input placeholder="캡션(선택)" value="${esc(im.caption || '')}" data-j="${j}">
      <button class="btn btn-sm del-img" data-j="${j}">✕</button></div>`).join('');
  }

  function renderHalf(h) {
    const sec = document.querySelector(`.half[data-half="${h}"]`);
    sec.querySelector('.intro').value = state[h].intro || '';
    sec.querySelector('.items').innerHTML = state[h].items.map(itemHtml).join('');
    sec.querySelector('.images').innerHTML = imagesHtml(state[h].images);
    if (R.readonly) sec.querySelectorAll('input,textarea,button').forEach(el => el.disabled = true);
  }

  // DOM -> state (한 반기)
  function collectHalf(h) {
    const sec = document.querySelector(`.half[data-half="${h}"]`);
    const items = [...sec.querySelectorAll('.ritem')].map(el => {
      const old = state[h].items[el.dataset.i] || {};
      const v = cls => (el.querySelector('.' + cls) || {}).value || '';
      const it = {type: old.type, title: v('f-title'), date: v('f-date'), place: v('f-place'), desc: v('f-desc')};
      if (it.type === 'conference') {
        it.sessions = [...el.querySelectorAll('.session')].map(se => ({
          name: se.querySelector('.s-name').value, moderator: se.querySelector('.s-mod').value,
          roundtable: se.querySelector('.s-round').value,
          talks: [...se.querySelectorAll('.talk')].map(t => ({
            title: t.querySelector('.t-title').value, presenter: t.querySelector('.t-presenter').value,
            discussant: t.querySelector('.t-discussant').value}))
        }));
      } else if (it.type === 'event') {
        it.moderator = v('f-moderator'); it.presenters = v('f-presenters'); it.discussants = v('f-discussants');
      } else if (it.type === 'publication') {
        it.authors = v('f-authors'); it.publisher = v('f-publisher');
      }
      return it;
    });
    const images = [...sec.querySelectorAll('.img-chip')].map((c, j) => ({file: state[h].images[j].file, caption: c.querySelector('input').value}));
    state[h] = {intro: sec.querySelector('.intro').value, items, images};
  }
  function collectAll() {
    state.chair = document.getElementById('f-chair').value;
    state.secretaries = document.getElementById('f-secs').value;
    state.no_report = document.getElementById('f-noreport').checked;
    collectHalf('past'); collectHalf('plan');
  }

  document.getElementById('halves').addEventListener('click', async e => {
    const sec = e.target.closest('.half'); if (!sec) return;
    const h = sec.dataset.half;
    const btn = e.target.closest('button'); if (!btn) return;
    if (btn.dataset.add) {
      collectHalf(h);
      const t = btn.dataset.add;
      const it = {type: t, title: '', desc: ''};
      if (t === 'conference') it.sessions = [{name: '', moderator: '', talks: [{title: '', presenter: '', discussant: ''}], roundtable: ''}];
      state[h].items.push(it); renderHalf(h); markDirty();
      const last = sec.querySelector('.items').lastElementChild; last.scrollIntoView({behavior: 'smooth', block: 'center'}); last.querySelector('.f-title').focus();
      return;
    }
    const itemEl = e.target.closest('.ritem');
    if (!itemEl) {
      if (btn.classList.contains('del-img')) { collectHalf(h); state[h].images.splice(Number(btn.dataset.j), 1); renderHalf(h); markDirty(); }
      return;
    }
    e.preventDefault();
    collectHalf(h);
    const i = Number(itemEl.dataset.i); const items = state[h].items;
    if (btn.classList.contains('del')) { if (!confirm('이 항목을 삭제할까요?')) return; items.splice(i, 1); }
    else if (btn.classList.contains('up') && i > 0) [items[i - 1], items[i]] = [items[i], items[i - 1]];
    else if (btn.classList.contains('down') && i < items.length - 1) [items[i + 1], items[i]] = [items[i], items[i + 1]];
    else if (btn.classList.contains('add-session')) items[i].sessions.push({name: '', moderator: '', talks: [{title: '', presenter: '', discussant: ''}], roundtable: ''});
    else if (btn.classList.contains('del-session')) { const si = Number(btn.closest('.session').dataset.si); items[i].sessions.splice(si, 1); }
    else if (btn.classList.contains('add-talk')) { const si = Number(btn.closest('.session').dataset.si); items[i].sessions[si].talks.push({title: '', presenter: '', discussant: ''}); }
    else if (btn.classList.contains('del-talk')) { const t = btn.closest('.talk'); items[i].sessions[Number(t.dataset.si)].talks.splice(Number(t.dataset.ti), 1); }
    else return;
    renderHalf(h); markDirty();
  });
  document.getElementById('halves').addEventListener('input', markDirty);
  document.getElementById('halves').addEventListener('change', async e => {
    if (e.target.type !== 'file') return;
    const sec = e.target.closest('.half'); const h = sec.dataset.half;
    collectHalf(h);
    for (const f of e.target.files) {
      const r = await uploadImage(R.urls.upload, f);
      if (r.file) state[h].images.push({file: r.file, caption: ''}); else toast(r.detail || '업로드 실패');
    }
    e.target.value = ''; renderHalf(h); markDirty();
  });
  for (const h of ['past', 'plan']) {
    const box = document.querySelector(`.half[data-half="${h}"] .items`);
    makeSortableBlocks(box, () => {
      const order = [...box.querySelectorAll('.ritem')].map(el => Number(el.dataset.i));
      collectHalfKeepOrder(h, order); renderHalf(h); markDirty();
    });
  }
  function collectHalfKeepOrder(h, order) {
    // DOM 순서가 바뀐 뒤: 먼저 값 수집(원래 index 기준) 후 order로 재배열
    const sec = document.querySelector(`.half[data-half="${h}"]`);
    const byIdx = {};
    [...sec.querySelectorAll('.ritem')].forEach(el => { byIdx[el.dataset.i] = el; });
    collectHalf(h); // collectHalf는 DOM 순서대로 수집하므로 이미 새 순서가 반영됨
  }

  async function save(submitted) {
    collectAll();
    const r = await postJSON(R.urls.save, {data: state, submitted});
    if (r.ok) {
      dirty = false; R.submitted = !!r.submitted;
      const b = document.getElementById('status-badge');
      b.textContent = r.submitted ? '제출 완료' : '작성 중'; b.className = 'badge ' + (r.submitted ? 'ok' : 'warn');
      toast(submitted ? '제출되었습니다. 감사합니다!' : '임시저장되었습니다.');
    } else toast('저장 실패: ' + (r.detail || ''), 4000);
    return r.ok;
  }
  const sd = document.getElementById('save-draft'), ss = document.getElementById('save-submit');
  if (sd) sd.onclick = () => save(false);
  if (ss) ss.onclick = () => { if (confirm('제출 완료로 표시할까요? (마감 전까지 다시 수정할 수 있습니다)')) save(true); };
  document.getElementById('preview-btn').addEventListener('click', async e => {
    if (R.readonly || !dirty) return;
    e.preventDefault();
    if (await save(R.submitted)) window.open(R.urls.preview, '_blank');
  });
  window.addEventListener('beforeunload', e => { if (dirty) { e.preventDefault(); e.returnValue = ''; } });

  renderHalf('past'); renderHalf('plan');
  if (R.readonly) document.querySelectorAll('#f-chair,#f-secs,#f-noreport').forEach(el => el.disabled = true);
})();
