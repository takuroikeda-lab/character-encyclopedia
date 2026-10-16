import fs from "node:fs";

const path = "public/characters.json";
const chars = JSON.parse(fs.readFileSync(path, "utf8"));
const byId = new Map(chars.map(c => [c.id, c]));

const pad = n => String(n).padStart(3, "0");
const mainIds = [...Array.from({length: 28}, (_,i)=>i+1), 32];
const draftIds = [29,30,33,34,35];

for (const id of mainIds) {
  let c = byId.get(id);
  if (!c) {
    c = {
      id,
      slug: `untitled-${pad(id)}`,
      nameJa: "名称未確定",
      nameEn: "UNTITLED",
      status: "MAYBE",
      verified: false,
      provenance: "regenerated-draft",
      emotionTheme: [],
      concept: "統一フォーマット再生成から仮登録。名称・設定は確認待ち。",
      images: {}
    };
    chars.push(c);
    byId.set(id,c);
  }
  c.images = c.images || {};
  c.images.main = `/characters/${pad(id)}/main.webp`;
  delete c.legacyCrop;
}

for (const id of draftIds) {
  const c = byId.get(id);
  if (!c) continue;
  c.regeneratedDraft = `/characters/${pad(id)}/draft.webp`;
}

chars.sort((a,b)=>a.id-b.id);
fs.writeFileSync(path, JSON.stringify(chars,null,2)+"\n");
