const grid = document.querySelector("#grid");
const search = document.querySelector("#search");
const sort = document.querySelector("#sort");
const statusFilter = document.querySelector("#statusFilter");
const selectedOnly = document.querySelector("#selectedOnly");
const count = document.querySelector("#count");
const selectedCount = document.querySelector("#selectedCount");
const selectionSummary = document.querySelector("#selectionSummary");
const exportSelection = document.querySelector("#exportSelection");
const clearSelection = document.querySelector("#clearSelection");
const empty = document.querySelector("#empty");

let characters = [];
const STORAGE_KEY = "character-encyclopedia:selected";
let selected = new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"));

const pad = (n) => String(n).padStart(3, "0");
const esc = (value = "") => String(value)
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

function persistSelection() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...selected].sort((a,b) => a-b)));
}

function imageFor(c) {
  return c.images?.normal || c.images?.main || c.images?.graphic || "";
}

function render() {
  const q = search.value.trim().toLowerCase();

  let list = characters.filter((c) => {
    const haystack = [c.nameJa, c.nameEn, c.slug, c.animal, c.concept, ...(c.emotionTheme || []), String(c.id)]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    const searchOK = haystack.includes(q);
    const statusOK = statusFilter.value === "ALL" || (c.status || "MAYBE") === statusFilter.value;
    const selectedOK = !selectedOnly.checked || selected.has(c.id);
    return searchOK && statusOK && selectedOK;
  });

  list.sort((a, b) => {
    if (sort.value === "desc") return b.id - a.id;
    if (sort.value === "name") return (a.nameJa || "").localeCompare(b.nameJa || "", "ja");
    return a.id - b.id;
  });

  count.textContent = `${characters.length} characters`;
  selectedCount.textContent = `${selected.size} selected`;
  selectionSummary.textContent = selected.size
    ? `正式候補 ${selected.size}体を選択中`
    : "正式候補を選択してください";

  empty.hidden = list.length !== 0;

  grid.innerHTML = list.map((c) => {
    const img = imageFor(c);
    const isSelected = selected.has(c.id);
    return `
      <article class="card ${isSelected ? "is-selected" : ""}" data-id="${c.id}">
        <div class="card-top">
          <div class="id">#${pad(c.id)}</div>
          <span class="status status-${esc((c.status || "MAYBE").toLowerCase())}">${esc(c.status || "MAYBE")}</span>
        </div>
        <div class="thumb ${img ? "" : "placeholder"}">
          ${img ? `<img src="${esc(img)}" alt="${esc(c.nameJa)}">` : `<span>#${pad(c.id)}</span>`}
        </div>
        <div class="name-ja">${esc(c.nameJa)}</div>
        <div class="name-en">${esc(c.nameEn)}</div>
        ${c.animal ? `<div class="meta">MOTIF · ${esc(c.animal)}</div>` : ""}
        ${c.concept ? `<p class="concept">${esc(c.concept)}</p>` : ""}
        <button class="select-btn ${isSelected ? "active" : ""}" type="button" data-select="${c.id}" aria-pressed="${isSelected}">
          ${isSelected ? "✓ 正式候補に選択中" : "＋ 正式候補に追加"}
        </button>
      </article>
    `;
  }).join("");

  grid.querySelectorAll("[data-select]").forEach((button) => {
    button.addEventListener("click", () => {
      const id = Number(button.dataset.select);
      if (selected.has(id)) selected.delete(id);
      else selected.add(id);
      persistSelection();
      render();
    });
  });
}

async function init() {
  const res = await fetch("/characters.json", { cache: "no-store" });
  if (!res.ok) throw new Error("characters.json could not be loaded");
  characters = await res.json();

  const validIds = new Set(characters.map(c => c.id));
  selected = new Set([...selected].filter(id => validIds.has(id)));
  persistSelection();
  render();
}

[search, sort, statusFilter, selectedOnly].forEach((el) => {
  el.addEventListener(el === search ? "input" : "change", render);
});

clearSelection.addEventListener("click", () => {
  if (!selected.size) return;
  selected.clear();
  persistSelection();
  render();
});

exportSelection.addEventListener("click", () => {
  const data = characters.filter(c => selected.has(c.id));
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "official-character-selection.json";
  a.click();
  URL.revokeObjectURL(url);
});

init().catch((err) => {
  console.error(err);
  empty.hidden = false;
  empty.textContent = "図鑑データの読み込みに失敗しました。";
});
