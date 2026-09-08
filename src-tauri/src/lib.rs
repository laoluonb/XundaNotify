#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use chrono::Local;
use serde::{Deserialize, Serialize};
use std::{fs, io::{Read, Write}, net::{TcpListener, TcpStream}, path::PathBuf, process::Command, sync::{Arc, Mutex}, thread, time::Duration};
use tauri::{menu::{MenuBuilder, MenuItemBuilder}, tray::{TrayIconBuilder, TrayIconEvent}, AppHandle, Emitter, Manager, State, WindowEvent};
use tauri_plugin_notification::NotificationExt;

#[derive(Clone, Serialize, Deserialize)]
pub struct Message { pub time: String, pub title: String, pub body: String }

#[derive(Clone, Serialize)]
pub struct Snapshot { pub running: bool, pub port: u16, pub address: String, pub messages: usize, pub history: Vec<Message>, pub logs: String, pub notification_mode: String, pub sound: bool, pub quiet_mode: bool }

#[derive(Deserialize)]
pub struct SettingsInput { pub port: u16, pub mode: String, pub sound: bool, pub quiet: bool }
#[derive(Clone, Serialize, Deserialize)]
struct StoredSettings { port: u16, notification_mode: String, sound: bool, quiet_mode: bool }

pub struct AppState { pub running: Mutex<bool>, pub port: Mutex<u16>, pub history: Mutex<Vec<Message>>, pub logs: Mutex<String>, pub stop: Mutex<bool>, pub notification_mode: Mutex<String>, pub sound: Mutex<bool>, pub quiet_mode: Mutex<bool> }
pub type Shared = Arc<AppState>;

fn data_dir() -> PathBuf { std::env::var_os("APPDATA").map(PathBuf::from).unwrap_or_else(|| PathBuf::from("." )).join("XundaNotify") }
fn log_path() -> PathBuf { data_dir().join("xunda-tauri.log") }
fn write_log(state: &Shared, line: impl AsRef<str>) { let line = format!("{}  {}\n", Local::now().format("%Y-%m-%d %H:%M:%S"), line.as_ref()); if let Ok(mut logs)=state.logs.lock(){ logs.push_str(&line); } let _=fs::create_dir_all(data_dir()); let _=fs::OpenOptions::new().create(true).append(true).open(log_path()).and_then(|mut f| f.write_all(line.as_bytes())); }
fn clear_log() { let _=fs::create_dir_all(data_dir()); let _=fs::write(log_path(), ""); }

#[tauri::command]
fn clear_logs(state: State<'_, Shared>) -> Result<(), String> {
    if let Ok(mut logs) = state.logs.lock() { logs.clear(); }
    clear_log();
    Ok(())
}

fn updates_dir() -> PathBuf { std::env::temp_dir().join("XundaNotify-updates") }

#[tauri::command]
fn download_update(url: String, version: String) -> Result<String, String> {
    let parsed = reqwest::Url::parse(&url).map_err(|e| format!("更新地址无效：{}", e))?;
    let host = parsed.host_str().unwrap_or_default();
    if parsed.scheme() != "https" || !matches!(host, "github.com" | "objects.githubusercontent.com" | "github-releases.githubusercontent.com") {
        return Err("只允许从 GitHub 下载更新包".into());
    }
    let response = reqwest::blocking::Client::builder().user_agent("XundaNotify-Updater").build().map_err(|e| e.to_string())?.get(parsed).send().map_err(|e| format!("连接 GitHub 失败：{}", e))?;
    if !response.status().is_success() { return Err(format!("下载失败：HTTP {}", response.status())); }
    let filename = if url.to_ascii_lowercase().contains(".msi") { format!("XundaNotify-{}-x64.msi", version) } else { format!("XundaNotify-{}-x64-setup.exe", version) };
    fs::create_dir_all(updates_dir()).map_err(|e| e.to_string())?;
    let path = updates_dir().join(filename);
    let bytes = response.bytes().map_err(|e| format!("读取安装包失败：{}", e))?;
    fs::write(&path, bytes).map_err(|e| format!("保存安装包失败：{}", e))?;
    Ok(path.to_string_lossy().into_owned())
}

#[tauri::command]
fn install_update(path: String) -> Result<(), String> {
    let path = PathBuf::from(path);
    if !path.exists() { return Err("安装包不存在，请重新下载".into()); }
    if path.parent() != Some(updates_dir().as_path()) { return Err("安装包路径不受信任".into()); }
    if path.extension().and_then(|value| value.to_str()).map(|value| value.eq_ignore_ascii_case("msi")).unwrap_or(false) { Command::new("msiexec.exe").args(["/i", path.to_string_lossy().as_ref()]).spawn().map_err(|e| format!("启动安装程序失败：{}", e))?; } else { Command::new(&path).spawn().map_err(|e| format!("启动安装程序失败：{}", e))?; }
    Ok(())
}

fn history_path() -> PathBuf { data_dir().join("history-tauri.json") }
fn settings_path() -> PathBuf { data_dir().join("settings-tauri.json") }
fn load_settings() -> StoredSettings {
    fs::read_to_string(settings_path()).ok().and_then(|text| serde_json::from_str::<StoredSettings>(&text).ok()).unwrap_or(StoredSettings { port: 8080, notification_mode: "both".into(), sound: true, quiet_mode: false })
}
fn save_settings_file(settings: &StoredSettings) { let _=fs::create_dir_all(data_dir()); let _=fs::write(settings_path(), serde_json::to_string_pretty(settings).unwrap_or_else(|_| "{}".into())); }
fn load_history() -> Vec<Message> {
    fs::read_to_string(history_path()).ok().and_then(|text| serde_json::from_str::<Vec<Message>>(&text).ok()).unwrap_or_default()
}
fn save_history(history: &[Message]) {
    let _ = fs::create_dir_all(data_dir());
    let _ = fs::write(history_path(), serde_json::to_string_pretty(history).unwrap_or_else(|_| "[]".into()));
}

fn clean_value(value: &str) -> String {
    urlencoding::decode(value).unwrap_or_else(|_| value.into()).replace('+', " ").replace('\r', "")
}

fn clean_sender(value: &str) -> String {
    let mut text = clean_value(value).trim().to_string();
    for prefix in ["微信-", "QQ-", "TIM-", "钉钉-", "飞书-"] {
        if let Some(rest) = text.strip_prefix(prefix) { text = rest.trim().to_string(); break; }
    }
    if looks_like_timestamp(&text) {
        text = text[10..].trim_start_matches([' ', '-', '_']).to_string();
    }
    if text.len() >= 8 && text.as_bytes().get(2) == Some(&b':') && text.as_bytes().get(5) == Some(&b':') {
        text = text[8..].trim_start_matches([' ', '-', '_']).to_string();
    }
    if let Some(open) = text.find('[') {
        if let Some(close_rel) = text[open..].find(']') {
            let close = open + close_rel;
            let marker = &text[open + 1..close];
            if let Some(count) = marker.strip_suffix('条') {
                if count.chars().all(|c| c.is_ascii_digit()) {
                text = format!("{}{}", &text[..open], &text[close + 1..]);
                }
            }
        }
    }
    if let Some(pos) = text.find("条新消息)") {
        if let Some(open) = text[..pos].rfind('(') { text.truncate(open); }
    }
    text = regexless_strip_metadata(&text);
    text.trim_matches(['-', '_', ' ', '　'].as_ref()).to_string()
}

fn looks_like_timestamp(value: &str) -> bool {
    let bytes = value.as_bytes();
    bytes.len() >= 10
        && bytes[..10].iter().enumerate().all(|(index, byte)| {
            if index == 4 || index == 7 { *byte == b'-' } else { byte.is_ascii_digit() }
        })
}

fn regexless_strip_metadata(value: &str) -> String {
    let mut text = value.trim().to_string();
    if let Some(pos) = text.rfind(']') {
        let suffix = &text[pos + 1..];
        if suffix.trim().is_empty() { text = text[..pos].to_string(); }
    }
    for marker in ["[1条]", "[2条]", "[3条]", "[4条]", "[5条]", "[6条]", "[7条]", "[8条]", "[9条]"] {
        text = text.replace(marker, "");
    }
    let bytes = text.as_bytes();
    if bytes.len() >= 8 && bytes.iter().all(|b| b.is_ascii_digit() || *b == b'-' || *b == b':' || *b == b' ' || *b == b'[' || *b == b']') {
        return String::new();
    }
    text
}

fn is_metadata_line(value: &str) -> bool {
    let line = value.trim();
    let lower = line.to_lowercase();
    lower.starts_with("uid")
        || lower.starts_with("timestamp")
        || lower.starts_with("package")
        || line.contains("com.tencent.")
        || (line.len() >= 10 && looks_like_timestamp(line) && line.len() <= 24)
}

fn parse_message(raw: &str) -> (String, String) {
    let mut package = String::new(); let mut sender = String::new(); let mut group = String::new(); let mut content = String::new();
    let mut input = raw.trim().trim_start_matches("/?msg=").to_string();
    if let Some(query) = input.strip_prefix('?') { input = query.to_string(); }
    if input.trim_start().starts_with('{') {
        if let Ok(value) = serde_json::from_str::<serde_json::Value>(&input) {
            let get = |keys: &[&str]| keys.iter().find_map(|key| value.get(*key).and_then(|v| v.as_str()).map(clean_value)).unwrap_or_default();
            package=get(&["package","pkg","from","app_package","app包名"]); sender=clean_sender(&get(&["sender","nickname","name","title","通知标题"])); group=clean_sender(&get(&["group","group_name","chat","conversation","群名"])); content=get(&["content","msg","message","text","body","通知内容"]);
        }
    }
    if package.is_empty() && sender.is_empty() && content.is_empty() {
        for pair in input.split('&') { let mut it=pair.splitn(2,'='); let k=it.next().unwrap_or("").to_lowercase(); let v=clean_value(it.next().unwrap_or("")); match k.as_str(){"package"|"pkg"|"from"|"app_package"=>package=v,"sender"|"nickname"|"name"|"title"|"通知标题"=>sender=clean_sender(&v),"group"|"group_name"|"chat"|"conversation"|"群名"=>group=clean_sender(&v),"content"|"msg"|"message"|"text"|"body"|"通知内容"=>content=v,_=>{}} }
    }
    if content.is_empty() && input.contains(':') && !input.contains("=") { content=input.to_string(); }
    let mut lines: Vec<String> = content.lines().map(str::trim).filter(|line| !line.is_empty()).filter(|line| !is_metadata_line(line)).map(str::to_string).collect();
    if sender.is_empty() && !lines.is_empty() { let first=lines[0].clone(); if first.contains('：') || first.contains(':') { let mut split=first.splitn(2, |c| c=='：' || c==':'); sender=clean_sender(split.next().unwrap_or("")); lines[0]=split.next().unwrap_or("").trim().to_string(); } }
    if lines.last().map(|line| clean_sender(line) == sender).unwrap_or(false) { lines.pop(); }
    if sender.is_empty() && lines.len() >= 2 { let candidate=clean_sender(lines.last().cloned().unwrap_or_default().as_str()); if !candidate.is_empty() { sender=candidate; lines.pop(); } }
    if group.is_empty() && lines.len() >= 2 { let candidate=lines.last().cloned().unwrap_or_default(); let terminal = candidate.chars().last().map(|c| matches!(c, '。'|'！'|'？'|'!'|'?'|'，'|',' )).unwrap_or(false); if candidate.len() <= 40 && candidate != sender && !terminal { group=candidate; lines.pop(); } }
    content=lines.join("\n").trim().to_string(); if content.is_empty(){content="新消息".into();}
    let software = match package.as_str(){"com.tencent.mm"=>"微信", "com.tencent.mobileqq"=>"QQ", "com.tencent.tim"=>"TIM", "com.tencent.wework"=>"企业微信", "com.alibaba.android.rimet"=>"钉钉", "com.ss.android.lark"=>"飞书", "com.whatsapp"=>"WhatsApp", "org.telegram.messenger"=>"Telegram", "com.sina.weibo"=>"微博", "com.android.mms"=>"短信", "com.google.android.gm"=>"Gmail", _=>""};
    let title = if software.is_empty() {
        sender.clone()
    } else if !sender.is_empty() && !group.is_empty() {
        format!("{}-{}-{}", software, group, sender)
    } else if !sender.is_empty() {
        format!("{}-{}", software, sender)
    } else if !group.is_empty() {
        format!("{}-{}", software, group)
    } else {
        software.to_string()
    };
    (if title.trim_matches('-').is_empty(){"新消息".into()}else{title}, content)
}

fn platform_from_title(title: &str) -> &'static str {
    if title.starts_with("微信") { "wechat" }
    else if title.starts_with("QQ") { "qq" }
    else if title.starts_with("钉钉") { "dingtalk" }
    else if title.starts_with("飞书") { "feishu" }
    else { "xunda" }
}

fn platform_icon_path(app: &AppHandle, platform: &str) -> PathBuf {
    let filename = format!("{}.png", platform);
    let candidates = [
        app.path().resource_dir().ok().map(|path| path.join("icons").join("notifications").join(&filename)),
        Some(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("icons").join("notifications").join(&filename)),
    ];
    let path = candidates.into_iter().flatten().find(|path| path.exists()).unwrap_or_else(|| {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("icons").join("notifications").join("xunda.png")
    });
    path
}

#[cfg(windows)]
fn show_windows_toast(title: &str, body: &str, received_at: &str, icon_path: &PathBuf, sound_enabled: bool) -> Result<(), String> {
    let text = format!("{}\n接收时间 {}", if body.trim().is_empty() { "新消息" } else { body }, received_at);
    let mut toast = winrt_notification::Toast::new("com.xunda.notify")
        .title("讯达通知中心")
        .text1(title)
        .text2(&text)
        .image(icon_path.as_path(), "平台图标");
    toast = if sound_enabled {
        toast.sound(Some(winrt_notification::Sound::Default))
    } else {
        toast.sound(None)
    };
    toast.show().map_err(|error| format!("{}", error))
}

fn notify(state: &Shared, app: &AppHandle, title: &str, body: &str, received_at: &str) {
    if *state.quiet_mode.lock().unwrap_or_else(|e| e.into_inner()) { return; }
    let mode = state.notification_mode.lock().unwrap_or_else(|e| e.into_inner()).clone();
    let message = Message { time: received_at.to_string(), title: title.to_string(), body: body.to_string() };
    let notification_body = format!("{}\n{}\n接收时间 {}", title, if body.trim().is_empty() { "新消息" } else { body }, received_at);
    if mode == "windows" || mode == "both" {
        let sound_enabled = *state.sound.lock().unwrap_or_else(|e| e.into_inner());
        let icon_path = platform_icon_path(app, platform_from_title(title));
        #[cfg(windows)]
        let result = show_windows_toast(title, body, received_at, &icon_path, sound_enabled);
        #[cfg(not(windows))]
        let result = {
            let mut builder = app.notification().builder()
                .title("讯达通知中心")
                .body(notification_body.clone())
                .icon(icon_path.to_string_lossy().into_owned());
            if sound_enabled { builder = builder.sound("default"); }
            builder.show().map_err(|error| error.to_string())
        };
        if let Err(error) = result { write_log(state, format!("Windows 通知发送失败：{}", error)); }
    }
    if mode == "software" || mode == "both" {
        let _ = app.emit("software-notification", message);
    }
}

fn handle_client(mut stream: TcpStream, state: Shared, app: AppHandle) {
    let mut buf=[0u8;16384]; let n=stream.read(&mut buf).unwrap_or(0); let req=String::from_utf8_lossy(&buf[..n]); let request_line=req.lines().next().unwrap_or(""); let target=request_line.split_whitespace().nth(1).unwrap_or(""); let body=req.split("\r\n\r\n").nth(1).unwrap_or(""); let raw=if !body.trim().is_empty(){body}else{target.split_once('?').map(|(_,query)| query).unwrap_or(target)}; let (title,body)=parse_message(raw); let received_at=Local::now().format("%H:%M:%S").to_string(); let message=Message{time:received_at.clone(),title:title.clone(),body:body.clone()}; if let Ok(mut h)=state.history.lock(){h.insert(0,message.clone());h.truncate(500);save_history(&h);} write_log(&state, format!("收到消息：标题={}，正文长度={}",title,body.len())); notify(&state,&app,&title,&body,&received_at); let response="HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: 11\r\nConnection: close\r\n\r\n{\"ok\":true}"; let _=stream.write_all(response.as_bytes()); let _=app.emit("message", message);
}

fn start_listener(state: Shared, app: AppHandle, port: u16) { thread::spawn(move || { let listener=match TcpListener::bind(("0.0.0.0",port)){Ok(v)=>v,Err(e)=>{write_log(&state,format!("服务启动失败：{}",e));return;}}; let _=listener.set_nonblocking(true); write_log(&state,format!("WebHook 服务已启动：端口 {}",port)); loop { if *state.stop.lock().unwrap_or_else(|e|e.into_inner()){break;} match listener.accept(){Ok((stream,_))=>handle_client(stream,state.clone(),app.clone()),Err(_)=>thread::sleep(Duration::from_millis(100))} } write_log(&state,"WebHook 服务已停止"); }); }

#[tauri::command]
fn snapshot(state: State<'_, Shared>) -> Snapshot { let port=*state.port.lock().unwrap(); let history=state.history.lock().unwrap().clone(); Snapshot{running:*state.running.lock().unwrap(),port,address:format!("127.0.0.1:{}",port),messages:history.len(),history,logs:state.logs.lock().unwrap().clone(),notification_mode:state.notification_mode.lock().unwrap().clone(),sound:*state.sound.lock().unwrap(),quiet_mode:*state.quiet_mode.lock().unwrap()} }
#[tauri::command]
fn toggle_server(state: State<'_, Shared>, app: AppHandle) { let mut running=state.running.lock().unwrap(); if *running { *state.stop.lock().unwrap()=true; *running=false; write_log(&state,"用户停止服务"); } else { *state.stop.lock().unwrap()=false; *running=true; let port=*state.port.lock().unwrap(); start_listener(state.inner().clone(),app,port); } }
#[tauri::command]
fn test_notification(state: State<'_, Shared>, app: AppHandle) { let now=Local::now().format("%H:%M:%S").to_string(); let message=Message{time:now.clone(),title:"讯达-测试通知".into(),body:"新消息：讯达通知中心运行正常".into()}; state.history.lock().unwrap().insert(0,message.clone()); save_history(&state.history.lock().unwrap()); write_log(&state,"发送测试通知"); notify(&state,&app,&message.title,&message.body,&now); let _=app.emit("message", message); }
#[tauri::command]
fn save_settings(input: SettingsInput, state: State<'_, Shared>) -> Result<(), String> { if !(1..=65535).contains(&input.port){return Err("端口范围无效".into())}; let notification_mode=match input.mode.as_str(){"Windows 通知"=>"windows", "软件通知"=>"software", _=>"both"}.to_string(); *state.port.lock().unwrap()=input.port; *state.notification_mode.lock().unwrap()=notification_mode.clone(); *state.sound.lock().unwrap()=input.sound; *state.quiet_mode.lock().unwrap()=input.quiet; save_settings_file(&StoredSettings{port:input.port,notification_mode,sound:input.sound,quiet_mode:input.quiet}); write_log(&state,format!("设置已保存：端口={}，通知方式={}，免打扰={}",input.port,input.mode,input.quiet)); Ok(()) }

pub fn run() { clear_log(); let settings=load_settings(); let state:Shared=Arc::new(AppState{running:Mutex::new(false),port:Mutex::new(settings.port),history:Mutex::new(load_history()),logs:Mutex::new(String::new()),stop:Mutex::new(false),notification_mode:Mutex::new(settings.notification_mode),sound:Mutex::new(settings.sound),quiet_mode:Mutex::new(settings.quiet_mode)}); tauri::Builder::default().manage(state.clone()).plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| { if let Some(window)=app.get_webview_window("main") { let _=window.show(); let _=window.unminimize(); let _=window.set_focus(); } })).plugin(tauri_plugin_notification::init()).invoke_handler(tauri::generate_handler![snapshot,toggle_server,test_notification,save_settings,clear_logs,download_update,install_update]).setup(move |app| { let show=MenuItemBuilder::with_id("show","显示窗口").build(app)?; let quit=MenuItemBuilder::with_id("quit","退出程序").build(app)?; let menu=MenuBuilder::new(app).items(&[&show,&quit]).build()?; TrayIconBuilder::new().menu(&menu).show_menu_on_left_click(true).on_tray_icon_event(|tray,event| { if let TrayIconEvent::DoubleClick{..}=event { if let Some(window)=tray.app_handle().get_webview_window("main"){let _=window.show();let _=window.unminimize();let _=window.set_focus();} } }).on_menu_event(|app,event| { if event.id().as_ref()=="show" {if let Some(w)=app.get_webview_window("main"){let _=w.show();let _=w.unminimize();let _=w.set_focus();}} else if event.id().as_ref()=="quit" {app.exit(0);} }).build(app)?; Ok(()) }).on_window_event(|window,event| { if let WindowEvent::CloseRequested{api,..}=event { api.prevent_close(); let _=window.hide(); } }).build(tauri::generate_context!()).expect("error while running tauri application").run(|_,event| { if let tauri::RunEvent::ExitRequested{..}=event {clear_log();} }); }

#[cfg(test)]
mod tests {
    use super::parse_message;

    #[test]
    fn title_rules_match_notification_contract() {
        assert_eq!(parse_message(r#"{"package":"com.tencent.mm","sender":"张三","content":"你好"}"#).0, "微信-张三");
        assert_eq!(parse_message(r#"{"package":"com.tencent.mm","sender":"不熬","group":"股羊六群","content":"29.9的羽绒服退款"}"#).0, "微信-股羊六群-不熬");
        assert_eq!(parse_message(r#"{"package":"com.tencent.mobileqq","sender":"李四","group":"工作群","content":"收到"}"#).0, "QQ-工作群-李四");
        assert_eq!(parse_message(r#"{"package":"com.example.unknown","sender":"赵六","group":"测试群","content":"测试消息"}"#).0, "赵六");
        assert_eq!(parse_message(r#"{"package":"com.tencent.mm","sender":"张三","content":""}"#).1, "新消息");
        let (title, body) = parse_message("from=com.tencent.mm&content=com.tencent.mm%0A不熬：29.9的羽绒服退款%0A股羊六群%0AUID：10399");
        assert_eq!(title, "微信-股羊六群-不熬");
        assert_eq!(body, "29.9的羽绒服退款");
    }
}

