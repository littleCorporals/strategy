const DEFAULT_FIELDS = "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount";
const STORAGE_KEYS = {
  watchlist: "simpleDesk.watchlist",
  lastDaily: "simpleDesk.lastDaily.cn.v2",
};
const CANDIDATE_PAGE_SIZE = 12;

const state = {
  rows: [],
  summary: {},
  history: [],
  selected: null,
  activeBucket: "priority",
  sortKey: "score",
  sortDirection: "desc",
  watchlist: [],
  basicMap: {},
  analysis: null,
  recommendation: null,
  recommendations: [],
  industryTrends: [],
  backtest: null,
  tradeDate: "",
  dataSource: "",
  databaseCached: false,
  recommendationStatus: "idle",
  recommendationError: "",
  loadError: "",
  candidateVisible: CANDIDATE_PAGE_SIZE,
  activeInterface: "daily_basic",
};

const els = {};
const COLUMN_LABELS = {
  name: "股票名称",
  ts_code: "代码",
  industry: "行业",
  close: "收盘价",
  pct_chg: "涨跌幅",
  amount: "成交额",
  score: "评分",
  signal: "信号",
};
const MODAL_COLUMNS = {
  ts_code: "代码",
  trade_date: "日期",
  name: "名称",
  industry: "行业",
  area: "地区",
  market: "市场",
  list_date: "上市日",
  close: "收盘",
  turnover_rate: "换手%",
  turnover_rate_f: "自由换手%",
  volume_ratio: "量比",
  pe: "市盈率",
  pb: "市净率",
  total_mv: "总市值",
  circ_mv: "流通市值",
  open: "开盘",
  high: "最高",
  low: "最低",
  pre_close: "昨收",
  change: "涨跌额",
  pct_chg: "涨跌幅",
  vol: "成交量",
  amount: "成交额",
  buy_sm_amount: "小单买入",
  sell_sm_amount: "小单卖出",
  buy_md_amount: "中单买入",
  sell_md_amount: "中单卖出",
  buy_lg_amount: "大单买入",
  sell_lg_amount: "大单卖出",
  buy_elg_amount: "超大单买入",
  sell_elg_amount: "超大单卖出",
  net_mf_amount: "净流入",
};
const INTERFACE_NAMES = {
  daily_basic: "指标",
  moneyflow: "资金",
  daily: "日线",
  stock_basic: "资料",
};

function qs(id) {
  return document.getElementById(id);
}

function fromTradeDate(tradeDate) {
  if (!tradeDate || tradeDate.length !== 8) return "";
  return `${tradeDate.slice(0, 4)}-${tradeDate.slice(4, 6)}-${tradeDate.slice(6, 8)}`;
}

function toTradeDate(dateValue) {
  return dateValue.replaceAll("-", "");
}

function numberValue(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function formatNumber(value, digits = 2) {
  const num = numberValue(value);
  if (num === null) return "--";
  return num.toLocaleString("zh-CN", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function formatPct(value) {
  const num = numberValue(value);
  if (num === null) return "--";
  return `${formatNumber(num, 2)}%`;
}

function formatAmount(value) {
  const amount = numberValue(value);
  if (amount === null) return "--";
  if (Math.abs(amount) >= 100000000) return `${formatNumber(amount / 100000000, 2)} 亿`;
  if (Math.abs(amount) >= 10000) return `${formatNumber(amount / 10000, 2)} 万`;
  return formatNumber(amount, 2);
}

function formatThousandYuan(value) {
  const amount = numberValue(value);
  if (amount === null) return "--";
  return formatAmount(amount * 1000);
}

function formatTenThousandYuan(value) {
  const amount = numberValue(value);
  if (amount === null) return "--";
  return formatAmount(amount * 10000);
}

function signedMoneyWan(value) {
  const amount = numberValue(value);
  if (amount === null) return "--";
  const prefix = amount > 0 ? "+" : "";
  return `${prefix}${formatTenThousandYuan(amount)}`;
}

function saveJson(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function loadJson(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
}

function showToast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => els.toast.classList.remove("show"), 3000);
}

function quoteClass(value) {
  const num = numberValue(value);
  if (num === null || num === 0) return "";
  return num > 0 ? "number-up" : "number-down";
}

function dataSourceText(source) {
  if (source === "browser") return "浏览器缓存";
  if (source === "database") return "本地库";
  if (source === "online") return "线上更新";
  if (source === "memory") return "内存缓存";
  if (source === "not_ready") return "未到收盘";
  if (source === "tushare_empty") return "无交易数据";
  if (source === "empty") return "暂无数据";
  return "数据源";
}

function setLoading(isLoading, requestedTradeDate = "") {
  document.body.classList.toggle("is-loading", isLoading);
  els.queryBtn.disabled = isLoading;
  els.exportBtn.disabled = isLoading || state.rows.length === 0;
  els.queryBtn.querySelector("span").textContent = isLoading ? "刷新中" : "刷新";
  if (isLoading) {
    state.loadError = "";
    els.actionLabel.textContent = "加载行情";
    els.actionTag.textContent = requestedTradeDate ? displayTradeDate(requestedTradeDate) : "请稍等";
    els.dataDateLabel.textContent = requestedTradeDate ? `正在读取 ${displayTradeDate(requestedTradeDate)}` : "正在读取交易日";
    els.actionReason.textContent = "正在读取日线行情和股票名称。推荐池会在行情确认后单独计算。";
    els.candidateInfo.textContent = "加载中";
    els.candidateList.innerHTML = '<div class="loading-card">正在加载行情...</div>';
  }
}

function applyDailyPayload(payload, { fromCache = false } = {}) {
  state.rows = decorateRows(payload.rows || []);
  state.summary = payload.summary || {};
  state.tradeDate = payload.trade_date || "";
  state.dataSource = fromCache ? "browser" : payload.data_source || "";
  state.databaseCached = Boolean(payload.database_cached);
  state.loadError = "";
  state.recommendationStatus = "idle";
  state.recommendationError = "";
  if (payload.trade_date) {
    els.tradeDate.value = fromTradeDate(payload.trade_date);
  }
  resetVisibleCounts();
  state.recommendations = decorateRows(payload.recommendations || []);
  const selectedStillExists = state.rows.find((row) => row.ts_code === state.selected?.ts_code);
  state.selected = state.recommendations[0] || selectedStillExists || state.rows[0] || null;
  updateMarket();
  renderCandidates();
  renderSelected();
  if (state.selected && !fromCache) loadSelectedStock(state.selected.ts_code);
  if (payload.trade_date && !fromCache) loadRecommendations(payload.trade_date);
  if (payload.trade_date && !fromCache) loadIndustryTrends(payload.trade_date);
  if (fromCache) {
    showToast("先显示上次数据，正在后台刷新");
  }
}

async function loadRecommendations(tradeDate) {
  state.recommendationStatus = "loading";
  state.recommendationError = "";
  renderCandidates();
  try {
    const response = await fetch(`/api/recommendations?trade_date=${tradeDate}&limit=20`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "推荐池计算失败");
    if (payload.data_source) state.dataSource = payload.data_source;
    state.recommendations = decorateRows(payload.rows || []);
    if (Object.keys(state.basicMap).length) {
      state.recommendations = state.recommendations.map((row) => ({
        ...mergeBasic(row),
        score: row.score,
        signal: row.signal,
      }));
    }
    state.recommendationStatus = "done";
    if (!state.recommendations.length) {
      renderCandidates();
      return;
    }
    const selectedCode = state.selected?.ts_code;
    state.selected = state.recommendations.find((row) => row.ts_code === selectedCode) || state.recommendations[0];
    state.activeBucket = "priority";
    renderCandidates();
    renderSelected();
    await loadSelectedStock(state.selected.ts_code);
  } catch (error) {
    state.recommendationStatus = "error";
    state.recommendationError = error.message || "推荐池计算失败";
    renderCandidates();
  }
}

async function loadIndustryTrends(tradeDate) {
  els.industryInfo.textContent = "加载中";
  try {
    const response = await fetch(`/api/industry-trends?trade_date=${tradeDate}&limit=16`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "行业趋势加载失败");
    if (payload.data_source) state.dataSource = payload.data_source;
    state.industryTrends = payload.rows || [];
    renderIndustryTrends();
  } catch (error) {
    els.industryInfo.textContent = error.message || "行业趋势加载失败";
  }
}

function loadCachedDaily() {
  const cached = loadJson(STORAGE_KEYS.lastDaily, null);
  if (!cached || !cached.rows || !cached.rows.length) return false;
  const namedRows = cached.rows.filter((row) => row.name).length;
  if (namedRows / cached.rows.length < 0.8) return false;
  applyDailyPayload(cached, { fromCache: true });
  return true;
}

function updateStatus(status) {
  els.statusBadge.classList.remove("ready", "error");
  const blockedSeconds = Number(status.tushare_blocked_remaining_seconds || 0);
  if (blockedSeconds > 0) {
    els.statusBadge.classList.add("error");
    els.statusBadge.querySelector("span:last-child").textContent = `冷却 ${blockedSeconds}s`;
    return;
  }
  if (!status.sdk_available || !status.token_configured) {
    els.statusBadge.classList.add("error");
    els.statusBadge.querySelector("span:last-child").textContent = !status.sdk_available
      ? "依赖未安装"
      : "未配置行情";
    return;
  }
  els.statusBadge.classList.add("ready");
  const latest = status.latest_db_trade_date ? displayTradeDate(status.latest_db_trade_date) : "";
  els.statusBadge.querySelector("span:last-child").textContent = latest ? `本地库 ${latest}` : "行情正常";
}

function scoreRow(row) {
  const pct = numberValue(row.pct_chg) ?? 0;
  if (row.recommend_score !== undefined && row.recommend_score !== null) return Number(row.recommend_score);
  const amount = numberValue(row.amount) ?? 0;
  const close = numberValue(row.close) ?? 1;
  const high = numberValue(row.high) ?? close;
  const low = numberValue(row.low) ?? close;
  const nearHighBonus = high > 0 && close / high > 0.985 ? 12 : 0;
  const amplitude = ((high - low) / Math.max(close, 1)) * 100;
  return pct * 8 + Math.log10(Math.max(amount, 1)) * 4 + nearHighBonus + amplitude;
}

function signalFor(row) {
  if (row.recommend_type) return row.recommend_type;
  const pct = numberValue(row.pct_chg) ?? 0;
  const close = numberValue(row.close) ?? 0;
  const open = numberValue(row.open) ?? 0;
  const high = numberValue(row.high) ?? 0;
  const nearHigh = high > 0 && close / high > 0.985;
  if (pct >= 8 && nearHigh) return "过热观察";
  if (pct >= 3 && close >= open) return "次日回踩";
  if (pct <= -5) return "先回避";
  if (pct < 0 && close < open) return "偏弱";
  return "次日低吸";
}

function stockTitle(row) {
  if (!row) return "未选择";
  return row.name ? `${row.name} ${row.ts_code}` : row.ts_code;
}

function candidateName(row) {
  return row?.name || row?.ts_code || "--";
}

function stockSubTitle(row) {
  if (!row) return "";
  const parts = [row.industry, row.area].filter(Boolean);
  return parts.length ? parts.join(" · ") : "行业信息待补充";
}

function modalValue(column, value) {
  if (value === null || value === undefined || value === "") return "";
  if (column === "amount") return formatThousandYuan(value);
  if (["total_mv", "circ_mv"].includes(column)) return formatTenThousandYuan(value);
  if (column === "net_mf_amount" || column.includes("amount")) return formatTenThousandYuan(value);
  if (["turnover_rate", "turnover_rate_f", "volume_ratio", "pe", "pb", "open", "high", "low", "close", "pre_close", "change", "pct_chg"].includes(column)) {
    return typeof value === "number" ? formatNumber(value, 2) : value;
  }
  return value;
}

function setBar(el, value) {
  const pct = Math.max(0, Math.min(100, numberValue(value) ?? 0));
  el.style.width = `${pct}%`;
}

function formatSignedPct(value) {
  const num = numberValue(value);
  if (num === null) return "--";
  return `${num > 0 ? "+" : ""}${formatNumber(num, 2)}%`;
}

function displayTradeDate(tradeDate) {
  if (!tradeDate || tradeDate.length !== 8) return "--";
  return `${tradeDate.slice(0, 4)}-${tradeDate.slice(4, 6)}-${tradeDate.slice(6, 8)}`;
}

function clampNumber(value, min, max, fallback) {
  const num = Number(value);
  if (!Number.isFinite(num)) return fallback;
  return Math.max(min, Math.min(max, Math.round(num)));
}

function nextDayText(row) {
  const next = row?.next_day;
  if (!next) return "";
  const closeText = next.close_pct === null || next.close_pct === undefined ? "--" : formatSignedPct(next.close_pct);
  const highText = next.high_pct === null || next.high_pct === undefined ? "--" : formatSignedPct(next.high_pct);
  return `${next.result || "次日验证"}：收 ${closeText} / 高 ${highText}`;
}

function conditionText(row) {
  const checks = row?.screen_conditions;
  const metrics = row?.screen_metrics;
  if (!checks || !metrics) return "";
  const marketValue = metrics.market_value_yi === null || metrics.market_value_yi === undefined
    ? "--"
    : `${formatNumber(metrics.market_value_yi, 0)}亿`;
  return `量比${formatNumber(metrics.volume_ratio, 2)} / 换手${formatNumber(metrics.turnover_rate, 2)}% / 市值${marketValue}`;
}

function decorateRows(rows) {
  return rows.map((row) => ({
    ...mergeBasic(row),
    score: Number(scoreRow(row).toFixed(2)),
    signal: signalFor(row),
  }));
}

function mergeBasic(row) {
  const info = state.basicMap[row.ts_code] || {};
  return {
    ...row,
    name: row.name || info.name,
    industry: row.industry || info.industry,
    area: row.area || info.area,
  };
}

function applyBasicToRows() {
  if (!Object.keys(state.basicMap).length || !state.rows.length) return;
  const selectedCode = state.selected?.ts_code;
  state.rows = state.rows.map((row) => ({
    ...mergeBasic(row),
    score: Number(scoreRow(row).toFixed(2)),
    signal: signalFor(row),
  }));
  state.recommendations = state.recommendations.map((row) => ({
    ...mergeBasic(row),
    score: row.score,
    signal: row.signal,
  }));
  state.selected =
    state.recommendations.find((row) => row.ts_code === selectedCode) ||
    state.rows.find((row) => row.ts_code === selectedCode) ||
    state.selected;
  renderCandidates();
  renderSelected();
}

function marketDecision(summary) {
  const ratio = numberValue(summary.up_ratio) ?? 0;
  const avg = numberValue(summary.avg_pct_chg) ?? 0;
  if (!summary.total) {
    return {
      mode: "wait",
      label: "等待数据",
      tag: "--",
      reason: "打开页面后会自动找最近有数据的交易日。",
    };
  }
  if (ratio >= 58 && avg > 0) {
    return {
      mode: "attack",
      label: "可以出手",
      tag: "只做强势股",
      reason: "上涨家数占优，平均涨跌幅为正。我的做法是只挑最强的，不在杂毛里消耗精力。",
    };
  }
  if (ratio >= 42) {
    return {
      mode: "wait",
      label: "轻仓观察",
      tag: "先看后动",
      reason: "市场不是单边强势，适合先筛候选，等股票自己走出确认信号。",
    };
  }
  return {
    mode: "defend",
    label: "防守观望",
    tag: "少交易",
    reason: "下跌家数明显更多。我的做法是降低仓位，只记录候选，不急着买。",
  };
}

function updateMarket() {
  const summary = state.summary || {};
  if (state.loadError && !summary.total) {
    els.marketAnswer.classList.remove("attack", "wait", "defend");
    els.marketAnswer.classList.add("defend");
    els.dataDateLabel.textContent = "行情接口异常";
    els.actionLabel.textContent = "暂时没有数据";
    els.actionTag.textContent = "稍后刷新";
    els.actionReason.textContent = state.loadError;
    els.upMetric.textContent = "--";
    els.downMetric.textContent = "--";
    els.avgMetric.textContent = "--";
    els.amountMetric.textContent = "--";
    els.breadthBar.style.width = "0%";
    els.breadthText.textContent = "--";
    return;
  }
  const decision = marketDecision(summary);
  els.marketAnswer.classList.remove("attack", "wait", "defend");
  els.marketAnswer.classList.add(decision.mode);
  const sourceText = state.dataSource ? ` · ${dataSourceText(state.dataSource)}` : "";
  els.dataDateLabel.textContent = state.tradeDate
    ? `数据日 ${displayTradeDate(state.tradeDate)} · ${summary.total || 0} 条 · ${summary.temperature || "--"}${sourceText}`
    : "等待交易日";
  els.actionLabel.textContent = decision.label;
  els.actionTag.textContent = decision.tag;
  els.actionReason.textContent = decision.reason;
  els.upMetric.textContent = summary.up ?? "--";
  els.downMetric.textContent = summary.down ?? "--";
  els.avgMetric.textContent =
    summary.avg_pct_chg === null || summary.avg_pct_chg === undefined ? "--" : formatPct(summary.avg_pct_chg);
  els.amountMetric.textContent = formatThousandYuan(summary.amount_total);
  const ratio = Math.max(0, Math.min(100, numberValue(summary.up_ratio) ?? 0));
  els.breadthBar.style.width = `${ratio}%`;
  els.breadthText.textContent = summary.total ? `${formatNumber(ratio, 1)}% 上涨` : "--";
}

function resetVisibleCounts() {
  state.candidateVisible = CANDIDATE_PAGE_SIZE;
}

function rowBucket(bucket) {
  const recommended = [...state.recommendations];
  const rows = [...state.rows];
  if (bucket === "priority") {
    if (recommended.length) return recommended.sort((a, b) => b.score - a.score);
    if (state.recommendationStatus === "done") {
      return rows
        .filter((row) => {
          const pct = numberValue(row.pct_chg) ?? 0;
          const amount = numberValue(row.amount) ?? 0;
          return amount > 0 && pct > -3.5 && pct < 9.5;
        })
        .map((row) => ({
          ...row,
          recommend_reason: "严格推荐为空，显示活跃备选",
          recommend_type: "备选观察",
        }))
        .sort((a, b) => (numberValue(b.amount) ?? 0) - (numberValue(a.amount) ?? 0));
    }
    return [];
  }
  if (bucket === "pullback") {
    return (recommended.length ? recommended : rows)
      .filter((row) => {
        const pct = numberValue(row.pct_chg) ?? 0;
        return pct > -2.5 && pct < 6;
      })
      .sort((a, b) => b.score - a.score);
  }
  if (bucket === "active") {
    return rows
      .filter((row) => (numberValue(row.pct_chg) ?? 0) < 9.5)
      .sort((a, b) => (numberValue(b.amount) ?? 0) - (numberValue(a.amount) ?? 0));
  }
  return rows
    .filter((row) => (numberValue(row.pct_chg) ?? 0) <= -5)
    .sort((a, b) => (numberValue(a.pct_chg) ?? 0) - (numberValue(b.pct_chg) ?? 0));
}

function renderCandidates() {
  const allRows = rowBucket(state.activeBucket);
  const rows = allRows.slice(0, state.candidateVisible);
  if (!state.rows.length) {
    els.candidateInfo.textContent = "等待行情";
  } else if (state.activeBucket === "priority" && state.recommendationStatus === "loading") {
    els.candidateInfo.textContent = `计算中 · ${state.rows.length} 条行情`;
  } else if (state.activeBucket === "priority" && state.recommendationStatus === "error") {
    els.candidateInfo.textContent = "推荐失败";
  } else if (state.activeBucket === "priority" && !state.recommendations.length && state.recommendationStatus === "done") {
    els.candidateInfo.textContent = `${rows.length}/${allRows.length} 只 · 活跃备选`;
  } else {
    els.candidateInfo.textContent = `${rows.length}/${allRows.length} 只 · ${displayTradeDate(state.tradeDate)}`;
  }
  els.candidateList.innerHTML = "";
  document.querySelectorAll("[data-bucket]").forEach((button) => {
    button.classList.toggle("active", button.dataset.bucket === state.activeBucket);
  });
  if (!rows.length) {
    if (state.activeBucket === "priority" && state.recommendationStatus === "loading") {
      els.candidateList.innerHTML = '<div class="empty">严格推荐池正在计算：量比、换手、市值、均线和次日验证都要过一遍，会比行情慢。</div>';
    } else if (state.activeBucket === "priority" && state.recommendationStatus === "error") {
      els.candidateList.innerHTML = `<div class="empty">推荐池计算失败：${state.recommendationError || "请稍后刷新"}。可以先切到“活跃”看全市场。</div>`;
    } else if (state.activeBucket === "priority" && state.recommendationStatus === "done") {
      els.candidateList.innerHTML = '<div class="empty">当前交易日没有股票同时满足严格推荐条件，活跃备选也为空。建议少交易。</div>';
    } else {
      els.candidateList.innerHTML =
        state.activeBucket === "priority"
          ? '<div class="empty">行情已到，推荐池尚未开始计算。</div>'
          : '<div class="empty">这个分组暂时没有股票</div>';
    }
    return;
  }
  const fragment = document.createDocumentFragment();
  rows.forEach((row) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = `candidate-card ${state.selected?.ts_code === row.ts_code ? "active" : ""}`;
    card.innerHTML = `
      <div class="candidate-top">
        <span>
          <strong>${candidateName(row)}</strong>
          ${row.name ? `<em>${row.ts_code}</em>` : ""}
        </span>
        <strong class="${quoteClass(row.pct_chg)}">${formatPct(row.pct_chg)}</strong>
      </div>
      <p class="candidate-reason">${row.recommend_reason || row.signal || stockSubTitle(row)}</p>
      <div class="candidate-tags">
        <span>${row.recommend_type || row.signal}</span>
        <span>额 ${formatThousandYuan(row.amount)}</span>
        ${row.screen_conditions ? `<span>${conditionText(row)}</span>` : `<span>${stockSubTitle(row)}</span>`}
      </div>
      ${row.next_day ? `<p class="next-day">${nextDayText(row)}</p>` : ""}
    `;
    card.addEventListener("click", () => selectStock(row));
    fragment.appendChild(card);
  });
  if (rows.length < allRows.length) {
    const more = document.createElement("div");
    more.className = "load-hint";
    more.textContent = "继续向下滚动加载更多";
    fragment.appendChild(more);
  }
  els.candidateList.appendChild(fragment);
}

function renderIndustryTrends() {
  const rows = state.industryTrends || [];
  els.industryInfo.textContent = rows.length ? `${rows.length} 个行业` : "暂无行业";
  els.industryList.innerHTML = "";
  if (!rows.length) {
    els.industryList.innerHTML = '<div class="empty">暂无行业趋势</div>';
    return;
  }
  const fragment = document.createDocumentFragment();
  rows.slice(0, 8).forEach((row) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "industry-item";
    const top = row.top_stock?.name || row.top_stock?.ts_code || "--";
    item.innerHTML = `
      <div>
        <strong>${row.industry}</strong>
        <span>${row.up}/${row.count} 上涨 · 强势 ${row.strong}</span>
      </div>
      <em class="${quoteClass(row.avg_pct_chg)}">${formatSignedPct(row.avg_pct_chg)}</em>
      <b><i style="width:${Math.max(0, Math.min(100, row.up_ratio || 0))}%"></i></b>
      <p>${top} ${formatSignedPct(row.top_stock?.pct_chg)}</p>
    `;
    item.addEventListener("click", () => {
      const match = state.recommendations.find((stock) => stock.industry === row.industry) ||
        state.rows.find((stock) => stock.industry === row.industry);
      if (match) selectStock(match);
    });
    fragment.appendChild(item);
  });
  els.industryList.appendChild(fragment);
}

function evaluateStock(row) {
  if (!row) {
    return {
      badge: "--",
      title: "先选择一只股票",
      reason: "我会把买入、观察、回避拆成明确条件，避免只凭涨跌幅冲动操作。",
      entry: "--",
      stop: "--",
      target: "--",
      position: "--",
      warning: "规则写不出来，就不交易。",
    };
  }
  const pct = numberValue(row.pct_chg) ?? 0;
  const close = numberValue(row.close) ?? 0;
  const open = numberValue(row.open) ?? close;
  const high = numberValue(row.high) ?? close;
  const low = numberValue(row.low) ?? close;
  const market = marketDecision(state.summary);

  if (pct <= -5 || (market.mode === "defend" && pct < 3)) {
    return {
      badge: "回避",
      title: "今天不急着买",
      reason: "要么个股偏弱，要么市场环境不支持进攻。我的处理是先放观察池，等重新站强。",
      entry: `重新站上 ${formatNumber(Math.max(open, close), 2)}`,
      stop: `跌破 ${formatNumber(low, 2)}`,
      target: "先不设目标",
      position: "0 到 1 成",
      warning: "弱市里最贵的是冲动，不是错过。",
    };
  }

  if (pct >= 8 && high > 0 && close / high > 0.985) {
    return {
      badge: "观察",
      title: "很强，但不追高",
      reason: "这类票说明资金关注度高，但日内涨幅已经大。我的做法是等回踩或次日确认。",
      entry: `${formatNumber(close * 0.97, 2)} 到 ${formatNumber(close, 2)}`,
      stop: `${formatNumber(Math.max(low, close * 0.94), 2)}`,
      target: `${formatNumber(close * 1.06, 2)} 上方`,
      position: "最多 1 到 2 成",
      warning: "如果开盘直接高开很多，我不会追。",
    };
  }

  if (pct >= 3 && close >= open) {
    return {
      badge: "候选",
      title: "可以列入明日重点",
      reason: "涨幅、收盘位置和成交额都还不错。我的处理是等回踩不破或放量继续走强。",
      entry: `${formatNumber(close * 0.98, 2)} 到 ${formatNumber(close * 1.01, 2)}`,
      stop: `${formatNumber(Math.max(low, close * 0.95), 2)}`,
      target: `${formatNumber(close * 1.05, 2)} 到 ${formatNumber(close * 1.08, 2)}`,
      position: market.mode === "attack" ? "2 到 3 成" : "1 到 2 成",
      warning: "买点必须靠近计划价，离太远就放弃。",
    };
  }

  return {
    badge: "观察",
    title: "先看，不急",
    reason: "这只股票暂时没有足够强的信号。我的处理是只记录，不主动出手。",
    entry: `${formatNumber(close * 0.98, 2)} 附近企稳`,
    stop: `${formatNumber(low, 2)} 下方`,
    target: `${formatNumber(high, 2)} 附近`,
    position: "0 到 1 成",
    warning: "没有明显优势时，现金也是仓位。",
  };
}

function renderSelected() {
  const row = state.selected;
  const idea = evaluateStock(row);
  els.selectedCode.textContent = stockTitle(row);
  els.selectedClose.textContent = row ? formatNumber(row.close, 2) : "--";
  els.selectedPct.textContent = row ? formatPct(row.pct_chg) : "--";
  els.selectedPct.className = row ? quoteClass(row.pct_chg) : "";
  els.selectedAmount.textContent = row ? formatThousandYuan(row.amount) : "--";
  els.decisionBadge.textContent = idea.badge;
  els.planTitle.textContent = idea.title;
  els.planReason.textContent = idea.reason;
  els.planWarning.textContent = idea.warning;
  els.planEntry.textContent = idea.entry;
  els.planStop.textContent = idea.stop;
  els.planTarget.textContent = idea.target;
  els.planPosition.textContent = idea.position;
  if (!row) renderAnalysis(null);
}

function renderForecast(forecast) {
  if (!forecast) return;
  els.planTitle.textContent = forecast.title || "明日观察";
  els.planReason.textContent = forecast.summary || "等待更多数据确认。";
  els.planWarning.textContent = forecast.avoid_signal || "不符合计划就放弃。";
  els.planEntry.textContent = forecast.entry_zone || "--";
  els.planStop.textContent = forecast.stop_price || "--";
  els.planTarget.textContent = forecast.target_zone || "--";
  els.planPosition.textContent = forecast.position || "--";
  els.forecastMetric.textContent = forecast.direction
    ? `${forecast.direction} ${forecast.confidence ?? "--"}`
    : `${forecast.title || "--"} ${forecast.confidence ?? "--"}`;
}

function renderMoneyFlow(money) {
  if (!money) {
    if (els.moneyMetric) els.moneyMetric.textContent = "--";
    els.moneyFlowTitle.textContent = "等待资金数据";
    els.moneyFlowStrength.textContent = "--";
    els.moneyFlowSummary.textContent = "选择股票后显示大单和超大单推算出的主力方向。";
    els.mainMoneyNet.textContent = "--";
    els.extraLargeMoney.textContent = "--";
    els.largeMoney.textContent = "--";
    els.totalMoneyNet.textContent = "--";
    setBar(els.moneyStrengthBar, 0);
    return;
  }
  if (els.moneyMetric) {
    els.moneyMetric.textContent = money.main_net === null || money.main_net === undefined
      ? money.level
      : `${money.level} ${signedMoneyWan(money.main_net)}`;
  }
  els.moneyFlowTitle.textContent = money.level || "资金不明";
  els.moneyFlowStrength.textContent = money.direction || "--";
  els.moneyFlowSummary.textContent = money.readable || money.detail || "资金数据方向不明显。";
  els.mainMoneyNet.textContent = signedMoneyWan(money.main_net);
  els.mainMoneyNet.className = quoteClass(money.main_net);
  els.extraLargeMoney.textContent = signedMoneyWan(money.extra_large_net);
  els.extraLargeMoney.className = quoteClass(money.extra_large_net);
  els.largeMoney.textContent = signedMoneyWan(money.large_net);
  els.largeMoney.className = quoteClass(money.large_net);
  els.totalMoneyNet.textContent = signedMoneyWan(money.net);
  els.totalMoneyNet.className = quoteClass(money.net);
  setBar(els.moneyStrengthBar, money.strength || 0);
}

function renderAnalysis(payload) {
  state.analysis = payload;
  if (!payload) {
    els.recommendTitle.textContent = "等待推荐";
    els.recommendReason.textContent = "先核验消息来源，再结合行情和资金判断。";
    els.forecastMetric.textContent = "--";
    els.trendMetric.textContent = "--";
    if (els.moneyMetric) els.moneyMetric.textContent = "--";
    els.supportMetric.textContent = "--";
    els.resistanceMetric.textContent = "--";
    els.riskWarning.textContent = "等待消息核验。";
    setBar(els.trendBar, 0);
    setBar(els.confidenceBar, 0);
    els.trend5Metric.textContent = "--";
    els.trend20Metric.textContent = "--";
    els.volumeMetric.textContent = "--";
    els.turnoverMetric.textContent = "--";
    els.peMetric.textContent = "--";
    els.pbMetric.textContent = "--";
    els.analysisNotes.textContent = "选择股票后显示关键分析点。";
    els.sourceInfo.textContent = "暂无来源";
    els.sourceList.innerHTML = "";
    renderMoneyFlow(null);
    return;
  }
  const { trend, money, valuation, support_resistance: sr, risk, forecast } = payload;
  if (!state.recommendation) {
    els.recommendTitle.textContent = `${risk.level} · ${risk.action}`;
    els.recommendReason.textContent = forecast?.summary || `${trend.level}，${money.level}，${valuation.level}`;
  }
  renderForecast(forecast);
  renderMoneyFlow(money);
  els.trendMetric.textContent = `${trend.level} ${trend.score}`;
  els.supportMetric.textContent = sr.support ? `${formatNumber(sr.support, 2)} / ${formatSignedPct(-sr.support_gap_pct)}` : "--";
  els.resistanceMetric.textContent = sr.resistance ? `${formatNumber(sr.resistance, 2)} / ${formatSignedPct(sr.resistance_gap_pct)}` : "--";
  els.riskWarning.textContent = `风险 ${risk.score}：${risk.action}`;
  setBar(els.trendBar, trend.score);
  if (!state.recommendation) setBar(els.confidenceBar, Math.max(0, 100 - risk.score));
  els.trend5Metric.textContent = formatSignedPct(trend.pct5);
  els.trend20Metric.textContent = formatSignedPct(trend.pct20);
  els.volumeMetric.textContent = trend.volume_ratio ? `${formatNumber(trend.volume_ratio, 2)} 倍` : "--";
  els.turnoverMetric.textContent = valuation.turnover ? `${formatNumber(valuation.turnover, 2)}%` : "--";
  els.peMetric.textContent = valuation.pe ? formatNumber(valuation.pe, 2) : "--";
  els.pbMetric.textContent = valuation.pb ? formatNumber(valuation.pb, 2) : "--";
  const notes = [...(trend.reasons || []), ...(valuation.notes || [])];
  if (!state.recommendation) {
    els.analysisNotes.textContent = notes.length ? notes.join("；") : "暂无明显异常，继续结合盘面确认。";
  }
}

async function loadAnalysis(tsCode) {
  const tradeDate = toTradeDate(els.tradeDate.value);
  state.recommendation = null;
  renderAnalysis(null);
  els.recommendTitle.textContent = "分析中";
  els.recommendReason.textContent = "正在计算趋势、资金、估值和风险。";
  try {
    const response = await fetch(`/api/stock/${encodeURIComponent(tsCode)}/analysis?end_date=${tradeDate}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "分析失败");
    if (state.selected?.ts_code === tsCode) renderAnalysis(payload);
  } catch (error) {
    els.recommendTitle.textContent = "分析失败";
    els.recommendReason.textContent = error.message || "分析数据加载失败";
  }
}

function renderSources(sources) {
  const announcements = sources?.announcements || [];
  const cninfo = sources?.cninfo || [];
  const news = sources?.news || [];
  const errors = sources?.errors || [];
  const items = [
    ...cninfo.map((item) => ({ type: item.source_level || "一级来源", title: item.title, meta: `${item.source || "巨潮资讯"} ${item.date || ""}`, url: item.url })),
    ...announcements.map((item) => ({ type: "公告", title: item.title, meta: item.ann_date, url: item.url })),
    ...news.map((item) => ({ type: "新闻", title: item.title, meta: item.pub_time || item.src, url: item.url })),
    ...errors.map((item) => ({ type: "提示", title: item, meta: "", url: "" })),
  ];
  els.sourceInfo.textContent = items.length ? `${items.length} 条来源` : "未取到来源";
  els.sourceList.innerHTML = "";
  if (!items.length) {
    els.sourceList.innerHTML = '<div class="empty">没有取到公告或新闻来源</div>';
    return;
  }
  const fragment = document.createDocumentFragment();
  items.slice(0, 12).forEach((item) => {
    const row = document.createElement(item.url ? "a" : "div");
    row.className = "source-item";
    if (item.url) {
      row.href = item.url;
      row.target = "_blank";
      row.rel = "noreferrer";
    }
    row.innerHTML = `<span>${item.type}</span><strong>${item.title || "--"}</strong><em>${item.meta || ""}</em>`;
    fragment.appendChild(row);
  });
  els.sourceList.appendChild(fragment);
}

function renderRecommendation(payload) {
  state.recommendation = payload;
  if (payload?.analysis) renderAnalysis(payload.analysis);
  const rec = payload?.recommendation;
  if (!rec) return;
  els.recommendTitle.textContent = `${rec.action || "等待"} · ${rec.confidence ?? "--"}分`;
  els.recommendReason.textContent = rec.verification || "消息来源不足，谨慎参考。";
  setBar(els.confidenceBar, rec.confidence || 0);
  const reasons = rec.reasons || [];
  const risks = rec.risks || [];
  const conditions = rec.conditions || [];
  els.analysisNotes.textContent = [...reasons, ...risks, ...conditions].slice(0, 6).join("；") || "没有生成有效理由。";
  renderSources(payload.sources);
}

async function loadRecommendation(tsCode) {
  const tradeDate = toTradeDate(els.tradeDate.value);
  els.recommendTitle.textContent = "核验消息中";
  els.recommendReason.textContent = "正在拉取公告、新闻，并调用模型做真实性检查。";
  try {
    const response = await fetch(`/api/stock/${encodeURIComponent(tsCode)}/recommendation?end_date=${tradeDate}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "推荐失败");
    if (state.selected?.ts_code === tsCode) renderRecommendation(payload);
  } catch (error) {
    els.recommendTitle.textContent = "推荐失败";
    els.recommendReason.textContent = error.message || "模型或消息源暂不可用";
  }
}

async function loadSelectedStock(tsCode) {
  await loadHistory(tsCode);
  await Promise.allSettled([loadAnalysis(tsCode), loadRecommendation(tsCode)]);
}

function movingAverage(rows, index, span) {
  if (index + 1 < span) return null;
  const slice = rows.slice(index + 1 - span, index + 1);
  return slice.reduce((sum, row) => sum + (numberValue(row.close) ?? 0), 0) / span;
}

function renderKline() {
  const canvas = els.klineChart;
  const ctx = canvas.getContext("2d");
  const box = canvas.getBoundingClientRect();
  const dpr = Math.max(1, Math.min(window.devicePixelRatio || 1, 2.5));
  const cssWidth = Math.max(320, Math.floor(box.width || canvas.clientWidth || 760));
  const cssHeight = Math.max(180, Math.floor(box.height || canvas.clientHeight || 260));
  const pixelWidth = Math.floor(cssWidth * dpr);
  const pixelHeight = Math.floor(cssHeight * dpr);
  if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
    canvas.width = pixelWidth;
    canvas.height = pixelHeight;
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const width = cssWidth;
  const height = cssHeight;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#fbfcfc";
  ctx.fillRect(0, 0, width, height);
  if (!state.history.length) {
    ctx.fillStyle = "#67736f";
    ctx.font = "15px Segoe UI, Arial";
    ctx.textAlign = "center";
    ctx.fillText("选择股票后加载走势", width / 2, height / 2);
    return;
  }

  const rows = state.history;
  const prices = rows.flatMap((row) => [numberValue(row.high), numberValue(row.low)]).filter((value) => value !== null);
  const vols = rows.map((row) => numberValue(row.vol) ?? 0);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const maxVol = Math.max(...vols, 1);
  const pad = { top: 22, right: 34, bottom: 34, left: 46 };
  const priceHeight = height * 0.65;
  const volTop = pad.top + priceHeight + 22;
  const volHeight = height - volTop - pad.bottom;
  const step = (width - pad.left - pad.right) / rows.length;
  const candleWidth = Math.max(4, Math.min(11, step * 0.58));
  const yPrice = (value) => pad.top + ((maxPrice - value) / Math.max(maxPrice - minPrice, 0.01)) * priceHeight;
  const yVol = (value) => volTop + volHeight - (value / maxVol) * volHeight;

  function crisp(value) {
    return Math.round(value) + 0.5;
  }

  ctx.strokeStyle = "#d8e3df";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i += 1) {
    const y = crisp(pad.top + (priceHeight / 4) * i);
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(width - pad.right, y);
    ctx.stroke();
  }

  const maPoints = [];
  rows.forEach((row, index) => {
    const x = crisp(pad.left + step * index + step / 2);
    const open = numberValue(row.open) ?? 0;
    const close = numberValue(row.close) ?? 0;
    const high = numberValue(row.high) ?? 0;
    const low = numberValue(row.low) ?? 0;
    const up = close >= open;
    ctx.strokeStyle = up ? "#c23b3f" : "#168158";
    ctx.fillStyle = up ? "#c23b3f" : "#168158";
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(x, yPrice(high));
    ctx.lineTo(x, yPrice(low));
    ctx.stroke();
    const bodyTop = Math.round(yPrice(Math.max(open, close)));
    const bodyHeight = Math.max(2, Math.abs(yPrice(open) - yPrice(close)));
    ctx.fillRect(Math.round(x - candleWidth / 2), bodyTop, Math.max(2, Math.round(candleWidth)), Math.round(bodyHeight));
    ctx.globalAlpha = 0.25;
    const volY = Math.round(yVol(numberValue(row.vol) ?? 0));
    ctx.fillRect(Math.round(x - candleWidth / 2), volY, Math.max(2, Math.round(candleWidth)), Math.round(volTop + volHeight - volY));
    ctx.globalAlpha = 1;
    const ma = movingAverage(rows, index, 5);
    if (ma !== null) maPoints.push([x, yPrice(ma)]);
  });

  ctx.strokeStyle = "#245f78";
  ctx.lineWidth = 1.8;
  ctx.beginPath();
  maPoints.forEach(([x, y], index) => {
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  ctx.fillStyle = "#67736f";
  ctx.font = "12px Segoe UI, Arial";
  ctx.textAlign = "right";
  ctx.fillText(formatNumber(maxPrice, 2), pad.left - 8, pad.top + 4);
  ctx.fillText(formatNumber(minPrice, 2), pad.left - 8, pad.top + priceHeight);
  ctx.textAlign = "center";
  ctx.fillText(rows[0]?.trade_date ?? "", pad.left + 36, height - 12);
  ctx.fillText(rows[rows.length - 1]?.trade_date ?? "", width - pad.right - 42, height - 12);
}

async function loadHistory(tsCode) {
  const tradeDate = toTradeDate(els.tradeDate.value);
  els.historyInfo.textContent = `${tsCode} 走势加载中`;
  try {
    const response = await fetch(`/api/stock/${encodeURIComponent(tsCode)}/history?end_date=${tradeDate}&days=80`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "历史行情查询失败");
    state.history = payload.rows || [];
    els.historyInfo.textContent = `${tsCode} · 最近 ${state.history.length} 个交易日`;
    renderKline();
  } catch (error) {
    state.history = [];
    els.historyInfo.textContent = error.message || "历史行情查询失败";
    renderKline();
  }
}

async function selectStock(row) {
  state.selected = row;
  renderSelected();
  renderCandidates();
  await loadSelectedStock(row.ts_code);
}

function loadMoreCandidatesIfNeeded() {
  const el = els.candidateList;
  if (!el || el.scrollTop + el.clientHeight < el.scrollHeight - 60) return;
  const total = rowBucket(state.activeBucket).length;
  if (state.candidateVisible >= total) return;
  state.candidateVisible = Math.min(total, state.candidateVisible + CANDIDATE_PAGE_SIZE);
  renderCandidates();
}

function openDataModal() {
  els.dataModal.hidden = false;
  els.modalTsCode.value = state.selected?.ts_code || "";
  els.modalTradeDate.value = els.tradeDate.value || "";
  els.modalStartDate.value = "";
  els.modalEndDate.value = "";
  renderInterfaceTabs();
  if (window.lucide) window.lucide.createIcons();
}

function closeDataModal() {
  els.dataModal.hidden = true;
}

function openBacktestModal() {
  els.backtestModal.hidden = false;
  els.backtestEndDate.value = els.tradeDate.value || "";
  if (!state.backtest) {
    renderBacktestEmpty();
  }
  if (window.lucide) window.lucide.createIcons();
}

function closeBacktestModal() {
  els.backtestModal.hidden = true;
}

function renderInterfaceTabs() {
  document.querySelectorAll("[data-interface]").forEach((button) => {
    button.classList.toggle("active", button.dataset.interface === state.activeInterface);
  });
}

function renderModalTable(payload) {
  const columns = payload.columns || [];
  const rows = payload.rows || [];
  els.modalTableHead.innerHTML = "";
  els.modalTableBody.innerHTML = "";
  const tr = document.createElement("tr");
  columns.forEach((column) => {
    const th = document.createElement("th");
    th.textContent = MODAL_COLUMNS[column] || column;
    tr.appendChild(th);
  });
  els.modalTableHead.appendChild(tr);

  if (!rows.length) {
    els.modalTableBody.innerHTML = `<tr><td class="empty" colspan="${Math.max(columns.length, 1)}">没有查到数据</td></tr>`;
    return;
  }

  const fragment = document.createDocumentFragment();
  rows.forEach((row) => {
    const rowEl = document.createElement("tr");
    columns.forEach((column) => {
      const td = document.createElement("td");
      const value = row[column];
      if (column === "pct_chg" || column === "net_mf_amount") td.className = quoteClass(value);
      td.textContent = modalValue(column, value);
      rowEl.appendChild(td);
    });
    fragment.appendChild(rowEl);
  });
  els.modalTableBody.appendChild(fragment);
}

async function queryModalData() {
  const params = new URLSearchParams();
  const tsCode = els.modalTsCode.value.trim().toUpperCase();
  const tradeDate = toTradeDate(els.modalTradeDate.value || "");
  const startDate = toTradeDate(els.modalStartDate.value || "");
  const endDate = toTradeDate(els.modalEndDate.value || "");
  if (state.activeInterface !== "stock_basic" && tsCode) params.set("ts_code", tsCode);
  if (tradeDate) params.set("trade_date", tradeDate);
  if (startDate) params.set("start_date", startDate);
  if (endDate) params.set("end_date", endDate);
  els.modalStatus.textContent = `${INTERFACE_NAMES[state.activeInterface]}查询中`;
  els.modalQueryBtn.disabled = true;
  try {
    const response = await fetch(`/api/query/${state.activeInterface}?${params.toString()}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "查询失败");
    renderModalTable(payload);
    els.modalStatus.textContent = `显示 ${payload.count} 条`;
  } catch (error) {
    els.modalTableHead.innerHTML = "";
    els.modalTableBody.innerHTML = "";
    els.modalStatus.textContent = error.message || "查询失败";
  } finally {
    els.modalQueryBtn.disabled = false;
  }
}

function renderBacktestEmpty(message = "点击开始推演后显示结果") {
  els.backtestTitle.textContent = "等待推演";
  els.backtestText.textContent = message;
  els.backtestRules.innerHTML = "";
  els.backtestMeta.textContent = "未运行";
  els.backtestTableBody.innerHTML = '<tr><td class="empty" colspan="7">暂无策略结果</td></tr>';
  els.backtestExampleInfo.textContent = "暂无";
  els.backtestExamples.innerHTML = '<div class="empty">暂无次日验证样本</div>';
}

function renderBacktest(payload) {
  state.backtest = payload;
  const suggestion = payload.suggestion || {};
  els.backtestTitle.textContent = suggestion.title || "推演完成";
  els.backtestText.textContent = suggestion.text || "已完成策略对比。";
  els.backtestRules.innerHTML = "";
  (suggestion.rules || []).forEach((rule) => {
    const item = document.createElement("p");
    item.textContent = rule;
    els.backtestRules.appendChild(item);
  });
  els.backtestMeta.textContent = `${payload.tested_days || 0} 个交易日 · 验证至 ${payload.validated_until || payload.end_date || "--"}`;
  els.backtestTableBody.innerHTML = "";
  const results = payload.results || [];
  if (!results.length) {
    els.backtestTableBody.innerHTML = '<tr><td class="empty" colspan="7">样本不足，无法推演</td></tr>';
    els.backtestExamples.innerHTML = '<div class="empty">暂无次日验证样本</div>';
    return;
  }
  const fragment = document.createDocumentFragment();
  results.forEach((row, index) => {
    const tr = document.createElement("tr");
    if (index === 0) tr.className = "selected";
    tr.innerHTML = `
      <td><strong>${row.name}</strong><em>${row.quality_label || ""}</em></td>
      <td>${row.signal_count}</td>
      <td>${formatPct(row.win_rate)}</td>
      <td class="${quoteClass(row.avg_next_close_pct)}">${formatSignedPct(row.avg_next_close_pct)}</td>
      <td class="${quoteClass(row.avg_next_high_pct)}">${formatSignedPct(row.avg_next_high_pct)}</td>
      <td>${formatPct(row.stop_hit_rate)}</td>
      <td>${formatNumber(row.quality_score, 1)}</td>
    `;
    fragment.appendChild(tr);
  });
  els.backtestTableBody.appendChild(fragment);

  const best = results[0];
  const examples = best?.examples || [];
  els.backtestExampleInfo.textContent = examples.length ? `${best.name} · ${examples.length} 条` : "暂无";
  els.backtestExamples.innerHTML = "";
  if (!examples.length) {
    els.backtestExamples.innerHTML = '<div class="empty">最佳策略暂无样本</div>';
    return;
  }
  const cardFragment = document.createDocumentFragment();
  examples.forEach((row) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "backtest-example";
    card.innerHTML = `
      <div>
        <strong>${candidateName(row)}</strong>
        <span>${row.ts_code} · ${row.trade_date}</span>
      </div>
      <em class="${quoteClass(row.pct_chg)}">${formatPct(row.pct_chg)}</em>
      <p>${conditionText(row) || stockSubTitle(row)}</p>
      <b>${nextDayText(row)}</b>
    `;
    card.addEventListener("click", () => {
      closeBacktestModal();
      selectStock(row);
    });
    cardFragment.appendChild(card);
  });
  els.backtestExamples.appendChild(cardFragment);
}

async function runBacktest() {
  const endDate = toTradeDate(els.backtestEndDate.value || els.tradeDate.value);
  if (!endDate || endDate.length !== 8) {
    showToast("请选择有效结束日");
    return;
  }
  const tradeDays = clampNumber(els.backtestDays.value, 4, 20, 4);
  const perDayLimit = clampNumber(els.backtestLimit.value, 3, 15, 8);
  els.backtestDays.value = tradeDays;
  els.backtestLimit.value = perDayLimit;
  els.runBacktestBtn.disabled = true;
  els.runBacktestBtn.querySelector("span").textContent = "推演中";
  els.backtestTitle.textContent = "正在推演";
  els.backtestText.textContent = "正在逐日读取历史因子并验证次日表现。Tushare 因子接口较慢，首次运行可能需要1-3分钟。";
  els.backtestMeta.textContent = "运行中";
  try {
    const params = new URLSearchParams({
      end_date: endDate,
      trade_days: String(tradeDays),
      per_day_limit: String(perDayLimit),
    });
    const response = await fetch(`/api/backtest/short-swing?${params.toString()}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "推演失败");
    renderBacktest(payload);
  } catch (error) {
    els.backtestTitle.textContent = "推演失败";
    els.backtestText.textContent = error.message || "历史推演暂时不可用";
    els.backtestMeta.textContent = "失败";
    els.backtestTableBody.innerHTML = '<tr><td class="empty" colspan="7">推演失败</td></tr>';
  } finally {
    els.runBacktestBtn.disabled = false;
    els.runBacktestBtn.querySelector("span").textContent = "开始推演";
  }
}

function addSelectedToWatchlist() {
  if (!state.selected) {
    showToast("先选择一只股票");
    return;
  }
  if (!state.watchlist.includes(state.selected.ts_code)) {
    state.watchlist.unshift(state.selected.ts_code);
    state.watchlist = state.watchlist.slice(0, 30);
    saveJson(STORAGE_KEYS.watchlist, state.watchlist);
  }
  showToast(`${state.selected.ts_code} 已加入观察`);
}

async function loadStatus() {
  try {
    const response = await fetch("/api/status");
    const status = await response.json();
    updateStatus(status);
    if (!els.tradeDate.value && status.default_trade_date) {
      els.tradeDate.value = fromTradeDate(status.default_trade_date);
    }
  } catch {
    els.statusBadge.classList.add("error");
    els.statusBadge.querySelector("span:last-child").textContent = "服务异常";
  }
}

async function loadStockBasicInBackground() {
  try {
    const response = await fetch("/api/stock-basic");
    const payload = await response.json();
    if (!response.ok || !payload.items) return;
    state.basicMap = payload.items;
    applyBasicToRows();
  } catch {
    // Names are nice to have;行情本身不能被它拖住。
  }
}

async function queryDaily() {
  const tradeDate = toTradeDate(els.tradeDate.value);
  if (!tradeDate || tradeDate.length !== 8) {
    showToast("请选择有效交易日");
    return;
  }
  const params = new URLSearchParams({
    trade_date: tradeDate,
    fields: DEFAULT_FIELDS,
    auto_fallback: "true",
  });
  setLoading(true, tradeDate);
  const hadCache = state.rows.length > 0 || loadCachedDaily();
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), hadCache ? 45000 : 70000);
  try {
    const response = await fetch(`/api/daily?${params.toString()}`, { signal: controller.signal });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "查询失败");
    saveJson(STORAGE_KEYS.lastDaily, payload);
    if (payload.trade_date && payload.trade_date !== tradeDate) {
      els.tradeDate.value = fromTradeDate(payload.trade_date);
      showToast(`未到收盘或当日暂无数据，已切换到 ${displayTradeDate(payload.trade_date)}`);
    }
    applyDailyPayload(payload);
    const sourceText = dataSourceText(payload.data_source);
    if (!payload.fallback_used) showToast(`已加载 ${state.rows.length} 条行情 · ${sourceText}`);
    if (payload.data_source === "online") loadStockBasicInBackground();
  } catch (error) {
    if (hadCache) {
      showToast(error.message?.includes("冷却") || error.message?.includes("refused")
        ? "Tushare 临时冷却，继续显示上次数据"
        : "刷新较慢，继续显示上次数据");
      return;
    }
    state.loadError = error.name === "AbortError"
      ? "行情接口响应较慢，请稍后刷新。"
      : error.message || "行情接口暂时不可用，请稍后刷新。";
    state.rows = [];
    state.summary = {};
    state.selected = null;
    state.history = [];
    state.analysis = null;
    updateMarket();
    renderCandidates();
    renderSelected();
    renderKline();
    showToast(state.loadError);
  } finally {
    window.clearTimeout(timeoutId);
    setLoading(false);
  }
}

function exportCsv() {
  const tradeDate = toTradeDate(els.tradeDate.value);
  const params = new URLSearchParams({ trade_date: tradeDate, fields: DEFAULT_FIELDS });
  window.location.href = `/api/daily.csv?${params.toString()}`;
}

function bind() {
  [
    "tradeDate",
    "queryBtn",
    "exportBtn",
    "statusBadge",
    "marketAnswer",
    "dataDateLabel",
    "actionLabel",
    "actionTag",
    "actionReason",
    "breadthBar",
    "breadthText",
    "upMetric",
    "downMetric",
    "avgMetric",
    "amountMetric",
    "candidateInfo",
    "candidateList",
    "selectedCode",
    "selectedClose",
    "selectedPct",
    "selectedAmount",
    "decisionBadge",
    "planTitle",
    "planReason",
    "planWarning",
    "planEntry",
    "planStop",
    "planTarget",
    "planPosition",
    "riskWarning",
    "historyInfo",
    "klineChart",
    "addSelectedBtn",
    "dataModalBtn",
    "backtestModalBtn",
    "dataModal",
    "backtestModal",
    "closeDataModalBtn",
    "closeBacktestModalBtn",
    "modalTsCode",
    "modalTradeDate",
    "modalStartDate",
    "modalEndDate",
    "modalQueryBtn",
    "modalStatus",
    "modalTableHead",
    "modalTableBody",
    "forecastMetric",
    "trendMetric",
    "moneyMetric",
    "supportMetric",
    "resistanceMetric",
    "trendBar",
    "confidenceBar",
    "trend5Metric",
    "trend20Metric",
    "volumeMetric",
    "turnoverMetric",
    "peMetric",
    "pbMetric",
    "analysisNotes",
    "industryInfo",
    "industryList",
    "recommendTitle",
    "recommendReason",
    "moneyFlowTitle",
    "moneyFlowStrength",
    "moneyFlowSummary",
    "mainMoneyNet",
    "extraLargeMoney",
    "largeMoney",
    "totalMoneyNet",
    "moneyStrengthBar",
    "sourceInfo",
    "sourceList",
    "backtestEndDate",
    "backtestDays",
    "backtestLimit",
    "runBacktestBtn",
    "backtestTitle",
    "backtestText",
    "backtestRules",
    "backtestMeta",
    "backtestTableBody",
    "backtestExampleInfo",
    "backtestExamples",
    "toast",
  ].forEach((id) => {
    els[id] = qs(id);
  });

  state.watchlist = loadJson(STORAGE_KEYS.watchlist, []);

  els.queryBtn.addEventListener("click", queryDaily);
  els.exportBtn.addEventListener("click", exportCsv);
  els.addSelectedBtn.addEventListener("click", addSelectedToWatchlist);
  els.dataModalBtn.addEventListener("click", openDataModal);
  els.backtestModalBtn.addEventListener("click", openBacktestModal);
  els.closeDataModalBtn.addEventListener("click", closeDataModal);
  els.closeBacktestModalBtn.addEventListener("click", closeBacktestModal);
  els.dataModal.addEventListener("click", (event) => {
    if (event.target === els.dataModal) closeDataModal();
  });
  els.backtestModal.addEventListener("click", (event) => {
    if (event.target === els.backtestModal) closeBacktestModal();
  });
  els.modalQueryBtn.addEventListener("click", queryModalData);
  els.runBacktestBtn.addEventListener("click", runBacktest);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !els.dataModal.hidden) closeDataModal();
    if (event.key === "Escape" && !els.backtestModal.hidden) closeBacktestModal();
  });
  document.querySelectorAll("[data-interface]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeInterface = button.dataset.interface;
      renderInterfaceTabs();
      els.modalStatus.textContent = `已切换到${INTERFACE_NAMES[state.activeInterface]}`;
    });
  });
  els.candidateList.addEventListener("scroll", loadMoreCandidatesIfNeeded);
  document.querySelectorAll("[data-bucket]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeBucket = button.dataset.bucket;
      state.candidateVisible = CANDIDATE_PAGE_SIZE;
      els.candidateList.scrollTop = 0;
      renderCandidates();
    });
  });
}

window.addEventListener("DOMContentLoaded", async () => {
  bind();
  if (window.lucide) window.lucide.createIcons();
  if (!els.tradeDate.value) {
    const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000);
    els.tradeDate.value = yesterday.toISOString().slice(0, 10);
  }
  updateMarket();
  renderCandidates();
  renderSelected();
  renderKline();
  setLoading(false);
  await loadStatus();
  await queryDaily();
});

window.addEventListener("resize", () => {
  window.clearTimeout(renderKline.resizeTimer);
  renderKline.resizeTimer = window.setTimeout(renderKline, 120);
});
