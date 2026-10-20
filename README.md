# AI Signal

> 进入事件视界，看见 AI 的下一步。

AI Signal 是一个面向 AI 资讯与讨论的信息聚合平台。它计划从多个公开来源收集近 30 天的 AI 信号，将不同平台的内容转换为统一、可检索、可去重且可追溯的数据，再以“事件视界”式的沉浸界面呈现给用户。

项目目前已完成完整的账户认证基础设施与登录后控制台空状态，内容采集、规范化和资讯流正在建设中。

![License](https://img.shields.io/badge/status-in%20development-8b5cf6)
![Frontend](https://img.shields.io/badge/frontend-Vue%203-42b883)
![Backend](https://img.shields.io/badge/backend-FastAPI-009688)
![Database](https://img.shields.io/badge/database-PostgreSQL-336791)

## 为什么做这个项目

AI 领域的信息变化极快，但信息分散在新闻网站、社区、代码仓库、视频与社交平台中。AI Signal 希望解决三个问题：

- 聚合：为不同来源建立可扩展的采集适配器。
- 降噪：通过 URL、标题与正文指纹去重，减少重复信息。
- 优先级：把真正值得关注的变化以统一信息流和事件形式呈现。

## 当前已实现

- 动态深空登录与注册页：Three.js 黑洞、吸积盘、星空、视差网格与 reduced-motion 支持。
- 用户认证：注册、登录、短期 JWT、可撤销刷新令牌、会话恢复与退出登录。
- 后端基础设施：FastAPI、SQLAlchemy 2、Alembic、PostgreSQL、Redis 与 Docker Compose。
- 数据库迁移：用户与刷新令牌数据模型及首个 Alembic migration。
- 登录后控制台：延续动态星空和低速黑洞场景，提供来源接入前的清晰空状态。
- 工程门禁：前端构建、托管产物和 Sites Worker 测试。

## 技术栈

| 范围 | 技术 |
| --- | --- |
| 前端 | Vue 3、Vite、Three.js、Iconify |
| 后端 | FastAPI、SQLAlchemy 2、Pydantic Settings |
| 认证 | Argon2（pwdlib）、JWT、刷新令牌轮换 |
| 数据库 | PostgreSQL 16、Alembic |
| 缓存与队列基础 | Redis 7 |
| 本地编排 | Docker Compose |

## 快速开始

### 1. 准备配置

```bash
cp .env.example .env
```

请在共享或生产环境中替换 `.env` 中的 `JWT_SECRET_KEY`、数据库密码等默认值。

### 2. 启动前端、API、数据库、Redis 和 MinIO

```bash
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose exec backend python scripts/import_openai_fixtures.py
```

Docker 前端访问地址：`http://127.0.0.1:8080/`

API 健康检查地址：`http://127.0.0.1:8000/api/v1/health`

MinIO 控制台：`http://127.0.0.1:9001/`

前端由 Nginx 提供生产构建，并将 `/api/v1` 反向代理到 Compose 中的 `backend` 服务。若需要修改宿主机端口，可在 `.env` 中设置 `FRONTEND_PORT`。

### 3. 可选：前端本地热更新开发

```bash
npm install
npm run dev
```

打开 `http://127.0.0.1:5173/`，注册账号后即可进入控制台。

## API 概览

所有接口均位于 `/api/v1` 前缀下。

| 方法 | 接口 | 用途 |
| --- | --- | --- |
| `GET` | `/health` | 服务健康检查 |
| `POST` | `/auth/register` | 注册账户并获取会话 |
| `POST` | `/auth/login` | 登录并获取会话 |
| `POST` | `/auth/refresh` | 刷新访问令牌 |
| `POST` | `/auth/logout` | 撤销刷新令牌并退出 |
| `GET` | `/me` | 获取当前用户 |

## 数据规范（规划中）

每个采集适配器只负责“拉取 + 转换”，核心业务使用统一的 `NormalizedArticle`，以避免来源特有字段渗入系统。

```ts
type NormalizedArticle = {
  externalId: string
  sourceKey: string
  canonicalUrl: string
  title: string
  summary?: string
  authorName?: string
  publishedAt: string
  language?: string
  topics: string[]
  metrics: { likes?: number; comments?: number; shares?: number; views?: number }
  rawPayload: Record<string, unknown>
}
```

## 开发与验证

前端与托管产物检查：

```bash
npm run check
```

后端测试（Docker 服务已启动时）：

```bash
docker compose exec backend /app/.venv/bin/pytest
```

所有改动通过 Pull Request 进入 `main`：本地检查 → Draft PR → GitHub Actions → Code Review → Squash merge。完整规范与仓库分支保护设置见[开发文档.md](开发文档.md#开发review-与合并流程)。

项目的详细约束与设计规范请参阅：

- [开发文档.md](开发文档.md)
- [数据模型与接口.md](数据模型与接口.md)
- [前端主题规范.md](前端主题规范.md)
- [测试文档.md](测试文档.md)

## Roadmap

- [x] Docker 化 API、PostgreSQL、Redis 基础设施
- [x] 用户认证与令牌轮换
- [x] 登录后控制台基础界面
- [ ] 来源、文章、标签、收藏的数据模型与查询 API
- [ ] 第一个资讯来源适配器与 `NormalizedArticle` 转换
- [ ] 去重、失败重试与后台任务链路
- [ ] 资讯流、筛选、收藏与事件详情页

## 贡献

欢迎通过 Issue 讨论新的来源、信息排序策略、采集适配器和体验优化。在提交 PR 前，请确保 `npm run check` 通过，并为后端行为补充相应测试。
