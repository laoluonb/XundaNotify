import "./style.css";
import { invoke } from "@tauri-apps/api/core";

type Message = { time: string; title: string; body: string };
type Snapshot = { running: boolean; port: number; address: string; messages: number; history: Message[]; logs: string };

const app = document.querySelector<HTMLDivElement>("#app")!;
let active = "overview";
let snapshot: Snapshot = { running: false, port: 8080, address: "127.0.0.1:8080", messages: 0, history: [], logs: "" };

const esc = (value: string) => value.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
const icon = (name: string) => `<span class="icon icon-${name}"></span>`;

function render() {
  const nav = [["overview", "总览", "grid"], ["history", "消息历史", "history"], ["settings", "设置", "sliders"], ["logs", "运行日志", "terminal"]] as const;
  app.innerHTML = `<div class="shell">
    <aside class="sidebar">
      <div class="brand"><div class="brand-mark">✦</div><div><strong>讯达</strong><small>通知中心</small></div></div>
      <div class="nav-label">工作台</div>
      <nav>${nav.map(([key, label, ico]) => `<button class="nav ${active === key ? "active" : ""}" data-view="${key}">${icon(ico)}<span>${label}</span></button>`).join("")}</nav>
      <div class="side-footer"><span class="live-dot"></span> 本机通知服务<small>v1.2.0 · Tauri / Windows</small></div>
    </aside>
    <main class="content">${active === "overview" ? overview() : active === "history" ? history() : active === "settings" ? settings() : logs()}</main>
  </div>`;
  document.querySelectorAll<HTMLButtonElement>("[data-view]").forEach((button) => button.onclick = () => { active = button.dataset.view!; render(); });
  bindActions();
  if (active === "logs") requestAnimationFrame(() => { const el = document.querySelector<HTMLElement>(".log-output"); if (el) el.scrollTop = el.scrollHeight; });
}

function overview() { return `<header><div><div class="eyebrow">LOCAL WEBHOOK GATEWAY</div><h1>消息接收台</h1><p>把手机上的重要消息，安静地送到你的 Windows 桌面。</p></div><span class="status ${snapshot.running ? "ok" : "off"}">${snapshot.running ? "服务运行中" : "服务未启动"}</span></header>
  <section class="stats"><div class="stat"><small>服务状态</small><strong>${snapshot.running ? "运行中" : "未启动"}</strong><span>局域网接收服务</span></div><div class="stat cyan"><small>今日消息</small><strong>${snapshot.messages}</strong><span>条通知已送达</span></div><div class="stat violet"><small>监听地址</small><strong>${esc(snapshot.address)}</strong><span>提供给手机端 WebHook</span></div></section>
  <section class="workspace"><div class="panel endpoint"><div class="panel-head"><div><small class="eyebrow">WEBHOOK ENDPOINT</small><h2>接收地址</h2></div><button class="primary" id="toggle">${snapshot.running ? "停止服务" : "启动服务"}</button></div><p>将下方地址填入 SmsForwarder 的 WebHook，支持 GET / POST。</p><div class="address"><code>http://${esc(snapshot.address)}/?msg=</code><button class="ghost" id="copy">复制地址</button></div><button class="ghost test" id="test">发送测试通知</button></div><div class="panel activity"><div class="panel-head"><div><small class="eyebrow">RECENT ACTIVITY</small><h2>最近活动</h2></div><button class="link" data-view="history">查看全部</button></div>${snapshot.history.slice(0, 6).map((m) => `<div class="activity-row"><time>${esc(m.time)}</time><div><strong>${esc(m.title)}</strong><span>${esc(m.body)}</span></div></div>`).join("") || `<div class="empty">暂无消息</div>`}</div></section>`; }
function history() { return `<header><div><div class="eyebrow">MESSAGE ARCHIVE</div><h1>消息历史</h1><p>所有接收到的通知都会保存在这里。</p></div></header><section class="panel table-panel"><div class="table-head"><span>接收时间</span><span>标题</span><span>消息</span></div>${snapshot.history.map((m) => `<div class="table-row"><time>${esc(m.time)}</time><strong>${esc(m.title)}</strong><span>${esc(m.body)}</span></div>`).join("") || `<div class="empty">暂无历史消息</div>`}</section>`; }
function settings() { return `<header><div><div class="eyebrow">PREFERENCES</div><h1>设置</h1><p>管理服务端口、通知方式和免打扰选项。</p></div></header><section class="panel settings"><label>监听端口<input id="port" value="${snapshot.port}" type="number" min="1" max="65535"></label><label>通知方式<select id="mode"><option>Windows 通知</option><option>软件通知</option><option>同时通知</option></select></label><label class="check"><input type="checkbox" id="sound" checked>播放通知提示音</label><label class="check"><input type="checkbox" id="quiet">免打扰模式（仅记录，不弹窗）</label><button class="primary" id="save">保存设置</button></section>`; }
function logs() { return `<header><div><div class="eyebrow">RUNTIME DIAGNOSTICS</div><h1>运行日志</h1><p>实时查看服务、通知和系统事件。</p></div><span class="status ok">实时更新</span></header><section class="panel log-panel"><pre class="log-output">${esc(snapshot.logs || "暂无运行日志")}</pre></section>`; }

async function refresh() { try { snapshot = await invoke<Snapshot>("snapshot"); render(); } catch { render(); } }
function bindActions() { document.querySelectorAll<HTMLButtonElement>("[data-view]").forEach((button) => button.onclick = () => { active = button.dataset.view!; render(); }); const toggle = document.querySelector<HTMLButtonElement>("#toggle"); if (toggle) toggle.onclick = async () => { await invoke("toggle_server"); refresh(); }; const test = document.querySelector<HTMLButtonElement>("#test"); if (test) test.onclick = async () => { await invoke("test_notification"); refresh(); }; const copy = document.querySelector<HTMLButtonElement>("#copy"); if (copy) copy.onclick = () => navigator.clipboard.writeText(`http://${snapshot.address}/?msg=`); const save = document.querySelector<HTMLButtonElement>("#save"); if (save) save.onclick = async () => { await invoke("save_settings", { port: Number((document.querySelector("#port") as HTMLInputElement).value), mode: (document.querySelector("#mode") as HTMLSelectElement).value }); refresh(); }; }
render(); refresh(); setInterval(refresh, 1000);
