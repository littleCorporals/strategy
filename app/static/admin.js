const state = {
  overview: null,
  diagnostics: null,
  loading: false,
  modelPage: 1,
  modelPageSize: 6,
  trainingTab: "single",
  operation: null,
};

const $ = (id) => document.getElementById(id);

function text(value, fallback = "-") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return String(value);
}

function shortId(value) {
  const raw = text(value);
  return raw.length > 24 ? `${raw.slice(0, 13)}...${raw.slice(-6)}` : raw;
}

function badge(status) {
  const value = text(status, "unknown");
  const labels = {
    candidate: "待审核",
    approved: "已通过",
    rejected: "已拒绝",
    active: "使用中",
    inactive: "已下线",
    archived: "已归档",
    queued: "待训练",
    running: "训练中",
    completed: "已完成",
    failed: "失败",
    planned: "计划中",
  };
  return `<span class="badge ${value}">${labels[value] || value}</span>`;
}

function escapeHtml(value) {
  return text(value, "").replace(/[&<>"']/g, (char) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[char] || char;
  });
}

function showToast(message, duration = 2200) {
  const toast = $("toast");
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), duration);
}

function operationStatusLayer() {
  let layer = document.querySelector(".operation-status");
  if (!layer) {
    layer = document.createElement("div");
    layer.className = "operation-status";
    layer.setAttribute("role", "status");
    layer.setAttribute("aria-live", "polite");
    layer.innerHTML = `
      <div class="operation-status-head">
        <strong data-operation-title></strong>
        <span data-operation-percent></span>
      </div>
      <div class="operation-status-message" data-operation-message></div>
      <div class="operation-progress" aria-hidden="true">
        <div data-operation-progress></div>
      </div>
      <div class="operation-status-meta" data-operation-meta></div>
    `;
    document.body.appendChild(layer);
  }
  return layer;
}

function formatElapsed(ms) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function renderOperationStatus() {
  const operation = state.operation;
  const layer = operationStatusLayer();
  if (!operation) {
    return;
  }
  const elapsedMs = Date.now() - operation.startedAt;
  let progress = operation.progress;
  if (operation.estimateSeconds) {
    progress = Math.min(95, Math.max(progress || 6, (elapsedMs / (operation.estimateSeconds * 1000)) * 90));
  }
  const percent = operation.complete ? 100 : Math.round(progress || 0);
  layer.querySelector("[data-operation-title]").textContent = operation.title || "正在处理";
  layer.querySelector("[data-operation-percent]").textContent = operation.indeterminate ? "进行中" : `${percent}%`;
  layer.querySelector("[data-operation-message]").textContent = operation.message || "";
  layer.querySelector("[data-operation-meta]").textContent = `${operation.detail ? `${operation.detail} · ` : ""}已等待 ${formatElapsed(elapsedMs)} · 预计进度仅供参考，完成后会自动刷新`;
  layer.querySelector("[data-operation-progress]").style.width = operation.indeterminate ? "38%" : `${percent}%`;
  layer.classList.toggle("indeterminate", Boolean(operation.indeterminate));
  layer.classList.add("show");
}

function showOperationStatus(message, options = {}) {
  const layer = operationStatusLayer();
  window.clearInterval(state.operation?.timer);
  state.operation = {
    title: options.title || "正在处理",
    message,
    detail: options.detail || "",
    estimateSeconds: Number(options.estimateSeconds || 0),
    progress: Number(options.progress || 0),
    indeterminate: Boolean(options.indeterminate),
    complete: false,
    startedAt: Date.now(),
    timer: null,
  };
  renderOperationStatus();
  state.operation.timer = window.setInterval(renderOperationStatus, 1000);
  layer.classList.add("show");
}

function updateOperationStatus(message, options = {}) {
  if (!state.operation) {
    showOperationStatus(message, options);
    return;
  }
  state.operation.message = message || state.operation.message;
  state.operation.title = options.title || state.operation.title;
  state.operation.detail = options.detail || state.operation.detail;
  if (options.estimateSeconds !== undefined) {
    state.operation.estimateSeconds = Number(options.estimateSeconds || 0);
  }
  if (options.progress !== undefined) {
    state.operation.progress = Number(options.progress || 0);
  }
  if (options.indeterminate !== undefined) {
    state.operation.indeterminate = Boolean(options.indeterminate);
  }
  renderOperationStatus();
}

function completeOperationStatus(message) {
  if (!state.operation) {
    return;
  }
  state.operation.message = message || state.operation.message;
  state.operation.progress = 100;
  state.operation.complete = true;
  state.operation.indeterminate = false;
  window.clearInterval(state.operation.timer);
  state.operation.timer = null;
  renderOperationStatus();
}

function hideOperationStatus() {
  const layer = document.querySelector(".operation-status");
  window.clearInterval(state.operation?.timer);
  state.operation = null;
  if (layer) {
    layer.classList.remove("show");
    layer.classList.remove("indeterminate");
  }
}

function busyButtons(ids, label) {
  const buttons = ids.map((id) => $(id)).filter(Boolean);
  buttons.forEach((button) => {
    if (!button.dataset.originalText) {
      button.dataset.originalText = button.textContent;
    }
    button.textContent = label;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
  });
  return buttons;
}

function restoreButtons(buttons) {
  buttons.forEach((button) => {
    button.textContent = button.dataset.originalText || button.textContent;
    delete button.dataset.originalText;
    button.disabled = false;
    button.removeAttribute("aria-busy");
  });
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

function normalizeHelpTips(root = document) {
  root.querySelectorAll(".help-tip").forEach((tip) => {
    const value =
      tip.dataset.tooltip ||
      tip.getAttribute("title") ||
      tip.querySelector(".help-popover")?.textContent?.trim() ||
      tip.getAttribute("aria-label") ||
      "";
    if (value) {
      tip.dataset.tooltip = value;
      tip.setAttribute("aria-label", value);
    }
    tip.removeAttribute("title");
  });
}

function tooltipLayer() {
  let layer = document.querySelector(".help-tooltip-layer");
  if (!layer) {
    layer = document.createElement("div");
    layer.className = "help-tooltip-layer";
    layer.setAttribute("role", "tooltip");
    document.body.appendChild(layer);
  }
  return layer;
}

function showHelpTooltip(target) {
  normalizeHelpTips(target.parentElement || document);
  const value = target.dataset.tooltip || "";
  if (!value) {
    return;
  }
  const layer = tooltipLayer();
  layer.textContent = value;
  layer.classList.remove("below", "show");
  layer.style.left = "0px";
  layer.style.top = "0px";
  layer.style.visibility = "hidden";
  layer.classList.add("show");

  const margin = 12;
  const gap = 9;
  const targetRect = target.getBoundingClientRect();
  const layerRect = layer.getBoundingClientRect();
  const maxLeft = Math.max(margin, window.innerWidth - layerRect.width - margin);
  const left = Math.min(maxLeft, Math.max(margin, targetRect.left + targetRect.width / 2 - layerRect.width / 2));
  let top = targetRect.top - layerRect.height - gap;
  if (top < margin) {
    top = targetRect.bottom + gap;
    layer.classList.add("below");
  }

  layer.style.left = `${Math.round(left)}px`;
  layer.style.top = `${Math.round(top)}px`;
  layer.style.visibility = "visible";
}

function hideHelpTooltip() {
  const layer = document.querySelector(".help-tooltip-layer");
  if (layer) {
    layer.classList.remove("show", "below");
    layer.style.visibility = "hidden";
  }
}

function bindHelpTooltips() {
  normalizeHelpTips();
  document.addEventListener("pointerover", (event) => {
    const target = event.target.closest(".help-tip");
    if (target) {
      showHelpTooltip(target);
    }
  });
  document.addEventListener("pointerout", (event) => {
    const target = event.target.closest(".help-tip");
    if (target && !target.contains(event.relatedTarget)) {
      hideHelpTooltip();
    }
  });
  document.addEventListener("focusin", (event) => {
    const target = event.target.closest(".help-tip");
    if (target) {
      showHelpTooltip(target);
    }
  });
  document.addEventListener("focusout", (event) => {
    if (event.target.closest(".help-tip")) {
      hideHelpTooltip();
    }
  });
  window.addEventListener("resize", hideHelpTooltip);
  document.addEventListener("scroll", hideHelpTooltip, true);
}

function fromTradeDate(value) {
  const raw = text(value, "").replaceAll("-", "");
  if (!/^\d{8}$/.test(raw)) {
    return "";
  }
  return `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`;
}

function toTradeDate(value) {
  return text(value, "").replaceAll("-", "");
}

function parseTradeDate(value) {
  const raw = text(value, "").replaceAll("-", "");
  if (!/^\d{8}$/.test(raw)) {
    return null;
  }
  const date = new Date(Number(raw.slice(0, 4)), Number(raw.slice(4, 6)) - 1, Number(raw.slice(6, 8)));
  return Number.isNaN(date.getTime()) ? null : date;
}

function weekdayCount(startValue, endValue) {
  const start = parseTradeDate(startValue);
  const end = parseTradeDate(endValue);
  if (!start || !end || start > end) {
    return 0;
  }
  let count = 0;
  const current = new Date(start.getTime());
  while (current <= end) {
    const day = current.getDay();
    if (day !== 0 && day !== 6) {
      count += 1;
    }
    current.setDate(current.getDate() + 1);
  }
  return count;
}

function emptyRow(message, columns) {
  return `<tr><td colspan="${columns}"><div class="empty">${message}</div></td></tr>`;
}

const HELP_TEXT = {
  task: "本次训练任务编号。鼠标停在编号上可以看完整 run_id。",
  status: "训练任务当前状态：待训练、训练中、已完成或失败。",
  featureLabel: "特征集决定输入模型的字段；标签集决定模型要预测的目标。",
  samples: "总样本是参与训练和验证的样本数量；验证样本是时间切分后留出来评估模型的数据。",
  validationF1: "F1 同时考虑精确率和召回率，越高说明验证集上的正例识别越均衡。",
  logLoss: "Log Loss 衡量概率预测质量，越低越好；它比单纯命中率更关注概率是否靠谱。",
  top50: "按模型分数排序前 50 只股票的标签命中率，候选池场景优先看这个指标。",
  top50Lift: "Top50 命中率减去全市场基准命中率，正数越大说明排序越有用。",
  params: "训练超参数，例如验证集比例、学习率、L2 正则、最大迭代轮次和早停耐心。",
  accuracy: "验证集里预测对的比例。样本正负不均衡时不能只看它。",
  precision: "模型判断为正例的样本里，真实命中的比例。",
  recall: "真实正例里，被模型找出来的比例。",
  trainSamples: "从缓存历史行情构造出的监督学习样本数量。",
  featureCount: "当前模型实际使用的特征字段数量。",
  marketBase: "同一验证区间里，全市场不排序直接观察的平均命中率。",
  iterations: "训练实际执行的迭代轮次。",
  bestIteration: "验证集 Log Loss 最优时对应的训练轮次。",
  nonZeroWeights: "权重不为 0 的特征数量，反映模型实际使用了多少特征。",
  positiveRate: "验证集里标签为 1 的样本比例，用来判断正负样本是否均衡。",
  validationRatio: "从时间序列尾部切出来做验证集的比例。",
  learningRate: "每轮参数更新步长，太大容易震荡，太小训练慢。",
  l2: "L2 正则强度，用来限制权重过大，降低过拟合风险。",
  maxIter: "训练最多迭代多少轮。",
  patience: "验证集长期不改善时提前停止训练的等待轮数。",
};

function helpTip(key, fallback = "") {
  const value = HELP_TEXT[key] || fallback;
  if (!value) {
    return "";
  }
  return `
    <span class="help-tip" tabindex="0" data-tooltip="${escapeHtml(value)}" aria-label="${escapeHtml(value)}">
      ?
      <span class="help-popover" role="tooltip">${escapeHtml(value)}</span>
    </span>
  `;
}

function helpLabel(label, key, fallback = "") {
  return `<span class="help-label">${escapeHtml(label)}${helpTip(key, fallback)}</span>`;
}

function modelActions(item) {
  const id = escapeHtml(item.model_id);
  const actions = [];
  if (item.status === "candidate") {
    actions.push(`<button type="button" data-model-action="approve" data-model-id="${id}">通过</button>`);
    actions.push(`<button type="button" data-model-action="reject" data-model-id="${id}">拒绝</button>`);
  }
  if (["approved", "inactive"].includes(item.status)) {
    actions.push(`<button type="button" data-model-action="activate" data-model-id="${id}">上线</button>`);
  }
  if (item.status === "active") {
    actions.push(`<button type="button" data-model-action="deactivate" data-model-id="${id}">下线</button>`);
  }
  if (item.status !== "archived") {
    actions.push(`<button type="button" data-model-action="archive" data-model-id="${id}">归档</button>`);
  }
  return `<div class="row-actions">${actions.join("")}</div>`;
}

function renderModels(models) {
  const body = $("modelsBody");
  if (!models.length) {
    body.innerHTML = emptyRow("暂无其它模型版本。训练候选模型后会显示在这里。", 4);
    renderModelPagination(0, 0, 0, 1);
    return;
  }
  const totalPages = Math.max(1, Math.ceil(models.length / state.modelPageSize));
  state.modelPage = Math.min(Math.max(1, state.modelPage), totalPages);
  const start = (state.modelPage - 1) * state.modelPageSize;
  const pageItems = models.slice(start, start + state.modelPageSize);
  body.innerHTML = pageItems
    .map((item) => {
      const summary = metricSummary(item.metrics || {});
      const feature = featureDefinition(item.feature_set);
      const label = labelDefinition(item.label_set);
      return `
        <tr class="model-version-card">
          <td class="model-cell-main" title="${escapeHtml(item.model_id)}">
            <span class="model-card-kicker">模型版本</span>
            <strong class="model-row-title">${escapeHtml(item.name || item.model_id)}</strong>
            <small class="model-row-id">${escapeHtml(shortId(item.model_id))}</small>
            <div class="model-sample-strip">
              <span><b>总样本</b>${escapeHtml(text(summary.sampleCount))}</span>
              <span><b>验证</b>${escapeHtml(text(summary.validationSampleCount))}</span>
            </div>
          </td>
          <td class="model-cell-definition">
            <div class="model-definition-pair">
              <strong>${escapeHtml(item.feature_set)}</strong>
              <small>${escapeHtml(feature?.description || "未配置特征集说明")}</small>
            </div>
            <div class="model-definition-pair">
              <strong>${escapeHtml(item.label_set)}</strong>
              <small>${escapeHtml(label?.description || "未配置标签集说明")}</small>
            </div>
          </td>
          <td class="model-cell-side">
            <div class="model-action-panel">
              <div class="model-side-top">
                ${badge(item.status)}
                <small>${escapeHtml(item.created_at)}</small>
              </div>
              ${modelActions(item)}
            </div>
          </td>
          <td class="model-cell-metrics">
            ${renderModelMetricBars(summary, "compact")}
          </td>
        </tr>
      `;
    })
    .join("");
  renderModelPagination(models.length, start + 1, Math.min(start + pageItems.length, models.length), totalPages);
}

function modelMetricRows(summary) {
  const lift = numberValue(summary.top50Lift);
  const loss = numberValue(summary.logLoss);
  const lossScore = loss === null ? 0 : Math.max(0, Math.min(100, (1 - loss) * 100));
  const liftWidth = lift === null ? 0 : Math.max(0, Math.min(100, Math.abs(lift) * 200));
  return [
    { label: "F1", value: percent(summary.f1), width: boundedPct(summary.f1), tone: "brand" },
    { label: "Top50", value: percent(summary.top50HitRate), width: boundedPct(summary.top50HitRate), tone: "green" },
    {
      label: "提升",
      value: signedPct(lift !== null ? lift * 100 : null),
      width: liftWidth,
      tone: lift === null ? "neutral" : lift >= 0 ? "green" : "red",
    },
    { label: "Loss", value: decimal(summary.logLoss, 4), width: lossScore, tone: "amber" },
  ];
}

function progressStatusClass(tone) {
  if (tone === "red") {
    return "ant-progress-status-exception";
  }
  if (tone === "green") {
    return "ant-progress-status-success";
  }
  return "ant-progress-status-normal";
}

function renderModelMetricBars(summary, variant = "compact") {
  const rows = modelMetricRows(summary);
  const visibleRows = variant === "compact" ? rows.filter((row) => row.label !== "Loss") : rows;
  return `
    <div class="model-metric-bars ${escapeHtml(variant)}">
      ${visibleRows
        .map((row) => {
          const width = stylePct(row.width);
          const now = numberValue(row.width) ?? 0;
          const ariaValue = Math.round(Math.max(0, Math.min(100, now)) * 10) / 10;
          return `
            <div class="model-metric-bar ant-metric-progress-card" data-progress-tone="${escapeHtml(row.tone)}">
              <div class="ant-metric-progress-head">
                <span>${escapeHtml(row.label)}</span>
              </div>
              <div
                class="ant-progress ant-progress-line ant-progress-show-info ant-progress-default ${progressStatusClass(row.tone)}"
                role="progressbar"
                aria-label="${escapeHtml(row.label)}"
                aria-valuemin="0"
                aria-valuemax="100"
                aria-valuenow="${escapeHtml(ariaValue)}"
              >
                <div class="ant-progress-outer">
                  <div class="ant-progress-inner">
                    <div class="ant-progress-bg" style="width: ${escapeHtml(width)}; height: 10px;"></div>
                  </div>
                </div>
                <span class="ant-progress-text">${escapeHtml(row.value)}</span>
              </div>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderModelPagination(total, start, end, totalPages) {
  const container = $("modelsPagination");
  if (!container) {
    return;
  }
  if (!total) {
    container.innerHTML = "";
    return;
  }
  const page = state.modelPage;
  container.innerHTML = `
    <div class="pagination-info">第 ${escapeHtml(page)} / ${escapeHtml(totalPages)} 页，显示 ${escapeHtml(start)}-${escapeHtml(end)}，共 ${escapeHtml(total)} 个模型</div>
    <div class="pagination-actions">
      <button type="button" data-model-page-action="first" ${page <= 1 ? "disabled" : ""}>首页</button>
      <button type="button" data-model-page-action="prev" ${page <= 1 ? "disabled" : ""}>上一页</button>
      <button type="button" data-model-page-action="next" ${page >= totalPages ? "disabled" : ""}>下一页</button>
      <button type="button" data-model-page-action="last" ${page >= totalPages ? "disabled" : ""}>末页</button>
    </div>
  `;
}

function changeModelPage(action) {
  const models = modelListItems();
  const totalPages = Math.max(1, Math.ceil(models.length / state.modelPageSize));
  if (action === "first") {
    state.modelPage = 1;
  } else if (action === "prev") {
    state.modelPage = Math.max(1, state.modelPage - 1);
  } else if (action === "next") {
    state.modelPage = Math.min(totalPages, state.modelPage + 1);
  } else if (action === "last") {
    state.modelPage = totalPages;
  }
  renderModels(models);
}

function modelListItems() {
  const models = state.overview?.models || [];
  const active = state.overview?.active_model || models.find((item) => item.status === "active");
  return active ? models.filter((item) => item.model_id !== active.model_id) : models;
}

function findDefinition(group, id) {
  const items = state.overview?.[group] || [];
  return items.find((item) => item.id === id) || null;
}

function featureDefinition(id) {
  return findDefinition("feature_sets", id);
}

function labelDefinition(id) {
  return findDefinition("label_sets", id);
}

function metricSummary(metrics) {
  const data = metrics || {};
  const ranking = data.ranking?.validation || {};
  const top50 = ranking.top_n?.["50"] || {};
  return {
    sampleCount: data.sample_count,
    validationSampleCount: data.validation_sample_count,
    f1: data.validation?.f1 ?? data.f1,
    logLoss: data.validation?.log_loss,
    top50HitRate: top50.hit_rate,
    top50Lift: top50.lift,
    marketHitRate: ranking.market_hit_rate,
  };
}

function paramSummary(params) {
  const data = params || {};
  const keys = ["validation_ratio", "learning_rate", "l2", "max_iter", "patience"];
  const parts = keys
    .filter((key) => data[key] !== undefined && data[key] !== null && data[key] !== "")
    .map((key) => `${key}=${data[key]}`);
  return parts.length ? parts.join(" · ") : "-";
}

function paramHelpKey(key) {
  const mapping = {
    validation_ratio: "validationRatio",
    learning_rate: "learningRate",
    l2: "l2",
    max_iter: "maxIter",
    patience: "patience",
  };
  return mapping[key] || "params";
}

function compactMetricBlock(rows) {
  return `
    <div class="compact-metrics">
      ${rows
        .map(
          ([label, value, helpKey]) => `
            <span>
              <b>${helpKey ? helpLabel(label, helpKey) : escapeHtml(label)}</b>
              ${escapeHtml(value)}
            </span>
          `,
        )
        .join("")}
    </div>
  `;
}

function runModelRef(item) {
  if (!item.model_id) {
    return `<div class="run-model-ref empty-ref"><span>模型</span><strong>未生成</strong></div>`;
  }
  const model = (state.overview?.models || []).find((entry) => entry.model_id === item.model_id);
  return `
    <div class="run-model-ref" title="${escapeHtml(item.model_id)}">
      <span>模型</span>
      <strong>${escapeHtml(shortId(item.model_id))}</strong>
      ${model?.status ? badge(model.status) : ""}
      <button type="button" data-admin-view="models">查看</button>
    </div>
  `;
}

function runRecordMetric(label, value, helpKey) {
  return `
    <div class="run-record-metric">
      <span>${helpKey ? helpLabel(label, helpKey) : escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function renderRuns(runs) {
  const body = $("runsBody");
  if (!runs.length) {
    body.innerHTML = emptyRow("还没有训练任务。点击上方“新建训练任务”即可开始。", 8);
    return;
  }
  body.innerHTML = runs
    .map((item) => {
      const summary = metricSummary(item.metrics || {});
      const params = paramSummary(item.params || {});
      return `
        <tr class="run-record-row">
          <td colspan="8">
            <article class="run-record-card">
              <div class="run-record-main" title="${escapeHtml(item.run_id)}">
                <div class="run-record-eyebrow">
                  ${badge(item.status)}
                  ${runModelRef(item)}
                </div>
                <strong>${escapeHtml(shortId(item.run_id))}</strong>
                <small>${escapeHtml(item.created_at || "-")}</small>
              </div>
              <div class="run-record-config">
                <span>特征 / 标签</span>
                <strong>${escapeHtml(item.feature_set)}</strong>
                <small>${escapeHtml(item.label_set)}</small>
                <p title="${escapeHtml(JSON.stringify(item.params || {}))}">参数：${escapeHtml(params)}</p>
              </div>
              <div class="run-record-metrics">
                ${runRecordMetric("总样本", text(summary.sampleCount), "trainSamples")}
                ${runRecordMetric("验证样本", text(summary.validationSampleCount), "samples")}
                ${runRecordMetric("F1", percent(summary.f1), "validationF1")}
                ${runRecordMetric("Loss", decimal(summary.logLoss, 4), "logLoss")}
                ${runRecordMetric("Top50", percent(summary.top50HitRate), "top50")}
                ${runRecordMetric("提升", signedPct(summary.top50Lift !== undefined && summary.top50Lift !== null ? summary.top50Lift * 100 : null), "top50Lift")}
              </div>
              <div class="run-record-actions">
                ${runActions(item)}
              </div>
            </article>
          </td>
        </tr>
      `;
    })
    .join("");
}

function runActions(item) {
  if (!["queued", "failed"].includes(item.status)) {
    return `<div class="row-actions"></div>`;
  }
  return `
    <div class="row-actions">
      <button type="button" data-run-action="run" data-run-id="${escapeHtml(item.run_id)}">执行</button>
    </div>
  `;
}

function renderStages(stages) {
  const container = $("stageList");
  if (!stages.length) {
    container.innerHTML = `<div class="empty">暂无流水线阶段</div>`;
    return;
  }
  container.innerHTML = stages
    .map(
      (stage) => `
        <div class="stage">
          <div>
            <strong>${escapeHtml(stage.name)}</strong>
            <span>${escapeHtml(stage.id)}</span>
          </div>
          ${badge(stage.status)}
        </div>
      `,
    )
    .join("");
}

function renderDefinitions(id, items) {
  const container = $(id);
  if (!items.length) {
    container.innerHTML = `<div class="empty">暂无定义</div>`;
    return;
  }
  container.innerHTML = items
    .map(
      (item) => `
        <div class="definition-item">
          <strong>${escapeHtml(item.name || item.id)}</strong>
          <p>${escapeHtml(item.description)}</p>
          ${badge(item.status)}
        </div>
      `,
    )
    .join("");
}

function renderSelectOptions(id, items, fallback) {
  const select = $(id);
  if (!select) {
    return;
  }
  const current = select.value || fallback;
  select.innerHTML = (items || [])
    .map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name || item.id)}</option>`)
    .join("");
  if ([...select.options].some((option) => option.value === current)) {
    select.value = current;
  } else if (fallback) {
    select.value = fallback;
  }
}

function renderTrainingOptions(payload) {
  renderSelectOptions("featureSetInput", payload.feature_sets || [], "short_swing_v2");
  renderSelectOptions("labelSetInput", payload.label_sets || [], "next_high_3pct_v1");
}

function syncSuggestedInput(id, value) {
  const input = $(id);
  if (!input) {
    return;
  }
  input.placeholder = value ? fromTradeDate(value) : "暂无推荐日期";
  if (input.dataset.autofilled === "true" && value) {
    input.value = fromTradeDate(value);
  }
}

function renderWorkflowSummary(workflow) {
  const container = $("workflowSummary");
  if (!container) {
    return;
  }
  container.innerHTML = `
    <div class="workflow-item">
      <span>预测使用</span>
      <strong>${escapeHtml(workflow.suggested_prediction_date || "暂无行情")}</strong>
    </div>
    <div class="workflow-item">
      <span>验证预测日</span>
      <strong>${escapeHtml(workflow.suggested_validation_date || "暂无预测")}</strong>
    </div>
    <div class="workflow-item">
      <span>验证对比日</span>
      <strong>${escapeHtml(workflow.validation_next_trade_date || "等待行情")}</strong>
    </div>
  `;
}

function renderWorkflow(payload) {
  const workflow = payload.workflow || {};
  syncSuggestedInput("predictionDateInput", workflow.suggested_prediction_date);
  syncSuggestedInput("validationDateInput", workflow.suggested_validation_date);
  syncHistoryDefaults(workflow);
  renderWorkflowSummary(workflow);

  const hint = $("validationHint");
  if (hint) {
    const latestMarket = workflow.latest_market_date || "暂无";
    const latestPrediction = workflow.latest_prediction_date || "暂无";
    const validationText = workflow.validation_ready
      ? `可验证 ${workflow.suggested_validation_date || latestPrediction} 的预测。`
      : workflow.validation_reason || "暂无可验证预测，或后续行情还没入库。";
    hint.textContent = `最新行情日 ${latestMarket}；最近预测日 ${latestPrediction}；${validationText}`;
  }

  const hasActive = Boolean(payload.active_model);
  const canPredict = hasActive && Boolean(workflow.suggested_prediction_date);
  const canValidate = hasActive && Boolean(workflow.suggested_validation_date) && Boolean(workflow.validation_ready);
  if ($("runPredictionBtn")) $("runPredictionBtn").disabled = !canPredict;
  if ($("runValidationBtn")) $("runValidationBtn").disabled = !canValidate;
}

function previousYearDate(value) {
  const raw = text(value, "");
  if (!/^\d{8}$/.test(raw)) {
    return "";
  }
  const year = Math.max(1900, Number(raw.slice(0, 4)) - 1);
  return `${year}${raw.slice(4)}`;
}

function todayTradeDate() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}${month}${day}`;
}

function syncHistoryDefaults(workflow) {
  const start = $("backfillStartInput");
  const end = $("backfillEndInput");
  const latest = workflow.latest_market_date || workflow.suggested_prediction_date || todayTradeDate();
  if (start && !start.value && latest) {
    start.placeholder = fromTradeDate(previousYearDate(latest)) || "选择开始日期";
  }
  if (end && latest) {
    end.placeholder = fromTradeDate(latest) || "选择结束日期";
  }
  const hint = $("historyBackfillHint");
  if (hint) {
    const latestText = workflow.latest_market_date || "本地暂无行情";
    hint.textContent = `当前最新行情日 ${latestText}。历史越长，训练/验证越能覆盖不同行情阶段；批量训练会按 Top50 提升自动选优。`;
  }
}

function syncWorkflowButtons() {
  if (state.overview) {
    renderWorkflow(state.overview);
  }
}

function renderActiveModelPanel(model) {
  const container = $("activeModelPanel");
  if (!container) {
    return;
  }
  if (!model) {
    container.innerHTML = `
      <div class="active-model-empty">
        <div>
          <span>当前使用中</span>
          <h3>暂无使用中模型</h3>
          <p>先训练候选模型，通过审核后再上线。</p>
        </div>
      </div>
    `;
    return;
  }
  const summary = metricSummary(model.metrics || {});
  const feature = featureDefinition(model.feature_set);
  const label = labelDefinition(model.label_set);
  container.innerHTML = `
    <div class="active-model-layout models-hero-layout">
      <div class="active-model-main">
        <div class="active-model-title">
          <span>当前使用中</span>
          <h3>${escapeHtml(model.name || model.model_id)}</h3>
          <p>${escapeHtml(shortId(model.model_id))} · ${escapeHtml(model.created_at || "-")}</p>
        </div>
        <div class="active-model-tags">
          ${badge(model.status)}
          <span>${escapeHtml(model.model_type || "-")}</span>
          <span>${escapeHtml(model.feature_set || "-")}</span>
          <span>${escapeHtml(model.label_set || "-")}</span>
        </div>
        <div class="model-sample-strip active-samples">
          <span><b>总样本</b>${escapeHtml(text(summary.sampleCount))}</span>
          <span><b>验证样本</b>${escapeHtml(text(summary.validationSampleCount))}</span>
          <span><b>市场基准</b>${escapeHtml(percent(summary.marketHitRate))}</span>
        </div>
        <div class="model-detail-notes">
          <p><b>特征集说明：</b>${escapeHtml(feature?.description || "未配置特征集说明")}</p>
          <p><b>标签集说明：</b>${escapeHtml(label?.description || "未配置标签集说明")}</p>
        </div>
      </div>
      <div class="active-model-chart">
        ${renderModelMetricBars(summary, "featured")}
      </div>
      <div class="active-model-actions">
        ${modelActions(model)}
      </div>
    </div>
  `;
}

function renderOverview(payload) {
  const models = payload.models || [];
  const runs = payload.training_runs || [];
  const stages = payload.pipelines?.stages || [];
  const activeModel = payload.active_model || models.find((item) => item.status === "active");

  $("activeModel").textContent = activeModel?.name || activeModel?.model_id || "暂无";
  $("modelCount").textContent = models.length;
  $("runCount").textContent = runs.length;
  $("stageCount").textContent = stages.length;

  renderActiveModelPanel(activeModel);
  renderStepGuide(payload);
  renderModels(modelListItems());
  renderRuns(runs);
  renderStages(stages);
  renderEvents(payload.model_events || []);
  renderPerformance(payload.model_performance || []);
  renderDefinitions("featureSets", payload.feature_sets || []);
  renderDefinitions("labelSets", payload.label_sets || []);
  renderTrainingOptions(payload);
  renderWorkflow(payload);
  renderDiagnostics(payload);
  renderCoach(payload);
  normalizeHelpTips();
}

function findFirst(items, statuses) {
  return (items || []).find((item) => statuses.includes(item.status));
}

function setStep(activeStep) {
  document.querySelectorAll(".step-card").forEach((item) => {
    item.classList.toggle("active", item.dataset.step === activeStep);
  });
}

function stepState(status) {
  const mapping = {
    current: { label: "现在做", className: "current" },
    done: { label: "已完成", className: "done" },
    waiting: { label: "等前一步", className: "waiting" },
  };
  return mapping[status] || mapping.waiting;
}

function guideActionButton(label, action) {
  return `<button type="button" data-guide-action="${escapeHtml(action)}">${escapeHtml(label)}</button>`;
}

function guideViewButton(label, view, trainingTab = "") {
  const tabAttr = trainingTab ? ` data-guide-training-tab="${escapeHtml(trainingTab)}"` : "";
  return `<button type="button" data-guide-view="${escapeHtml(view)}"${tabAttr}>${escapeHtml(label)}</button>`;
}

function renderStepGuide(payload) {
  const container = $("stepGuide");
  if (!container) {
    return;
  }
  const models = payload.models || [];
  const runs = payload.training_runs || [];
  const workflow = payload.workflow || {};
  const performance = payload.model_performance || [];
  const queued = findFirst(runs, ["queued", "failed"]);
  const candidate = findFirst(models, ["candidate"]);
  const approved = findFirst(models, ["approved"]);
  const hasActive = Boolean(payload.active_model);
  const hasMarketData = Boolean(workflow.latest_market_date);
  const hasPrediction = Boolean(workflow.latest_prediction_date);
  const validationReady = Boolean(workflow.validation_ready);
  const hasValidation = performance.some((item) => Number(item.validation_count || 0) > 0);

  const steps = [
    hasMarketData
      ? {
          step: "data",
          number: 1,
          title: "准备训练样本",
          place: "训练任务 / 多模型选优",
          status: "done",
          detail: `本地已有行情缓存，最新行情日 ${workflow.latest_market_date}。后续训练会从这些日线数据里构造样本。`,
          actions: [guideViewButton("继续回填", "training", "matrix")],
        }
      : {
          step: "data",
          number: 1,
          title: "先回填历史行情",
          place: "训练任务 / 多模型选优",
          status: "current",
          detail: "训练样本来自本地日线缓存。清库或首次使用后，必须先回填历史行情，再开始训练。",
          actions: [guideViewButton("去回填历史", "training", "matrix")],
        },
    queued
      ? {
          step: "train",
          number: 2,
          title: "执行训练任务",
          place: "工作台 / 训练任务",
          status: hasMarketData ? "current" : "waiting",
          detail: hasMarketData
            ? "你已经建好了训练任务，现在点“执行待训练任务”就会开始训练，并生成候选模型。"
            : "你已经建好了训练任务，但本地行情为空。先回填历史行情，再执行训练。",
          actions: hasMarketData
            ? [guideActionButton("执行待训练任务", "runQueued"), guideViewButton("去训练页", "training", "records")]
            : [guideViewButton("去回填历史", "training", "matrix")],
        }
      : candidate || approved || hasActive
        ? {
            step: "train",
            number: 2,
            title: "生成候选模型",
            place: "工作台 / 训练任务",
            status: "done",
            detail: "训练已经跑过了。这一步以后想重训时，再回“训练任务”页新建并执行任务。",
            actions: [guideViewButton("去训练页", "training")],
          }
        : {
            step: "train",
            number: 2,
            title: "先训练一个候选模型",
            place: "工作台 / 训练任务",
            status: hasMarketData ? "current" : "waiting",
            detail: hasMarketData
              ? "分步操作就是先点“新建训练任务”，再点“执行待训练任务”。想省事可以直接点“一键训练并上线”。"
              : "先完成历史行情回填。回填后再创建训练任务，模型才有样本可学。",
            actions: hasMarketData
              ? [guideActionButton("新建训练任务", "queueTrain"), guideActionButton("一键训练并上线", "trainApproveActivate")]
              : [guideViewButton("去回填历史", "training", "matrix")],
          },
    candidate
      ? {
          step: "approve",
          number: 3,
          title: "审核候选模型",
          place: "模型版本",
          status: "current",
          detail: "去“模型版本”页，先看验证 F1、Top50 和验证样本数，确认没有明显异常后再点“通过”。",
          actions: [guideActionButton("通过候选模型", "approveCandidate"), guideViewButton("去模型版本", "models")],
        }
      : approved || hasActive
        ? {
            step: "approve",
            number: 3,
            title: "审核候选模型",
            place: "模型版本",
            status: "done",
            detail: "候选模型已经审核通过。如果后面重新训练出新候选，再回“模型版本”页处理。",
            actions: [guideViewButton("去模型版本", "models")],
          }
        : {
            step: "approve",
            number: 3,
            title: "审核候选模型",
            place: "模型版本",
            status: "waiting",
            detail: "先完成训练。训练结束后，这里会出现“候选模型”，再去点“通过”。",
            actions: [guideViewButton("去模型版本", "models")],
          },
    approved
      ? {
          step: "activate",
          number: 4,
          title: "上线启用模型",
          place: "模型版本",
          status: "current",
          detail: "审核通过后，到“模型版本”页点“上线”。上线后，预测和验证都会使用这个模型。",
          actions: [guideActionButton("上线已通过模型", "activateApproved"), guideViewButton("去模型版本", "models")],
        }
      : hasActive
        ? {
            step: "activate",
            number: 4,
            title: "上线启用模型",
            place: "模型版本",
            status: "done",
            detail: "已经有启用中的模型了。如果要换版本，可以回“模型版本”页继续切换或回滚。",
            actions: [guideViewButton("去模型版本", "models")],
          }
        : {
            step: "activate",
            number: 4,
            title: "上线启用模型",
            place: "模型版本",
            status: "waiting",
            detail: "先把候选模型审核通过。通过后，这一步才会出现可点的“上线”按钮。",
            actions: [guideViewButton("去模型版本", "models")],
          },
    !hasActive
      ? {
          step: "monitor",
          number: 5,
          title: "预测并验证",
          place: "预测验证",
          status: "waiting",
          detail: "先完成前面 3 步。模型上线后，再去“预测验证”页生成预测和做次日验证。",
          actions: [guideViewButton("去预测验证", "predict")],
        }
      : validationReady
        ? {
            step: "monitor",
            number: 5,
            title: "验证最近一次预测",
            place: "预测验证",
            status: "current",
            detail: "系统已经找到最近可验证的预测日期，现在去“预测验证”页点“验证最近可验证预测”。",
            actions: [guideActionButton("验证最近可验证预测", "runValidation"), guideViewButton("去预测验证", "predict")],
          }
        : hasPrediction
          ? {
              step: "monitor",
              number: 5,
              title: "等待下一交易日后验证",
              place: "预测验证",
              status: hasValidation ? "done" : "current",
              detail: "最近一次预测已经生成。等下一交易日数据到齐后，再回“预测验证”页点“验证最近可验证预测”。",
              actions: [guideViewButton("去预测验证", "predict"), guideActionButton("继续生成预测", "runPrediction")],
            }
          : {
              step: "monitor",
              number: 5,
              title: "生成最新预测",
              place: "预测验证",
              status: "current",
              detail: "模型已经上线。现在去“预测验证”页点“生成最新预测”，等下一交易日后再做验证。",
              actions: [guideActionButton("生成最新预测", "runPrediction"), guideViewButton("去预测验证", "predict")],
            },
  ];

  container.innerHTML = steps
    .map((item) => {
      const state = stepState(item.status);
      return `
        <article class="step-card ${escapeHtml(state.className)}" data-step="${escapeHtml(item.step)}">
          <div class="step-head">
            <b>${escapeHtml(item.number)}</b>
            <div class="step-copy">
              <strong>${escapeHtml(item.title)}</strong>
              <span class="step-place">${escapeHtml(item.place)}</span>
            </div>
            <span class="step-state ${escapeHtml(state.className)}">${escapeHtml(state.label)}</span>
          </div>
          <p>${escapeHtml(item.detail)}</p>
          <div class="step-actions">${item.actions.join("")}</div>
        </article>
      `;
    })
    .join("");
}

function setView(view) {
  const target = document.querySelector(`[data-view-panel="${view}"]`);
  if (!target) {
    return;
  }
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.view === view);
  });
  document.querySelectorAll("[data-view-panel]").forEach((item) => {
    item.classList.toggle("active", item.dataset.viewPanel === view);
  });
  if (window.location.hash !== `#${view}`) {
    window.history.replaceState(null, "", `#${view}`);
  }
}

function setTrainingTab(tab) {
  const target = document.querySelector(`[data-training-panel="${tab}"]`);
  if (!target) {
    return;
  }
  state.trainingTab = tab;
  document.querySelectorAll("[data-training-tab]").forEach((item) => {
    item.classList.toggle("active", item.dataset.trainingTab === tab);
  });
  document.querySelectorAll("[data-training-panel]").forEach((item) => {
    item.classList.toggle("active", item.dataset.trainingPanel === tab);
  });
}

function openAdminView(view, trainingTab = "") {
  setView(view);
  if (view === "training" && trainingTab) {
    setTrainingTab(trainingTab);
  }
}

function syncViewFromHash() {
  const initialView = window.location.hash.replace("#", "");
  if (initialView) {
    setView(initialView);
  }
}

function renderCoach(payload) {
  const models = payload.models || [];
  const runs = payload.training_runs || [];
  const workflow = payload.workflow || {};
  const hasActive = Boolean(payload.active_model);
  const hasMarketData = Boolean(workflow.latest_market_date);
  const queued = findFirst(runs, ["queued", "failed"]);
  const candidate = findFirst(models, ["candidate"]);
  const approved = findFirst(models, ["approved"]);
  const performance = payload.model_performance || [];
  const hasValidation = performance.some((item) => Number(item.validation_count || 0) > 0);
  const actions = $("coachActions");

  if (!hasMarketData) {
    $("coachTitle").textContent = "先回填历史行情";
    $("coachText").textContent = "训练样本来自本地日线缓存。现在缓存为空，先去回填历史日线，再创建训练任务。";
    actions.innerHTML = `<button type="button" data-coach-action="openBackfill">去回填历史</button>`;
    setStep("data");
    return;
  }
  if (queued) {
    $("coachTitle").textContent = "有训练任务等待执行";
    $("coachText").textContent = "点击执行后，系统会从本地历史行情里生成一个候选模型。";
    actions.innerHTML = `<button type="button" data-coach-action="runQueued">执行训练</button>`;
    setStep("train");
    return;
  }
  if (candidate) {
    $("coachTitle").textContent = "有候选模型等待审核";
    $("coachText").textContent = "先去模型版本页看验证 F1、Top50 和验证样本数，确认没有明显异常后再点通过。";
    actions.innerHTML = `<button type="button" data-coach-action="approveCandidate">通过候选</button>`;
    setStep("approve");
    return;
  }
  if (approved) {
    $("coachTitle").textContent = "有已通过模型可以上线";
    $("coachText").textContent = "上线后，预测和验证都会使用这个模型版本。";
    actions.innerHTML = `<button type="button" data-coach-action="activateApproved">上线模型</button>`;
    setStep("activate");
    return;
  }
  if (hasActive && !hasValidation) {
    $("coachTitle").textContent = "模型已上线，可以生成预测";
    $("coachText").textContent = "系统已自动选择最近行情日；先生成预测，下一交易日数据有了以后再验证。";
    actions.innerHTML = `<button type="button" data-coach-action="runPrediction">生成预测</button>`;
    setStep("monitor");
    return;
  }
  if (hasActive) {
    $("coachTitle").textContent = "模型正在使用中";
    $("coachText").textContent = "可以继续生成预测，或观察下面的命中率和平均收益。";
    actions.innerHTML = `<button type="button" data-coach-action="runPrediction">继续预测</button>`;
    setStep("monitor");
    return;
  }

  $("coachTitle").textContent = "先训练一个候选模型";
  $("coachText").textContent = "选择一个标签集后，可一键训练、审批并上线；后续再用 Top50 指标决定保留哪个版本。";
  actions.innerHTML = `
    <button type="button" data-coach-action="trainApproveActivate">一键训练并上线</button>
    <button type="button" data-coach-action="queueTrain">只新建任务</button>
  `;
  setStep("train");
}

function percent(value) {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${Math.round(Number(value) * 1000) / 10}%`;
}

function signedPct(value) {
  if (value === null || value === undefined) {
    return "-";
  }
  const number = Number(value);
  const sign = number > 0 ? "+" : "";
  return `${sign}${Math.round(number * 100) / 100}%`;
}

function decimal(value, digits = 4) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : "-";
}

function numberValue(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function boundedPct(value) {
  const number = numberValue(value);
  if (number === null) {
    return 0;
  }
  return Math.max(0, Math.min(100, number * 100));
}

function stylePct(value) {
  const number = numberValue(value);
  if (number === null) {
    return "0%";
  }
  const bounded = Math.max(0, Math.min(100, number));
  return `${Math.round(bounded * 100) / 100}%`;
}

function topMetric(item, size = "50") {
  return item.ranking?.top_n?.[size] || null;
}

function metricRow(label, value) {
  return metricRowHelp(label, value, "");
}

function metricRowHelp(label, value, helpKey, fallback = "") {
  return `
    <div class="metric-detail-item">
      <span>${helpKey ? helpLabel(label, helpKey, fallback) : escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function kpi(label, value, helpKey = "") {
  return `
    <div class="metric-kpi">
      <span>${helpKey ? helpLabel(label, helpKey) : escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function metricPill(label, value, tone = "neutral") {
  return `
    <span class="metric-pill ${escapeHtml(tone)}">
      <b>${escapeHtml(label)}</b>
      ${escapeHtml(value)}
    </span>
  `;
}

function scoreCard(label, value, hint, tone = "neutral", helpKey = "") {
  return `
    <div class="score-card ${escapeHtml(tone)}">
      <span>${helpKey ? helpLabel(label, helpKey) : escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <small>${escapeHtml(hint)}</small>
    </div>
  `;
}

function renderRankingChart(topN, marketHitRate) {
  const rows = ["20", "50", "100"]
    .map((size) => ({ size, item: topN?.[size] || null }))
    .filter((row) => row.item);
  if (!rows.length) {
    return `<div class="empty">暂无 TopN 排序指标</div>`;
  }
  const market = boundedPct(marketHitRate);
  return `
    <div class="ranking-chart">
      <div class="chart-legend">
        <span><i class="legend-fill"></i>TopN 命中率</span>
        <span><i class="legend-line"></i>全市场基准 ${escapeHtml(percent(marketHitRate))}</span>
      </div>
      <div class="ranking-axis">
        <span>0%</span>
        <span>50%</span>
        <span>100%</span>
      </div>
      ${rows
        .map(({ size, item }) => {
          const hitRate = boundedPct(item.hit_rate);
          const lift = numberValue(item.lift);
          const liftTone = lift === null ? "neutral" : lift >= 0 ? "positive" : "negative";
          return `
            <div class="ranking-row">
              <div class="ranking-label">
                <strong>Top${escapeHtml(size)}</strong>
                <span>${escapeHtml(text(item.count, size))} 只</span>
              </div>
              <div class="ranking-bar">
                <span class="ranking-bar-fill" style="width: ${escapeHtml(stylePct(hitRate))};"></span>
                <span class="ranking-market" style="left: ${escapeHtml(stylePct(market))};"></span>
              </div>
              <div class="ranking-value">
                <strong>${escapeHtml(percent(item.hit_rate))}</strong>
                <span class="${liftTone}">${escapeHtml(signedPct(lift !== null ? lift * 100 : null))}</span>
              </div>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderRankingSummary(topN) {
  const rows = ["20", "50", "100"]
    .map((size) => ({ size, item: topN?.[size] || null }))
    .filter((row) => row.item);
  if (!rows.length) {
    return `<div class="empty">暂无排序摘要</div>`;
  }
  return rows
    .map(({ size, item }) => {
      const lift = numberValue(item.lift);
      const tone = lift === null ? "neutral" : lift >= 0 ? "positive" : "negative";
      return `
        <div class="ranking-summary-item">
          <span>Top${escapeHtml(size)}</span>
          <strong>${escapeHtml(percent(item.hit_rate))}</strong>
          <small class="${tone}">${helpLabel("提升", "top50Lift")} ${escapeHtml(signedPct(lift !== null ? lift * 100 : null))}</small>
          <b>${escapeHtml(signedPct(item.avg_window_high_pct ?? item.avg_next_high_pct))}</b>
        </div>
      `;
    })
    .join("");
}

function chartPoint(index, length, value, minValue, maxValue) {
  const width = 560;
  const height = 150;
  const padX = 38;
  const padY = 18;
  const usableW = width - padX * 2;
  const usableH = height - padY * 2;
  const x = length <= 1 ? width / 2 : padX + (index / (length - 1)) * usableW;
  const y = padY + ((maxValue - value) / (maxValue - minValue || 1)) * usableH;
  return [Number(x.toFixed(2)), Number(y.toFixed(2))];
}

function renderLossChart(history) {
  const rows = Array.isArray(history) ? history.filter((row) => row && row.iteration !== undefined) : [];
  if (!rows.length) {
    return `<div class="empty">暂无训练过程曲线</div>`;
  }
  const values = rows
    .flatMap((row) => [numberValue(row.train_log_loss), numberValue(row.validation_log_loss)])
    .filter((value) => value !== null);
  if (!values.length) {
    return `<div class="empty">暂无训练过程曲线</div>`;
  }
  let minValue = Math.min(...values);
  let maxValue = Math.max(...values);
  if (minValue === maxValue) {
    minValue -= 0.01;
    maxValue += 0.01;
  } else {
    const padding = (maxValue - minValue) * 0.12;
    minValue -= padding;
    maxValue += padding;
  }
  const trainPoints = rows
    .map((row, index) => chartPoint(index, rows.length, numberValue(row.train_log_loss), minValue, maxValue).join(","))
    .join(" ");
  const validationPoints = rows
    .map((row, index) => chartPoint(index, rows.length, numberValue(row.validation_log_loss), minValue, maxValue).join(","))
    .join(" ");
  const firstIteration = rows[0]?.iteration;
  const lastIteration = rows[rows.length - 1]?.iteration;
  const lastTrain = rows[rows.length - 1]?.train_log_loss;
  const lastValidation = rows[rows.length - 1]?.validation_log_loss;
  return `
    <div class="loss-chart">
      <svg viewBox="0 0 560 150" role="img" aria-label="训练和验证 Log Loss 曲线">
        <line class="chart-grid-line" x1="38" y1="18" x2="38" y2="132"></line>
        <line class="chart-grid-line" x1="38" y1="132" x2="522" y2="132"></line>
        <line class="chart-guide" x1="38" y1="75" x2="522" y2="75"></line>
        <polyline class="loss-line train" points="${escapeHtml(trainPoints)}"></polyline>
        <polyline class="loss-line validation" points="${escapeHtml(validationPoints)}"></polyline>
      </svg>
      <div class="loss-meta">
        <span>迭代 ${escapeHtml(text(firstIteration))} - ${escapeHtml(text(lastIteration))}</span>
        <span>训练 ${escapeHtml(decimal(lastTrain, 6))}</span>
        <span>验证 ${escapeHtml(decimal(lastValidation, 6))}</span>
      </div>
      <div class="chart-legend">
        <span><i class="legend-train"></i>训练 Log Loss</span>
        <span><i class="legend-validation"></i>验证 Log Loss</span>
      </div>
    </div>
  `;
}

function renderWeightChart(weights) {
  const rows = Array.isArray(weights) ? weights.slice(0, 18) : [];
  if (!rows.length) {
    return `<div class="empty">暂无特征权重</div>`;
  }
  const maxAbs = Math.max(...rows.map((item) => Math.abs(numberValue(item.weight) || 0)), 0.000001);
  return rows
    .map((item, index) => {
      const weight = numberValue(item.weight) || 0;
      const width = Math.max(3, Math.min(100, (Math.abs(weight) / maxAbs) * 100));
      const tone = weight >= 0 ? "positive" : "negative";
      return `
        <div class="weight-row ${tone}" title="${escapeHtml(item.feature)}">
          <div class="weight-rank">${index + 1}</div>
          <div class="weight-name">${escapeHtml(item.feature)}</div>
          <div class="weight-bar-track">
            <span class="weight-bar-fill" style="width: ${escapeHtml(stylePct(width))};"></span>
          </div>
          <div class="weight-value">${escapeHtml(decimal(weight, 5))}</div>
        </div>
      `;
    })
    .join("");
}

function renderValidationFlow(workflow, liveTop50) {
  const steps = [
    {
      state: workflow.latest_prediction_date ? "done" : workflow.suggested_prediction_date ? "ready" : "wait",
      title: "生成预测",
      value: workflow.latest_prediction_date || workflow.suggested_prediction_date || "暂无行情",
      detail: "写入 ml_predictions，作为后续验证样本。",
    },
    {
      state: workflow.validation_next_trade_date ? "done" : "wait",
      title: "等待真实行情",
      value: workflow.validation_next_trade_date || "等待下一交易日",
      detail: `最近预测日：${workflow.latest_prediction_date || "暂无"}`,
    },
    {
      state: workflow.validation_ready ? "ready" : liveTop50 ? "done" : "wait",
      title: "验证结果",
      value: liveTop50 ? `Top50 ${percent(liveTop50.hit_rate)}` : workflow.validation_ready ? "可验证" : "未完成",
      detail: workflow.validation_reason || "验证会写入 ml_validation_results。",
    },
  ];
  return `
    <div class="verify-flow">
      ${steps
        .map(
          (step, index) => `
            <div class="verify-node ${escapeHtml(step.state)}">
              <span>${index + 1}</span>
              <strong>${escapeHtml(step.title)}</strong>
              <b>${escapeHtml(step.value)}</b>
              <p>${escapeHtml(step.detail)}</p>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderPerformance(items) {
  const body = $("performanceBody");
  if (!items.length) {
    body.innerHTML = emptyRow("暂无模型表现数据", 8);
    return;
  }
  body.innerHTML = items
    .map((item) => {
      const top50 = topMetric(item);
      return `
        <tr>
          <td title="${escapeHtml(item.model_id)}">${escapeHtml(shortId(item.name || item.model_id))}</td>
          <td>${badge(item.status)}</td>
          <td>${escapeHtml(item.prediction_count)}</td>
          <td>${escapeHtml(item.validation_count)}</td>
          <td>${percent(item.hit_rate)}</td>
          <td>${percent(top50?.hit_rate)}</td>
          <td>${signedPct(top50?.lift !== undefined && top50?.lift !== null ? top50.lift * 100 : null)}</td>
          <td>${signedPct(top50?.avg_window_high_pct ?? top50?.avg_next_high_pct)}</td>
        </tr>
      `;
    })
    .join("");
}

function activePerformance(payload) {
  const activeId = payload.active_model?.model_id;
  return (payload.model_performance || []).find((item) => item.model_id === activeId) || null;
}

function renderDiagnostics(payload) {
  const model = payload.active_model || {};
  const metrics = model.metrics || {};
  const diagnostics = state.diagnostics?.diagnostics || {};
  const performance = activePerformance(payload);
  const top50 = metrics.ranking?.validation?.top_n?.["50"];
  const liveTop50 = performance?.ranking?.top_n?.["50"];
  const validation = metrics.validation || {};
  const topN = metrics.ranking?.validation?.top_n || {};
  const marketHitRate = metrics.ranking?.validation?.market_hit_rate;
  const training = diagnostics.training || {};
  const params = diagnostics.params || model.params || {};

  const modelName = $("diagnosticModelName");
  if (modelName) {
    modelName.textContent = model.model_id ? model.name || model.model_id : "暂无模型";
  }

  const meta = $("diagnosticModelMeta");
  if (meta) {
    meta.textContent = model.model_id
      ? `${model.model_type || diagnostics.model_type || "-"} · ${model.feature_set || "-"} · ${model.label_set || "-"}`
      : "暂无模型";
  }

  const health = $("diagnosticHealth");
  if (health) {
    const lift = numberValue(top50?.lift);
    health.innerHTML = model.model_id
      ? [
          metricPill("模型", badge(model.status).replace(/<[^>]+>/g, ""), model.status === "active" ? "positive" : "neutral"),
          metricPill("样本", text(metrics.sample_count), "neutral"),
          metricPill("Top50 提升", signedPct(lift !== null ? lift * 100 : null), lift !== null && lift >= 0 ? "positive" : "negative"),
          metricPill("验证基准", percent(marketHitRate), "neutral"),
        ].join("")
      : "";
  }

  const kpis = $("diagnosticKpis");
  if (kpis) {
    kpis.innerHTML = model.model_id
      ? [
          kpi("训练样本", text(metrics.sample_count), "trainSamples"),
          kpi("特征数", text(diagnostics.feature_count), "featureCount"),
          kpi("验证 F1", percent(validation.f1 ?? metrics.f1), "validationF1"),
          kpi("Top50", percent(top50?.hit_rate), "top50"),
        ].join("")
      : `<div class="empty">暂无激活模型</div>`;
  }

  const rankingChart = $("rankingChart");
  if (rankingChart) {
    rankingChart.innerHTML = model.model_id ? renderRankingChart(topN, marketHitRate) : `<div class="empty">暂无激活模型</div>`;
  }

  const lossChart = $("lossChart");
  if (lossChart) {
    lossChart.innerHTML = renderLossChart(training.history || []);
  }

  const trainingScoreGrid = $("trainingScoreGrid");
  if (trainingScoreGrid) {
    trainingScoreGrid.innerHTML = model.model_id
      ? [
          scoreCard("Accuracy", percent(validation.accuracy), "验证集整体判断", "neutral", "accuracy"),
          scoreCard("Precision", percent(validation.precision), "预测为正时命中率", "neutral", "precision"),
          scoreCard("Recall", percent(validation.recall), "正例覆盖能力", "neutral", "recall"),
          scoreCard("F1", percent(validation.f1 ?? metrics.f1), "精确率与召回率平衡", "positive", "validationF1"),
        ].join("")
      : `<div class="empty">暂无训练指标</div>`;
  }

  const trainingBody = $("trainingMetricBody");
  if (trainingBody) {
    trainingBody.innerHTML = [
      metricRowHelp("Log Loss", decimal(validation.log_loss, 6), "logLoss"),
      metricRowHelp("验证样本", text(metrics.validation_sample_count), "samples"),
      metricRowHelp("正例率", percent(validation.positive_rate), "positiveRate"),
    ].join("");
  }

  const rankingBody = $("rankingMetricBody");
  if (rankingBody) {
    rankingBody.innerHTML = renderRankingSummary(topN);
  }

  const processBody = $("trainingProcessBody");
  if (processBody) {
    processBody.innerHTML = [
      metricRowHelp("训练轮次", text(training.iterations), "iterations"),
      metricRowHelp("最佳轮次", text(training.best_iteration), "bestIteration"),
      metricRowHelp("最佳验证 Log Loss", decimal(training.best_validation_log_loss, 6), "logLoss"),
      metricRowHelp("非零权重", text(diagnostics.non_zero_weight_count), "nonZeroWeights"),
    ].join("");
  }

  const paramBody = $("trainingParamBody");
  if (paramBody) {
    const rows = Object.entries(params || {});
    paramBody.innerHTML = rows.length
      ? rows
          .map(([key, value]) =>
            metricRowHelp(key, typeof value === "object" ? JSON.stringify(value) : text(value), paramHelpKey(key), "训练时传入的参数。")
          )
          .join("")
      : `<div class="empty">暂无训练参数</div>`;
  }

  const weightList = $("featureWeightList");
  if (weightList) {
    const weights = diagnostics.top_weights || [];
    weightList.innerHTML = renderWeightChart(weights);
  }

  const verifySteps = $("dataVerifySteps");
  if (verifySteps) {
    const workflow = payload.workflow || {};
    verifySteps.innerHTML = renderValidationFlow(workflow, liveTop50);
  }
}

function renderEvents(events) {
  const container = $("eventList");
  if (!events.length) {
    container.innerHTML = `<div class="empty">暂无模型事件</div>`;
    return;
  }
  container.innerHTML = events
    .map(
      (item) => `
        <div class="event-item">
          <div>
            <strong>${escapeHtml(item.event_type)} · ${escapeHtml(shortId(item.model_id))}</strong>
            <span>${escapeHtml(item.from_status)} → ${escapeHtml(item.to_status)} · ${escapeHtml(item.created_at)}</span>
          </div>
          ${badge(item.actor || "system")}
        </div>
      `,
    )
    .join("");
}

async function loadOverview({ silent = false } = {}) {
  if (state.loading) {
    return;
  }
  state.loading = true;
  $("refreshBtn").disabled = true;
  try {
    const res = await fetch("/api/admin/overview");
    if (!res.ok) {
      throw new Error(`加载失败：${res.status}`);
    }
    state.overview = await res.json();
    await loadDiagnostics({ silent: true });
    renderOverview(state.overview);
    if (!silent) {
      showToast("已刷新");
    }
  } catch (error) {
    showToast(error.message || "加载失败");
  } finally {
    state.loading = false;
    $("refreshBtn").disabled = false;
  }
}

async function loadDiagnostics({ silent = false } = {}) {
  if (!state.overview?.active_model) {
    state.diagnostics = null;
    return;
  }
  try {
    const res = await fetch(`/api/admin/model-diagnostics?model_id=${encodeURIComponent(state.overview.active_model.model_id)}`);
    if (!res.ok) {
      throw new Error(`诊断加载失败：${res.status}`);
    }
    state.diagnostics = await res.json();
  } catch (error) {
    state.diagnostics = null;
    if (!silent) {
      showToast(error.message || "诊断加载失败");
    }
  }
}

async function createTrainingRun() {
  const res = await fetch("/api/admin/training-runs", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      dataset_version: "market_cache_v1",
      feature_set: $("featureSetInput")?.value || "short_swing_v2",
      label_set: $("labelSetInput")?.value || "next_high_3pct_v1",
      notes: "manual queued from admin",
    }),
  });
  const payload = await res.json();
  if (!res.ok) {
    throw new Error(payload.detail || `创建失败：${res.status}`);
  }
  return payload.item;
}

async function queueTrainingRun() {
  const buttons = ["queueTrainBtn", "queueTrainBtnTraining"].map((id) => $(id)).filter(Boolean);
  buttons.forEach((button) => {
    button.disabled = true;
  });
  try {
    const item = await createTrainingRun();
    showToast(`已创建任务 ${shortId(item?.run_id || "")}`);
    await loadOverview({ silent: true });
    setTrainingTab("records");
  } catch (error) {
    showToast(error.message || "创建失败");
  } finally {
    buttons.forEach((button) => {
      button.disabled = false;
    });
  }
}

function firstRun(statuses) {
  return findFirst(state.overview?.training_runs || [], statuses);
}

function firstModel(statuses) {
  return findFirst(state.overview?.models || [], statuses);
}

async function runFirstQueuedTraining() {
  const buttons = busyButtons(["runQueuedBtn", "runQueuedBtnTraining"], "训练中...");
  let finished = false;
  try {
    const run = firstRun(["queued", "failed"]);
    if (!run) {
      showToast("没有待执行的训练任务");
      return;
    }
    showOperationStatus("正在训练模型，样本多时可能需要几分钟。", {
      title: "模型训练",
      detail: "正在构造样本、训练并保存候选模型",
      estimateSeconds: 240,
      progress: 8,
    });
    await runTraining(run.run_id, { showSuccessToast: false });
    completeOperationStatus("训练完成，正在刷新训练记录");
    finished = true;
    setTrainingTab("records");
  } finally {
    if (finished) {
      window.setTimeout(hideOperationStatus, 900);
    } else {
      hideOperationStatus();
    }
    restoreButtons(buttons);
  }
}

async function runTraining(runId, { reload = true, showSuccessToast = true, showErrorToast = true } = {}) {
  try {
    const res = await fetch(`/api/admin/training-runs/${encodeURIComponent(runId)}/run`, {
      method: "POST",
    });
    const payload = await res.json();
    if (!res.ok) {
      throw new Error(payload.detail || `执行失败：${res.status}`);
    }
    if (showSuccessToast) {
      showToast(`训练完成 ${shortId(payload.model?.model_id || "")}`);
    }
    if (reload) {
      await loadOverview({ silent: true });
    }
    return payload;
  } catch (error) {
    if (showErrorToast) {
      showToast(error.message || "执行失败");
    }
    throw error;
  }
}

async function trainApproveActivate() {
  const buttons = busyButtons(["trainApproveActivateBtn", "trainApproveActivateBtnTraining"], "处理中...");
  let finished = false;
  try {
    showOperationStatus("正在创建训练任务。", {
      title: "一键训练并上线",
      detail: "创建任务、训练模型、审批候选、激活上线",
      estimateSeconds: 300,
      progress: 6,
    });
    const run = await createTrainingRun();
    updateOperationStatus("正在训练模型，样本多时可能需要几分钟。", { progress: 18 });
    const trained = await runTraining(run.run_id, { reload: false, showSuccessToast: false, showErrorToast: false });
    const modelId = trained?.model?.model_id;
    if (!modelId) {
      throw new Error("训练完成但没有返回模型编号");
    }
    updateOperationStatus("正在通过候选模型。", { progress: 88 });
    await mutateModel(modelId, "approve", { reload: false, showSuccessToast: false, showErrorToast: false });
    updateOperationStatus("正在上线模型。", { progress: 94 });
    await mutateModel(modelId, "activate", { reload: false, showSuccessToast: false, showErrorToast: false });
    updateOperationStatus("正在刷新最新模型状态。", { progress: 98 });
    await loadOverview({ silent: true });
    setView("predict");
    completeOperationStatus("模型已上线，可以生成预测");
    finished = true;
  } catch (error) {
    showToast(error.message || "一键流程失败");
    await loadOverview({ silent: true });
  } finally {
    if (finished) {
      window.setTimeout(hideOperationStatus, 900);
    } else {
      hideOperationStatus();
    }
    restoreButtons(buttons);
  }
}

function backfillStartDate() {
  const value = toTradeDate($("backfillStartInput")?.value);
  if (value) {
    return value;
  }
  const latest = state.overview?.workflow?.latest_market_date || state.overview?.workflow?.suggested_prediction_date || todayTradeDate();
  return previousYearDate(latest) || "";
}

function backfillEndDate() {
  return toTradeDate($("backfillEndInput")?.value);
}

async function backfillHistory() {
  const buttons = busyButtons(["backfillHistoryBtn"], "回填中...");
  let finished = false;
  try {
    const startDate = backfillStartDate();
    if (!startDate) {
      throw new Error("请选择回填开始日");
    }
    const body = {
      start_date: startDate,
      max_days: 260,
    };
    const endDate = backfillEndDate();
    if (endDate) {
      body.end_date = endDate;
    }
    const fetchEndDate = endDate || state.overview?.workflow?.latest_market_date || todayTradeDate();
    const days = weekdayCount(startDate, fetchEndDate);
    const cappedDays = Math.min(days || body.max_days, body.max_days);
    showOperationStatus("正在回填历史日线，会按交易日逐天拉取数据。", {
      title: "历史行情回填",
      detail: cappedDays ? `预计检查 ${cappedDays} 个工作日` : "正在检查日期范围",
      estimateSeconds: Math.max(45, cappedDays * 8),
      progress: 5,
    });
    const res = await fetch("/api/admin/history/backfill", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body),
    });
    const payload = await res.json();
    if (!res.ok) {
      throw new Error(payload.detail || `回填失败：${res.status}`);
    }
    completeOperationStatus(`回填完成：新增 ${payload.fetched_days || 0} 天，缓存 ${payload.cached_days || 0} 天`);
    finished = true;
    await loadOverview({ silent: true });
    return payload;
  } catch (error) {
    showToast(error.message || "回填失败");
    throw error;
  } finally {
    if (finished) {
      window.setTimeout(hideOperationStatus, 900);
    } else {
      hideOperationStatus();
    }
    restoreButtons(buttons);
  }
}

async function runTrainingMatrix() {
  const buttons = busyButtons(
    ["runTrainingMatrixBtn", "runTrainingMatrixBtnTraining", "runTrainingMatrixBtnPanel"],
    "训练中...",
  );
  let finished = false;
  try {
    const labelCount = 3;
    showOperationStatus("正在多轮训练选优，会依次训练多个标签集。", {
      title: "多模型选优",
      detail: `预计训练 ${labelCount} 个标签集，完成后自动上线最优`,
      estimateSeconds: labelCount * 240,
      progress: 5,
    });
    const res = await fetch("/api/admin/training-matrix/run", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        dataset_version: "market_cache_v1",
        feature_sets: [$("featureSetInput")?.value || "short_swing_v2"],
        label_sets: ["next_high_3pct_v1", "next_high_2pct_v1", "next_3d_high_3pct_v1"],
        params: {validation_ratio: 0.2},
        activate_best: true,
        notes: "training matrix from admin",
      }),
    });
    const payload = await res.json();
    if (!res.ok) {
      throw new Error(payload.detail || `多轮训练失败：${res.status}`);
    }
    const best = payload.best?.metrics_summary || {};
    const suffix = best.top50_hit_rate !== undefined && best.top50_hit_rate !== null
      ? `，Top50 ${Math.round(best.top50_hit_rate * 100)}%`
      : "";
    completeOperationStatus(`多模型选优完成：已训练 ${payload.completed_count || 0} 个模型${suffix}`);
    finished = true;
    await loadOverview({ silent: true });
    setView("metrics");
    return payload;
  } catch (error) {
    showToast(error.message || "多轮训练失败");
    await loadOverview({ silent: true });
    throw error;
  } finally {
    if (finished) {
      window.setTimeout(hideOperationStatus, 900);
    } else {
      hideOperationStatus();
    }
    restoreButtons(buttons);
  }
}

async function runContinuousTraining() {
  const buttons = busyButtons(
    ["runContinuousTrainingBtn", "runContinuousTrainingBtnTraining", "runContinuousTrainingBtnPanel"],
    "续训中...",
  );
  const rounds = 3;
  let finished = false;
  try {
    showOperationStatus("正在围绕当前激活模型持续训练。", {
      title: "持续训练",
      detail: `连续训练 ${rounds} 轮，只在候选模型优于当前模型时自动上线`,
      estimateSeconds: rounds * 260,
      progress: 5,
    });
    const res = await fetch("/api/admin/training-continuous/run", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        rounds,
        dataset_version: "market_cache_v1",
        params: {validation_ratio: 0.2},
        activate_if_better: true,
        notes: "continuous training from admin",
      }),
    });
    const payload = await res.json();
    if (!res.ok) {
      throw new Error(payload.detail || `持续训练失败：${res.status}`);
    }
    const active = shortId(payload.active_model?.model_id || "");
    const suffix = payload.activated_count
      ? `，上线 ${payload.activated_count} 次，当前 ${active}`
      : "，没有发现优于当前模型的新版本";
    completeOperationStatus(`持续训练完成：训练 ${payload.completed_count || 0} 个模型${suffix}`);
    finished = true;
    await loadOverview({ silent: true });
    setView(payload.activated_count ? "metrics" : "models");
    return payload;
  } catch (error) {
    showToast(error.message || "持续训练失败");
    await loadOverview({ silent: true });
    throw error;
  } finally {
    if (finished) {
      window.setTimeout(hideOperationStatus, 1000);
    } else {
      hideOperationStatus();
    }
    restoreButtons(buttons);
  }
}

function predictionTradeDate() {
  const value = toTradeDate($("predictionDateInput")?.value);
  if (value) {
    return value;
  }
  return "";
}

function validationTradeDate() {
  const value = toTradeDate($("validationDateInput")?.value);
  if (value) {
    return value;
  }
  return "";
}

async function runPrediction() {
  const tradeDate = predictionTradeDate();
  const button = $("runPredictionBtn");
  button.disabled = true;
  try {
    const body = { limit: 500 };
    if (tradeDate) {
      body.trade_date = tradeDate;
    }
    const res = await fetch("/api/admin/predictions/run", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body),
    });
    const payload = await res.json();
    if (!res.ok) {
      throw new Error(payload.detail || `预测失败：${res.status}`);
    }
    showToast(`已生成 ${payload.count || 0} 条预测`);
    await loadOverview({ silent: true });
  } catch (error) {
    showToast(error.message || "预测失败");
  } finally {
    syncWorkflowButtons();
  }
}

async function runValidation() {
  const tradeDate = validationTradeDate();
  const button = $("runValidationBtn");
  button.disabled = true;
  try {
    const body = {};
    if (tradeDate) {
      body.trade_date = tradeDate;
    }
    const res = await fetch("/api/admin/validations/run", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body),
    });
    const payload = await res.json();
    if (!res.ok) {
      throw new Error(payload.detail || `验证失败：${res.status}`);
    }
    const top50 = payload.ranking?.top_n?.["50"];
    const suffix = top50 ? `，Top50 ${Math.round((top50.hit_rate || 0) * 100)}%` : "";
    showToast(`验证完成，命中率 ${Math.round((payload.hit_rate || 0) * 100)}%${suffix}`);
    await loadOverview({ silent: true });
    setView("monitor");
  } catch (error) {
    showToast(error.message || "验证失败");
  } finally {
    syncWorkflowButtons();
  }
}

async function approveFirstCandidate() {
  const model = firstModel(["candidate"]);
  if (!model) {
    showToast("没有待审核模型");
    return;
  }
  await mutateModel(model.model_id, "approve");
}

async function activateFirstApproved() {
  const model = firstModel(["approved", "inactive"]);
  if (!model) {
    showToast("没有可上线模型");
    return;
  }
  await mutateModel(model.model_id, "activate");
}

async function mutateModel(modelId, action, { reload = true, showSuccessToast = true, showErrorToast = true } = {}) {
  try {
    const res = await fetch(`/api/admin/models/${encodeURIComponent(modelId)}/${action}`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ reason: `manual ${action} from admin` }),
    });
    const payload = await res.json();
    if (!res.ok) {
      throw new Error(payload.detail || `操作失败：${res.status}`);
    }
    const names = {activate: "已上线", approve: "已通过", reject: "已拒绝", deactivate: "已下线", archive: "已归档"};
    if (showSuccessToast) {
      showToast(`${names[action] || "已更新"} ${shortId(modelId)}`);
    }
    if (reload) {
      await loadOverview({ silent: true });
    }
    return payload;
  } catch (error) {
    if (showErrorToast) {
      showToast(error.message || "操作失败");
    }
    throw error;
  }
}

function handleCoachAction(action) {
  const handlers = {
    openBackfill: () => openAdminView("training", "matrix"),
    queueTrain: queueTrainingRun,
    runQueued: runFirstQueuedTraining,
    trainApproveActivate,
    approveCandidate: approveFirstCandidate,
    activateApproved: activateFirstApproved,
    runPrediction,
    runValidation,
  };
  const handler = handlers[action];
  if (handler) {
    handler();
  }
}

function bindOptional(id, eventName, handler) {
  const element = $(id);
  if (element) {
    element.addEventListener(eventName, handler);
  }
}

async function rollbackModel() {
  const button = $("rollbackModelBtn");
  button.disabled = true;
  try {
    const res = await fetch("/api/admin/models/rollback", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ reason: "manual rollback from admin" }),
    });
    const payload = await res.json();
    if (!res.ok) {
      throw new Error(payload.detail || `回滚失败：${res.status}`);
    }
    showToast(`已回滚到 ${shortId(payload.active_model?.model_id || "")}`);
    await loadOverview({ silent: true });
  } catch (error) {
    showToast(error.message || "回滚失败");
  } finally {
    button.disabled = false;
  }
}

window.addEventListener("DOMContentLoaded", () => {
  bindDatePickers();
  bindHelpTooltips();
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", () => setView(item.dataset.view));
  });
  syncViewFromHash();
  window.addEventListener("hashchange", syncViewFromHash);
  setTrainingTab(state.trainingTab);
  bindOptional("refreshBtn", "click", () => loadOverview());
  bindOptional("refreshBtnMetrics", "click", () => loadOverview());
  bindOptional("rollbackModelBtn", "click", rollbackModel);
  bindOptional("rollbackModelBtnModels", "click", rollbackModel);
  bindOptional("queueTrainBtn", "click", queueTrainingRun);
  bindOptional("queueTrainBtnTraining", "click", queueTrainingRun);
  bindOptional("runQueuedBtn", "click", runFirstQueuedTraining);
  bindOptional("runQueuedBtnTraining", "click", runFirstQueuedTraining);
  bindOptional("trainApproveActivateBtn", "click", trainApproveActivate);
  bindOptional("trainApproveActivateBtnTraining", "click", trainApproveActivate);
  bindOptional("backfillHistoryBtn", "click", backfillHistory);
  bindOptional("runTrainingMatrixBtn", "click", runTrainingMatrix);
  bindOptional("runTrainingMatrixBtnTraining", "click", runTrainingMatrix);
  bindOptional("runTrainingMatrixBtnPanel", "click", runTrainingMatrix);
  bindOptional("runContinuousTrainingBtn", "click", runContinuousTraining);
  bindOptional("runContinuousTrainingBtnTraining", "click", runContinuousTraining);
  bindOptional("runContinuousTrainingBtnPanel", "click", runContinuousTraining);
  bindOptional("approveCandidateBtn", "click", approveFirstCandidate);
  bindOptional("activateApprovedBtn", "click", activateFirstApproved);
  bindOptional("runPredictionBtn", "click", runPrediction);
  bindOptional("runValidationBtn", "click", runValidation);
  bindOptional("coachActions", "click", (event) => {
    const button = event.target.closest("[data-coach-action]");
    if (!button) {
      return;
    }
    handleCoachAction(button.dataset.coachAction);
  });
  bindOptional("stepGuide", "click", (event) => {
    const actionButton = event.target.closest("[data-guide-action]");
    if (actionButton) {
      handleCoachAction(actionButton.dataset.guideAction);
      return;
    }
    const viewButton = event.target.closest("[data-guide-view]");
    if (viewButton) {
      openAdminView(viewButton.dataset.guideView, viewButton.dataset.guideTrainingTab || "");
    }
  });
  bindOptional("trainingTabs", "click", (event) => {
    const button = event.target.closest("[data-training-tab]");
    if (!button) {
      return;
    }
    setTrainingTab(button.dataset.trainingTab);
  });
  document.addEventListener("click", (event) => {
    const viewButton = event.target.closest("[data-admin-view]");
    if (viewButton) {
      openAdminView(viewButton.dataset.adminView, viewButton.dataset.adminTrainingTab || "");
      return;
    }
    const tabButton = event.target.closest("[data-training-tab-target]");
    if (tabButton) {
      setTrainingTab(tabButton.dataset.trainingTabTarget);
    }
  });
  bindOptional("modelsBody", "click", (event) => {
    const button = event.target.closest("[data-model-action]");
    if (!button) {
      return;
    }
    mutateModel(button.dataset.modelId, button.dataset.modelAction);
  });
  bindOptional("activeModelPanel", "click", (event) => {
    const button = event.target.closest("[data-model-action]");
    if (!button) {
      return;
    }
    mutateModel(button.dataset.modelId, button.dataset.modelAction);
  });
  bindOptional("modelsPagination", "click", (event) => {
    const button = event.target.closest("[data-model-page-action]");
    if (!button || button.disabled) {
      return;
    }
    changeModelPage(button.dataset.modelPageAction);
  });
  bindOptional("runsBody", "click", (event) => {
    const button = event.target.closest("[data-run-action]");
    if (!button) {
      return;
    }
    runTraining(button.dataset.runId);
  });
  loadOverview({ silent: true });
});
