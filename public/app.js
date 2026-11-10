const grid = document.querySelector("#grid");
const search = document.querySelector("#search");
const sort = document.querySelector("#sort");
const statusFilter = document.querySelector("#statusFilter");
const selectedOnly = document.querySelector("#selectedOnly");
const latestOnly = document.querySelector("#latestOnly");
const count = document.querySelector("#count");
const selectedCount = document.querySelector("#selectedCount");
const selectionSummary = document.querySelector("#selectionSummary");
const exportSelection = document.querySelector("#exportSelection");
const clearSelection = document.querySelector("#clearSelection");
const empty = document.querySelector("#empty");

let characters = [];
const SOURCE = document.body.dataset.source || "chatgpt";
const DATA_URL = document.body.dataset.dataUrl || "/characters.json";
// Shared across ChatGPT, Gemini and OFFICIAL on this browser.
// Source-prefixed keys avoid collisions between independently numbered archives.
const STORAGE_KEY = "character-encyclopedia:official-selection:v2";
const keyFor = (c) => `${c._archive || SOURCE}:${c.slug || c.id}`;
let selected;
try { selected = new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]")); }
catch { selected = new Set(); }
if (![...selected].every(x => typeof x === "string")) selected = new Set();

const NAME_DRAFT_KEY = "character-encyclopedia:name-drafts:v1";
let nameDrafts = {};
try { nameDrafts = JSON.parse(localStorage.getItem(NAME_DRAFT_KEY) || "{}") || {}; }
catch { nameDrafts = {}; }
function applyNameDraft(c) {
  const draft = nameDrafts[keyFor(c)];
  if (!draft) return c;
  return {...c, nameJa: draft.nameJa, nameEn: draft.nameEn};
}
function downloadNameDrafts() {
  const edits = Object.entries(nameDrafts).map(([key, names]) => ({
    key, nameJa:names.nameJa, nameEn:names.nameEn
  }));
  const blob = new Blob([JSON.stringify({version:1, edits}, null, 2)], {type:"application/json"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "character-name-revisions.json";
  a.click();
  URL.revokeObjectURL(url);
}
function editNames(c) {
  const nameJa = prompt("日本語名（正式IDは変わりません）", c.nameJa);
  if (nameJa === null) return;
  const ja = nameJa.trim();
  if (!ja || ja.length > 80) { alert("日本語名は1〜80文字で入力してください。"); return; }
  const nameEn = prompt("英語名", c.nameEn || "");
  if (nameEn === null) return;
  const en = nameEn.trim();
  if (!en || en.length > 80) { alert("英語名は1〜80文字で入力してください。"); return; }
  nameDrafts[keyFor(c)] = {nameJa:ja, nameEn:en};
  try { localStorage.setItem(NAME_DRAFT_KEY, JSON.stringify(nameDrafts)); }
  catch { alert("このブラウザには保存できませんでした。"); return; }
  characters = characters.map(item => keyFor(item) === keyFor(c) ? applyNameDraft(item) : item);
  render();
  alert("名前の改訂案をこのブラウザに保存しました。正式反映にはJSONの登録が必要です。");
}
const pad = (n) => String(n).padStart(3, "0");
const esc = (value = "") => String(value)
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

function persistSelection() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...selected].sort()));
}

function imageFor(c) {
  return c.images?.normal || c.images?.main || c.images?.graphic || "";
}

function legacyStyle(c, img) {
  const crop = c.legacyCrop;
  if (!crop) return "";
  const sizeX = 10000 / crop.w;
  const sizeY = 10000 / crop.h;
  const posX = crop.x === 0 ? 0 : (crop.x / (100 - crop.w)) * 100;
  const posY = crop.y === 0 ? 0 : (crop.y / (100 - crop.h)) * 100;
  return `background-image:url('${img}');background-size:${sizeX}% ${sizeY}%;background-position:${posX}% ${posY}%;`;
}


function openDetail(c) {
  let modal = document.querySelector("#characterModal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "characterModal";
    modal.className = "modal";
    modal.innerHTML = `
      <div class="modal-backdrop" data-close-modal></div>
      <section class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
        <button class="modal-close" type="button" data-close-modal aria-label="閉じる">×</button>
        <div id="modalContent"></div>
      </section>`;
    document.body.appendChild(modal);
    modal.addEventListener("click", (e) => {
      if (e.target.matches("[data-close-modal]")) closeDetail();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeDetail();
    });
  }

  const main = c.images?.main || c.images?.normal || c.images?.graphic || "";
  const normal = c.images?.normal || "";
  const graphic = c.images?.graphic || "";
  const content = modal.querySelector("#modalContent");

  const renderImg = (src, label) => {
    if (!src) return "";
    if (c.legacyCrop && src.includes("legacy_archive")) {
      return `<div class="detail-image legacy-image" role="img" aria-label="${esc(label)}" style="${legacyStyle(c, src)}"></div>`;
    }
    return `<img class="detail-image" src="${esc(src)}" alt="${esc(label)}">`;
  };

  content.innerHTML = `
    <div class="detail-head">
      <div class="id">#${pad(c.id)}</div>
      <h2 id="modalTitle">${esc(c.nameJa)}</h2>
      <div class="name-en">${esc(c.nameEn)}</div>
      ${c.animal ? `<div class="meta">MOTIF · ${esc(c.animal)}</div>` : ""}
    </div>
    <div class="detail-gallery">
      ${renderImg(main, c.nameJa)}
      ${normal && normal !== main ? renderImg(normal, c.nameJa + " 通常版") : ""}
      ${graphic && graphic !== main ? renderImg(graphic, c.nameJa + " グラフィック版") : ""}
      ${c.regeneratedDraft ? `<div class="draft-block"><div class="draft-label">REGENERATED DRAFT</div>${renderImg(c.regeneratedDraft, c.nameJa + " 再生成ドラフト")}</div>` : ""}
    </div>
    ${c.concept ? `<p class="detail-concept">${esc(c.concept)}</p>` : ""}
    ${(c.emotionTheme || []).length ? `<div class="detail-tags">${c.emotionTheme.map(t=>`<span>${esc(t)}</span>`).join("")}</div>` : ""}
  `;

  modal.classList.add("open");
  document.body.classList.add("modal-open");
}

function closeDetail() {
  const modal = document.querySelector("#characterModal");
  if (modal) modal.classList.remove("open");
  document.body.classList.remove("modal-open");
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
    const selectedOK = !selectedOnly.checked || selected.has(keyFor(c));
    const maxId = characters.length ? Math.max(...characters.map(x => Number(x.id) || 0)) : 0;
    const latestOK = !latestOnly.checked || c.id >= Math.max(1, maxId - 6);
    return searchOK && statusOK && selectedOK && latestOK;
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
    const isSelected = selected.has(keyFor(c));
    return `
      <article class="card ${isSelected ? "is-selected" : ""}" data-id="${c.id}" tabindex="0" role="button" aria-label="${esc(c.nameJa)} の詳細を開く">
        <div class="card-top">
          <div class="id">#${pad(c.id)}</div>
          <span class="status status-${esc((c.status || "MAYBE").toLowerCase())}">${esc(c.status || "MAYBE")}</span>
        </div>
        <div class="thumb ${img ? "" : "placeholder"}">
          ${img ? (c.legacyCrop
            ? `<div class="legacy-image" role="img" aria-label="${esc(c.nameJa)}" style="${legacyStyle(c, img)}"></div>`
            : `<img src="${esc(img)}" alt="${esc(c.nameJa)}">`)
          : `<span>#${pad(c.id)}</span>`}
        </div>
        <div class="name-ja">${esc(c.nameJa)}</div>
        <div class="name-en">${esc(c.nameEn)}</div>
        ${c.animal ? `<div class="meta">MOTIF · ${esc(c.animal)}</div>` : ""}
        ${c.concept ? `<p class="concept">${esc(c.concept)}</p>` : ""}
        <button class="name-edit-btn" type="button" data-edit="${esc(keyFor(c))}" aria-label="${esc(c.nameJa)} の名前を編集">✎ NAME</button>
        <button class="select-btn ${isSelected ? "active" : ""}" type="button" data-select="${esc(keyFor(c))}" aria-pressed="${isSelected}">
          ${isSelected ? "✓ SELECTED" : "＋SELECT"}
        </button>
      </article>
    `;
  }).join("");

  grid.querySelectorAll(".card").forEach((card) => {
    const id = Number(card.dataset.id);
    const character = characters.find(c => c.id === id);
    card.addEventListener("click", (e) => {
      if (e.target.closest("[data-select], [data-edit]")) return;
      openDetail(character);
    });
    card.addEventListener("keydown", (e) => {
      if ((e.key === "Enter" || e.key === " ") && !e.target.closest("[data-select], [data-edit]")) {
        e.preventDefault();
        openDetail(character);
      }
    });
  });

  grid.querySelectorAll("[data-edit]").forEach((button) => {
    button.addEventListener("click", () => {
      const c = characters.find(item => keyFor(item) === button.dataset.edit);
      if (c) editNames(c);
    });
  });

  grid.querySelectorAll("[data-select]").forEach((button) => {
    button.addEventListener("click", () => {
      const id = button.dataset.select;
      if (selected.has(id)) selected.delete(id);
      else selected.add(id);
      persistSelection();
      if (SOURCE === "official") characters = characters.filter(c => selected.has(keyFor(c)));
      render();
    });
  });
}

async function init() {
  if (SOURCE === "official") {
    const urls = [["chatgpt", "/characters.json"], ["gemini", "/gemini/characters.json"]];
    const responses = await Promise.all(urls.map(async ([archive, url]) => {
      const response = await fetch(url, {cache:"no-store"});
      if (!response.ok) throw new Error(url + " could not be loaded");
      const data = await response.json();
      return data.map(c => ({...c, _archive:archive}));
    }));
    characters = responses.flat().filter(c => selected.has(keyFor(c))).map(applyNameDraft);
  } else {
    const res = await fetch(DATA_URL, { cache: "no-store" });
    if (!res.ok) throw new Error("characters.json could not be loaded");
    characters = (await res.json()).map(c => applyNameDraft({...c, _archive:SOURCE}));
  }
  render();
}

[search, sort, statusFilter, selectedOnly, latestOnly].forEach((el) => {
  el.addEventListener(el === search ? "input" : "change", render);
});

clearSelection.addEventListener("click", () => {
  if (!selected.size) return;
  selected.clear();
  persistSelection();
  if (SOURCE === "official") characters = [];
  render();
});

exportSelection.addEventListener("click", () => {
  const data = characters.filter(c => selected.has(keyFor(c)));
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${SOURCE}-official-character-selection.json`;
  a.click();
  URL.revokeObjectURL(url);
});

const exportNameButton = document.createElement("button");
exportNameButton.type = "button";
exportNameButton.textContent = "名前の改訂案をJSON保存";
exportNameButton.addEventListener("click", downloadNameDrafts);
exportSelection.parentElement.appendChild(exportNameButton);

init().catch((err) => {
  console.error(err);
  empty.hidden = false;
  empty.textContent = "図鑑データの読み込みに失敗しました。";
});
