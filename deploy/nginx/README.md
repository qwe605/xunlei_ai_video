# Nginx 部署说明

`default.conf` 同时承担 React 静态文件服务和 FastAPI 反向代理：

- 将 `app/dist/` 挂载到 `/usr/share/nginx/html`。
- 将 FastAPI 服务注册为 Docker/内网主机名 `backend:8000`。
- `/api/` 请求保留原路径代理到后端。
- 非静态文件路径回退到 `index.html`，保证页面深链接刷新可用。
- 视频上传上限与后端默认值保持为 300 MB。
