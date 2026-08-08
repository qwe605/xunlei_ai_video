# ADR-004：采用 FastAPI、SQLAlchemy 与 React 分层架构

## 状态

已接受

## 背景

早期 Demo 将上传处理、路由和后台任务实例集中在一个 FastAPI 文件中，分析任务只保存在
进程内存；前端页面使用组件内枚举切换，无法形成可刷新、可分享的页面地址。随着本地导入、
ASR、MiniMax 和任务队列能力增加，这种结构不利于测试、部署和后续接入真实云盘数据。

## 决策

- 后端使用 Controller、Dependency、Service、Repository、Integration 分层。
- 使用 SQLAlchemy 2.0 ORM 持久化分析任务，Controller 和 Service 禁止散落原生 SQL。
- Demo 默认使用 SQLite，部署时允许通过 SQLAlchemy URL 切换 PostgreSQL。
- 第三方模型和系统协议放入 Integration，Service 只负责编排。
- 前端继续使用 React，并按 `views/components/api/router/assets` 分工。
- 前端路由基于浏览器 History API，避免引入当前存在高危审计项的路由依赖。
- Nginx 统一提供 React 静态资源、History 回退和 `/api/` 反向代理。

## 后果

- 分析任务在后端重启后仍可查询，数据访问逻辑可以独立测试。
- 新增实体时必须先定义 ORM Model，再通过 Repository 暴露数据操作。
- Controller、Service、Integration 的职责边界更清晰，但文件数量有所增加。
- 前端搜索、详情和播放页面拥有稳定 URL，可使用浏览器前进和后退。
- SQLite 适合本地 Demo；多实例部署时应切换 PostgreSQL 并增加迁移工具。
