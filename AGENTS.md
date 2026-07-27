# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

## 文档与交付门禁（必须遵守）

以下文档是本项目的规范来源。开始对应类型的工作前必须阅读，实施后必须按文档中的验收项检查：

| 工作范围 | 必读文档 |
| --- | --- |
| 前后端架构、目录、认证、配置 | `开发文档.md` |
| PostgreSQL、迁移、采集器、API | `数据模型与接口.md` |
| 视觉、交互、动效、响应式、无障碍 | `前端主题规范.md` |
| 单元、集成、端到端、发布验收 | `测试文档.md` |

- 每项交付都必须运行 `npm run check`；不得只报告“页面可打开”。
- 任何数据表修改必须同时提交 Alembic migration 和对应测试；不得手工改数据库作为交付方式。
- 每个新内容来源必须实现 `NormalizedArticle` 转换、fixture 测试、去重与失败重试处理。
- 新 API 必须使用 `/api/v1` 前缀、Pydantic schema，并补充认证/权限/错误路径测试。
- 视觉改动必须保留已确认的黑洞、文案、认证卡片布局关系，并在同一视口完成对照检查。
- 如规范之间出现冲突，先停止实施并要求确认；不得自行选择一个方向。

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

## AI Signal authentication direction

- Desktop composition: original CodePen-inspired neon black hole in the left visual field, dark frosted login panel on the right.
- The source of truth is the latest approved composition: cyan/magenta/soft-violet event horizon, left-bottom → right-top accretion disk, subtle perspective grid, and sparse dark-space star field. Do not switch the active direction to amber-gold without explicit approval.
- The black-hole canvas is the complete page background. Keep it interactive (drag to orbit, wheel to zoom), with no separate raster background layer or busy particle field.
- The panel has 24–28px continuous corners, substantial iPhone-style backdrop blur, restrained internal highlight, and a dark translucent material. Its left border takes the scene's cool cyan/violet light; the other edges recede into the space background.
- Protect the composition: reserve the right third for the card, place the black hole left/upper-middle, and keep the product copy readable at bottom-left.
- Login success transitions by fading the form and moving/scaling the black hole to the canvas center.

## 登录后控制台方向

- 控制台必须复用登录页的动态 Three.js 星空与黑洞，而非静态背景；黑洞缩小、后退并低速运转，作为数据表面的空间氛围。
- 控制台数据卡片采用深色半透明毛玻璃，与背景融合但不牺牲正文对比度；避免黑洞高亮直接穿透文字和状态区域。
- 空状态展示应使用明确业务文案（例如“等待首个来源 / 0 个来源已连接”），禁止无业务含义的 `00 ACTIVE` 装饰仪表。

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run check`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.
