"""摩点众筹 MCP Server · PC 版 (FastMCP, stdio).

只走 PC 端 https://zhongchou.modian.com SSR HTML (requests + BeautifulSoup),
外加 Selenium 兜底渲染 www 侧 SPA 页。不含移动 apim、不含登录态：
纯只读浏览，适合 rapid 查档。需要下单/移动数据用 login 目录的版本。

运行 (pip install . 后任意目录均可):
    python -m modian_mcp.server
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import scraper
from .scraper import CATEGORIES, SORTS, STATUSES

mcp = FastMCP("modian-zhongchou")


@mcp.tool()
def list_projects(category: str = "all", sort: str = "top_comment",
                  status: str = "going", page: int = 1) -> dict:
    """众筹项目列表.

    Args:
        category: all/games/publishing/tablegames/toys/cards/technology/film-video/music/activities/design/curio/home/food/comics/charity/animals/wishes/others
        sort: top_comment=评论最多 top_time=最新上线 top_money=金额最高
        status: going=众筹中 preheat=预热 success=众筹成功 all=全部
        page: 页码 >=1, 第1页无后缀, >=2 自动拼 /N
    """
    return scraper.fetch_projects(category=category, sort=sort,
                                  status=status, page=page)


@mcp.tool()
def get_project_detail(pro_id: str) -> dict:
    """项目详情. pro_id 可传纯数字 (160002) 或完整 url
    (https://zhongchou.modian.com/item/160002.html).

    返回: 标题/发起人/类别/状态/已筹/目标/进度/支持人数/起止时间/封面/视频/更新数/详情预览.
    """
    return scraper.fetch_project_detail(pro_id)


@mcp.tool()
def get_project_rewards(pro_id: str) -> dict:
    """回报档位列表 (价格/标题/已支持/限量/描述/预计发货/图片). 无偿支持 rew_id=-3."""
    return scraper.fetch_project_rewards(pro_id)


@mcp.tool()
def get_project_updates(pro_id: str) -> dict:
    """项目更新 (动态) 链接列表. 详情页只暴露部分时看 note;
    更新正文本体在 www 侧 SPA, 可用 fetch_rendered_page 抓."""
    return scraper.fetch_project_updates(pro_id)


@mcp.tool()
def get_project_description(pro_id: str, max_chars: int = 15000) -> dict:
    """项目详情富文本 (纯文本 + 图片 URL). 默认截断 15000 字防爆 token."""
    return scraper.fetch_project_description(pro_id, max_chars=max_chars)


@mcp.tool()
def fetch_rendered_page(url: str, wait: int = 6) -> dict:
    """Chrome 无头渲染抓取 (Selenium 兜底).

    适用: www.modian.com 的 SPA 更新详情页 / product_rewards 页等.
    普通列表和详情页请优先用上面专用工具 (更快更省).
    需要 pip install 'modian-mcp[browser]' 且本机有 Chrome.
    """
    return scraper.fetch_rendered(url, wait=wait)


@mcp.tool()
def get_filter_options() -> dict:
    """返回列表页可用的 category/sort/status 枚举 (给 AI 做参数校验)."""
    return {
        "categories": CATEGORIES,
        "sorts": {k: v for k, v in SORTS.items()},
        "statuses": {k: v for k, v in STATUSES.items()},
        "list_url_pattern": "https://zhongchou.modian.com/{category}/{sort}/{status}[/{page}]",
        "item_url_pattern": "https://zhongchou.modian.com/item/{pro_id}.html",
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
