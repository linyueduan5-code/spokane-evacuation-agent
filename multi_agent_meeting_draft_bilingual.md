# 灾害响应多智能体系统：会前讨论草稿
# Disaster-Response Multi-Agent System: Pre-Meeting Draft

> 目标 / Goal：为 NVIDIA 黑客马拉松定义一个两天内可实现、可验证、可扩展的 MVP。会议集中讨论三件事：多智能体边界、统一数据口径、虚拟数据与评测方法。

## 1. 一句话项目定义 / One-sentence definition

**中文：** 系统根据居民位置、时间和家庭需求，同时查询撤离等级、火场、道路与避难所信息，生成安全、可解释、可追溯的撤离方案。

**English:** Given a resident's location, time, and household needs, the system combines evacuation, fire, road, and shelter data to produce a safe, explainable, and traceable evacuation plan.

## 2. 为什么从“单智能体 + 工具”升级 / Why go beyond one agent with tools

原方案本质上是一个 LLM 调用多个工具，适合快速原型，但所有判断都集中在同一个上下文中。多智能体的价值不是为了增加数量，而是把互相独立、可以并行且可能互相冲突的任务分开：

The original design is essentially one LLM calling multiple tools. That is suitable for rapid prototyping, but it concentrates all decisions in one context. The reason to introduce multiple agents is not agent count; it is to separate independent, parallel, and potentially conflicting decisions.

- **态势智能体 / Situation Agent**：判断撤离等级、火场距离、数据时效和风险。
- **路线智能体 / Routing Agent**：排除封路、火场、危险区，计算安全可达路线。
- **资源智能体 / Resource Agent**：根据容量、轮椅、医疗和宠物需求筛选避难所。
- **调度智能体 / Supervisor Agent**：并行调用以上智能体，合并候选方案并处理冲突。
- **确定性安全审核器 / Deterministic Safety Guard**：使用固定规则审核最终建议；它不应只是另一个 LLM。

MVP 不需要七八个智能体。建议采用 **1 个调度智能体 + 3 个专业智能体 + 1 个规则审核器**。通知、寻人和灾后返家可以作为后续扩展。

The MVP does not need seven or eight agents. Use **one supervisor, three specialist agents, and one rule-based safety guard**. Notifications, reunification, and post-fire re-entry can remain future work.

## 3. MVP 最小输入 / Minimum MVP inputs

### 用户必须提供 / Required user inputs

1. **位置 / Location**：GPS 经纬度优先，地址作为备用。
2. **时间 / Time**：默认当前时间；演示模式允许选择历史时间点。
3. **关键需求 / Critical needs**：轮椅或行动不便、医疗支持、宠物/服务动物。

用户不需要先理解 Level 1/2/3，也不需要手动选择避难所。系统应通过位置自动判断。

The user should not need to understand evacuation levels or select a shelter manually. The system determines these from location and available data.

### 系统必须具备 / Required system inputs

1. 撤离区多边形及其等级、官方指令和生效时间。
2. 火场边界、更新时间与事件标识。
3. 道路网络和道路封闭状态。
4. 避难所位置、开放状态及已知服务能力。
5. 每条数据的来源、抓取时间、有效时间和可信等级。

### MVP 输出 / MVP output

- 当前撤离等级与“立即行动”提示。
- 一个首选避难所和一个备选避难所。
- 至少一条避开已知危险和封路的路线。
- 无法确认的信息明确显示为“未知”，不得推测为安全。
- 展示所用数据来源、时间戳和智能体步骤。

## 4. 建议流程 / Proposed workflow

```text
用户位置 + 时间 + 家庭需求
              ↓
          调度智能体
       ↙       ↓       ↘
  态势智能体  路线智能体  资源智能体
       ↘       ↓       ↙
          候选撤离方案
              ↓
       确定性安全审核器
        ↙             ↘
   通过：显示方案     否决：重新规划/升级人工处理
```

Level 3 不应跳过轮椅、医疗或宠物筛选。正确流程是立即显示“马上撤离”，同时并行搜索满足硬性需求且可安全到达的避难所。

At Level 3, the system must not skip wheelchair, medical, or animal requirements. It should issue the immediate evacuation warning first while simultaneously finding a reachable shelter that satisfies hard constraints.

## 5. 数据口径统一 / Data normalization and source of truth

### 数据源优先级 / Source priority

| 领域 / Domain | MVP 首选来源 / Preferred source | 使用原则 / Rule |
|---|---|---|
| 撤离区 | Spokane SREC 官方 GIS | 用坐标做 point-in-polygon；不要手绘作为默认方案 |
| 火场边界 | NIFC WFIGS | 保留观测时间；边界之外仍加入安全缓冲区 |
| 火灾日报与损失 | NIFC IMSR | 作为带日期的官方快照，不覆盖后来修订 |
| 避难所 | FEMA ESF #6 Shelter System | Unknown 不能转换成 No 或 Yes；必要时提示电话确认 |
| 州级封路 | WSDOT Road Alerts | 只覆盖州级道路，需与地方封路数据合并 |
| 地方封路 | Spokane County/SREC | 数据为空或过期时必须显示覆盖不足 |

### 所有记录的公共字段 / Common metadata for every record

```json
{
  "record_id": "...",
  "event_id": "...",
  "source_id": "SREC|WFIGS|NIFC|FEMA|WSDOT|SYNTHETIC",
  "data_class": "official|derived|synthetic",
  "observed_at": "ISO-8601 timestamp",
  "valid_from": "ISO-8601 timestamp",
  "valid_to": null,
  "fetched_at": "ISO-8601 timestamp",
  "authority_tier": 1,
  "confidence": 0.0,
  "geometry": null,
  "provenance_url": "..."
}
```

### 冲突处理规则 / Conflict-resolution rules

1. 不把新记录静默覆盖旧记录；每次更新保存为快照。
2. 界面显示“截至何时 / as of”，并标明来源。
3. 同级来源冲突时，安全相关字段采用更保守值，同时显示冲突。
4. 数据超过规定 TTL 后标记 stale，不能据此宣布“可以返家”。
5. SREC 公共图层中没有某撤离区，不等于官方已经 All Clear；必须取得明确解除通知。

Do not silently overwrite conflicting records. Preserve snapshots, show provenance, prefer the more conservative safety interpretation, and require an explicit all-clear before recommending re-entry.

### 当前需要统一的损失数字 / Damage-count discrepancy to resolve

朋友方案写的是 Old Trails 694、Autumn Lane 168、Fairview 59；现有研究中找到的 NIFC 2026-08-10 日报快照是 **569、149、56**。这些数字可能继续修订，因此演示时应使用“来源 + 日期 + 字段定义”，而不是声称存在一个永久正确的数字。

The friend's draft lists 694, 168, and 59 structures lost. The NIFC 10 Aug 2026 snapshot in our research lists **569, 149, and 56**. Since operational figures may be revised, the demo must attach a source, date, and definition rather than presenting a timeless total.

## 6. 虚拟数据集设计 / Synthetic dataset design

### 基本原则 / Principles

- 真实公开数据只作为地理和时间线基础。
- 容量、签到、个人身份、医疗需求等敏感或缺失字段全部使用合成数据。
- 每条记录明确标为 `official`、`derived` 或 `synthetic`，界面不得混淆。
- 合成数据使用虚构姓名、电话和地址，不映射真实居民。
- 演示数据与生产数据物理或逻辑隔离。

Use public data as the geographic and timeline foundation. Shelter capacity, check-ins, identities, and sensitive household information should be synthetic. Every record must be labeled as official, derived, or synthetic.

### 建议数据表 / Suggested tables

| 表 / Table | 内容 / Content |
|---|---|
| `incident_snapshots` | 火场边界、面积、控制率及时间快照 |
| `evacuation_zone_snapshots` | Level、边界、官方消息、生效区间 |
| `road_status_snapshots` | 道路开放/封闭、原因、更新时间 |
| `shelter_snapshots` | 开放状态、合成容量、宠物/轮椅/医疗能力 |
| `household_cases` | 合成家庭位置与需求 |
| `expected_actions` | 每个测试场景预期撤离、路线和避难所结果 |
| `source_registry` | 来源权威等级、TTL、许可证与接口信息 |

### 最小测试场景矩阵 / Minimum scenario matrix

建议先做 **30–50 个可重复场景**，覆盖：

- Level 1、2、3 和明确 All Clear。
- 撤离区数据缺失或已经过期。
- SREC 与其他来源发生冲突。
- 最近道路被封，必须选择绕行路线。
- 首选避难所已满或路线不可达。
- 轮椅、医疗、宠物以及多个条件组合。
- 没有完全符合条件的避难所，需要人工升级处理。
- 火场边界更新后，原路线失效并触发重新规划。

Build **30–50 deterministic scenarios** covering evacuation levels, stale and conflicting data, road closures, full or unreachable shelters, accessibility constraints, no-valid-option cases, and route invalidation after a fire update.

## 7. Agent 评分与改进闭环 / Agent evaluation and improvement loop

建议将评分分成两层，而不是只给一个平均分。

Use a two-layer evaluation rather than a single average score.

### 第一层：安全硬门槛 / Layer 1: hard safety gates

出现以下任意情况，该案例直接判为失败：

- 建议用户进入 Level 3、火场、危险品区或已封闭道路。
- 把不确定或过期数据表述成“安全”。
- 给轮椅用户推荐明确不具备无障碍条件的地点。
- 忽略官方 Level 3 立即撤离命令。
- 在没有明确 All Clear 的情况下建议返家。

Any route through a known hazard, misuse of stale/unknown data, violation of a hard accessibility need, failure to prioritize a Level 3 order, or unsupported re-entry advice causes an automatic failure.

### 第二层：质量评分 / Layer 2: quality score (100 points)

| 指标 / Metric | 权重 / Weight |
|---|---:|
| 撤离等级和风险判断正确 / Situation correctness | 25 |
| 路线安全且可达 / Route feasibility | 20 |
| 避难所满足硬性需求 / Constraint satisfaction | 15 |
| 数据来源、时间戳与冲突处理 / Provenance and freshness | 15 |
| 对未知和不确定性的表达 / Uncertainty handling | 10 |
| 任务完成度与行动清晰度 / Task completion and clarity | 10 |
| 延迟与工具调用效率 / Latency and tool efficiency | 5 |

### 如何“学习”评分 / How the system learns from scores

黑客马拉松阶段不建议让系统在灾害现场在线自我训练。更安全的方式是离线评测闭环：

Do not let the system self-train online during a disaster. Use an offline evaluation loop:

```text
运行固定虚拟场景
      ↓
记录每个智能体的输入、工具调用和输出
      ↓
安全规则 + 预期答案 + LLM Judge 辅助评分
      ↓
生成失败标签：数据过期 / 路线危险 / 条件遗漏 / 来源冲突
      ↓
人工审核后修改规则、提示词、工具选择或调度策略
      ↓
重新运行回归测试
```

LLM Judge 只能评价解释质量和自然语言，不能单独决定路线是否安全；空间相交、封路、撤离等级和无障碍条件应由确定性程序评分。

An LLM judge may assess explanation quality, but it must not decide route safety by itself. Geometry intersections, closures, evacuation levels, and accessibility constraints require deterministic checks.

> 注 / Note：这里暂时把“AA 评分”理解为 Agent 的自动评测机制。如果 AA 指某个具体平台或比赛评分标准，需要在会上确认后重新映射指标。

## 8. 隐私边界 / Privacy boundary

失踪人员报告和避难所签到不建议进入第一版 MVP。若为了故事完整必须演示：

- 只使用完全合成的人员与签到数据。
- 明确标注“Demo / Synthetic”。
- 查询必须经过用户同意，并限制访问角色。
- 日志不得记录不必要的姓名、电话和医疗细节。
- 演示结束后可以一键清除数据。

Missing-person and shelter check-in features should stay outside the first MVP. If included for storytelling, use fully synthetic records, explicit consent, role-based access, minimal logging, and easy deletion.

## 9. 两天 MVP 建议范围 / Recommended two-day scope

### 必做 / Must have

- 1 个预设家庭案例，另加 30–50 个后台测试案例。
- SREC 撤离区、WFIGS 火场、FEMA 避难所接口或固定快照。
- 合成道路封闭和避难所能力/容量数据。
- 调度、态势、路线、资源三个决策模块。
- 安全审核器、数据时间戳和来源展示。
- Agent Steps 面板和一条完整演示故事。

### 可以延后 / Defer

- 真实短信或邮件发送。
- 真实失踪人员数据库。
- 完整实时地图动画。
- 自动在线学习。
- 大规模车队、救护车和跨避难所全局优化。

## 10. 会议希望确定的问题 / Decisions for the meeting

1. 我们是否同意采用“1 个 Supervisor + 3 个专业 Agent + 规则安全审核器”？
2. MVP 的最小用户输入是否只保留位置、时间和三类关键需求？
3. 哪些数据使用实时 API，哪些锁定为带时间戳的回放快照？
4. 是否以 NIFC 2026-08-10 快照作为演示损失数字基线？
5. 合成数据由谁负责生成、审核和维护预期答案？
6. “AA 评分”具体指通用 Agent Eval，还是某个既定平台/赛事指标？
7. 寻人流程是否完全移出 MVP，只放在 Future Work？

### 建议的会议结论 / Desired meeting outcome

会议结束前锁定一张系统边界图、一份字段字典、一套 30–50 条测试场景，以及一个可执行的两天开发分工。此后新增想法统一进入 Future Work，不再扩大 MVP。

By the end of the meeting, lock one system-boundary diagram, one shared data dictionary, a suite of 30–50 test scenarios, and a two-day implementation assignment. New ideas go to Future Work rather than expanding the MVP.
