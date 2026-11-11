'use strict';

const ICONS = {
  chat:'<path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z"/>',
  note:'<path d="M5 3h14v18H5zM9 7h6M9 11h6M9 15h4"/>',
  daily:'<path d="M5 5h14v16H5zM8 3v4M16 3v4M5 10h14M9 14h2M14 14h1M9 17h2"/>',
  memory:'<path d="M9 4a3 3 0 0 0-5 3 4 4 0 0 0-1 7 3 3 0 0 0 3 5 3 3 0 0 0 5 1V4a2 2 0 0 0-2-2M15 4a3 3 0 0 1 5 3 4 4 0 0 1 1 7 3 3 0 0 1-3 5 3 3 0 0 1-5 1V4a2 2 0 0 1 2-2M7 8l4 2M17 8l-4 2M7 15l4-2M17 15l-4-2"/>',
  settings:'<path d="m9 3-1 3-3 1-2 3 2 3-1 3 3 2 2-1 3 2 3-2 2 1 3-2-1-3 2-3-2-3-3-1-1-3z"/><circle cx="12" cy="11" r="3"/>',
  search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  inbox:'<path d="M4 4h16v16H4zM4 14h5l2 3h2l2-3h5M8 8h8M8 11h5"/>',
  collect:'<path d="M6 3h12v18l-6-4-6 4z"/>',
  transfer:'<path d="M3 7h15l-4-4M21 17H6l4 4M18 7l-4 4M6 17l4-4"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',
  close:'<path d="m6 6 12 12M6 18 18 6"/>',
  attach:'<path d="m21 11-9 9a6 6 0 0 1-8.5-8.5l10-10a4 4 0 0 1 5.7 5.7l-10 10a2 2 0 0 1-2.8-2.8l9-9"/>',
  send:'<path d="m22 2-7 20-4-9-9-4zM22 2 11 13"/>',
  reply:'<path d="m9 4-6 6 6 6M3 10h10a8 8 0 0 1 8 8"/>',
  copy:'<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
  file:'<path d="M5 3h9l5 5v13H5zM14 3v6h5M8 13h8M8 17h5"/>',
  folder:'<path d="M3 5h6l2 3h10v13H3z"/>',
  check:'<path d="m4 12 5 5L20 6"/>',
  stop:'<rect x="6" y="6" width="12" height="12" rx="2"/>',
  edit:'<path d="m15 4 5 5M4 20l4-1L20 7a3.5 3.5 0 0 0-5-5L3 14l-1 6z"/>',
  download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  trash:'<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M9 10v7M15 10v7"/>',
  refresh:'<path d="M20 7v5h-5M4 17v-5h5M6 7a7 7 0 0 1 12-2l2 7M4 12l2 7a7 7 0 0 0 12-2"/>',
  link:'<path d="m10 13 4-4M8 16l-2 2a4 4 0 0 1-6-6l5-5a4 4 0 0 1 6 0M13 17a4 4 0 0 0 6 0l5-5a4 4 0 0 0-6-6l-2 2" transform="translate(1 -1) scale(.9)"/>',
  arrow:'<path d="M12 4v16m-6-6 6 6 6-6"/>',
  spark:'<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z"/>',
};
const NAV = [['chat','聊天'],['note','笔记'],['daily','日报'],['memory','记忆'],['settings','设置']];
const CHANNELS = [
  {id:'inbox',title:'随手记',description:'先接住，再一起整理',mode:'auto'},
  {id:'chat',title:'聊一聊',description:'提问、讨论、交给我做',mode:'chat'},
  {id:'collect',title:'收藏夹',description:'链接、截图和值得留下的东西',mode:'collect'},
  {id:'transfer',title:'文件传输',description:'存放文件与临时文字',mode:'transfer'},
];
const S={view:'chat',channel:'inbox',channels:CHANNELS,stats:{},settings:{},pending:{},messages:[],messageHash:'',historyLoaded:false,historyEnd:false,attachments:new Map(),drafts:{},draftFiles:{},reply:null,notes:[],note:null,noteTab:'read',category:'',kind:'',query:'',reports:[],report:null,reportRunning:false,memories:[],polling:false,connected:false,activeRequest:0,toastTimer:null};
Object.assign(S,{libraryId:null,library:null,libraries:[],libraryEpoch:0,switching:false,libraryDrafts:{}});
const $=selector=>document.querySelector(selector);
const main=$('#main'), sidebar=$('#sidebar'), dialog=$('#dialog');

function el(tag, attrs={}, ...children){
  const node=document.createElement(tag);
  for(const [k,v] of Object.entries(attrs||{})){
    if(v===undefined||v===null||v===false) continue;
    if(k==='class') node.className=v;
    else if(k==='text') node.textContent=v;
    else if(k==='html') throw new Error('Unsafe HTML');
    else if(k.startsWith('on')&&typeof v==='function')node.addEventListener(k.slice(2).toLowerCase(),v);
    else if(k==='value')node.value=v;
    else if(k==='checked')node.checked=!!v;
    else if(k==='disabled')node.disabled=!!v;
    else node.setAttribute(k,v===true?'':String(v));
  }
  for(const child of children.flat(Infinity)){if(child===null||child===undefined||child===false)continue;node.append(child instanceof Node?child:document.createTextNode(String(child)));}
  return node;
}
function icon(name){const n=document.createElementNS('http://www.w3.org/2000/svg','svg');n.setAttribute('viewBox','0 0 24 24');n.setAttribute('aria-hidden','true');n.innerHTML=ICONS[name]||ICONS.file;return n;}
function btn(label,click,cls='button',ico){return el('button',{type:'button',class:cls,onclick:click},ico?icon(ico):null,label);}
function ib(name,label,click){return el('button',{type:'button',class:'icon-button',title:label,'aria-label':label,onclick:click},icon(name));}
function channelIcon(id){return {inbox:'inbox',chat:'chat',collect:'collect',transfer:'transfer'}[id]||'chat';}
function channelTitle(id){return S.channels.find(c=>c.id===id)?.title||CHANNELS.find(c=>c.id===id)?.title||id;}
function toast(message,error=false){if(!message)return;const n=$('#toast');n.textContent=message;n.className='toast visible'+(error?' error':'');clearTimeout(S.toastTimer);S.toastTimer=setTimeout(()=>n.classList.remove('visible'),error?7000:3400);}
function errorText(e){return e?.name==='LibraryChanged'?'':String(e?.message||e||'操作失败').slice(0,450);}
function libraryChanged(){const error=new Error('资料库已切换');error.name='LibraryChanged';return error;}
function libraryUrl(path,libraryId=S.libraryId){const url=new URL(path,location.origin);if(libraryId)url.searchParams.set('library',libraryId);return url.pathname+url.search+url.hash;}
async function api(path,options={}){
  const libraryId=S.libraryId,epoch=S.libraryEpoch;
  const opts={...options,headers:{...options.headers}};
  if(libraryId)opts.headers['X-Personal-Library']=libraryId;
  if(opts.body&&!(opts.body instanceof FormData)){opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(opts.body);}
  let response;
  try{response=await fetch(path,opts);}catch(error){if(libraryId!==S.libraryId||epoch!==S.libraryEpoch)throw libraryChanged();throw error;}
  let data={};try{data=await response.json();}catch{if(!response.ok)throw new Error(`请求失败（${response.status}）`);}
  if(libraryId!==S.libraryId||epoch!==S.libraryEpoch)throw libraryChanged();
  if(!response.ok){const detail=data.detail||data.error||`请求失败（${response.status}）`;throw new Error(typeof detail==='string'?detail:JSON.stringify(detail));}
  return data;
}
async function action(button,fn){if(button?.disabled)return;if(button)button.disabled=true;try{return await fn();}catch(e){toast(errorText(e),true);}finally{if(button)button.disabled=false;}}
function date(value,options={}){if(!value)return '';const d=new Date(value);if(Number.isNaN(d.getTime()))return String(value);return d.toLocaleString('zh-CN',options);}
function shortDate(value){return date(value,{month:'2-digit',day:'2-digit'});}
function bytes(n){if(!n)return '0 B';if(n<1024)return n+' B';if(n<1048576)return (n/1024).toFixed(1)+' KB';return (n/1048576).toFixed(1)+' MB';}
function safeUrl(value){try{const u=new URL(value,location.origin);return ['http:','https:','mailto:'].includes(u.protocol)?u.href:null;}catch{return null;}}
function externalLink(label,url,cls=''){
  const href=safeUrl(url);if(!href)return el('span',{class:cls},label);
  const parsed=new URL(href);
  if(parsed.origin===location.origin&&['note','report','message'].some(key=>parsed.searchParams.has(key))){
    const libraryId=parsed.searchParams.get('library')||S.libraryId;
    return el('a',{href:libraryUrl(href,libraryId),class:cls,onclick:async e=>{e.preventDefault();if(libraryId!==S.libraryId)await switchLibrary(libraryId,false);if(parsed.searchParams.has('note'))openNote(parsed.searchParams.get('note'));else if(parsed.searchParams.has('message'))jumpToMessage(parsed.searchParams.get('message'));else openReport(parsed.searchParams.get('report'));}},label);
  }
  return el('a',{href,target:'_blank',rel:'noopener noreferrer',class:cls},label);
}

function inline(text){
  const frag=document.createDocumentFragment();
  const regex=/(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^\s)]+\)|https?:\/\/[^\s<>()]+|\*[^*\n]+\*)/g;let last=0,m;
  while((m=regex.exec(text))){frag.append(document.createTextNode(text.slice(last,m.index)));const t=m[0];
    if(t.startsWith('`'))frag.append(el('code',{},t.slice(1,-1)));
    else if(t.startsWith('**'))frag.append(el('strong',{},t.slice(2,-2)));
    else if(t.startsWith('*'))frag.append(el('em',{},t.slice(1,-1)));
    else if(t.startsWith('[')){const z=t.match(/^\[([^\]]+)\]\((.+)\)$/);frag.append(externalLink(z[1],z[2]));}
    else frag.append(externalLink(t,t));last=regex.lastIndex;
  }
  frag.append(document.createTextNode(text.slice(last)));return frag;
}
function markdown(text){
  const out=el('div',{class:'markdown'});const lines=String(text||'').replace(/\r/g,'').split('\n');let i=0;
  while(i<lines.length){let line=lines[i];
    if(!line.trim()){i++;continue;}
    if(line.startsWith('```')){i++;const code=[];while(i<lines.length&&!lines[i].startsWith('```'))code.push(lines[i++]);i++;const raw=code.join('\n');out.append(el('pre',{},el('code',{},raw),btn('复制',()=>copy(raw),'')));continue;}
    const heading=line.match(/^(#{1,4})\s+(.*)/);if(heading){out.append(el('h'+Math.min(heading[1].length+1,4),{},inline(heading[2])));i++;continue;}
    if(/^\s*([-*_])\1\1+\s*$/.test(line)){out.append(el('hr'));i++;continue;}
    if(/^>\s?/.test(line)){const q=[];while(i<lines.length&&/^>\s?/.test(lines[i]))q.push(lines[i++].replace(/^>\s?/,''));out.append(el('blockquote',{},markdown(q.join('\n'))));continue;}
    if(/^\s*([-*+] |\d+\. )/.test(line)){const ordered=/^\s*\d+\./.test(line);const list=el(ordered?'ol':'ul');while(i<lines.length&&/^\s*([-*+] |\d+\. )/.test(lines[i]))list.append(el('li',{},inline(lines[i++].replace(/^\s*([-*+] |\d+\. )/,''))));out.append(list);continue;}
    if(line.includes('|')&&i+1<lines.length&&/^\s*\|?\s*:?-{2,}/.test(lines[i+1])){const cells=s=>s.replace(/^\s*\||\|\s*$/g,'').split('|').map(x=>x.trim());const table=el('table',{},el('thead',{},el('tr',{},cells(line).map(x=>el('th',{},inline(x))))));i+=2;const tbody=el('tbody');while(i<lines.length&&lines[i].includes('|'))tbody.append(el('tr',{},cells(lines[i++]).map(x=>el('td',{},inline(x)))));table.append(tbody);out.append(el('div',{class:'table-scroll'},table));continue;}
    const p=el('p');while(i<lines.length&&lines[i].trim()&&!/^(#{1,4} |```|> |[-*+] |\d+\. )/.test(lines[i])){if(p.childNodes.length)p.append(el('br'));p.append(inline(lines[i++]));}if(!p.childNodes.length){p.append(inline(lines[i++]));}out.append(p);
  }return out;
}
async function copy(value){try{await navigator.clipboard.writeText(value);toast('已复制');}catch{toast('复制失败，请选中文字手动复制',true);}}
function empty(title,description,ico='note',extra){return el('div',{class:'empty'},el('div',{class:'empty-mark'},icon(ico)),el('h2',{},title),el('p',{},description),extra);}
function head(title,description,actions=[]){return el('header',{class:'main-head'},el('div',{class:'head-copy'},el('h1',{},title),description?el('p',{},description):null),el('div',{class:'head-actions'},actions));}
function showDialog(title,body,actions=[]){const content=$('#dialog-content');content.replaceChildren(el('div',{class:'dialog-head'},el('h2',{},title),ib('close','关闭',()=>dialog.close())),el('div',{class:'dialog-body'},body,actions.length?el('div',{class:'dialog-actions'},actions):null));if(!dialog.open)dialog.showModal();}
dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});

function renderNav(){
  $('#navigation').replaceChildren(...NAV.map(([id,label])=>el('button',{type:'button',class:'nav-button'+(S.view===id?' active':''),'aria-label':label,'aria-current':S.view===id?'page':null,onclick:()=>navigate(id)},icon(id),el('span',{},label))));
}
function renderSidebar(){
  const view=S.view;
  if(view==='chat'){
    sidebar.replaceChildren(el('div',{class:'side-head'},el('h2',{},'我的 Agent'),el('p',{class:'subtitle'},'把散落的想法，慢慢放好。')),
      el('button',{class:'side-search',onclick:openSearch},icon('search'),el('span',{},'搜索笔记与聊天'),el('kbd',{},'Ctrl K')),
      el('div',{class:'side-list'},S.channels.map(c=>el('button',{class:'channel'+(c.id===S.channel?' active':''),onclick:()=>selectChannel(c.id),'aria-current':c.id===S.channel?'true':null},el('div',{class:'channel-avatar'},icon(channelIcon(c.id))),el('div',{class:'channel-copy'},el('div',{class:'channel-title'},c.title),el('div',{class:'channel-description'},c.description||CHANNELS.find(v=>v.id===c.id)?.description||'')),S.pending[c.id]?.count?el('span',{class:'count-badge'},S.pending[c.id].count):null))),
      el('div',{class:'side-foot'},el('strong',{},'资料存储在本机'),el('br'),`${S.stats.notes||0} 篇笔记 · ${S.stats.memories||0} 条记忆`));
  }else if(view==='note'){
    const categories=new Map();for(const n of S.notes)categories.set(n.category||'收件箱',(categories.get(n.category||'收件箱')||0)+1);
    sidebar.replaceChildren(el('div',{class:'side-head'},el('h2',{},'笔记'),el('p',{class:'subtitle'},'按主题整理，随时回到原文。')),
      btn('新建笔记',()=>newNote(),'button side-action','plus'),
      el('div',{class:'side-list'},el('div',{class:'section-label'},'分类'),el('button',{class:'category-button'+(!S.category?' active':''),onclick:()=>{S.category='';renderNotes();}},icon('note'),'全部笔记',el('span',{class:'category-count'},S.notes.length)),[...categories].sort((a,b)=>a[0].localeCompare(b[0],'zh-CN')).map(([category,count])=>el('button',{class:'category-button'+(S.category===category?' active':''),onclick:()=>{S.category=category;renderNotes();},title:category},icon('folder'),el('span',{},category),el('span',{class:'category-count'},count)))),
      el('div',{class:'side-foot'},'整理后的笔记可编辑、可导出。',el('br'),'原始消息与附件会保留。'));
  }else if(view==='daily'){
    sidebar.replaceChildren(el('div',{class:'side-head'},el('h2',{},'每日来信'),el('p',{class:'subtitle'},'从你的收藏与问题出发。')),btn(S.reportRunning?'正在整理…':'生成今天的日报',e=>generateReport(e.currentTarget),'button side-action','plus'),el('div',{class:'side-list'},S.reports.length?S.reports.map(r=>el('button',{class:'side-report'+(S.report?.id===r.id?' active':''),onclick:()=>selectReport(r.id)},el('h3',{},r.title),el('span',{},r.day||shortDate(r.created_at)))):el('p',{class:'side-empty'},'第一份日报会出现在这里。')),el('div',{class:'side-foot'},S.settings.daily_enabled?`每天 ${S.settings.daily_time||'09:00'} 自动整理`:'可在设置中开启每日自动整理',el('br'),'需要软件保持运行。'));
  }else if(view==='memory'){
    sidebar.replaceChildren(el('div',{class:'side-head'},el('h2',{},'记忆'),el('p',{class:'subtitle'},'关于你，也由你来决定。')),btn('添加一条记忆',()=>editMemory(),'button side-action','plus'),el('div',{class:'side-list'},el('div',{class:'section-label'},'记忆与上下文'),el('button',{class:'category-button active'},icon('memory'),'长期记忆',el('span',{class:'category-count'},S.memories.length)),btn('查看聊天摘要',()=>contextDialog(),'category-button','chat')),el('div',{class:'side-foot'},'记忆是回答时的参考。',el('br'),'你可以随时修改或删除。'));
  }else{
    sidebar.replaceChildren(el('div',{class:'side-head'},el('h2',{},'设置'),el('p',{class:'subtitle'},'让 Agent 适合你的习惯。')),el('div',{class:'side-list'},['模型与能力','聊天节奏','每日来信','MCP 工具','数据位置'].map((x,i)=>btn(x,()=>$('#settings-'+i)?.scrollIntoView({behavior:'smooth'}),'category-button',i===3?'link':'settings'))),el('div',{class:'side-foot'},'Personal Agent',el('br'),'本地个人工作空间'));
  }
}
async function navigate(view){
  saveDraft();S.activeRequest++;S.view=view;renderNav();renderSidebar();
  try{
    if(view==='chat'){renderChat();await refreshMessages(true);}
    else if(view==='note'){main.replaceChildren(head('笔记',''),el('div',{class:'busy-line'},'正在读取笔记…'));await loadNotes();}
    else if(view==='daily'){main.replaceChildren(head('每日来信',''),el('div',{class:'busy-line'},'正在读取日报…'));await loadReports();}
    else if(view==='memory'){main.replaceChildren(head('长期记忆',''),el('div',{class:'busy-line'},'正在读取记忆…'));await loadMemories();}
    else await renderSettings();
  }catch(e){if(e.name!=='LibraryChanged')main.replaceChildren(head(NAV.find(v=>v[0]===view)?.[1]||'', ''),empty('暂时没有读到内容',errorText(e),'refresh',btn('重试',()=>navigate(view),'button','refresh')));}
}
function saveDraft(){const input=$('#composer-input');if(input)S.drafts[S.channel]=input.value;}
async function selectChannel(id){saveDraft();S.channel=id;S.reply=null;S.messages=[];S.messageHash='';S.historyLoaded=false;S.historyEnd=false;renderSidebar();renderChat();await refreshMessages(true);}
function mobileChannels(){showDialog('选择聊天',el('div',{},S.channels.map(c=>btn(c.title,()=>{dialog.close();selectChannel(c.id);},'category-button',channelIcon(c.id)))));}
function renderChat(){
  const c=S.channels.find(x=>x.id===S.channel)||CHANNELS[0];const transfer=c.id==='transfer';
  const input=el('textarea',{id:'composer-input','aria-label':'消息内容',placeholder:transfer?'放一段文字，或拖入文件…':c.id==='collect'?'把想收藏的链接、截图或文字发过来…':'想法、问题、看到的东西，都可以放在这里…',rows:'3',value:S.drafts[c.id]||''});
  input.addEventListener('input',()=>{S.drafts[S.channel]=input.value;input.style.height='auto';input.style.height=Math.min(180,input.scrollHeight)+'px';});
  input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();sendMessage();}});
  input.addEventListener('paste',e=>{const files=[...(e.clipboardData?.items||[])].filter(x=>x.kind==='file').map(x=>x.getAsFile()).filter(Boolean);if(files.length){e.preventDefault();uploadFiles(files);}});
  const fileInput=el('input',{type:'file',id:'file-input',multiple:true,class:'hidden',onchange:e=>{uploadFiles([...e.target.files]);e.target.value='';}});
  const composer=el('section',{class:'composer',id:'composer','aria-label':'发送消息'},el('div',{class:'composer-top'},el('div',{class:'composer-tools'},ib('attach','添加文件或图片',()=>fileInput.click()),el('span',{class:'composer-note'},transfer?'仅保存，不分析':c.id==='collect'?'保存原文，整理成笔记':'可以连续发送，我会等你说完')),el('div',{id:'batch-status',class:'batch-status'})),el('div',{id:'composer-reply'}),el('div',{id:'pending-attachments',class:'pending-attachments'}),input,el('div',{class:'composer-bottom'},el('span',{class:'composer-hint'},'Enter 发送 · Shift + Enter 换行'),el('div',{class:'composer-buttons'},transfer?null:btn('发完了',e=>flushMessages(e.currentTarget),'button', 'check'),btn('发送',()=>sendMessage(),'button primary','send'))),fileInput);
  for(const event of ['dragenter','dragover'])composer.addEventListener(event,e=>{e.preventDefault();composer.classList.add('dragover');});
  composer.addEventListener('dragleave',e=>{if(!composer.contains(e.relatedTarget))composer.classList.remove('dragover');});composer.addEventListener('drop',e=>{e.preventDefault();composer.classList.remove('dragover');uploadFiles([...(e.dataTransfer?.files||[])]);});
  const mobile=ib('chat','切换聊天',mobileChannels);mobile.classList.add('mobile-switch');mobile.style.display='none';
  main.replaceChildren(head(c.title,c.description||'', [mobile,ib('search','搜索笔记与聊天',openSearch),transfer?null:ib('memory','查看当前上下文',()=>contextDialog(c.id))]),el('div',{class:'messages',id:'messages','aria-label':'聊天记录'}),composer);
  renderMessages(true);renderPendingAttachments();renderReply();updateBatch();input.focus();
}
function renderMessages(forceBottom=false){
  const area=$('#messages');if(!area)return;const wasNearBottom=area.scrollHeight-area.scrollTop-area.clientHeight<150;const oldTop=area.scrollTop;
  if(!S.messages.length){const values={inbox:['先放在这里，慢慢整理','随手发一段想法、一张截图，或一个链接。值得留下的内容，会有自己的位置。'],chat:['从一句话开始','可以问问题，也可以接着以前的收藏聊。我会从你的笔记和记忆里寻找相关内容。'],collect:['给喜欢的东西留个位置','链接、图片、文字、文件都能收藏。告诉我为什么留它，也可以先什么都不说。'],transfer:['你的文件传输助手','文件和临时文字保存在这里。不会交给模型分析，也不会写入个人记忆。']};const v=values[S.channel];area.replaceChildren(empty(v[0],v[1],channelIcon(S.channel),S.channel!=='transfer'?el('p',{class:'small'},'连续发几条后，点「发完了」就可以一起处理。'):null));return;}
  const frag=document.createDocumentFragment();let previousDate='';
  if(!S.historyEnd&&S.messages.length>=100)frag.append(el('div',{style:'text-align:center;margin-bottom:20px'},btn('查看更早的消息',e=>loadOlderMessages(e.currentTarget),'text-button')));
  for(const m of S.messages){const day=date(m.created_at,{year:'numeric',month:'long',day:'numeric'});if(day!==previousDate){frag.append(el('div',{class:'message-date'},day));previousDate=day;}frag.append(messageNode(m));}
  area.replaceChildren(frag);if(wasNearBottom||forceBottom)requestAnimationFrame(()=>area.scrollTop=area.scrollHeight);else area.scrollTop=oldTop;
}
function messageNode(m){
  const isUser=m.role==='user';const author=sourceAuthor(m);const bubble=el('div',{class:'bubble'});const wrap=el('div',{class:'msg-wrap'},el('div',{class:'msg-name'},`${author} · ${date(m.created_at,{hour:'2-digit',minute:'2-digit'})}`),bubble);
  if(m.reply_to){const ref=S.messages.find(x=>x.id===m.reply_to);bubble.append(el('button',{class:'reply-block',onclick:()=>jumpToMessage(m.reply_to)},ref?.content||'查看引用的消息'));}
  if(m.content)bubble.append(markdown(m.content));
  if(m.attachment_ids?.length){const list=el('div',{class:'attachment-list'});bubble.append(list);for(const id of m.attachment_ids)attachNode(id,list);}
  const noteIds=m.meta?.note_ids||m.meta?.notes||[];
  if(Array.isArray(noteIds)&&noteIds.length)wrap.append(el('div',{class:'note-links'},noteIds.map(v=>{const id=typeof v==='object'?v.id:v;return btn(typeof v==='object'?v.title||'查看笔记':'查看整理的笔记',()=>openNote(id),'note-link','note');})));
  if(m.meta?.report_id)wrap.append(el('div',{class:'note-links'},btn('打开日报',()=>openReport(m.meta.report_id),'note-link','daily')));
  if(m.meta?.parsed?.length){
    const parsed=m.meta.parsed;
    const details=el('details',{class:'parse-details'},el('summary',{},`来源读取 · ${parsed.length} 项`));
    for(const p of parsed){const good=['ok','success','ready','parsed'].includes(p.status);details.append(el('div',{class:'parse-source'},el('strong',{},p.title||p.name||p.url||'附件'),el('p',{},`${good?'已读取':'读取状态：'+(p.status||'未知')} · ${({'article':'网页正文','full_text':'完整文字','transcript':'音频转写','subtitles':'字幕','metadata':'仅链接信息','vision':'图片识别','image_description':'图片识别'})[p.scope]||p.scope||''}`),p.error?el('p',{class:'inline-error'},p.error):null,p.url?externalLink('打开来源',p.url):null));}wrap.append(details);
  }
  const actions=el('div',{class:'message-actions'},btn('引用',()=>{S.reply=m;renderReply();$('#composer-input')?.focus();},'', 'reply'),btn('复制',()=>copy(m.content||''),'','copy'));
  if(S.channel!=='transfer')actions.append(btn('存为笔记',()=>saveMessageAsNote(m),'','note'));
  if(m.status==='pending')actions.append(el('span',{class:'message-status'},'已收下，等待一起处理'));
  if(m.status==='processing')actions.append(el('span',{class:'message-status'},'正在整理'));
  if(m.status==='error')actions.append(btn('重试',()=>flushMessages(),'','refresh'));
  wrap.append(actions);
  const node=el('article',{class:'message '+(isUser?'user':'assistant')+(m.status==='error'?' error':''),id:'message-'+m.id,'data-id':m.id},el('div',{class:'msg-avatar'+(!isUser?' agent':'')},isUser?author.slice(0,1):icon('spark')),wrap);return node;
}
async function attachNode(id,parent){
  const libraryId=S.libraryId;
  try{let a=S.attachments.get(id);if(!a){const r=await api('/api/attachments/'+encodeURIComponent(id));a=r.attachment||r;S.attachments.set(id,a);}const href=libraryUrl('/api/files/'+encodeURIComponent(id),libraryId);
    if(a.mime?.startsWith('image/')){const img=el('img',{src:href,alt:a.name||'图片附件',class:'image-attachment',loading:'lazy',onclick:()=>window.open(href,'_blank','noopener')});parent.append(el('a',{href,target:'_blank',rel:'noopener',title:'打开原图'},img));}
    else parent.append(el('a',{href,download:a.name||'',class:'file-card'},icon('file'),el('div',{class:'file-copy'},el('div',{class:'file-name'},a.name||'附件'),el('div',{class:'file-size'},bytes(a.size)))));
  }catch(e){if(e.name!=='LibraryChanged')parent.append(el('span',{class:'small muted'},'附件暂时无法读取'));}
}
function renderReply(){const area=$('#composer-reply');if(!area)return;area.replaceChildren();if(S.reply)area.append(el('div',{class:'composer-reply'},icon('reply'),el('span',{},S.reply.content||'附件消息'),ib('close','取消引用',()=>{S.reply=null;renderReply();})));}
function renderPendingAttachments(){const area=$('#pending-attachments');if(!area)return;area.replaceChildren(...(S.draftFiles[S.channel]||[]).map(a=>el('div',{class:'attachment-chip'},icon('file'),el('span',{},a.name),el('button',{title:'移除附件','aria-label':'移除附件 '+a.name,onclick:()=>{S.draftFiles[S.channel]=S.draftFiles[S.channel].filter(v=>v.id!==a.id);renderPendingAttachments();}},'×'))));}
async function uploadFiles(files){
  if(!files.length)return;const channel=S.channel;const status=$('#batch-status');if(status)status.textContent=`正在上传 ${files.length} 个附件…`;
  try{const form=new FormData();files.forEach(f=>form.append('files',f));const r=await api('/api/upload',{method:'POST',body:form});S.draftFiles[channel]=[...(S.draftFiles[channel]||[]),...(r.attachments||[])];for(const a of r.attachments||[])S.attachments.set(a.id,a);if(S.channel===channel)renderPendingAttachments();toast('附件已添加，发送后保存');}catch(e){toast(errorText(e),true);}finally{updateBatch();}
}
let sending=false;
async function sendMessage(){
  const input=$('#composer-input');if(!input||sending)return;const content=input.value.trim();const channel=S.channel;const files=S.draftFiles[channel]||[];if(!content&&!files.length){input.focus();return;}
  const libraryId=S.libraryId;const reply=S.reply;input.value='';input.style.height='auto';S.drafts[channel]='';S.draftFiles[channel]=[];S.reply=null;renderReply();renderPendingAttachments();sending=true;
  try{const r=await api('/api/messages',{method:'POST',body:{channel,content,reply_to:reply?.id||null,attachment_ids:files.map(x=>x.id)}});if(r.pending)S.pending[channel]=r.pending;if(S.channel===channel&&S.view==='chat')await refreshMessages(true);await refreshState();}
  catch(e){if(libraryId!==S.libraryId||e.name==='LibraryChanged')return;S.drafts[channel]=content;S.draftFiles[channel]=files;if(S.channel===channel&&S.view==='chat'){input.value=content;renderPendingAttachments();S.reply=reply;renderReply();}toast(errorText(e),true);}
  finally{sending=false;input?.focus();}
}
async function flushMessages(button){await action(button,async()=>{const libraryId=S.libraryId;const input=$('#composer-input');if(input?.value.trim()||(S.draftFiles[S.channel]||[]).length)await sendMessage();if(libraryId!==S.libraryId)throw libraryChanged();const r=await api('/api/flush',{method:'POST',body:{channel:S.channel}});if(r.pending)S.pending[S.channel]=r.pending;await refreshMessages();updateBatch();toast('收到，开始一起整理');});}
function updateBatch(){
  const status=$('#batch-status');if(!status)return;const p=S.pending[S.channel]||{};
  if(S.channel==='transfer'){status.replaceChildren();return;}
  if(p.running){status.replaceChildren(el('span',{class:'dot running'}),el('span',{},'正在思考，可以继续补充'),btn('停止',async()=>{try{await api('/api/stop',{method:'POST',body:{channel:S.channel}});toast('已停止');await refreshMessages();}catch(e){toast(errorText(e),true);}},'text-button'));}
  else if(p.count){let secs=p.due_at?Math.max(0,Math.ceil((new Date(p.due_at).getTime()-Date.now())/1000)):null;if(typeof p.due_at==='number')secs=Math.max(0,Math.ceil((p.due_at*1000-Date.now())/1000));status.replaceChildren(el('span',{class:'dot'}),el('span',{},secs!==null&&Number.isFinite(secs)?`已收下 ${p.count} 条 · ${secs} 秒后整理`:`已收下 ${p.count} 条，等你说完`));}
  else status.replaceChildren();
}
async function refreshMessages(force=false){
  const channel=S.channel;const r=await api('/api/messages?channel='+encodeURIComponent(channel));if(S.channel!==channel||S.view!=='chat')return;
  S.pending[channel]=r.pending||{};let messages=r.messages||[];
  if(S.historyLoaded){const ids=new Set(messages.map(m=>m.id));messages=[...S.messages.filter(m=>!ids.has(m.id)),...messages].sort((a,b)=>a.created_at.localeCompare(b.created_at));}
  const hash=JSON.stringify(messages);if(hash!==S.messageHash||force){S.messages=messages;S.messageHash=hash;renderMessages(force);}updateBatch();
}
async function loadOlderMessages(button){await action(button,async()=>{
  if(!S.messages.length)return;const channel=S.channel;const area=$('#messages');const height=area.scrollHeight;const top=area.scrollTop;
  const r=await api('/api/messages?channel='+encodeURIComponent(channel)+'&before='+encodeURIComponent(S.messages[0].id));if(channel!==S.channel)return;
  const ids=new Set(S.messages.map(m=>m.id));S.messages=[...(r.messages||[]).filter(m=>!ids.has(m.id)),...S.messages];S.historyLoaded=true;S.historyEnd=(r.messages||[]).length<100;S.messageHash=JSON.stringify(S.messages);renderMessages();requestAnimationFrame(()=>area.scrollTop=top+(area.scrollHeight-height));
});}
async function refreshState(){const r=await api('/api/state');const old=JSON.stringify([S.stats,S.pending]);S.stats=r.stats||{};S.settings={...S.settings,...r.settings};S.pending=r.pending||S.pending;if(r.library){S.library=r.library;document.title='我的 Personal Agent · '+r.library.title;}if(r.channels?.length)S.channels=r.channels;S.connected=true;$('#connection-dot').className='connection-dot connected';$('#connection-dot').title='已连接本地服务';if(old!==JSON.stringify([S.stats,S.pending])&&S.view==='chat')renderSidebar();return r;}
async function jumpToMessage(id){
  if(!id)return;dialog.close();
  let target=S.messages.find(m=>m.id===id);if(!target){try{const r=await api('/api/messages/'+encodeURIComponent(id));target=r.message||r;}catch{toast('原消息暂时无法读取',true);return;}}const channel=target?.channel;
  if(!channel){toast('原消息暂时未在当前记录中找到',true);return;}
  saveDraft();S.view='chat';S.channel=channel;S.messages=[];S.messageHash='';S.historyLoaded=true;S.historyEnd=false;renderNav();renderSidebar();renderChat();const r=await api('/api/messages?channel='+encodeURIComponent(channel)+'&limit=300');S.messages=r.messages||[];if(!S.messages.some(m=>m.id===id)){const older=await api('/api/messages?channel='+encodeURIComponent(channel)+'&before='+encodeURIComponent(id)+'&limit=20');S.messages=[...(older.messages||[]),target,...S.messages];}S.messageHash=JSON.stringify(S.messages);renderMessages();setTimeout(()=>{const n=document.getElementById('message-'+id);n?.scrollIntoView({behavior:'smooth',block:'center'});n?.classList.add('highlight');setTimeout(()=>n?.classList.remove('highlight'),2400);},80);
}
async function saveMessageAsNote(m){
  newNote({title:(m.content||'附件收藏').slice(0,38).split('\n')[0],body:m.content||'',original:m.content||'',source_ids:[m.id],category:'收件箱',kind:m.role==='user'?'note':'reference'});
}

async function loadNotes(){const r=await api('/api/notes');if(S.view!=='note')return;S.notes=r.notes||[];if(S.note?.id){S.note=S.notes.find(n=>n.id===S.note.id)||S.note;}renderNotes();}
function renderNotes(){
  renderSidebar();const search=el('input',{type:'search',placeholder:'搜索笔记…','aria-label':'搜索笔记',value:S.query});let timer;search.addEventListener('input',()=>{S.query=search.value;clearTimeout(timer);timer=setTimeout(renderNoteList,180);});
  const select=el('select',{'aria-label':'笔记类型'},[['','所有类型'],['note','笔记'],['judgment','我的判断'],['thought','想法'],['question','待探索'],['project','项目'],['idea','灵感'],['reference','参考资料'],['collection','收藏']].map(([v,l])=>el('option',{value:v},l)));select.value=S.kind;select.addEventListener('change',()=>{S.kind=select.value;renderNoteList();});
  main.replaceChildren(head(S.category||'全部笔记','保留原文，也让内容更容易找回来',[ib('refresh','刷新笔记',()=>loadNotes()),ib('plus','新建笔记',()=>newNote())]),el('div',{class:'toolbar',style:'padding:16px 20px 0;margin-bottom:14px'},search,select),el('div',{class:'notes-layout'},el('div',{class:'notes-list',id:'notes-list'}),el('div',{class:'note-detail',id:'note-detail'})));
  renderNoteList();renderNoteDetail();
}
function renderNoteList(){
  const area=$('#notes-list');if(!area)return;const q=S.query.toLowerCase().trim();const notes=S.notes.filter(n=>(!S.category||n.category===S.category)&&(!S.kind||n.kind===S.kind)&&(!q||[n.title,n.body,n.original,n.category,...(n.tags||[])].join(' ').toLowerCase().includes(q)));
  area.replaceChildren(...(notes.length?notes.map(n=>el('button',{class:'note-row'+(S.note?.id===n.id?' active':''),onclick:()=>selectNote(n.id)},el('h3',{},n.title),el('p',{},n.body?.replace(/[#*`>]/g,'').slice(0,160)||n.original?.slice(0,160)||'暂无正文'),el('div',{class:'note-row-meta'},el('span',{},n.category||'收件箱'),el('time',{},shortDate(n.updated_at||n.created_at))))):[el('p',{class:'side-empty'},q||S.category||S.kind?'没有匹配的笔记。':'有价值的内容整理好后，会出现在这里。')]));
}
async function selectNote(id){try{const r=await api('/api/notes/'+encodeURIComponent(id));S.note=r.note||r;S.noteTab='read';renderNoteList();renderNoteDetail();}catch(e){toast(errorText(e),true);}}
async function openNote(id){S.note=null;S.view='note';renderNav();await loadNotes();await selectNote(id);}
function renderNoteDetail(){
  const area=$('#note-detail');if(!area)return;const n=S.note;
  if(!n){area.replaceChildren(empty('每一条，都有来处','选择一篇笔记查看正文、原始内容和相关聊天。','note'));return;}
  if(S.noteTab==='edit'){area.replaceChildren(noteEditor(n));return;}
  const buttons=[ib('edit','编辑笔记',()=>{S.noteTab='edit';renderNoteDetail();}),el('a',{class:'icon-button',href:libraryUrl('/api/notes/'+encodeURIComponent(n.id)+'/export'),download:'',title:'导出 Markdown','aria-label':'导出 Markdown'},icon('download')),ib('trash','归档笔记',()=>archiveNote(n))];
  area.replaceChildren(el('div',{class:'note-detail-head'},el('div',{},el('h2',{},n.title),el('div',{class:'note-detail-meta'},el('span',{},n.category||'收件箱'),el('span',{},'更新于 '+date(n.updated_at,{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'})),...(n.tags||[]).map(t=>el('span',{class:'tag'},t)))),el('div',{class:'head-actions'},buttons)),el('div',{class:'tabs'},btn('整理后的笔记',()=>{S.noteTab='read';renderNoteDetail();},'tab'+(S.noteTab==='read'?' active':'')),btn('原文与来源',()=>{S.noteTab='source';renderNoteDetail();},'tab'+(S.noteTab==='source'?' active':''))));
  if(S.noteTab==='read')area.append(el('div',{class:'note-body'},markdown(n.body||'还没有整理后的正文。')));
  else renderNoteSources(n,area);
}

function sourceAuthor(message,preferSelf=false){const p=message.meta?.provenance||{};if(preferSelf&&p.is_self===true)return '我';return p.sender_name||message.sender_name||message.author||(message.role==='assistant'?'Agent':p.is_self===false?'原作者':'我');}
function sourceTime(value){
  const raw=String(value||'');if(!raw)return '';
  if(/^\d{10,13}$/.test(raw))value=Number(value)*(raw.length<=10?1000:1);
  else if(!/(?:[zZ]|[+-]\d{2}:?\d{2})$/.test(raw))return raw;
  const time=new Date(value);if(!Number.isFinite(time.getTime()))return date(value);
  const offset=-time.getTimezoneOffset(),absolute=Math.abs(offset);const zone=`UTC${offset<0?'-':'+'}${String(Math.floor(absolute/60)).padStart(2,'0')}:${String(absolute%60).padStart(2,'0')}`;
  return date(value,{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'})+' '+zone;
}
function sourceTimestamp(value){return el('time',{title:value||''},sourceTime(value));}
function sourceText(value,limit=1400){
  const text=String(value||'');const body=el('div',{class:'source-raw'},text.length>limit?text.slice(0,limit)+'…':text);
  if(text.length<=limit)return body;
  let expanded=false;const control=btn(`展开全文（${text.length.toLocaleString()} 字）`,()=>{expanded=!expanded;body.textContent=expanded?text:text.slice(0,limit)+'…';control.textContent=expanded?'收起全文':`展开全文（${text.length.toLocaleString()} 字）`;control.setAttribute('aria-expanded',String(expanded));},'text-button source-expand');
  control.setAttribute('aria-expanded','false');return el('div',{class:'source-text'},body,control);
}
function sourceDisclosure(label,render,cls=''){
  const details=el('details',{class:'source-disclosure '+cls},el('summary',{},label));let mounted=false;
  details.addEventListener('toggle',()=>{if(details.open&&!mounted){mounted=true;details.append(render());}});return details;
}
function sourceContent(message,limit=1400){
  const share=message.meta?.share||message.share;
  if(!share)return sourceText(message.content||message.text||'',limit);
  const card=el('div',{class:'source-share'},el('div',{class:'source-share-label'},icon('link'),'分享内容'),externalLink(share.title||'打开分享',share.url,'source-share-title'));
  if(share.description)card.append(sourceText(share.description,500));
  if(share.url)card.append(externalLink(share.url,share.url,'source-share-url'));
  const content=el('div',{class:'source-content'},card);
  if(share.user_text)content.append(el('div',{class:'source-user-text'},el('span',{class:'source-share-label'},'附言'),sourceText(share.user_text,limit)));
  return content;
}
function sourceQuote(value){return el('div',{class:'source-quote'},el('div',{class:'source-author'},value.sender_name||value.author||'引用消息',value.time?sourceTimestamp(value.time):null),sourceContent(value,260));}
function sourceForwarded(items,depth=0){
  const forwarded=el('div',{class:'source-forwarded'},el('h4',{},'转发的聊天记录'));
  function renderItem(item){
    const child=el('div',{class:'forwarded-message'},el('div',{class:'source-author'},el('strong',{},item.sender_name||item.author||'原作者'),sourceTimestamp(item.time||item.created_at)),item.quote?sourceQuote(item.quote):null,sourceContent(item));
    if(item.attachment_ids?.length){const files=el('div',{class:'attachment-list'});child.append(files);for(const id of item.attachment_ids)attachNode(id,files);}
    if(item.forwarded?.length&&depth<8)child.append(sourceForwarded(item.forwarded,depth+1));
    return child;
  }
  items.slice(0,5).forEach(item=>forwarded.append(renderItem(item)));
  if(items.length>5)forwarded.append(sourceDisclosure(`其余 ${items.length-5} 条转发`,()=>el('div',{},items.slice(5).map(renderItem))));
  return forwarded;
}
function sourceMessage(message,focused,byId,referenced=false){
  const provenance=message.meta?.provenance||{};const quote=message.reply_to?byId.get(message.reply_to):null;
  const row=el('article',{class:'source-message'+(focused?' focused':''),'data-source-id':message.id},
    el('div',{class:'source-author'},el('strong',{},sourceAuthor(message,true)),sourceTimestamp(message.created_at),focused?el('span',{class:'tag'},'笔记来源'):referenced?el('span',{class:'tag'},'引用消息'):null),
    quote?sourceQuote({...quote,sender_name:sourceAuthor(quote,true),time:quote.created_at}):message.meta?.quote?sourceQuote(message.meta.quote):null,
    sourceContent(message));
  if(message.attachment_ids?.length){const attachments=el('div',{class:'attachment-list'});row.append(attachments);for(const id of message.attachment_ids)attachNode(id,attachments);}
  const missing=(message.meta?.media_status||[]).filter(item=>item.status==='missing').length;
  if(missing)row.append(el('p',{class:'source-media-missing'},icon('file'),`${missing} 个附件未能读取`));
  if(message.meta?.forwarded?.length)row.append(sourceForwarded(message.meta.forwarded));
  const conversation=[provenance.conversation_kind==='direct'?'私聊':'',provenance.conversation_title||''].filter(Boolean).join(' · ');
  row.append(el('div',{class:'source-message-footer'},el('span',{},conversation),btn('回到这条消息',()=>jumpToMessage(message.id),'text-button','chat')));
  return row;
}
async function renderNoteSources(note,area){
  const libraryId=S.libraryId;const ids=note.source_ids||[];
  if(note.source_url)area.append(el('div',{class:'source-links'},externalLink('打开原始链接',note.source_url,'source-link')));
  const contextArea=el('section',{class:'source-context'},el('h3',{},'原始消息'),el('p',{class:'small muted',style:'margin:12px 0'},ids.length?'正在读取原始消息…':'这篇笔记没有关联聊天消息。'));
  area.append(contextArea);
  if(note.original)area.append(ids.length?sourceDisclosure('存档原文',()=>sourceText(note.original),'source-snapshot'):el('section',{class:'source-snapshot'},el('h3',{},'存档原文'),sourceText(note.original)));
  if(!ids.length)return;
  const results=await Promise.allSettled(ids.map(id=>api('/api/messages/'+encodeURIComponent(id)+'/context')));
  if(S.libraryId!==libraryId||S.note?.id!==note.id||S.noteTab!=='source'||!area.isConnected)return;
  const messages=new Map();const focus=new Set(ids);let unavailable=0;
  for(const result of results){if(result.status==='fulfilled'){for(const m of result.value.messages||[])messages.set(m.id,m);if(result.value.focus_id)focus.add(result.value.focus_id);}else unavailable++;}
  contextArea.replaceChildren(el('h3',{},'原始消息'));
  const ordered=[...messages.values()].sort((a,b)=>String(a.created_at).localeCompare(String(b.created_at)));
  const included=new Set(focus);
  for(const id of focus){const traversed=new Set([id]);let current=messages.get(id);while(current?.reply_to&&!traversed.has(current.reply_to)){traversed.add(current.reply_to);included.add(current.reply_to);current=messages.get(current.reply_to);}}
  for(const m of ordered.filter(m=>focus.has(m.id)))contextArea.append(sourceMessage(m,true,messages));
  const references=ordered.filter(m=>included.has(m.id)&&!focus.has(m.id));
  if(references.length)contextArea.append(el('section',{class:'source-references'},el('h4',{},'引用的消息'),references.map(m=>sourceMessage(m,false,messages,true))));
  const nearby=ordered.filter(m=>!included.has(m.id));
  if(nearby.length)contextArea.append(sourceDisclosure(`附近对话（${nearby.length} 条）`,()=>el('div',{class:'source-nearby'},nearby.map(m=>sourceMessage(m,false,messages))),'source-nearby-disclosure'));
  if(unavailable)contextArea.append(el('p',{class:'inline-error'},`${unavailable} 处来源暂时无法读取，存档原文仍保留在下方。`));
  if(!ordered.length&&!unavailable)contextArea.append(el('p',{class:'small muted'},'没有找到关联消息。'));
}
function kindSelect(value='note'){const s=el('select',{},[['note','笔记'],['judgment','我的判断'],['thought','想法'],['question','待探索'],['project','项目'],['idea','灵感'],['reference','参考资料'],['collection','收藏']].map(([v,l])=>el('option',{value:v},l)));if(![...s.options].some(o=>o.value===value))s.append(el('option',{value},value));s.value=value;return s;}
function field(label,input,hint){const id=input.id||'field-'+Math.random().toString(36).slice(2);input.id=id;return el('div',{class:'editor-field'},el('label',{for:id},label),input,hint?el('p',{class:'field-hint'},hint):null);}
function noteEditor(note={},onSaved){
  const title=el('input',{value:note.title||'',placeholder:'给这篇笔记起个名字',required:true});const category=el('input',{value:note.category||'收件箱',placeholder:'例如 AI / 使用经验'});const kind=kindSelect(note.kind);const tags=el('input',{value:(note.tags||[]).join('，'),placeholder:'用逗号分隔'});const body=el('textarea',{rows:'14',value:note.body||'',placeholder:'支持 Markdown'});
  const save=btn('保存笔记',e=>action(e.currentTarget,async()=>{if(!title.value.trim()){title.focus();throw new Error('请填写笔记标题');}const payload={title:title.value.trim(),body:body.value,category:category.value.trim()||'收件箱',kind:kind.value,tags:tags.value.split(/[,，]/).map(t=>t.trim()).filter(Boolean)};if(!note.id)Object.assign(payload,{source_ids:note.source_ids||[],source_url:note.source_url||'',original:note.original||body.value});const r=await api('/api/notes'+(note.id?'/'+encodeURIComponent(note.id):''),{method:note.id?'PUT':'POST',body:payload});S.note=r.note||r;S.noteTab='read';toast('笔记已保存');if(onSaved)onSaved();else await loadNotes();}),'button primary','check');
  return el('div',{class:'note-editor'},el('h2',{style:'margin-bottom:22px'},note.id?'编辑笔记':'新建笔记'),field('标题',title),el('div',{class:'editor-row'},field('分类',category),field('类型',kind)),field('标签',tags),field('正文',body),el('div',{class:'editor-actions'},btn('取消',()=>{if(onSaved)dialog.close();else{S.noteTab='read';renderNoteDetail();}},'button'),save));
}
function newNote(values={}){showDialog('留下一篇笔记',noteEditor(values,async()=>{dialog.close();S.view='note';renderNav();await loadNotes();}));}
function archiveNote(note){showDialog('归档这篇笔记？',el('p',{class:'section-intro'},`「${note.title}」将从笔记列表中移除，原始聊天和附件会保留。`),[btn('取消',()=>dialog.close()),btn('归档笔记',e=>action(e.currentTarget,async()=>{await api('/api/notes/'+encodeURIComponent(note.id),{method:'DELETE'});S.note=null;dialog.close();await loadNotes();toast('笔记已归档');}),'button danger','trash')]);}

async function loadReports(){const r=await api('/api/reports');if(S.view!=='daily')return;S.reports=r.reports||[];renderSidebar();if(S.report)await selectReport(S.report.id);else if(S.reports.length)await selectReport(S.reports[0].id);else main.replaceChildren(head('每日来信','你的问题、收藏与下一步'),empty('一份更懂你的日报','回顾最近留下的内容，找出值得继续读、继续想的线索。','daily',btn('生成今天的日报',e=>generateReport(e.currentTarget),'button primary','spark')));}
async function openReport(id){S.view='daily';renderNav();await loadReports();await selectReport(id);}
async function selectReport(id){try{const r=await api('/api/reports/'+encodeURIComponent(id));S.report=r.report||r;renderSidebar();const report=S.report;main.replaceChildren(head('每日来信',report.day||'',[btn('复制全文',()=>copy(report.body),'button','copy'),ib('refresh','生成新的日报',e=>generateReport(e.currentTarget))]),el('div',{class:'scroll-page'},el('article',{class:'report'},el('h1',{class:'report-title'},report.title),el('div',{class:'report-byline'},(report.day||shortDate(report.created_at))+' · 来自你的个人资料库'),markdown(report.body),report.source_ids?.length?el('div',{},el('h3',{style:'margin-top:28px'},'回到来源'),el('div',{class:'source-links'},report.source_ids.map((id,i)=>btn('来源 '+(i+1),()=>openNote(id),'source-link','note')))):null)));}catch(e){toast(errorText(e),true);}}
async function generateReport(button){await action(button,async()=>{await api('/api/reports/generate',{method:'POST'});S.reportRunning=true;renderSidebar();toast('正在整理日报，完成后会显示在这里');});}

async function loadMemories(){
  const r=await api('/api/memories');if(S.view!=='memory')return;
  S.memories=r.memories||[];renderSidebar();
  const items=S.memories.map(m=>{
    const meta=el('div',{class:'memory-meta'},
      el('span',{class:'tag'},({preference:'偏好',fact:'背景',judgment:'判断',goal:'目标',observation:'观察'})[m.kind]||m.kind||'记忆'),
      el('time',{},shortDate(m.updated_at||m.created_at)),
      ...(m.source_ids||[]).slice(0,3).map(id=>btn('来源',()=>jumpToMessage(id),'text-button')));
    return el('article',{class:'memory-item'},
      el('div',{class:'memory-item-main'},el('p',{class:'memory-content'},m.content),meta),
      el('div',{class:'memory-item-actions'},ib('edit','编辑记忆',()=>editMemory(m)),ib('trash','删除记忆',()=>deleteMemory(m))));
  });
  const content=S.memories.length?el('div',{class:'memory-list'},items):empty('慢慢认识你','可以直接添加一条偏好，或在聊天里说「记住这件事」。','memory');
  main.replaceChildren(
    head('长期记忆','让之后的回答，接得上你以前说过的话',[btn('添加记忆',()=>editMemory(),'button','plus')]),
    el('div',{class:'scroll-page'},el('div',{class:'page-inner'},
      el('p',{class:'section-intro'},'这里保留你的偏好、背景与想法。每条记忆都可以修正；具体的观点和资料原文仍保存在笔记里。'),content)));
}
function editMemory(memory={}){
  const content=el('textarea',{rows:'5',value:memory.content||'',placeholder:'例如：我希望回答简洁，先说结论，再给必要的依据。'});const kind=el('select',{},[['preference','偏好'],['fact','背景'],['judgment','判断'],['goal','目标'],['observation','观察']].map(([v,l])=>el('option',{value:v},l)));kind.value=memory.kind||'preference';
  showDialog(memory.id?'编辑记忆':'添加记忆',el('div',{},field('内容',content),field('类型',kind)),[btn('取消',()=>dialog.close()),btn('保存',e=>action(e.currentTarget,async()=>{if(!content.value.trim()){content.focus();throw new Error('请填写记忆内容');}await api('/api/memories'+(memory.id?'/'+encodeURIComponent(memory.id):''),{method:memory.id?'PUT':'POST',body:{content:content.value.trim(),kind:kind.value,source_ids:memory.source_ids||[]}});dialog.close();toast('记忆已保存');if(S.view==='memory')await loadMemories();}),'button primary','check')]);
}
function deleteMemory(memory){showDialog('删除这条记忆？',el('p',{class:'original'},memory.content),[btn('取消',()=>dialog.close()),btn('删除记忆',e=>action(e.currentTarget,async()=>{await api('/api/memories/'+encodeURIComponent(memory.id),{method:'DELETE'});dialog.close();await loadMemories();toast('已删除这条记忆');}),'button danger','trash')]);}

async function renderSettings(){
  main.replaceChildren(head('设置',''),el('div',{class:'busy-line'},'正在读取配置…'));const r=await api('/api/settings');if(S.view!=='settings')return;const settings=r.settings||{};S.settings={...S.settings,...settings};const creds=r.credentials||{};
  const librarySelect=el('select',{'aria-label':'当前资料库'},S.libraries.map(l=>el('option',{value:l.id},l.title)));librarySelect.value=S.libraryId;librarySelect.addEventListener('change',()=>switchLibrary(librarySelect.value));
  const model=el('input',{value:settings.model||'',placeholder:'模型名称'});const base=el('input',{type:'url',value:settings.base_url||'',placeholder:'https://api.example.com/v1'});const apiKey=el('input',{type:'password',autocomplete:'new-password',placeholder:creds.api_key?'已配置；留空保持不变':'输入 API Key'});
  const buffer=el('input',{type:'number',min:'0',max:'600',step:'1',value:settings.buffer_seconds??60});const dailyTime=el('input',{type:'time',value:settings.daily_time||'09:00'});const dailyTimezone=el('input',{value:settings.daily_timezone||'America/Los_Angeles',placeholder:'例如 Asia/Shanghai'});const dailyEnabled=el('input',{type:'checkbox',checked:settings.daily_enabled});const prompt=el('textarea',{rows:'4',value:settings.system_prompt||'',placeholder:'例如：回答时直接一些，有需要再展开。'});
  const keyInputs={};for(const [key,label] of [['vision_key','图片识别 API Key'],['groq_key','语音 / 视频转写 API Key'],['brave_key','Brave 搜索 API Key（可选）'],['tikhub_key','平台内容解析 API Key']])keyInputs[key]={label,input:el('input',{type:'password',autocomplete:'new-password',placeholder:creds[key]?'已配置；留空保持不变':'尚未配置'})};
  const extra=el('details',{class:'settings-details'},el('summary',{},'图片、转写与搜索的独立密钥'),el('div',{},Object.values(keyInputs).map(v=>field(v.label,v.input))));
  const mcpEditor=el('textarea',{class:'mcp-editor',spellcheck:'false','aria-label':'MCP 服务器 JSON 配置',value:'{\n  "mcpServers": {}\n}'});const serverList=el('div',{class:'server-list',id:'server-list'});const mcpError=el('p',{class:'inline-error',id:'mcp-error'});
  const sections=[
    el('section',{class:'settings-section library-setting'},el('h2',{},'资料库'),el('p',{},'聊天、笔记、记忆与附件分别保存，模型连接设置共用。'),field('当前资料库',librarySelect)),
    el('section',{class:'settings-section',id:'settings-0'},el('h2',{},'模型与能力'),el('p',{},'使用兼容 Chat Completions 的模型服务。密钥只保存在本机。'),field('模型名称',model),field('API 地址',base),field('API Key',apiKey),btn('测试已保存的模型',e=>action(e.currentTarget,async()=>{const test=await api('/api/settings/test',{method:'POST'});toast(test.ok?'模型连接正常':test.error||test.message||'模型连接失败',!test.ok);}),'button','refresh'),extra,field('你希望它怎样与你相处',prompt)),
    el('section',{class:'settings-section',id:'settings-1'},el('h2',{},'聊天节奏'),el('p',{},'连续发送时，等你停下来再一起处理。也可以随时点「发完了」。'),field('等待时间（秒）',buffer,'新消息会重新开始计时；处理期间也可以继续补充。')),
    el('section',{class:'settings-section',id:'settings-2'},el('h2',{},'每日来信'),el('p',{},'围绕你最近的收藏、问题和记忆整理日报，软件运行时会按时执行。'),el('label',{class:'check-field'},dailyEnabled,'每天自动生成日报'),el('div',{class:'editor-row',style:'margin-top:18px'},field('每天的时间',dailyTime),field('时区',dailyTimezone,'例如 America/Los_Angeles 或 Asia/Shanghai。'))),
    el('section',{class:'settings-section',id:'settings-3'},el('h2',{},'MCP 工具'),el('p',{},'接入你选定的工具服务，支持 stdio 与 Streamable HTTP。保存后可测试连接。'),mcpEditor,mcpError,el('div',{class:'mcp-actions'},btn('保存 MCP 配置',e=>action(e.currentTarget,async()=>{mcpError.textContent='';let config;try{config=JSON.parse(mcpEditor.value);}catch{mcpError.textContent='JSON 格式不正确，请检查引号、逗号和括号。';return;}if(!config.mcpServers||typeof config.mcpServers!=='object')throw new Error('配置需要包含 mcpServers 对象');await api('/api/mcp',{method:'PUT',body:{config}});toast('MCP 配置已保存');await loadMcp();}),'button','check'),btn('测试连接',e=>action(e.currentTarget,async()=>{mcpError.textContent='';serverList.replaceChildren(el('p',{class:'small muted'},'正在连接工具服务…'));const result=await api('/api/mcp/test',{method:'POST'});renderServers(result.servers||[]);toast(`已发现 ${result.tools_count||0} 个工具`);}),'button','refresh')),serverList),
    el('section',{class:'settings-section',id:'settings-4'},el('h2',{},'数据位置'),el('p',{},'聊天、附件、笔记、配置和运行数据存放在这里。软件目录只保留程序文件。'),el('div',{class:'data-path'},r.data_dir||settings.data_dir||''),btn('复制数据目录',()=>copy(r.data_dir||settings.data_dir||''),'text-button')),
  ];
  const status=el('span');const save=btn('保存设置',e=>action(e.currentTarget,async()=>{status.textContent='';const seconds=Number(buffer.value);if(!Number.isFinite(seconds)||seconds<0||seconds>600)throw new Error('等待时间需在 0–600 秒之间');const payload={model:model.value.trim(),base_url:base.value.trim(),buffer_seconds:seconds,daily_time:dailyTime.value,daily_timezone:dailyTimezone.value.trim(),daily_enabled:dailyEnabled.checked,system_prompt:prompt.value};if(apiKey.value.trim())payload.api_key=apiKey.value.trim();for(const [key,{input}] of Object.entries(keyInputs))if(input.value.trim())payload[key]=input.value.trim();await api('/api/settings',{method:'PUT',body:payload});apiKey.value='';Object.values(keyInputs).forEach(v=>v.input.value='');status.textContent='已保存';toast('设置已保存');await refreshState();}),'button primary','check');
  main.replaceChildren(head('设置','模型、聊天节奏与连接的工具'),el('div',{class:'scroll-page'},el('div',{class:'page-inner settings'},sections,el('div',{class:'settings-footer'},save,status))));renderSidebar();
  async function loadMcp(){try{const m=await api('/api/mcp');mcpEditor.value=JSON.stringify(m.config||{mcpServers:{}},null,2);renderServers(m.servers||[]);}catch(e){mcpError.textContent=errorText(e);}}
  function renderServers(servers){serverList.replaceChildren(...(servers.length?servers.map(s=>el('div',{class:'server-row'},icon('link'),el('strong',{},s.name),el('span',{class:'status'},`${s.status||'未连接'} · ${Array.isArray(s.tools)?s.tools.length:s.tools||0} 个工具`),s.error?el('div',{class:'server-error'},s.error):null)):[el('p',{class:'small muted'},'还没有连接 MCP 服务。')]));}
  await loadMcp();
}

async function contextDialog(channel=S.channel){
  showDialog('当前上下文',el('div',{class:'busy-line'},'正在读取…'));
  try{const r=await api('/api/context?channel='+encodeURIComponent(channel));const summary=typeof r.summary==='string'?r.summary:r.summary?.content;showDialog(channelTitle(channel)+' · 上下文',el('div',{},el('p',{class:'section-intro'},`${r.message_count||0} 条原始消息 · ${r.memory_count||0} 条长期记忆。压缩只整理供模型阅读的摘要，原始聊天会保留。`),el('h3',{},'聊天摘要'),summary?el('div',{class:'original'},summary):el('p',{class:'section-intro',style:'margin-top:14px'},'当前还不需要摘要。对话变长后会自动整理。')),[btn('整理当前上下文',e=>action(e.currentTarget,async()=>{await api('/api/context/compact',{method:'POST',body:{channel}});toast('上下文已整理');await contextDialog(channel);}),'button','refresh'),btn('关闭',()=>dialog.close(),'button primary')]);}catch(e){showDialog('当前上下文',el('p',{class:'inline-error'},errorText(e)));}
}
function openSearch(){
  const input=el('input',{class:'dialog-search',type:'search',placeholder:'找一个主题、一句话或一篇收藏…','aria-label':'搜索内容'});const results=el('div',{},el('p',{class:'small muted'},'搜索笔记与聊天，文件传输里的内容不参与检索。'));let timer,sequence=0;
  input.addEventListener('input',()=>{clearTimeout(timer);const q=input.value.trim();const seq=++sequence;if(!q){results.replaceChildren();return;}timer=setTimeout(async()=>{results.replaceChildren(el('div',{class:'busy-line'},'正在查找…'));try{const r=await api('/api/search?q='+encodeURIComponent(q));if(seq!==sequence)return;const notes=r.notes||[],messages=r.messages||[];results.replaceChildren(...notes.map(n=>el('button',{class:'search-result',onclick:()=>{dialog.close();openNote(n.id);}},el('div',{class:'search-kind'},'笔记 · '+(n.category||'收件箱')),el('strong',{},n.title),el('p',{},n.body||n.original||''))),...messages.map(m=>el('button',{class:'search-result',onclick:()=>jumpToMessage(m.id)},el('div',{class:'search-kind'},'聊天 · '+channelTitle(m.channel)),el('strong',{},m.content?.slice(0,100)||'附件消息'),el('p',{},date(m.created_at)))));if(!notes.length&&!messages.length)results.append(el('p',{class:'small muted'},'没有找到相关记录，换个关键词试试。'));}catch(e){results.replaceChildren(el('p',{class:'inline-error'},errorText(e)));}},280);});
  showDialog('搜索',el('div',{},input,results));setTimeout(()=>input.focus(),30);
}
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();openSearch();}});

let pollCount=0;
async function poll(){
  if(S.polling||document.hidden||S.switching||!S.libraryId)return;S.polling=true;
  try{if(S.view==='chat')await refreshMessages();if(++pollCount%4===0)await refreshState();if(S.reportRunning||S.view==='daily'){const r=await api('/api/reports/status');if(S.reportRunning&&!r.running){S.reportRunning=false;if(r.error)toast(r.error,true);else{toast('新的日报已整理好');if(S.view==='daily'){S.report=null;await loadReports();}}}else S.reportRunning=!!r.running;}}
  catch(e){if(e.name!=='LibraryChanged'){S.connected=false;$('#connection-dot').className='connection-dot error';$('#connection-dot').title='本地服务暂时未连接';}}
  finally{S.polling=false;}
}
function rememberLibrary(id){try{sessionStorage.setItem('personal-agent-library',id);}catch{}}
async function switchLibrary(id,render=true){
  if(id===S.libraryId||S.switching)return;
  const oldId=S.libraryId,view=S.view;saveDraft();S.libraryDrafts[oldId]={drafts:S.drafts,draftFiles:S.draftFiles};
  S.switching=true;S.libraryEpoch++;dialog.close();main.replaceChildren(head('资料库',''),el('div',{class:'busy-line'},'正在打开资料库…'));
  try{
    const result=await api('/api/libraries/select',{method:'POST',body:{id}});
    S.libraryId=result.selected_id;S.library=result.library;rememberLibrary(S.libraryId);
    const drafts=S.libraryDrafts[id]||{drafts:{},draftFiles:{}};
    Object.assign(S,{channel:'inbox',channels:CHANNELS,stats:{},settings:{},pending:{},messages:[],messageHash:'',historyLoaded:false,historyEnd:false,attachments:new Map(),drafts:drafts.drafts,draftFiles:drafts.draftFiles,reply:null,notes:[],note:null,noteTab:'read',category:'',kind:'',query:'',reports:[],report:null,reportRunning:false,memories:[]});
    const url=new URL(location.href);url.searchParams.set('library',id);for(const key of ['note','report','message','channel'])url.searchParams.delete(key);history.replaceState(null,'',url);
    await refreshState();if(render)await navigate(view);toast('已打开'+result.library.title);
  }catch(e){toast(errorText(e),true);if(S.libraryId===oldId&&render)await navigate(view);}
  finally{S.switching=false;}
}
async function boot(){
  renderNav();renderSidebar();renderChat();
  try{
    const params=new URLSearchParams(location.search);let remembered;try{remembered=sessionStorage.getItem('personal-agent-library');}catch{}
    const available=await api('/api/libraries');S.libraries=available.libraries||[];
    const requested=params.get('library')||remembered||available.selected_id;
    S.libraryId=S.libraries.some(l=>l.id===requested)?requested:available.selected_id;rememberLibrary(S.libraryId);
    await refreshState();renderSidebar();
    if(params.get('note'))await openNote(params.get('note'));else if(params.get('report'))await openReport(params.get('report'));else if(params.get('message'))await jumpToMessage(params.get('message'));else if(NAV.some(([view])=>view===params.get('view')))await navigate(params.get('view'));else{renderChat();await refreshMessages(true);}
  }catch(e){toast('暂时无法连接本地服务，请确认程序正在运行。',true);$('#connection-dot').className='connection-dot error';}
  setInterval(poll,1500);setInterval(updateBatch,1000);
}
boot();
