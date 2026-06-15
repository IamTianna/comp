# AI 驱动的竞品分析 Agent 协作系统

这是一个独立 Web App，不再依赖 Coze，也不依赖 `codeact_sdk`。

系统由 FastAPI 后端、6 个独立 Agent 脚本、统一 LLM/Search/Fetch 客户端、前端 Agent 工作间组成。

## 项目结构

```text
frontend/index.html
backend/server.py
backend/clients/llm_client.py
backend/clients/search_client.py
backend/clients/fetch_client.py
backend/models/schemas.py
backend/services/run_manager.py
backend/services/artifact_loader.py
scripts/planning_agent.py
scripts/collecting_agent.py
scripts/structuring_agent.py
scripts/comparing_agent.py
scripts/writing_agent.py
scripts/quality_agent.py
scripts/orchestrator.py
data/demo/
output/
logs/
```

## 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 配置环境变量

```bash
cp .env.example .env
```

Demo mode 不需要 API Key。真实 API mode 需要配置：

```text
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
TAVILY_API_KEY=...
```

当缺少 LLM 或搜索 API Key 时，系统自动进入 Demo mode，使用 `data/demo/` 跑通完整流程，并在前端标注 Demo mode。

## 启动后端

```bash
uvicorn backend.server:app --reload --host 127.0.0.1 --port 8000
```

然后打开：

```text
http://127.0.0.1:8000/
```

也可以直接打开 `frontend/index.html`，此时前端会请求 `http://127.0.0.1:8000`。

## 运行 Demo

点击首页的“运行多 Agent 协作 Demo”。前端会调用：

```text
POST /api/runs
```

后端会按顺序运行：

```text
planning -> collecting -> structuring -> comparing -> writing -> quality -> final
```

每 2 秒轮询：

```text
GET /api/runs/{run_id}/status
```

## 产物位置

每次运行都会创建独立目录：

```text
output/{run_id}/
logs/{run_id}/
```

主要产物：

- `planning_result.json`
- `collected_sources.json`
- `structured_schema_table.json`
- `comparison_analysis.json`
- `report_draft.md`
- `report_metadata.json`
- `quality_report.json`
- `competitive_report_final.md`
- `result.json`
- `logs/{run_id}/status.json`
- `logs/{run_id}/pipeline.json`
- `logs/{run_id}/error.json`，仅失败时生成

## API 对应关系

- `POST /api/runs`：启动一次多 Agent 任务
- `GET /api/runs/{run_id}/status`：读取运行状态
- `GET /api/runs/{run_id}/logs`：读取流水日志
- `GET /api/runs/{run_id}/agent/{agent_id}`：读取某个 Agent 产物
- `GET /api/runs/{run_id}/result`：读取最终报告和所有关键产物
- `GET /api/runs/{run_id}/artifacts`：列出产物文件

## Agent 职责

- Planning Agent：理解任务、收窄范围、生成任务规划结果。
- Collecting Agent：调用搜索 API 和网页抓取，生成公开资料包。
- Structuring Agent：整理统一竞品知识 Schema，标记缺失和冲突。
- Comparing Agent：生成对比矩阵、行业共性、差异和机会点。
- Writing Agent：生成带来源、证据链和风险边界的 Markdown 报告初稿。
- Quality Agent：检查来源完整性、字段一致性、结论支撑和推断跳跃，必要时给出回退建议。

## 降级策略

- 缺少 `OPENAI_API_KEY` 或 `TAVILY_API_KEY`：自动 Demo mode。
- 搜索或抓取失败：允许使用搜索摘要作为弱来源。
- 单步失败：写入 `logs/{run_id}/error.json`，前端可显示失败原因。
- 质检不通过：最多触发一次自动修订，避免无限回退。
