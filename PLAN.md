# active_minute_encoder_discovery_v0_4

Plan version: v0.4  
Status: initial AI-generated blueprint  
Execution source: `TODO.md`  
Global project rules: `PROJECT.md`  

## How to use this plan

This file is the high-level project blueprint.

It is not automatically treated as a fully validated implementation plan.

Before starting each phase:

1. Read `PROJECT.md`.
2. Read the relevant section in this file.
3. Run a technical ownership review for that phase.
4. Convert the phase into an executable spec under `docs/phases/phase_XX.md`.
5. Generate or update `TODO.md`.
6. Let Codex implement only the Active task in `TODO.md`.

Do not implement multiple phases at once.

Do not repeatedly rewrite the whole plan unless the global phase blueprint changes.

## Confidence model

The plan contains three types of content:

1. Hard invariants  
   These belong in `PROJECT.md`.

2. Provisional design choices  
   These may be used for v0 but should be validated with QA, spikes, or small runs.

3. Open assumptions  
   These should be tracked in phase specs, reviews, reports, or `docs/decisions.md`.

Examples of provisional choices:

- `ticker_bucket = hash(ticker) % 128`
- PatchTST-style encoder
- UMAP + HDBSCAN
- Specific liquidity thresholds
- Specific active-minute thresholds

These are not global invariants unless explicitly promoted to `PROJECT.md`.

---

# Original Plan
# active_minute_encoder_discovery_v0_5

## Project positioning

本项目 v0.5 的目标不是预测第一波上涨，也不是直接证明 L2 trading bot 可以实盘赚钱。

v0.5 的目标是：

```text
Use OHLCV-only 1min data to discover post-activation morphology clusters
among already in-play low-priced stocks.

核心问题：
当一只低价股已经被第一波 news / flow / scanner / crowd trigger 激活后，
它之后的 1min OHLCV morphology 是否能被分成稳定且有交易含义的行为簇？
```

v0.5 研究对象是：

```text
first wave 之后的 active-minute behavior
continuation / second wave
fakeout
fade
exhaustion
chop
high-risk trap
```

v0.5 不研究：

```text
first-wave trigger prediction
news / filing / social trigger detection
真实 L2 queue / fillability
盘口撤单 / 排队 / 冲击成本
real-time bot execution
```

因此，v0.5 的最终 GO 不是 “GO for trading bot”，而是：

```text
GO for L2 data collection and L2 entry/exit/execution research
```

---

# Global rule：只处理 trading days

生成统一交易日表：

```text
data/reference/trading_calendar_v0.parquet
```

字段：

```text
date
is_trading_day
is_early_close
regular_open_et
regular_close_et
dataset_split
research_split
```

v0.5 只处理：

```text
is_trading_day == true
```

不处理：

```text
weekends
NYSE holidays
non-trading calendar days
```

半日交易日：

```text
is_early_close == true
```

v0.5 默认保留半日交易日，但 RTH 边界使用该日的 `regular_close_et`，不是固定 16:00。

Session 定义：

```text
premarket:
  04:00 <= bar_start_et < 09:30

RTH:
  09:30 <= bar_start_et < regular_close_et
```

普通交易日：

```text
RTH = 09:30–16:00
```

半日交易日：

```text
RTH = 09:30–13:00
```

---

# Dataset split

Main split:

```text
Train:
  2016-08-02 to 2021-12-31

Val:
  2022-01-01 to 2023-12-31

OOS:
  2024-01-01 to 2026-06-18
```

Val 内部再切：

```text
Val-A:
  2022-01-01 to 2022-12-31

Val-B:
  2023-01-01 to 2023-12-31
```

用途：

```text
Train:
  fit scaler / normalizer / encoder / UMAP / PCA / HDBSCAN / baseline models

Val-A:
  estimate cluster_score
  select candidate clusters

Val-B:
  tune online thresholds / cooldown / caps

OOS:
  final one-shot chronological replay
```

严格规则：

```text
No OOS tuning.
No OOS refit.
No OOS cluster selection.
No OOS threshold selection.
```

---

# Storage standard

所有大表：

```text
Parquet compression = zstd
format = pyarrow dataset
```

分区原则：

```text
minute-level:
  partition by date + ticker_bucket

daily-level:
  partition by year

model input / embeddings:
  partition by dataset_split + date + ticker_bucket

cluster assignment:
  partition by method + dataset_split + date + ticker_bucket
```

ticker bucket：

```text
ticker_bucket = hash(ticker) % 128
```

每个 phase 写 manifest：

```text
data/manifests/<phase_name>_manifest.parquet
```

manifest 字段：

```text
phase
date
ticker_bucket
partition
input_files
output_files
row_count
status
error_message
created_at
code_version
config_version
```

写入规则：

```text
write temp path
run QA
if QA pass:
  commit / rename
if QA fail:
  do not overwrite previous result
```

---

# Phase 0：Build trading calendar

## 目的

生成全项目唯一 trading-day source of truth。

## 输入

```text
US equity trading calendar source
Massive available daily/minute file dates
```

## 输出

```text
data/reference/trading_calendar_v0.parquet
```

## 做法

生成 2016-08-02 到 2026-06-18 的日历表。

字段：

```text
date
is_trading_day
is_early_close
regular_open_et
regular_close_et
dataset_split
research_split
```

dataset_split：

```text
Train:
  2016-08-02 to 2021-12-31

Val:
  2022-01-01 to 2023-12-31

OOS:
  2024-01-01 to 2026-06-18
```

research_split：

```text
Train:
  2016-08-02 to 2021-12-31

Val-A:
  2022-01-01 to 2022-12-31

Val-B:
  2023-01-01 to 2023-12-31

OOS:
  2024-01-01 to 2026-06-18
```

## 并发

不需要并发，单进程生成。

## QA

```text
no weekends marked trading day
no known market holidays marked trading day
all trading days have dataset_split
all trading days have research_split
regular_open_et not null
regular_close_et not null
regular_close_et >= 13:00
early-close dates correctly marked
```

## GO

```text
GO if trading calendar covers all Train / Val-A / Val-B / OOS dates
and every downstream phase uses this table as date driver.
```

## NO-GO

```text
NO-GO if any downstream phase independently loops raw calendar days.
```

---

# Phase 1：Download / ingest Massive data

## 目的

只按 trading days 下载并转换 Massive 原始数据。

Massive 相关依赖保持 OHLCV-only：

```text
1min aggregates only assume:
  open / high / low / close / volume

daily aggregates only assume:
  open / high / low / close / volume
```

REST 只使用可全市场拉取的 endpoint，不做逐 ticker 全市场循环。

## 输入

```text
trading_calendar_v0 where is_trading_day == true

Massive S3:
  minute aggregates flat files
  daily aggregates flat files

Massive REST:
  /v3/reference/tickers/types
  /v3/reference/tickers
  /stocks/v1/splits
```

## 输出

```text
data/bronze/daily_ohlcv/year=YYYY/part.parquet

data/bronze/minute_ohlcv/date=YYYY-MM-DD/ticker_bucket=XXX/part.parquet

data/bronze/reference/ticker_types_snapshot.json

data/bronze/reference/tickers/date=YYYY-MM-DD/part.parquet

data/bronze/reference/splits/execution_date=YYYY-MM-DD/part.parquet
```

## 1.1 Daily OHLCV

只处理 trading days。

字段：

```text
ticker
date
daily_open
daily_high
daily_low
daily_close
daily_volume
```

不依赖：

```text
daily_vwap
daily_transactions
```

## 1.2 Minute OHLCV

只处理 trading days。

字段：

```text
ticker
date
bar_start_utc
bar_start_et
open
high
low
close
volume
ticker_bucket
```

只保留：

```text
04:00 <= bar_start_et < 16:00
```

注意：

```text
即使是半日交易日，也可以保留 13:00–16:00 bars，
但这些 bars 不属于 RTH。
后续 session_type 根据 regular_close_et 判断。
```

## 1.3 Ticker metadata

每个 trading day 调用：

```text
/v3/reference/tickers
  date = D
  market = stocks
  active = true
  limit = 1000
  follow next_url
```

不做逐 ticker 循环。

## 1.4 Splits

每个 trading day 调用：

```text
/stocks/v1/splits
  execution_date = D
  limit = 5000
  follow next_url
```

不传 ticker。

## 并发

并发粒度：

```text
S3 daily:
  per date

S3 minute:
  per date, then split by ticker_bucket

REST ticker metadata:
  per date

REST splits:
  per date
```

建议：

```text
S3 download workers:
  8–16

parquet convert workers:
  num_cores - 2

REST workers:
  2–4, respect rate limit
```

失败重跑：

```text
daily:
  per date

minute:
  per date + ticker_bucket

REST:
  per date
```

## QA

```text
only trading days ingested
no weekend / holiday files processed
daily row_count > 0 for each trading day
minute row_count > 0 for each trading day
required OHLCV columns exist
no duplicate ticker + bar_start_et

OHLC valid:
  high >= max(open, close, low)
  low <= min(open, close, high)
  volume >= 0

all minute bars within 04:00–16:00 ET
ticker metadata pagination exhausted
splits pagination exhausted or explicitly empty
```

Historical metadata QA：

```text
random old dates checked
inactive-now but active-then tickers can appear when they should
delisted examples spot checked
reverse split examples spot checked
```

## GO

```text
GO if:
  >= 99.5% trading days have daily OHLCV
  >= 99.5% trading days have minute OHLCV
  required OHLCV columns exist
  duplicate ticker-minute = 0
  invalid OHLC rows < 0.01%
  all REST pagination completed
  historical metadata spot checks pass
```

## NO-GO

```text
NO-GO if:
  calendar days are processed instead of trading days
  required OHLCV columns missing
  timestamp conversion to ET unreliable
  REST all-market retrieval fails
  metadata appears to introduce survivorship bias
```

---

# Phase 2：Build daily_universe_v0

## 目的

生成每日 clean ticker-day universe。

## 输入

```text
trading_calendar_v0
bronze/daily_ohlcv
bronze/reference/tickers
bronze/reference/ticker_types_snapshot.json
bronze/reference/splits
```

## 输出

```text
data/silver/daily_universe_v0/year=YYYY/part.parquet
```

## 做法

只处理：

```text
trading_calendar_v0.is_trading_day == true
```

一行：

```text
ticker + date
```

## clean_stock

```text
metadata exists for ticker-date
active == true
locale == us
market == stocks
currency_symbol == USD
type in allowed_common_stock_type_codes
primary_exchange in allowed_us_listing_mics
```

排除 name 包含：

```text
ETF
ETN
FUND
TRUST
PREFERRED
PREF
WARRANT
RIGHT
UNIT
NOTE
BOND
```

## Corporate action filter

基础 split filter：

```text
has_split_execution_today =
  ticker appears in splits[execution_date == date]
```

进入 universe 必须：

```text
has_split_execution_today == false
```

加强版 corporate action exclusion：

```text
exclude if split execution date within [-5, +5] trading days
mark reverse split separately if available
exclude suspicious corporate-action-like daily gap
store corporate_action_reason
```

如果可用，尽量保存稳定标识：

```text
security_id
cik
figi
composite_figi
share_class_figi
```

不要只依赖 ticker string。

## prev_close

```text
prev_close_unadjusted =
  previous valid trading day's daily_close
```

必须只用：

```text
date < current date
```

## avg20

```text
daily_dollar_volume_proxy =
  daily_close * daily_volume

avg20_volume =
  mean(daily_volume over previous 20 valid trading days)

avg20_dollar_volume_proxy =
  mean(daily_dollar_volume_proxy over previous 20 valid trading days)

avg20_valid_day_count >= 20
```

## filters

```text
price_ok =
  0.30 <= prev_close_unadjusted <= 20.00

liquidity_ok =
  avg20_valid_day_count >= 20
  AND avg20_volume >= 200,000
  AND avg20_dollar_volume_proxy >= 300,000
```

## 并发

并发粒度：

```text
per year
```

原因：

```text
avg20 / prev_close 需要 ticker 时间序列。
按年处理时，每年需要 preload 前 30 个 trading days 作为 warmup。
```

推荐：

```text
year workers:
  4–8

within year:
  groupby ticker parallel if memory allows
```

重跑：

```text
per year
```

## QA

```text
only trading days present
no duplicate ticker + date
dataset_split assigned
research_split assigned
prev_close uses date < current date only
avg20 uses previous trading days only
avg20_valid_day_count >= 20 for liquidity_ok rows
no split execution date remains in eligible rows
no split-window exclusion rows remain in eligible rows
clean_stock false rows have reason
corporate_action_excluded rows have reason
```

## GO

```text
GO if:
  duplicate ticker-date = 0
  prev_close leakage check passes
  avg20 leakage check passes
  eligible rows exist in every Train / Val-A / Val-B / OOS year
  no split execution dates remain in eligible rows
  split-window exclusion works
```

## NO-GO

```text
NO-GO if:
  any non-trading date appears
  avg20 includes current date
  ticker metadata join fails for large fraction
  eligible universe collapses unexpectedly in a year
  corporate actions visibly pollute eligible universe
```

---

# Phase 3：Build base_active_minute_universe_v0

## 目的

从 clean daily universe 生成 broad post-activation active-minute pool。

v0.5 不试图捕捉 first-wave trigger。
Phase 3 的目标是定义：

```text
already in-play low-priced stocks after activation
```

## 输入

```text
trading_calendar_v0
daily_universe_v0
bronze/minute_ohlcv
```

## 输出

```text
data/silver/base_active_minute_universe_v0/date=YYYY-MM-DD/ticker_bucket=XXX/part.parquet
```

## eligible ticker-day

只处理：

```text
clean_stock == true
price_ok == true
liquidity_ok == true
has_split_execution_today == false
corporate_action_excluded == false
```

## candidate timing

```text
signal_bar_start_et =
  completed 1min bar

decision_time_et =
  signal_bar_start_et + 1 minute

entry_time_et =
  decision_time_et

entry_model =
  next_bar_open_proxy_v0
```

时间范围：

```text
04:10 <= signal_bar_start_et
decision_time_et <= min(15:30, regular_close_et - 30min)
```

这保证半日交易日不会生成无法评估 30m RTH execution 的 RTH candidate。

## Session

```text
premarket:
  04:00 <= bar_start_et < 09:30

RTH:
  09:30 <= bar_start_et < regular_close_et
```

## active price

```text
current_gain_pct =
  close_t / prev_close_unadjusted - 1

high_so_far_gain_pct =
  max(high from 04:00 through signal_bar_start_et)
  / prev_close_unadjusted - 1
```

post-activation 入选：

```text
current_gain_pct >= 0.03

OR

high_so_far_gain_pct >= 0.10
AND current_gain_pct >= 0.00
```

解释：

```text
current_gain_pct >= 3%:
  fresh active / active momentum

high_so_far_gain_pct >= 10% and current_gain_pct >= 0:
  extended / faded but still active
```

## active volume

```text
rolling_3m_volume =
  sum(volume of last 3 completed bars ending at signal_bar_start_et)

rolling_3m_dollar_volume_proxy =
  sum(close_i * volume_i of last 3 completed bars)

rolling_3m_volume_to_avg20 =
  rolling_3m_volume / avg20_volume
```

Premarket：

```text
rolling_3m_volume >= 10,000
rolling_3m_dollar_volume_proxy >= 10,000
rolling_3m_volume_to_avg20 >= 0.001
```

RTH：

```text
rolling_3m_volume >= 15,000
rolling_3m_dollar_volume_proxy >= 25,000
rolling_3m_volume_to_avg20 >= 0.002
```

## Intraday liquidity diagnostics

这些字段用于后验解释和过滤，不用于 label 泄漏：

```text
bars_present_last_30m
nonzero_volume_bar_count_last_30m
rolling_15m_volume
rolling_15m_dollar_volume_proxy
rolling_30m_volume
rolling_30m_dollar_volume_proxy
```

## OHLCV-only proxy

```text
session_vwc_so_far =
  sum(close_i * volume_i from session start through signal bar)
  / sum(volume_i from session start through signal bar)

close_to_session_vwc_pct =
  close_t / session_vwc_so_far - 1
```

不使用：

```text
VWAP field
transactions field
bid
ask
spread
L2
future bars
full-day high / low
```

## Diagnostic tags

只用于后验分析，不输入 encoder：

```text
activation_state:

fresh_active:
  current_gain_pct >= 0.03
  AND high_so_far_gain_pct < 0.10

extended_active:
  current_gain_pct >= 0.10

faded_active:
  high_so_far_gain_pct >= 0.10
  AND 0.00 <= current_gain_pct < 0.10

deep_fade:
  high_so_far_gain_pct >= 0.10
  AND current_gain_pct < 0.03
```

## Episode ID

为避免同一次 spike 产生大量重复样本污染统计，生成：

```text
episode_id = ticker + date + active_episode_number
```

Episode start：

```text
first minute when active condition becomes true
```

Episode end：

```text
active condition false for N consecutive minutes
OR after max gap threshold
OR end of trading session
```

建议：

```text
inactive_minutes_to_end_episode = 10
```

## 并发

并发粒度：

```text
primary:
  date

secondary:
  ticker_bucket
```

推荐：

```text
date workers:
  4–8

ticker_bucket workers per date:
  8–16
```

每个 task：

```text
(date, ticker_bucket)
```

只读取：

```text
minute_ohlcv/date=D/ticker_bucket=B
daily_universe rows for date D and bucket B
trading_calendar row for date D
```

重跑：

```text
per date + ticker_bucket
```

## QA

```text
only trading days processed
no duplicate ticker + signal_bar_start_et
all rows have matching daily_universe row
session_type not null
active price condition true for all rows
active volume condition true for all rows
no vwap / transactions fields used
no bid / ask / spread fields used
no full-day high / low fields used
no candidate after allowed decision cutoff
episode_id assigned for all rows
activation_state assigned for all rows
```

Distribution QA：

```text
rows per trading day
rows per ticker-day
PM / RTH row count
yearly row count
top ticker concentration
top date concentration
early-close day row count
activation_state distribution
episode count per day
rows per episode
```

## GO

```text
GO if:
  duplicate ticker-minute = 0
  all active condition checks pass
  Train / Val-A / Val-B / OOS all have rows
  PM and RTH both have samples
  no future / full-day fields present
  early-close days handled by calendar close
  episode_id distribution is reasonable
```

## NO-GO

```text
NO-GO if:
  non-trading dates appear
  active universe dominated by one date / ticker
  PM or RTH accidentally empty
  feature audit finds future / full-day columns
  episode construction creates pathological giant episodes
```

---

# Phase 4：Add labels_v0

## 目的

给 active-minute rows 打 future diagnostics 和 execution labels。

Labels 不用于 self-supervised encoder pretraining。
Labels 只用于 attribution、selection、baseline、replay。

## 输入

```text
trading_calendar_v0
base_active_minute_universe_v0
minute_ohlcv
```

## 输出

```text
data/silver/base_active_minute_labeled_v0/date=YYYY-MM-DD/ticker_bucket=XXX/part.parquet
```

## Entry

基础 entry：

```text
entry_price = open of entry_time_et bar
entry_model = next_bar_open_proxy_v0
```

保守 entry variants：

```text
entry_next_open =
  next bar open

entry_next_open_plus_50bps =
  next bar open * 1.005

entry_next_open_plus_100bps =
  next bar open * 1.010

entry_adverse_proxy =
  max(next_bar_open, signal_close * 1.0025)
```

Primary label 使用：

```text
entry_next_open
```

但所有 final reports 必须做 sensitivity。

## Future window

```text
10m:
  entry_time_et <= bar_start_et < entry_time_et + 10m

30m:
  entry_time_et <= bar_start_et < entry_time_et + 30m
```

如果 future window 跨过该日 `regular_close_et`：

```text
label_quality_flag = INSUFFICIENT_FUTURE_BARS
```

## Primary execution label

```text
sl5_tp8_hold30

SL = -5%
TP = +8%
max_hold = 30m
round_trip_cost = 0.50%
```

Same-bar TP/SL：

```text
conservative stop-first
```

## Cost sensitivity labels

额外生成：

```text
round_trip_cost = 0.50%
round_trip_cost = 1.00%
round_trip_cost = 1.50%
round_trip_cost = 2.00%
```

Label variants：

```text
sl5_tp8_hold30_cost050
sl5_tp8_hold30_cost100
sl5_tp8_hold30_cost150
sl5_tp8_hold30_cost200
```

## Diagnostics

```text
future_mfe_10m
future_mae_10m
future_mfe_30m
future_mae_30m
time_to_mfe_30m
time_to_mae_30m
fade_after_high_pct
continuation_flag
fakeout_flag
exhaustion_flag
```

Diagnostics 不等于 PnL。
Primary PnL 只使用 execution labels。

## 并发

并发粒度：

```text
date + ticker_bucket
```

每个 task 读取：

```text
active candidates for date D bucket B
minute bars for date D bucket B
trading_calendar row for date D
```

推荐：

```text
workers = num_cores - 2
```

重跑：

```text
per date + ticker_bucket
```

## QA

```text
only trading days processed
label_quality_flag assigned for all rows
entry_price not null for OK rows
future_bar_count_10m valid
future_bar_count_30m valid
exit_time_et not null for OK execution rows
return_after_cost = return_before_cost - cost
same-bar ambiguous handled as stop-first
raw MFE / MAE marked diagnostic
cost sensitivity labels generated
entry variant labels generated
```

OK-rate QA：

```text
label_quality_flag OK rate by:
  year
  session_type
  activation_state
  price bucket
  liquidity bucket
```

## GO

```text
GO if:
  label_quality_flag == OK for >= 95% rows overall
  OK rate not pathologically low in any key bucket
  execution labels valid for all OK rows
  impossible returns = 0
  null exits for OK rows = 0
  same-bar ambiguous rate reported
```

## NO-GO

```text
NO-GO if:
  non-trading dates processed
  entry bar missing rate too high
  exit logic has nulls or impossible returns
  same-bar handling inconsistent
  label missingness concentrated in important buckets
```

---

# Phase 5：Build encoder_windows_v0

## 目的

把每个 active-minute row 转成 60-bar historical input window。

## 输入

```text
base_active_minute_universe_v0
minute_ohlcv
trading_calendar_v0
```

## 输出

```text
data/gold/encoder_windows_v0/dataset_split=Train/date=YYYY-MM-DD/ticker_bucket=XXX/part.parquet

data/gold/encoder_windows_v0/dataset_split=Val/date=YYYY-MM-DD/ticker_bucket=XXX/part.parquet

data/gold/encoder_windows_v0/dataset_split=OOS/date=YYYY-MM-DD/ticker_bucket=XXX/part.parquet
```

## Window

```text
lookback = 60 completed bars
window ends at signal_bar_start_et
```

有效 bars：

```text
<30:
  drop

30–59:
  left-pad

>=60:
  keep last 60
```

## Input features

OHLCV-only，且只用 signal_bar_start_et 及以前：

```text
return_1m
log_close_relative_to_window_start
high_low_range_pct
close_open_return
volume
log_volume
dollar_volume_proxy
volume_zscore_past
range_zscore_past
close_to_session_vwc_pct
rolling_3m_volume_to_avg20
```

不输入：

```text
future labels
entry price
future MFE / MAE
execution return
cluster_id
activation_state if it creates shortcut risk
full-day stats
daily future info
```

## Feature normalization

```text
fit normalizer on Train only
apply same normalizer to Val / OOS
```

Prefer：

```text
rolling / causal normalization when possible
```

避免：

```text
full-day volume normalization
current day total volume
future day stats
Val / OOS fitted scaler
```

## 并发

分两步。

### 5.1 Fit normalizer

并发粒度：

```text
Train date + ticker_bucket partial stats
```

每个 worker 输出：

```text
count
sum
sum_sq
min
max
quantile sketch if needed
```

最后 reduce 成：

```text
data/gold/encoder/models/feature_normalizer_v0.pkl
```

### 5.2 Build windows

并发粒度：

```text
date + ticker_bucket
```

推荐：

```text
workers = num_cores - 2
```

重跑：

```text
normalizer:
  full Train rerun

windows:
  per date + ticker_bucket
```

## QA

```text
only trading days processed
no labels in windows
no future bars in windows
window ends at signal_bar_start_et
normalizer fit uses Train only
Val / OOS use Train normalizer
finite feature ratio >= 99.9%
padding_mask valid
feature audit passes
```

## GO

```text
GO if:
  feature audit passes
  no label / future columns present
  finite feature ratio >= 99.9%
  Train / Val / OOS windows generated
```

## NO-GO

```text
NO-GO if:
  labels leak into X
  entry / future bars leak into X
  normalizer fitted on Val / OOS
  large fraction of windows invalid
```

---

# Phase 6：Train self-supervised encoder_v0

## 目的

训练 intraday OHLCV morphology encoder。

## 输入

```text
encoder_windows_v0 where dataset_split == Train
```

## 输出

```text
data/gold/encoder/models/domain_encoder_v0.pt
data/reports/encoder_train_report_v0.md
```

## Train 内部时间切

```text
encoder_train_inner:
  2016-08-02 to 2021-09-30

encoder_train_holdout:
  2021-10-01 to 2021-12-31
```

## Sampling

```text
group by ticker + date
max_windows_per_ticker_day = 60
min_spacing_minutes = 2
session-balanced sampling
activation_state-balanced sampling if needed
```

## Model

```text
PatchTST-style Transformer encoder

input_length = 60
patch_len = 5
stride = 5
d_model = 128
layers = 4
heads = 4
embedding_dim = 128
```

## Self-supervised objective

v0.5 必须明确训练任务。

Primary objective：

```text
masked patch reconstruction
```

Optional auxiliary objectives：

```text
contrastive learning with time-crop / jitter augmentation
future patch prediction within historical window only
same ticker-day nearby window as weak positive
different ticker/date/session as negatives
```

禁止使用：

```text
future labels
future bars after signal_bar_start_et
execution returns
cluster attribution
```

## Shortcut controls

防止模型只学：

```text
session_type
padding pattern
ticker identity
price level
liquidity bucket
year / regime shortcut
```

措施：

```text
session-balanced batches
ticker-day cap
price-relative features
volume normalization
padding mask audit
embedding probe tests
```

Probe tests：

```text
probe predict session_type from embedding
probe predict price bucket
probe predict liquidity bucket
probe predict year
probe predict ticker identity for frequent tickers
```

如果这些 probe 过强，需要判断 embedding 是否被 shortcut 主导。

## 并发

训练本身：

```text
single GPU preferred
DataLoader workers = 4–8
prefetch_factor = 2–4
```

CPU only：

```text
use smaller batch
num_workers = num_cores / 2
```

Data loading：

```text
shard by date + ticker_bucket
shuffle shards
sample within shard
```

v0 不做大规模 sweep。

## QA

```text
training uses Train only
holdout is time-split
loss decreases
holdout loss improves then stabilizes
embedding variance not collapsed
no NaN gradients
positive pair similarity > random negative similarity
shortcut probe tests reported
padding/session shortcut risk reported
```

## GO

```text
GO if:
  training stable
  holdout loss improves then stabilizes
  embedding collapse check passes
  model embeds Val / OOS without NaNs
  shortcut probes acceptable
```

## NO-GO

```text
NO-GO if:
  embedding collapse
  NaN loss
  model only learns padding/session shortcut
  Val/OOS embedding generation unstable
```

---

# Phase 7：Generate embeddings_v0

## 目的

把 Train / Val / OOS windows 转成 128d embeddings。

## 输入

```text
domain_encoder_v0.pt
encoder_windows_v0
```

## 输出

```text
data/gold/encoder/embeddings_v0/dataset_split=Train/date=YYYY-MM-DD/ticker_bucket=XXX/part.parquet

data/gold/encoder/embeddings_v0/dataset_split=Val/date=YYYY-MM-DD/ticker_bucket=XXX/part.parquet

data/gold/encoder/embeddings_v0/dataset_split=OOS/date=YYYY-MM-DD/ticker_bucket=XXX/part.parquet
```

字段：

```text
ticker
date
bar_start_et
signal_bar_start_et
decision_time_et
dataset_split
research_split
ticker_bucket
episode_id
embedding_000 ... embedding_127
```

不包含：

```text
labels
future returns
execution PnL
```

## 并发

如果 GPU：

```text
single GPU inference
batch by shard
DataLoader workers = 4–8
```

如果 CPU：

```text
parallel by date + ticker_bucket
workers = num_cores - 2
```

重跑：

```text
per dataset_split + date + ticker_bucket
```

## QA

```text
only trading days present
row count matches valid windows
embedding dim = 128
embedding finite rate >= 99.99%
duplicate key = 0
no labels included
```

## GO

```text
GO if:
  embeddings generated for all splits
  duplicate key = 0
  finite rate >= 99.99%
```

## NO-GO

```text
NO-GO if:
  missing split embeddings
  NaN embeddings
  duplicate keys
  labels leak into embedding table
```

---

# Phase 8：Fit dimensionality reduction / clustering_v0

## 目的

在 Train embeddings 上发现 morphology clusters。

v0.5 使用双轨：

```text
Primary discovery:
  UMAP + HDBSCAN

Robustness checks:
  PCA + HDBSCAN
  raw embedding + HDBSCAN
  PCA / embedding + KMeans or GMM
```

核心原则：

```text
UMAP is a discovery lens, not the only truth.
```

## 输入

```text
embeddings_v0 where dataset_split == Train
```

## 输出

Models：

```text
data/gold/encoder/models/embedding_scaler_v0.pkl

data/gold/encoder/models/umap_v0.pkl
data/gold/encoder/models/umap_scaler_v0.pkl
data/gold/encoder/models/hdbscan_umap_v0.pkl

data/gold/encoder/models/pca_v0.pkl
data/gold/encoder/models/pca_scaler_v0.pkl
data/gold/encoder/models/hdbscan_pca_v0.pkl

data/gold/encoder/models/hdbscan_raw_v0.pkl

data/gold/encoder/models/kmeans_v0.pkl
data/gold/encoder/models/gmm_v0.pkl
```

Cluster assignments：

```text
data/gold/encoder/clusters_v0/method=umap_hdbscan/dataset_split=Train/...

data/gold/encoder/clusters_v0/method=umap_hdbscan/dataset_split=Val/...

data/gold/encoder/clusters_v0/method=umap_hdbscan/dataset_split=OOS/...

data/gold/encoder/clusters_v0/method=pca_hdbscan/...

data/gold/encoder/clusters_v0/method=raw_hdbscan/...

data/gold/encoder/clusters_v0/method=kmeans/...

data/gold/encoder/clusters_v0/method=gmm/...
```

## Fit sample

```text
max_fit_rows = 1,000,000

stratify by:
  year
  session_type
  activation_state
  ticker-day

Train only
```

## Primary pipeline

```text
128d embedding
→ Train-fitted StandardScaler
→ Train-fitted UMAP 5d
→ Train-fitted UMAP StandardScaler
→ Train-fitted HDBSCAN
```

Val / OOS：

```text
transform only
approximate_predict only
```

## Robustness pipelines

PCA + HDBSCAN：

```text
128d embedding
→ Train-fitted StandardScaler
→ Train-fitted PCA 20d
→ Train-fitted PCA StandardScaler
→ Train-fitted HDBSCAN
```

Raw embedding + HDBSCAN：

```text
128d embedding
→ Train-fitted StandardScaler
→ Train-fitted HDBSCAN
```

KMeans / GMM：

```text
128d embedding or PCA 20d
→ Train-fitted scaler
→ Train-fitted KMeans / GMM
```

## Stability checks

Run multiple seeds / bootstrap samples:

```text
n_bootstrap = 5–10
```

Report：

```text
cluster membership stability
selected cluster recurrence across seeds
Val-A attribution consistency
Val-B replay consistency
selected trade overlap across methods
OOS noise rate by year
OOS low-probability assignment rate
embedding distance-to-train distribution
largest cluster share
noise rate
```

## 并发

Fit UMAP / HDBSCAN：

```text
single process or library-level parallelism
n_jobs if supported
```

Transform / assignment：

```text
parallel by method + dataset_split + date + ticker_bucket
workers = num_cores - 2
```

重跑：

```text
fit models:
  full Train sample rerun

cluster assignment:
  method + dataset_split + date + ticker_bucket
```

## QA

```text
fit uses Train only
Val / OOS not used in fit
cluster_id assigned or -1 noise
cluster_probability in [0,1] when available
noise rate reported
largest cluster share reported
stability across seeds reported
Val/OOS transform succeeds
```

## GO

```text
GO if:
  non-noise clusters exist
  largest cluster share not extreme
  Val / OOS transform succeeds
  selected high/low behavior clusters are not purely seed artifacts
```

## NO-GO

```text
NO-GO if:
  all rows noise
  one cluster dominates almost everything
  accidental refit on Val / OOS
  UMAP-only clusters disappear under all robustness checks
```

---

# Phase 9：Cluster attribution_v0

## 目的

评估 clusters 是否对应 executable behavior 或 meaningful path behavior。

因为 v0.5 是探索阶段，所以 cluster 的价值不只来自赚钱，也来自识别：

```text
continuation
fakeout
fade
exhaustion
high-risk trap
untradeable chop
```

## 输入

```text
clusters_v0
base_active_minute_labeled_v0
base_active_minute_universe_v0
```

## 输出

```text
data/reports/cluster_attribution_train_v0.csv
data/reports/cluster_attribution_val_a_v0.csv
data/reports/cluster_attribution_val_b_v0.csv
data/reports/cluster_attribution_oos_v0.csv

data/reports/cluster_path_profile_v0.csv
data/reports/cluster_stability_report_v0.md
```

## Metrics

Primary execution metrics：

```text
mean_exec_return_after_cost
median_exec_return_after_cost
win_rate_after_cost
tp_rate
sl_rate
timeout_rate
mean_hold_minutes
same_bar_ambiguous_rate
```

Cost sensitivity：

```text
mean_return_cost050
mean_return_cost100
mean_return_cost150
mean_return_cost200
```

Path diagnostics：

```text
future_mfe_10m
future_mae_10m
future_mfe_30m
future_mae_30m
time_to_mfe_30m
time_to_stop
fade_probability
continuation_probability
fakeout_probability
exhaustion_probability
```

Concentration metrics：

```text
sample_count
episode_count
trade_count_proxy
unique_dates
unique_tickers
max_single_date_share
max_single_ticker_share
max_single_episode_share
session_distribution
activation_state_distribution
```

## Row-level / episode-level / trade-level

必须报告三层：

```text
row-level metrics:
  every active-minute row

episode-level metrics:
  aggregate by episode_id

trade-level replay metrics:
  after online selection rules
```

最终以：

```text
trade-level chronological replay
```

为主。

## 并发

省内存做法：

```text
dataset_split + date partition partial aggregate
then reduce by method + cluster_id
```

推荐：

```text
workers = num_cores - 2
```

## QA

```text
labels joined by exact key
join coverage >= 99%
primary metrics use execution labels only
raw MFE / MAE marked diagnostic
row-level and episode-level metrics both computed
concentration metrics computed
cost sensitivity computed
```

## GO

```text
GO if:
  enough clusters pass minimum sample threshold
  Val-A / Val-B / OOS metrics available
  clusters show interpretable path separation
```

## NO-GO

```text
NO-GO if:
  label join fails
  attribution relies on raw MFE as PnL
  cluster performance is dominated by one date/ticker/episode
```

---

# Phase 10：Val-A cluster scoring and selection_v0

## 目的

只用 Val-A 估计 cluster_score 和 selected_clusters。

不在 Val-A 上调 threshold / cooldown / caps。

## 输入

```text
cluster_attribution_val_a_v0
clusters_val_a_v0
labels_val_a_v0
```

## 输出

```text
data/gold/encoder/config/selected_clusters_candidates_v0.json
data/reports/cluster_selection_val_a_v0.csv
```

## Minimum eligibility

cluster 必须满足：

```text
min_val_a_rows
min_val_a_episodes
min_val_a_dates
min_val_a_tickers
max_single_date_share
max_single_ticker_share
max_single_episode_share
```

建议初始值：

```text
min_val_a_rows = 500
min_val_a_episodes = 50
min_val_a_dates = 20
min_val_a_tickers = 20
max_single_date_share = 0.20
max_single_ticker_share = 0.20
max_single_episode_share = 0.10
```

## Shrinked cluster score

不要直接用 cluster mean return。

使用：

```text
cluster_score_shrunk =
  (n / (n + k)) * cluster_mean
  + (k / (n + k)) * global_mean
```

其中：

```text
n = number of Val-A replay-eligible samples or episodes
k = shrinkage strength
```

建议：

```text
k = 500 rows
or k = 50 episodes
```

Primary score：

```text
score_primary =
  shrinked mean sl5_tp8_hold30_return_after_cost050
```

Robust score：

```text
score_robust =
  weighted combination of:
    shrinked mean cost050
    shrinked mean cost100
    median daily return
    date concentration penalty
    ticker concentration penalty
```

## Selected cluster categories

不是只选赚钱 cluster。可以标记：

```text
positive_continuation_clusters
negative_avoid_clusters
fakeout_clusters
exhaustion_clusters
chop_clusters
```

v0.5 主交易 replay 只使用 positive_continuation_clusters。

但 report 要保留所有 behavior cluster。

## QA

```text
Val-A only
no Val-B access
no OOS access
cluster_score uses shrinkage
minimum sample thresholds enforced
concentration filters enforced
```

## GO

```text
GO if:
  selected candidate clusters have nontrivial sample size
  not dominated by one ticker/date/episode
  cluster path profiles are interpretable
```

## NO-GO

```text
NO-GO if:
  selected clusters only exist due to tiny sample
  selected clusters are concentration artifacts
  selection accidentally uses Val-B or OOS
```

---

# Phase 11：Val-B online selection_v0

## 目的

只用 Val-B 锁定可用于 OOS replay 的 online selection config。

## 输入

```text
selected_clusters_candidates_v0.json
clusters_val_b_v0
labels_val_b_v0
```

## 输出

```text
data/gold/encoder/config/online_selection_config_v0.json
data/reports/online_selection_val_b_v0.csv
```

## Point score

```text
point_score =
  cluster_score_shrunk_from_ValA * cluster_probability
```

对于没有 cluster_probability 的方法：

```text
point_score =
  cluster_score_shrunk_from_ValA
```

## Val-B grid

```text
selected_probability_threshold ∈ {0.50, 0.60, 0.70}

score_threshold ∈ {90, 95, 97.5, 99 percentile}

cooldown_minutes ∈ {0, 15, 30, 60}

max_trades_per_day ∈ {5, 10, 20, 50}

max_premarket_trades_per_day ∈ {2, 3, 5, 10}

max_rth_trades_per_day ∈ {5, 10, 20, 40}

max_trades_per_ticker_day ∈ {1, 2, 3}
```

## Replay rules

每个 date 内必须：

```text
sort by decision_time_et ascending
single-thread chronological replay
```

规则：

```text
if cluster_id not selected:
  skip

if cluster_probability < selected_probability_threshold:
  skip

if point_score < selected_score_threshold:
  skip

if trades_today >= max_trades_per_day:
  skip

if session_trades >= max_session_trades:
  skip

if ticker_trades_today >= max_trades_per_ticker_day:
  skip

if decision_time_et < ticker_block_until[ticker]:
  skip

else:
  take trade
```

take trade 后：

```text
exit_time = exec_sl5_tp8_hold30_exit_time_et
ticker_block_until[ticker] = exit_time + cooldown_minutes
```

## 并发

Grid search 可并发：

```text
one worker per config
workers = min(num_cores - 2, number_of_configs)
```

每个 config 内部：

```text
Val-B chronological replay by date
```

日期之间可以并发：

```text
parallel by date
reduce daily results
```

但单个 date 内必须 chronological。

## QA

```text
all config selected using Val-B only
no OOS access
Val-B replay chronological
one open position per ticker enforced
cooldown starts after exit_time
no end-of-day top-N
trade count nontrivial
```

## GO

```text
GO if:
  Val-B selected config has nontrivial trade count
  not dominated by one ticker/date/episode
  beats or is competitive with simple baselines
  cost sensitivity not completely fragile
```

## NO-GO

```text
NO-GO if:
  selected config uses OOS
  end-of-day top-N appears
  trade count too small
  selected trades highly concentrated
```

---

# Phase 12：Baselines_v0

## 目的

建立同 universe、同 label、同 replay policy 下的可比较 baselines。

所有 baselines 必须使用：

```text
same active-minute universe
same labels
same cost assumptions
same Train / Val-A / Val-B / OOS split
same chronological replay constraints
```

---

## Baseline A：raw active-minute

输入：

```text
base_active_minute_labeled_v0
```

输出：

```text
data/reports/baseline_raw_active_minute_train_val_oos_v0.csv
```

方法：

```text
take all eligible active-minute rows subject to same replay/cooldown/caps
or report unconditional row/episode-level behavior
```

并发：

```text
parallel partial aggregate by dataset_split + date
reduce by dataset_split
```

---

## Baseline B：simple online rule

Feature examples：

```text
current_gain_pct
high_so_far_gain_pct
rolling_3m_volume_to_avg20
close_to_session_vwc_pct
rolling_15m_dollar_volume_proxy
activation_state
session_type
```

Bucket edges：

```text
fit on Train only
quantiles = 20%, 40%, 60%, 80%
```

Val-A：

```text
estimate bucket/rule scores
```

Val-B：

```text
select rule / threshold / cooldown / caps
```

OOS：

```text
final replay
```

并发：

```text
bucket edge fit:
  partial quantile sketch by Train date + ticker_bucket
  reduce to final edges

Val grid:
  parallel by config
  within each config, replay by date

OOS:
  parallel by date
```

单个 date 内必须 chronological。

---

## Baseline C：handcrafted ranking

Model：

```text
Logistic regression
or LightGBM
```

Target：

```text
exec_sl5_tp8_hold30_positive_after_cost
```

Fit：

```text
Train only
```

Selection：

```text
Val-A score calibration
Val-B threshold/caps/cooldown selection
```

OOS：

```text
chronological replay
```

Feature availability：

```text
only signal_bar_start_et and earlier
same active-minute universe
same entry/exit label
same cost assumptions
```

并发：

```text
feature table build:
  date + ticker_bucket

model training:
  library-level parallelism

Val/OOS replay:
  parallel by date
  chronological within date
```

---

## Baseline D：encoder features + handcrafted features

Purpose：

```text
test whether encoder adds value as feature,
not only as cluster selector
```

Models：

```text
LightGBM handcrafted only
LightGBM handcrafted + embedding
LightGBM handcrafted + cluster features
```

This helps separate：

```text
discovery value:
  clusters as interpretable morphology groups

predictive feature value:
  embedding improves supervised ranking
```

---

## QA

```text
all baselines use same active-minute universe
all primary comparisons use sl5_tp8_hold30
Train-only fit
Val-A scoring if needed
Val-B-only selection
OOS chronological replay
only trading days
no future features
same cost assumptions
```

## GO

```text
GO if:
  all baselines generated with same policy/cost/universe
```

## NO-GO

```text
NO-GO if:
  baselines use different universe
  baselines use different policy
  baselines tune on OOS
  baselines use future features
```

---

# Phase 13：OOS encoder replay and benchmark_v0

## 目的

最终检验 encoder cluster online selection 是否有增量。

## 输入

```text
clusters_oos_v0
labels_oos_v0
selected_clusters_candidates_v0.json
online_selection_config_v0.json
baseline reports
```

## 输出

```text
data/reports/encoder_online_selection_oos_v0.csv
data/reports/encoder_vs_baselines_oos_v0.csv
data/reports/final_report_v0.md
```

## OOS replay

只处理：

```text
OOS trading days
```

每个 date 内按：

```text
decision_time_et ascending
```

逐条 replay：

```text
if cluster_id not selected:
  skip

if cluster_probability < selected_probability_threshold:
  skip

if point_score < selected_score_threshold:
  skip

if trades_today >= max_trades_per_day:
  skip

if session_trades >= max_session_trades:
  skip

if ticker_trades_today >= max_trades_per_ticker_day:
  skip

if decision_time_et < ticker_block_until[ticker]:
  skip

else:
  take trade
```

take trade 后：

```text
exit_time = exec_sl5_tp8_hold30_exit_time_et
ticker_block_until[ticker] = exit_time + cooldown_minutes
```

## 并发

并发粒度：

```text
date
```

因为不同 trading days 独立。

每个 date 内：

```text
single-thread chronological replay
```

推荐：

```text
date workers = num_cores - 2
```

reduce：

```text
aggregate all daily results into final OOS report
```

## Required OOS breakdowns

不要只报一个总表。

必须报告：

```text
OOS overall
OOS by year
OOS by quarter
OOS by month
OOS by session PM/RTH
OOS by activation_state
OOS by price bucket
OOS by liquidity bucket
OOS by cluster_id
OOS by method
OOS by cost assumption
OOS by entry assumption
```

Risk metrics：

```text
mean trade return
median trade return
daily mean return
median daily return
win rate
profit factor
max drawdown proxy
worst day
worst 1% trades
left-tail loss
trade count
trades per day
unique tickers
unique dates
max single ticker contribution
max single date contribution
```

## QA

```text
only OOS trading days processed
OOS config exactly matches Val-B-selected config
no end-of-day top-N
no same-ticker overlapping position
all returns use primary 0.50% cost
cost sensitivity separate
entry sensitivity separate
OOS not used for refit or selection
```

## GO

```text
GO if:
  OOS replay completes
  comparison table generated
  concentration metrics acceptable
  results interpretable against all baselines
```

## NO-GO

```text
NO-GO if:
  OOS uses future ranking
  OOS config differs from Val-B config
  selected trades too few
  concentration invalidates result
  OOS was inspected and then used to tune config
```

---

# Final Decision Gate

v0.5 的最终 gate 是：

```text
GO / NO-GO for L2 research
```

不是：

```text
GO / NO-GO for production trading bot
```

## GO for L2 research if

Encoder cluster online selection in OOS:

```text
1. OOS mean return after cost > 0

2. Beats raw active-minute baseline

3. Beats or is competitive with simple online rule baseline

4. Shows incremental value versus handcrafted ranking,
   or at minimum discovers stable behavior clusters
   that are useful as setup library

5. Val-A / Val-B / OOS direction consistent

6. Trade count is nontrivial

7. Date/ticker/episode concentration acceptable

8. Same-bar ambiguous rate acceptable

9. Cost sensitivity is not completely fragile:
   preferably still reasonable under 1.00% cost

10. OOS by year/quarter does not show all edge coming from one tiny period

11. Cluster identities are reasonably stable under:
    UMAP seed changes
    PCA robustness check
    raw embedding or KMeans/GMM comparison

12. Cluster profiles are interpretable:
    continuation / fakeout / fade / exhaustion / trap
```

## NO-GO for L2 research if

```text
1. Encoder clusters do not beat raw active-minute behavior

2. Simple handcrafted rules explain the entire effect

3. Selected clusters are tiny-sample artifacts

4. OOS results are dominated by one ticker/date/episode

5. Performance only works at 0.50% cost and collapses at 1.00%

6. UMAP-only clusters disappear under all robustness checks

7. OOS is inconsistent with Val-A / Val-B

8. Trade count too small to justify L2 data cost

9. Cluster behavior is not interpretable

10. Replay depends on unrealistic next-bar open assumptions
```

---

# Next phase after GO

If v0.5 passes, next step is not direct live trading.

Next step：

```text
L2_research_v1
```

Purpose：

```text
For selected post-activation morphology clusters,
collect or replay L2 / trades data to test:

1. Can we enter with realistic queue / spread / partial-fill assumptions?

2. Can L2 identify continuation vs exhaustion earlier than OHLCV?

3. Can we exit before the major fade/crash?

4. What is realistic size?

5. What is true slippage?

6. Which clusters are tradeable and which are only visually profitable?
```

Only after L2 research passes should the project move to:

```text
supervised L2 entry model
L2 exit/danger model
execution model
shadow mode
paper trading
small live A/B
```

---

# Final hard constraints

```text
1. Every phase uses trading_calendar_v0 as date driver.

2. No phase loops over raw calendar days.

3. 1min data only assumes OHLCV.

4. No required VWAP, transactions, bid, ask, spread, or L2 in v0.5.

5. REST API only used for all-market retrieval.

6. No per-ticker REST loop for all-market data.

7. Active-minute features use only signal_bar_start_et and earlier bars.

8. Entry price is next-bar open proxy for labels/PnL only.

9. Train fits models/scalers/normalizers/UMAP/PCA/HDBSCAN/KMeans/GMM.

10. Val-A estimates cluster_score and selected_clusters.

11. Val-B selects thresholds/cooldowns/caps.

12. OOS only does chronological replay.

13. Date-level tasks can run concurrently.

14. Within a single trading day replay must be chronological.

15. UMAP is a discovery lens, not the only truth.

16. PCA/raw embedding/KMeans/GMM robustness checks are required.

17. Cluster attribution must report row-level, episode-level, and trade-level metrics.

18. Primary PnL uses execution labels, not raw MFE/MAE.

19. Cost and entry sensitivity must be reported.

20. Final GO means GO for L2 research, not GO for production trading bot.
```
