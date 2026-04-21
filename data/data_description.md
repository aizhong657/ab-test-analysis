# 数据字段说明 · Data Dictionary

## `ab_data.csv`

| 字段 Field | 类型 Type | 说明 Description |
|------------|-----------|------------------|
| `user_id` | int | 用户唯一标识 · Unique visitor ID |
| `timestamp` | datetime | 访问时间 · Visit timestamp (YYYY-MM-DD HH:MM:SS.ffffff) |
| `group` | str | 实验分组 · Experiment assignment (`control` / `treatment`) |
| `landing_page` | str | 实际展示页面 · Landing page served (`old_page` / `new_page`) |
| `converted` | int | 是否完成转化 · Conversion flag (`0` = 未转化, `1` = 转化) |

## 数据规模 · Size

- 原始行数 · Raw rows: **294,478**
- 清洗后行数 · Clean rows: **290,584**
- 实验周期 · Experiment window: **2017-01-02 ~ 2017-01-23**（22 天）
- 分组 / 页面映射 · Expected mapping:
  - `control` ⇄ `old_page`
  - `treatment` ⇄ `new_page`

## 数据来源 · Source note

分析脚本 `generate_data.py` 会生成一份与公开发表的 Kaggle A/B 测试数据集描述性统计高度一致的数据（294,478 条，3,893 条分组污染，转化率约 12.04% vs 11.88%）。若已获取真实 `ab_data.csv`，可直接覆盖该文件。

`generate_data.py` produces a simulation whose headline statistics closely match the published Kaggle landing-page dataset (294,478 rows, 3,893 contaminated rows, ≈12.04% vs 11.88% conversion). If you have access to the real file, drop it in place of the generated one.
