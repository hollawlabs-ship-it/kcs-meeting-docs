"""연구회 운영위원회 회의자료 자동생성 서비스 (FastAPI)."""
from __future__ import annotations

import io
import json
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageOps

from . import auth, db as D, docgen

APP_DIR = Path(__file__).resolve().parent
app = FastAPI(title="연구회 운영위원회 회의자료 생성기")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
templates.env.globals.update(KIND_LABELS=docgen.KIND_LABELS, ITEM_TYPE_LABELS=docgen.ITEM_TYPE_LABELS)

D.init_db(auth.hash_password)
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
app.mount("/uploads", StaticFiles(directory=str(D.UPLOAD_DIR)), name="uploads")


@app.exception_handler(auth.RedirectToLogin)
async def _redirect_login(request: Request, exc: auth.RedirectToLogin):
    return RedirectResponse(exc.headers["Location"], status_code=303)


def render(request: Request, name: str, **ctx) -> HTMLResponse:
    session = auth.read_session(request)
    with D.db() as conn:
        settings = D.all_settings(conn)
    return templates.TemplateResponse(request, name, {"session": session, "settings": settings, **ctx})


def set_cookie(resp: Response, payload: dict, request: Request | None = None) -> Response:
    secure = bool(request) and (
        request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https")
    resp.set_cookie(auth.COOKIE_NAME, auth.make_session(payload), max_age=auth.SESSION_MAX_AGE,
                    httponly=True, samesite="lax", secure=secure)
    return resp


@app.get("/healthz")
def healthz():
    return {"ok": True}


# ================================================================ 공통/로그인
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    s = auth.read_session(request)
    if s and s.get("role") == "admin":
        return RedirectResponse("/admin", status_code=303)
    if s and s.get("role") == "group":
        return RedirectResponse("/g", status_code=303)
    return render(request, "home.html")


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, next: str = "/admin"):
    return render(request, "login.html", next=next, error=None)


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), next: str = Form("/admin")):
    with D.db() as conn:
        user = D.row(conn, "SELECT * FROM users WHERE username=?", (username.strip(),))
    if not user or not auth.verify_password(password, user["pw_hash"]):
        return render(request, "login.html", next=next, error="아이디 또는 비밀번호가 올바르지 않습니다.")
    target = next if next.startswith("/") else "/admin"
    return set_cookie(RedirectResponse(target, status_code=303), {"role": "admin", "username": user["username"]}, request)


@app.get("/logout")
def logout():
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie(auth.COOKIE_NAME)
    return resp


@app.get("/g/login", response_class=HTMLResponse)
def group_login_form(request: Request, next: str = "/g"):
    with D.db() as conn:
        groups = D.rows(conn, "SELECT id, name FROM groups WHERE active=1 ORDER BY sort, id")
    return render(request, "group_login.html", groups=groups, next=next, error=None)


@app.post("/g/login")
def group_login(request: Request, group_id: int = Form(...), password: str = Form(...), next: str = Form("/g")):
    with D.db() as conn:
        g = D.row(conn, "SELECT * FROM groups WHERE id=? AND active=1", (group_id,))
        groups = D.rows(conn, "SELECT id, name FROM groups WHERE active=1 ORDER BY sort, id")
        pw_hash = D.get_setting(conn, "group_pw_hash")
        ver = D.get_setting(conn, "group_pw_ver", "1")
    if not pw_hash:
        return render(request, "group_login.html", groups=groups, next=next,
                      error="연구회 비밀번호가 아직 설정되지 않았습니다. 사무국에 문의하세요.")
    if not g or not auth.verify_password(password, pw_hash):
        return render(request, "group_login.html", groups=groups, next=next, error="비밀번호가 올바르지 않습니다.")
    target = next if next.startswith("/") else "/g"
    return set_cookie(RedirectResponse(target, status_code=303),
                      {"role": "group", "group_id": g["id"], "group_name": g["name"], "v": ver}, request)


# ================================================================ 이미지 업로드
MAX_SIDE = 1600


def save_image(upload: UploadFile) -> str:
    raw = upload.file.read()
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(413, "이미지 파일은 25MB 이하만 업로드할 수 있습니다.")
    try:
        im = Image.open(io.BytesIO(raw))
        im.load()
    except Exception:
        raise HTTPException(400, "이미지 파일(JPG/PNG/GIF/BMP/WebP)만 업로드할 수 있습니다.")
    fmt = (im.format or "PNG").upper()
    if fmt == "GIF" and getattr(im, "n_frames", 1) > 1:
        im.seek(0)
    im = ImageOps.exif_transpose(im)
    if max(im.size) > MAX_SIDE:
        im.thumbnail((MAX_SIDE, MAX_SIDE))
    if fmt in ("JPEG", "JPG") or (fmt == "BMP"):
        ext, save_kw = "jpg", {"format": "JPEG", "quality": 88, "optimize": True}
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
    else:
        ext, save_kw = "png", {"format": "PNG", "optimize": True}
        if im.mode == "P":
            im = im.convert("RGBA")
    name = f"{uuid.uuid4().hex}.{ext}"
    im.save(D.UPLOAD_DIR / name, **save_kw)
    return name


@app.post("/admin/upload")
def admin_upload(request: Request, file: UploadFile = File(...), s=Depends(auth.require_admin)):
    name = save_image(file)
    return {"file": name, "url": docgen.image_url(name)}


@app.post("/g/upload")
def group_upload(request: Request, file: UploadFile = File(...), s=Depends(auth.require_group)):
    name = save_image(file)
    return {"file": name, "url": docgen.image_url(name)}


# ================================================================ 관리자
@app.get("/admin", response_class=HTMLResponse)
def admin_home(request: Request, s=Depends(auth.require_admin)):
    with D.db() as conn:
        meetings = D.rows(conn, "SELECT * FROM meetings ORDER BY term DESC, seq DESC")
        n_groups = conn.execute("SELECT COUNT(*) FROM groups WHERE active=1").fetchone()[0]
        for m in meetings:
            m["n_submitted"] = conn.execute(
                "SELECT COUNT(*) FROM reports r JOIN groups g ON g.id=r.group_id "
                "WHERE r.meeting_id=? AND r.submitted=1 AND g.active=1", (m["id"],)).fetchone()[0]
            m["n_draft"] = conn.execute(
                "SELECT COUNT(*) FROM reports r JOIN groups g ON g.id=r.group_id "
                "WHERE r.meeting_id=? AND r.submitted=0 AND g.active=1", (m["id"],)).fetchone()[0]
    return render(request, "admin/dashboard.html", meetings=meetings, n_groups=n_groups)


@app.get("/admin/settings", response_class=HTMLResponse)
def settings_form(request: Request, s=Depends(auth.require_admin), msg: str = ""):
    with D.db() as conn:
        st = D.all_settings(conn)
    return render(request, "admin/settings.html", st=st, msg=msg, group_pw_set=bool(st.get("group_pw_hash")),
                  logo_url=docgen.image_url(docgen.logo_ref(st)),
                  term_image_url=docgen.image_url(docgen.term_image_ref(st)))


@app.post("/admin/settings")
def settings_save(
    request: Request, s=Depends(auth.require_admin),
    society_name: str = Form(""), society_name_en: str = Form(""), term: str = Form("53"),
    president_name: str = Form(""), president_affiliation: str = Form(""), cover_note: str = Form(""),
    logo: UploadFile | None = File(None), term_image: UploadFile | None = File(None),
    reset_logo: str = Form(""), reset_term_image: str = Form(""),
):
    with D.db() as conn:
        for k, v in {
            "society_name": society_name, "society_name_en": society_name_en, "term": term.strip(),
            "president_name": president_name, "president_affiliation": president_affiliation,
            "cover_note": cover_note,
        }.items():
            D.set_setting(conn, k, v.strip())
        if reset_logo:
            D.set_setting(conn, "logo_file", "")
        elif logo and logo.filename:
            D.set_setting(conn, "logo_file", save_image(logo))
        if reset_term_image:
            D.set_setting(conn, "term_image_file", "")
        elif term_image and term_image.filename:
            D.set_setting(conn, "term_image_file", save_image(term_image))
    return RedirectResponse("/admin/settings?msg=saved", status_code=303)


@app.post("/admin/password")
def change_password(request: Request, s=Depends(auth.require_admin),
                    current: str = Form(...), new1: str = Form(...), new2: str = Form(...)):
    with D.db() as conn:
        user = D.row(conn, "SELECT * FROM users WHERE username=?", (s["username"],))
        if not user or not auth.verify_password(current, user["pw_hash"]):
            return RedirectResponse("/admin/settings?msg=pw_wrong", status_code=303)
        if new1 != new2 or len(new1) < 6:
            return RedirectResponse("/admin/settings?msg=pw_mismatch", status_code=303)
        conn.execute("UPDATE users SET pw_hash=? WHERE id=?", (auth.hash_password(new1), user["id"]))
    return RedirectResponse("/admin/settings?msg=pw_changed", status_code=303)


@app.post("/admin/group-password")
def change_group_password(request: Request, s=Depends(auth.require_admin),
                          gpw1: str = Form(...), gpw2: str = Form(...)):
    if gpw1 != gpw2 or len(gpw1) < 4:
        return RedirectResponse("/admin/settings?msg=gpw_mismatch", status_code=303)
    with D.db() as conn:
        D.set_setting(conn, "group_pw_hash", auth.hash_password(gpw1))
        ver = int(D.get_setting(conn, "group_pw_ver", "1") or 1) + 1
        D.set_setting(conn, "group_pw_ver", str(ver))
    return RedirectResponse("/admin/settings?msg=gpw_changed", status_code=303)


# ---- 위원회 명단
@app.get("/admin/committee", response_class=HTMLResponse)
def committee_page(request: Request, s=Depends(auth.require_admin)):
    with D.db() as conn:
        members = D.rows(conn, "SELECT * FROM committee_members ORDER BY sort, id")
        st = D.all_settings(conn)
    return render(request, "admin/committee.html", members=members, st=st)


@app.post("/admin/committee")
async def committee_save(request: Request, s=Depends(auth.require_admin)):
    payload = await request.json()
    items = payload.get("members", [])
    with D.db() as conn:
        conn.execute("DELETE FROM committee_members")
        for i, m in enumerate(items):
            if not (m.get("name") or m.get("role")):
                continue
            conn.execute("INSERT INTO committee_members(role, name, affiliation, sort) VALUES(?,?,?,?)",
                         (m.get("role", "").strip(), m.get("name", "").strip(), m.get("affiliation", "").strip(), i))
    return {"ok": True}


# ---- 연구회 명단
@app.get("/admin/groups", response_class=HTMLResponse)
def groups_page(request: Request, s=Depends(auth.require_admin)):
    with D.db() as conn:
        groups = D.rows(conn, "SELECT * FROM groups ORDER BY sort, id")
    return render(request, "admin/groups.html", groups=groups)


@app.post("/admin/groups")
async def groups_save(request: Request, s=Depends(auth.require_admin)):
    payload = await request.json()
    items = payload.get("groups", [])
    keep_ids = []
    with D.db() as conn:
        for i, g in enumerate(items):
            name = (g.get("name") or "").strip()
            if not name:
                continue
            vals = (name, (g.get("chair_name") or "").strip(), (g.get("chair_affiliation") or "").strip(),
                    (g.get("secretaries") or "").strip(), 1 if g.get("is_new") else 0,
                    1 if g.get("is_preliminary") else 0, 1 if g.get("active", True) else 0, i)
            gid = g.get("id")
            if gid and conn.execute("SELECT 1 FROM groups WHERE id=?", (gid,)).fetchone():
                conn.execute("UPDATE groups SET name=?, chair_name=?, chair_affiliation=?, secretaries=?, "
                             "is_new=?, is_preliminary=?, active=?, sort=? WHERE id=?", vals + (gid,))
                keep_ids.append(int(gid))
            else:
                cur = conn.execute("INSERT INTO groups(name, chair_name, chair_affiliation, secretaries, is_new, "
                                   "is_preliminary, active, sort, access_code) VALUES(?,?,?,?,?,?,?,?,?)",
                                   vals + (D.new_access_code(),))
                keep_ids.append(cur.lastrowid)
        # 목록에서 제거된 연구회는 삭제(보고서도 함께 삭제됨)
        if keep_ids:
            q = ",".join("?" * len(keep_ids))
            conn.execute(f"DELETE FROM groups WHERE id NOT IN ({q})", keep_ids)
        else:
            conn.execute("DELETE FROM groups")
    return {"ok": True}


# ---- 회의
@app.post("/admin/meetings/new")
def meeting_new(request: Request, s=Depends(auth.require_admin)):
    with D.db() as conn:
        st = D.all_settings(conn)
        term = int(st.get("term") or 53)
        last = D.row(conn, "SELECT * FROM meetings ORDER BY term DESC, seq DESC LIMIT 1")
        seq = (last["seq"] + 1) if last and last["term"] == term else 1
        cur = conn.execute(
            "INSERT INTO meetings(term, seq, title, date_text, place, method, host_name, host_title, "
            "past_label, plan_label, status, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (term, seq, last["title"] if last else "연구회 운영위원회", "", last["place"] if last else "",
             last["method"] if last else "", last["host_name"] if last else "", last["host_title"] if last else "",
             "", "", "open", D.now_iso()))
        mid = cur.lastrowid
        src = D.rows(conn, "SELECT * FROM agenda_items WHERE meeting_id=? ORDER BY sort, id",
                     (last["id"],)) if last else []
        if not src:
            src = [{"kind": k, "title": t, "body": b, "images": "[]"} for k, t, b in D.SEED_AGENDA]
        for i, a in enumerate(src):
            conn.execute("INSERT INTO agenda_items(meeting_id, sort, kind, title, body, images) VALUES(?,?,?,?,?,?)",
                         (mid, i, a["kind"], a["title"], a["body"] if a["kind"] == "text" else "", "[]"))
    return RedirectResponse(f"/admin/meetings/{mid}", status_code=303)


def _meeting_or_404(conn, mid: int) -> dict:
    m = D.row(conn, "SELECT * FROM meetings WHERE id=?", (mid,))
    if not m:
        raise HTTPException(404, "회의를 찾을 수 없습니다.")
    return m


@app.get("/admin/meetings/{mid}", response_class=HTMLResponse)
def meeting_edit(mid: int, request: Request, s=Depends(auth.require_admin), msg: str = ""):
    with D.db() as conn:
        m = _meeting_or_404(conn, mid)
        agenda = D.rows(conn, "SELECT * FROM agenda_items WHERE meeting_id=? ORDER BY sort, id", (mid,))
        for a in agenda:
            a["images"] = D.loads(a["images"], [])
    return render(request, "admin/meeting_edit.html", m=m, agenda=agenda, agenda_json=json.dumps(agenda, ensure_ascii=False), msg=msg)


@app.post("/admin/meetings/{mid}/info")
def meeting_info_save(
    mid: int, request: Request, s=Depends(auth.require_admin),
    term: int = Form(...), seq: int = Form(...), title: str = Form(...), date_text: str = Form(""),
    place: str = Form(""), method: str = Form(""), host_name: str = Form(""), host_title: str = Form(""),
    past_label: str = Form(""), plan_label: str = Form(""), status: str = Form("open"),
):
    with D.db() as conn:
        _meeting_or_404(conn, mid)
        conn.execute(
            "UPDATE meetings SET term=?, seq=?, title=?, date_text=?, place=?, method=?, host_name=?, host_title=?, "
            "past_label=?, plan_label=?, status=? WHERE id=?",
            (term, seq, title.strip(), date_text.strip(), place.strip(), method.strip(), host_name.strip(),
             host_title.strip(), past_label.strip(), plan_label.strip(),
             status if status in ("open", "closed") else "open", mid))
    return RedirectResponse(f"/admin/meetings/{mid}?msg=saved", status_code=303)


@app.post("/admin/meetings/{mid}/agenda")
async def agenda_save(mid: int, request: Request, s=Depends(auth.require_admin)):
    payload = await request.json()
    items = payload.get("items", [])
    with D.db() as conn:
        _meeting_or_404(conn, mid)
        conn.execute("DELETE FROM agenda_items WHERE meeting_id=?", (mid,))
        for i, a in enumerate(items):
            title = (a.get("title") or "").strip()
            if not title:
                continue
            kind = a.get("kind") if a.get("kind") in docgen.KIND_LABELS else "text"
            images = [{"file": im.get("file", ""), "caption": im.get("caption", "")}
                      for im in a.get("images", []) if im.get("file")]
            conn.execute("INSERT INTO agenda_items(meeting_id, sort, kind, title, body, images) VALUES(?,?,?,?,?,?)",
                         (mid, i, kind, title, a.get("body") or "", json.dumps(images, ensure_ascii=False)))
    return {"ok": True}


@app.post("/admin/meetings/{mid}/delete")
def meeting_delete(mid: int, s=Depends(auth.require_admin)):
    with D.db() as conn:
        conn.execute("DELETE FROM meetings WHERE id=?", (mid,))
    return RedirectResponse("/admin", status_code=303)


# ---- 연구회 보고 취합
@app.get("/admin/meetings/{mid}/reports", response_class=HTMLResponse)
def reports_status(mid: int, request: Request, s=Depends(auth.require_admin)):
    with D.db() as conn:
        m = _meeting_or_404(conn, mid)
        groups = D.rows(conn, "SELECT * FROM groups WHERE active=1 ORDER BY sort, id")
        reps = {r["group_id"]: r for r in D.rows(conn, "SELECT * FROM reports WHERE meeting_id=?", (mid,))}
    status = []
    for g in groups:
        r = reps.get(g["id"])
        state = "none"
        if r:
            state = "submitted" if r["submitted"] else "draft"
        status.append({"group": g, "state": state, "updated_at": r["updated_at"] if r else "",
                       "updated_by": r["updated_by"] if r else ""})
    n_sub = sum(1 for x in status if x["state"] == "submitted")
    return render(request, "admin/reports.html", m=m, status=status, n_sub=n_sub, n_total=len(status))


@app.get("/admin/meetings/{mid}/reports/{gid}", response_class=HTMLResponse)
def admin_report_edit(mid: int, gid: int, request: Request, s=Depends(auth.require_admin)):
    return _report_editor(request, mid, gid, admin=True)


@app.post("/admin/meetings/{mid}/reports/{gid}")
async def admin_report_save(mid: int, gid: int, request: Request, s=Depends(auth.require_admin)):
    return await _report_save(request, mid, gid, by=f"관리자({s['username']})")


# ---- 문서 출력
def _doc_html(request: Request | None, mid: int, inline: bool, mode: str) -> str:
    with D.db() as conn:
        ctx = docgen.meeting_context(conn, mid, inline_images=inline)
    tpl = templates.get_template("doc.html")
    return tpl.render(**ctx, mode=mode)


@app.get("/admin/meetings/{mid}/doc", response_class=HTMLResponse)
def doc_preview(mid: int, request: Request, s=Depends(auth.require_admin)):
    with D.db() as conn:
        _meeting_or_404(conn, mid)
    return HTMLResponse(_doc_html(request, mid, inline=False, mode="preview"))


@app.get("/admin/meetings/{mid}/pdf")
def doc_pdf(mid: int, request: Request, s=Depends(auth.require_admin), inline: int = 0):
    with D.db() as conn:
        m = _meeting_or_404(conn, mid)
        st = D.all_settings(conn)
        footer_logo = docgen.image_data_uri(docgen.logo_ref(st))
    html = _doc_html(request, mid, inline=True, mode="pdf")
    try:
        pdf = docgen.render_pdf(html, footer_logo, f"제{m['term']}-{m['seq']}차")
    except Exception as e:  # Playwright 미설치 등
        raise HTTPException(500, f"PDF 생성 실패: {e}. 'python -m playwright install chromium' 실행 여부를 확인하세요.")
    fname = f"{st.get('society_name', '한국언론학회')}_제{m['term']}-{m['seq']}차_{m['title']}_회의자료.pdf"
    from urllib.parse import quote
    disp = "inline" if inline else "attachment"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"{disp}; filename*=UTF-8''{quote(fname)}"})


# ================================================================ 연구회
def _session_group(s: dict, conn) -> dict | None:
    if s.get("role") == "group":
        return D.row(conn, "SELECT * FROM groups WHERE id=?", (s["group_id"],))
    return None


@app.get("/g", response_class=HTMLResponse)
def group_home(request: Request, s=Depends(auth.require_group)):
    if s.get("role") == "admin":
        return RedirectResponse("/admin", status_code=303)
    with D.db() as conn:
        g = _session_group(s, conn)
        if not g:
            return RedirectResponse("/logout", status_code=303)
        meetings = D.rows(conn, "SELECT * FROM meetings ORDER BY term DESC, seq DESC")
        reps = {r["meeting_id"]: r for r in D.rows(conn, "SELECT * FROM reports WHERE group_id=?", (g["id"],))}
    for m in meetings:
        r = reps.get(m["id"])
        m["state"] = ("submitted" if r["submitted"] else "draft") if r else "none"
        m["updated_at"] = r["updated_at"] if r else ""
    return render(request, "group/home.html", g=g, meetings=meetings)


@app.get("/g/meetings/{mid}", response_class=HTMLResponse)
def group_report_edit(mid: int, request: Request, s=Depends(auth.require_group)):
    if s.get("role") != "group":
        return RedirectResponse("/admin", status_code=303)
    return _report_editor(request, mid, s["group_id"], admin=False)


@app.post("/g/meetings/{mid}")
async def group_report_save(mid: int, request: Request, s=Depends(auth.require_group)):
    if s.get("role") != "group":
        raise HTTPException(403)
    with D.db() as conn:
        m = _meeting_or_404(conn, mid)
    if m["status"] != "open":
        raise HTTPException(403, "입력이 마감된 회의입니다. 사무국(관리자)에 문의하세요.")
    return await _report_save(request, mid, s["group_id"], by=s.get("group_name", "연구회"))


@app.get("/g/meetings/{mid}/preview", response_class=HTMLResponse)
def group_report_preview(mid: int, request: Request, s=Depends(auth.require_group), gid: int | None = None):
    if s.get("role") == "group":
        gid = s["group_id"]
    if gid is None:
        raise HTTPException(400)
    with D.db() as conn:
        ctx = docgen.meeting_context(conn, mid, inline_images=False)
    ctx["group_reports"] = [gr for gr in ctx["group_reports"] if gr["group"]["id"] == gid]
    tpl = templates.get_template("doc.html")
    return HTMLResponse(tpl.render(**ctx, mode="report_preview"))


def _report_editor(request: Request, mid: int, gid: int, admin: bool) -> HTMLResponse:
    with D.db() as conn:
        m = _meeting_or_404(conn, mid)
        g = D.row(conn, "SELECT * FROM groups WHERE id=?", (gid,))
        if not g:
            raise HTTPException(404)
        rep = D.row(conn, "SELECT * FROM reports WHERE meeting_id=? AND group_id=?", (mid, gid))
    data = D.loads(rep["data"], None) if rep else None
    if not data:
        data = D.empty_report(g)
    if admin:
        urls = {"save": f"/admin/meetings/{mid}/reports/{gid}", "upload": "/admin/upload",
                "preview": f"/g/meetings/{mid}/preview?gid={gid}", "back": f"/admin/meetings/{mid}/reports"}
    else:
        urls = {"save": f"/g/meetings/{mid}", "upload": "/g/upload",
                "preview": f"/g/meetings/{mid}/preview", "back": "/g"}
    return render(request, "report_edit.html", m=m, g=g, data_json=json.dumps(data, ensure_ascii=False),
                  submitted=bool(rep and rep["submitted"]), urls=urls, is_admin=admin,
                  readonly=(not admin and m["status"] != "open"))


async def _report_save(request: Request, mid: int, gid: int, by: str):
    payload = await request.json()
    data = payload.get("data") or {}
    submitted = 1 if payload.get("submitted") else 0
    clean = {
        "chair": str(data.get("chair", "")).strip(),
        "secretaries": str(data.get("secretaries", "")).strip(),
        "no_report": bool(data.get("no_report")),
        "past": _clean_half(data.get("past")),
        "plan": _clean_half(data.get("plan")),
    }
    with D.db() as conn:
        _meeting_or_404(conn, mid)
        conn.execute(
            "INSERT INTO reports(meeting_id, group_id, data, submitted, updated_at, updated_by) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(meeting_id, group_id) DO UPDATE SET data=excluded.data, submitted=excluded.submitted, "
            "updated_at=excluded.updated_at, updated_by=excluded.updated_by",
            (mid, gid, json.dumps(clean, ensure_ascii=False), submitted, D.now_iso(), by))
    return {"ok": True, "submitted": submitted}


def _clean_half(sec) -> dict:
    sec = sec or {}
    items = []
    for it in sec.get("items", []) or []:
        t = it.get("type") if it.get("type") in docgen.ITEM_TYPE_LABELS else "other"
        clean = {"type": t, "title": str(it.get("title", "")).strip(), "desc": str(it.get("desc", "")),
                 "date": str(it.get("date", "")).strip(), "place": str(it.get("place", "")).strip()}
        if t == "conference":
            sessions = []
            for ss in it.get("sessions", []) or []:
                talks = [{"title": str(tk.get("title", "")).strip(), "presenter": str(tk.get("presenter", "")).strip(),
                          "discussant": str(tk.get("discussant", "")).strip()}
                         for tk in ss.get("talks", []) or []
                         if (tk.get("title") or tk.get("presenter"))]
                sessions.append({"name": str(ss.get("name", "")).strip(), "moderator": str(ss.get("moderator", "")).strip(),
                                 "talks": talks, "roundtable": str(ss.get("roundtable", "")).strip()})
            clean["sessions"] = sessions
        elif t == "event":
            for k in ("moderator", "presenters", "discussants"):
                clean[k] = str(it.get(k, "")).strip()
        elif t == "publication":
            for k in ("authors", "publisher"):
                clean[k] = str(it.get(k, "")).strip()
        items.append(clean)
    images = [{"file": Path(str(im.get("file", ""))).name, "caption": str(im.get("caption", "")).strip()}
              for im in sec.get("images", []) or [] if im.get("file")]
    return {"intro": str(sec.get("intro", "")), "items": items, "images": images}
