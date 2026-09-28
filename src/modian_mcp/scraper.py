"""摩点众筹 MCP — HTML 抓取层.

设计原则:
- 默认只用 requests + BeautifulSoup 解析 SSR 页面 (快、无需浏览器):
  - 列表页: https://zhongchou.modian.com/{category}/{sort}/{status}[/{page}]
  - 详情页: https://zhongchou.modian.com/item/{pro_id}.html
- apim.modian.com 的 JSON 接口有反爬 JS 挑战, 不做默认依赖;
  需要动态渲染的 SPA 页面 (update detail / product_rewards / backer 列表)
  才走可选的 Selenium/Chrome 兜底 (fetch_rendered_page / use_browser=True).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://zhongchou.modian.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

CATEGORIES = [
    "all", "games", "publishing", "tablegames", "toys", "cards",
    "technology", "film-video", "music", "activities", "design",
    "curio", "home", "food", "comics", "charity", "animals",
    "wishes", "others",
]
SORTS = {"top_comment": "评论最多", "top_time": "最新上线", "top_money": "金额最高"}
STATUSES = {"going": "众筹中", "preheat": "预热", "success": "众筹成功", "all": "全部"}

_session = requests.Session()
_session.headers.update({"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})


def extract_pro_id(text: str) -> str:
    """从纯 id / item url 中提取数字 id."""
    if text is None:
        raise ValueError("pro_id 为空")
    text = str(text).strip()
    if text.isdigit():
        return text
    m = re.search(r"/item/(\d+)", text)
    if m:
        return m.group(1)
    m = re.search(r"(\d{4,})", text)
    if m:
        return m.group(1)
    raise ValueError(f"无法解析项目 id: {text!r}")


def list_url(category="all", sort="top_comment", status="going", page=1) -> str:
    if category not in CATEGORIES:
        raise ValueError(f"category 非法: {category}, 可选 {CATEGORIES}")
    if sort not in SORTS:
        raise ValueError(f"sort 非法: {sort}, 可选 {list(SORTS)}")
    if status not in STATUSES:
        raise ValueError(f"status 非法: {status}, 可选 {list(STATUSES)}")
    page = int(page)
    url = f"{BASE}/{category}/{sort}/{status}"
    if page >= 2:
        url += f"/{page}"
    return url


def item_url(pro_id: str) -> str:
    return f"{BASE}/item/{extract_pro_id(pro_id)}.html"


def _get(url: str, timeout: int = 20) -> str:
    r = _session.get(url, timeout=timeout)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def parse_list_page(html: str) -> tuple[list[dict], dict]:
    """解析列表页, 返回 (projects, meta)."""
    soup = BeautifulSoup(html, "lxml")
    projects: list[dict] = []
    for li in soup.select("ul.pro_ul > li[data-pro-id]"):
        pid = li.get("data-pro-id", "").strip()
        a = li.select_one('a[href*="/item/"]')
        title_el = li.select_one(".pro_title")
        author_el = li.select_one(".author p")
        money_el = li.select_one("[backer_money]")
        rate_el = li.select_one("[rate]")
        count_el = li.select_one("[backer_count]")
        img_el = li.select_one(".pro_logo img")
        # 兼容部分卡片结构差异
        title = title_el.get_text(strip=True) if title_el else (a.get_text(strip=True) if a else "")
        try:
            raised = money_el.get_text(strip=True) if money_el else ""
            percent = rate_el.get_text(strip=True).replace("%", "") if rate_el else ""
            backers = count_el.get_text(strip=True) if count_el else ""
            projects.append({
                "pro_id": pid,
                "title": title,
                "url": item_url(pid) if pid else "",
                "author": author_el.get_text(strip=True) if author_el else "",
                "raised_yuan": raised,
                "percent": percent + ("%" if percent and "%" not in percent else ""),
                "backer_count": int(backers.replace(",", "")) if backers and backers.replace(",", "").isdigit() else backers,
                "cover": img_el.get("src", "") if img_el else "",
            })
        except Exception:
            continue
    # 总数 "共 334 个众筹项目"
    total = None
    m = re.search(r"共\s*(\d+)\s*个众筹项目", soup.get_text(" ", strip=True))
    if m:
        total = int(m.group(1))
    return projects, {"total": total}


def fetch_projects(category="all", sort="top_comment", status="going",
                   page=1, timeout=20) -> dict:
    url = list_url(category, sort, status, page)
    html = _get(url, timeout=timeout)
    projects, meta = parse_list_page(html)
    return {
        "url": url, "category": category, "sort": sort,
        "status": status, "page": int(page),
        "total_projects": meta.get("total"),
        "count": len(projects), "projects": projects,
    }


def _text(el) -> str:
    return el.get_text(" ", strip=True) if el else ""


def parse_item_page(html: str, pro_id: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    def one(sel):
        return soup.select_one(sel)

    title = _text(one(".short-cut .title span")) or _text(soup.title).split("-")[0].strip()
    sponsor = _text(one(".sponsor-l .name span")) or _text(one(".sponsor-l .name"))
    category = ""
    m = re.search(r"项目类别[:：]\s*(\S+)", soup.get_text(" ", strip=True))
    if m:
        category = m.group(1)
    raised = _text(one("[backer_money]"))
    goal = _text(one(".goal-money"))
    percent = _text(one(".percent"))
    backer_count_raw = _text(one(".support-people h3 span")) or _text(one('[backer_count]'))
    status_el = one(".tanchuzhuangtai")
    status = status_el.get("status", "").strip() if status_el else ""
    time_el = one(".remain-time h3")
    start_time = time_el.get("start_time", "") if time_el else ""
    end_time = time_el.get("end_time", "") if time_el else ""
    deadline_note = _text(one("#my_back_info li"))
    cover = ""
    big_logo = one("#big_logo")
    if big_logo and big_logo.get("src"):
        cover = big_logo["src"]
    video_el = one(".vedio_url")
    video = video_el.get("data-duration") and video_el.get_text(strip=True) or ""
    if video_el:
        video = video_el.get_text(strip=True)
    updates_count = None
    uc = one("[upadte_count]")
    if uc:
        try:
            updates_count = int(uc.get_text(strip=True))
        except ValueError:
            updates_count = uc.get_text(strip=True)
    # 项目详情富文本: 真实内容在 <script id="projectContentTemplate"> 里
    # (#cont_match_htmlstr 为空, 由 JS cont_match_reg 填充), 多为图片少文字
    detail_text, detail_images, detail_links = "", [], []
    tpl = one("#projectContentTemplate")
    if tpl is not None:
        inner = tpl.get_text()
        if inner.strip():
            tsoup = BeautifulSoup(inner, "lxml")
            detail_text = tsoup.get_text("\n", strip=True)[:20000]
            for img in tsoup.find_all("img"):
                src = img.get("src") or img.get("data-original") or img.get("data-src") or ""
                if src and src.startswith("http"):
                    detail_images.append(src)
            for a in tsoup.find_all("a", href=True):
                detail_links.append(a["href"])
            detail_images = list(dict.fromkeys(detail_images))[:50]
            detail_links = list(dict.fromkeys(detail_links))[:50]
    # 短介绍 (部分项目有)
    short_intro = _text(one("#cont_match_short")) or _text(one(".short-intro"))

    return {
        "pro_id": str(pro_id),
        "url": item_url(pro_id),
        "title": title,
        "sponsor": sponsor,
        "category": category,
        "status": status,
        "raised_yuan": raised,
        "goal": goal,
        "percent": percent,
        "backer_count": backer_count_raw,
        "start_time": start_time,
        "end_time": end_time,
        "deadline_note": deadline_note,
        "cover": cover,
        "video": video,
        "updates_count": updates_count,
        "short_intro": short_intro[:1000],
        "detail_text_preview": detail_text[:3000],
        "detail_text_len": len(detail_text),
        "detail_images": detail_images[:20],
        "detail_image_count": len(detail_images),
        "detail_links": detail_links[:20],
    }


def fetch_project_detail(pro_id: str, timeout=20) -> dict:
    pid = extract_pro_id(pro_id)
    html = _get(item_url(pid), timeout=timeout)
    return parse_item_page(html, pid)


def parse_rewards(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    rewards: list[dict] = []
    for div in soup.select(".back-list"):
        rew_id = div.get("rew_id", "")
        price_el = div.select_one(".head span")
        subtitle_el = div.select_one(".back-sub-title")
        count_el = div.select_one(".count")
        desc_el = div.select_one(".back-detail")
        time_el = div.select_one(".back-time")
        imgs = []
        for img in div.select(".back-img img"):
            src = img.get("data-original") or img.get("data-src") or img.get("src") or ""
            if src.startswith("http"):
                imgs.append(src)
        limit_el = div.select_one(".zc-subhead")
        rewards.append({
            "rew_id": rew_id or "-3",
            "price_yuan": price_el.get_text(strip=True).replace("¥", "").replace(",", "") if price_el else "0",
            "title": subtitle_el.get_text(strip=True) if subtitle_el else "无偿支持",
            "sold_info": count_el.get_text(strip=True) if count_el else "",
            "limit_info": limit_el.get_text(" ", strip=True) if limit_el else "",
            "desc": desc_el.get_text("\n", strip=True) if desc_el else "",
            "delivery": time_el.get_text(strip=True) if time_el else "",
            "images": list(dict.fromkeys(imgs))[:10],
        })
    return rewards


def fetch_project_rewards(pro_id: str, timeout=20) -> dict:
    pid = extract_pro_id(pro_id)
    html = _get(item_url(pid), timeout=timeout)
    rewards = parse_rewards(html)
    return {"pro_id": pid, "url": item_url(pid), "count": len(rewards), "rewards": rewards}


def parse_updates(html: str) -> list[dict]:
    """详情页只 SSR 最近 1 次更新全文 + 详情模板里嵌的若干更新链接.

    完整历史 (upadte_count 往往 > 解析数) 需浏览器渲染或登录态, 这里如实返回可抓到的部分.
    """
    soup = BeautifulSoup(html, "lxml")
    # 模板 script 里的 HTML 单独解析 (详情图链了很多历史更新);
    # 不能拼回整文档尾部, lxml 会丢弃 </html> 之后的内容
    tpl = soup.select_one("#projectContentTemplate")
    try:
        inner_html = tpl.decode_contents() if tpl is not None else ""
    except Exception:
        inner_html = ""
    soups = [soup]
    if inner_html.strip():
        soups.append(BeautifulSoup(inner_html, "lxml"))
    updates: list[dict] = []
    seen: set[str] = set()
    anchors = []
    for s in soups:
        anchors.extend(s.select('a[href*="/project/update/detail/"]'))
    for a in anchors:
        href = a.get("href", "")
        m = re.search(r"/detail/(\d+)", href)
        if not m:
            continue
        uid = m.group(1)
        if uid in seen:
            continue
        seen.add(uid)
        title = a.get_text(" ", strip=True)[:200] or (a.get("title") or "")[:200]
        if not title:
            parent = a.parent
            title = parent.get_text(" ", strip=True)[:200] if parent else ""
        updates.append({
            "update_id": uid,
            "title": title,
            "url": urljoin("https://www.modian.com", href),
        })
    # 最近更新块补标题/时间
    latest = {}
    upd = soup.select_one(".update")
    if upd is not None:
        latest = {
            "latest_title": upd.select_one(".update-title").get_text(strip=True) if upd.select_one(".update-title") else "",
            "latest_time": upd.select_one(".time").get_text(strip=True) if upd.select_one(".time") else "",
            "latest_count": upd.select_one(".count").get_text(strip=True) if upd.select_one(".count") else "",
        }
    # 把最近更新顶到前面
    if latest.get("latest_title"):
        for u in updates:
            if latest["latest_title"] in u["title"] or u["title"] in latest["latest_title"]:
                updates.remove(u)
                updates.insert(0, {**u, **latest})
                break
    return updates


def fetch_project_updates(pro_id: str, timeout=20) -> dict:
    pid = extract_pro_id(pro_id)
    html = _get(item_url(pid), timeout=timeout)
    updates = parse_updates(html)
    soup = BeautifulSoup(html, "lxml")
    uc = soup.select_one("[upadte_count]")
    total = uc.get_text(strip=True) if uc else str(len(updates))
    note = ""
    try:
        if int(total) > len(updates):
            note = (
                f"详情页仅暴露 {len(updates)} 条更新链接, 官方总数为 {total}; "
                "完整历史需登录/浏览器渲染, 可用 fetch_rendered_page 兜底"
            )
    except (ValueError, TypeError):
        pass
    return {"pro_id": pid, "total": total, "count": len(updates),
            "updates": updates, "note": note}


def fetch_project_description(pro_id: str, timeout=20, max_chars=15000) -> dict:
    """返回项目详情全文 (文本 + 图片 + 外链, 截断保护).

    注意: 摩点详情多为长图, 文字少是正常的, 图片 URL 全量返回供视觉模型分析.
    """
    pid = extract_pro_id(pro_id)
    html = _get(item_url(pid), timeout=timeout)
    soup = BeautifulSoup(html, "lxml")
    tpl = soup.select_one("#projectContentTemplate")
    if tpl is None or not tpl.get_text().strip():
        return {"pro_id": pid, "text": "", "images": [], "links": [], "truncated": False,
                "note": "未找到详情模板, 页面可能改版"}
    inner = tpl.get_text()
    tsoup = BeautifulSoup(inner, "lxml")
    text = tsoup.get_text("\n", strip=True)
    images, links = [], []
    for img in tsoup.find_all("img"):
        src = img.get("src") or img.get("data-original") or img.get("data-src") or ""
        if src.startswith("http"):
            images.append(src)
    for a in tsoup.find_all("a", href=True):
        links.append({"text": a.get_text(" ", strip=True)[:100], "href": a["href"]})
    images = list(dict.fromkeys(images))
    truncated = len(text) > max_chars
    return {
        "pro_id": pid, "url": item_url(pid),
        "text": text[:max_chars], "text_len": len(text),
        "images": images, "image_count": len(images),
        "links": links[:50], "truncated": truncated,
        "note": "详情多为图片, 需看图时把 images 逐张给视觉模型",
    }


def fetch_rendered(url: str, wait: int = 6, timeout: int = 60) -> dict:
    """Selenium + Chrome 无头渲染兜底 (SPA 页面 / 反爬页面专用).

    需要: pip install \"modian-mcp[browser]\" 且本机有 Chrome.
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service
            use_manager = True
        except ImportError:
            use_manager = False
    except ImportError as e:
        raise RuntimeError(
            "未安装浏览器依赖, 请执行: pip install 'modian-mcp[browser]'"
        ) from e

    import time
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument(f"--user-agent={UA}")
    opts.add_argument("--window-size=1366,2400")
    if use_manager:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    else:
        driver = webdriver.Chrome(options=opts)  # 需自备 chromedriver
    try:
        driver.set_page_load_timeout(timeout)
        driver.get(url)
        time.sleep(wait)
        html = driver.page_source
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text("\n", strip=True)
        return {
            "url": url, "title": driver.title,
            "html_len": len(html), "html": html[:100000],
            "text": text[:15000], "text_len": len(text),
            "note": "html 已截断 100k / text 截断 15k, 完整分析请缩小范围或用专用工具",
        }
    finally:
        driver.quit()
