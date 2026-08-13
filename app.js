const state = {
  bootstrap: null,
  dashboard: null,
  selectedObjectId: null,
  selectedPortfolioIds: new Set(),
  requestToken: 0,
  activeModalChartId: null,
};

const refs = {
  heroStatus: document.getElementById("heroStatus"),
  heroMeta: document.getElementById("heroMeta"),
  generatedAt: document.getElementById("generatedAt"),
  globalCards: document.getElementById("globalCards"),
  objectSelect: document.getElementById("objectSelect"),
  areaInput: document.getElementById("areaInput"),
  equipmentCountInput: document.getElementById("equipmentCountInput"),
  equipmentPowerInput: document.getElementById("equipmentPowerInput"),
  refreshButton: document.getElementById("refreshButton"),
  resetButton: document.getElementById("resetButton"),
  scenarioTitle: document.getElementById("scenarioTitle"),
  scenarioText: document.getElementById("scenarioText"),
  portfolioBody: document.getElementById("portfolioBody"),
  compareButton: document.getElementById("compareButton"),
  objectHeading: document.getElementById("objectHeading"),
  objectSubheading: document.getElementById("objectSubheading"),
  statusChips: document.getElementById("statusChips"),
  cheapHours: document.getElementById("cheapHours"),
  expensiveHours: document.getElementById("expensiveHours"),
  benchmarkCards: document.getElementById("benchmarkCards"),
  summaryCards: document.getElementById("summaryCards"),
  recommendations: document.getElementById("recommendations"),
  consumptionChart: document.getElementById("consumptionChart"),
  priceChart: document.getElementById("priceChart"),
  spotComparisonChart: document.getElementById("spotComparisonChart"),
  planChart: document.getElementById("planChart"),
  planTableBody: document.getElementById("planTableBody"),
  dailyTrendChart: document.getElementById("dailyTrendChart"),
  alertsTableBody: document.getElementById("alertsTableBody"),
};

const numberFormat = new Intl.NumberFormat("lv-LV", {
  maximumFractionDigits: 1,
});

const integerFormat = new Intl.NumberFormat("lv-LV", {
  maximumFractionDigits: 0,
});

let inputTimer = null;

initialise().catch((error) => {
  console.error(error);
  refs.heroStatus.textContent = "Kļūda";
  refs.heroStatus.className = "hero-status error";
  refs.scenarioText.textContent = error.message;
});

async function initialise() {
  setLoadingState(true, "Ielādē backend kopsavilkumu...");
  renderChartLoadingState();
  state.bootstrap = await fetchJson("/api/bootstrap");
  state.selectedObjectId = state.bootstrap.defaultObjectId;
  state.selectedPortfolioIds = new Set(state.selectedObjectId ? [state.selectedObjectId] : []);
  populateObjectSelect(state.bootstrap.objects, state.selectedObjectId);
  renderGlobalSummary(state.bootstrap);
  renderPortfolio(state.bootstrap.portfolio);
  wireEvents();
  await refreshDashboard("Aprēķina objekta analītiku...");
}

function wireEvents() {
  refs.objectSelect.addEventListener("change", () => {
    state.selectedObjectId = refs.objectSelect.value;
    state.selectedPortfolioIds.add(state.selectedObjectId);
    renderPortfolio(state.bootstrap.portfolio);
    refreshDashboard("Atjauno objekta skatu...");
  });

  refs.portfolioBody.addEventListener("change", (event) => {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || input.type !== "checkbox") {
      return;
    }

    const objectId = input.dataset.objectId;
    if (!objectId) {
      return;
    }

    if (input.checked) {
      state.selectedPortfolioIds.add(objectId);
    } else {
      state.selectedPortfolioIds.delete(objectId);
      if (state.selectedObjectId === objectId) {
        const nextSelection = Array.from(state.selectedPortfolioIds)[0] || objectId;
        state.selectedObjectId = nextSelection;
        refs.objectSelect.value = nextSelection;
      }
    }

    renderPortfolio(state.bootstrap.portfolio);
  });

  refs.portfolioBody.addEventListener("click", (event) => {
    const checkbox = event.target.closest("input[type='checkbox']");
    if (checkbox) {
      return;
    }

    const row = event.target.closest("tr[data-object-id]");
    if (!row) {
      return;
    }

    const objectId = row.dataset.objectId;
    state.selectedObjectId = objectId;
    state.selectedPortfolioIds.add(objectId);
    refs.objectSelect.value = objectId;
    renderPortfolio(state.bootstrap.portfolio);
    refreshDashboard("Atjauno atlasītā objekta skatu...");
  });

  refs.compareButton.addEventListener("click", () => {
    if (state.selectedPortfolioIds.size === 0) {
      return;
    }

    const nextObjectId = Array.from(state.selectedPortfolioIds)[0];
    state.selectedObjectId = nextObjectId;
    refs.objectSelect.value = nextObjectId;
    renderPortfolio(state.bootstrap.portfolio);
    refreshDashboard("Atjauno atlasīto objektu scenāriju...");
  });

  [refs.areaInput, refs.equipmentCountInput, refs.equipmentPowerInput].forEach((input) => {
    input.addEventListener("input", () => {
      window.clearTimeout(inputTimer);
      inputTimer = window.setTimeout(() => {
        refreshDashboard("Pārrēķina scenāriju...");
      }, 250);
    });
  });

  refs.refreshButton.addEventListener("click", () => {
    refreshDashboard("Piespiedu pārrēķins...");
  });

  refs.resetButton.addEventListener("click", () => {
    refs.areaInput.value = "";
    refs.equipmentCountInput.value = "";
    refs.equipmentPowerInput.value = "";
    refreshDashboard("Atjauno sākotnējo scenāriju...");
  });

  document.querySelectorAll(".chart-card").forEach((card) => {
    card.setAttribute("tabindex", "0");
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", `${card.id ? "Palielināt grafiku" : "Palielināt grafiku"}`);
    card.setAttribute("aria-expanded", "false");
    card.addEventListener("click", () => toggleChartExpansion(card));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggleChartExpansion(card);
      }
    });
  });
}

function toggleChartExpansion(card) {
  if (!card || !card.classList.contains("chart-card")) {
    return;
  }

  const isExpanded = card.classList.toggle("chart-expanded");
  card.setAttribute("aria-expanded", String(isExpanded));

  document.querySelectorAll(".chart-card").forEach((otherCard) => {
    if (otherCard !== card && otherCard.classList.contains("chart-expanded")) {
      otherCard.classList.remove("chart-expanded");
      otherCard.setAttribute("aria-expanded", "false");
    }
  });

  card.title = isExpanded ? "Noklikšķiniet, lai samazinātu" : "Noklikšķiniet, lai palielinātu";
}

async function refreshDashboard(message) {
  if (!state.selectedObjectId) {
    return;
  }

  const token = ++state.requestToken;
  setLoadingState(true, message);
  renderChartLoadingState();
  try {
    const params = new URLSearchParams({
      objectId: state.selectedObjectId,
      area: refs.areaInput.value || "0",
      equipmentCount: refs.equipmentCountInput.value || "0",
      equipmentPowerWatts: refs.equipmentPowerInput.value || "0",
    });

    const dashboard = await fetchJson(`/api/dashboard?${params.toString()}`);
    if (token !== state.requestToken) {
      return;
    }

    state.dashboard = dashboard;
    renderDashboard(dashboard);
    setLoadingState(false, "Backend dati ir aktuāli.");
  } catch (error) {
    if (token !== state.requestToken) {
      return;
    }
    console.error(error);
    refs.scenarioTitle.textContent = "Neizdevās pārrēķināt scenāriju";
    refs.scenarioText.textContent = error.message;
    refs.heroStatus.textContent = "Backend kļūda";
    refs.heroStatus.className = "hero-status error";
    refs.refreshButton.disabled = false;
    renderChartErrorState("Neizdevās ielādēt grafiku datus. Mēģini pārlādēt lapu vai atkārtot pieprasījumu.");
  }
}

function populateObjectSelect(objects, selectedObjectId) {
  refs.objectSelect.innerHTML = objects
    .map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)} (${escapeHtml(item.id)})</option>`)
    .join("");
  refs.objectSelect.value = selectedObjectId;
}

function renderGlobalSummary(bootstrap) {
  refs.generatedAt.textContent = `Datu ģenerēšana: ${formatDateTime(bootstrap.generatedAt)}`;

  const cards = [
    {
      label: "Objekti portfelī",
      value: integerFormat.format(bootstrap.globalSummary.objectCount),
      note: "Atlasāmi frontend vadības panelī.",
    },
    {
      label: "Kopējais gada patēriņš",
      value: `${integerFormat.format(bootstrap.globalSummary.totalConsumption)} kWh`,
      note: "Summa visiem datu faila objektiem.",
    },
    {
      label: "Kopējās izmaksas",
      value: `${integerFormat.format(bootstrap.globalSummary.totalCost)} EUR`,
      note: "Aprēķins pēc vēsturiskajām cenām.",
    },
    {
      label: "Rītdienas vidējā cena",
      value: `${numberFormat.format(bootstrap.globalSummary.averageTomorrowPrice)} €/MWh`,
      note: `Tirgus diena ${bootstrap.tomorrowPriceDate}.`,
    },
  ];

  refs.globalCards.innerHTML = cards
    .map(
      (card) => `
        <article class="global-card">
          <span>${escapeHtml(card.label)}</span>
          <strong>${escapeHtml(card.value)}</strong>
          <small>${escapeHtml(card.note)}</small>
        </article>
      `
    )
    .join("");
}

function renderPortfolio(portfolio) {
  refs.portfolioBody.innerHTML = portfolio
    .map((item) => {
      const active = item.id === state.selectedObjectId ? "is-active" : "";
      const selected = state.selectedPortfolioIds.has(item.id) ? "checked" : "";
      return `
        <tr class="${active}" data-object-id="${escapeHtml(item.id)}">
          <td class="select-cell">
            <label class="checkbox-label">
              <input type="checkbox" data-object-id="${escapeHtml(item.id)}" ${selected} />
              <span>
                <strong>${escapeHtml(item.name)}</strong>
                <small>${escapeHtml(item.id)}</small>
              </span>
            </label>
          </td>
          <td>${escapeHtml(integerFormat.format(item.annualCost))} EUR</td>
          <td>${escapeHtml(integerFormat.format(item.anomalyCount))}</td>
        </tr>
      `;
    })
    .join("");
}

function renderDashboard(dashboard) {
  refs.objectHeading.textContent = `${dashboard.object.name} (${dashboard.object.id})`;
  refs.objectSubheading.textContent = `Objekts ieņem ${dashboard.object.rankByAnnualCost}. vietu no ${dashboard.benchmark.portfolioSize} pēc gada izmaksām.`;
  refs.heroMeta.innerHTML = `
    <span>Patēriņa periods: ${escapeHtml(dashboard.period.consumptionStart)} - ${escapeHtml(dashboard.period.consumptionEnd)}</span>
    <span>Biržas cena: ${escapeHtml(dashboard.period.marketStart)} - ${escapeHtml(dashboard.period.marketEnd)}</span>
    <span>Rītdienas cenu scenārijs: ${escapeHtml(dashboard.period.tomorrowPriceDate)}</span>
  `;

  refs.scenarioTitle.textContent = dashboard.scenarioSummary.title;
  refs.scenarioText.textContent = dashboard.scenarioSummary.text;

  renderStatusChips(dashboard.statusChips);
  renderSignalLists(dashboard.priceSignals);
  renderBenchmark(dashboard.benchmark);
  renderSummaryCards(dashboard.cards);
  renderRecommendations(dashboard.recommendations);
  renderHourlyChart(refs.consumptionChart, dashboard.charts.consumptionHourly, "consumption", dashboard.priceSignals);
  renderHourlyChart(refs.priceChart, dashboard.charts.priceHourly, "price", dashboard.priceSignals);
  renderSpotComparisonChart(dashboard.charts.consumptionHourly, dashboard.charts.priceHourly);
  renderPlanChart(dashboard.planRows);
  renderPlanTable(dashboard.planRows);
  renderDailyTrend(dashboard.charts.dailyTrend);
  renderAlerts(dashboard.alerts);
}

function renderStatusChips(chips) {
  refs.statusChips.innerHTML = chips
    .map((chip) => `<span class="chip ${chip.tone}">${escapeHtml(chip.label)}</span>`)
    .join("");
}

function renderSignalLists(signals) {
  refs.cheapHours.innerHTML = signals.cheapestHours
    .map((item) => `<span class="signal-pill success">${escapeHtml(item.hour)}<strong>${escapeHtml(numberFormat.format(item.price))}</strong></span>`)
    .join("");

  refs.expensiveHours.innerHTML = signals.expensiveHours
    .map((item) => `<span class="signal-pill danger">${escapeHtml(item.hour)}<strong>${escapeHtml(numberFormat.format(item.price))}</strong></span>`)
    .join("");
}

function renderBenchmark(benchmark) {
  const cards = [
    { label: "Portfeļa vieta", value: `${benchmark.portfolioRank}. / ${benchmark.portfolioSize}` },
    { label: "Pārbīdāmā slodze", value: `${numberFormat.format(benchmark.shiftableEnergy)} kWh` },
    { label: "Slodzes samazinājums", value: `${numberFormat.format(benchmark.loadReductionKw)} kW` },
    {
      label: "Uzstādītā jauda",
      value: benchmark.installedPowerKw > 0 ? `${numberFormat.format(benchmark.installedPowerKw)} kW` : "Nav ievadīta",
    },
  ];

  refs.benchmarkCards.innerHTML = cards
    .map(
      (card) => `
        <article class="benchmark-card">
          <span>${escapeHtml(card.label)}</span>
          <strong>${escapeHtml(card.value)}</strong>
        </article>
      `
    )
    .join("");
}

function renderSummaryCards(cards) {
  refs.summaryCards.innerHTML = cards
    .map(
      (card) => `
        <article class="metric-card">
          <span class="metric-label">${escapeHtml(card.label)}</span>
          <strong>${escapeHtml(numberFormat.format(card.value))} ${escapeHtml(card.unit)}</strong>
          <small>${escapeHtml(card.note)}</small>
        </article>
      `
    )
    .join("");
}

function renderRecommendations(recommendations) {
  refs.recommendations.innerHTML = recommendations
    .map(
      (item) => `
        <article class="recommendation ${item.tone}">
          <div class="recommendation-top">
            <h3>${escapeHtml(item.title)}</h3>
            <span class="recommendation-metric">${escapeHtml(item.metric)}</span>
          </div>
          <p>${escapeHtml(item.text)}</p>
        </article>
      `
    )
    .join("");
}

function renderHourlyChart(container, items, mode, signals) {
  if (!Array.isArray(items) || items.length === 0) {
    renderSingleChartState(container, "error", "Šim grafikam nav pieejamu datu.");
    return;
  }

  const maxValue = Math.max(...items.map((item) => item[mode === "consumption" ? "consumption" : "price"]));
  const cheapSet = new Set(signals.cheapestHours.map((item) => item.hour));
  const expensiveSet = new Set(signals.expensiveHours.map((item) => item.hour));

  container.innerHTML = `
    <div class="bars">
      ${items
        .map((item) => {
          const value = item[mode === "consumption" ? "consumption" : "price"];
          const height = Math.max(16, Math.round((value / maxValue) * 190));
          const tone =
            mode === "price" && cheapSet.has(item.hour)
              ? "success"
              : mode === "price" && expensiveSet.has(item.hour)
              ? "danger"
              : mode === "price" && value > signals.averagePrice
              ? "warning"
              : "neutral";
          return `
            <div class="bar-col" title="${escapeHtml(item.hour)} - ${escapeHtml(numberFormat.format(value))}">
              <div class="bar-value">${escapeHtml(numberFormat.format(value))}</div>
              <div class="bar ${tone}" style="height:${height}px"></div>
              <div class="bar-caption">${escapeHtml(item.hour.slice(0, 2))}</div>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderPlanChart(rows) {
  if (!Array.isArray(rows) || rows.length === 0) {
    refs.planChart.innerHTML = `
      <div class="chart-state error">
        <div class="chart-state-icon">!</div>
        <strong>Grafiks nav pieejams</strong>
        <p>Patēriņa plānošana pa stundām šobrīd nav pieejama.</p>
      </div>
    `;
    return;
  }

  const maxConsumption = Math.max(...rows.map((row) => row.consumption), 1);
  const toneClass = {
    success: "success",
    danger: "danger",
    warning: "warning",
    neutral: "neutral",
  };

  refs.planChart.innerHTML = `
    <div class="plan-chart-grid">
      ${rows
        .map((row) => {
          const height = Math.max(18, Math.round((row.consumption / maxConsumption) * 110));
          const tone = toneClass[row.tone] || "neutral";
          return `
            <div class="plan-hour" title="${escapeHtml(row.hour)} — ${escapeHtml(row.action)} (${escapeHtml(numberFormat.format(row.consumption))} kWh / ${escapeHtml(numberFormat.format(row.price))} €/MWh)">
              <span class="plan-value">${escapeHtml(numberFormat.format(row.consumption))}</span>
              <span class="plan-bar ${tone}" style="height:${height}px"></span>
              <span class="plan-label">${escapeHtml(row.hour.slice(0, 2))}</span>
            </div>
          `;
        })
        .join("")}
    </div>
    <div class="mini-legend">
      <span><i class="legend-consumption"></i>Patēriņš</span>
      <span><i class="legend-cost"></i>Darbības ieteikums</span>
    </div>
  `;
}

function renderSpotComparisonChart(consumptionItems, priceItems) {
  if (!Array.isArray(consumptionItems) || !Array.isArray(priceItems) || consumptionItems.length === 0 || priceItems.length === 0) {
    renderSingleChartState(refs.spotComparisonChart, "error", "SPOT profila salīdzinājums nav pieejams.");
    return;
  }

  const consumptionMap = new Map(consumptionItems.map((item) => [item.hour, item.consumption]));
  const maxConsumption = Math.max(...consumptionItems.map((item) => item.consumption), 1);
  const maxPrice = Math.max(...priceItems.map((item) => item.price), 1);

  refs.spotComparisonChart.innerHTML = `
    <div class="comparison-chart">
      ${priceItems
        .map((priceItem) => {
          const hour = priceItem.hour;
          const consumption = consumptionMap.get(hour) ?? 0;
          const consumptionPercent = Math.max(8, Math.round((consumption / maxConsumption) * 100));
          const pricePercent = Math.max(8, Math.round((priceItem.price / maxPrice) * 100));
          return `
            <div class="comparison-step" title="${escapeHtml(hour)} — ${escapeHtml(numberFormat.format(consumption))} kWh / ${escapeHtml(numberFormat.format(priceItem.price))} €/MWh">
              <div class="comparison-bars">
                <span class="comparison-bar comparison-consumption" style="height:${consumptionPercent}%"></span>
                <span class="comparison-bar comparison-price" style="height:${pricePercent}%"></span>
              </div>
              <div class="comparison-label">${escapeHtml(hour.slice(0, 2))}</div>
            </div>
          `;
        })
        .join("")}
    </div>
    <div class="mini-legend">
      <span><i class="legend-consumption"></i>Klienta patēriņš</span>
      <span><i class="legend-price"></i>SPOT cena</span>
    </div>
  `;
}

function renderPlanTable(rows) {
  refs.planTableBody.innerHTML = rows
    .map(
      (row) => `
        <tr>
          <td>${escapeHtml(row.hour)}</td>
          <td>${escapeHtml(numberFormat.format(row.consumption))} kWh</td>
          <td>${escapeHtml(numberFormat.format(row.price))} €/MWh</td>
          <td><span class="table-pill ${row.tone}">${escapeHtml(row.action)}</span></td>
        </tr>
      `
    )
    .join("");
}

function renderDailyTrend(days) {
  if (!Array.isArray(days) || days.length === 0) {
    renderSingleChartState(refs.dailyTrendChart, "error", "Nav pieejamu pēdējo 30 dienu datu.");
    return;
  }

  const maxConsumption = Math.max(...days.map((item) => item.consumption));
  const maxCost = Math.max(...days.map((item) => item.cost));
  refs.dailyTrendChart.innerHTML = `
    <div class="trend">
      ${days
        .map((item) => {
          const consumptionHeight = Math.max(10, Math.round((item.consumption / maxConsumption) * 120));
          const costHeight = Math.max(10, Math.round((item.cost / maxCost) * 90));
          return `
            <div class="trend-day" title="${escapeHtml(item.date)} - ${escapeHtml(
              `${numberFormat.format(item.consumption)} kWh / ${numberFormat.format(item.cost)} EUR`
            )}">
              <div class="trend-bars">
                <span class="trend-consumption" style="height:${consumptionHeight}px"></span>
                <span class="trend-cost" style="height:${costHeight}px"></span>
              </div>
              <div class="trend-label">${escapeHtml(item.date.slice(5))}</div>
            </div>
          `;
        })
        .join("")}
    </div>
    <div class="mini-legend">
      <span><i class="legend-consumption"></i>Patēriņš</span>
      <span><i class="legend-cost"></i>Izmaksas</span>
    </div>
  `;
}

function renderAlerts(alerts) {
  refs.alertsTableBody.innerHTML = alerts
    .map(
      (alert) => `
        <tr>
          <td>${escapeHtml(alert.date)}</td>
          <td>${escapeHtml(alert.hour)}</td>
          <td>${escapeHtml(numberFormat.format(alert.consumption))} kWh</td>
          <td>${escapeHtml(alert.reason)}</td>
        </tr>
      `
    )
    .join("");
}

function renderChartLoadingState() {
  [refs.consumptionChart, refs.priceChart, refs.dailyTrendChart].forEach((container) => {
    renderSingleChartState(container, "loading", "Grafiks tiek ielādēts...");
  });
}

function renderChartErrorState(message) {
  [refs.consumptionChart, refs.priceChart, refs.dailyTrendChart].forEach((container) => {
    renderSingleChartState(container, "error", message);
  });
}

function renderSingleChartState(container, tone, message) {
  container.innerHTML = `
    <div class="chart-state ${tone}">
      <div class="chart-state-icon">${tone === "loading" ? "◌" : "!"}</div>
      <strong>${tone === "loading" ? "Ielāde" : "Grafiks nav pieejams"}</strong>
      <p>${escapeHtml(message)}</p>
    </div>
  `;
}

function setLoadingState(isLoading, message) {
  refs.heroStatus.textContent = message;
  refs.heroStatus.className = isLoading ? "hero-status loading" : "hero-status ready";
  refs.refreshButton.disabled = isLoading;
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    let message = `Pieprasījums neizdevās (${response.status})`;
    try {
      const payload = await response.json();
      if (payload.error) {
        message = payload.error;
      }
    } catch (_error) {
      // Keep the HTTP error message when response is not JSON.
    }
    throw new Error(message);
  }
  return response.json();
}

function formatDateTime(value) {
  return new Date(value).toLocaleString("lv-LV");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
