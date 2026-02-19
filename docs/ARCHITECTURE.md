# Emission Agent 架构文档

## 目录

1. [系统概述](#系统概述)
2. [整体架构](#整体架构)
3. [核心组件](#核心组件)
4. [工作流程](#工作流程)
5. [数据流](#数据流)
6. [Agent-Skill架构](#agent-skill架构)
7. [上下文管理](#上下文管理)
8. [智能列名映射](#智能列名映射)
9. [Web架构](#web架构)
10. [关键技术](#关键技术)
11. [最近改进 (v1.2.0)](#最近改进-v120)

---

## 系统概述

Emission Agent 是一个基于 **Agent-Skill 架构** 的智能机动车排放计算系统。系统通过自然语言理解用户意图，自动调用相应的计算模块，并以对话形式返回结果。

### 设计理念

1. **Agent-Skill 分离**: Agent 层轻量，Skill 层重量
2. **智能标准化**: 使用 LLM 进行车型/污染物标准化，而非硬编码规则
3. **本地模型支持**: 支持本地微调模型，降低成本、提升性能、保护数据隐私
4. **对话式交互**: 支持多轮对话、追问、上下文记忆
5. **灵活性**: 支持多种输入方式（文本、文件、JSON）

### 系统能力

| 能力 | 描述 | 技术基础 |
|------|------|----------|
| 排放因子查询 | 查询 MOVES 数据库的速度-排放曲线 | MOVES Matrix |
| 微观排放计算 | 基于逐秒轨迹计算排放 | VSP 方法 |
| 宏观排放计算 | 基于路段数据计算排放 | MOVES-Matrix |
| 知识检索 | 检索排放计算相关文档 | 向量检索 |
| 智能映射 | 自动理解 Excel 列名 | LLM |
| 本地标准化 | 使用本地微调模型进行标准化 | VLLM + LoRA |

---

## 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户界面层                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  Web 界面    │  │   CLI 界面   │  │   API 接口   │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Agent 层                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  Core Agent  │  │  Validator   │  │  Reflector   │           │
│  │  (意图理解)   │  │  (参数验证)   │  │  (反思机制)   │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│  ┌──────────────┐  ┌──────────────┐                             │
│  │   Context    │  │   Learner    │                             │
│  │  (上下文管理) │  │  (学习机制)   │                             │
│  └──────────────┘  └──────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Skill 层                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ 排放因子查询  │  │ 微观排放计算  │  │ 宏观排放计算  │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│  ┌──────────────┐                                              │
│  │  知识检索     │                                              │
│  └──────────────┘                                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       共享服务层                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  标准化器     │  │  LLM 客户端  │  │  文件处理器  │           │
│  │  (API/本地)  │  └──────────────┘  └──────────────┘           │
│  └──────┬───────┘                                                │
│         │                                                         │
│         ├─ API模式: 调用云端LLM (qwen-flash)                     │
│         └─ 本地模式: 调用本地VLLM服务 (Qwen3-4B + LoRA)          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       数据层                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ MOVES 数据   │  │ 向量索引      │  │  会话存储     │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    本地模型层 (可选)                              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  WSL2 + VLLM Service (port 8001)                           │ │
│  │  ├─ 基础模型: Qwen3-4B-Instruct-2507                       │ │
│  │  ├─ LoRA适配器: unified (车型+污染物标准化)                │ │
│  │  └─ LoRA适配器: column (列名映射)                          │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 核心组件

### 1. Agent Core (`agent/core.py`)

**职责**:
- 理解用户意图
- 规划任务执行
- 协调 Skill 调用
- 综合返回结果

**核心方法**:

```python
class Agent:
    def chat(self, message: str) -> str:
        """主入口：处理用户消息"""

    def _plan(self, message: str) -> List[SkillCall]:
        """规划需要执行的 Skill"""

    def _execute_skill(self, skill_call: SkillCall) -> SkillResult:
        """执行单个 Skill"""

    def _synthesize(self, results: List[SkillResult]) -> str:
        """综合 Skill 结果生成回复"""
```

**System Prompt 结构**:
```
你是一个机动车排放计算助手。

可用工具:
- query_emission_factors: 查询排放因子
- calculate_micro_emission: 微观排放计算
- calculate_macro_emission: 宏观排放计算
- search_knowledge: 知识检索

工作流程:
1. 理解用户意图
2. 提取必要参数
3. 调用相应工具
4. 综合结果回复用户
```

### 2. Context Manager (`agent/context.py`)

**职责**:
- 管理对话历史
- 维护 Turn 状态
- 压缩上下文

**数据结构**:

```python
class Turn:
    """单次对话轮次"""
    user_input: str
    assistant_response: str
    skill_executions: List[SkillExecution]
    chart_data: Optional[Dict]
    table_data: Optional[Dict]
    data_type: Optional[str]
    timestamp: datetime

class Context:
    """对话上下文"""
    turns: List[Turn]
    session_id: str
    metadata: Dict

    def add_turn(self, turn: Turn):
        """添加新的对话轮次"""

    def get_summary(self) -> str:
        """获取上下文摘要"""
```

**上下文压缩策略**:
1. 保留最近 N 条完整对话
2. 保留所有 Skill 执行结果
3. 早期对话压缩为摘要
4. 保留用户偏好设置

### 3. Skill Registry (`skills/registry.py`)

**职责**:
- 注册所有可用 Skill
- 提供 Skill 发现机制
- 管理 Skill 依赖

```python
class SkillRegistry:
    _skills: Dict[str, Skill] = {}

    @classmethod
    def register(cls, skill: Skill):
        """注册 Skill"""

    @classmethod
    def get(cls, name: str) -> Skill:
        """获取 Skill"""

    @classmethod
    def list_all(cls) -> List[str]:
        """列出所有 Skill"""
```

### 4. Validator (`agent/validator.py`)

**职责**:
- 验证 Skill 参数
- 检查数据完整性
- 提供友好的错误提示

```python
class Validator:
    def validate_emission_query(self, params: Dict) -> ValidationResult:
        """验证排放查询参数"""

    def validate_trajectory(self, data: List) -> ValidationResult:
        """验证轨迹数据"""
```

---

## 工作流程

### 完整请求处理流程

```
用户输入消息
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 1. 前端处理 (web/app.js)                                      │
│    - 构建请求（message, session_id, file）                    │
│    - 显示加载动画                                              │
└──────────────────────────────────────────────────────────────┘
    │
    ▼ POST /chat
┌──────────────────────────────────────────────────────────────┐
│ 2. API 层 (api/routes.py)                                     │
│    - 接收请求                                                  │
│    - 处理文件上传                                              │
│    - 获取/创建会话                                             │
└──────────────────────────────────────────────────────────────┘
    │
    ▼ session.agent.chat(message)
┌──────────────────────────────────────────────────────────────┐
│ 3. Agent 层 (agent/core.py)                                   │
│    3.1 创建新的 Turn                                          │
│    3.2 规划：分析意图，提取参数                               │
│    3.3 执行：调用相应 Skill                                   │
│    3.4 综合：生成自然语言回复                                 │
└──────────────────────────────────────────────────────────────┘
    │
    ├─▶ Skill: query_emission_factors
│         │
│         ▼
│    ┌──────────────────────────────────────────────┐
│    │ 4. Skill 执行                                │
│    │    - 标准化参数（车型、污染物）               │
│    │    - 查询 MOVES 数据                         │
│    │    - 计算排放因子                            │
│    └──────────────────────────────────────────────┘
│         │
│         ▼
│    SkillResult { success: true, data: {...} }
│
├─▶ Skill: calculate_micro_emission
│         │
│         ▼
│    ┌──────────────────────────────────────────────┐
│    │ 4. Skill 执行                                │
│    │    - 解析上传文件                            │
│    │    - 智能列名映射                            │
│    │    - 验证数据完整性                          │
│    │    - 询问缺失参数（车型）                    │
│    │    - 计算 VSP 和排放                         │
│    │    - 生成结果文件                            │
│    └──────────────────────────────────────────────┘
│         │
│         ▼
│    SkillResult { success: true, data: {...} }
│
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. 上下文保存                                                  │
│    - 更新 Turn（skill_executions, 结果）                      │
│    - 压缩历史对话                                              │
│    - 保存到 SessionManager                                     │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 6. 响应构建                                                    │
│    - 提取当前 turn 的图表/表格数据                            │
│    - 构建 ChatResponse                                        │
│    - 清理回复文本（移除 JSON 等）                             │
└──────────────────────────────────────────────────────────────┘
    │
    ▼ JSON Response
┌──────────────────────────────────────────────────────────────┐
│ 7. 前端渲染                                                    │
│    - 移除加载动画                                              │
│    - 显示 Markdown 回复                                        │
│    - 渲染图表/表格                                            │
│    - 更新会话列表                                              │
└──────────────────────────────────────────────────────────────┘
```

### 多轮对话示例

```
User: "查询2020年小汽车的CO2排放因子"
      │
      ▼
Agent: [执行 query_emission_factors]
      返回图表 + "2020年小汽车的CO2排放因子如下..."

User: "那公交车呢？"
      │
      ▼
Agent: [上下文理解：延续上一个查询]
      [保持参数：pollutant=CO2, year=2020]
      [更新参数：vehicle_type=公交车]
      [执行 query_emission_factors]
      返回图表 + "2020年公交车的CO2排放因子如下..."
```

---

## 数据流

### 1. 排放因子查询数据流

```
用户输入
    │
    ▼
Agent: 提取参数
    │
    ├─ vehicle_type → 标准化器 → "Passenger Car"
    ├─ pollutant → 标准化器 → "CO2"
    └─ model_year → 验证器 → 2020
    │
    ▼
Skill: query_emission_factors
    │
    ├─ 读取 MOVES Matrix
    │  └─ atlanta_2025_1_55_65.csv
    │
    ├─ 插值计算
    │  └─ 生成 speed-emission 曲线
    │
    └─ 提取关键点
       └─ 30/60/90 km/h 排放值
    │
    ▼
返回数据结构:
{
  "speed_curve": [
    {"speed_kph": 5, "emission_rate": 180.5},
    {"speed_kph": 10, "emission_rate": 165.2},
    ...
  ],
  "query_summary": {
    "vehicle_type": "小汽车",
    "pollutant": "CO2",
    "model_year": 2020
  },
  "unit": "g/mile",
  "data_points": 73
}
    │
    ▼
前端: 渲染 ECharts 折线图
```

### 2. 微观排放计算数据流

```
用户上传文件
    │
    ▼
文件分析 (file_analyzer.py)
    │
    ├─ 读取文件结构
    │  └─ columns, sample_data, row_count
    │
    └─ 智能列名映射
       ├─ LLM 理解列名
       ├─ 生成映射关系
       └─ 应用映射
    │
    ▼
ExcelHandler (micro_emission/excel_handler.py)
    │
    ├─ 读取并验证数据
    │  └─ 检查必需列
    │
    ├─ 数据预处理
    │  ├─ 计算加速度（如缺失）
    │  ├─ 填充坡度（默认0%）
    │  └─ 单位转换
    │
    └─ 参数验证
       └─ 检查车型是否指定
    │
    ▼
Calculator (micro_emission/calculator.py)
    │
    ├─ VSP 计算
    │  └─ vsp = v * (1.1 * a + 9.81 * grade + 0.132) + 0.000302 * v^3
    │
    ├─ VSP Bin 分配
    │  └─ 将 VSP 分类到 20 个 Bin
    │
    └─ 排放计算
       ├─ 查找每个 Bin 的排放率
       └─ 逐秒累加排放
    │
    ▼
输出结果
    │
    ├─ Excel 文件
    │  └─ 逐秒排放明细
    │
    └─ 汇总数据
       ├─ 总排放量
       ├─ 排放率统计
       └─ 图表数据
    │
    ▼
前端: 渲染结果表格
```

---

## Agent-Skill 架构

### 设计原则

| 层级 | 职责 | 特点 |
|------|------|------|
| **Agent** | 意图理解、任务规划、结果综合 | 轻量、通用、可组合 |
| **Skill** | 领域知识、计算逻辑、数据处理 | 重量、专用、独立 |

### 接口定义

```python
class Skill(ABC):
    """Skill 基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Skill 名称"""

    @property
    @abstractmethod
    def description(self) -> str:
        """Skill 描述（用于 Agent 理解）"""

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, ParameterSchema]:
        """参数定义"""

    @abstractmethod
    def execute(self, **kwargs) -> SkillResult:
        """执行 Skill"""

    def get_missing_params(self, provided: Dict) -> List[str]:
        """检查缺失的必需参数"""
```

### Skill 示例

```python
class QueryEmissionFactorsSkill(Skill):
    name = "query_emission_factors"
    description = "查询MOVES数据库中的排放因子速度曲线"

    parameters = {
        "vehicle_type": {
            "type": "string",
            "required": True,
            "description": "车型（如小汽车、公交车）"
        },
        "pollutant": {
            "type": "string",
            "required": True,
            "description": "污染物（如CO2、NOx）"
        },
        "model_year": {
            "type": "integer",
            "required": True,
            "description": "年份（1995-2025）"
        }
    }

    def execute(self, **kwargs) -> SkillResult:
        # 1. 标准化参数
        vehicle = self.standardizer.standardize_vehicle(
            kwargs["vehicle_type"]
        )

        # 2. 查询数据
        data = self.calculator.query(
            vehicle_type=vehicle,
            pollutant=kwargs["pollutant"],
            year=kwargs["model_year"]
        )

        # 3. 返回结果
        return SkillResult(
            success=True,
            data=data
        )
```

### Agent 如何使用 Skill

```python
class Agent:
    def __init__(self):
        self.skill_registry = SkillRegistry()
        self._register_skills()

    def _plan(self, message: str) -> List[SkillCall]:
        """使用 LLM 规划需要执行的 Skill"""
        available_skills = self.skill_registry.list_all()

        prompt = f"""
        用户消息: {message}

        可用工具: {available_skills}

        请分析需要调用哪些工具，以及每个工具的参数。
        返回 JSON 格式。
        """

        response = self.llm.call(prompt)
        return self._parse_skill_plan(response)

    def _execute_skill(self, skill_call: SkillCall) -> SkillResult:
        """执行单个 Skill"""
        skill = self.skill_registry.get(skill_call.skill_name)
        return skill.execute(**skill_call.parameters)
```

---

## 上下文管理

### Context 数据结构

```python
class Context:
    """对话上下文管理器"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.turns: List[Turn] = []
        self.max_turns = 50  # 最多保留轮次
        self.compress_threshold = 10  # 超过此数量开始压缩

    def add_turn(self, turn: Turn):
        """添加新的对话轮次"""
        self.turns.append(turn)

        # 压缩旧对话
        if len(self.turns) > self.compress_threshold:
            self._compress_old_turns()

    def _compress_old_turns(self):
        """压缩旧对话为摘要"""
        keep_recent = 5  # 保留最近5轮完整对话
        old_turns = self.turns[:-keep_recent]

        # 生成摘要
        summary = self._generate_summary(old_turns)

        # 替换为摘要
        self.turns = [
            Turn(
                user_input="[历史对话摘要]",
                assistant_response=summary,
                skill_executions=[],  # 不保留旧执行详情
                timestamp=old_turns[0].timestamp
            )
        ] + self.turns[-keep_recent:]

    def get_relevant_context(self, current_turn: Turn) -> str:
        """获取与当前对话相关的上下文"""
        context_parts = []

        # 添加最近的对话
        for turn in self.turns[-3:]:
            context_parts.append(f"用户: {turn.user_input}")
            context_parts.append(f"助手: {turn.assistant_response}")

        # 添加最近的 Skill 执行结果
        for turn in self.turns[-3:]:
            if turn.skill_executions:
                for execution in turn.skill_executions:
                    if execution.success:
                        context_parts.append(
                            f"之前执行了 {execution.skill_name}，"
                            f"参数: {execution.parameters}"
                        )

        return "\n".join(context_parts)
```

### Turn 生命周期

```
创建 Turn
    │
    ├─ user_input: 用户消息
    ├─ timestamp: 时间戳
    └─ skill_executions: [] (初始为空)
    │
    ▼
执行 Skill
    │
    ├─ 记录 SkillExecution
    │  ├─ skill_name
    │  ├─ parameters
    │  ├─ result
    │  └─ success
    │
    └─ 更新 skill_executions
    │
    ▼
生成回复
    │
    ├─ assistant_response: 自然语言回复
    ├─ chart_data: 图表数据 (如果有)
    └─ table_data: 表格数据 (如果有)
    │
    ▼
保存到 Context
    │
    └─ context.add_turn(turn)
    │
    ▼
上下文压缩 (如果需要)
    │
    └─ 旧对话 → 摘要
```

---

## 智能列名映射

### 问题背景

用户上传的 Excel 文件列名千变万化：
- `speed_kph`, `Speed`, `速度`, `车速`
- `acceleration`, `acc`, `加速度`
- `length`, `link_length`, `路段长度`

硬编码所有变体是不可能的。

### 解决方案：LLM 映射

```python
# skills/common/column_mapper.py

def map_columns_with_llm(file_info: Dict, task_type: str, llm_client) -> Dict:
    """使用 LLM 进行列名映射"""

    prompt = f"""
    文件信息:
    - 列名: {file_info['columns']}
    - 示例数据: {file_info['sample_data'][:2]}

    任务类型: {task_type}

    标准字段定义:
    {FIELD_DEFINITIONS[task_type]}

    请分析用户列名，将每个用户列映射到对应的标准字段。
    只返回映射关系的 JSON，不要解释。

    返回格式:
    {{
        "mapping": {{
            "用户列名": "标准字段名",
            ...
        }},
        "unmapped_columns": ["未映射的列"],
        "confidence": 0.95
    }}
    """

    response = llm_client.call(prompt)
    return json.loads(response)
```

### 字段定义

```python
FIELD_DEFINITIONS = {
    "micro_emission": {
        "time": {"description": "时间（秒）", "examples": ["t", "time", "时间", "timestamp"]},
        "speed": {"description": "速度（km/h）", "examples": ["speed_kph", "speed", "速度", "车速"]},
        "acceleration": {"description": "加速度（m/s²）", "examples": ["acceleration", "acc", "加速度"]},
        "grade": {"description": "坡度（%）", "examples": ["grade", "slope", "坡度", "gradient"]}
    },
    "macro_emission": {
        "link_id": {"description": "路段ID", "examples": ["link_id", "id", "路段ID"]},
        "length": {"description": "路段长度（km）", "examples": ["length", "link_length", "长度"]},
        "flow": {"description": "交通流量（辆/小时）", "examples": ["flow", "traffic_flow", "流量"]},
        "avg_speed": {"description": "平均速度（km/h）", "examples": ["avg_speed", "speed", "速度"]},
        # ... 车队组成字段（13种MOVES车型）
    }
}
```

### 执行流程

```
上传文件
    │
    ▼
analyze_file_structure()
    │
    ├─ 读取列名
    ├─ 读取示例数据（前3行）
    └─ 返回: {columns, sample_data, row_count}
    │
    ▼
map_columns_with_llm()
    │
    ├─ 构建 Prompt（列名 + 示例 + 字段定义）
    ├─ 调用 LLM
    └─ 返回映射关系
    │
    ▼
apply_column_mapping(df, mapping)
    │
    └─ 重命名 DataFrame 列
    │
    ▼
验证映射结果
    │
    ├─ 检查必需列是否存在
    ├─ 检查数据类型是否正确
    └─ 失败则回退到硬编码匹配
    │
    ▼
返回映射后的数据
```

### 回退机制

```python
# 如果 LLM 映射失败，使用硬编码匹配

FALLBACK_MAPPING = {
    "micro_emission": {
        "time": ["t", "time", "时间", "timestamp"],
        "speed": ["speed_kph", "speed", "velocity", "速度", "车速"],
        "acceleration": ["acceleration", "acc", "accel", "加速度"],
        "grade": ["grade", "slope", "gradient", "坡度", "grade_pct"]
    }
}

def find_column_fallback(df: pd.DataFrame, target_field: str) -> Optional[str]:
    """使用模糊匹配查找列"""
    candidates = FALLBACK_MAPPING[task_type][target_field]
    for col in df.columns:
        if col.lower() in [c.lower() for c in candidates]:
            return col
    return None
```

---

## Web 架构

### 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| 后端 | FastAPI | Web 框架 |
| 后端 | Uvicorn | ASGI 服务器 |
| 前端 | Vanilla JS | 客户端逻辑 |
| 前端 | Tailwind CSS | 样式 |
| 前端 | ECharts | 图表渲染 |
| 前端 | Marked.js | Markdown 渲染 |

### API 端点

```
POST /chat
    - 发送消息
    - 上传文件
    - 获取回复

GET  /sessions
    - 获取会话列表

POST /sessions/new
    - 创建新会话

GET  /sessions/{id}/history
    - 获取会话历史

DELETE /sessions/{id}
    - 删除会话

POST /file/preview
    - 预览上传文件

GET  /file/download/{file_id}
    - 下载结果文件

GET  /file/template/{template_type}
    - 下载模板文件
```

### 前端状态管理

```javascript
// web/app.js

const state = {
    currentSessionId: null,
    isProcessing: false,
    uploadedFile: null,
    messages: []
};

// 消息处理
async function sendMessage() {
    // 1. 收集输入
    const message = messageInput.value;
    const file = state.uploadedFile;

    // 2. 显示用户消息
    addUserMessage(message, file?.name);

    // 3. 显示加载动画
    const loadingId = addLoadingMessage();

    // 4. 发送请求
    const formData = new FormData();
    formData.append('message', message);
    formData.append('session_id', state.currentSessionId);
    if (file) formData.append('file', file);

    // 5. 处理响应
    const response = await fetch('/chat', {
        method: 'POST',
        body: formData
    });

    const data = await response.json();

    // 6. 显示助手消息
    removeLoadingMessage(loadingId);
    addAssistantMessage(data);

    // 7. 渲染图表
    if (data.data_type === 'chart') {
        renderChart(data.chart_data);
    }

    // 8. 更新会话列表
    loadSessionList();
}
```

### 图表渲染

```javascript
// 渲染排放因子曲线图
function renderEmissionChart(chartData, chartId) {
    const chart = echarts.init(document.getElementById(chartId));

    const pollutants = Object.keys(chartData.pollutants);
    const series = pollutants.map(p => ({
        name: p,
        data: chartData.pollutants[p].curve,
        type: 'line',
        smooth: true
    }));

    const option = {
        xAxis: { name: '速度 (km/h)' },
        yAxis: { name: '排放率 (g/km)' },
        series: series,
        legend: { data: pollutants },
        tooltip: { trigger: 'axis' }
    };

    chart.setOption(option);
}
```

### 数据显示修复

**问题**: 追问时显示重复的历史数据

**原因**: 后端读取了持久化的 `last_successful_result`

**修复**:
```python
# api/routes.py

# 只读取当前 turn 的 Skill 执行结果
if current_turn.skill_executions:
    last_execution = current_turn.skill_executions[-1]
    if last_execution.success:
        # 构建图表数据
        chart_data = build_emission_chart_data(...)

# 没有执行 Skill，不显示图表
else:
    chart_data = None
    table_data = None
```

**前端防护**:
```javascript
// 验证数据有效性
const hasValidChartData = data.data_type === 'chart' &&
                         data.chart_data &&
                         Object.keys(data.chart_data).length > 0;

if (hasValidChartData) {
    renderChart(data.chart_data);
}
```

---

## 关键技术

### 1. VSP (Vehicle Specific Power) 计算

用于微观排放计算，基于车辆运动状态计算瞬时功率。

```python
def calculate_vsp(speed_kph: float, acceleration_mps2: float, grade_pct: float) -> float:
    """
    VSP = v * (1.1 * a + 9.81 * grade + 0.132) + 0.000302 * v^3

    单位:
    - speed_kph: km/h
    - acceleration_mps2: m/s²
    - grade_pct: %
    - 返回: kW/ton
    """
    v = speed_kph
    a = acceleration_mps2
    grade = grade_pct / 100  # 转换为小数

    vsp = v * (1.1 * a + 9.81 * grade + 0.132) + 0.000302 * v**3
    return vsp
```

### 2. MOVES Matrix 方法

用于宏观排放计算，基于平均速度和车型查找排放率。

```
排放率 = f(车型, 年份, 污染物, 季节, 道路类型, 速度)

通过多维插值从预计算矩阵中获取排放率。
```

### 3. LLM 参数标准化

```python
class VehicleStandardizer:
    """车型标准化器"""

    def __init__(self, llm_client):
        self.llm = llm_client
        self.cache = {}

    def standardize(self, user_input: str) -> str:
        """将用户输入标准化为 MOVES 标准车型"""

        # 检查缓存
        if user_input in self.cache:
            return self.cache[user_input]

        # 构建 Prompt
        prompt = f"""
        将以下车型映射到 MOVES 标准车型之一:
        {STANDARD_VEHICLE_TYPES}

        用户输入: {user_input}

        只返回标准车型名称。
        """

        # 调用 LLM
        response = self.llm.call(prompt)

        # 解析结果
        standard_type = self._parse_response(response)

        # 缓存
        self.cache[user_input] = standard_type

        return standard_type
```

### 4. 上下文压缩

```python
def compress_context(context: Context) -> Context:
    """压缩对话上下文"""

    # 策略1: 保留最近 N 轮
    recent_turns = context.turns[-5:]

    # 策略2: 保留所有 Skill 成功执行的结果
    skill_results = [
        turn for turn in context.turns
        if any(exec.success for exec in turn.skill_executions)
    ]

    # 策略3: 早期对话摘要
    summary = generate_summary(context.turns[:-10])

    return Context(
        turns=[summary_turn] + recent_turns,
        session_id=context.session_id
    )
```

### 5. 文件处理

```python
class ExcelHandler:
    """Excel 文件处理器"""

    def read_trajectory(self, file_path: str) -> pd.DataFrame:
        """读取轨迹数据"""

        # 1. 读取文件
        df = pd.read_excel(file_path)

        # 2. 智能列名映射
        mapping = self._map_columns(df, task_type="micro_emission")
        df = df.rename(columns=mapping)

        # 3. 验证必需列
        required = ["time", "speed"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(f"缺少必需列: {missing}")

        # 4. 数据预处理
        if "acceleration" not in df.columns:
            df["acceleration"] = calculate_acceleration(df["speed"])

        if "grade" not in df.columns:
            df["grade"] = 0.0

        return df

    def _map_columns(self, df: pd.DataFrame, task_type: str) -> Dict:
        """智能列名映射"""
        # 尝试 LLM 映射
        try:
            mapping = map_columns_with_llm(df, task_type, self.llm)
            return mapping["mapping"]
        except Exception:
            # 回退到硬编码
            return self._fallback_mapping(df, task_type)
```

---

## 性能优化

### 缓存策略

| 缓存类型 | 内容 | TTL | 位置 |
|---------|------|-----|------|
| 标准化缓存 | 车型/污染物映射 | 永久 | 内存 |
| MOVES 缓存 | 排放因子查询结果 | 永久 | 内存 |
| 会话缓存 | 对话历史 | 24h | 文件 |
| LLM 缓存 | 相同输入的响应 | 1h | 内存 |

### 异步处理

```python
@router.post("/chat")
async def chat(...):
    """异步处理聊天请求"""

    # 异步保存文件
    input_file_path = await save_file_async(file)

    # 异步执行 Agent
    reply = await asyncio.to_thread(
        session.agent.chat,
        message
    )

    return ChatResponse(reply=reply, ...)
```

---

## 错误处理

### 分层错误处理

```
┌─────────────────────────────────────────┐
│ 前端错误处理                             │
│ - 网络错误提示                           │
│ - 文件验证                               │
│ - 友好错误消息                           │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ API 错误处理                             │
│ - 请求验证                               │
│ - 文件大小限制                           │
│ - HTTP 异常                              │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ Agent 错误处理                           │
│ - 参数缺失 → 询问用户                    │
│ - Skill 失败 → 重试/回退                 │
│ - LLM 错误 → 使用缓存                    │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ Skill 错误处理                           │
│ - 数据验证失败 → 具体错误提示            │
│ - 计算错误 → 返回部分结果                │
│ - 文件错误 → 降级处理                    │
└─────────────────────────────────────────┘
```

---

## 部署架构

### 开发环境

```
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 生产环境

```
                    ┌─────────────────┐
                    │   Nginx / CDN   │
                    │   (静态文件)     │
                    └─────────────────┘
                             │
                    ┌─────────────────┐
                    │  Gunicorn +     │
                    │  Uvicorn        │
                    │  (多进程)       │
                    └─────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │  Worker 1   │ │  Worker 2   │ │  Worker 3   │
    └─────────────┘ └─────────────┘ └─────────────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
                    ┌─────────────────┐
                    │  Redis Cache    │
                    └─────────────────┘
```

---

## 本地模型集成

### 架构设计

系统支持两种标准化模式：

1. **API模式** (默认)
   - 调用云端LLM API (qwen-flash)
   - 优点：无需本地资源、快速部署
   - 缺点：有API调用成本、需要网络连接

2. **本地模式** (可选)
   - 使用本地微调的Qwen3-4B模型
   - 通过VLLM服务提供高性能推理
   - 优点：无API成本、更低延迟、数据隐私
   - 缺点：需要GPU资源、需要模型训练

### 本地模型架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Windows (emission_agent)                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  VehicleStandardizer / PollutantStandardizer           │ │
│  │  └─> LocalStandardizerClient                           │ │
│  │      ├─ 模式: VLLM                                     │ │
│  │      ├─ 禁用代理访问本地服务                           │ │
│  │      └─ 动态切换LoRA适配器                             │ │
│  └────────────────────────────────────────────────────────┘ │
│                                │                              │
│                                │ HTTP (no proxy)              │
│                                ↓                              │
│                    ┌────────────────────────┐                 │
│                    │   WSL2 Network Bridge  │                 │
│                    │   172.20.x.x:8001      │                 │
│                    └────────────────────────┘                 │
└────────────────────────────────────────────────────────────────┘
                                 │
┌────────────────────────────────┼──────────────────────────────┐
│                    WSL2 (Ubuntu)                               │
│  ┌────────────────────────────┼────────────────────────────┐ │
│  │  VLLM Service (port 8001)  │                            │ │
│  │  ├─ Base: Qwen3-4B-Instruct-2507 (4B参数)             │ │
│  │  ├─ LoRA: unified (车型+污染物, rank=16)               │ │
│  │  └─ LoRA: column (列名映射, rank=32)                   │ │
│  │                                                          │ │
│  │  性能指标:                                               │ │
│  │  - 首次延迟: ~100ms                                     │ │
│  │  - 后续延迟: ~50ms                                      │ │
│  │  - 显存占用: ~4GB                                       │ │
│  │  - 并发支持: 高 (PagedAttention)                       │ │
│  └────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

### 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 基础模型 | Qwen3-4B-Instruct-2507 | 4B参数，支持中英文 |
| 微调方法 | LoRA (Low-Rank Adaptation) | 低秩适配，高效微调 |
| 推理引擎 | VLLM 0.15.0 | 高性能推理服务器 |
| 部署环境 | WSL2 + Ubuntu | Windows下的Linux子系统 |
| 通信协议 | HTTP REST API | OpenAI兼容接口 |

### LoRA适配器

系统使用两个独立的LoRA适配器：

1. **unified_lora** (rank=16)
   - 任务：车型标准化 + 污染物标准化
   - 训练数据：4,352条训练 + 512条验证
   - 准确率目标：≥95%

2. **column_lora** (rank=32)
   - 任务：Excel列名映射
   - 训练数据：2,550条训练 + 300条验证
   - 准确率目标：≥90%

### 配置管理

```python
# config.py

self.use_local_standardizer = os.getenv("USE_LOCAL_STANDARDIZER", "false").lower() == "true"

self.local_standardizer_config = {
    "enabled": self.use_local_standardizer,
    "mode": os.getenv("LOCAL_STANDARDIZER_MODE", "direct"),  # "direct" or "vllm"
    "base_model": os.getenv("LOCAL_STANDARDIZER_BASE_MODEL", "..."),
    "unified_lora": os.getenv("LOCAL_STANDARDIZER_UNIFIED_LORA", "..."),
    "column_lora": os.getenv("LOCAL_STANDARDIZER_COLUMN_LORA", "..."),
    "device": os.getenv("LOCAL_STANDARDIZER_DEVICE", "cuda"),
    "max_length": int(os.getenv("LOCAL_STANDARDIZER_MAX_LENGTH", "256")),
    "vllm_url": os.getenv("LOCAL_STANDARDIZER_VLLM_URL", "http://172.20.x.x:8001"),
}
```

### 关键技术细节

#### 1. 代理配置处理

**问题**: emission_agent配置了HTTP代理，导致无法连接本地VLLM服务。

**解决方案**: 在`local_client.py`中禁用代理：

```python
response = requests.post(
    f"{self.vllm_url}/v1/completions",
    json={...},
    proxies={"http": None, "https": None}  # 禁用代理
)
```

#### 2. WSL2网络配置

**问题**: Windows无法通过`localhost`访问WSL2服务。

**解决方案**: 使用WSL2的实际IP地址（如`172.20.251.164`）。

```bash
# 在WSL2中获取IP
hostname -I | awk '{print $1}'
```

#### 3. LoRA适配器动态切换

VLLM支持在同一服务中加载多个LoRA适配器，通过请求参数切换：

```python
# 车型标准化
response = requests.post(
    f"{vllm_url}/v1/completions",
    json={"model": "unified", "prompt": "[vehicle] 小汽车", ...}
)

# 列名映射
response = requests.post(
    f"{vllm_url}/v1/completions",
    json={"model": "column", "prompt": json.dumps(columns), ...}
)
```

### 性能对比

| 指标 | API模式 (qwen-flash) | 本地VLLM模式 (qwen3-4b) |
|------|---------------------|------------------------|
| 首次延迟 | ~500ms | ~100ms |
| 后续延迟 | ~500ms | ~50ms |
| 显存占用 | 0 | ~4GB |
| 并发支持 | 高 | 高 |
| 成本 | 按调用计费 | 免费 |
| 数据隐私 | 云端 | 完全本地 |
| 网络依赖 | 需要 | 不需要 |
| 准确率 | 高 | 取决于训练质量 |

### 数据收集与模型训练

系统自动收集标准化数据用于模型训练：

```python
# llm/data_collector.py

self._collector.log(
    task="vehicle_type",
    input_value=user_input,
    output={"standard": result.standard, "confidence": result.confidence},
    method=result.method,
    model="local_qwen3-4b",  # 记录使用的模型
    context=context
)
```

收集的数据可用于：
1. 评估模型性能
2. 发现标准化错误
3. 持续改进训练数据
4. 微调模型参数

### 部署流程

1. **模型训练** (在WSL2中)
   ```bash
   cd ~/LOCAL_STANDARDIZER_MODEL
   python scripts/04_train_lora.py --config configs/unified_lora_config.yaml
   python scripts/04_train_lora.py --config configs/column_lora_config.yaml
   ```

2. **启动VLLM服务** (在WSL2中)
   ```bash
   vllm serve /path/to/base/model \
       --enable-lora \
       --lora-modules unified=/path/to/unified_lora \
                      column=/path/to/column_lora \
       --port 8001
   ```

3. **配置emission_agent** (在Windows中)
   ```bash
   # 编辑 .env
   USE_LOCAL_STANDARDIZER=true
   LOCAL_STANDARDIZER_MODE=vllm
   LOCAL_STANDARDIZER_VLLM_URL=http://172.20.x.x:8001
   ```

4. **重启服务**
   ```powershell
   .\scripts\restart_server.ps1
   ```

### 故障排查

常见问题及解决方案：

1. **无法连接VLLM服务**
   - 检查WSL2服务是否运行
   - 确认IP地址是否正确
   - 测试连接：`curl http://172.20.x.x:8001/health`

2. **代理干扰**
   - 确认`local_client.py`中已禁用代理
   - 检查环境变量`HTTP_PROXY`

3. **模型返回无效结果**
   - 检查LoRA适配器是否正确加载
   - 验证训练数据质量
   - 查看VLLM服务日志

详细部署指南请参考：[本地模型部署指南](本地模型部署指南.md)

---

## 最近改进 (v1.2.0)

### UI/UX 优化

#### 1. ChatGPT风格界面设计

**问题**：原界面缺乏视觉层次，消息区分不明显

**解决方案**：
```css
/* 页面背景 */
body {
    background: #f7f7f8;  /* 浅灰背景 */
}

/* AI消息卡片 */
.ai-message {
    background: white;
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

/* 用户消息气泡 */
.user-message {
    background: #10a37f;  /* 绿色气泡 */
    color: white;
}
```

**效果**：
- 清晰的视觉层次
- 更好的消息区分
- 现代化的外观

#### 2. 智能布局优化

**问题**：滚动条不贴边，内容不居中，输入框不对齐

**解决方案**：
```css
/* 消息容器 - 全宽，滚动条贴边 */
#messages-container {
    width: 100%;
    padding: 0;
}

/* 消息包装器 - 内容居中 */
#messages-container > div {
    max-width: 52rem;
    margin: 0 auto;
    padding: 0 1rem;
}

/* 输入区域 - 与消息对齐 */
#input-area .max-w-4xl {
    max-width: 52rem;
}
```

**效果**：
- 滚动条贴右边缘
- 内容居中显示（52rem宽度）
- 输入框与消息完美对齐

#### 3. 完整表格显示

**问题**：表格只显示前5列，隐藏了排放结果列

**修复前**：
```python
# api/routes.py (旧代码)
preview_columns = list(df.columns)[:5]  # 只显示前5列
table_data["columns"] = preview_columns
```

**修复后**：
```python
# api/routes.py (新代码)
table_data["columns"] = list(df.columns)  # 显示所有列
table_data["preview_rows"] = df.head(5).to_dict(orient="records")
```

**效果**：
- 显示所有列（输入+车型分布+排放结果）
- 用户可以看到完整的计算结果

### Agent质量提升

#### 1. 样本数据保留策略

**问题**：LLM没有具体数据参考，回答质量差

**修复前**：
```python
# agent/core.py (旧代码)
if "results" in data:
    filtered_data["results_count"] = len(data["results"])
    # 不包含 data["results"] 本身
```

**修复后**：
```python
# agent/core.py (新代码)
if "results" in data:
    filtered_data["results_count"] = len(data["results"])
    filtered_data["results_sample"] = data["results"][:5]  # 保留前5条样本
```

**效果**：
- LLM有具体数据可以参考
- 回答更准确、更具体
- 避免发送过多数据（只保留5条样本）

#### 2. 动态格式指导

**问题**：文件输入和文字描述输入应该有不同的回答格式

**解决方案**：
```python
# agent/core.py
def _synthesize(self, query: str, understanding: str, results: Dict) -> str:
    # 检查是否有input_file
    has_input_file = self._check_has_input_file(results)

    if has_input_file:
        format_instruction = "前端会自动显示完整的表格预览。你的回答应该简洁。"
    else:
        format_instruction = "前端不会显示表格。你的回答应该包含完整的计算结果。"

    prompt = SYNTHESIS_PROMPT + format_instruction
    return self._synthesis_llm.chat(prompt)
```

**效果**：
- 文件输入：简洁回答 + 表格预览
- 文字描述：完整文本回答（无表格）

#### 3. 智能回答格式切换

**问题**：文字描述输入时显示"暂无数据"

**解决方案**：
```python
# api/routes.py
if has_input_file:
    # 文件输入 -> 返回表格格式
    data_type = "table"
    table_data = {...}
else:
    # 文字描述输入 -> 纯文本格式
    data_type = None  # 不返回表格数据
```

**效果**：
- 根据输入方式自动选择合适的展示格式
- 避免"暂无数据"的尴尬情况

### 数据修复

#### 1. 微观排放CSV表头修复

**问题**：CSV文件表头有重复的`EmissionQuant`列名

**原始表头**：
```
opModeID,pollutantID,SourceType,ModelYear,EmissionQuant,EmissionQuant
```

**数据结构**：
- 第5列（第一个EmissionQuant）：年份值（2025, 2024...）
- 第6列（第二个EmissionQuant）：排放因子值（0.00990433...）

**问题原因**：
- pandas读取时，第二个列被重命名为`EmissionQuant.1`
- 代码读取`EmissionQuant`时，实际读到的是年份列
- 结果：所有排放值都是2025

**修复方案**：
```bash
# 统一三个CSV文件的表头
opModeID,pollutantID,SourceType,ModelYear,CalendarYear,EmissionQuant
```

**修复文件**：
- `atlanta_2025_1_55_65.csv` (冬季)
- `atlanta_2025_4_75_65.csv` (春季)
- `atlanta_2025_7_90_70.csv` (夏季)

**效果**：
- 排放值正确（不再是2025）
- 三个季节数据格式统一
- 从源头解决问题

#### 2. 表格预览数据完整性

**问题**：文字描述输入时没有表格预览数据

**解决方案**：
```python
# api/routes.py
if result_file_path and result_file_path.exists():
    # 从Excel文件读取
    df = pd.read_excel(result_file_path)
    table_data["columns"] = list(df.columns)
    table_data["preview_rows"] = df.head(5).to_dict(orient="records")
else:
    # 从results数组构建
    results = skill_data.get("results", [])
    if results:
        table_data["columns"] = list(results[0].keys())
        table_data["preview_rows"] = results[:5]
```

**效果**：
- 文件输入和文字描述输入都能正确显示数据
- 数据来源灵活（Excel文件或results数组）

### 技术改进总结

| 改进类别 | 具体改进 | 影响范围 |
|---------|---------|---------|
| UI/UX | ChatGPT风格界面 | 前端 (web/index.html) |
| UI/UX | 智能布局优化 | 前端 (CSS) |
| UI/UX | 完整表格显示 | 后端 (api/routes.py) |
| Agent | 样本数据保留 | Agent层 (agent/core.py) |
| Agent | 动态格式指导 | Agent层 (agent/core.py) |
| Agent | 智能格式切换 | API层 (api/routes.py) |
| 数据 | CSV表头修复 | 数据层 (skills/micro_emission/data/) |
| 数据 | 表格预览完整性 | API层 (api/routes.py) |

---

## 总结

Emission Agent 是一个完整的智能系统，展示了：

1. **清晰的架构分层**: Agent-Skill 分离，职责明确
2. **灵活的组件设计**: 可插拔的 Skill 系统
3. **智能的数据处理**: LLM 辅助的参数标准化和列名映射
4. **完善的对话管理**: 上下文压缩、多轮对话、状态保持
5. **友好的用户界面**: ChatGPT风格Web界面、图表可视化、智能表格展示
6. **本地模型支持**: 降低成本、提升性能、保护数据隐私
7. **持续优化改进**: UI/UX优化、Agent质量提升、数据完整性修复

系统的核心优势在于将复杂的领域计算封装在独立的 Skill 中，而 Agent 层保持轻量和通用，使得系统易于扩展和维护。通过本地模型集成，系统进一步提升了性能和数据安全性。v1.2.0版本的改进进一步提升了用户体验和系统可靠性。

---

**文档版本**: v1.2.0
**最后更新**: 2026-02-03
**维护者**: Emission Agent Team
