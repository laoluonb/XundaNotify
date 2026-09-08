import "./style.css";
import { invoke } from "@tauri-apps/api/core";

type Message = { time: string; title: string; body: string };
type Snapshot = {
  running: boolean;
  port: number;
  address: string;
  messages: number;
  history: Message[];
  logs: string;
  notification_mode: "windows" | "software" | "both" | string;
  sound: boolean;
  quiet_mode: boolean;
};
type UpdateState = { status: "idle" | "checking" | "latest" | "available" | "error"; version?: string; url?: string; note?: string };

const app = document.querySelector<HTMLDivElement>("#app")!;
let active = "overview";
let snapshot: Snapshot = {
  running: false,
  port: 8080,
  address: "127.0.0.1:8080",
  messages: 0,
  history: [],
  logs: "",
  notification_mode: "both",
  sound: true,
  quiet_mode: false,
};
const CURRENT_VERSION = "1.3.0";
let updateState: UpdateState = { status: "idle" };
let settingsDirty = false;

const esc = (value: string) => value.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
const icon = (name: string) => `<span class="icon icon-${name}"></span>`;

function render() {
  const nav = [["overview", "总览", "grid"], ["history", "消息历史", "history"], ["settings", "设置", "sliders"], ["logs", "运行日志", "terminal"]] as const;
  app.innerHTML = `<div class="shell">
    <aside class="sidebar">
      <div class="brand"><div class="brand-mark">✦</div><div><strong>讯达</strong><small>通知中心</small></div></div>
      <div class="nav-label">工作台</div>
      <nav>${nav.map(([key, label, ico]) => `<button class="nav ${active === key ? "active" : ""}" data-view="${key}">${icon(ico)}<span>${label}</span></button>`).join("")}</nav>
      <div class="side-footer"><span class="live-dot"></span> 本机通知服务<small>v${CURRENT_VERSION} · Tauri / Windows</small></div>
    </aside>
    <main class="content"><div class="topbar"><div class="topbar-spacer"></div><button class="tool" id="check-update-top" title="检查更新">↻</button><button class="tool" title="当前版本">v${CURRENT_VERSION}</button></div>${active === "overview" ? overview() : active === "history" ? history() : active === "settings" ? settings() : logs()}</main>
  </div>`;
  document.querySelectorAll<HTMLButtonElement>("[data-view]").forEach((button) => button.onclick = () => { active = button.dataset.view!; render(); });
  bindActions();
  if (active === "logs") requestAnimationFrame(() => { const el = document.querySelector<HTMLElement>(".log-output"); if (el) el.scrollTop = el.scrollHeight; });
}

function overview() { return `<header><div><div class="eyebrow">LOCAL WEBHOOK GATEWAY</div><h1>总览</h1><p>检查服务状态、消息接收和快速操作。</p></div><span class="status ${snapshot.running ? "ok" : "off"}">${snapshot.running ? "服务运行中" : "服务未启动"}</span></header>
  ${updateBanner()}
  <section class="stats"><div class="stat"><small>服务状态</small><strong>${snapshot.running ? "运行中" : "未启动"}</strong><span>局域网接收服务</span></div><div class="stat cyan"><small>今日消息</small><strong>${snapshot.messages}</strong><span>条通知已送达</span></div><div class="stat violet"><small>监听地址</small><strong>${esc(snapshot.address)}</strong><span>提供给手机端 WebHook</span></div></section>
  <section class="workspace"><div class="panel endpoint"><div class="panel-head"><div><small class="eyebrow">WEBHOOK ENDPOINT</small><h2>接收地址</h2></div><button class="primary" id="toggle">${snapshot.running ? "停止服务" : "启动服务"}</button></div><p>将下方地址填入 SmsForwarder 的 WebHook，支持 GET / POST。</p><div class="address"><code>http://${esc(snapshot.address)}/?msg=</code><button class="ghost" id="copy">复制地址</button></div><button class="ghost test" id="test">发送测试通知</button></div><div class="panel activity"><div class="panel-head"><div><small class="eyebrow">RECENT ACTIVITY</small><h2>最近活动</h2></div><button class="link" data-view="history">查看全部</button></div>${snapshot.history.slice(0, 6).map((m) => `<div class="activity-row"><time>${esc(m.time)}</time><div><strong>${esc(m.title)}</strong><span>${esc(m.body)}</span></div></div>`).join("") || `<div class="empty">暂无消息</div>`}</div></section>`; }
function history() { return `<header><div><div class="eyebrow">MESSAGE ARCHIVE</div><h1>消息历史</h1><p>所有接收到的通知都会保存在这里。</p></div></header><section class="panel table-panel"><div class="table-head"><span>接收时间</span><span>标题</span><span>消息</span></div>${snapshot.history.map((m) => `<div class="table-row"><time>${esc(m.time)}</time><strong>${esc(m.title)}</strong><span>${esc(m.body)}</span></div>`).join("") || `<div class="empty">暂无历史消息</div>`}</section>`; }
function updateBanner() { if (updateState.status === "available") return `<section class="update-banner"><div><span class="eyebrow">NEW VERSION</span><strong>发现新版本 v${esc(updateState.version || "")}</strong><span>${esc(updateState.note || "GitHub Release 已发布更新")}</span></div><button class="primary" id="open-update">立即更新</button></section>`; if (updateState.status === "checking") return `<section class="update-banner muted"><span>正在检查更新...</span></section>`; if (updateState.status === "latest") return `<section class="update-banner muted"><span>当前已是最新版本 v${CURRENT_VERSION}</span></section>`; return ""; }
function settings() {
  const mode = snapshot.notification_mode === "windows" ? "Windows 通知" : snapshot.notification_mode === "software" ? "软件通知" : "同时通知";
  return `<header><div><div class="eyebrow">PREFERENCES</div><h1>设置</h1><p>管理服务端口、通知方式和更新选项。</p></div></header><section class="panel settings"><label>监听端口<input id="port" value="${snapshot.port}" type="number" min="1" max="65535"></label><label>通知方式<select id="mode"><option ${mode === "Windows 通知" ? "selected" : ""}>Windows 通知</option><option ${mode === "软件通知" ? "selected" : ""}>软件通知</option><option ${mode === "同时通知" ? "selected" : ""}>同时通知</option></select></label><label class="check"><input type="checkbox" id="sound" ${snapshot.sound ? "checked" : ""}>播放通知提示音</label><label class="check"><input type="checkbox" id="quiet" ${snapshot.quiet_mode ? "checked" : ""}>免打扰模式（仅记录，不弹窗）</label><div class="setting-divider"></div><div class="version-row"><div><span>当前版本</span><strong>v${CURRENT_VERSION}</strong></div><button class="ghost" id="check-update">${updateState.status === "checking" ? "检查中..." : "检查更新"}</button></div><div class="update-result ${updateState.status}">${updateState.status === "available" ? `发现 v${esc(updateState.version || "")}，点击更新按钮打开下载页面。` : updateState.status === "latest" ? "已经是最新版本。" : updateState.note || ""}</div><button class="primary" id="save">保存设置</button></section>`;
}
function logs() { return `<header><div><div class="eyebrow">RUNTIME DIAGNOSTICS</div><h1>运行日志</h1><p>实时查看服务、通知和系统事件。</p></div><span class="status ok">实时更新</span></header><section class="panel log-panel"><pre class="log-output">${esc(snapshot.logs || "暂无运行日志")}</pre></section>`; }

function isEditingSettings() {
  if (active !== "settings") return false;
  const focused = document.activeElement;
  return settingsDirty || focused instanceof HTMLInputElement || focused instanceof HTMLSelectElement || focused instanceof HTMLTextAreaElement;
}

async function refresh() {
  try {
    snapshot = await invoke<Snapshot>("snapshot");
    // Do not rebuild the settings DOM while a native input/select is focused.
    // Rebuilding it closes an open Windows select popup and discards unsaved edits.
    if (!isEditingSettings()) render();
  } catch {
    if (!isEditingSettings()) render();
  }
}
async function checkForUpdates() { updateState = { status: "checking" }; render(); try { const response = await fetch("https://api.github.com/repos/laoluonb/XundaNotify/releases/latest", { headers: { Accept: "application/vnd.github+json" } }); if (!response.ok) throw new Error(`HTTP ${response.status}`); const release = await response.json() as { tag_name?: string; html_url?: string; body?: string }; const latest = (release.tag_name || "").replace(/^v/, ""); const isNewer = latest && latest !== CURRENT_VERSION && latest.localeCompare(CURRENT_VERSION, undefined, { numeric: true }) > 0; updateState = isNewer ? { status: "available", version: latest, url: release.html_url, note: release.body?.split("\n")[0] || "GitHub Release 已发布更新" } : { status: "latest" }; } catch (error) { updateState = { status: "error", note: `检查更新失败：${String(error)}` }; } render(); }
function bindActions() { document.querySelectorAll<HTMLButtonElement>("[data-view]").forEach((button) => button.onclick = () => { active = button.dataset.view!; settingsDirty = false; render(); }); const toggle = document.querySelector<HTMLButtonElement>("#toggle"); if (toggle) toggle.onclick = async () => { await invoke("toggle_server"); refresh(); }; const test = document.querySelector<HTMLButtonElement>("#test"); if (test) test.onclick = async () => { await invoke("test_notification"); refresh(); }; const copy = document.querySelector<HTMLButtonElement>("#copy"); if (copy) copy.onclick = () => navigator.clipboard.writeText(`http://${snapshot.address}/?msg=`); const settingFields = document.querySelectorAll<HTMLInputElement | HTMLSelectElement>("#port, #mode, #sound, #quiet"); settingFields.forEach((field) => field.addEventListener("input", () => { settingsDirty = true; })); settingFields.forEach((field) => field.addEventListener("change", () => { settingsDirty = true; })); const save = document.querySelector<HTMLButtonElement>("#save"); if (save) save.onclick = async () => { const port = Number((document.querySelector("#port") as HTMLInputElement).value); const mode = (document.querySelector("#mode") as HTMLSelectElement).value; const sound = (document.querySelector("#sound") as HTMLInputElement).checked; const quiet = (document.querySelector("#quiet") as HTMLInputElement).checked; await invoke("save_settings", { port, mode, sound, quiet }); settingsDirty = false; await refresh(); }; const check = document.querySelector<HTMLButtonElement>("#check-update"); if (check) check.onclick = checkForUpdates; const checkTop = document.querySelector<HTMLButtonElement>("#check-update-top"); if (checkTop) checkTop.onclick = checkForUpdates; const open = document.querySelector<HTMLButtonElement>("#open-update"); if (open) open.onclick = () => { if (updateState.url) window.open(updateState.url, "_blank"); }; }
render(); refresh(); setInterval(refresh, 1000);
