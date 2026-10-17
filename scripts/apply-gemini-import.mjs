import fs from "node:fs";

const registryPath = "public/gemini/characters.json";
const incomingPath = "imports/gemini-character.json";

if (!fs.existsSync(incomingPath)) {
  console.log("No imports/gemini-character.json found; skipping registry merge.");
  process.exit(0);
}

const incoming = JSON.parse(fs.readFileSync(incomingPath, "utf8"));
const list = fs.existsSync(registryPath) ? JSON.parse(fs.readFileSync(registryPath, "utf8")) : [];

const id = Number(incoming.id);
if (!Number.isInteger(id) || id < 1) throw new Error("Gemini character id must be a positive integer.");

const pad = String(id).padStart(3,"0");
const entry = {
  ...incoming,
  id,
  source:"gemini",
  status: incoming.status || "MAYBE",
  verified: incoming.verified !== false,
  images: incoming.images || {
    main:`/gemini/characters/${pad}/main.webp`,
    normal:`/gemini/characters/${pad}/a.webp`,
    graphic:`/gemini/characters/${pad}/b.webp`
  }
};

const existingIndex = list.findIndex(x => Number(x.id) === id);
if (existingIndex >= 0) list[existingIndex] = entry;
else list.push(entry);

list.sort((a,b)=>Number(a.id)-Number(b.id));
fs.writeFileSync(registryPath, JSON.stringify(list,null,2)+"\n");
fs.rmSync(incomingPath);
console.log(`Merged Gemini character #${pad}`);
