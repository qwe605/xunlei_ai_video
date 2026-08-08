# 后端架构

后端使用 FastAPI、Pydantic、SQLAlchemy 2.0 和 Repository 模式。默认数据库为
`backend/data/xunlei.db`，部署环境可通过 `DATABASE_URL` 切换数据库。

```text
app/
├── app.py                 FastAPI 工厂、生命周期和程序入口
├── config.py              环境变量与密钥配置
├── schemas/               请求和响应的 Pydantic 契约
├── controllers/           路由、HTTP 状态码和参数边界
├── dependencies/          FastAPI 依赖注入
├── services/              业务流程编排
├── database/
│   ├── base.py            ORM 基类和通用字段
│   ├── session.py         Engine、Session 和事务边界
│   ├── models/            SQLAlchemy 数据表实体
│   └── repositories/      数据查询与 ORM 映射
└── integrations/          ASR、MiniMax 与 Windows 协议适配
```

## 分层规则

- Controller 只处理 HTTP 语义，不读写数据库、不调用第三方 SDK。
- Service 负责用例编排，每次数据库操作通过 Repository 完成。
- Repository 是 ORM 查询的唯一入口；常规查询禁止原生 SQL。
- Integration 隔离第三方模型、HTTP API 和操作系统能力。
- 所有外部输入和模型输出先经过 Pydantic schema 校验。

启动命令：

```powershell
.\run.ps1
```

OpenAPI 文档位于 `http://127.0.0.1:8000/api/docs`。

## 字幕模式

- 快速模式：FunASR Paraformer-zh，默认 CPU，适合日常批量整理。
- 精准模式：faster-whisper large-v3，保留词级时间戳，适合口音、专名和嘈杂音轨。

精准模式默认使用 CPU int8，但必须在上线前执行模型安装脚本：

    powershell.exe -ExecutionPolicy Bypass -File ..\tools\install_precise_model.ps1

模型未就绪时，健康接口返回 preciseModelReady=false，前端禁用精准模式；用户任务不会临时
下载 3.09 GB 权重。GPU 服务器可设置：

精准转写会按已处理的音频时间持续更新任务进度。当前 Windows CPU `int8` 实测 541.955 秒
中文视频耗时 997.06 秒；本地界面会提示该量级，正式服务器建议使用 GPU 推理。

MiniMax 返回的 JSON 会经过 Pydantic 字段约束和章节覆盖校验。完整 JSON 若不合规，服务会将
校验错误反馈给模型修复一次；最后章节必须覆盖到主要内容末尾，避免摘要成功但后半段没有章节。

```text
XUNLEI_PRECISE_ASR_DEVICE=cuda
XUNLEI_PRECISE_ASR_COMPUTE_TYPE=int8_float16
```

默认在服务启动后后台预热快速 ASR（`XUNLEI_PRELOAD_ASR=true`），减少用户第一次选择快速模式时
停留在模型加载阶段的时间；预热线程与用户分析任务执行器相互独立，不会下载或加载精准模型。
资源紧张的部署环境可显式设为 `false`。

安装脚本使用 aria2、ModelScope 国内 CDN、文件大小和 SHA256 完整性校验，支持断点续传。

CUDA 模式需要 CTranslate2 对应的 CUDA 12 cuBLAS 与 cuDNN 9 动态库。服务不会自动降级后
伪装成精准结果；运行库缺失时任务会明确失败，并提示用户切换快速模式。
