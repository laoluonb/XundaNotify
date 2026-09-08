#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use chrono::Local;
use serde::{Deserialize, Serialize};
use std::{fs, io::{Read, Write}, net::{TcpListener, TcpStream}, path::PathBuf, sync::{Arc, Mutex}, thread, time::Duration};
use tauri::{menu::{MenuBuilder, MenuItemBuilder}, tray::{TrayIconBuilder, TrayIconEvent}, AppHandle, Emitter, Manager, State, WindowEvent};
use tauri_plugin_notification::NotificationExt;

#[derive(Clone, Serialize, Deserialize)]
pub struct Message { pub time: String, pub title: String, pub body: String }

#[derive(Clone, Serialize)]
pub struct Snapshot { pub running: bool, pub port: u16, pub address: String, pub messages: usize, pub history: Vec<Message>, pub logs: String }

#[derive(Deserialize)]
pub struct SettingsInput { pub port: u16, pub mode: String }

pub struct AppState { pub running: Mutex<bool>, pub port: Mutex<u16>, pub history: Mutex<Vec<Message>>, pub logs: Mutex<String>, pub stop: Mutex<bool> }
pub type Shared = Arc<AppState>;

fn data_dir() -> PathBuf { std::env::var_os("APPDATA").map(PathBuf::from).unwrap_or_else(|| PathBuf::from("." )).join("XundaNotify") }
fn log_path() -> PathBuf { data_dir().join("xunda-tauri.log") }
fn write_log(state: &Shared, line: impl AsRef<str>) { let line = format!("{}  {}\n", Local::now().format("%Y-%m-%d %H:%M:%S"), line.as_ref()); if let Ok(mut logs)=state.logs.lock(){ logs.push_str(&line); } let _=fs::create_dir_all(data_dir()); let _=fs::OpenOptions::new().create(true).append(true).open(log_path()).and_then(|mut f| f.write_all(line.as_bytes())); }
fn clear_log() { let _=fs::create_dir_all(data_dir()); let _=fs::write(log_path(), ""); }

fn parse_message(raw: &str) -> (String, String) {
    let decoded = raw.replace('+', " ");
    let mut package = String::new(); let mut sender = String::new(); let mut group = String::new(); let mut content = String::new();
    for pair in decoded.split('&') { let mut it=pair.splitn(2,'='); let k=it.next().unwrap_or("").to_lowercase(); let v=it.next().unwrap_or(""); match k.as_str(){"package"|"pkg"|"from"=>package=v.to_string(),"sender"|"nickname"|"name"|"title"=>sender=v.to_string(),"group"|"group_name"|"chat"=>group=v.to_string(),"content"|"msg"|"message"|"text"|"body"=>content=v.to_string(),_=>{}} }
    if content.is_empty() || content.contains("com.tencent.") { content="新消息".into(); }
    let software = match package.as_str(){"com.tencent.mm"=>"微信", "com.tencent.mobileqq"=>"QQ", "com.tencent.tim"=>"TIM", "com.tencent.wework"=>"企业微信", "com.alibaba.android.rimet"=>"钉钉", "com.ss.android.lark"=>"飞书", "com.whatsapp"=>"WhatsApp", "org.telegram.messenger"=>"Telegram", "com.sina.weibo"=>"微博", "com.android.mms"=>"短信", "com.google.android.gm"=>"Gmail", _=>""};
    let title = if software.is_empty(){ sender.clone() } else if group.is_empty(){ format!("{}-{}", software, sender) } else { format!("{}-{}-{}", software, group, sender) };
    (if title.trim_matches('-').is_empty(){"新消息".into()}else{title}, content)
}

fn notify(app: &AppHandle, title: &str, body: &str) { let _=app.notification().builder().title(title).body(body).show(); }
fn handle_client(mut stream: TcpStream, state: Shared, app: AppHandle) {
    let mut buf=[0u8;16384]; let n=stream.read(&mut buf).unwrap_or(0); let req=String::from_utf8_lossy(&buf[..n]); let raw=req.split("\r\n\r\n").nth(1).unwrap_or_else(|| req.split_whitespace().nth(1).unwrap_or("")); let (title,body)=parse_message(raw.trim_start_matches("/?msg=")); let message=Message{time:Local::now().format("%H:%M:%S").to_string(),title:title.clone(),body:body.clone()}; if let Ok(mut h)=state.history.lock(){h.insert(0,message.clone());h.truncate(500);} write_log(&state, format!("收到消息：标题={}，正文长度={}",title,body.len())); notify(&app,&title,&format!("{}\n接收时间 {}",body,message.time)); let response="HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: 11\r\nConnection: close\r\n\r\n{\"ok\":true}"; let _=stream.write_all(response.as_bytes()); let _=app.emit("message", message);
}

fn start_listener(state: Shared, app: AppHandle, port: u16) { thread::spawn(move || { let listener=match TcpListener::bind(("0.0.0.0",port)){Ok(v)=>v,Err(e)=>{write_log(&state,format!("服务启动失败：{}",e));return;}}; let _=listener.set_nonblocking(true); write_log(&state,format!("WebHook 服务已启动：端口 {}",port)); loop { if *state.stop.lock().unwrap_or_else(|e|e.into_inner()){break;} match listener.accept(){Ok((stream,_))=>handle_client(stream,state.clone(),app.clone()),Err(_)=>thread::sleep(Duration::from_millis(100))} } write_log(&state,"WebHook 服务已停止"); }); }

#[tauri::command]
fn snapshot(state: State<'_, Shared>) -> Snapshot { let port=*state.port.lock().unwrap(); let history=state.history.lock().unwrap().clone(); Snapshot{running:*state.running.lock().unwrap(),port,address:format!("127.0.0.1:{}",port),messages:history.len(),history,logs:state.logs.lock().unwrap().clone()} }
#[tauri::command]
fn toggle_server(state: State<'_, Shared>, app: AppHandle) { let mut running=state.running.lock().unwrap(); if *running { *state.stop.lock().unwrap()=true; *running=false; write_log(&state,"用户停止服务"); } else { *state.stop.lock().unwrap()=false; *running=true; let port=*state.port.lock().unwrap(); start_listener(state.inner().clone(),app,port); } }
#[tauri::command]
fn test_notification(state: State<'_, Shared>, app: AppHandle) { let now=Local::now().format("%H:%M:%S").to_string(); let message=Message{time:now.clone(),title:"讯达-测试通知".into(),body:"新消息：讯达通知中心运行正常".into()}; state.history.lock().unwrap().insert(0,message.clone()); write_log(&state,"发送测试通知"); notify(&app,&message.title,&format!("{}\n接收时间 {}",message.body,now)); }
#[tauri::command]
fn save_settings(input: SettingsInput, state: State<'_, Shared>) -> Result<(), String> { if !(1..=65535).contains(&input.port){return Err("端口范围无效".into())}; *state.port.lock().unwrap()=input.port; write_log(&state,format!("设置已保存：端口={}，通知方式={}",input.port,input.mode)); Ok(()) }

pub fn run() { clear_log(); let state:Shared=Arc::new(AppState{running:Mutex::new(false),port:Mutex::new(8080),history:Mutex::new(Vec::new()),logs:Mutex::new(String::new()),stop:Mutex::new(false)}); tauri::Builder::default().manage(state.clone()).plugin(tauri_plugin_notification::init()).invoke_handler(tauri::generate_handler![snapshot,toggle_server,test_notification,save_settings]).setup(move |app| { let show=MenuItemBuilder::with_id("show","显示窗口").build(app)?; let quit=MenuItemBuilder::with_id("quit","退出程序").build(app)?; let menu=MenuBuilder::new(app).items(&[&show,&quit]).build()?; TrayIconBuilder::new().menu(&menu).show_menu_on_left_click(false).on_tray_icon_event(|tray,event| { if let TrayIconEvent::DoubleClick{..}=event { if let Some(window)=tray.app_handle().get_webview_window("main"){let _=window.show();let _=window.set_focus();} } }).on_menu_event(|app,event| { if event.id().as_ref()=="show" {if let Some(w)=app.get_webview_window("main"){let _=w.show();let _=w.set_focus();}} else if event.id().as_ref()=="quit" {app.exit(0);} }).build(app)?; Ok(()) }).on_window_event(|window,event| { if let WindowEvent::CloseRequested{api,..}=event { api.prevent_close(); let _=window.hide(); } }).build(tauri::generate_context!()).expect("error while running tauri application").run(|_,event| { if let tauri::RunEvent::ExitRequested{..}=event {clear_log();} }); }
