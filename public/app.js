const grid = document.querySelector("#grid");
const search = document.querySelector("#search");
const sort = document.querySelector("#sort");

let characters = [];

const pad = (n) => String(n).padStart(3, "0");

function render() {
  const q = search.value.trim().toLowerCase();
  let list = characters.filter((c) =>
    [c.nameJa, c.nameEn, c.slug, String(c.id)]
      .join(" ")
      .toLowerCase()
      .includes(q)
  );

  list.sort((a, b) => sort.value === "desc" ? b.id - a.id : a.id - b.id);

  grid.innerHTML = list.map((c) => `
    <article class="card">
      <div class="id">#${pad(c.id)}</div>
      <div class="name-ja">${c.nameJa}</div>
      <div class="name-en">${c.nameEn}</div>
      <span class="status">${c.status || "MAYBE"}</span>
    </article>
  `).join("");
}

async function init() {
  const res = await fetch("/characters.json", { cache: "no-store" });
  characters = await res.json();
  render();
}

search.addEventListener("input", render);
sort.addEventListener("change", render);
init();
