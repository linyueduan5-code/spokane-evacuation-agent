# EMBER — Spokane Evacuation Agent MVP

一个可直接演示的灾害响应 MVP：**1 个 Agent 编排 7 个工具**，React 前端，FastAPI 后端。系统基于 Spokane 2026 火灾时间线回放，结合官方来源快照与明确标注的合成数据，在没有模型密钥和网络的情况下也能稳定运行。

This is a runnable disaster-response MVP: **one agent orchestrating seven tools**, with a React frontend and FastAPI backend. It replays the 2026 Spokane wildfire scenario using official-source snapshots plus explicitly labeled synthetic data.

## 已实现 / Delivered

- `get_evacuation_status`：坐标匹配撤离多边形，处理来源冲突，缺失不等于 All Clear。
- `get_active_incidents`：返回附近火灾、边界、时间戳及采用统一口径的损失数字。
- `find_shelters`：把宠物、行动辅助和医疗作为硬条件，同时避开已知封路走廊。
- `check_hazmat_clearance`：没有明确放行时禁止建议返家。
- `file_missing_person`：必须获得授权，仅写入内存合成数据。
- `search_missing_reports`：只搜索合成签到记录。
- `send_notification`：模拟通知，不向任何外部服务发送信息。
- 时间线、一键预设、地图、路线、数据来源和 Agent Steps 面板。
- 可选 openrouteservice 实际道路路线；自动避开当前封路缓冲区，失败时回退到离线候选走廊。
- 可选 Mapbox Temporary Geocoding 地址搜索；后端代理、500ms 前端防抖、最小输入长度和内存缓存控制调用量。
- SREC、WFIGS、FEMA、WSDOT 的真实 API 适配器接口；MVP 默认不依赖网络。
- NVIDIA NIM OpenAI-compatible 客户端接口；默认使用确定性编排，不需要密钥。
- 40 条合成评测场景、硬性安全门槛、100 分质量评分和浏览器评测面板。

## 架构 / Architecture

```text
React + Leaflet (:5173)
          ↓
FastAPI (:8000)
          ↓
EvacuationAgent — deterministic single orchestrator
          ↓
7 tools → replay snapshots + in-memory synthetic store
          ↓
optional public-data adapters / NVIDIA NIM seam
```

Agent 首先查询撤离状态，然后并行调用火情、避难所/路线和危险品工具。Level 3 会立即发出撤离与模拟通知，但不会跳过轮椅、医疗或宠物筛选。

## 快速启动 / Quick start

首次运行：

```bash
cd /Users/danny/Documents/救灾
./scripts/bootstrap.sh
```

启动前后端：

```bash
./scripts/run.sh
```

打开 [http://127.0.0.1:5173](http://127.0.0.1:5173)。FastAPI 文档位于 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)。

当前开发会话中的两个服务已经启动。如果端口被占用，可先终止旧进程，再运行脚本。

## 演示流程 / Demo flow

1. 保持预设 `Rifle Club Road`、Pets 和 Mobility 已选中。
2. 选择 `AUG 1`，点击 `RUN EVACUATION PLAN`。
3. 展示 Level 3、火情、避难所、安全候选路线、来源冲突和 5 个工具步骤。
4. 点击 `AUG 7` 后再次运行，展示 Level 2 但危险品未放行，因此禁止返家。
5. 打开 `Synthetic reunification demo`，勾选授权并搜索 `Avery Chen`，展示其余三个工具。

## 数据口径 / Data policy

| 领域 | 来源 | MVP 使用方式 |
|---|---|---|
| 撤离区 | Spokane SREC | 官方来源回放快照；point-in-polygon |
| 火场 | WFIGS / NIFC IMSR | 回放边界；损失数字使用 2026-08-10 日报口径：Old Trails 569、Autumn Lane 149、Fairview 56 |
| 避难所 | FEMA ESF #6 | 位置/名称基于公开记录；能力与容量为合成数据 |
| 道路 | WSDOT + synthetic | API 接口已预留；演示封路为合成走廊 |
| 危险品 | Synthetic | 只作为返家安全分支演示 |
| 人员/签到 | Synthetic | 虚构姓名和内存存储，不提交至政府机构 |

每条安全相关记录携带 `source_id`、`source_class`、`observed_at`、`as_of` 和 `stale`。冲突不会被静默覆盖，未知不会被解释为安全。

## API 插槽 / API seams

公共数据适配器位于 `backend/app/adapters.py`：

- `fetch_srec_evacuation`
- `fetch_wfigs`
- `fetch_fema_shelters`
- `fetch_wsdot_closures`

NIM 配置见 `.env.example`。`backend/app/llm.py` 已实现 OpenAI-compatible `/chat/completions` 客户端，但没有接管安全规则；之后接入模型时，应只用于意图理解和解释生成，空间与撤离安全判断继续由确定性代码负责。

真实路线可通过本地 `.env` 开启（密钥不要提交到 GitHub）：

```env
ROUTING_PROVIDER=openrouteservice
ORS_API_KEY=your-local-key
MAPBOX_ACCESS_TOKEN=your-public-token
```

系统会向 ORS 请求实际道路折线、距离和预计时间，并把演示中的当前封路转换为避让多边形。外部服务失败时会明确标记并回退，不会把失败解释为道路安全。

## 合成评测集 / Synthetic evaluation suite

数据集位于 `backend/data/evaluation_scenarios.json`，由 `scripts/generate_eval_dataset.py` 确定性生成。共 40 个场景、8 个类别：

- Level 3 紧急响应
- 数据过期
- 来源冲突
- 封路绕行
- 避难所满员
- 轮椅、医疗和宠物硬约束
- 没有安全可用避难所
- 返家与危险品安全

评分先执行安全硬门槛。危险路线、忽略官方 Level 3、违反无障碍硬条件、把过期数据当作安全证据、未明确解除警报便建议返家，都会令该案例直接归零。通过硬门槛后，再按态势 25、路线 20、需求 15、来源与时效 15、不确定性 10、任务完成 10、工具效率 5 计分。

页面右上角 `RUN 40-CASE EVALUATION` 会运行完整评测并展示结果。也可以调用：

```bash
curl -X POST http://127.0.0.1:8000/api/evaluation/run
```

未来 NIM、Prompt 或多智能体版本可以将自己的结构化输出提交到 `POST /api/evaluation/score`，使用同一套场景和规则比较。

当前 100 分是**确定性基线对为其设计的合成回归集的结果**，不是生产准确率、真实灾害安全保证或外部独立基准。负向控制测试已经验证评分器能够捕获危险路线、忽略无障碍需求和错误返家建议。

## DeepSeek 临时 Agent Provider

在 NVIDIA NIM 可用前，项目支持 DeepSeek 的 OpenAI-compatible Function Calling。配置 `.env`：

```env
AGENT_PROVIDER=deepseek
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_API_KEY=your-local-key
DEEPSEEK_MODEL=deepseek-v4-flash
```

DeepSeek 负责理解请求并选择七个工具。确定性安全层会补齐缺失的撤离、火情、避难所和危险品查询，并负责最终居民安全结论。界面的 Agent Steps 会分别标记 `model` 与 `safety guard` 调用。`.env` 已被 Git 忽略，不应提交或发送给他人。

## 验证 / Verification

```bash
cd /Users/danny/Documents/救灾/backend
../.venv-runtime/bin/python -m pytest -q

cd /Users/danny/Documents/救灾/frontend
npm run build
```

测试覆盖 Level 3 的宠物/行动辅助硬条件、道路避让、冲突优先级、寻人授权、七工具覆盖和 Level 2 返家限制。

## 安全边界 / Safety boundary

这是黑客马拉松决策支持演示，不是 911、官方撤离命令或经过认证的导航服务。路线是候选安全走廊，不提供逐向导航；出发前必须核对官方命令、道路状态并联系避难所。真实部署还需要认证、角色权限、审计、加密、数据保留政策、运行监控和应急机构审核。
