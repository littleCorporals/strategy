# Tushare 行情展示平台

这是一个本地 FastAPI 展示平台，通过 Tushare SDK 查询日线行情，并在浏览器里展示概览、涨跌分布、筛选排序表格和 CSV 导出。

## 运行

1. 安装依赖：

```powershell
python -m pip install -r requirements.txt
```

2. 配置 token：

```powershell
New-Item .env -ItemType File
notepad .env
```

把 `.env` 里的 `TUSHARE_TOKEN` 改成你的 token。平台启动后只在后端读取 token，不会发到前端页面。

3. 启动服务：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 [http://127.0.0.1:8000](http://127.0.0.1:8000) 即可使用。

模型管理 MVP 入口：[http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin)。

## 配置项

- `TUSHARE_TOKEN`：Tushare token。
- `TUSHARE_PROXY_URL`：可选代理地址，通过本地 `.env` 或环境变量配置。
- `TUSHARE_MIN_INTERVAL`：最小请求间隔，默认 `0.65` 秒，用来降低触发限流的概率。
- `MARKET_CACHE_DB`：本地 SQLite 缓存库位置，默认 `data/market_cache.sqlite3`。
- `MARKET_REFRESH_AFTER`：当日行情允许刷新时间，默认 `15:10`。

## 本地数据缓存

行情数据先读本地 SQLite。请求的交易日如果本地没有完整数据，并且满足刷新时间规则，后端才会请求第三方数据服务；成功返回后会同步写入本地库，下次相同日期优先读数据库。

数据库默认是文件存储：`data/market_cache.sqlite3`。主要表包括 `market_rows`、`sync_state`、`cached_payloads`，以及为后续机器学习准备的 `ml_models`、`ml_training_runs`、`ml_pipeline_runs`、`ml_predictions`、`ml_validation_results`。

## 模型模块

业务接口仍在 `app/` 下；模型相关规划放在独立的 `modeling/` 包中，当前 MVP 先提供特征集、标签集、训练任务队列、模型注册表和流水线概览。真实训练器、模型产物和每日批量预测可以后续接到 `ml_training_runs` 和 `ml_pipeline_runs`。

## 工程结构

```text
app/
  main.py              # 应用工厂、CORS、静态资源、路由挂载
  admin/               # 模型管理台 API
  api/routes/          # HTTP 路由，当前行情业务在 market.py
  services/            # 后续放纯业务服务
  clients/             # 后续放 Tushare、巨潮、AI 等第三方适配器
  repositories/        # 后续放数据库仓储
  schemas/             # 后续放请求/响应模型
  db/                  # SQLite 连接、缓存、模型仓储
  core/                # 配置和基础设施
modeling/              # 独立模型工程，不反向依赖 app
migrations/            # 后续数据库迁移脚本
tests/                 # 后续自动化测试
```

## 接口

- `GET /api/status`：检查依赖、token 和代理配置。
- `GET /api/daily?trade_date=20260423`：查询日线行情。
- `GET /api/daily.csv?trade_date=20260423`：导出 CSV。
- `GET /api/admin/overview`：模型管理概览。
- `POST /api/admin/training-runs`：创建一个训练排队任务。
