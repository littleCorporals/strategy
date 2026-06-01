const state = {
  overview: null,
  diagnostics: null,
  loading: false,
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
  return raw.length > 18 ? `${raw.slice(0, 15)}...` : raw;
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

function showToast(message) {
  const toast = $("toast");
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 2200);
}

function emptyRow(message, columns) {
  return `<tr><td colspan="${columns}"><div class="empty">${message}</div></td></tr>`;
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
    body.innerHTML = emptyRow("还没有模型。先点击“新建训练任务”，再点击“执行待训练任务”。", 6);
    return;
  }
  body.innerHTML = models
    .map(
      (item) => `
        <tr>
          <td title="${escapeHtml(item.model_id)}">${escapeHtml(shortId(item.name || item.model_id))}</td>
          <td>${badge(item.status)}</td>
          <td>${escapeHtml(item.feature_set)}</td>
          <td>${escapeHtml(item.label_set)}</td>
          <td>${escapeHtml(item.created_at)}</td>
          <td>${modelActions(item)}</td>
        </tr>
      `,
    )
    .join("");
}

function renderRuns(runs) {
  const body = $("runsBody");
  if (!runs.length) {
    body.innerHTML = emptyRow("还没有训练任务。点击上方“新建训练任务”即可开始。", 6);
    return;
  }
  body.innerHTML = runs
    .map(
      (item) => `
        <tr>
          <td title="${escapeHtml(item.run_id)}">${escapeHtml(shortId(item.run_id))}</td>
          <td>${badge(item.status)}</td>
          <td>${escapeHtml(item.dataset_version)}</td>
          <td>${escapeHtml(item.feature_set)}</td>
          <td>${escapeHtml(item.created_at)}</td>
          <td>${runActions(item)}</td>
        </tr>
      `,
    )
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
  input.placeholder = value ? `自动：${value}` : "暂无推荐日期";
  if (input.dataset.autofilled === "true" && value) {
    input.value = value;
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

function syncWorkflowButtons() {
  if (state.overview) {
    renderWorkflow(state.overview);
  }
}

function renderOverview(payload) {
  const models = payload.models || [];
  const runs = payload.training_runs || [];
  const stages = payload.pipelines?.stages || [];
  const activeModel = payload.active_model;

  $("activeModel").textContent = activeModel?.name || activeModel?.model_id || "暂无";
  $("modelCount").textContent = models.length;
  $("runCount").textContent = runs.length;
  $("stageCount").textContent = stages.length;

  renderModels(models);
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
}

function findFirst(items, statuses) {
  return (items || []).find((item) => statuses.includes(item.status));
}

function setStep(activeStep) {
  document.querySelectorAll(".step-card").forEach((item) => {
    item.classList.toggle("active", item.dataset.step === activeStep);
  });
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

function renderCoach(payload) {
  const models = payload.models || [];
  const runs = payload.training_runs || [];
  const hasActive = Boolean(payload.active_model);
  const queued = findFirst(runs, ["queued", "failed"]);
  const candidate = findFirst(models, ["candidate"]);
  const approved = findFirst(models, ["approved"]);
  const performance = payload.model_performance || [];
  const hasValidation = performance.some((item) => Number(item.validation_count || 0) > 0);
  const actions = $("coachActions");

  if (queued) {
    $("coachTitle").textContent = "有训练任务等待执行";
    $("coachText").textContent = "点击执行后，系统会从本地历史行情里生成一个候选模型。";
    actions.innerHTML = `<button type="button" data-coach-action="runQueued">执行训练</button>`;
    setStep("train");
    return;
  }
  if (candidate) {
    $("coachTitle").textContent = "有候选模型等待审核";
    $("coachText").textContent = "新手可以先点通过，后面再用表现数据决定是否保留。";
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

function topMetric(item, size = "50") {
  return item.ranking?.top_n?.[size] || null;
}

function metricRow(label, value) {
  return `
    <div class="metric-detail-item">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function kpi(label, value) {
  return `
    <div class="metric-kpi">
      <span>${escapeHtml(label)}</span>
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

function scoreCard(label, value, hint, tone = "neutral") {
  return `
    <div class="score-card ${escapeHtml(tone)}">
      <span>${escapeHtml(label)}</span>
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
              <div class="ranking-bar" style="--value: ${hitRate}; --market: ${market};">
                <span class="ranking-bar-fill"></span>
                <span class="ranking-market"></span>
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
          <small class="${tone}">提升 ${escapeHtml(signedPct(lift !== null ? lift * 100 : null))}</small>
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
          <div class="weight-bar-track" style="--weight: ${width};">
            <span class="weight-bar-fill"></span>
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
          kpi("训练样本", text(metrics.sample_count)),
          kpi("特征数", text(diagnostics.feature_count)),
          kpi("验证 F1", percent(validation.f1 ?? metrics.f1)),
          kpi("Top50", percent(top50?.hit_rate)),
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
          scoreCard("Accuracy", percent(validation.accuracy), "验证集整体判断", "neutral"),
          scoreCard("Precision", percent(validation.precision), "预测为正时命中率", "neutral"),
          scoreCard("Recall", percent(validation.recall), "正例覆盖能力", "neutral"),
          scoreCard("F1", percent(validation.f1 ?? metrics.f1), "精确率与召回率平衡", "positive"),
        ].join("")
      : `<div class="empty">暂无训练指标</div>`;
  }

  const trainingBody = $("trainingMetricBody");
  if (trainingBody) {
    trainingBody.innerHTML = [
      metricRow("Log Loss", decimal(validation.log_loss, 6)),
      metricRow("验证样本", text(metrics.validation_sample_count)),
      metricRow("正例率", percent(validation.positive_rate)),
    ].join("");
  }

  const rankingBody = $("rankingMetricBody");
  if (rankingBody) {
    rankingBody.innerHTML = renderRankingSummary(topN);
  }

  const processBody = $("trainingProcessBody");
  if (processBody) {
    processBody.innerHTML = [
      metricRow("训练轮次", text(training.iterations)),
      metricRow("最佳轮次", text(training.best_iteration)),
      metricRow("最佳验证 Log Loss", decimal(training.best_validation_log_loss, 6)),
      metricRow("非零权重", text(diagnostics.non_zero_weight_count)),
    ].join("");
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
  const button = $("queueTrainBtn");
  button.disabled = true;
  try {
    const item = await createTrainingRun();
    showToast(`已创建任务 ${shortId(item?.run_id || "")}`);
    await loadOverview({ silent: true });
  } catch (error) {
    showToast(error.message || "创建失败");
  } finally {
    button.disabled = false;
  }
}

function firstRun(statuses) {
  return findFirst(state.overview?.training_runs || [], statuses);
}

function firstModel(statuses) {
  return findFirst(state.overview?.models || [], statuses);
}

async function runFirstQueuedTraining() {
  const run = firstRun(["queued", "failed"]);
  if (!run) {
    showToast("没有待执行的训练任务");
    return;
  }
  await runTraining(run.run_id);
}

async function runTraining(runId, { reload = true } = {}) {
  try {
    const res = await fetch(`/api/admin/training-runs/${encodeURIComponent(runId)}/run`, {
      method: "POST",
    });
    const payload = await res.json();
    if (!res.ok) {
      throw new Error(payload.detail || `执行失败：${res.status}`);
    }
    showToast(`训练完成 ${shortId(payload.model?.model_id || "")}`);
    if (reload) {
      await loadOverview({ silent: true });
    }
    return payload;
  } catch (error) {
    showToast(error.message || "执行失败");
    throw error;
  }
}

async function trainApproveActivate() {
  const button = $("trainApproveActivateBtn");
  button.disabled = true;
  try {
    showToast("正在创建训练任务");
    const run = await createTrainingRun();
    showToast("正在训练模型");
    const trained = await runTraining(run.run_id, { reload: false });
    const modelId = trained?.model?.model_id;
    if (!modelId) {
      throw new Error("训练完成但没有返回模型编号");
    }
    showToast("正在通过候选模型");
    await mutateModel(modelId, "approve", { reload: false });
    showToast("正在上线模型");
    await mutateModel(modelId, "activate", { reload: false });
    await loadOverview({ silent: true });
    setView("predict");
    showToast("模型已上线，可以生成预测");
  } catch (error) {
    showToast(error.message || "一键流程失败");
    await loadOverview({ silent: true });
  } finally {
    button.disabled = false;
  }
}

function predictionTradeDate() {
  const value = $("predictionDateInput")?.value.trim();
  if (value) {
    return value;
  }
  return "";
}

function validationTradeDate() {
  const value = $("validationDateInput")?.value.trim();
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

async function mutateModel(modelId, action, { reload = true } = {}) {
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
    showToast(`${names[action] || "已更新"} ${shortId(modelId)}`);
    if (reload) {
      await loadOverview({ silent: true });
    }
    return payload;
  } catch (error) {
    showToast(error.message || "操作失败");
    throw error;
  }
}

function handleCoachAction(action) {
  const handlers = {
    queueTrain: queueTrainingRun,
    runQueued: runFirstQueuedTraining,
    trainApproveActivate,
    approveCandidate: approveFirstCandidate,
    activateApproved: activateFirstApproved,
    runPrediction,
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
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", () => setView(item.dataset.view));
  });
  const initialView = window.location.hash.replace("#", "");
  if (initialView) {
    setView(initialView);
  }
  bindOptional("refreshBtn", "click", () => loadOverview());
  bindOptional("refreshBtnMetrics", "click", () => loadOverview());
  bindOptional("rollbackModelBtn", "click", rollbackModel);
  bindOptional("rollbackModelBtnModels", "click", rollbackModel);
  bindOptional("queueTrainBtn", "click", queueTrainingRun);
  bindOptional("queueTrainBtnTraining", "click", queueTrainingRun);
  bindOptional("runQueuedBtn", "click", runFirstQueuedTraining);
  bindOptional("trainApproveActivateBtn", "click", trainApproveActivate);
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
  bindOptional("modelsBody", "click", (event) => {
    const button = event.target.closest("[data-model-action]");
    if (!button) {
      return;
    }
    mutateModel(button.dataset.modelId, button.dataset.modelAction);
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
