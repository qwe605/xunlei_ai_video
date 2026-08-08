# 公网部署底座

本目录保留 Nginx 反向代理配置。仓库根目录新增 `Dockerfile.backend`、`Dockerfile.frontend` 和
`docker-compose.yml`，用于训练营提交前快速拉起一套前后端服务。

## 启动

```powershell
cd E:\xunlei
copy backend\.env.example .env
# 在 .env 中填入 MINIMAX_API_KEY、XUNLEI_PUBLIC_BASE_URL 和火山 ASR 凭证，不要提交 .env
docker compose up --build
```

默认访问地址：

- 前端：`http://127.0.0.1:8080`
- 后端健康检查：`http://127.0.0.1:8080/api/v1/health`

## 数据与模型

- `xunlei-data`：保存 SQLite 数据库和上传媒体。
- `xunlei-models`：保存 Hugging Face、ModelScope 和 faster-whisper 模型缓存。
- `MINIMAX_API_KEY`、`MINIMAX_MODEL`、`MINIMAX_BASE_URL` 均从环境变量注入。
- `VOLC_ASR_API_KEY` 或 `VOLC_ASR_APP_ID` + `VOLC_ASR_ACCESS_TOKEN` 用于火山引擎 ASR API；`XUNLEI_PUBLIC_BASE_URL` 必须填写评委可访问的公网域名或公网 IP，否则云端 ASR 无法拉取临时音频。

## 腾讯云演示限制

当前腾讯云小规格服务器默认不加载本地 Whisper large-v3 精准模式。线上演示提供快速识别和 ASR API 识别；本地精准识别保留给安装包版本，避免 large-v3 权重和 CPU 推理时间拖垮公网 Demo。

## 仍需上线前补齐

当前 Compose 是可演示底座，不是完整生产方案。公网提交前仍应补服务端鉴权、用户隔离、上传
限流、任务取消、HTTPS 证书、结构化日志和备份策略。
