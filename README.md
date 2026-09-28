# 摩点众筹 MCP  (modian-mcp)

只读浏览用：只走 PC 端 `zhongchou.modian.com` SSR HTML
（`requests + BeautifulSoup`，Selenium 兜底 www 侧 SPA）。
**不含登录态、不支持下单、不支持加关注**。

## 安装

```bash
pip install .   # 非 editable 安装：文件拷进 site-packages，整个目录搬走也不坏
# 开发改代码才用: pip install -e .
# 需要浏览器兜底时:
pip install ".[browser]"
```

## 运行（任意目录均可，包已装进环境）

```bash
python -m modian_mcp.server
```

`mcp.json`：见 `mcp.json.example`（无 `cwd` 死路径，装好后直接用）。

## 工具一览（全 PC，只读）

| 工具 | 说明 |
|---|---|
| `list_projects(category, sort, status, page)` | 项目列表：`category=all/games/.../cards/...` `sort=top_comment/top_time/top_money` `status=going/preheat/success/all` |
| `get_project_detail(pro_id)` | 标题/发起人/已筹/目标/进度/人数/起止时间/状态/封面/视频 |
| `get_project_rewards(pro_id)` | 回报档位：价格/标题/已支持/限量/描述/发货/图片 |
| `get_project_updates(pro_id)` | 更新链接（详情页只暴露部分时看 `note`） |
| `get_project_description(pro_id, max_chars)` | 详情富文本（文本+图片，默认截断 15k） |
| `fetch_rendered_page(url, wait)` | Selenium 兜底（SPA 更新详情页等） |
| `get_filter_options()` | 分类/排序/状态枚举 |

## URL 规则

- 列表: `https://zhongchou.modian.com/{category}/{sort}/{status}[/{page}]`
  例: `/all/top_comment/going`、`/cards/top_money/going`、`/all/top_time/going/2`
- 详情: `https://zhongchou.modian.com/item/{pro_id}.html`
  例: `https://zhongchou.modian.com/item/160002.html`

## 说明

- 列表页/详情页是 SSR，`requests` 直抓即可
- 详情正文真实内容在 `<script id="projectContentTemplate">` 里（多为长图），已解析
- 详情页只 SSR 最近 1 次更新全文，其余更新只有链接；要正文走 `fetch_rendered_page`
