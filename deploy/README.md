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

## 腾讯云轻量部署

腾讯云小规格服务器建议在根目录 `.env` 中增加：

```env
XUNLEI_BACKEND_DOCKERFILE=Dockerfile.backend.cloud
XUNLEI_WEB_PORT=18080
XUNLEI_PRELOAD_ASR=false
XUNLEI_PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple
XUNLEI_PUBLIC_BASE_URL=http://公网IP:18080
```

`Dockerfile.backend.cloud` 只安装 FastAPI、SQLite、PyAV、MiniMax 与火山 ASR API 所需依赖，不安装
`torch`、`FunASR`、`faster-whisper` 和 `stable-ts`。这样公网 Demo 可以稳定使用 ASR API 识别；本地
Whisper large-v3 精准模式仍保留给安装包或高配私有部署。镜像构建时直接使用基础镜像内置 pip，
避免公网服务器因为额外下载 pip 或系统包而长时间阻塞。

如果服务器 80/443 端口已有其他业务，不要覆盖原域名配置。当前腾讯云演示采用“IP 兜底入口”：
Compose 仍监听 `18080`，宿主机 Nginx 只新增 `server_name 62.234.39.243 _` 的
`default_server`，把 `http://62.234.39.243/` 反向代理到 `http://127.0.0.1:18080`。
已有 `weilai.wit-motion.cn` 精确域名仍命中原来的站点配置。

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
