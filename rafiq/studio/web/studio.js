"use strict";

const state = { lang: localStorage.getItem("rafiq-language") || "ar", view: "board", projects: [], project: null, sceneId: null, assets: [], jobs: [], dirty: false, editVersion: 0, saving: null, ready: null, quote: null, token: "", config: null };
const app = document.getElementById("app");
const modal = document.getElementById("modal");
const t = (ar, en) => state.lang === "ar" ? ar : en;
const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
const icons = {
  board: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  people: '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3m1-16a3 3 0 0 1 0 6m3 10v-3a6 6 0 0 0-3-5"/>',
  place: '<path d="M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
  script: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6m-6 4h6m-6 4h4"/>',
  export: '<path d="M4 16v4h16v-4M12 3v12M8 7l4-4 4 4"/>',
  engine: '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4m6-4v4m-6 12v4m6-4v4M2 9h4m-4 6h4m12-6h4m-4 6h4"/>',
  film: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 5v14m10-14v14M3 10h4m-4 4h4m10-4h4m-4 4h4"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  save: '<path d="M5 3h13l3 3v15H3V3zm2 0v6h10V3M7 21v-8h10v8"/>',
  globe: '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
  play: '<path d="m9 5 11 7-11 7Z"/>',
};
const icon = name => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.film}</svg>`;
const hasExportVisual = shot => Boolean(shot.video_asset_id || (shot.use_still && shot.reference_asset_id));
const scene = () => state.project?.scenes.find(item => item.id === state.sceneId);
const assetUrl = id => `/api/assets/${encodeURIComponent(id)}`;
const options = (items, selected) => items.map(([value, label]) => `<option value="${esc(value)}"${String(value) === String(selected ?? "") ? " selected" : ""}>${esc(label)}</option>`).join("");
const styleName = style => ({ "3d": t("رسوم ثلاثية الأبعاد", "3D animation"), realistic: t("واقعي", "Live action"), anime: t("أنمي", "Anime") })[style];
const statusName = name => ({ awaiting_gpu: t("بانتظار نتيجة GPU", "Awaiting GPU result"), queued: t("في الانتظار", "Queued"), running: t("قيد التنفيذ", "Running"), succeeded: t("مكتمل", "Completed"), failed: t("تعذر التنفيذ", "Failed"), interrupted: t("توقف التتبع", "Interrupted"), cancelled: t("ملغى", "Cancelled") })[name] || name;

async function api(path, init = {}) {
  const headers = { "X-Rafiq-Token": state.token, ...init.headers };
  if (init.body && !(init.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const response = await fetch(path, { ...init, headers });
  const body = await response.json();
  if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || body));
  return body;
}

function toast(message, error = false) {
  const node = document.getElementById("toast");
  node.textContent = message;
  node.className = error ? "visible error" : "visible";
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { node.className = ""; }, error ? 10000 : 4000);
}

function dirty() {
  state.dirty = true;
  state.editVersion += 1;
  document.querySelectorAll(".save-state").forEach(node => { node.textContent = t("تعديلات غير محفوظة", "Unsaved changes"); });
}

async function save(showToast = false) {
  if (state.saving) {
    await state.saving;
    return save(showToast);
  }
  if (!state.dirty) return;
  const version = state.editVersion;
  const projectId = state.project.id;
  state.saving = api(`/api/projects/${projectId}`, { method: "PUT", body: JSON.stringify(state.project) });
  try {
    const saved = await state.saving;
    state.projects = state.projects.map(item => item.id === projectId ? saved : item);
    if (state.project.id === projectId) {
      if (state.editVersion === version) { state.project = saved; state.dirty = false; }
      else state.project.revision = saved.revision;
    }
  } finally { state.saving = null; }
  if (state.dirty) return save(showToast);
  document.querySelectorAll(".save-state").forEach(node => { node.textContent = t("جميع التعديلات محفوظة", "All changes saved"); });
  if (showToast) toast(t("تم حفظ المشروع", "Project saved"));
}

async function loadProject(id) {
  const [project, assets, jobs] = await Promise.all([api(`/api/projects/${id}`), api(`/api/projects/${id}/assets`), api(`/api/jobs?project_id=${id}`)]);
  state.project = project;
  state.assets = assets;
  state.jobs = jobs;
  state.sceneId = project.scenes[0]?.id || null;
  state.dirty = false;
  state.ready = null;
  localStorage.setItem("rafiq-project", id);
  render();
}

function field(label, path, value, type = "text", extra = "") {
  const id = `field-${path.replaceAll(".", "-")}`;
  return `<div class="field"><label for="${id}">${label}</label><input id="${id}" data-path="${path}" type="${type}" value="${esc(value)}" ${extra}></div>`;
}

function textField(label, path, value, extra = "") {
  const id = `field-${path.replaceAll(".", "-")}`;
  return `<div class="field"><label for="${id}">${label}</label><textarea id="${id}" data-path="${path}" dir="auto" ${extra}>${esc(value)}</textarea></div>`;
}

function assetSelect(kind, selected, path, label) {
  const items = [["", t("لم يتم التحديد", "Not selected")], ...state.assets.filter(item => item.kind === kind).map(item => [item.id, item.original_name])];
  const id = `asset-${path.replaceAll(".", "-")}`;
  return `<div class="field"><label for="${id}">${label}</label><select id="${id}" data-path="${path}" data-null="true">${options(items, selected)}</select></div>`;
}

function uploadField(kind, path, label) {
  const accept = { image: "image/png,image/jpeg,image/webp", audio: "audio/*", video: "video/mp4,video/quicktime" }[kind];
  const id = `upload-${path.replaceAll(".", "-")}`;
  return `<div class="field"><label for="${id}">${label}</label><input type="file" id="${id}" data-upload="${kind}" data-target="${path}" accept="${accept}"></div>`;
}

function heading(title, subtitle, actions = "") {
  return `<div class="page-heading"><div><p class="eyebrow">RAFIQ / ${esc(state.view.toUpperCase())}</p><h2>${title}</h2><p class="subtle">${subtitle}</p></div>${actions}</div>`;
}

function render() {
  document.documentElement.lang = state.lang;
  document.documentElement.dir = state.lang === "ar" ? "rtl" : "ltr";
  const p = state.project;
  if (!p) return;
  const nav = [
    ["board", "board", t("لوحة المشاهد", "Storyboard"), p.scenes.length],
    ["characters", "people", t("الشخصيات", "Characters"), p.characters.length],
    ["locations", "place", t("الأماكن", "Locations"), p.locations.length],
    ["script", "script", t("السيناريو", "Script"), null],
    ["jobs", "export", t("الإنتاج والتصدير", "Production & export"), null],
    ["engine", "engine", t("المحرك والتكلفة", "Engine & cost"), null],
  ];
  app.innerHTML = `<div class="layout"><aside class="sidebar"><div class="brand"><img src="/static/mark.svg" alt=""><div><strong>RAFIQ AI</strong><small>STUDIO</small></div></div><p class="owner">${t("مساحة إنتاج مستقلة<br>مؤسسة رفيق البصيرة", "Independent production<br>Rafiq Al-Basira")}</p><div class="project-select"><label for="project-picker">${t("المشروع الحالي", "Current project")}</label><select id="project-picker">${options(state.projects.map(item => [item.id, item.title]), p.id)}</select><button class="quiet small" data-action="new-project">${icon("plus")}${t("مشروع جديد", "New project")}</button><button data-action="new-interview">${t("قالب مقابلة AI", "AI interview template")}</button></div><nav class="nav" aria-label="${t("التنقل الرئيسي", "Main navigation")}">${nav.map(([key, symbol, label, count]) => `<button data-action="nav" data-view="${key}" class="${state.view === key ? "active" : ""}" ${state.view === key ? 'aria-current="page"' : ""}>${icon(symbol)}${label}${count !== null ? `<span class="count">${count}</span>` : ""}</button>`).join("")}</nav><div class="sidebar-bottom"><div class="engine-label"><span class="dot ${state.ready?.ready ? "ready" : ""}"></span>${state.ready?.ready ? t("المحرك جاهز للفحص الفعلي", "Engine preflight passed") : state.ready ? t("المحرك يحتاج إعدادًا", "Engine needs setup") : t("المحرك لم يُفحص بعد", "Engine not checked")}</div><p>${t("تشغيل محلي · الخدمات المدفوعة معطلة", "Local execution · paid services disabled")}</p><button class="quiet small" data-action="check-engine">${icon("engine")}${t("فحص المحرك", "Check engine")}</button></div></aside><main class="workspace"><header class="topbar"><div><div class="breadcrumb">${t("مساحة العمل / المشروع", "Workspace / Project")}</div><h1>${esc(p.title)}</h1></div><div class="top-actions"><span class="save-state">${state.dirty ? t("تعديلات غير محفوظة", "Unsaved changes") : t("جميع التعديلات محفوظة", "All changes saved")}</span><button class="quiet" data-action="language">${icon("globe")}${t("English", "العربية")}</button><button data-action="save">${icon("save")}${t("حفظ", "Save")}</button></div></header><div class="page">${({ board: boardView, characters: charactersView, locations: locationsView, script: scriptView, jobs: jobsView, engine: engineView })[state.view]()}</div></main></div>`;
}

function boardView() {
  const p = state.project;
  const s = scene();
  const total = p.scenes.reduce((sum, shot) => sum + Number(shot.seconds), 0);
  const stats = `<div class="stats"><div class="stat"><b>${p.scenes.length}</b><span>${t("مشاهد", "scenes")}</span></div><div class="stat"><b>${total}s</b><span>${t("المدة المخططة", "planned duration")}</span></div><div class="stat"><b>${p.scenes.filter(hasExportVisual).length}/${p.scenes.length}</b><span>${t("لقطات محددة", "selected takes")}</span></div></div>`;
  const head = heading(t("من الفكرة إلى المشهد", "From idea to scene"), t("اكتب اللقطة، ثبّت تفاصيلها، ثم اختبر توليدًا قصيرًا.", "Write the shot, preserve its details, then test a short generation."), stats);
  if (!s) return `${head}<div class="empty-list">${t("ابدأ بإضافة المشهد الأول إلى مشروعك.", "Add the first scene to your project.")}<br><button data-action="add-scene" class="primary">${icon("plus")}${t("إضافة مشهد", "Add scene")}</button></div>`;
  let preview;
  if (s.video_asset_id) preview = `<video controls preload="metadata" src="${assetUrl(s.video_asset_id)}"></video>`;
  else if (s.reference_asset_id) preview = `<img src="${assetUrl(s.reference_asset_id)}" alt="${t("الصورة المرجعية للمشهد", "Scene reference image")}">`;
  else preview = `<div class="empty-frame"><div class="frame-symbol">${icon("film")}</div><strong>${t("مشهد ينتظر صورته الأولى", "A scene waiting for its first frame")}</strong><p>${t("أضف صورة مرجعية أو ولّد لقطة من الوصف.<br>لن تظهر معاينة فيديو قبل إنتاج ملف فعلي.", "Add a reference image or generate from a prompt.<br>A video preview appears only after a real file exists.")}</p></div>`;
  return `${head}<div class="editor-grid"><section><div class="viewer"><div class="viewer-top"><span>${esc(s.title)}</span><span class="badge">${s.video_asset_id ? t("لقطة محددة", "Selected take") : s.reference_asset_id ? t("صورة مرجعية", "Reference image") : t("لم يُنتج بعد", "Not rendered")}</span></div><div class="stage">${preview}</div><div class="stage-info"><div>${styleName(p.style)}</div><span>${p.settings.width} × ${p.settings.height} · ${p.settings.fps} fps · ${s.seconds}s</span></div></div><div class="below-viewer"><button class="quiet small" data-action="move-scene" data-direction="-1">${t("تقديم المشهد", "Move earlier")}</button><button class="quiet small" data-action="move-scene" data-direction="1">${t("تأخير المشهد", "Move later")}</button><button class="quiet small" data-action="duplicate-scene">${t("نسخ المشهد", "Duplicate")}</button><button class="quiet small danger" data-action="delete-scene">${t("حذف المشهد", "Remove scene")}</button></div><div class="timeline-head"><h3>${t("تسلسل المشاهد", "Shot sequence")}</h3><button class="small quiet" data-action="add-scene">${icon("plus")}${t("مشهد جديد", "Add scene")}</button></div><div class="filmstrip">${p.scenes.map((shot, index) => `<button data-action="select-scene" data-id="${esc(shot.id)}" class="shot ${shot.id === s.id ? "selected" : ""}" aria-label="${esc(shot.title)}" aria-pressed="${shot.id === s.id}"><div class="shot-image">${shot.reference_asset_id ? `<img loading="lazy" src="${assetUrl(shot.reference_asset_id)}" alt="">` : icon("film")}<span class="shot-index">${String(index + 1).padStart(2, "0")}</span></div><div class="shot-text"><strong>${esc(shot.title)}</strong><small>${shot.seconds}s · ${shot.video_asset_id ? t("لقطة محددة", "Take selected") : t("بانتظار الإنتاج", "Awaiting render")}</small></div></button>`).join("")}</div><div class="notice">${t("ثبات الهوية يحتاج صورة مرجعية ومراجعة لكل لقطة. حفظ البذرة والوصف يساعد التكرار، لكنه لا يضمن تطابق الوجوه.", "Identity consistency needs a reference image and review of every take. Saved seeds and descriptions help repeatability but do not guarantee matching faces.")}</div><div class="queue-line" id="queue-summary">${queueSummary()}</div></section><aside class="inspector"><h3 class="panel-title">${t("تفاصيل المشهد", "Scene details")}<span class="badge">${String(p.scenes.indexOf(s) + 1).padStart(2, "0")}</span></h3><div class="inspector-content">${field(t("اسم المشهد", "Scene title"), "scene.title", s.title)}${textField(t("الوصف البصري", "Visual prompt"), "scene.prompt", s.prompt, 'class="prompt"')}<div class="two-fields">${field(t("المدة بالثواني", "Seconds"), "scene.seconds", s.seconds, "number", 'min="1" max="60" step="0.1"')}${field(t("البذرة الثابتة", "Seed"), "scene.seed", s.seed, "number", 'min="0" step="1"')}</div><div class="field"><label for="scene-mode">${t("مصدر الفيديو", "Video input")}</label><select id="scene-mode" data-path="scene.mode">${options([["text", t("من النص", "Text to video")], ["image", t("من صورة مرجعية", "Image to video")]], s.mode)}</select></div><div class="field"><label for="scene-location">${t("المكان", "Location")}</label><select id="scene-location" data-path="scene.location_id" data-null="true">${options([["", t("بدون مكان محدد", "No location")], ...p.locations.map(item => [item.id, item.name])], s.location_id)}</select></div><div class="field"><span class="field-label">${t("الشخصيات في اللقطة", "Characters in frame")}</span><div class="chips">${p.characters.map(character => `<label class="check-chip"><input type="checkbox" data-cast="${esc(character.id)}"${s.character_ids.includes(character.id) ? " checked" : ""}>${esc(character.name)}</label>`).join("")}</div></div><details><summary>${t("الصورة المرجعية والملفات", "Reference image & media")}</summary><div>${assetSelect("image", s.reference_asset_id, "scene.reference_asset_id", t("مرجع المشهد المستخدم في I2V", "Scene image used for I2V"))}${uploadField("image", "scene.reference_asset_id", t("رفع صورة للمشهد", "Upload scene image"))}<label><input type="checkbox" data-path="scene.use_still"${s.use_still ? " checked" : ""}> ${t("استخدم صورة المشهد عند غياب الفيديو", "Use scene image when no video is selected")}</label>${assetSelect("video", s.video_asset_id, "scene.video_asset_id", t("اللقطة المعتمدة للمونتاج", "Take selected for editing"))}${uploadField("video", "scene.video_asset_id", t("استيراد لقطة MP4", "Import MP4 take"))}${assetSelect("audio", s.audio_asset_id, "scene.audio_asset_id", t("مسار الحوار", "Dialogue track"))}${uploadField("audio", "scene.audio_asset_id", t("استيراد حوار مسجّل", "Import recorded dialogue"))}</div></details><details><summary>${t("الحوار والأصوات", "Dialogue & voices")} (${s.dialogue.length})</summary><div>${dialogueView(s)}<div class="toolbar"><button class="small" data-action="add-line">${icon("plus")}${t("إضافة جملة", "Add line")}</button><button class="small" data-action="quote-voice">${t("توليد الحوار محليًا", "Generate local dialogue")}</button></div><p class="field-help">${t("يتطلب محرك Chatterbox محليًا وعينة صوت لكل شخصية. مزامنة الشفاه غير متاحة في هذه النسخة.", "Requires local Chatterbox and a voice reference per character. Lip sync is not available in this release.")}</p></div></details><details><summary>${t("ملاحظات الإخراج", "Direction notes")}</summary><div>${textField(t("ملاحظات المشهد", "Scene notes"), "scene.notes", s.notes)}</div></details></div><div class="inspector-footer"><button class="primary" data-action="quote-video">${icon("play")}${t("تقدير التكلفة وتوليد اللقطة", "Estimate & generate take")}</button><button class="quiet" data-action="gpu-export">${icon("export")}${t("تجهيز المشهد لجهاز GPU", "Prepare GPU job")}</button><p class="field-help">${t("مراجعة الإعدادات والتكلفة قبل التنفيذ", "Review settings and cost before execution")}</p></div></aside></div>`;
}

function dialogueView(s) {
  return s.dialogue.map((line, index) => `<div class="dialogue-line"><select aria-label="${t("الشخصية المتحدثة", "Speaker")}" data-path="scene.dialogue.${index}.character_id">${options(state.project.characters.map(item => [item.id, item.name]), line.character_id)}</select><textarea aria-label="${t("نص الحوار", "Dialogue text")}" dir="auto" data-path="scene.dialogue.${index}.text">${esc(line.text)}</textarea><div class="two-fields"><select aria-label="${t("لغة الحوار", "Dialogue language")}" data-path="scene.dialogue.${index}.language">${options([["ar", "العربية"], ["en", "English"]], line.language)}</select><button class="quiet small danger" data-action="remove-line" data-index="${index}">${t("حذف الجملة", "Remove line")}</button></div></div>`).join("");
}

function charactersView() {
  return heading(t("شخصياتك، بتفاصيلها", "Your cast, in detail"), t("احفظ ملامح الشخصية وملابسها وعينتها الصوتية مرة واحدة.", "Save each character’s appearance, wardrobe and voice reference."), `<button data-action="add-character" class="primary">${icon("plus")}${t("شخصية جديدة", "Add character")}</button>`) + `<div class="notice">${t("الأوصاف والملابس تُضاف إلى وصف اللقطة تلقائيًا. صور الشخصيات محفوظة كدليل إنتاج؛ لتوجيه الفيديو بصريًا اختر صورة تركيبية للمشهد في وضع «من صورة مرجعية».", "Descriptions and wardrobe are added to the shot prompt. Character sheets are a production guide; condition a video by selecting a composed scene image in Image to Video mode.")}</div><br><div class="cards">${state.project.characters.map((c, index) => `<article class="entity-card"><div class="entity-heading"><div class="avatar">${c.reference_asset_id ? `<img src="${assetUrl(c.reference_asset_id)}" alt="">` : esc(c.name[0])}</div><div><h3>${esc(c.name)}</h3><span class="field-help">${c.voice_asset_id ? t("عينة صوت محفوظة", "Voice reference saved") : t("لم تُعتمد عينة صوت بعد", "No voice reference yet")}</span></div></div>${field(t("اسم الشخصية", "Character name"), `project.characters.${index}.name`, c.name)}${textField(t("ملامح ثابتة", "Fixed appearance"), `project.characters.${index}.description`, c.description)}${textField(t("ملابس ثابتة", "Fixed wardrobe"), `project.characters.${index}.wardrobe`, c.wardrobe)}${uploadField("image", `project.characters.${index}.reference_asset_id`, t("صورة مرجعية للشخصية", "Character reference image"))}${textField(t("ملاحظات الصوت", "Voice direction"), `project.characters.${index}.voice_notes`, c.voice_notes)}${c.voice_asset_id ? `<audio controls preload="none" src="${assetUrl(c.voice_asset_id)}"></audio>` : ""}${uploadField("audio", `project.characters.${index}.voice_asset_id`, t("عينة صوت تملك حق استخدامها", "Voice reference you have permission to use"))}</article>`).join("")}</div>`;
}

function locationsView() {
  return heading(t("أمكنة تعود إليها القصة", "Places your story returns to"), t("ثبّت اتجاه الإضاءة وتوزيع العناصر بين اللقطات.", "Keep lighting direction and spatial arrangements consistent."), `<button data-action="add-location" class="primary">${icon("plus")}${t("مكان جديد", "Add location")}</button>`) + `<div class="cards">${state.project.locations.map((location, index) => `<article class="entity-card">${location.reference_asset_id ? `<img class="preview-thumb" src="${assetUrl(location.reference_asset_id)}" alt="${esc(location.name)}">` : ""}${field(t("اسم المكان", "Location name"), `project.locations.${index}.name`, location.name)}${textField(t("وصف المكان وتوزيعه", "Location & spatial arrangement"), `project.locations.${index}.description`, location.description)}${uploadField("image", `project.locations.${index}.reference_asset_id`, t("صورة دليل للمكان", "Location guide image"))}<p class="field-help">${t("صورة دليل المكان لا تُمرر تلقائيًا إلى نموذج الفيديو؛ حدد صورة المشهد في لوحة المشاهد.", "The location guide is not automatically sent to the video model; select a scene image in the storyboard.")}</p></article>`).join("") || `<div class="empty-list">${t("أضف المكان الأول.", "Add your first location.")}</div>`}</div>`;
}

function scriptView() {
  return heading(t("السيناريو يبدأ هنا", "The script starts here"), t("اكتب المعالجة والحوار، ثم انقل كل لقطة إلى لوحة المشاهد.", "Write your treatment and dialogue, then add shots to the storyboard."), `<button class="quiet" data-action="nav" data-view="board">${icon("board")}${t("لوحة المشاهد", "Storyboard")}</button>`) + `${textField(t("اسم المشروع", "Project title"), "project.title", state.project.title)}${textField(t("السيناريو والمعالجة", "Script & treatment"), "project.script", state.project.script, 'class="script-editor"')}<p class="field-help">${t("النص محفوظ ضمن المشروع. لا تُرسل كتاباتك إلى خدمة خارجية لإعادة الصياغة.", "Your text is saved in the project. It is not sent to an external rewriting service.")}</p>`;
}

function gpuTransferPanel() {
  return `<section class="settings-panel"><h3>${t("توليد المشاهد على جهاز GPU آخر", "Render shots on another GPU")}</h3><p class="subtle">${t("جهّز حزمة المشهد من لوحة المشاهد، وشغّلها في دفتر GPU، ثم استورد ملف النتيجة ZIP هنا. ستبقى اللقطة للمراجعة قبل اعتمادها في الفيلم.", "Prepare a scene package from the storyboard, run it in the GPU notebook, then import its result ZIP here. Review the take before selecting it for the film.")}</p><div class="toolbar"><a href="/api/gpu-notebook">${t("تنزيل دفتر تشغيل GPU", "Download GPU notebook")}</a><label for="gpu-result-file">${t("استيراد نتيجة GPU", "Import GPU result")}</label><input id="gpu-result-file" type="file" accept="application/zip,.zip" data-gpu-result="true"></div><p class="field-help">${t("نقل الملفات لا يحجز موردًا ولا يبدأ فوترة. تكلفة جهاز GPU وزمنه غير مقاسين بعد. عند رفع الحزمة إلى خدمة سحابية، تنتقل إليها بيانات اللقطة والصورة المرجعية المحددة.", "File transfer does not provision compute or start billing. GPU cost and runtime are not yet measured. Uploading the package to a cloud service shares the shot data and its selected reference image with that service.")}</p></section>`;
}

function jobsView() {
  const p = state.project;
  const ready = p.scenes.length && p.scenes.every(hasExportVisual);
  return heading(t("من اللقطات إلى الفيلم", "From takes to film"), t("راجع النتائج، اختر لقطة لكل مشهد، ثم جمّع الفيلم بترتيب اللوحة.", "Review results, select a take per scene, then assemble the film in storyboard order."), `<button class="primary" data-action="quote-export" ${ready ? "" : "disabled"}>${icon("export")}${t("تصدير الفيلم MP4", "Export film as MP4")}</button>`) + `<div class="settings-panel"><div class="toolbar"><a href="/api/projects/${p.id}/download" data-action="download-project">${t("تنزيل بيانات المشروع JSON", "Download project JSON")}</a><label class="small" for="import-project">${t("استيراد مشروع JSON", "Import project JSON")}</label><input id="import-project" type="file" accept="application/json,.json" data-import="true"></div><p class="field-help">${t("ملف JSON يحفظ السيناريو والإعدادات. احتفظ أيضًا بنسخة احتياطية من مجلد بيانات RafiqAIStudio للوسائط. استيراد JSON ينشئ نسخة جديدة ويزيل روابط الوسائط القديمة.", "JSON preserves script and settings. Also back up your RafiqAIStudio data folder for media. Importing JSON creates a copy and clears old media links.")}</p><p class="subtle">${p.scenes.filter(hasExportVisual).length} / ${p.scenes.length} ${t("مشاهد جاهزة للتصدير", "scenes ready for export")}</p></div><br>${gpuTransferPanel()}<br><div id="jobs-list">${jobCards()}</div>`;
}

function jobCards() {
  if (!state.jobs.length) return `<div class="empty-list">${t("لا توجد مهام إنتاج بعد. ابدأ بلقطة قصيرة من لوحة المشاهد، أو استورد لقطاتك لاختبار المونتاج.", "No production jobs yet. Start a short shot from the storyboard, or import clips to test editing.")}</div>`;
  return state.jobs.map(job => {
    const title = state.project.scenes.find(item => item.id === job.scene_id)?.title || t("الفيلم المجمع", "Assembled film");
    const kind = job.execution === "portable" ? t("توليد على جهاز GPU آخر", "Portable GPU generation") : { generate: t("توليد فيديو", "Video generation"), voice: t("توليد حوار", "Dialogue generation"), export: t("تصدير MP4", "MP4 export") }[job.kind];
    return `<article class="job-card"><div class="job-card-top"><div><h3>${esc(title)}</h3><span class="field-help">${kind} · ${new Date(job.created * 1000).toLocaleString(state.lang === "ar" ? "ar-JO" : "en-GB")}</span></div><span class="badge">${statusName(job.state)}</span></div>${job.error ? `<p class="error" dir="auto">${esc(job.error)}</p>` : ""}${job.state === "running" ? `<p class="field-help">${t("جارٍ تنفيذ المهمة. ستظهر النتيجة عند وصول ملف فعلي من المحرك.", "The job is running. A result appears when the engine returns a real file.")}</p>` : ""}${job.output_asset_id ? job.kind === "voice" ? `<audio controls src="${assetUrl(job.output_asset_id)}"></audio>` : `<video controls preload="metadata" src="${assetUrl(job.output_asset_id)}"></video>` : ""}<div class="job-actions">${job.execution === "portable" ? `<a href="/api/jobs/${job.id}/gpu-request">${t("تنزيل حزمة المشهد", "Download scene package")}</a>` : ""}${job.state === "succeeded" && job.kind !== "export" ? `<button class="small primary" data-action="apply-job" data-id="${job.id}">${t("اعتماد الناتج للمشهد", "Use result for scene")}</button>` : ""}${job.output_asset_id ? `<a href="${assetUrl(job.output_asset_id)}?download=true">${t("تنزيل الملف", "Download file")}</a>` : ""}${job.state === "queued" ? `<button class="small quiet" data-action="cancel-job" data-id="${job.id}">${t("إلغاء الانتظار", "Cancel waiting job")}</button>` : ""}<a href="/api/jobs/${job.id}/manifest">${t("سجل الإعدادات", "Render manifest")}</a>${job.elapsed_seconds ? `<span class="field-help">${job.elapsed_seconds.toFixed(1)}s ${t("مدة التنفيذ", "elapsed")}</span>` : ""}</div></article>`;
  }).join("");
}

function engineView() {
  const s = state.project.settings;
  const checked = state.ready;
  return heading(t("محركك، تحت سيطرتك", "Your engine, under your control"), t("ابدأ بالدقة المنخفضة، قِس الزمن، ثم قرر جودة الإنتاج.", "Start at low resolution, measure runtime, then choose production quality."), `<button class="primary" data-action="check-engine">${icon("engine")}${t("فحص الجاهزية", "Run preflight")}</button>`) + `<div class="settings-grid"><section class="settings-panel"><h3>${t("إعدادات التوليد", "Generation settings")}</h3><div class="field"><label for="preset">${t("النموذج", "Model")}</label><select id="preset" data-path="project.settings.preset">${options(Object.entries(state.config.presets).map(([id, preset]) => [id, preset.name]), s.preset)}</select><p class="field-help">Apache 2.0 · ${t("مسار الربط لم يُختبر بعد على GPU", "Integration has not yet been verified on a GPU")}</p></div><div class="field"><label for="style">${t("الأسلوب البصري", "Visual style")}</label><select id="style" data-path="project.style">${options(["3d", "realistic", "anime"].map(key => [key, styleName(key)]), state.project.style)}</select></div><div class="two-fields">${field(t("العرض", "Width"), "project.settings.width", s.width, "number", 'min="64" max="1920" step="32"')}${field(t("الارتفاع", "Height"), "project.settings.height", s.height, "number", 'min="64" max="1088" step="32"')}</div><div class="two-fields">${field(t("إطار / ثانية", "Frames / second"), "project.settings.fps", s.fps, "number", 'min="8" max="30"')}${field(t("خطوات التوليد", "Sampling steps"), "project.settings.steps", s.steps, "number", 'min="1" max="100"')}</div>${field("CFG", "project.settings.cfg", s.cfg, "number", 'min="0" max="20" step="0.1"')}${textField(t("الوصف السلبي", "Negative prompt"), "project.settings.negative_prompt", s.negative_prompt)}<div class="notice">${t("LTX‑2.5 خيار التطوير التالي للصوت والفيديو المتزامنين. هذه النسخة تبدأ بـ Wan؛ أوزان النماذج لا تُنزّل تلقائيًا.", "LTX‑2.5 is the next integration candidate for synchronized audio/video. This release starts with Wan; model weights are not downloaded automatically.")}</div></section><section><div class="settings-panel"><h3>${t("تقدير تكلفة التشغيل المحلي", "Local operating cost")}</h3><p class="subtle">${t("تعتمد التكلفة على زمن جهازك واستهلاكه للكهرباء. اترك القيم فارغة إن لم تعرفها؛ لن نعرض تكلفة صفرية على أنها قياس.", "Cost depends on your device runtime and electricity use. Leave unknown values blank; zero is never presented as a measurement.")}</p>${field(t("سعر الكهرباء بالدولار / kWh", "Electricity in USD / kWh"), "project.settings.electricity_usd_kwh", s.electricity_usd_kwh, "number", 'min="0" max="10" step="0.001" data-null="true"')}${field(t("قدرة الجهاز الكلية بالواط", "Whole-system power in watts"), "project.settings.system_watts", s.system_watts, "number", 'min="1" max="5000" data-null="true"')}${field(t("زمن متوقع لهذه اللقطة بالثواني", "Assumed render seconds for this shot"), "project.settings.assumed_render_seconds", s.assumed_render_seconds, "number", 'min="1" max="86400" data-null="true"')}<p class="field-help">${t("الزمن المفترض مدخل منك. بعد نجاح توليد مماثل يُستخدم متوسط القياسات المسجلة. لا يشمل التقدير ثمن الجهاز أو إعادة المحاولات.", "The assumed time is your input. After a comparable generation succeeds, recorded measurements are used. Hardware cost and retries are excluded.")}</p></div><br><div class="settings-panel"><h3>${t("حالة التشغيل", "Runtime status")}</h3><p class="technical">ComfyUI: ${esc(state.config.engine_url)}\nFFmpeg: ${state.config.ffmpeg ? "available" : "missing"}\nVoice environment: ${state.config.voice_configured ? "configured — weights unverified" : "not configured"}\nCloud provisioning: disabled</p>${checked ? checked.ready ? `<div class="notice">${t("نجح فحص العقد والأوزان والجهاز المسرّع. ابدأ بتوليد لقطة لاختبار الجودة والزمن فعليًا.", "Nodes, weights and accelerator preflight passed. Generate a shot to measure actual quality and runtime.")}</div>` : `<div class="notice warning">${t("لم يجتز المحرك فحص الجاهزية. تفاصيل المتطلبات الناقصة:", "The engine did not pass preflight. Missing requirements:")}<pre class="technical">${esc(checked.errors.join("\n"))}</pre></div>` : `<p class="subtle">${t("اضغط فحص الجاهزية للتحقق من الاتصال والعقد والأوزان.", "Run preflight to check connectivity, nodes and weights.")}</p>`}<p class="field-help">${t("فحص المحرك يقرأ جهاز ComfyUI المتصل؛ لا يقرأ مواصفات حاسوبك Windows عن بُعد.", "Preflight reads the connected ComfyUI machine; it cannot inspect your Windows computer remotely.")}</p></div></section></div>`;
}

function queueSummary() {
  const active = state.jobs.filter(job => ["running", "queued"].includes(job.state));
  return active.length ? `${t("مهام إنتاج نشطة", "Active production jobs")}: ${active.length} · ${t("تابعها من الإنتاج والتصدير", "View them in Production & export")}` : t("لا توجد مهام قيد التنفيذ. كل توليد يبدأ بعد مراجعتك.", "No active jobs. Each generation starts after your review.");
}

function openModal(content) {
  modal.innerHTML = content;
  if (!modal.open) modal.showModal();
}

function newRecordDialog(kind) {
  const labels = { project: t("مشروع جديد", "New project"), character: t("شخصية جديدة", "New character"), location: t("مكان جديد", "New location") };
  openModal(`<h2 id="modal-title">${labels[kind]}</h2><label for="new-record-name">${t("الاسم", "Name")}</label><input id="new-record-name" maxlength="120" autofocus><div class="modal-actions"><button data-action="close-modal">${t("إلغاء", "Cancel")}</button><button class="primary" data-action="create-record" data-kind="${kind}">${t("إنشاء", "Create")}</button></div>`);
}

async function showQuote(kind) {
  await save();
  const base = `/api/projects/${state.project.id}`;
  const url = kind === "export" ? `${base}/export` : kind === "voice" ? `${base}/voice/${scene().id}` : `${base}/estimate/${scene().id}`;
  const q = await api(url, { method: "POST" });
  state.quote = q;
  if (kind === "generate") state.ready = q.readiness;
  const c = q.cost;
  const price = c.estimated_cost === null ? t("غير محسوبة بعد", "Not yet measured") : `$${c.estimated_cost.toFixed(4)}`;
  const timing = c.estimated_seconds === null ? t("زمن التنفيذ غير معروف", "Render time is unknown") : `${Math.round(c.estimated_seconds)}s · ${c.source === "measured-similar-jobs" ? t("تقدير من قياسات سابقة", "Estimated from previous measurements") : t("افتراض أدخلته أنت", "Your own assumption")}`;
  openModal(`<h2 id="modal-title">${t("مراجعة المهمة قبل التنفيذ", "Review before execution")}</h2><p class="cost-value">${price}</p><p class="cost-label">${timing}<br>${t("رسوم مزود خارجي: لا يوجد. التقدير للكهرباء فقط، ولا يشمل ثمن الجهاز أو المحاولات الإضافية.", "No external provider fee. This estimate covers electricity only, excluding hardware and additional attempts.")}</p>${q.readiness.ready ? `<div class="notice">${t("مسار محلي جاهز للتنفيذ. سيتم حفظ إعدادات المهمة وبذرتها.", "Local execution passed preflight. The job settings and seed will be recorded.")}</div>` : `<div class="notice warning">${t("التنفيذ محجوب حتى استكمال الإعداد:", "Execution is blocked until setup is complete:")}<pre class="technical">${esc(q.readiness.errors.join("\n"))}</pre></div>`}${q.prompt ? `<details><summary>${t("الوصف الذي سيصل للمحرك", "Prompt sent to the engine")}</summary><pre class="technical">${esc(q.prompt)}</pre></details>` : ""}<p class="field-help">${kind === "generate" ? t("هذا المسار يولد الصورة المتحركة دون صوت. صور أدلة الشخصيات والأماكن لا تُستخدم كاشتراطات بصرية؛ صورة المشهد المحددة فقط تُمرر في I2V. ثبات الهوية ومزامنة الشفاه يحتاجان مراجعة وتطويرًا لاحقًا.", "This workflow generates video without audio. Character and location guide images are not visual conditioning; only the selected scene image is passed in I2V. Identity consistency and lip sync need review and further work.") : kind === "export" ? t("سيُرتّب الفيلم وفق اللوحة. يُقص الفيديو والحوار إلى مدة كل مشهد، وتثبت آخر صورة إذا كان الفيديو أقصر.", "The film follows storyboard order. Video and dialogue are trimmed to scene duration; short clips hold their final frame.") : t("يتطلب أوزان Chatterbox مخزنة محليًا. راجع النطق وتشابه الصوت قبل اعتماد الحوار.", "Requires locally cached Chatterbox weights. Review pronunciation and voice similarity before using the dialogue.")}</p><div class="modal-actions"><button data-action="close-modal">${t("رجوع", "Back")}</button><button class="primary" data-action="accept-quote" ${q.readiness.ready ? "" : "disabled"}>${t("اعتماد وبدء المهمة", "Approve & start job")}</button></div>`);
}

function resolvePath(path) {
  const parts = path.split(".");
  const root = parts.shift() === "scene" ? scene() : state.project;
  let object = root;
  while (parts.length > 1) object = object[parts.shift()];
  return [object, parts[0]];
}

async function action(button) {
  const key = button.dataset.action;
  if (key === "nav") { state.view = button.dataset.view; render(); }
  else if (key === "language") { state.lang = state.lang === "ar" ? "en" : "ar"; localStorage.setItem("rafiq-language", state.lang); render(); }
  else if (key === "save") { await save(true); render(); }
  else if (key === "select-scene") { state.sceneId = button.dataset.id; render(); }
  else if (key === "new-project") newRecordDialog("project");
  else if (key === "new-interview") {
    await save();
    const project = await api("/api/projects/interview", { method: "POST" });
    state.projects.unshift(project);
    state.view = "board";
    await loadProject(project.id);
  }
  else if (key === "add-character") newRecordDialog("character");
  else if (key === "add-location") newRecordDialog("location");
  else if (key === "close-modal") modal.close();
  else if (key === "create-record") {
    const name = document.getElementById("new-record-name").value.trim();
    if (!name) throw new Error(t("أدخل اسمًا أولًا", "Enter a name first"));
    const id = crypto.randomUUID().replaceAll("-", "");
    if (button.dataset.kind === "project") {
      await save();
      const project = await api("/api/projects", { method: "POST", body: JSON.stringify({ title: name }) });
      state.projects.unshift(project);
      state.view = "board";
      await loadProject(project.id);
    } else if (button.dataset.kind === "character") {
      state.project.characters.push({ id, name, description: "", wardrobe: "", reference_asset_id: null, voice_asset_id: null, voice_notes: "" });
      dirty(); render();
    } else {
      state.project.locations.push({ id, name, description: "", reference_asset_id: null });
      dirty(); render();
    }
    modal.close();
  } else if (key === "add-scene") {
    const id = crypto.randomUUID().replaceAll("-", "");
    state.project.scenes.push({ id, title: t("مشهد جديد", "New scene"), prompt: "", notes: "", seconds: 5, seed: 42, mode: "text", character_ids: [], location_id: null, reference_asset_id: null, video_asset_id: null, audio_asset_id: null, dialogue: [] });
    state.sceneId = id; dirty(); render();
  } else if (key === "duplicate-scene") {
    const copy = structuredClone(scene());
    copy.id = crypto.randomUUID().replaceAll("-", "");
    copy.title += t(" — نسخة", " — copy");
    copy.video_asset_id = null; copy.audio_asset_id = null;
    state.project.scenes.splice(state.project.scenes.indexOf(scene()) + 1, 0, copy);
    state.sceneId = copy.id; dirty(); render();
  } else if (key === "move-scene") {
    const list = state.project.scenes;
    const from = list.indexOf(scene());
    const to = from + Number(button.dataset.direction);
    if (to >= 0 && to < list.length) { [list[from], list[to]] = [list[to], list[from]]; dirty(); render(); }
  } else if (key === "delete-scene") {
    openModal(`<h2 id="modal-title">${t("إزالة المشهد من اللوحة", "Remove scene from storyboard")}</h2><p class="subtle">${esc(scene().title)}<br>${t("تبقى ملفات الوسائط وسجل التوليد محفوظين.", "Media files and render history remain saved.")}</p><div class="modal-actions"><button data-action="close-modal">${t("رجوع", "Back")}</button><button data-action="confirm-delete-scene" class="danger">${t("إزالة المشهد", "Remove scene")}</button></div>`);
  } else if (key === "confirm-delete-scene") {
    state.project.scenes = state.project.scenes.filter(item => item.id !== state.sceneId);
    state.sceneId = state.project.scenes[0]?.id; dirty(); modal.close(); render();
  } else if (key === "add-line") {
    if (!state.project.characters.length) throw new Error(t("أضف شخصية أولًا", "Add a character first"));
    scene().dialogue.push({ character_id: state.project.characters[0].id, text: "", language: state.lang });
    dirty(); render();
  } else if (key === "remove-line") { scene().dialogue.splice(Number(button.dataset.index), 1); dirty(); render(); }
  else if (key === "check-engine") {
    await save();
    if (!scene()) throw new Error(t("أضف مشهدًا لفحص مساره", "Add a scene to check its workflow"));
    state.ready = await api(`/api/projects/${state.project.id}/readiness/${scene().id}`);
    state.view = "engine"; render();
  } else if (key === "quote-video") await showQuote("generate");
  else if (key === "quote-export") await showQuote("export");
  else if (key === "quote-voice") await showQuote("voice");
  else if (key === "gpu-export") {
    await save();
    const projectId = state.project.id;
    const job = await api(`/api/projects/${projectId}/gpu-request/${scene().id}`, { method: "POST", body: JSON.stringify({ revision: state.project.revision }) });
    if (state.project.id === projectId) { state.jobs.unshift(job); render(); }
    openModal(`<h2 id="modal-title">${t("حزمة المشهد جاهزة", "Scene package ready")}</h2><p class="subtle">${t("الحزمة تحفظ وصف هذه اللقطة وبذرتها وإعداداتها وصورتها المرجعية إن وُجدت. لا تتضمن الكتاب كاملًا أو عينات الأصوات.", "The package contains this shot’s prompt, seed, settings and selected reference image. It excludes the full script and voice samples.")}</p><ol class="checklist"><li><a href="/api/jobs/${job.id}/gpu-request">${t("تنزيل حزمة المشهد ZIP", "Download scene ZIP")}</a></li><li><a href="/api/gpu-notebook">${t("تنزيل دفتر GPU وفتحه في Colab", "Download the GPU notebook and open it in Colab")}</a></li><li>${t("بعد التوليد، استورد حزمة النتيجة من صفحة الإنتاج والتصدير.", "After rendering, import the result package in Production & export.")}</li></ol><div class="notice warning">${t("لم يبدأ توليد أو حجز GPU. التكلفة والزمن غير مقاسين على الجهاز الآخر. استخدم جلسة مجانية إن توفرت، ولا تشترِ موارد قبل تحديد الميزانية.", "No generation or GPU provisioning has started. Cost and runtime on the other machine are unknown. Use a free session if available; approve a budget before buying compute.")}</div><div class="modal-actions"><button class="primary" data-action="close-modal">${t("تم", "Done")}</button></div>`);
  }
  else if (key === "accept-quote") {
    button.disabled = true;
    try {
      const job = await api("/api/jobs", { method: "POST", body: JSON.stringify({ quote_id: state.quote.id, approved: true }) });
      state.jobs.unshift(job); modal.close(); state.view = "jobs"; render();
      toast(t("أُضيفت المهمة إلى طابور التنفيذ", "Job added to the queue"));
    } finally { button.disabled = false; }
  } else if (key === "apply-job") {
    await save();
    state.project = await api(`/api/jobs/${button.dataset.id}/apply`, { method: "POST", body: JSON.stringify({ revision: state.project.revision }) });
    state.projects = state.projects.map(item => item.id === state.project.id ? state.project : item);
    toast(t("تم اعتماد الناتج للمشهد", "Result selected for the scene")); render();
  } else if (key === "cancel-job") {
    await api(`/api/jobs/${button.dataset.id}/cancel`, { method: "POST" }); await poll();
  } else if (key === "download-project") {
    await save();
    const link = document.createElement("a");
    link.href = `/api/projects/${state.project.id}/download`; link.download = "rafiq-project.json"; link.click();
  }
}

document.addEventListener("click", async event => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  event.preventDefault();
  if (button.dataset.busy) return;
  button.dataset.busy = "true";
  try { await action(button); } catch (error) { toast(error.message, true); }
  finally { delete button.dataset.busy; }
});

document.addEventListener("input", event => {
  const element = event.target;
  if (element.dataset.path) {
    const [object, key] = resolvePath(element.dataset.path);
    object[key] = element.dataset.null && element.value === "" ? null : element.type === "checkbox" ? element.checked : element.type === "number" ? Number(element.value) : element.value;
    dirty();
  } else if (element.dataset.cast) {
    const s = scene();
    s.character_ids = element.checked ? [...new Set([...s.character_ids, element.dataset.cast])] : s.character_ids.filter(id => id !== element.dataset.cast);
    dirty();
  }
});

document.addEventListener("change", async event => {
  const element = event.target;
  try {
    if (element.id === "project-picker") { await save(); await loadProject(element.value); }
    if (element.dataset.path && ["scene.mode", "project.style", "project.settings.preset"].includes(element.dataset.path)) {
      if (element.dataset.path === "project.settings.preset") state.project.settings.fps = state.config.presets[state.project.settings.preset].fps;
      render();
    }
    if (element.dataset.upload && element.files[0]) {
      const [object, key] = resolvePath(element.dataset.target);
      const projectId = state.project.id;
      const file = element.files[0];
      const max = { image: 25, audio: 50, video: 512 }[element.dataset.upload] * 1024 ** 2;
      if (file.size > max) throw new Error(t("حجم الملف يتجاوز الحد المتاح", "File exceeds the upload limit"));
      element.disabled = true;
      const data = new FormData(); data.append("file", file);
      const asset = await api(`/api/projects/${projectId}/assets?kind=${element.dataset.upload}`, { method: "POST", body: data });
      if (projectId !== state.project.id) return;
      object[key] = asset.id; state.assets.push(asset); dirty(); await save(); render();
      toast(t("تم رفع الملف وحفظه", "File uploaded and saved"));
    }
    if (element.dataset.import && element.files[0]) {
      if (element.files[0].size > 5 * 1024 ** 2) throw new Error("Project JSON is too large");
      await save();
      const project = await api("/api/projects/import", { method: "POST", body: await element.files[0].text() });
      state.projects.unshift(project); await loadProject(project.id);
      toast(t("تم استيراد السيناريو والإعدادات دون روابط الوسائط القديمة", "Script and settings imported; old media links cleared"));
    }
    if (element.dataset.gpuResult && element.files[0]) {
      const file = element.files[0];
      if (file.size > 512 * 1024 ** 2) throw new Error(t("حزمة النتيجة أكبر من 512MB", "Result package exceeds 512MB"));
      await save();
      const projectId = state.project.id;
      const data = new FormData(); data.append("file", file);
      element.disabled = true;
      const result = await api(`/api/projects/${projectId}/gpu-result`, { method: "POST", body: data });
      if (state.project.id !== projectId) return;
      state.assets = await api(`/api/projects/${projectId}/assets`);
      state.jobs = await api(`/api/jobs?project_id=${projectId}`);
      state.view = "jobs"; render();
      toast(result.imported ? t("استوردت اللقطة. راجعها ثم اعتمدها للمشهد.", "Take imported. Review it, then select it for the scene.") : t("هذه النتيجة مستوردة مسبقًا", "This result was already imported"));
    }
  } catch (error) { toast(error.message, true); element.disabled = false; }
});

document.addEventListener("keydown", event => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
    event.preventDefault(); save(true).catch(error => toast(error.message, true));
  }
});
window.addEventListener("beforeunload", event => { if (state.dirty) { event.preventDefault(); event.returnValue = ""; } });

async function poll() {
  if (!state.project) return;
  const projectId = state.project.id;
  const jobs = await api(`/api/jobs?project_id=${projectId}`);
  if (state.project.id !== projectId) return;
  const completed = jobs.some(job => job.state === "succeeded" && !state.jobs.some(old => old.id === job.id && old.state === "succeeded"));
  state.jobs = jobs;
  if (completed) state.assets = await api(`/api/projects/${projectId}/assets`);
  const list = document.getElementById("jobs-list");
  if (list) list.innerHTML = jobCards();
  const summary = document.getElementById("queue-summary");
  if (summary) summary.textContent = queueSummary();
}

async function start() {
  try {
    state.config = await api("/api/bootstrap"); state.token = state.config.token;
    state.projects = await api("/api/projects");
    const remembered = localStorage.getItem("rafiq-project");
    await loadProject(state.projects.some(p => p.id === remembered) ? remembered : state.projects[0].id);
    setInterval(() => { if (state.jobs.some(job => ["queued", "running"].includes(job.state))) poll().catch(error => toast(error.message, true)); }, 3000);
  } catch (error) {
    app.innerHTML = `<div class="error-panel"><h1>Rafiq AI Studio</h1><p>${t("تعذر فتح المشروع. تحقق من تشغيل خادم الاستوديو ثم أعد تحميل الصفحة.", "Could not open the project. Check the studio server and reload.")}</p><pre class="technical">${esc(error.message)}</pre></div>`;
  }
}
start();
