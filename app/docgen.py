"""회의자료 문서 생성: 템플릿 컨텍스트 구성, 마크다운 변환, PDF 출력(Playwright/Chromium)."""
from __future__ import annotations

import base64
import mimetypes
import os
import sqlite3
from pathlib import Path

import markdown

from . import db as D

STATIC_DIR = Path(__file__).resolve().parent / "static"
ROMAN = ["Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ", "Ⅴ", "Ⅵ", "Ⅶ", "Ⅷ", "Ⅸ", "Ⅹ", "Ⅺ", "Ⅻ"]
KIND_LABELS = {
    "opening": "개회 및 성원 보고",
    "greeting": "회장 인사 (자동: 회장 이름·소속)",
    "committee": "위원 소개 (자동: 집행부 위원 표 + 연구회 명단 표)",
    "reports": "연구회별 활동 보고 (자동: 연구회 제출 내용 취합)",
    "text": "일반 안건 (본문 직접 입력)",
    "closing": "폐회",
}
ITEM_TYPE_LABELS = {
    "conference": "정기학술대회 세션",
    "event": "세미나·워크숍·특강",
    "publication": "출판·저술",
    "other": "기타 활동",
}


def roman(i: int) -> str:
    return ROMAN[i] if i < len(ROMAN) else str(i + 1)


def md(text: str) -> str:
    if not text:
        return ""
    return markdown.markdown(
        text,
        extensions=["tables", "nl2br", "sane_lists"],
        output_format="html5",
    )


def spaced_name(name: str) -> str:
    """회의자료 표에 쓰는 '홍 경 수' 형태. 한글 2~4자 이름만 띄운다."""
    n = (name or "").strip()
    if 2 <= len(n) <= 4 and all("가" <= ch <= "힣" for ch in n):
        return " ".join(n)
    return n


# ---------------------------------------------------------------- images
def image_path(filename: str) -> Path | None:
    """업로드 파일명 -> 실제 경로. 'static:'로 시작하면 정적 파일."""
    if not filename:
        return None
    if filename.startswith("static:"):
        p = STATIC_DIR / filename[len("static:"):]
    else:
        p = D.UPLOAD_DIR / Path(filename).name
    return p if p.exists() else None


def image_url(filename: str) -> str:
    if not filename:
        return ""
    if filename.startswith("static:"):
        return "/static/" + filename[len("static:"):]
    return "/uploads/" + Path(filename).name


def image_data_uri(filename: str) -> str:
    p = image_path(filename)
    if p is None:
        return ""
    mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def logo_ref(settings: dict) -> str:
    return settings.get("logo_file") or "static:img/logo_ksjcs.png"


def term_image_ref(settings: dict) -> str:
    return settings.get("term_image_file") or "static:img/term53.svg"


# ---------------------------------------------------------------- context
def meeting_context(conn: sqlite3.Connection, meeting_id: int, inline_images: bool = False) -> dict:
    """문서 템플릿(doc.html)에 넘길 전체 컨텍스트."""
    settings = D.all_settings(conn)
    meeting = D.row(conn, "SELECT * FROM meetings WHERE id=?", (meeting_id,))
    if meeting is None:
        raise KeyError(meeting_id)
    img = image_data_uri if inline_images else image_url

    committee = D.rows(conn, "SELECT * FROM committee_members ORDER BY sort, id")
    groups = D.rows(conn, "SELECT * FROM groups WHERE active=1 ORDER BY sort, id")
    reports_raw = {
        r["group_id"]: r for r in D.rows(conn, "SELECT * FROM reports WHERE meeting_id=?", (meeting_id,))
    }
    group_reports = []
    for g in groups:
        rep = reports_raw.get(g["id"])
        data = D.loads(rep["data"], None) if rep else None
        if not data:
            data = D.empty_report(g)
        group_reports.append({
            "group": g,
            "data": data,
            "submitted": bool(rep and rep["submitted"]),
            "has_content": bool(rep) and _has_content(data),
        })

    agenda = D.rows(conn, "SELECT * FROM agenda_items WHERE meeting_id=? ORDER BY sort, id", (meeting_id,))
    items = []
    for i, a in enumerate(agenda):
        images = [
            {"src": img(im.get("file", "")), "caption": im.get("caption", "")}
            for im in D.loads(a["images"], [])
            if image_path(im.get("file", ""))
        ]
        items.append({
            **a,
            "num": roman(i),
            "body_html": md(a["body"]),
            "image_list": images,
        })

    # 보고서 이미지 src 변환
    for gr in group_reports:
        for half in ("past", "plan"):
            sec = gr["data"].setdefault(half, {"intro": "", "items": [], "images": []})
            sec["image_list"] = [
                {"src": img(im.get("file", "")), "caption": im.get("caption", "")}
                for im in sec.get("images", [])
                if image_path(im.get("file", ""))
            ]
            sec["intro_html"] = md(sec.get("intro", ""))
            for it in sec.get("items", []):
                it["desc_html"] = md(it.get("desc", ""))

    term = settings.get("term", "53")
    return {
        "settings": settings,
        "meeting": meeting,
        "doc_title": f"{settings.get('society_name', '한국언론학회')} 제{term}-{meeting['seq']}차",
        "doc_subtitle": f"{meeting['title']} 회의자료",
        "logo_src": img(logo_ref(settings)),
        "term_image_src": img(term_image_ref(settings)),
        "president": {
            "name": settings.get("president_name", ""),
            "affiliation": settings.get("president_affiliation", ""),
            "title": f"제{term}대 {settings.get('society_name', '한국언론학회')}장",
        },
        "committee": committee,
        "groups": groups,
        "group_reports": group_reports,
        "agenda": items,
        "spaced": spaced_name,
    }


def _has_content(data: dict) -> bool:
    if data.get("no_report"):
        return True
    for half in ("past", "plan"):
        sec = data.get(half) or {}
        if (sec.get("intro") or "").strip() or sec.get("items") or sec.get("images"):
            return True
    return False


# ---------------------------------------------------------------- PDF
def render_pdf(html: str, footer_logo_data_uri: str, title: str) -> bytes:
    """HTML 문자열 -> PDF bytes. 바닥글에 작은 로고 + 페이지 번호."""
    from playwright.sync_api import sync_playwright

    footer = f"""
    <div style="width:100%; font-size:9px; font-family:'Malgun Gothic','맑은 고딕','NanumGothic','Noto Sans CJK KR',sans-serif; color:#444;
                display:flex; align-items:center; justify-content:center; gap:8px; padding:0 15mm;">
      <img src="{footer_logo_data_uri}" style="height:16px; width:auto;" />
      <span>- <span class="pageNumber"></span> -</span>
    </div>"""
    header = "<div></div>"
    # 컨테이너에서 root 로 실행될 때 Chromium 샌드박스를 끈다
    args = ["--no-sandbox"] if os.name != "nt" and getattr(os, "geteuid", lambda: 1)() == 0 else []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=args)
        page = browser.new_page()
        page.set_content(html, wait_until="load")
        page.emulate_media(media="print")
        pdf = page.pdf(
            format="A4",
            print_background=True,
            display_header_footer=True,
            header_template=header,
            footer_template=footer,
            margin={"top": "18mm", "bottom": "18mm", "left": "0", "right": "0"},
            prefer_css_page_size=False,
        )
        browser.close()
    return pdf
