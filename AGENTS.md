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

## 协作与提交流程

- 所有业务改动必须经 feature/fix/docs 分支和 Pull Request 进入 `main`；提交前运行 `npm run check`，后端变更还需运行 `cd backend && pytest` 与 `ruff check .`。
- 合并前必须通过 GitHub Actions 的全部检查，获得 Code Owner Review，且没有未解决的 Review 评论；使用 Squash merge。

## 已确认的黑洞场景偏好

- 用户提供的原版 CodePen 场景代码是前端背景的唯一实现基准：保留其星空、吸积盘噪声着色、旋转、Bloom、引力透镜、glitch 和 OrbitControls；不要叠加静态深空图片或用简化着色器替换。
- 可在原版星空中增加一条低对比的青紫银河星带作为远景层；当前确认走向为左上至右下的斜纵向。它必须弱于黑洞和吸积盘，不能影响登录卡片与文案的可读性。
- 登录页当前确认的黑洞、银河带、星空、亮度与场景姿态是所有页面的统一背景基准；路由/登录状态切换只能替换前景内容，不得改变该背景构图或额外压暗它。
- 登录与控制台之间必须预留稳定的页面滚动条空间，避免控制台内容出现滚动条时改变 Canvas 宽高比，造成黑洞位置跳变。
- Canvas 的黑洞 Group 姿态、缩放与 OrbitControls 在整个会话中固定。登录页黑洞位于左侧构图；点击登录后仅使用相机取景中心的平移，让黑洞在 glitch 中归心，并在效果结束前基本到位；不得移动/旋转黑洞本体，不得让控制台中出现明显平移、闪切或大小改变。
- Canvas 与深空蒙层必须使用 `position: fixed` 和视口尺寸；控制台导航或内容高度增加不得拉伸背景画布、改变相机纵横比或导致黑洞位置变化。
- “信号流”是独立的 AI 资讯浏览页面，提供来源接入后的事件时间流、主题筛选、摘要、来源和收藏入口；在尚无来源时，页面必须明确展示零事件及下一步，而不能使用虚构资讯数据。
- 控制台导航使用顶部现代化毛玻璃栏（品牌左、导航中、用户操作右）；数据卡片应增加足够的深色毛玻璃以和高亮背景协调，同时确保正文不被吸积盘穿透。登录成功过渡中，控制台应在不超过 1 秒的 glitch 后段平滑淡入并轻微上移，禁止 glitch 结束后闪切首页或改变背景构图。
- 黑洞采用原版 CodePen 场景姿态：事件视界半径 `1.3`、吸积盘倾角 `π/3`；用户确认需要略宽的盘面，因此吸积盘半径为 `1.5 → 9.5`。允许用户使用 OrbitControls 拖拽调整视角、滚轮缩放；不得强行锁死场景或以镜像盘面替代原版透视结构。
- 登录成功使用原版短暂 glitch 与表单淡出衔接控制台。
- 控制台必须沿用登录页的同一黑洞、相机和吸积盘姿态；只允许缩小并后退作为背景氛围，不得切换成不同的黑洞造型或仅剩事件视界圆环。
- 信号流页不展示 `EVENT HORIZON / 信号流` 之类重复路径；页面标题和顶栏导航已经提供足够定位信息。
- 信号流筛选分为“来源”和“官网分类”两层：来源选项由已启用来源动态提供，默认查看全部来源；来源筛选位于官网分类筛选上方，现阶段只有 OpenAI 一个来源。切换来源时重置官网分类，避免保留其他来源的分类条件。
- 信号流分类采用来源官网的分类体系。OpenAI 当前筛选项为公司、研究、产品、安全、工程、安全防护、全球事务、AI 采用、应用 AI；文章详情在标题前按“发布日期 + 官网分类”展示。
- 采集文章不得由模型改写或生成摘要冒充正文。OpenAI 内容必须由专用采集器和无损格式化器按源顺序转换，原始正文或快照归档到对象存储，并保留原文链接。
- OpenAI 文章中的交互演示媒体必须保留官网编排语义：同一演示组使用顶部胶囊选项卡切换，下方只展示当前媒体；不得把组内视频拆成连续纵向列表。
- 每个资讯平台在接入前必须建立并维护 `来源布局画像.md` 与代码侧 `SourceLayoutProfile`，记录原生组件、分组、顺序、媒体归档和降级规则；格式化器不得静默丢弃图表、轮播或平台专属组件。
- OpenAI 评测图表必须从 RSC payload 保留原始 Vega-Lite spec，按官网 tab 组展示；不得用摘要、普通表格或自造图形替代互动图表。
- OpenAI 文章必须优先抓取 `/zh-Hans-CN/` 页面，并只将页面语言为中文的正文、标题和描述写入及展示；RSS 英文标题和摘要仅用于发现候选文章，不得显示为中文资讯内容。未提供中文版的文章暂不入库。
- OpenAI 采集器按上海时区每小时整点运行；必须先规范化并按 canonical URL 合并候选，再查库跳过已采集 URL 后才请求文章正文。失败文章在下一次运行重试，不能重复存储同一 URL。
- 控制台保持打开时每 5 分钟刷新列表；页面关闭或切到后台时停止轮询，避免重复请求。
- 多平台采集采用“平台 Collector + 平台 Formatter + SourceLayoutProfile + fixture”确定性链路；Agent 只能辅助未知组件识别、质量检查和规则草稿生成，不得直接改写正文或写入生产文章。

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run check`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.
