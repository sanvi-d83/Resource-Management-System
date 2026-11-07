const units = { Water: "L", Electricity: "kWh" };
const capacities = { Water: 10000, Electricity: 1000 };

function showToast(message, isError = false) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.style.background = isError ? "#a92f3d" : "#17233b";
  el.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => el.classList.remove("show"), 3000);
}

async function api(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}

async function loadLimits() {
  const limits = await api("/api/limits");
  const tbody = document.getElementById("limits-table");
  tbody.innerHTML = "";
  limits.forEach(item => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${item.building_name}</strong><div class="building-id">${item.building_id}</div></td>
      <td>${item.resource}</td>
      <td><input type="number" min="0" max="${capacities[item.resource]}" step="any" value="${item.threshold}" id="limit-${item.building_id}-${item.resource}"></td>
      <td>${units[item.resource]}</td>
      <td><button class="btn primary save-btn" data-building="${item.building_id}" data-resource="${item.resource}">Save</button></td>`;
    tbody.appendChild(tr);
  });
  tbody.querySelectorAll("button[data-building]").forEach(button => {
    button.addEventListener("click", () => saveLimit(button.dataset.building, button.dataset.resource));
  });
}

async function saveLimit(buildingId, resource) {
  const input = document.getElementById(`limit-${buildingId}-${resource}`);
  try {
    const result = await api("/api/limits", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ building_id: buildingId, resource, threshold: input.value })
    });
    showToast(result.message);
  } catch (error) {
    showToast(error.message, true);
  }
}

document.addEventListener("DOMContentLoaded", () => loadLimits().catch(e => showToast(e.message, true)));
