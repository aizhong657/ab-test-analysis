# 电商三臂 A/B 测试分析 · 3-arm E-commerce A/B Test Analysis

> 基于 **200 万条真实事件日志**（2021-01-01 ~ 2023-12-31，633,462 个 session、100,000 位用户），
> 评估两个新版页面（Variant_A / Variant_B）相比控制组（Control）的转化影响，
> 并给出业务上线决策建议。

> Full statistical analysis on 2M real event logs, covering 3 years,
> 633,462 sessions and 100,000 customers, to decide whether
> Variant_A or Variant_B should replace the Control landing page.

---

## 项目背景 · Background

某电商平台在落地页上并行测试 Variant_A 与 Variant_B 两个新方案，希望通过 A/B 测试验证是否值得上线替换 Control。
本项目对真实事件日志进行端到端分析，覆盖数据质量、假设检验、效应量、统计功效与业务建议。

An e-commerce platform is running two candidate landing-page redesigns (Variant_A, Variant_B) against its
existing Control. This repository delivers an end-to-end analysis on the raw event log to decide whether either variant
should ship.

**核心业务问题 · Business question:**
两个新版 Variant 的 session 级转化率是否显著高于 Control？

---

## 数据集 · Dataset

数据存放于仓库外的 `D:\Project\1\`，由 5 张表组成：

| 文件 File | 行数 Rows | 说明 Description |
|-----------|-----------|------------------|
| `events.csv` | **2,000,000** | 用户行为事件日志 · event log |
| `customers.csv` | ~100,000 | 用户档案 · customer profiles |
| `transactions.csv` | ~150,000 | 交易流水 · order transactions |
| `products.csv` | ~2,700 | 商品目录 · product catalogue |
| `campaigns.csv` | ~100 | 营销活动 · marketing campaigns |

**本分析仅使用 `events.csv`**，关键字段如下：

| 字段 Field | 说明 Description |
|-----------|------------------|
| `session_id` | Session 标识 · session identifier (analysis unit) |
| `customer_id` | 用户标识 · customer identifier |
| `timestamp` | 事件时间 · event timestamp |
| `event_type` | `view` / `click` / `add_to_cart` / `bounce` / `purchase` |
| `experiment_group` | 实验分组 · `Control` / `Variant_A` / `Variant_B` |
| `traffic_source` | 流量来源（存在大小写不一致问题） |

- 样本量 · Sessions：**633,462**
- 实验周期 · Window：**2021-01-01 ~ 2023-12-31**（约 3 年）
- 转化定义 · Conversion：session 中存在至少一条 `event_type == 'purchase'`

---

## 实验设计 · Experiment design

| 项目 Item | 内容 Detail |
|-----------|------------|
| 零假设 H0 | Variant 与 Control 转化率相同 · equal conversion |
| 备择假设 H1 | Variant 与 Control 转化率不同 · different (two-sided) |
| 检验方法 | 两比例 z 检验 · two-proportion z-test |
| 比较次数 | 2 · Variant_A vs Control, Variant_B vs Control |
| 多重校正 | **Bonferroni** · α_family = 0.05, α_adj = 0.025 |
| 分析单元 | **session**（每个 session 的 group 取其事件中的 **众数** 标签）|
| 效应量指标 | 相对提升率 Lift 与 Cohen's h |

---

## 分析流程 · Workflow

```
加载 events.csv (2M 行)
        ↓
数据质量检验 (session 污染 / traffic_source 大小写)
        ↓
Session 级分组与转化标记 (modal group + any purchase)
        ↓
两比例 z 检验 × 2 (Variant_A vs Ctl, Variant_B vs Ctl)
        ↓
Bonferroni 校正 + 置信区间 + 效应量 + 功效
        ↓
业务结论与建议
```

---

## 关键发现 · Key findings

### 1. 数据质量 · Data quality

| 发现 Finding | 数量 Count |
|--------------|----------|
| 原始事件 Total events | **2,000,000** |
| Session 总数 | **633,462** |
| **分组污染**：session 内 `experiment_group` 不一致 | **411,260**（64.92%）|
| `traffic_source` 大小写重复 | 5 组（`Organic`/`ORGANIC`、`Email`/`EMAIL` 等）|

> **重要 · Important**：约 **65%** 的 session 同时被打上了多个 `experiment_group` 标签，
> 这是一个严重的埋点/分流实现问题。本项目用 **modal 众数法**给每个 session 赋一个最可能的 group，
> 但这种数据质量问题通常需要向数据工程团队反馈。

---

### 2. 统计检验 · Statistical results

| 指标 Metric | Control | Variant_A | Variant_B |
|-------------|---------|-----------|-----------|
| 样本量 Sessions (n) | 501,551 | 73,727 | 58,184 |
| 转化率 Rate (p) | **15.36%** | 13.37% | 14.82% |
| 绝对差异 vs Control | — | -1.99 pp | -0.54 pp |
| 相对提升 vs Control | — | -12.98% | -3.53% |
| p-value (Bonferroni) | — | 5.83e-45 | 1.18e-03 |
| 显著性 (α=0.025) | — | **显著 (Significant)** | **显著 (Significant)** |

**结论 · Conclusion:**
- **Variant_A** 和 **Variant_B** 的转化率都**显著低于** Control。
- **Variant_A** 表现最差，转化率下降了约 13%。
- 虽然 **Variant_B** 表现略好于 A，但仍比旧版 Control 差。

---

## 业务建议 · Business Recommendations

❌ **不建议上线任一新版本 · Do NOT ship either variant.**

**理由 · Reasons:**
1.  **统计层面**：两个变体的 p 值均远小于校正后的显著性水平（0.025），且差异方向均为**负向**。
2.  **业务层面**：上线 Variant_A 预计会导致转化率下降近 2 个百分点，这将对收入产生重大负面影响。
3.  **数据风险**：65% 的会话存在分组污染，虽然分析采用了众数法兜底，但底层的分流逻辑可能存在系统性偏差。

**下一步行动 · Next steps:**
- 检查新页面（Variant A/B）的加载性能与埋点是否正常，排除技术故障导致转化率下降。
- 与产品经理回顾设计方案，探究为何新版页面表现不如旧版（可能是用户习惯或导航改动）。
- **立即修复**分流污染问题，确保后续实验的数据纯净。

---

## 可视化 · Visualizations

| 图表 Chart | 文件 File | 说明 Description |
|-----------|-----------|------------------|
| 三组转化率对比 | `images/conversion_rate.png` | 带 95% CI 的条形图 |
| 每日转化率趋势 | `images/daily_trend.png` | 14 日滚动均值（探查新鲜感 / 时间漂移）|
| 差异置信区间 | `images/confidence_interval.png` | 两组 variant-vs-control 差异 95% CI |
| 样本量累积曲线 | `images/sample_growth.png` | 流量分配随时间的稳定性 |

---

## 技术栈 · Tech stack

- **语言 Language**：Python 3
- **数据处理 Data**：Pandas, NumPy
- **统计检验 Stats**：SciPy, Statsmodels（proportions_ztest / confint_proportions_2indep / NormalIndPower）
- **可视化 Viz**：Matplotlib
- **环境 Env**：Jupyter Notebook

---

## 项目结构 · Repository layout

```
ab-test-analysis/
├── README.md                  # 本文件 · this file
├── notebook.ipynb             # 完整分析笔记本 · full analysis
├── ab_test_analysis.py        # 端到端分析脚本 · end-to-end pipeline
├── images/                    # 四张可视化 · charts
│   ├── conversion_rate.png
│   ├── daily_trend.png
│   ├── confidence_interval.png
│   └── sample_growth.png
└── data/
    ├── results.json           # 机器可读指标 · machine-readable metrics
    └── data_description.md    # 字段说明 · data dictionary

# 原始数据 · raw data lives outside the repo
../1/
├── events.csv (179 MB, 2,000,000 rows)
├── customers.csv
├── transactions.csv
├── products.csv
└── campaigns.csv
```

---

## 运行方式 · How to run

```bash
# 1. 安装依赖 · install deps
pip install pandas numpy scipy statsmodels matplotlib jupyter nbformat

# 2. 确认真实数据的位置 · make sure events.csv is available
#    默认会依次尝试：
#    $AB_EVENTS_CSV  ->  ./data/events.csv  ->  ../1/events.csv
export AB_EVENTS_CSV="/path/to/events.csv"    # optional

# 3. 运行完整分析 · run full analysis
python ab_test_analysis.py
#    -> images/*.png & data/results.json

# 4. 或在 Notebook 里交互 · or open the notebook
jupyter notebook notebook.ipynb
```

---

## 延伸思考 · Further reflections

1. **"分组污染" 比想象中常见 · Assignment contamination is common**
   65% 的 session 分组不一致——这常由埋点方案随请求重新抽样、CDN 缓存、或服务器侧 A/B 分流未落到 session 上导致。
   任何 A/B 分析第一步都应先做 **分流完整性检查**。

2. **统计显著 ≠ 业务显著 · Statistical vs business significance**
   本项目中两者方向一致——既显著，又业务层面明显为负。实际场景中，微小但显著的差异还需权衡实验成本。

3. **多重比较必须校正 · Correct for multiple comparisons**
   当同时检验多个 Variant 时，若不做 Bonferroni/FDR 等校正，第一类错误率会随比较次数线性上升。

4. **效应量与功效同样重要 · Don't ignore effect size / power**
   单看 p 值可能让一个微弱效应"看起来很显著"（尤其大样本量时）。Cohen's h 与观测功效一起看才能做出稳健决策。

---

*作者 · Author：Marvinpk · 完成时间 · Completed：2026 年 4 月*
