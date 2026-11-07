let historyChart;
let buildingsCache = [];

const number = (value) => Number(value).toLocaleString("en-IN", { maximumFractionDigits: 1 });
const unitLabel = (resource) => resource === "Water" ? "L" : "kWh";

function toast(message) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove("show"), 3200);
}

async function getJSON(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Something went wrong");
  return data;
}

function renderBuildings(buildings) {
  const grid = document.getElementById("building-grid");
  let water = 0, electricity = 0, low = 0;
  grid.innerHTML = "";
  buildings.forEach(building => {
    const w = building.resources.Water;
    const e = building.resources.Electricity;
    water += w.value;
    electricity += e.value;
    if (w.status === "Low") low++;
    if (e.status === "Low") low++;
    const card = document.createElement("article");
    card.className = "building-card";
    card.innerHTML = `
      <div class="building-head">
        <div><div class="building-name">${building.name}</div><div class="building-id">${building.id}</div></div>
        <span class="status-pill ${w.status === "Low" || e.status === "Low" ? "status-low" : "status-ok"}">${w.status === "Low" || e.status === "Low" ? "Needs attention" : "All normal"}</span>
      </div>
      ${resourceMarkup("Water", w)}
      ${resourceMarkup("Electricity", e)}
    `;
    grid.appendChild(card);
  });
  document.getElementById("total-water").textContent = `${number(water)} L`;
  document.getElementById("total-electricity").textContent = `${number(electricity)} kWh`;
  document.getElementById("building-count").textContent = buildings.length;
  document.getElementById("low-count").textContent = low;
  document.getElementById("last-updated").textContent = `Updated ${new Date().toLocaleTimeString()}`;
}

function resourceMarkup(name, data) {
  const percent = Math.max(0, Math.min(100, data.capacity ? data.value / data.capacity * 100 : 0));
  const low = data.status === "Low";
  return `<div class="resource-row">
    <div class="resource-line"><span class="resource-name">${name}</span><span class="resource-value" style="color:${low ? '#d94d5c' : '#26344c'}">${number(data.value)} ${data.unit}</span></div>
    <div class="progress"><span class="${name === 'Electricity' ? 'electric' : ''}" style="width:${percent}%;background:${low ? '#d94d5c' : ''}"></span></div>
    <div class="resource-meta"><span>Minimum: ${number(data.threshold)} ${data.unit}</span><span>${percent.toFixed(0)}% of capacity</span></div>
  </div>`;
}

async function loadOverview() {
  buildingsCache = await getJSON("/api/overview");
  renderBuildings(buildingsCache);
  const select = document.getElementById("chart-building");
  const selected = select.value;
  if (select.options.length === 0) {
    buildingsCache.forEach(b => select.add(new Option(`${b.name} (${b.id})`, b.id)));
  }
  if (selected && buildingsCache.some(b => b.id === selected)) select.value = selected;
}

async function loadHistory() {
  const building = document.getElementById("chart-building").value || "B001";
  const resource = document.getElementById("chart-resource").value;
  const data = await getJSON(`/api/history?building_id=${encodeURIComponent(building)}&resource=${encodeURIComponent(resource)}`);
  const ctx = document.getElementById("history-chart").getContext("2d");
  if (historyChart) historyChart.destroy();
  const color = resource === "Water" ? "#3298d4" : "#e5a638";
  historyChart = new Chart(ctx, {
    type: "line",
    data: { labels: data.labels, datasets: [{
      label: `${resource} (${unitLabel(resource)})`, data: data.values,
      borderColor: color, backgroundColor: resource === "Water" ? "rgba(50,152,212,.10)" : "rgba(229,166,56,.12)",
      fill: true, tension: .35, pointRadius: 2, pointHoverRadius: 5, borderWidth: 2
    }]},
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { maxTicksLimit: 7, color: "#98a3b5", font: { size: 9 } } },
        y: { grid: { color: "#f0f2f6" }, ticks: { color: "#98a3b5", font: { size: 9 } } }
      }
    }
  });
}

async function loadAlerts() {
  const alerts = await getJSON("/api/alerts");
  document.getElementById("alert-count").textContent = alerts.length;
  const list = document.getElementById("alerts-list");
  if (!alerts.length) {
    list.innerHTML = '<p class="muted empty-state">No alerts recorded yet. Alerts appear when a resource falls below its limit.</p>';
    return;
  }
  list.innerHTML = alerts.slice(0, 8).map(a => `
    <div class="alert-item"><i class="alert-dot"></i><div>
      <strong>${a.resource} level low · ${a.building_name}</strong>
      <p>${a.current_value} (minimum ${a.threshold})</p>
      <p>${a.email_status}</p>
      <div class="alert-time">${new Date(a.created_at).toLocaleString()}</div>
    </div></div>`).join("");
}

async function refreshAll() {
  try {
    await loadOverview();
    await loadHistory();
    await loadAlerts();
  } catch (error) { toast(error.message); }
}

async function simulate() {
  try {
    const result = await getJSON("/api/simulate", { method: "POST" });
    await refreshAll();
    toast(result.new_alerts.length ? `${result.new_alerts.length} new low-resource alert(s) created.` : "New simulated readings generated.");
  } catch (error) { toast(error.message); }
}

document.addEventListener("DOMContentLoaded", async () => {
  document.getElementById("current-date").textContent = new Date().toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" });
  document.getElementById("chart-building").addEventListener("change", loadHistory);
  document.getElementById("chart-resource").addEventListener("change", loadHistory);
  document.getElementById("simulate-now").addEventListener("click", simulate);
  await refreshAll();
  // Demo polling: each cycle asks the backend to generate fresh simulated readings.
  setInterval(async () => {
    try {
      await getJSON("/api/simulate", { method: "POST" });
      await refreshAll();
    } catch (error) { console.error(error); }
  }, 10000);
});
