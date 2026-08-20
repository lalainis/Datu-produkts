const state = {
  bootstrap: null,
  dashboard: null,
  selectedObjectId: null,
  selectedPortfolioIds: new Set(),
  clientType: "office",
  hasSolar: false,
  fixedPriceMode: false,
  requestToken: 0,
  activeModalChartId: null,
};

const refs = {
  appShell: document.getElementById("appShell"),
  startupDialogBackdrop: document.getElementById("startupDialogBackdrop"),
  startupDialog: document.getElementById("startupDialog"),
  startupSourceSelect: document.getElementById("startupSourceSelect"),
  startupClientTypeSelect: document.getElementById("startupClientTypeSelect"),
  startupSolarSelect: document.getElementById("startupSolarSelect"),
  startupImportButton: document.getElementById("startupImportButton"),
  heroStatus: document.getElementById("heroStatus"),
  heroMeta: document.getElementById("heroMeta"),
  generatedAt: document.getElementById("generatedAt"),
  globalCards: document.getElementById("globalCards"),
  sourceSelect: document.getElementById("sourceSelect"),
  clientTypeSelect: document.getElementById("clientTypeSelect"),
  solarSelect: document.getElementById("solarSelect"),
  solarCapacityField: document.getElementById("solarCapacityField"),
  solarCapacityInput: document.getElementById("solarCapacityInput"),
  importSourceButton: document.getElementById("importSourceButton"),
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
  solarSummarySection: document.getElementById("solarSummarySection"),
  solarSummaryCards: document.getElementById("solarSummaryCards"),
  solarRecommendedHours: document.getElementById("solarRecommendedHours"),
  aiConsultantSection: document.getElementById("aiConsultantSection"),
  aiConsultantStatus: document.getElementById("aiConsultantStatus"),
  aiConsultantSummary: document.getElementById("aiConsultantSummary"),
  aiConsultantActions: document.getElementById("aiConsultantActions"),
  aiTomorrowPlan: document.getElementById("aiTomorrowPlan"),
  recommendations: document.getElementById("recommendations"),
  consumptionChart: document.getElementById("consumptionChart"),
  priceChart: document.getElementById("priceChart"),
  spotComparisonChart: document.getElementById("spotComparisonChart"),
  solarComparisonSection: document.getElementById("solarComparisonSection"),
  solarComparisonDescription: document.getElementById("solarComparisonDescription"),
  solarComparisonChart: document.getElementById("solarComparisonChart"),
  planChart: document.getElementById("planChart"),
  planTableBody: document.getElementById("planTableBody"),
  dailyTrendChart: document.getElementById("dailyTrendChart"),
  alertsTableBody: document.getElementById("alertsTableBody"),
  dashboardContent: document.getElementById("dashboardContent"),
  portfolioReportContent: document.getElementById("portfolioReportContent"),
  startupPriceTypeSelect: document.getElementById("startupPriceTypeSelect"),
  startupFixedPriceField: document.getElementById("startupFixedPriceField"),
  startupFixedPriceInput: document.getElementById("startupFixedPriceInput"),
  priceTypeSelect: document.getElementById("priceTypeSelect"),
  fixedPriceField: document.getElementById("fixedPriceField"),
  fixedPriceInput: document.getElementById("fixedPriceInput"),
  priceComparisonSection: document.getElementById("priceComparisonSection"),
  priceComparisonContent: document.getElementById("priceComparisonContent"),
};

const numberFormat = new Intl.NumberFormat("lv-LV", {
  maximumFractionDigits: 1,
});

const integerFormat = new Intl.NumberFormat("lv-LV", {
  maximumFractionDigits: 0,
});

const inputStorageKey = "energy-dashboard-object-inputs-v1";
const clientTypeStorageKey = "energy-dashboard-client-types-v1";
const solarStorageKey = "energy-dashboard-solar-v1";

let inputTimer = null;

initialise().catch((error) => {
  console.error(error);
  refs.heroStatus.textContent = "Kļūda";
  refs.heroStatus.className = "hero-status error";
  refs.scenarioText.textContent = error.message;
});

async function initialise() {
  setLoadingState(true, "Ielādē datu avotu sarakstu...");
  applyBootstrapData(await fetchJson("/api/bootstrap"));
  wireEvents();
  openStartupDialog();
}

function getStoredSolarSelections() {
  const raw = window.localStorage.getItem(solarStorageKey);
  if (!raw) {
    return {};
  }

  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (_error) {
    return {};
  }
}

function setStoredSolarSelections(data) {
  window.localStorage.setItem(solarStorageKey, JSON.stringify(data));
}

function wireEvents() {
  refs.startupSourceSelect.addEventListener("change", () => {
    refs.sourceSelect.value = refs.startupSourceSelect.value;
    const nextType = resolveClientTypeForSource(refs.startupSourceSelect.value);
    applyClientTypeSelection(nextType);
    updateImportButtonState();
  });

  refs.startupClientTypeSelect.addEventListener("change", () => {
    applyClientTypeSelection(refs.startupClientTypeSelect.value);
  });

  refs.startupSolarSelect.addEventListener("change", () => {
    applySolarSelection(refs.startupSolarSelect.value);
  });

  refs.startupPriceTypeSelect.addEventListener("change", () => {
    applyPriceTypeSelection(refs.startupPriceTypeSelect.value);
  });

  refs.startupFixedPriceInput.addEventListener("input", () => {
    refs.fixedPriceInput.value = refs.startupFixedPriceInput.value;
  });

  refs.startupImportButton.addEventListener("click", async () => {
    refs.sourceSelect.value = refs.startupSourceSelect.value;
    applyClientTypeSelection(refs.startupClientTypeSelect.value);
    await importSelectedSource({ force: true, closeStartup: true });
  });

  refs.sourceSelect.addEventListener("change", () => {
    refs.startupSourceSelect.value = refs.sourceSelect.value;
    const nextType = resolveClientTypeForSource(refs.sourceSelect.value);
    applyClientTypeSelection(nextType);
    updateImportButtonState();
  });

  refs.clientTypeSelect.addEventListener("change", () => {
    applyClientTypeSelection(refs.clientTypeSelect.value);
    saveClientTypeSelection();
    refreshDashboard("Pielāgo scenāriju klienta tipam...");
  });

  refs.solarSelect.addEventListener("change", () => {
    applySolarSelection(refs.solarSelect.value);
    saveSolarSelection();
    refreshDashboard("Pielāgo scenāriju SES profilam...");
  });

  refs.priceTypeSelect.addEventListener("change", () => {
    applyPriceTypeSelection(refs.priceTypeSelect.value);
    refreshDashboard("Pielāgo cenas scenāriju...");
  });

  refs.fixedPriceInput.addEventListener("input", () => {
    refs.startupFixedPriceInput.value = refs.fixedPriceInput.value;
    window.clearTimeout(inputTimer);
    inputTimer = window.setTimeout(() => {
      refreshDashboard("Pārrēķina ar fiksēto cenu...");
    }, 400);
  });

  refs.importSourceButton.addEventListener("click", async () => {
    await importSelectedSource();
  });

  refs.objectSelect.addEventListener("change", () => {
    saveCurrentInputs(state.selectedObjectId);
    state.selectedObjectId = refs.objectSelect.value;
    state.selectedPortfolioIds.add(state.selectedObjectId);
    renderPortfolio(state.bootstrap.portfolio);
    restoreSavedInputs(state.selectedObjectId);
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
    updateCompareButton();
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
    saveCurrentInputs(state.selectedObjectId);
    state.selectedObjectId = objectId;
    state.selectedPortfolioIds.add(objectId);
    refs.objectSelect.value = objectId;
    renderPortfolio(state.bootstrap.portfolio);
    updateCompareButton();
    restoreSavedInputs(objectId);
    refreshDashboard("Atjauno atlasītā objekta skatu...");
  });

  refs.compareButton.addEventListener("click", () => {
    if (state.selectedPortfolioIds.size === 0) {
      return;
    }

    if (state.selectedPortfolioIds.size >= 2) {
      openPortfolioReport();
      return;
    }

    saveCurrentInputs(state.selectedObjectId);
    const nextObjectId = Array.from(state.selectedPortfolioIds)[0];
    state.selectedObjectId = nextObjectId;
    refs.objectSelect.value = nextObjectId;
    renderPortfolio(state.bootstrap.portfolio);
    restoreSavedInputs(nextObjectId);
    refreshDashboard("Atjauno atlasīto objektu scenāriju...");
  });

  [refs.areaInput, refs.equipmentCountInput, refs.equipmentPowerInput, refs.solarCapacityInput].forEach((input) => {
    input.addEventListener("input", () => {
      saveCurrentInputs(state.selectedObjectId);
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
    refs.solarCapacityInput.value = "";
    clearSavedInputs(state.selectedObjectId);
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
    const fixedPriceEurKwh = state.fixedPriceMode ? (parseFloat(refs.fixedPriceInput.value) || 0) : 0;
    const params = new URLSearchParams({
      objectId: state.selectedObjectId,
      clientType: state.clientType,
      hasSolar: state.hasSolar ? "yes" : "no",
      area: refs.areaInput.value || "0",
      equipmentCount: refs.equipmentCountInput.value || "0",
      equipmentPowerWatts: refs.equipmentPowerInput.value || "0",
      solarCapacityKw: refs.solarCapacityInput.value || "0",
      fixedPriceEurMwh: fixedPriceEurKwh > 0 ? (fixedPriceEurKwh * 1000).toString() : "0",
    });

    const dashboard = await fetchJson(`/api/dashboard?${params.toString()}`);
    if (token !== state.requestToken) {
      return;
    }

    state.dashboard = dashboard;
    saveCurrentInputs(state.selectedObjectId);
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

function populateSourceSelect(sources, activeFileName) {
  const optionsMarkup = sources
    .map((item) => `<option value="${escapeHtml(item.fileName)}">${escapeHtml(item.label)}</option>`)
    .join("");
  refs.sourceSelect.innerHTML = optionsMarkup;
  refs.startupSourceSelect.innerHTML = optionsMarkup;
  refs.sourceSelect.value = activeFileName;
  refs.startupSourceSelect.value = activeFileName;
  updateImportButtonState();
}

function populateClientTypeSelect(options) {
  const optionsMarkup = options
    .map((item) => `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</option>`)
    .join("");
  refs.clientTypeSelect.innerHTML = optionsMarkup;
  refs.startupClientTypeSelect.innerHTML = optionsMarkup;
  applyClientTypeSelection(resolveClientTypeForSource(state.bootstrap.activeSource.fileName));
}

function populateSolarSelect(options) {
  const optionsMarkup = options
    .map((item) => `<option value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</option>`)
    .join("");
  refs.solarSelect.innerHTML = optionsMarkup;
  refs.startupSolarSelect.innerHTML = optionsMarkup;
  applySolarSelection(resolveSolarForSource(state.bootstrap.activeSource.fileName));
}

function updateImportButtonState() {
  if (!state.bootstrap || !state.bootstrap.activeSource) {
    refs.importSourceButton.disabled = true;
    refs.startupImportButton.disabled = true;
    return;
  }

  refs.importSourceButton.disabled = refs.sourceSelect.value === state.bootstrap.activeSource.fileName;
  refs.startupImportButton.disabled = !refs.startupSourceSelect.value;
}

function applyBootstrapData(bootstrap, preferredObjectId) {
  state.bootstrap = bootstrap;
  const resolvedObjectId = bootstrap.objects.some((item) => item.id === preferredObjectId)
    ? preferredObjectId
    : bootstrap.defaultObjectId;
  state.selectedObjectId = resolvedObjectId;
  state.selectedPortfolioIds = new Set(resolvedObjectId ? [resolvedObjectId] : []);
  populateSourceSelect(bootstrap.availableSources, bootstrap.activeSource.fileName);
  populateClientTypeSelect(bootstrap.clientTypeOptions);
  populateSolarSelect(bootstrap.solarOptions);
  populateObjectSelect(bootstrap.objects, resolvedObjectId);
  renderGlobalSummary(bootstrap);
  renderPortfolio(bootstrap.portfolio);
  updateCompareButton();
  restoreSavedInputs(resolvedObjectId);
}

async function importSelectedSource(options = {}) {
  const { force = false, closeStartup = false } = options;
  if (!state.bootstrap) {
    return;
  }

  const selectedSourceFile = refs.sourceSelect.value;
  const pendingClientType = refs.clientTypeSelect.value;
  const pendingSolarValue = refs.solarSelect.value;
  state.clientType = pendingClientType;
  state.hasSolar = pendingSolarValue === "yes";
  if (!force && selectedSourceFile === state.bootstrap.activeSource.fileName) {
    return;
  }

  saveCurrentInputs(state.selectedObjectId);
  refs.importSourceButton.disabled = true;
  refs.startupImportButton.disabled = true;
  setLoadingState(true, "Importē atlasīto datu failu...");
  renderChartLoadingState();

  try {
    const bootstrap = await fetchJson("/api/source", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        fileName: selectedSourceFile,
      }),
    });
    applyBootstrapData(bootstrap);
    applyClientTypeSelection(pendingClientType);
    applySolarSelection(pendingSolarValue);
    saveClientTypeSelection();
    saveSolarSelection();
    if (closeStartup) {
      closeStartupDialog();
    }
    await refreshDashboard("Aprēķina objekta analītiku...");
  } catch (error) {
    console.error(error);
    refs.heroStatus.textContent = "Importa kļūda";
    refs.heroStatus.className = "hero-status error";
    refs.scenarioTitle.textContent = "Neizdevās importēt datu failu";
    refs.scenarioText.textContent = error.message;
    refs.startupImportButton.disabled = false;
    updateImportButtonState();
  }
}

function openStartupDialog() {
  refs.appShell.classList.add("is-locked");
  refs.startupDialogBackdrop.hidden = false;
  document.body.classList.add("modal-open");
  refs.startupSourceSelect.value = state.bootstrap.activeSource.fileName;
  applyClientTypeSelection(resolveClientTypeForSource(state.bootstrap.activeSource.fileName));
  applySolarSelection(resolveSolarForSource(state.bootstrap.activeSource.fileName));
  updateImportButtonState();
  window.setTimeout(() => {
    refs.startupSourceSelect.focus();
  }, 0);
}

function closeStartupDialog() {
  refs.appShell.classList.remove("is-locked");
  refs.startupDialogBackdrop.hidden = true;
  document.body.classList.remove("modal-open");
}

function getStoredInputs() {
  const raw = window.localStorage.getItem(inputStorageKey);
  if (!raw) {
    return {};
  }

  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (_error) {
    return {};
  }
}

function setStoredInputs(data) {
  window.localStorage.setItem(inputStorageKey, JSON.stringify(data));
}

function readCurrentInputs() {
  return {
    area: refs.areaInput.value,
    equipmentCount: refs.equipmentCountInput.value,
    equipmentPowerWatts: refs.equipmentPowerInput.value,
    solarCapacityKw: refs.solarCapacityInput.value,
  };
}

function applyInputs(inputs) {
  refs.areaInput.value = inputs && Object.prototype.hasOwnProperty.call(inputs, "area") ? inputs.area : "";
  refs.equipmentCountInput.value = inputs && Object.prototype.hasOwnProperty.call(inputs, "equipmentCount") ? inputs.equipmentCount : "";
  refs.equipmentPowerInput.value = inputs && Object.prototype.hasOwnProperty.call(inputs, "equipmentPowerWatts") ? inputs.equipmentPowerWatts : "";
  refs.solarCapacityInput.value = inputs && Object.prototype.hasOwnProperty.call(inputs, "solarCapacityKw") ? inputs.solarCapacityKw : "";
}

function restoreSavedInputs(objectId) {
  const storageKey = getInputStorageObjectKey(objectId);
  if (!storageKey) {
    applyInputs(null);
    return;
  }

  const data = getStoredInputs();
  applyInputs(data[storageKey] || null);
}

function saveCurrentInputs(objectId) {
  const storageKey = getInputStorageObjectKey(objectId);
  if (!storageKey) {
    return;
  }

  const data = getStoredInputs();
  data[storageKey] = readCurrentInputs();
  setStoredInputs(data);
}

function clearSavedInputs(objectId) {
  const storageKey = getInputStorageObjectKey(objectId);
  if (!storageKey) {
    return;
  }

  const data = getStoredInputs();
  delete data[storageKey];
  setStoredInputs(data);
}

function getInputStorageObjectKey(objectId) {
  if (!objectId || !state.bootstrap || !state.bootstrap.activeSource) {
    return null;
  }

  return `${state.bootstrap.activeSource.fileName}:${objectId}`;
}

function getStoredClientTypes() {
  const raw = window.localStorage.getItem(clientTypeStorageKey);
  if (!raw) {
    return {};
  }

  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (_error) {
    return {};
  }
}

function setStoredClientTypes(data) {
  window.localStorage.setItem(clientTypeStorageKey, JSON.stringify(data));
}

function inferClientTypeFromSource(fileName) {
  const normalized = (fileName || "").toLowerCase();
  if (normalized.includes("razot")) {
    return "manufacturing";
  }
  if (normalized.includes("tirdz")) {
    return "retail";
  }
  return "office";
}

function resolveClientTypeForSource(fileName) {
  const storedTypes = getStoredClientTypes();
  return storedTypes[fileName] || inferClientTypeFromSource(fileName);
}

function saveClientTypeSelection() {
  if (!state.bootstrap || !state.bootstrap.activeSource) {
    return;
  }

  const storedTypes = getStoredClientTypes();
  storedTypes[state.bootstrap.activeSource.fileName] = state.clientType;
  setStoredClientTypes(storedTypes);
}

function applyClientTypeSelection(value) {
  state.clientType = value || "office";
  refs.clientTypeSelect.value = state.clientType;
  refs.startupClientTypeSelect.value = state.clientType;
}

function inferSolarFromSource(fileName) {
  return (fileName || "").toLowerCase().includes("ses");
}

function resolveSolarForSource(fileName) {
  const storedSolarSelections = getStoredSolarSelections();
  if (Object.prototype.hasOwnProperty.call(storedSolarSelections, fileName)) {
    return storedSolarSelections[fileName] ? "yes" : "no";
  }
  if (state.bootstrap && state.bootstrap.activeSource && state.bootstrap.activeSource.fileName === fileName) {
    return state.bootstrap.sourceHasSolar ? "yes" : "no";
  }
  return inferSolarFromSource(fileName) ? "yes" : "no";
}

function saveSolarSelection() {
  if (!state.bootstrap || !state.bootstrap.activeSource) {
    return;
  }

  const storedSolarSelections = getStoredSolarSelections();
  storedSolarSelections[state.bootstrap.activeSource.fileName] = state.hasSolar;
  setStoredSolarSelections(storedSolarSelections);
}

function applySolarSelection(value) {
  const normalizedValue = value === "yes" ? "yes" : "no";
  state.hasSolar = normalizedValue === "yes";
  refs.solarSelect.value = normalizedValue;
  refs.startupSolarSelect.value = normalizedValue;
  refs.solarCapacityField.hidden = !state.hasSolar;
  refs.solarCapacityInput.disabled = !state.hasSolar;
}

function applyPriceTypeSelection(value) {
  state.fixedPriceMode = value === "fixed";
  refs.priceTypeSelect.value = value;
  refs.startupPriceTypeSelect.value = value;
  refs.fixedPriceField.hidden = !state.fixedPriceMode;
  refs.startupFixedPriceField.hidden = !state.fixedPriceMode;
  refs.fixedPriceInput.disabled = !state.fixedPriceMode;
  refs.startupFixedPriceInput.disabled = !state.fixedPriceMode;
}

function renderPriceComparison(comparison) {
  if (!refs.priceComparisonSection || !refs.priceComparisonContent) {
    return;
  }
  if (!comparison) {
    refs.priceComparisonSection.hidden = true;
    return;
  }

  refs.priceComparisonSection.hidden = false;

  const diff = comparison.savingsEur;
  const diffLabel = diff > 0
    ? `Biržas cena ir dārgāka par ${numberFormat.format(Math.abs(diff))} EUR`
    : diff < 0
    ? `Fiksētā cena ir dārgāka par ${numberFormat.format(Math.abs(diff))} EUR`
    : "Izmaksas ir vienādas";
  const diffTone = diff > 0 ? "success" : diff < 0 ? "danger" : "neutral";

  const maxCost = Math.max(comparison.marketCostEur, comparison.fixedCostEur, 0.01);
  const marketBar = Math.round((comparison.marketCostEur / maxCost) * 100);
  const fixedBar = Math.round((comparison.fixedCostEur / maxCost) * 100);

  refs.priceComparisonContent.innerHTML = `
    <div class="price-cmp-grid">
      <div class="price-cmp-card">
        <span class="price-cmp-label">Biržas cena (SPOT)</span>
        <strong class="price-cmp-value">${numberFormat.format(comparison.marketCostEur)} EUR</strong>
        <small>${numberFormat.format(comparison.totalConsumptionKwh)} kWh × vidējā tirgus cena</small>
        <div class="price-cmp-bar" style="width:${marketBar}%" aria-hidden="true"></div>
      </div>
      <div class="price-cmp-card">
        <span class="price-cmp-label">Fiksētā cena</span>
        <strong class="price-cmp-value">${numberFormat.format(comparison.fixedCostEur)} EUR</strong>
        <small>${numberFormat.format(comparison.totalConsumptionKwh)} kWh × ${numberFormat.format(comparison.fixedPriceEurKwh * 100)} c/kWh</small>
        <div class="price-cmp-bar price-cmp-bar-fixed" style="width:${Math.min(fixedBar, 100)}%" aria-hidden="true"></div>
      </div>
    </div>
    <p class="price-cmp-verdict ${diffTone}">${escapeHtml(diffLabel)} dienā (${escapeHtml(comparison.date)})</p>
  `;
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
  refs.objectSubheading.textContent = `Objekts ieņem ${dashboard.object.rankByAnnualCost}. vietu no ${dashboard.benchmark.portfolioSize} pēc gada izmaksām. Klienta profils: ${dashboard.clientTypeLabel}. ${dashboard.solarLabel}.`;
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
  renderSolarSummary(dashboard.solarSummary, dashboard.hasSolar);
  renderAiConsultant(dashboard.aiConsultant);
  renderRecommendations(dashboard.recommendations);
  renderHourlyChart(refs.consumptionChart, dashboard.charts.consumptionHourly, "consumption", dashboard.priceSignals);
  renderHourlyChart(refs.priceChart, dashboard.charts.priceHourly, "price", dashboard.priceSignals);
  renderSpotComparisonChart(dashboard.charts.consumptionHourly, dashboard.charts.priceHourly);
  renderSolarComparisonChart(dashboard.charts.solarComparison, dashboard.hasSolar);
  renderPlanChart(dashboard.planRows);
  renderPlanTable(dashboard.planRows);
  renderPriceComparison(dashboard.priceComparison);
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

function renderSolarSummary(solarSummary, hasSolar) {
  refs.solarSummarySection.hidden = !hasSolar;
  refs.solarComparisonSection.hidden = !hasSolar;
  if (!hasSolar) {
    refs.solarSummaryCards.innerHTML = "";
    refs.solarRecommendedHours.innerHTML = "";
    refs.solarComparisonChart.innerHTML = "";
    return;
  }

  refs.solarSummaryCards.innerHTML = solarSummary.cards
    .map(
      (card) => `
        <article class="metric-card solar-metric-card">
          <span class="metric-label">${escapeHtml(card.label)}</span>
          <strong>${escapeHtml(numberFormat.format(card.value))} ${escapeHtml(card.unit)}</strong>
          <small>${escapeHtml(card.note)}</small>
        </article>
      `
    )
    .join("");

  refs.solarRecommendedHours.innerHTML = solarSummary.recommendedHours.length
    ? solarSummary.recommendedHours
        .map(
          (item) =>
            `<span class="signal-pill success">${escapeHtml(item.hour)}<strong>${escapeHtml(numberFormat.format(item.recommendedSelfUsePotential))} kWh</strong></span>`
        )
        .join("")
    : '<span class="signal-pill">Nav noteiktu SES stundu</span>';
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

function renderAiConsultant(aiConsultant) {
  if (!aiConsultant) {
    refs.aiConsultantStatus.textContent = "Nav datu";
    refs.aiConsultantStatus.className = "ai-status-chip warning";
    refs.aiConsultantSummary.textContent = "AI konsultanta dati nav pieejami.";
    refs.aiConsultantActions.innerHTML = "";
    refs.aiTomorrowPlan.innerHTML = "";
    return;
  }

  const toneMap = {
    ready: "success",
    unavailable: "warning",
    disabled: "warning",
    error: "danger",
  };
  const tone = toneMap[aiConsultant.status] || "warning";
  const statusLabel =
    aiConsultant.status === "ready"
      ? `Aktīvs · ${aiConsultant.model}`
      : aiConsultant.status === "disabled"
      ? "Izslēgts"
      : aiConsultant.status === "error"
      ? "Kļūda"
      : "Nav pieejams";

  refs.aiConsultantStatus.textContent = statusLabel;
  refs.aiConsultantStatus.className = `ai-status-chip ${tone}`;
  refs.aiConsultantSummary.textContent = aiConsultant.summary || "AI konsultants neatgrieza kopsavilkumu.";
  refs.aiConsultantActions.innerHTML = (aiConsultant.actions || []).length
    ? aiConsultant.actions
        .map(
          (action) => `
            <article class="ai-action-card">
              <div class="recommendation-top">
                <h3>${escapeHtml(action.title)}</h3>
                <span class="recommendation-metric">${escapeHtml(action.impact || aiConsultant.priority || "")}</span>
              </div>
              <p>${escapeHtml(action.reason)}</p>
            </article>
          `
        )
        .join("")
    : '<div class="ai-empty-state">AI konsultants šobrīd neiedeva papildu darbību sarakstu.</div>';
  refs.aiTomorrowPlan.innerHTML = (aiConsultant.tomorrowPlan || []).length
    ? aiConsultant.tomorrowPlan
        .map(
          (item) => `
            <article class="ai-tomorrow-item">
              <span class="ai-tomorrow-time">${escapeHtml(item.time || "Rīt")}</span>
              <div class="ai-tomorrow-copy">
                <strong>${escapeHtml(item.action)}</strong>
                <p>${escapeHtml(item.why || "")}</p>
              </div>
            </article>
          `
        )
        .join("")
    : '<div class="ai-empty-state">Rītdienas plāns šobrīd nav pieejams.</div>';
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

  renderDualLineChart(refs.spotComparisonChart, {
    primaryItems: consumptionItems,
    secondaryItems: priceItems,
    primaryValueKey: "consumption",
    secondaryValueKey: "price",
    primaryLabel: "Klienta patēriņš",
    secondaryLabel: "SPOT cena",
    secondaryUnit: "€/MWh",
    secondaryLegendClass: "legend-price",
    secondaryLineClass: "comparison-line-price",
    secondaryDotClass: "comparison-dot-price",
  });
}

function renderSolarComparisonChart(chartData, hasSolar) {
  if (!hasSolar) {
    refs.solarComparisonChart.innerHTML = "";
    return;
  }

  const items = Array.isArray(chartData) ? chartData : chartData?.items;
  const secondaryValueKey = Array.isArray(chartData) ? "export" : chartData?.secondaryValueKey || "export";
  const secondaryLabel = Array.isArray(chartData) ? "SES eksports" : chartData?.secondaryLabel || "SES eksports";
  const emptyMessage = Array.isArray(chartData)
    ? "SES eksportam nav pieejamu stundu datu."
    : chartData?.emptyMessage || "SES eksportam nav pieejamu stundu datu.";

  refs.solarComparisonDescription.textContent =
    secondaryValueKey === "forecastGeneration"
      ? "Salīdzina objekta tipisko patēriņu ar prognozēto SES izstrādes līkni, kas aprēķināta no ievadītās SES jaudas."
      : "Salīdzina objekta tipisko patēriņu ar SES eksporta profilu pa stundām.";

  if (!Array.isArray(items) || items.length === 0 || items.every((item) => (item[secondaryValueKey] || 0) <= 0)) {
    renderSingleChartState(refs.solarComparisonChart, "error", emptyMessage);
    return;
  }

  renderDualLineChart(refs.solarComparisonChart, {
    primaryItems: items,
    secondaryItems: items,
    primaryValueKey: "consumption",
    secondaryValueKey,
    primaryLabel: "Patēriņš",
    secondaryLabel,
    secondaryUnit: "kWh",
    secondaryLegendClass: "legend-solar",
    secondaryLineClass: "comparison-line-solar",
    secondaryDotClass: "comparison-dot-solar",
  });
}

function renderDualLineChart(container, config) {
  const {
    primaryItems,
    secondaryItems,
    primaryValueKey,
    secondaryValueKey,
    primaryLabel,
    secondaryLabel,
    secondaryUnit,
    secondaryLegendClass,
    secondaryLineClass,
    secondaryDotClass,
  } = config;

  const primaryMap = new Map(primaryItems.map((item) => [item.hour, item[primaryValueKey]]));
  const maxPrimary = Math.max(...primaryItems.map((item) => item[primaryValueKey]), 1);
  const maxSecondary = Math.max(...secondaryItems.map((item) => item[secondaryValueKey]), 1);
  const points = secondaryItems.map((secondaryItem, index) => {
    const hour = secondaryItem.hour;
    const primaryValue = primaryMap.get(hour) ?? 0;
    const secondaryValue = secondaryItem[secondaryValueKey];
    const x = 36 + index * 46;
    const primaryY = 200 - Math.round((primaryValue / maxPrimary) * 150);
    const secondaryY = 200 - Math.round((secondaryValue / maxSecondary) * 150);
    return {
      hour,
      primaryValue,
      secondaryValue,
      x,
      primaryY,
      secondaryY,
      anchorY: Math.round((primaryY + secondaryY) / 2),
    };
  });

  const primaryPath = points.map((point) => `${point.x},${point.primaryY}`).join(" ");
  const secondaryPath = points.map((point) => `${point.x},${point.secondaryY}`).join(" ");

  container.innerHTML = `
    <div class="comparison-wrapper">
      <svg class="comparison-svg" viewBox="0 0 1100 260" preserveAspectRatio="none" aria-hidden="true">
        <g class="comparison-grid">
          <line x1="20" y1="30" x2="1080" y2="30"></line>
          <line x1="20" y1="70" x2="1080" y2="70"></line>
          <line x1="20" y1="110" x2="1080" y2="110"></line>
          <line x1="20" y1="150" x2="1080" y2="150"></line>
          <line x1="20" y1="190" x2="1080" y2="190"></line>
        </g>
        <polyline class="comparison-line comparison-line-consumption" points="${primaryPath}"></polyline>
        <polyline class="comparison-line ${secondaryLineClass}" points="${secondaryPath}"></polyline>
        ${points
          .map(
            (point) => `
              <circle class="comparison-dot comparison-dot-consumption" cx="${point.x}" cy="${point.primaryY}" r="5"></circle>
              <circle class="comparison-dot ${secondaryDotClass}" cx="${point.x}" cy="${point.secondaryY}" r="5"></circle>
            `
          )
          .join("")}
      </svg>
      <div class="comparison-points">
        ${points
          .map(
            (point) => `
              <button
                type="button"
                class="comparison-point"
                style="left:${(point.x / 1100) * 100}%; top:${(point.anchorY / 260) * 100}%"
                data-hour="${escapeHtml(point.hour)}"
                data-primary-value="${escapeHtml(numberFormat.format(point.primaryValue))}"
                data-secondary-value="${escapeHtml(numberFormat.format(point.secondaryValue))}"
                data-primary-label="${escapeHtml(primaryLabel)}"
                data-secondary-label="${escapeHtml(secondaryLabel)}"
                data-secondary-unit="${escapeHtml(secondaryUnit)}"
                data-x="${point.x}"
                data-y="${point.anchorY}"
                aria-label="${escapeHtml(point.hour)}: ${escapeHtml(primaryLabel)} ${escapeHtml(numberFormat.format(point.primaryValue))} kWh, ${escapeHtml(secondaryLabel)} ${escapeHtml(numberFormat.format(point.secondaryValue))} ${escapeHtml(secondaryUnit)}"
                title="${escapeHtml(point.hour)} — ${escapeHtml(numberFormat.format(point.primaryValue))} kWh / ${escapeHtml(numberFormat.format(point.secondaryValue))} ${escapeHtml(secondaryUnit)}"
              ></button>
            `
          )
          .join("")}
      </div>
      <div class="comparison-tooltip" aria-live="polite" hidden></div>
      <div class="comparison-axis">
        ${points.map((point) => `<span>${escapeHtml(point.hour.slice(0, 2))}</span>`).join("")}
      </div>
    </div>
    <div class="mini-legend">
      <span><i class="legend-consumption"></i>${escapeHtml(primaryLabel)}</span>
      <span><i class="${secondaryLegendClass}"></i>${escapeHtml(secondaryLabel)}</span>
    </div>
  `;

  const wrapper = container.querySelector(".comparison-wrapper");
  const tooltip = container.querySelector(".comparison-tooltip");
  if (!wrapper || !tooltip) {
    return;
  }

  const showTooltip = (target) => {
    const hour = target.getAttribute("data-hour");
    const primaryValue = target.getAttribute("data-primary-value");
    const secondaryValue = target.getAttribute("data-secondary-value");
    const primarySeriesLabel = target.getAttribute("data-primary-label");
    const secondarySeriesLabel = target.getAttribute("data-secondary-label");
    const secondarySeriesUnit = target.getAttribute("data-secondary-unit");
    const x = Number(target.getAttribute("data-x"));
    const y = Number(target.getAttribute("data-y"));
    let left;
    let transform;
    if (x < 150) {
      left = "12px";
      transform = "translate(0, -100%)";
    } else if (x > 950) {
      left = "calc(100% - 12px)";
      transform = "translate(-100%, -100%)";
    } else {
      left = `${(x / 1100) * 100}%`;
      transform = "translate(-50%, -100%)";
    }

    tooltip.innerHTML = `
      <strong>${escapeHtml(hour)}</strong>
      <span>${escapeHtml(primarySeriesLabel)}: ${escapeHtml(primaryValue)} kWh</span>
      <span>${escapeHtml(secondarySeriesLabel)}: ${escapeHtml(secondaryValue)} ${escapeHtml(secondarySeriesUnit)}</span>
    `;
    tooltip.hidden = false;
    tooltip.style.left = left;
    tooltip.style.top = `${Math.max(24, y - 18) / 260 * 100}%`;
    tooltip.style.transform = transform;
  };

  wrapper.addEventListener("pointerover", (event) => {
    const target = event.target.closest(".comparison-point");
    if (!target) {
      return;
    }
    showTooltip(target);
  });

  wrapper.addEventListener("pointermove", (event) => {
    const target = event.target.closest(".comparison-point");
    if (!target) {
      return;
    }
    showTooltip(target);
  });

  wrapper.addEventListener("pointerleave", () => {
    tooltip.hidden = true;
  });
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
  [refs.consumptionChart, refs.priceChart, refs.spotComparisonChart, refs.solarComparisonChart, refs.dailyTrendChart].forEach((container) => {
    renderSingleChartState(container, "loading", "Grafiks tiek ielādēts...");
  });
}

function renderChartErrorState(message) {
  [refs.consumptionChart, refs.priceChart, refs.spotComparisonChart, refs.solarComparisonChart, refs.dailyTrendChart].forEach((container) => {
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

async function fetchJson(url, options = undefined) {
  const response = await fetch(url, options);
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

function updateCompareButton() {
  const count = state.selectedPortfolioIds.size;
  if (count >= 2) {
    refs.compareButton.textContent = `Ģenerēt pārskatu (${count} objekti)`;
    refs.compareButton.classList.add("primary-button");
    refs.compareButton.classList.remove("secondary-button");
  } else {
    refs.compareButton.textContent = "Rādīt scenāriju";
    refs.compareButton.classList.remove("primary-button");
    refs.compareButton.classList.add("secondary-button");
  }
}

async function openPortfolioReport() {
  setLoadingState(true, "Ģenerē portfeļa pārskatu...");
  try {
    const objectIds = Array.from(state.selectedPortfolioIds).join(",");
    const params = new URLSearchParams({
      objectIds,
      clientType: state.clientType,
      hasSolar: state.hasSolar ? "yes" : "no",
      area: refs.areaInput.value || "0",
      equipmentCount: refs.equipmentCountInput.value || "0",
      equipmentPowerWatts: refs.equipmentPowerInput.value || "0",
      solarCapacityKw: refs.solarCapacityInput.value || "0",
    });
    const data = await fetchJson(`/api/portfolio-report?${params.toString()}`);
    renderPortfolioReport(data);
    refs.dashboardContent.hidden = true;
    refs.portfolioReportContent.hidden = false;
    refs.portfolioReportContent.scrollIntoView({ behavior: "smooth", block: "start" });
    setLoadingState(false, "Portfeļa pārskats gatavs.");
  } catch (error) {
    console.error(error);
    setLoadingState(false, "Kļūda ģenerējot pārskatu.");
  }
}

function closePortfolioReport() {
  refs.portfolioReportContent.hidden = true;
  refs.dashboardContent.hidden = false;
}

function renderPortfolioReport(data) {
  const { objects } = data;
  const global = state.bootstrap.globalSummary;

  refs.portfolioReportContent.innerHTML = `
    <div class="report-nav">
      <button class="secondary-button compact-button" id="reportBackButton">← Atpakaļ</button>
      <strong>Portfeļa pārskats · ${objects.length} objekti</strong>
    </div>

    <section class="panel">
      <div class="panel-title-row">
        <div>
          <h2>Portfeļa kopsavilkums</h2>
          <p>Kopējie rādītāji visiem ${escapeHtml(String(global.objectCount))} portfeļa objektiem.</p>
        </div>
      </div>
      <div class="hero-global-grid">
        ${[
          { label: "Objekti portfelī", value: integerFormat.format(global.objectCount), note: "Datu faila kopējais skaits." },
          { label: "Kopējais patēriņš", value: `${integerFormat.format(global.totalConsumption)} kWh`, note: "Visi portfeļa objekti." },
          { label: "Kopējās izmaksas", value: `${integerFormat.format(global.totalCost)} EUR`, note: "Vēsturiskās biržas cenas." },
          { label: "Kopējās anomālijas", value: `${integerFormat.format(global.totalAnomalies)} not.`, note: "Stundas virs limita vai pīķa." },
        ].map((c) => `
          <article class="global-card">
            <span>${escapeHtml(c.label)}</span>
            <strong>${escapeHtml(c.value)}</strong>
            <small>${escapeHtml(c.note)}</small>
          </article>
        `).join("")}
      </div>
    </section>

    <section class="panel">
      <div class="panel-title-row">
        <div>
          <h2>Salīdzinājums pa objektiem</h2>
          <p>Atlasītie ${objects.length} objekti — galvenie rādītāji blakus.</p>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Objekts</th>
              <th>Vieta</th>
              <th>Patēriņš</th>
              <th>Izmaksas</th>
              <th>Pīķis (kWh)</th>
              <th>Ietaupījums</th>
              <th>Anomālijas</th>
              <th>Sl. samazin.</th>
            </tr>
          </thead>
          <tbody>
            ${objects.map((obj) => {
              const consumption = obj.cards[0] ? obj.cards[0].value : 0;
              const cost = obj.cards[1] ? obj.cards[1].value : 0;
              const peak = obj.cards[2] ? obj.cards[2].value : 0;
              const anomalies = obj.cards[5] ? obj.cards[5].value : 0;
              return `
                <tr>
                  <td><strong>${escapeHtml(obj.name)}</strong><br><small>${escapeHtml(obj.id)}</small></td>
                  <td>${escapeHtml(String(obj.rank))}. / ${escapeHtml(String(obj.portfolioSize))}</td>
                  <td>${escapeHtml(integerFormat.format(consumption))} kWh</td>
                  <td>${escapeHtml(integerFormat.format(cost))} EUR</td>
                  <td>${escapeHtml(numberFormat.format(peak))}</td>
                  <td>${escapeHtml(numberFormat.format(obj.potentialSavings))} EUR/d</td>
                  <td>${escapeHtml(String(anomalies))}</td>
                  <td>${escapeHtml(numberFormat.format(obj.loadReductionKw))} kW</td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <div class="panel-title-row">
        <div>
          <h2>Gada izmaksas pa objektiem</h2>
          <p>Vizuāls salīdzinājums — augstāks stabs nozīmē lielākas izmaksas.</p>
        </div>
      </div>
      ${renderReportCostBars(objects)}
    </section>

    ${objects.map((obj) => renderReportObjectSection(obj)).join("")}
  `;

  document.getElementById("reportBackButton").addEventListener("click", closePortfolioReport);
}

function renderReportCostBars(objects) {
  const maxCost = Math.max(...objects.map((obj) => obj.cards[1] ? obj.cards[1].value : 0), 1);
  return `
    <div class="bars">
      ${objects.map((obj) => {
        const cost = obj.cards[1] ? obj.cards[1].value : 0;
        const height = Math.max(20, Math.round((cost / maxCost) * 190));
        const shortName = obj.name.length > 14 ? obj.name.slice(0, 13) + "…" : obj.name;
        return `
          <div class="bar-col" title="${escapeHtml(obj.name)}: ${escapeHtml(integerFormat.format(cost))} EUR">
            <div class="bar-value">${escapeHtml(integerFormat.format(cost))}</div>
            <div class="bar neutral" style="height:${height}px"></div>
            <div class="bar-caption" style="font-size:0.6rem">${escapeHtml(shortName)}</div>
          </div>
        `;
      }).join("")}
    </div>
  `;
}

function renderReportObjectSection(obj) {
  const chips = (obj.statusChips || [])
    .map((chip) => `<span class="chip ${chip.tone}">${escapeHtml(chip.label)}</span>`)
    .join("");

  const cards = (obj.cards || [])
    .map((card) => `
      <article class="metric-card">
        <span class="metric-label">${escapeHtml(card.label)}</span>
        <strong>${escapeHtml(numberFormat.format(card.value))} ${escapeHtml(card.unit)}</strong>
        <small>${escapeHtml(card.note)}</small>
      </article>
    `).join("");

  const recs = (obj.recommendations || [])
    .map((rec) => `
      <article class="recommendation ${rec.tone}">
        <div class="recommendation-top">
          <h3>${escapeHtml(rec.title)}</h3>
          <span class="recommendation-metric">${escapeHtml(rec.metric)}</span>
        </div>
        <p>${escapeHtml(rec.text)}</p>
      </article>
    `).join("");

  const solarChip = obj.hasSolar ? '<span class="chip success">SES</span>' : "";

  return `
    <section class="panel">
      <div class="panel-title-row">
        <div>
          <h2>${escapeHtml(obj.name)}</h2>
          <p>${escapeHtml(obj.rank)}. vieta portfelī · ${escapeHtml(obj.clientTypeLabel)} · Periods: ${escapeHtml(obj.period.start)} – ${escapeHtml(obj.period.end)}</p>
        </div>
      </div>
      <div class="chip-row">
        ${solarChip}
        ${chips}
      </div>
      <div class="card-grid" style="margin-top:1rem">${cards}</div>
      <div class="recommendations" style="margin-top:1rem">${recs}</div>
    </section>
  `;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
