"""tests for modian-mcp, PC only (offline, no network)."""
from modian_mcp import scraper


def test_extract_pro_id():
    assert scraper.extract_pro_id("160002") == "160002"
    assert scraper.extract_pro_id("https://zhongchou.modian.com/item/160002.html") == "160002"


def test_list_url():
    assert scraper.list_url("all", "top_comment", "going", 1) == \
        "https://zhongchou.modian.com/all/top_comment/going"
    assert scraper.list_url("cards", "top_money", "going", 2) == \
        "https://zhongchou.modian.com/cards/top_money/going/2"


def test_parse_list_page():
    html = """
    <html><body>共 10 个众筹项目
    <ul class="pro_ul clearfix">
    <li data-pro-id="160002">
      <a href="https://zhongchou.modian.com/item/160002.html">
      <div class="pro_logo"><img src="http://cover.jpg"></div></a>
      <div class="pro_txt_field">
      <a href="https://zhongchou.modian.com/item/160002.html"><h3 class="pro_title">测试项目</h3></a>
      <div class="author"><p>作者A</p></div>
      <p class="status_title">¥<span backer_money="160002">100.00</span></p>
      <p class="right percent"><span rate="160002">100</span>%</p>
      <p class="gray_ex"><span backer_count="160002">5</span> 支持者</p>
      </div>
    </li>
    </ul></body></html>
    """
    projects, meta = scraper.parse_list_page(html)
    assert meta["total"] == 10
    assert len(projects) == 1
    assert projects[0]["pro_id"] == "160002"
    assert projects[0]["title"] == "测试项目"
    assert projects[0]["backer_count"] == 5
