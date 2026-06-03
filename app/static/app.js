const DEFAULT_FIELDS = "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount";
const STORAGE_KEYS = {
  watchlist: "strategyDesk.watchlist.v3",
  lastDaily: "strategyDesk.lastDaily.v3",
};
const CANDIDATE_PAGE_SIZE = 14;
const OVERVIEW_PREVIEW_SIZE = 6;

const VIEW_META = {
  overview: { eyebrow: "Market Console", title: "市场总览" },
  candidates: { eyebrow: "Candidates", title: "候选列表" },
  stock: { eyebrow: "Stock Analysis", title: "个股分析" },
  industry: { eyebrow: "Industry", title: "行业趋势" },
  tools: { eyebrow: "Tools", title: "数据工具" },
};

const state = {
  rows: [],
  summary: {},
  history: [],
  selected: null,
  activeView: "overview",
  activeBucket: "mlLate",
  watchlist: [],
  basicMap: {},
  recommendations: [],
  mlLateSessionRecommendations: [],
  lateSessionRecommendations: [],
  modelReference: null,
  industryTrends: [],
  recommendationStatus: "idle",
  recommendationError: "",
  mlLateSessionStatus: "idle",
  mlLateSessionError: "",
  lateSessionStatus: "idle",
  lateSessionError: "",
  tradeDate: "",
  dataSource: "",
  loadError: "",
  candidateVisible: CANDIDATE_PAGE_SIZE,
  activeInterface: "daily_basic",
  backtest: null,
};

const els = {};

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

const ICONS = {
  "layout-dashboard": [
    ["rect", { x: "3", y: "3", width: "7", height: "7", rx: "1" }],
    ["rect", { x: "14", y: "3", width: "7", height: "7", rx: "1" }],
    ["rect", { x: "14", y: "14", width: "7", height: "7", rx: "1" }],
    ["rect", { x: "3", y: "14", width: "7", height: "7", rx: "1" }],
  ],
  "list-filter": [
    ["path", { d: "M3 6h18" }],
    ["path", { d: "M7 12h10" }],
    ["path", { d: "M10 18h4" }],
  ],
  "scan-line": [
    ["path", { d: "M3 7V5a2 2 0 0 1 2-2h2" }],
    ["path", { d: "M17 3h2a2 2 0 0 1 2 2v2" }],
    ["path", { d: "M21 17v2a2 2 0 0 1-2 2h-2" }],
    ["path", { d: "M7 21H5a2 2 0 0 1-2-2v-2" }],
    ["path", { d: "M7 12h10" }],
  ],
  "building-2": [
    ["path", { d: "M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18" }],
    ["path", { d: "M6 12H4a2 2 0 0 0-2 2v8" }],
    ["path", { d: "M18 9h2a2 2 0 0 1 2 2v11" }],
    ["path", { d: "M10 6h4" }],
    ["path", { d: "M10 10h4" }],
    ["path", { d: "M10 14h4" }],
    ["path", { d: "M10 18h4" }],
  ],
  database: [
    ["ellipse", { cx: "12", cy: "5", rx: "8", ry: "3" }],
    ["path", { d: "M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5" }],
    ["path", { d: "M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" }],
  ],
  "settings-2": [
    ["path", { d: "M20 7h-9" }],
    ["path", { d: "M14 17H5" }],
    ["circle", { cx: "17", cy: "17", r: "3" }],
    ["circle", { cx: "7", cy: "7", r: "3" }],
  ],
  "refresh-cw": [
    ["path", { d: "M21 12a9 9 0 0 1-9 9 9.8 9.8 0 0 1-6.9-2.9" }],
    ["path", { d: "M3 12a9 9 0 0 1 9-9 9.8 9.8 0 0 1 6.9 2.9" }],
    ["path", { d: "M21 3v6h-6" }],
    ["path", { d: "M3 21v-6h6" }],
  ],
  download: [
    ["path", { d: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" }],
    ["path", { d: "M7 10l5 5 5-5" }],
    ["path", { d: "M12 15V3" }],
  ],
  "chart-no-axes-combined": [
    ["path", { d: "M12 16v5" }],
    ["path", { d: "M16 14v7" }],
    ["path", { d: "M20 10v11" }],
    ["path", { d: "M4 20l5-5 4 4 7-7" }],
  ],
  star: [
    ["path", { d: "M12 2l3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21 7 14.2 2 9.3l6.9-1L12 2z" }],
  ],
  play: [
    ["path", { d: "M6 3l15 9-15 9V3z" }],
  ],
  search: [
    ["circle", { cx: "11", cy: "11", r: "8" }],
    ["path", { d: "M21 21l-4.3-4.3" }],
  ],
  x: [
    ["path", { d: "M18 6L6 18" }],
    ["path", { d: "M6 6l12 12" }],
  ],
};

function qs(id) {
  return document.getElementById(id);
}

function text(value, fallback = "--") {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

function setText(id, value, fallback = "--") {
  if (els[id]) els[id].textContent = text(value, fallback);
}

function iconRefresh() {
  document.querySelectorAll("i[data-lucide]").forEach((node) => {
    if (node.dataset.iconReady === "true") return;
    const name = node.dataset.lucide;
    const shapes = ICONS[name];
    if (!shapes) return;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    shapes.forEach(([tag, attrs]) => {
      const shape = document.createElementNS("http://www.w3.org/2000/svg", tag);
      Object.entries(attrs).forEach(([key, value]) => shape.setAttribute(key, value));
      svg.appendChild(shape);
    });
    node.replaceChildren(svg);
    node.dataset.iconReady = "true";
  });
}

function clearNode(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function el(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  if (options.className) node.className = options.className;
  if (options.text !== undefined) node.textContent = text(options.text, "");
  if (options.title !== undefined) node.title = text(options.title, "");
  if (options.href) {
    node.href = options.href;
    node.target = "_blank";
    node.rel = "noreferrer";
  }
  if (options.type) node.type = options.type;
  if (options.dataset) {
    Object.entries(options.dataset).forEach(([key, value]) => {
      node.dataset[key] = value;
    });
  }
  children.forEach((child) => {
    if (child) node.appendChild(child);
  });
  return node;
}

function emptyNode(message, className = "empty") {
  return el("div", { className, text: message });
}

function fromTradeDate(tradeDate) {
  if (!tradeDate || tradeDate.length !== 8) return "";
  return `${tradeDate.slice(0, 4)}-${tradeDate.slice(4, 6)}-${tradeDate.slice(6, 8)}`;
}

function toTradeDate(dateValue) {
  return String(dateValue || "").replaceAll("-", "");
}

function bindDatePickers() {
  document.querySelectorAll('input[type="date"]').forEach((input) => {
    input.setAttribute("inputmode", "none");
    input.addEventListener("keydown", (event) => {
      if (["Tab", "Enter", "Escape", "Backspace", "Delete"].includes(event.key)) {
        return;
      }
      event.preventDefault();
    });
    input.addEventListener("paste", (event) => event.preventDefault());
    input.addEventListener("drop", (event) => event.preventDefault());
  });
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

function formatSignedPct(value) {
  const num = numberValue(value);
  if (num === null) return "--";
  return `${num > 0 ? "+" : ""}${formatNumber(num, 2)}%`;
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
  return `${amount > 0 ? "+" : ""}${formatTenThousandYuan(amount)}`;
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
  showToast.timer = window.setTimeout(() => els.toast.classList.remove("show"), 2600);
}

function quoteClass(value) {
  const num = numberValue(value);
  if (num === null || num === 0) return "";
  return num > 0 ? "number-up" : "number-down";
}

function dataSourceText(source) {
  const labels = {
    browser: "浏览器缓存",
    database: "本地库",
    online: "线上更新",
    memory: "内存缓存",
    not_ready: "未到刷新时间",
    tushare_empty: "无交易数据",
    empty: "暂无数据",
  };
  return labels[source] || "数据源";
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

function setBar(node, value) {
  if (!node) return;
  const pct = Math.max(0, Math.min(100, numberValue(value) ?? 0));
  node.style.width = `${pct}%`;
}

function setLoading(isLoading, requestedTradeDate = "") {
  document.body.classList.toggle("is-loading", isLoading);
  els.queryBtn.disabled = isLoading;
  els.exportBtn.disabled = isLoading || state.rows.length === 0;
  if (els.toolExportBtn) els.toolExportBtn.disabled = isLoading || state.rows.length === 0;
  els.queryBtn.querySelector("span").textContent = isLoading ? "刷新中" : "刷新";
  if (!isLoading) return;
  state.loadError = "";
  setText("actionLabel", "正在读取行情");
  setText("actionTag", requestedTradeDate ? displayTradeDate(requestedTradeDate) : "请稍等");
  setText("dataDateLabel", requestedTradeDate ? `读取 ${displayTradeDate(requestedTradeDate)}` : "读取交易日");
  setText("actionReason", "先加载日线行情，再生成候选池和行业方向。");
  setText("candidateInfo", "加载中");
  clearNode(els.candidateList);
  els.candidateList.appendChild(emptyNode("正在加载行情...", "loading-card"));
  renderOverviewCandidates([]);
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
    els.statusBadge.querySelector("span:last-child").textContent = !status.sdk_available ? "依赖未安装" : "未配置行情";
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
  const open = numberValue(row.open) ?? close;
  const high = numberValue(row.high) ?? close;
  const nearHigh = high > 0 && close / high > 0.985;
  if (pct >= 8 && nearHigh) return "过热观察";
  if (pct >= 3 && close >= open) return "次日回踩";
  if (pct <= -5) return "先回避";
  if (pct < 0 && close < open) return "偏弱";
  return "低吸观察";
}

function stockTitle(row) {
  if (!row) return "未选择";
  return row.name ? `${row.name} ${row.ts_code}` : row.ts_code;
}

function plainStockCode(row) {
  const match = String(row?.ts_code || "").match(/\d{6}/);
  return match ? match[0] : "";
}

function baiduSearchUrl(row) {
  const code = plainStockCode(row);
  if (code) return `https://gushitong.baidu.com/stock/ab-${code}`;
  const query = `${stockTitle(row)} 股票`;
  return `https://www.baidu.com/s?wd=${encodeURIComponent(query)}`;
}

function openBaiduSearch(row) {
  if (!row) {
    showToast("先选择一只股票");
    return;
  }
  window.open(baiduSearchUrl(row), "_blank", "noopener,noreferrer");
}

function stockRowSearchLink(row) {
  const link = el(
    "a",
    {
      className: "baidu-link",
      href: baiduSearchUrl(row),
      title: `打开百度股市通：${stockTitle(row)}`,
    },
    [el("i", { dataset: { lucide: "search" } }), el("span", { text: "实时" })],
  );
  link.addEventListener("click", (event) => event.stopPropagation());
  return link;
}

function candidateName(row) {
  return row?.name || row?.ts_code || "--";
}

function stockSubTitle(row) {
  if (!row) return "";
  const parts = [row.industry, row.area].filter(Boolean);
  return parts.length ? parts.join(" / ") : "行业信息待补充";
}

function rowDisplayPct(row) {
  return row?.late_session?.quote?.pct_chg ?? row?.pct_chg;
}

function rowDisplayAmount(row) {
  return row?.late_session?.quote?.amount_yi !== undefined && row?.late_session?.quote?.amount_yi !== null
    ? `${formatNumber(row.late_session.quote.amount_yi, 2)}亿`
    : formatThousandYuan(row.amount);
}

function rowScore(row) {
  return row?.late_session?.rank_score ?? row?.score;
}

function shortModelId(modelId) {
  const value = String(modelId || "");
  if (!value) return "--";
  return value.length > 18 ? `${value.slice(0, 10)}...${value.slice(-6)}` : value;
}

function modelProbability(row) {
  const probability = numberValue(row?.probability);
  return probability === null ? "--" : formatPct(probability * 100);
}

function modelScoreCell(row) {
  const rank = row?.ml_rank || row?.late_session?.model_rank;
  return el("span", { className: "score-cell" }, [
    el("strong", { text: formatNumber(rowScore(row), 1) }),
    el("small", { text: rank ? `模型#${rank} / ${modelProbability(row)}` : "规则分" }),
  ]);
}

function modelDetailText(row) {
  const rank = row?.ml_rank || row?.late_session?.model_rank;
  if (!rank && row?.probability === undefined) return "";
  return `模型#${rank || "--"} / 概率 ${modelProbability(row)}`;
}

function rowSignalText(row) {
  if (row?.late_session) {
    const quote = row.late_session.quote || {};
    const price = quote.price ? `现价 ${formatNumber(quote.price, 2)}` : "实时价 --";
    return [modelDetailText(row), `${row.late_session.action} / ${price}`, row.late_session.reason]
      .filter(Boolean)
      .join(" / ");
  }
  return row.recommend_reason || row.signal || stockSubTitle(row);
}

function nextDayText(row) {
  const next = row?.next_day;
  if (!next) return "";
  const closeText = next.close_pct === null || next.close_pct === undefined ? "--" : formatSignedPct(next.close_pct);
  const highText = next.high_pct === null || next.high_pct === undefined ? "--" : formatSignedPct(next.high_pct);
  return `${next.result || "次日验证"}：收 ${closeText} / 高 ${highText}`;
}

function conditionText(row) {
  const metrics = row?.screen_metrics;
  if (!metrics) return "";
  const marketValue =
    metrics.market_value_yi === null || metrics.market_value_yi === undefined
      ? "--"
      : `${formatNumber(metrics.market_value_yi, 0)}亿`;
  return `量比 ${formatNumber(metrics.volume_ratio, 2)} / 换手 ${formatNumber(metrics.turnover_rate, 2)}% / 市值 ${marketValue}`;
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
  state.rows = decorateRows(state.rows);
  state.recommendations = state.recommendations.map((row) => ({
    ...mergeBasic(row),
    score: row.score,
    signal: row.signal,
  }));
  state.mlLateSessionRecommendations = state.mlLateSessionRecommendations.map((row) => ({
    ...mergeBasic(row),
    score: row.score,
    signal: row.signal,
  }));
  state.lateSessionRecommendations = state.lateSessionRecommendations.map((row) => ({
    ...mergeBasic(row),
    score: row.score,
    signal: row.signal,
  }));
  state.selected =
    state.recommendations.find((row) => row.ts_code === selectedCode) ||
    state.mlLateSessionRecommendations.find((row) => row.ts_code === selectedCode) ||
    state.lateSessionRecommendations.find((row) => row.ts_code === selectedCode) ||
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
      reason: "打开页面后会自动寻找最近有行情的交易日。",
    };
  }
  if (ratio >= 58 && avg > 0) {
    return {
      mode: "attack",
      label: "可以找强势机会",
      tag: "只做计划内股票",
      reason: "上涨家数占优，平均涨跌为正。新手先看候选池，不追临时冲动。",
    };
  }
  if (ratio >= 42) {
    return {
      mode: "wait",
      label: "轻仓观察",
      tag: "先看后动",
      reason: "市场不是单边强势，适合筛候选、等回踩或突破确认。",
    };
  }
  return {
    mode: "defend",
    label: "防守观望",
    tag: "少交易",
    reason: "下跌家数明显更多，先降低操作频率，把观察名单整理好。",
  };
}

function updateMarket() {
  const summary = state.summary || {};
  els.marketAnswer.classList.remove("attack", "wait", "defend");
  if (state.loadError && !summary.total) {
    els.marketAnswer.classList.add("defend");
    setText("dataDateLabel", "行情接口异常");
    setText("actionLabel", "暂时没有数据");
    setText("actionTag", "稍后刷新");
    setText("actionReason", state.loadError);
    setText("upMetric", "--");
    setText("downMetric", "--");
    setText("avgMetric", "--");
    setText("amountMetric", "--");
    setText("breadthText", "市场宽度 --");
    setBar(els.breadthBar, 0);
    return;
  }

  const decision = marketDecision(summary);
  els.marketAnswer.classList.add(decision.mode);
  const sourceText = state.dataSource ? ` / ${dataSourceText(state.dataSource)}` : "";
  setText(
    "dataDateLabel",
    state.tradeDate
      ? `${displayTradeDate(state.tradeDate)} / ${summary.total || 0} 条 / ${summary.temperature || "--"}${sourceText}`
      : "等待交易日",
  );
  setText("actionLabel", decision.label);
  setText("actionTag", decision.tag);
  setText("actionReason", decision.reason);
  setText("headerSubtitle", state.tradeDate ? `当前交易日 ${displayTradeDate(state.tradeDate)}` : "等待行情数据");
  setText("upMetric", summary.up ?? "--");
  setText("downMetric", summary.down ?? "--");
  setText("avgMetric", summary.avg_pct_chg === null || summary.avg_pct_chg === undefined ? "--" : formatPct(summary.avg_pct_chg));
  setText("amountMetric", formatThousandYuan(summary.amount_total));
  const ratio = Math.max(0, Math.min(100, numberValue(summary.up_ratio) ?? 0));
  setText("breadthText", summary.total ? `市场宽度 ${formatNumber(ratio, 1)}% 上涨` : "市场宽度 --");
  setBar(els.breadthBar, ratio);
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
          recommend_reason: "严格推荐为空，显示活跃备选。",
          recommend_type: "备选观察",
        }))
        .sort((a, b) => (numberValue(b.amount) ?? 0) - (numberValue(a.amount) ?? 0));
    }
    return [];
  }
  if (bucket === "late") {
    return [...state.lateSessionRecommendations].sort((a, b) => (numberValue(rowScore(b)) ?? 0) - (numberValue(rowScore(a)) ?? 0));
  }
  if (bucket === "mlLate") {
    return [...state.mlLateSessionRecommendations].sort((a, b) => (numberValue(rowScore(b)) ?? 0) - (numberValue(rowScore(a)) ?? 0));
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

function emptyCandidateMessage() {
  const messages = {
    loading: "候选池正在计算，会先读取行情、指标和次日验证。",
    error: `推荐池失败：${state.recommendationError || "请稍后刷新"}。可以切到“活跃”看全市场。`,
    mlLateLoading: "模型尾盘正在读取 ML 预测并叠加实时风险闸门。",
    mlLateError: `模型尾盘失败：${state.mlLateSessionError || "请稍后刷新"}。`,
    mlLateIdle: "点击“模型尾盘”后会从模型 Top500 里剔除走弱、过热、低成交和 T+1 追高风险。",
    lateLoading: "尾盘候选正在叠加实时行情和 T+1 买点判断。",
    lateError: `尾盘候选失败：${state.lateSessionError || "请稍后刷新"}。`,
    lateIdle: "点击“尾盘”后会用实时行情复核今天是否还能买。",
    done: "当前交易日没有股票满足这个分类。",
    idle: "等待行情数据。",
  };
  if (state.activeBucket === "mlLate" && state.mlLateSessionStatus === "loading") return messages.mlLateLoading;
  if (state.activeBucket === "mlLate" && state.mlLateSessionStatus === "error") return messages.mlLateError;
  if (state.activeBucket === "mlLate" && state.mlLateSessionStatus !== "done") return messages.mlLateIdle;
  if (state.activeBucket === "late" && state.lateSessionStatus === "loading") return messages.lateLoading;
  if (state.activeBucket === "late" && state.lateSessionStatus === "error") return messages.lateError;
  if (state.activeBucket === "late" && state.lateSessionStatus !== "done") return messages.lateIdle;
  return messages[state.recommendationStatus] || messages.idle;
}

function candidateButton(row, { compact = false } = {}) {
  const nextText = nextDayText(row);
  const rowButton = el("div", {
    className: `${compact ? "compact-row" : "candidate-row"}${row.ts_code === state.selected?.ts_code ? " selected" : ""}`,
    title: [row.recommend_reason || row.signal || "", conditionText(row), nextText].filter(Boolean).join(" / "),
  });
  rowButton.setAttribute("role", "button");
  rowButton.tabIndex = 0;
  const stock = el("span", { className: "candidate-stock" }, [
    el("strong", { text: candidateName(row) }),
    el("small", { text: row.ts_code || "--" }),
  ]);
  if (compact) {
    rowButton.append(
      stock,
      el("span", { className: "muted-cell", text: row.industry || row.area || "--" }),
      el("strong", { className: quoteClass(rowDisplayPct(row)), text: formatPct(rowDisplayPct(row)) }),
    );
  } else {
    rowButton.append(
      stock,
      el("span", { className: "muted-cell", text: row.industry || row.area || "--" }),
      el("span", { className: quoteClass(rowDisplayPct(row)), text: formatPct(rowDisplayPct(row)) }),
      el("span", { text: rowDisplayAmount(row) }),
      modelScoreCell(row),
      el("span", { className: "signal-cell", text: rowSignalText(row) }),
      stockRowSearchLink(row),
    );
  }
  rowButton.addEventListener("click", () => selectStock(row));
  rowButton.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    selectStock(row);
  });
  return rowButton;
}

function renderOverviewCandidates(rows) {
  if (!els.overviewCandidateList) return;
  clearNode(els.overviewCandidateList);
  const previewRows = rows.slice(0, OVERVIEW_PREVIEW_SIZE);
  if (!previewRows.length) {
    els.overviewCandidateList.appendChild(emptyNode(emptyCandidateMessage()));
    return;
  }
  const fragment = document.createDocumentFragment();
  previewRows.forEach((row) => fragment.appendChild(candidateButton(row, { compact: true })));
  els.overviewCandidateList.appendChild(fragment);
}

function metricText(value, { pct = false, digits = 2 } = {}) {
  const num = numberValue(value);
  if (num === null) return "--";
  return pct ? formatPct(num * 100) : formatNumber(num, digits);
}

function renderModelReference() {
  if (!els.modelReference) return;
  clearNode(els.modelReference);
  if (state.activeBucket !== "mlLate") {
    els.modelReference.hidden = true;
    return;
  }
  els.modelReference.hidden = false;
  const ref = state.modelReference;
  if (!ref) {
    els.modelReference.appendChild(emptyNode("模型参考加载中", "model-reference-empty"));
    return;
  }
  const validation = ref.validation || {};
  const fit = ref.fit || {};
  const ranking = ref.ranking_validation || {};
  const top50 = ranking.top50 || {};
  const latest = ref.latest_prediction_validation || {};
  const latestTop50 = latest.top50 || {};
  const latestText = latest.trade_date
    ? `最近验证 ${displayTradeDate(latest.trade_date)} -> ${displayTradeDate(latest.next_trade_date || "")}：全量 ${metricText(latest.hit_rate, { pct: true })}，Top50 ${metricText(latestTop50.hit_rate, { pct: true })}，市场 ${metricText(latest.market_hit_rate, { pct: true })}。`
    : "最近预测验证暂无记录。";
  els.modelReference.append(
    el("div", { className: "model-reference-main" }, [
      el("span", { text: "Active Model" }),
      el("strong", { text: `${shortModelId(ref.model_id)} / ${ref.feature_set || "--"} / ${ref.label_set || "--"}` }),
      el("p", { text: ref.objective_note || "模型只作为候选召回参考。" }),
    ]),
    el("div", { className: "model-reference-metrics" }, [
      el("div", {}, [el("span", { text: "验证 F1" }), el("strong", { text: metricText(validation.f1, { pct: true }) })]),
      el("div", {}, [el("span", { text: "Accuracy" }), el("strong", { text: metricText(validation.accuracy, { pct: true }) })]),
      el("div", {}, [el("span", { text: "LogLoss" }), el("strong", { text: metricText(validation.log_loss, { digits: 4 }) })]),
      el("div", {}, [el("span", { text: "验证 Top50" }), el("strong", { text: metricText(top50.hit_rate, { pct: true }) })]),
      el("div", {}, [el("span", { text: "市场基准" }), el("strong", { text: metricText(ranking.market_hit_rate, { pct: true }) })]),
      el("div", {}, [el("span", { text: "样本/验证" }), el("strong", { text: `${text(ref.sample_count)} / ${text(ref.validation_sample_count)}` })]),
      el("div", {}, [el("span", { text: "拟合差" }), el("strong", { text: metricText(fit.log_loss_gap, { digits: 4 }) })]),
      el("div", {}, [el("span", { text: "最近 Top50" }), el("strong", { text: metricText(latestTop50.hit_rate, { pct: true }) })]),
    ]),
    el("p", { className: "model-reference-note", text: `${latestText} ${fit.note || ""}` }),
  );
}

function renderCandidates() {
  const allRows = rowBucket(state.activeBucket);
  const rows = allRows.slice(0, state.candidateVisible);
  if (!state.rows.length) setText("candidateInfo", "等待行情");
  else if (state.recommendationStatus === "loading") setText("candidateInfo", `计算中 / ${state.rows.length} 条`);
  else if (state.activeBucket === "mlLate" && state.mlLateSessionStatus === "loading") setText("candidateInfo", "模型尾盘计算中");
  else if (state.activeBucket === "mlLate" && state.mlLateSessionStatus === "error") setText("candidateInfo", "模型尾盘失败");
  else if (state.activeBucket === "late" && state.lateSessionStatus === "loading") setText("candidateInfo", "尾盘计算中");
  else if (state.activeBucket === "late" && state.lateSessionStatus === "error") setText("candidateInfo", "尾盘失败");
  else if (state.recommendationStatus === "error") setText("candidateInfo", "推荐失败");
  else setText("candidateInfo", `${rows.length}/${allRows.length} 只`);

  renderOverviewCandidates(allRows);
  renderModelReference();
  clearNode(els.candidateList);
  if (!rows.length) {
    els.candidateList.appendChild(emptyNode(emptyCandidateMessage()));
    return;
  }

  const fragment = document.createDocumentFragment();
  rows.forEach((row) => {
    fragment.appendChild(candidateButton(row));
  });
  els.candidateList.appendChild(fragment);
  iconRefresh();

  if (state.candidateVisible < allRows.length) {
    els.candidateList.appendChild(emptyNode("继续向下滚动加载更多", "loading-card"));
  }
}

function industryButton(row, { compact = false } = {}) {
  const item = el("button", { className: compact ? "compact-row industry-compact-row" : "industry-row", type: "button" });
  item.append(
    el("div", { className: "industry-main" }, [
      el("strong", { text: row.industry || "未分类" }),
      el("em", { className: quoteClass(row.avg_pct_chg), text: formatPct(row.avg_pct_chg) }),
    ]),
    el("p", { text: `上涨 ${row.up_count || 0}/${row.count || 0} / 龙头 ${row.top_stock?.name || row.top_stock?.ts_code || "--"}` }),
  );
  item.addEventListener("click", () => {
    const match =
      state.recommendations.find((stock) => stock.industry === row.industry) ||
      state.rows.find((stock) => stock.industry === row.industry);
    if (match) selectStock(match);
  });
  return item;
}

function renderOverviewIndustryTrends(rows) {
  if (!els.overviewIndustryList) return;
  clearNode(els.overviewIndustryList);
  const previewRows = rows.slice(0, OVERVIEW_PREVIEW_SIZE);
  if (!previewRows.length) {
    els.overviewIndustryList.appendChild(emptyNode("暂无行业趋势"));
    return;
  }
  const fragment = document.createDocumentFragment();
  previewRows.forEach((row) => fragment.appendChild(industryButton(row, { compact: true })));
  els.overviewIndustryList.appendChild(fragment);
}

function renderIndustryTrends() {
  const rows = state.industryTrends || [];
  setText("industryInfo", rows.length ? `${rows.length} 个行业` : "暂无行业");
  renderOverviewIndustryTrends(rows);
  clearNode(els.industryList);
  if (!rows.length) {
    els.industryList.appendChild(emptyNode("暂无行业趋势"));
    return;
  }
  const fragment = document.createDocumentFragment();
  rows.forEach((row) => {
    fragment.appendChild(industryButton(row));
  });
  els.industryList.appendChild(fragment);
}

function evaluateStock(row) {
  if (!row) {
    return {
      badge: "--",
      title: "先选择一只股票",
      reason: "从左侧候选池点一只股票，右侧会显示计划、资金和消息来源。",
      warning: "新手先看结论，再看理由，不要同时追太多股票。",
      entry: "--",
      stop: "--",
      target: "--",
      position: "--",
    };
  }
  const pct = numberValue(row.pct_chg) ?? 0;
  const close = numberValue(row.close) ?? 0;
  const low = numberValue(row.low) ?? close;
  const high = numberValue(row.high) ?? close;
  const market = marketDecision(state.summary);
  const hot = pct >= 7;
  const weak = pct <= -4;
  const entryLow = close ? close * (hot ? 0.975 : 0.985) : null;
  const stop = low ? low * 0.985 : null;
  const target = high ? high * 1.018 : null;
  if (market.mode === "defend" || weak) {
    return {
      badge: "先观察",
      title: "不急着买",
      reason: weak ? "个股当日偏弱，先看能否止跌。" : "市场整体偏弱，优先保留现金和观察名单。",
      warning: "没有确认信号就不要为了交易而交易。",
      entry: close ? `${formatNumber(entryLow, 2)} 附近再看` : "--",
      stop: stop ? formatNumber(stop, 2) : "--",
      target: target ? formatNumber(target, 2) : "--",
      position: "0-1成",
    };
  }
  if (hot) {
    return {
      badge: "等回踩",
      title: "强势但别追高",
      reason: "涨幅较大，适合等分时回踩或次日承接确认。",
      warning: "追高最容易把计划变成情绪交易。",
      entry: entryLow ? `${formatNumber(entryLow, 2)} 附近` : "--",
      stop: stop ? formatNumber(stop, 2) : "--",
      target: target ? formatNumber(target, 2) : "--",
      position: "1-2成",
    };
  }
  return {
    badge: "观察买入",
    title: "可以列入计划",
    reason: "涨跌幅没有过热，适合结合资金和行业强度继续确认。",
    warning: "只在买点出现时执行，跌破放弃线就撤。",
    entry: entryLow ? `${formatNumber(entryLow, 2)}-${formatNumber(close, 2)}` : "--",
    stop: stop ? formatNumber(stop, 2) : "--",
    target: target ? formatNumber(target, 2) : "--",
    position: "1成起",
  };
}

function renderSelected() {
  const row = state.selected;
  const idea = evaluateStock(row);
  setText("selectedCode", stockTitle(row));
  els.baiduSearchBtn.disabled = !row;
  els.candidateSearchBtn.disabled = !row;
  setText("selectedClose", row ? formatNumber(row.close, 2) : "--");
  setText("selectedPct", row ? formatPct(row.pct_chg) : "--");
  els.selectedPct.className = row ? quoteClass(row.pct_chg) : "";
  setText("selectedAmount", row ? formatThousandYuan(row.amount) : "--");
  setText("decisionBadge", idea.badge);
  setText("planTitle", idea.title);
  setText("planReason", idea.reason);
  setText("planWarning", idea.warning);
  setText("planEntry", idea.entry);
  setText("planStop", idea.stop);
  setText("planTarget", idea.target);
  setText("planPosition", idea.position);
}

function renderForecast(forecast) {
  if (!forecast) return;
  setText("planTitle", forecast.title || "明日观察");
  setText("planReason", forecast.summary || "等待更多数据确认。");
  setText("planWarning", forecast.avoid_signal || "不符合计划就放弃。");
  setText("planEntry", forecast.entry_zone || "--");
  setText("planStop", forecast.stop_price || "--");
  setText("planTarget", forecast.target_zone || "--");
  setText("planPosition", forecast.position || "--");
  setText("forecastMetric", forecast.direction ? `${forecast.direction} ${forecast.confidence ?? ""}` : "--");
  setBar(els.confidenceBar, forecast.confidence ?? 0);
}

function renderMoneyFlow(money) {
  if (!money) {
    setText("moneyFlowTitle", "等待资金数据");
    setText("moneyFlowStrength", "--");
    setText("moneyFlowSummary", "选择股票后显示主力资金方向。");
    ["mainMoneyNet", "extraLargeMoney", "largeMoney", "totalMoneyNet"].forEach((id) => setText(id, "--"));
    setBar(els.moneyStrengthBar, 0);
    return;
  }
  setText("moneyFlowTitle", money.level || "资金不明");
  setText("moneyFlowStrength", money.direction || "--");
  setText("moneyFlowSummary", money.readable || money.detail || "资金方向不明显。");
  setText("mainMoneyNet", signedMoneyWan(money.main_net));
  setText("extraLargeMoney", signedMoneyWan(money.extra_large_net));
  setText("largeMoney", signedMoneyWan(money.large_net));
  setText("totalMoneyNet", signedMoneyWan(money.net));
  setBar(els.moneyStrengthBar, money.strength_score ?? 0);
}

function renderAnalysis(payload) {
  if (!payload) {
    setText("recommendTitle", "等待推荐");
    setText("recommendReason", "先核验消息来源，再结合行情、趋势和资金判断。");
    setText("riskWarning", "等待消息核验。");
    setText("forecastMetric", "--");
    setText("trendMetric", "--");
    setText("supportMetric", "--");
    setText("resistanceMetric", "--");
    setBar(els.trendBar, 0);
    setBar(els.confidenceBar, 0);
    renderMoneyFlow(null);
    ["trend5Metric", "trend20Metric", "volumeMetric", "turnoverMetric", "peMetric", "pbMetric"].forEach((id) => setText(id, "--"));
    setText("analysisNotes", "选择股票后显示风险点。");
    clearNode(els.sourceList);
    setText("sourceInfo", "暂无来源");
    return;
  }
  const { trend, money, valuation, support_resistance: sr, risk, forecast } = payload;
  setText("recommendTitle", `${risk.level} / ${risk.action}`);
  setText("recommendReason", forecast?.summary || `${trend.level}，${money.level}，${valuation.level}`);
  setText("trendMetric", `${trend.level} ${trend.score}`);
  setText("supportMetric", sr.support ? `${formatNumber(sr.support, 2)} / ${formatSignedPct(-sr.support_gap_pct)}` : "--");
  setText("resistanceMetric", sr.resistance ? `${formatNumber(sr.resistance, 2)} / ${formatSignedPct(sr.resistance_gap_pct)}` : "--");
  setText("riskWarning", `风险 ${risk.score}：${risk.action}`);
  setBar(els.trendBar, trend.score ?? 0);
  renderForecast(forecast);
  renderMoneyFlow(money);
  setText("trend5Metric", formatSignedPct(trend.pct5));
  setText("trend20Metric", formatSignedPct(trend.pct20));
  setText("volumeMetric", trend.volume_ratio ? `${formatNumber(trend.volume_ratio, 2)} 倍` : "--");
  setText("turnoverMetric", valuation.turnover ? `${formatNumber(valuation.turnover, 2)}%` : "--");
  setText("peMetric", valuation.pe ? formatNumber(valuation.pe, 2) : "--");
  setText("pbMetric", valuation.pb ? formatNumber(valuation.pb, 2) : "--");
  const notes = [...(trend.reasons || []), ...(valuation.notes || [])];
  setText("analysisNotes", notes.length ? notes.join("；") : "暂无明显异常，继续结合盘面确认。");
}

async function loadAnalysis(tsCode) {
  const tradeDate = toTradeDate(els.tradeDate.value);
  setText("recommendTitle", "分析中");
  setText("recommendReason", "正在计算趋势、资金、估值和风险。");
  try {
    const response = await fetch(`/api/stock/${encodeURIComponent(tsCode)}/analysis?end_date=${tradeDate}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "分析数据加载失败");
    renderAnalysis(payload);
  } catch (error) {
    setText("recommendTitle", "分析失败");
    setText("recommendReason", error.message || "分析数据加载失败");
  }
}

function renderSources(sources) {
  const announcements = sources?.announcements || [];
  const cninfo = sources?.cninfo || [];
  const news = sources?.news || [];
  const errors = sources?.errors || [];
  const items = [
    ...announcements.map((item) => ({ ...item, type: "公告" })),
    ...cninfo.map((item) => ({ ...item, type: "巨潮" })),
    ...news.map((item) => ({ ...item, type: "新闻" })),
    ...errors.map((item) => ({ title: item, type: "提示" })),
  ].slice(0, 8);
  setText("sourceInfo", items.length ? `${items.length} 条来源` : "未取到来源");
  clearNode(els.sourceList);
  if (!items.length) {
    els.sourceList.appendChild(emptyNode("没有取到公告或新闻来源"));
    return;
  }
  const fragment = document.createDocumentFragment();
  items.forEach((item) => {
    const row = el(item.url ? "a" : "div", { className: "source-item", href: item.url });
    row.append(
      el("div", { className: "source-main" }, [
        el("strong", { className: "source-title", text: item.title || "--" }),
        el("span", { text: item.type }),
      ]),
      el("p", { text: item.meta || item.date || item.source || "" }),
    );
    fragment.appendChild(row);
  });
  els.sourceList.appendChild(fragment);
}

function renderRecommendation(payload) {
  renderSources(payload?.sources);
  const rec = payload?.recommendation;
  if (!rec) return;
  setText("recommendTitle", `${rec.action || "等待"} / ${rec.confidence ?? "--"}分`);
  setText("recommendReason", rec.verification || "消息来源不足，谨慎参考。");
  setBar(els.confidenceBar, rec.confidence ?? 0);
  const reasons = rec.reasons || [];
  const risks = rec.risks || [];
  const conditions = rec.conditions || [];
  setText("analysisNotes", [...reasons, ...risks, ...conditions].slice(0, 6).join("；") || "没有生成有效理由。");
}

async function loadRecommendation(tsCode) {
  const tradeDate = toTradeDate(els.tradeDate.value);
  setText("recommendTitle", "核验消息中");
  setText("recommendReason", "正在拉取公告、新闻，并调用模型做真实性检查。");
  try {
    const response = await fetch(`/api/stock/${encodeURIComponent(tsCode)}/recommendation?end_date=${tradeDate}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "推荐加载失败");
    renderRecommendation(payload);
  } catch (error) {
    setText("recommendTitle", "推荐失败");
    setText("recommendReason", error.message || "模型或消息源暂不可用");
  }
}

async function loadSelectedStock(tsCode) {
  await Promise.all([loadHistory(tsCode), loadAnalysis(tsCode), loadRecommendation(tsCode)]);
}

function validView(view) {
  return Object.prototype.hasOwnProperty.call(VIEW_META, view) ? view : "overview";
}

function setView(view, { updateHash = true } = {}) {
  const nextView = validView(view);
  state.activeView = nextView;
  const meta = VIEW_META[nextView];
  setText("viewEyebrow", meta.eyebrow);
  setText("viewTitle", meta.title);
  document.querySelectorAll(".side-nav .nav-item[data-view]").forEach((item) => {
    const isActive = item.dataset.view === nextView;
    item.classList.toggle("active", isActive);
    if (isActive && window.matchMedia("(max-width: 980px)").matches) {
      item.scrollIntoView({ block: "nearest", inline: "center" });
    }
  });
  document.querySelectorAll(".view[data-view-panel]").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.viewPanel === nextView);
  });
  const content = document.querySelector(".content");
  if (content) content.scrollTop = 0;
  window.scrollTo(0, 0);
  if (updateHash && window.location.hash !== `#${nextView}`) {
    window.history.replaceState(null, "", `#${nextView}`);
  }
  if (nextView === "stock") {
    window.requestAnimationFrame(renderKline);
  }
}

function movingAverage(rows, index, span) {
  if (index + 1 < span) return null;
  const slice = rows.slice(index + 1 - span, index + 1);
  const values = slice.map((row) => numberValue(row.close)).filter((value) => value !== null);
  return values.length === span ? values.reduce((sum, value) => sum + value, 0) / span : null;
}

function renderKline() {
  const canvas = els.klineChart;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const box = canvas.getBoundingClientRect();
  const dpr = Math.max(1, Math.min(window.devicePixelRatio || 1, 2.5));
  const cssWidth = Math.max(320, Math.floor(box.width || canvas.clientWidth || 760));
  const cssHeight = Math.max(220, Math.floor(box.height || canvas.clientHeight || 300));
  canvas.width = Math.floor(cssWidth * dpr);
  canvas.height = Math.floor(cssHeight * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssWidth, cssHeight);
  ctx.fillStyle = "#fbfcfb";
  ctx.fillRect(0, 0, cssWidth, cssHeight);

  const rows = state.history;
  if (!rows.length) {
    ctx.fillStyle = "#65736d";
    ctx.font = "14px Segoe UI, Arial";
    ctx.textAlign = "center";
    ctx.fillText("选择股票后显示走势", cssWidth / 2, cssHeight / 2);
    return;
  }

  const prices = rows.flatMap((row) => [numberValue(row.high), numberValue(row.low)]).filter((value) => value !== null);
  const vols = rows.map((row) => numberValue(row.vol) ?? 0);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const maxVol = Math.max(...vols, 1);
  const pad = { top: 22, right: 34, bottom: 34, left: 48 };
  const priceHeight = cssHeight * 0.65;
  const volTop = pad.top + priceHeight + 22;
  const volHeight = cssHeight - volTop - pad.bottom;
  const step = (cssWidth - pad.left - pad.right) / rows.length;
  const candleWidth = Math.max(4, Math.min(11, step * 0.58));
  const yPrice = (value) => pad.top + ((maxPrice - value) / Math.max(maxPrice - minPrice, 0.01)) * priceHeight;
  const yVol = (value) => volTop + volHeight - (value / maxVol) * volHeight;

  ctx.strokeStyle = "#dbe4df";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i += 1) {
    const y = Math.round(pad.top + (priceHeight / 4) * i) + 0.5;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(cssWidth - pad.right, y);
    ctx.stroke();
  }

  const maPoints = [];
  rows.forEach((row, index) => {
    const x = Math.round(pad.left + step * index + step / 2) + 0.5;
    const open = numberValue(row.open) ?? 0;
    const close = numberValue(row.close) ?? 0;
    const high = numberValue(row.high) ?? 0;
    const low = numberValue(row.low) ?? 0;
    const up = close >= open;
    ctx.strokeStyle = up ? "#bd3c43" : "#168158";
    ctx.fillStyle = up ? "#bd3c43" : "#168158";
    ctx.beginPath();
    ctx.moveTo(x, yPrice(high));
    ctx.lineTo(x, yPrice(low));
    ctx.stroke();
    const bodyTop = Math.round(yPrice(Math.max(open, close)));
    const bodyHeight = Math.max(2, Math.abs(yPrice(open) - yPrice(close)));
    ctx.fillRect(Math.round(x - candleWidth / 2), bodyTop, Math.max(2, Math.round(candleWidth)), bodyHeight);
    ctx.globalAlpha = 0.25;
    const volY = Math.round(yVol(numberValue(row.vol) ?? 0));
    ctx.fillRect(Math.round(x - candleWidth / 2), volY, Math.max(2, Math.round(candleWidth)), Math.round(volTop + volHeight - volY));
    ctx.globalAlpha = 1;
    const ma = movingAverage(rows, index, 5);
    if (ma !== null) maPoints.push([x, yPrice(ma)]);
  });

  ctx.strokeStyle = "#2d6f91";
  ctx.lineWidth = 1.8;
  ctx.beginPath();
  maPoints.forEach(([x, y], index) => {
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  ctx.fillStyle = "#65736d";
  ctx.font = "12px Segoe UI, Arial";
  ctx.textAlign = "right";
  ctx.fillText(formatNumber(maxPrice, 2), pad.left - 8, pad.top + 4);
  ctx.fillText(formatNumber(minPrice, 2), pad.left - 8, pad.top + priceHeight);
  ctx.textAlign = "center";
  ctx.fillText(rows[0]?.trade_date ?? "", pad.left + 38, cssHeight - 12);
  ctx.fillText(rows[rows.length - 1]?.trade_date ?? "", cssWidth - pad.right - 42, cssHeight - 12);
}

async function loadHistory(tsCode) {
  const tradeDate = toTradeDate(els.tradeDate.value);
  setText("historyInfo", `${tsCode} 走势加载中`);
  try {
    const response = await fetch(`/api/stock/${encodeURIComponent(tsCode)}/history?end_date=${tradeDate}&days=80`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "历史行情查询失败");
    state.history = payload.rows || [];
    setText("historyInfo", `${tsCode} / 最近 ${state.history.length} 个交易日`);
    renderKline();
  } catch (error) {
    state.history = [];
    setText("historyInfo", error.message || "历史行情查询失败");
    renderKline();
  }
}

async function selectStock(row) {
  state.selected = row;
  renderSelected();
  renderCandidates();
  setView("stock");
  await loadSelectedStock(row.ts_code);
}

function loadMoreCandidatesIfNeeded() {
  const elNode = els.candidateList;
  if (!elNode || elNode.scrollTop + elNode.clientHeight < elNode.scrollHeight - 60) return;
  const total = rowBucket(state.activeBucket).length;
  if (state.candidateVisible >= total) return;
  state.candidateVisible = Math.min(total, state.candidateVisible + CANDIDATE_PAGE_SIZE);
  renderCandidates();
}

function applyDailyPayload(payload, { fromCache = false } = {}) {
  state.rows = decorateRows(payload.rows || []);
  state.summary = payload.summary || {};
  state.tradeDate = payload.trade_date || "";
  state.dataSource = fromCache ? "browser" : payload.data_source || "";
  state.loadError = "";
  state.recommendationStatus = "idle";
  state.recommendationError = "";
  state.mlLateSessionStatus = "idle";
  state.mlLateSessionError = "";
  state.mlLateSessionRecommendations = [];
  state.lateSessionStatus = "idle";
  state.lateSessionError = "";
  state.lateSessionRecommendations = [];
  state.modelReference = null;
  if (payload.trade_date) els.tradeDate.value = fromTradeDate(payload.trade_date);
  resetVisibleCounts();
  state.recommendations = decorateRows(payload.recommendations || []);
  const selectedStillExists = state.rows.find((row) => row.ts_code === state.selected?.ts_code);
  state.selected = state.recommendations[0] || selectedStillExists || state.rows[0] || null;
  updateMarket();
  renderCandidates();
  renderSelected();
  renderKline();
  if (state.selected && !fromCache) loadSelectedStock(state.selected.ts_code);
  if (payload.trade_date && !fromCache) loadMlLateSessionRecommendations(payload.trade_date);
  if (payload.trade_date && !fromCache) loadRecommendations(payload.trade_date);
  if (payload.trade_date && !fromCache) loadIndustryTrends(payload.trade_date);
  if (fromCache) showToast("先显示上次数据，正在后台刷新");
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
    if (state.recommendations.length) {
      const selectedCode = state.selected?.ts_code;
      state.selected = state.recommendations.find((row) => row.ts_code === selectedCode) || state.recommendations[0];
      if (!["late", "mlLate"].includes(state.activeBucket)) state.activeBucket = "priority";
      updateBucketButtons();
      renderSelected();
      await loadSelectedStock(state.selected.ts_code);
    }
    renderCandidates();
  } catch (error) {
    state.recommendationStatus = "error";
    state.recommendationError = error.message || "推荐池计算失败";
    renderCandidates();
  }
}

async function loadMlLateSessionRecommendations(tradeDate) {
  if (!tradeDate) return;
  state.mlLateSessionStatus = "loading";
  state.mlLateSessionError = "";
  renderCandidates();
  try {
    const response = await fetch(`/api/recommendations/ml-late-session?trade_date=${tradeDate}&limit=20&prediction_limit=500`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "模型尾盘候选计算失败");
    if (payload.data_source) state.dataSource = payload.data_source;
    state.modelReference = payload.summary?.model_reference || null;
    state.mlLateSessionRecommendations = decorateRows(payload.rows || []);
    state.mlLateSessionStatus = "done";
    if (state.activeBucket === "mlLate" && state.mlLateSessionRecommendations.length) {
      const selectedCode = state.selected?.ts_code;
      state.selected =
        state.mlLateSessionRecommendations.find((row) => row.ts_code === selectedCode) ||
        state.mlLateSessionRecommendations[0];
      renderSelected();
      await loadSelectedStock(state.selected.ts_code);
    }
    renderCandidates();
  } catch (error) {
    state.mlLateSessionStatus = "error";
    state.mlLateSessionError = error.message || "模型尾盘候选计算失败";
    renderCandidates();
  }
}

async function loadLateSessionRecommendations(tradeDate) {
  if (!tradeDate) return;
  state.lateSessionStatus = "loading";
  state.lateSessionError = "";
  renderCandidates();
  try {
    const response = await fetch(`/api/recommendations/late-session?trade_date=${tradeDate}&limit=20`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "尾盘候选计算失败");
    if (payload.data_source) state.dataSource = payload.data_source;
    state.lateSessionRecommendations = decorateRows(payload.rows || []);
    state.lateSessionStatus = "done";
    if (state.activeBucket === "late" && state.lateSessionRecommendations.length) {
      const selectedCode = state.selected?.ts_code;
      state.selected =
        state.lateSessionRecommendations.find((row) => row.ts_code === selectedCode) ||
        state.lateSessionRecommendations[0];
      renderSelected();
      await loadSelectedStock(state.selected.ts_code);
    }
    renderCandidates();
  } catch (error) {
    state.lateSessionStatus = "error";
    state.lateSessionError = error.message || "尾盘候选计算失败";
    renderCandidates();
  }
}

async function loadIndustryTrends(tradeDate) {
  setText("industryInfo", "加载中");
  renderOverviewIndustryTrends([]);
  try {
    const response = await fetch(`/api/industry-trends?trade_date=${tradeDate}&limit=16`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "行业趋势加载失败");
    if (payload.data_source) state.dataSource = payload.data_source;
    state.industryTrends = payload.rows || [];
    renderIndustryTrends();
  } catch (error) {
    setText("industryInfo", error.message || "行业趋势加载失败");
    renderOverviewIndustryTrends([]);
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
    // Stock names are nice to have; market data should remain usable without them.
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
      showToast(`已切换到有数据的交易日 ${displayTradeDate(payload.trade_date)}`);
    }
    applyDailyPayload(payload);
    if (!payload.fallback_used) showToast(`已加载 ${state.rows.length} 条行情 / ${dataSourceText(payload.data_source)}`);
    if (payload.data_source === "online") loadStockBasicInBackground();
  } catch (error) {
    if (hadCache) {
      showToast("刷新较慢，继续显示上次数据");
      return;
    }
    state.loadError =
      error.name === "AbortError" ? "行情接口响应较慢，请稍后刷新。" : error.message || "行情接口暂不可用，请稍后刷新。";
    state.rows = [];
    state.summary = {};
    state.selected = null;
    state.history = [];
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

function openDataModal() {
  els.dataModal.hidden = false;
  els.modalTsCode.value = state.selected?.ts_code || "";
  els.modalTradeDate.value = els.tradeDate.value || "";
  els.modalStartDate.value = "";
  els.modalEndDate.value = "";
  renderInterfaceTabs();
  iconRefresh();
}

function closeDataModal() {
  els.dataModal.hidden = true;
}

function openBacktestModal() {
  els.backtestModal.hidden = false;
  els.backtestEndDate.value = els.tradeDate.value || "";
  if (!state.backtest) renderBacktestEmpty();
  iconRefresh();
}

function closeBacktestModal() {
  els.backtestModal.hidden = true;
}

function renderInterfaceTabs() {
  document.querySelectorAll("[data-interface]").forEach((button) => {
    button.classList.toggle("active", button.dataset.interface === state.activeInterface);
  });
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

function renderModalTable(payload) {
  const columns = payload.columns || [];
  const rows = payload.rows || [];
  clearNode(els.modalTableHead);
  clearNode(els.modalTableBody);
  const tr = document.createElement("tr");
  columns.forEach((column) => {
    tr.appendChild(el("th", { text: MODAL_COLUMNS[column] || column }));
  });
  els.modalTableHead.appendChild(tr);
  if (!rows.length) {
    const row = document.createElement("tr");
    const cell = el("td", { className: "empty", text: "没有查到数据" });
    cell.colSpan = Math.max(columns.length, 1);
    row.appendChild(cell);
    els.modalTableBody.appendChild(row);
    return;
  }
  const fragment = document.createDocumentFragment();
  rows.forEach((rowData) => {
    const row = document.createElement("tr");
    columns.forEach((column) => {
      const cell = el("td", { text: modalValue(column, rowData[column]) });
      if (column === "pct_chg" || column === "net_mf_amount") cell.className = quoteClass(rowData[column]);
      row.appendChild(cell);
    });
    fragment.appendChild(row);
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
  setText("modalStatus", `${INTERFACE_NAMES[state.activeInterface]}查询中`);
  els.modalQueryBtn.disabled = true;
  try {
    const response = await fetch(`/api/query/${state.activeInterface}?${params.toString()}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "查询失败");
    renderModalTable(payload);
    setText("modalStatus", `显示 ${payload.count} 条`);
  } catch (error) {
    clearNode(els.modalTableHead);
    clearNode(els.modalTableBody);
    setText("modalStatus", error.message || "查询失败");
  } finally {
    els.modalQueryBtn.disabled = false;
  }
}

function renderBacktestEmpty(message = "点击开始推演后显示结果") {
  setText("backtestTitle", "等待推演");
  setText("backtestText", message);
  clearNode(els.backtestRules);
  setText("backtestMeta", "未运行");
  clearNode(els.backtestTableBody);
  const row = document.createElement("tr");
  const cell = el("td", { className: "empty", text: "暂无策略结果" });
  cell.colSpan = 7;
  row.appendChild(cell);
  els.backtestTableBody.appendChild(row);
  setText("backtestExampleInfo", "暂无");
  clearNode(els.backtestExamples);
  els.backtestExamples.appendChild(emptyNode("暂无次日验证样本"));
}

function renderBacktest(payload) {
  state.backtest = payload;
  const suggestion = payload.suggestion || {};
  setText("backtestTitle", suggestion.title || "推演完成");
  setText("backtestText", suggestion.text || "已完成策略对比。");
  clearNode(els.backtestRules);
  (suggestion.rules || []).forEach((rule) => {
    els.backtestRules.appendChild(el("p", { text: rule }));
  });
  setText("backtestMeta", `${payload.tested_days || 0} 个交易日 / 验证至 ${payload.validated_until || payload.end_date || "--"}`);
  clearNode(els.backtestTableBody);
  const results = payload.results || [];
  if (!results.length) {
    const row = document.createElement("tr");
    const cell = el("td", { className: "empty", text: "样本不足，无法推演" });
    cell.colSpan = 7;
    row.appendChild(cell);
    els.backtestTableBody.appendChild(row);
    clearNode(els.backtestExamples);
    els.backtestExamples.appendChild(emptyNode("暂无次日验证样本"));
    return;
  }
  const fragment = document.createDocumentFragment();
  results.forEach((result, index) => {
    const row = document.createElement("tr");
    if (index === 0) row.className = "selected";
    [
      `${result.name || "--"} ${result.quality_label || ""}`,
      result.signal_count,
      formatPct(result.win_rate),
      formatSignedPct(result.avg_next_close_pct),
      formatSignedPct(result.avg_next_high_pct),
      formatPct(result.stop_hit_rate),
      formatNumber(result.quality_score, 1),
    ].forEach((value, cellIndex) => {
      const cell = el("td", { text: value });
      if ([3, 4].includes(cellIndex)) cell.className = quoteClass(value);
      row.appendChild(cell);
    });
    fragment.appendChild(row);
  });
  els.backtestTableBody.appendChild(fragment);

  const best = results[0];
  const examples = best?.examples || [];
  setText("backtestExampleInfo", examples.length ? `${best.name} / ${examples.length} 条` : "暂无");
  clearNode(els.backtestExamples);
  if (!examples.length) {
    els.backtestExamples.appendChild(emptyNode("最佳策略暂无样本"));
    return;
  }
  const cardFragment = document.createDocumentFragment();
  examples.forEach((row) => {
    const card = el("button", { className: "backtest-example", type: "button" });
    card.append(
      el("div", { className: "example-main" }, [
        el("strong", { text: candidateName(row) }),
        el("span", { className: quoteClass(row.pct_chg), text: formatPct(row.pct_chg) }),
      ]),
      el("p", { text: `${row.ts_code} / ${row.trade_date}` }),
      el("p", { text: conditionText(row) || stockSubTitle(row) }),
      el("p", { text: nextDayText(row) }),
    );
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
  setText("backtestTitle", "正在推演");
  setText("backtestText", "正在读取历史因子并验证次日表现，首次运行可能较慢。");
  setText("backtestMeta", "运行中");
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
    setText("backtestTitle", "推演失败");
    setText("backtestText", error.message || "历史推演暂时不可用");
    setText("backtestMeta", "失败");
    clearNode(els.backtestTableBody);
    const row = document.createElement("tr");
    const cell = el("td", { className: "empty", text: "推演失败" });
    cell.colSpan = 7;
    row.appendChild(cell);
    els.backtestTableBody.appendChild(row);
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

function updateBucketButtons() {
  document.querySelectorAll("[data-bucket]").forEach((button) => {
    button.classList.toggle("active", button.dataset.bucket === state.activeBucket);
  });
}

function bindViewNav() {
  document.querySelectorAll(".side-nav .nav-item[data-view]").forEach((item) => {
    item.addEventListener("click", (event) => {
      event.preventDefault();
      setView(item.dataset.view);
    });
  });
  document.querySelectorAll("[data-view-jump]").forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.viewJump));
  });
  window.addEventListener("hashchange", () => {
    const nextView = window.location.hash.replace("#", "");
    if (nextView) setView(nextView, { updateHash: false });
  });
}

function bind() {
  [
    "viewEyebrow",
    "viewTitle",
    "headerSubtitle",
    "tradeDate",
    "queryBtn",
    "exportBtn",
    "dataModalBtn",
    "backtestModalBtn",
    "toolDataBtn",
    "toolBacktestBtn",
    "toolExportBtn",
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
    "candidateSearchBtn",
    "modelReference",
    "overviewCandidateList",
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
    "baiduSearchBtn",
    "addSelectedBtn",
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
    "overviewIndustryList",
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
  els.baiduSearchBtn.addEventListener("click", () => openBaiduSearch(state.selected));
  els.candidateSearchBtn.addEventListener("click", () => openBaiduSearch(state.selected));
  els.addSelectedBtn.addEventListener("click", addSelectedToWatchlist);
  els.dataModalBtn.addEventListener("click", openDataModal);
  els.backtestModalBtn.addEventListener("click", openBacktestModal);
  if (els.toolDataBtn) els.toolDataBtn.addEventListener("click", openDataModal);
  if (els.toolBacktestBtn) els.toolBacktestBtn.addEventListener("click", openBacktestModal);
  if (els.toolExportBtn) els.toolExportBtn.addEventListener("click", exportCsv);
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
      setText("modalStatus", `已切换到${INTERFACE_NAMES[state.activeInterface]}`);
    });
  });
  els.candidateList.addEventListener("scroll", loadMoreCandidatesIfNeeded);
  document.querySelectorAll("[data-bucket]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeBucket = button.dataset.bucket;
      state.candidateVisible = CANDIDATE_PAGE_SIZE;
      els.candidateList.scrollTop = 0;
      updateBucketButtons();
      if (state.activeBucket === "mlLate" && state.mlLateSessionStatus !== "done") {
        loadMlLateSessionRecommendations(state.tradeDate);
      }
      if (state.activeBucket === "late" && state.lateSessionStatus !== "done") {
        loadLateSessionRecommendations(state.tradeDate);
      }
      renderCandidates();
    });
  });
  bindViewNav();
}

window.addEventListener("DOMContentLoaded", async () => {
  bind();
  bindDatePickers();
  iconRefresh();
  const initialView = validView(window.location.hash.replace("#", ""));
  setView(initialView, { updateHash: Boolean(window.location.hash) });
  if (!els.tradeDate.value) {
    const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000);
    els.tradeDate.value = yesterday.toISOString().slice(0, 10);
  }
  updateMarket();
  renderCandidates();
  renderIndustryTrends();
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
