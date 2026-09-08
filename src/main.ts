import "./style.css";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

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
type UpdateState = { status: "idle" | "checking" | "latest" | "available" | "downloading" | "downloaded" | "installing" | "error"; version?: string; url?: string; note?: string; installerPath?: string };

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
const CURRENT_VERSION = "1.6.0";
let updateState: UpdateState = { status: "idle" };
let settingsDirty = false;
let saveState = "";
let softwareNotices: Array<Message & { id: number }> = [];
let noticeId = 0;
let eventReady = false;

const esc = (value: string) => value.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
const icon = (name: string) => `<span class="nav-icon icon-${name}" aria-hidden="true">${({ grid: "⌂", history: "◷", sliders: "⚙", terminal: "≡", info: "ⓘ" }[name] || "·")}</span>`;

function render() {
  const nav = [["overview", "总览", "grid"], ["history", "消息历史", "history"], ["settings", "设置", "sliders"], ["logs", "运行日志", "terminal"], ["about", "关于", "info"]] as const;
  app.innerHTML = `<div class="shell">
    <aside class="sidebar">
      <div class="brand"><div class="brand-mark">✦</div><div><strong>讯达</strong><small>通知中心</small></div></div>
      <div class="nav-label">工作台</div>
      <nav>${nav.map(([key, label, ico]) => `<button class="nav ${active === key ? "active" : ""}" data-view="${key}">${icon(ico)}<span>${label}</span></button>`).join("")}</nav>
      <div class="side-footer"><span class="live-dot"></span> 本机通知服务<small>v${CURRENT_VERSION} · Tauri / Windows</small></div>
    </aside>
    <main class="content"><div class="topbar"><div class="topbar-spacer"></div><button class="tool version-tool ${updateState.status === "available" || updateState.status === "downloaded" ? "update-tool" : ""}" id="check-update-version" title="点击检查更新">v${CURRENT_VERSION}</button></div>${active === "overview" ? overview() : active === "history" ? history() : active === "settings" ? settings() : active === "about" ? about() : logs()}</main>
  </div>${softwareNoticeLayer()}`;
  document.querySelectorAll<HTMLButtonElement>("[data-view]").forEach((button) => button.onclick = () => { active = button.dataset.view!; render(); });
  bindActions();
  if (active === "logs") requestAnimationFrame(() => { const el = document.querySelector<HTMLElement>(".log-output"); if (el) el.scrollTop = el.scrollHeight; });
}

function overview() { return `<header><div><div class="eyebrow">LOCAL WEBHOOK GATEWAY</div><h1>总览</h1><p>检查服务状态、消息接收和快速操作。</p></div><span class="status ${snapshot.running ? "ok" : "off"}">${snapshot.running ? "服务运行中" : "服务未启动"}</span></header>
  ${updateBanner()}
  <section class="stats"><div class="stat"><small>服务状态</small><strong>${snapshot.running ? "运行中" : "未启动"}</strong><span>局域网接收服务</span></div><div class="stat cyan"><small>今日消息</small><strong>${snapshot.messages}</strong><span>条通知已送达</span></div><div class="stat violet"><small>监听地址</small><strong>${esc(snapshot.address)}</strong><span>提供给手机端 WebHook</span></div></section>
  <section class="workspace"><div class="panel endpoint"><div class="panel-head"><div><small class="eyebrow">WEBHOOK ENDPOINT</small><h2>接收地址</h2></div><button class="primary" id="toggle">${snapshot.running ? "停止服务" : "启动服务"}</button></div><p>将下方地址填入 SmsForwarder 的 WebHook，支持 GET / POST。</p><div class="address"><code>http://${esc(snapshot.address)}/?msg=</code><button class="ghost" id="copy">复制地址</button></div><button class="ghost test" id="test">发送测试通知</button></div><div class="panel activity"><div class="panel-head"><div><small class="eyebrow">RECENT ACTIVITY</small><h2>最近活动</h2></div><button class="link" data-view="history">查看全部</button></div>${snapshot.history.slice(0, 6).map((m) => `<div class="activity-row"><time>${esc(m.time)}</time><div><strong>${esc(m.title)}</strong><span>${esc(m.body)}</span></div></div>`).join("") || `<div class="empty">暂无消息</div>`}</div></section>`; }
function history() { return `<header><div><div class="eyebrow">MESSAGE ARCHIVE</div><h1>消息历史</h1><p>所有接收到的通知都会保存在这里。</p></div></header><section class="panel table-panel"><div class="table-head"><span>接收时间</span><span>标题</span><span>消息</span></div>${snapshot.history.map((m) => `<div class="table-row"><time>${esc(m.time)}</time><strong>${esc(m.title)}</strong><span>${esc(m.body)}</span></div>`).join("") || `<div class="empty">暂无历史消息</div>`}</section>`; }
function updateBanner() { if (updateState.status === "available") return `<section class="update-banner"><div><span class="eyebrow">NEW VERSION</span><strong>发现新版本 v${esc(updateState.version || "")}</strong><span>${esc(updateState.note || "GitHub Release 已发布更新")}</span></div><button class="primary" id="open-update">立即下载</button></section>`; if (updateState.status === "downloading") return `<section class="update-banner muted"><span>正在下载 v${esc(updateState.version || "")} 安装包...</span></section>`; if (updateState.status === "downloaded") return `<section class="update-banner"><div><span class="eyebrow">UPDATE READY</span><strong>安装包已准备好</strong><span>可以立即安装 v${esc(updateState.version || "")}。</span></div><button class="primary" id="install-update">立即安装</button></section>`; if (updateState.status === "installing") return `<section class="update-banner muted"><span>正在启动安装程序...</span></section>`; if (updateState.status === "checking") return `<section class="update-banner muted"><span>正在检查更新...</span></section>`; if (updateState.status === "latest") return `<section class="update-banner muted"><span>当前已是最新版本 v${CURRENT_VERSION}</span></section>`; return ""; }
function settings() {
  const mode = snapshot.notification_mode === "windows" ? "Windows 通知" : snapshot.notification_mode === "software" ? "软件通知" : "同时通知";
  const versionAction = updateState.status === "available" ? `<button class="primary" id="download-update-settings">立即下载</button>` : updateState.status === "downloaded" ? `<button class="primary" id="install-update-settings">立即安装</button>` : `<button class="ghost" id="check-update">${updateState.status === "checking" ? "检查中..." : "检查更新"}</button>`;
  return `<header><div><div class="eyebrow">PREFERENCES</div><h1>设置</h1><p>管理服务端口、通知方式和更新选项。</p></div></header><section class="panel settings"><label>监听端口<input id="port" value="${snapshot.port}" type="number" min="1" max="65535"></label><label>通知方式<select id="mode"><option ${mode === "Windows 通知" ? "selected" : ""}>Windows 通知</option><option ${mode === "软件通知" ? "selected" : ""}>软件通知</option><option ${mode === "同时通知" ? "selected" : ""}>同时通知</option></select></label><label class="check"><input type="checkbox" id="sound" ${snapshot.sound ? "checked" : ""}>播放通知提示音</label><label class="check"><input type="checkbox" id="quiet" ${snapshot.quiet_mode ? "checked" : ""}>免打扰模式（仅记录，不弹窗）</label><div class="setting-divider"></div><div class="version-row"><div><span>当前版本</span><strong>v${CURRENT_VERSION}</strong></div>${versionAction}</div><div class="update-result ${updateState.status}">${updateMessage()}</div>${saveState ? `<div class="save-result ${saveState.startsWith("保存失败") ? "error" : "success"}">${esc(saveState)}</div>` : ""}<button class="primary" id="save">保存设置</button></section>`;
}
function logs() { return `<header><div><div class="eyebrow">RUNTIME DIAGNOSTICS</div><h1>运行日志</h1><p>实时查看服务、通知和系统事件。</p></div><div class="header-actions"><span class="status ok">实时更新</span><button class="ghost" id="clear-logs">清空日志</button></div></header><section class="panel log-panel"><pre class="log-output">${esc(snapshot.logs || "暂无运行日志")}</pre></section>`; }
function updateMessage() {
  if (updateState.status === "available") return `发现 v${esc(updateState.version || "")}，点击“立即更新”下载并安装。`;
  if (updateState.status === "downloading") return "正在下载安装包，请稍候...";
  if (updateState.status === "downloaded") return "安装包已下载完成，可以立即安装。";
  if (updateState.status === "installing") return "正在启动安装程序...";
  if (updateState.status === "latest") return "已经是最新版本。";
  return updateState.note || "";
}
function about() { return `<header><div><div class="eyebrow">ABOUT XUNDA</div><h1>关于</h1><p>版本信息、项目链接、GitHub Release 更新和运行诊断。</p></div></header><section class="about-grid"><section class="panel about-card"><div class="about-card-head"><h2>关于讯达</h2><span>本地 WebHook 通知中心</span></div><div class="about-row"><span>讯达版本</span><strong>v${CURRENT_VERSION}</strong></div><div class="about-row"><span>技术栈</span><strong>Tauri 2 · Rust · WebView2</strong></div><div class="about-row"><span>项目地址</span><strong>github.com/laoluonb/XundaNotify</strong></div><div class="about-actions"><button class="ghost" data-external="https://github.com/laoluonb/XundaNotify">↗ 打开项目主页</button><button class="ghost" data-external="https://github.com/laoluonb/XundaNotify/issues">↗ 反馈问题</button></div></section><section class="panel about-card release-card"><div class="about-card-head"><h2>GitHub Release 更新</h2><span>当前版本 v${CURRENT_VERSION}</span></div><div class="about-row"><span>状态</span><strong>${updateState.status === "available" || updateState.status === "downloaded" ? "发现新版本" : updateState.status === "latest" ? "已是最新版本" : "未检查"}</strong></div><div class="about-row"><span>最新版本</span><strong>${updateState.version ? `v${esc(updateState.version)}` : `v${CURRENT_VERSION}`}</strong></div><div class="release-note">${esc(updateState.note || updateMessage() || "点击检查更新，获取 GitHub Release 的最新安装包。")}</div><div class="about-actions"><button class="primary" id="check-update-about">${updateState.status === "checking" ? "检查中..." : "检查更新"}</button>${updateState.status === "available" ? `<button class="ghost" id="open-update-about">立即下载</button>` : updateState.status === "downloaded" ? `<button class="primary" id="install-update-about">立即安装</button>` : ""}</div></section></section>`; }

function platformForTitle(title: string) { if (title.startsWith("微信")) return "wechat"; if (title.startsWith("QQ")) return "qq"; if (title.startsWith("钉钉")) return "dingtalk"; if (title.startsWith("飞书")) return "feishu"; return "xunda"; }
function softwareNoticeLayer() {
  if (!softwareNotices.length) return "";
  return `<div class="software-notices">${softwareNotices.map((notice) => `<article class="software-notice"><div class="software-notice-head"><span class="software-app-mark">✦</span><strong>讯达通知中心</strong><button class="notice-close" data-dismiss-notice="${notice.id}" aria-label="关闭">×</button></div><div class="software-notice-body"><img src="/notifications/${platformForTitle(notice.title)}.png" alt=""><div><strong>${esc(notice.title)}</strong><p>${esc(notice.body)}</p><time>接收时间 ${esc(notice.time)}</time></div></div></article>`).join("")}</div>`;
}

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
async function checkForUpdates() { updateState = { status: "checking" }; render(); try { const response = await fetch("https://api.github.com/repos/laoluonb/XundaNotify/releases/latest", { headers: { Accept: "application/vnd.github+json" } }); if (!response.ok) throw new Error(`HTTP ${response.status}`); const release = await response.json() as { tag_name?: string; html_url?: string; body?: string; assets?: Array<{ name?: string; browser_download_url?: string }> }; const latest = (release.tag_name || "").replace(/^v/, ""); const isNewer = latest && latest !== CURRENT_VERSION && latest.localeCompare(CURRENT_VERSION, undefined, { numeric: true }) > 0; const asset = (release.assets || []).find((item) => /x64-setup\.exe$/i.test(item.name || "")) || (release.assets || []).find((item) => /setup\.exe$/i.test(item.name || "")) || (release.assets || []).find((item) => /\.msi$/i.test(item.name || "")); updateState = isNewer ? { status: "available", version: latest, url: asset?.browser_download_url || release.html_url, note: release.body?.split("\n").find(Boolean) || "GitHub Release 已发布更新" } : { status: "latest" }; } catch (error) { updateState = { status: "error", note: `检查更新失败：${String(error)}` }; } render(); }
async function downloadUpdate() { if (!updateState.url || !updateState.version) return; updateState = { ...updateState, status: "downloading" }; render(); try { const installerPath = await invoke<string>("download_update", { url: updateState.url, version: updateState.version }); updateState = { ...updateState, status: "downloaded", installerPath }; } catch (error) { updateState = { ...updateState, status: "error", note: `下载更新失败：${String(error)}` }; } render(); }
async function installUpdate() { if (!updateState.installerPath) return; updateState = { ...updateState, status: "installing" }; render(); try { await invoke("install_update", { path: updateState.installerPath }); } catch (error) { updateState = { ...updateState, status: "error", note: `启动安装程序失败：${String(error)}` }; render(); } }
function bindActions() { document.querySelectorAll<HTMLButtonElement>("[data-view]").forEach((button) => button.onclick = () => { active = button.dataset.view!; settingsDirty = false; saveState = ""; render(); }); const toggle = document.querySelector<HTMLButtonElement>("#toggle"); if (toggle) toggle.onclick = async () => { await invoke("toggle_server"); refresh(); }; const test = document.querySelector<HTMLButtonElement>("#test"); if (test) test.onclick = async () => { await invoke("test_notification"); refresh(); }; const copy = document.querySelector<HTMLButtonElement>("#copy"); if (copy) copy.onclick = () => navigator.clipboard.writeText(`http://${snapshot.address}/?msg=`); const settingFields = document.querySelectorAll<HTMLInputElement | HTMLSelectElement>("#port, #mode, #sound, #quiet"); settingFields.forEach((field) => field.addEventListener("input", () => { settingsDirty = true; })); settingFields.forEach((field) => field.addEventListener("change", () => { settingsDirty = true; })); const save = document.querySelector<HTMLButtonElement>("#save"); if (save) save.onclick = async () => { const port = Number((document.querySelector("#port") as HTMLInputElement).value); const mode = (document.querySelector("#mode") as HTMLSelectElement).value; const sound = (document.querySelector("#sound") as HTMLInputElement).checked; const quiet = (document.querySelector("#quiet") as HTMLInputElement).checked; try { await invoke("save_settings", { input: { port, mode, sound, quiet } }); saveState = "设置已保存"; settingsDirty = false; await refresh(); } catch (error) { saveState = `保存失败：${String(error)}`; render(); } }; const clear = document.querySelector<HTMLButtonElement>("#clear-logs"); if (clear) clear.onclick = async () => { await invoke("clear_logs"); await refresh(); }; const check = document.querySelector<HTMLButtonElement>("#check-update"); if (check) check.onclick = checkForUpdates; const checkAbout = document.querySelector<HTMLButtonElement>("#check-update-about"); if (checkAbout) checkAbout.onclick = checkForUpdates; const checkVersion = document.querySelector<HTMLButtonElement>("#check-update-version"); if (checkVersion) checkVersion.onclick = checkForUpdates; const open = document.querySelector<HTMLButtonElement>("#open-update"); if (open) open.onclick = downloadUpdate; const openAbout = document.querySelector<HTMLButtonElement>("#open-update-about"); if (openAbout) openAbout.onclick = downloadUpdate; const downloadSettings = document.querySelector<HTMLButtonElement>("#download-update-settings"); if (downloadSettings) downloadSettings.onclick = downloadUpdate; const install = document.querySelector<HTMLButtonElement>("#install-update"); if (install) install.onclick = installUpdate; const installSettings = document.querySelector<HTMLButtonElement>("#install-update-settings"); if (installSettings) installSettings.onclick = installUpdate; const installAbout = document.querySelector<HTMLButtonElement>("#install-update-about"); if (installAbout) installAbout.onclick = installUpdate; document.querySelectorAll<HTMLButtonElement>("[data-dismiss-notice]").forEach((button) => button.onclick = () => { softwareNotices = softwareNotices.filter((item) => item.id !== Number(button.dataset.dismissNotice)); render(); }); document.querySelectorAll<HTMLButtonElement>("[data-external]").forEach((button) => button.onclick = () => window.open(button.dataset.external, "_blank")); }
async function setupEvents() { if (eventReady) return; eventReady = true; await listen<Message>("software-notification", (event) => { const notice = { ...event.payload, id: ++noticeId }; softwareNotices = [...softwareNotices, notice].slice(-3); render(); window.setTimeout(() => { softwareNotices = softwareNotices.filter((item) => item.id !== notice.id); render(); }, 9000); }); }
setupEvents(); render(); refresh(); setInterval(refresh, 1000);

