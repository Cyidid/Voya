const API = '/api';
let curSys = 'goal_based';
let chatMsgs = [];
let busy = false;
let _abortCtrl = null; // 取消重复请求
let loadStart = 0;
let loadTimer = null;

document.addEventListener('DOMContentLoaded', () => {
  checkHealth(); // 自带退避调度，无需 setInterval
  applyLang(); // apply saved language preference
  syncSysCards(); // highlight currently active system card
  updateDestHint(); // 初始化目的地提示

  // 出发日期默认今天
  const _dateEl = document.getElementById('startDateInput');
  if (_dateEl) _dateEl.value = _todayStr();

  // 目的地选择器：初始渲染城市列表
  _renderDestGrid('');
  // 初始化出行类型锁定（默认独旅→锁定1人）
  handleGroupChange();

  document.querySelectorAll('#scTabs .sc-tab').forEach(t => {
    t.addEventListener('click', () => {
      document.querySelectorAll('#scTabs .sc-tab').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      curSys = t.dataset.agent;
      syncNav(); syncSysCards(); updateDestHint();
    });
  });

  document.querySelectorAll('.nav-pill').forEach(t => {
    t.addEventListener('click', () => {
      document.querySelectorAll('.nav-pill').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      curSys = t.dataset.agent;
      syncSc(); syncSysCards();
    });
  });

  // ── Interest tag persistence (Issue 13) ──────────────────────
  const INTEREST_KEY = 'yy_interests';

  function saveInterests() {
    const active = [...document.querySelectorAll('.itag.on')].map(t => t.dataset.i);
    localStorage.setItem(INTEREST_KEY, JSON.stringify(active));
  }

  // Restore persisted interests (overrides HTML defaults)
  const savedInterests = localStorage.getItem(INTEREST_KEY);
  if (savedInterests !== null) {
    try {
      const arr = JSON.parse(savedInterests);
      document.querySelectorAll('.itag').forEach(t => {
        t.classList.toggle('on', arr.includes(t.dataset.i));
      });
    } catch (e) { /* ignore malformed data */ }
  }

  document.querySelectorAll('.itag').forEach(t => {
    t.addEventListener('click', () => { t.classList.toggle('on'); saveInterests(); });
  });

  // 用户画像 & 历史行程初始化
  _histRender();
  _renderMyTrips();

  // ── Event delegation: city picker buttons ────────────────────
  // 代替 inline onmousedown="pickDestCity(...)" / pickOriginCity(...)
  document.getElementById('destPickerGrid')?.addEventListener('mousedown', function(e) {
    const btn = e.target.closest('.cp-city');
    if (btn && btn.dataset.cityDest) pickDestCity(btn.dataset.cityDest);
  });
  document.getElementById('originPickerGrid')?.addEventListener('mousedown', function(e) {
    const btn = e.target.closest('.cp-city');
    if (btn && btn.dataset.cityOrigin) pickOriginCity(btn.dataset.cityOrigin);
  });
});

function handleGroupChange() {
  const g = document.getElementById('groupInput').value;
  const np = document.getElementById('numPeopleInput');
  const pf = document.getElementById('numPeoplePf');
  const couple = g === '情侣' || g === '夫妻';
  const solo   = g === '单人';
  const group_min2 = g === '朋友' || g === '家庭' || g === '同事';
  const locked = couple || solo;

  // 必须先解锁，否则 disabled select 在部分浏览器里写值不生效
  np.disabled = false;

  const targetVal = couple ? '2' : solo ? '1' : null;
  if (targetVal !== null) {
    np.value = targetVal;
    Array.from(np.options).forEach(o => { o.selected = o.value === targetVal; });
  } else if (group_min2 && parseInt(np.value) < 2) {
    np.value = '2';
    Array.from(np.options).forEach(o => { o.selected = o.value === '2'; });
  }

  np.disabled = locked;
  if (pf) pf.style.opacity = locked ? '.62' : '';
}

function syncNav() {
  document.querySelectorAll('.nav-pill').forEach(t =>
    t.classList.toggle('active', t.dataset.agent === curSys));
}
function syncSc() {
  document.querySelectorAll('#scTabs .sc-tab').forEach(t =>
    t.classList.toggle('active', t.dataset.agent === curSys));
}
function syncSysCards() {
  const map = { rule_based: '.sys-card.rule', supervised: '.sys-card.ml', goal_based: '.sys-card.ai' };
  document.querySelectorAll('.sys-card').forEach(c => c.classList.remove('cur'));
  document.querySelector(map[curSys])?.classList.add('cur');
}
function switchSys(s) {
  curSys = s; syncNav(); syncSc(); syncSysCards();
  const t = I18N[_lang];
  const names = { rule_based: t.nav_rule, supervised: t.nav_ml, goal_based: t.nav_goal };

  toast((_lang === 'zh' ? '已切换：' : 'Switched: ') + names[s], 'ok');
}

// 健康检查：使用轻量 /ping 接口，失败时指数退避（30→60→120→180s）
let _healthFailCount = 0;
let _healthTimer = null;

async function checkHealth() {
  try {
    const r = await fetch(`${API}/health/ping`, { signal: AbortSignal.timeout(4000) });
    const ok = r.ok;
    document.getElementById('statusDot').className = 'status-dot ' + (ok ? 'on' : 'off');
    document.getElementById('statusText').textContent = ok ? I18N[_lang].status_ok : I18N[_lang].status_err;
    _healthFailCount = ok ? 0 : _healthFailCount + 1;
  } catch {
    document.getElementById('statusDot').className = 'status-dot off';
    document.getElementById('statusText').textContent = I18N[_lang].status_err;
    _healthFailCount++;
  }
  // 退避调度：失败次数越多等待越久，上限 180s
  if (_healthTimer) clearTimeout(_healthTimer);
  const delay = _healthFailCount === 0 ? 30000 : Math.min(30000 * Math.pow(2, _healthFailCount), 180000);
  _healthTimer = setTimeout(checkHealth, delay);
}

// ── 出发地城市选择器 ────────────────────────────────────
const _ALL_ORIGINS = [
  '上海','北京','广州','深圳','成都','杭州','武汉','重庆',
  '西安','南京','天津','苏州','厦门','长沙','青岛','大连',
  '济南','哈尔滨','昆明','郑州','香港','台北','澳门',
];

function _renderOriginGrid(filter) {
  const cur = document.getElementById('originInput').value.trim();
  const cityMap = I18N[_lang]?.city_map || {};
  const list = filter
    ? _ALL_ORIGINS.filter(c => c.includes(filter) || (cityMap[c] || '').toLowerCase().includes(filter.toLowerCase()))
    : _ALL_ORIGINS;
  document.getElementById('originPickerGrid').innerHTML = list.map(c => {
    const display = _lang === 'en' ? (cityMap[c] || c) : c;
    return `<button class="cp-city ${c === cur ? 'cp-selected' : ''}" data-city-origin="${c}">${display}</button>`;
  }).join('');
}

function openOriginPicker() {
  const el = document.getElementById('originInput');
  el.removeAttribute('readonly');
  _renderOriginGrid('');
  document.getElementById('originPicker').classList.add('open');
  // 互斥：关闭目的地选择器
  const dp = document.getElementById('destInput');
  dp.setAttribute('readonly', '');
  document.getElementById('destPicker').classList.remove('open');
}

const filterOriginPicker = _debounce(function(val) {
  _renderOriginGrid(val.trim());
}, 150);

function pickOriginCity(city) {
  const el = document.getElementById('originInput');
  const cityMap = I18N[_lang]?.city_map || {};
  el.value = _lang === 'en' ? (cityMap[city] || city) : city;
  el.dataset.zh = city;  // 始终保存中文名供 API 使用
  el.setAttribute('readonly', '');
  document.getElementById('originPicker').classList.remove('open');
}

// ── 目的地城市选择器 ────────────────────────────────────
// 全部目的地城市（按地理区域排列：国内 → 近邻亚洲 → 中东 → 大洋洲 → 欧洲 → 美洲）
const _ALL_DESTS = [
  // 国内
  '广州',
  // 近邻亚洲
  '东京','大阪','京都','首尔','新加坡','曼谷','普吉岛','巴厘岛','马尔代夫',
  // 中东
  '迪拜','伊斯坦布尔','开罗',
  // 大洋洲
  '悉尼',
  // 欧洲
  '巴黎','伦敦','罗马','巴塞罗那','阿姆斯特丹','维也纳','布拉格','哥本哈根','苏黎世','里斯本',
  // 美洲
  '纽约',
];

function _renderDestGrid(filter) {
  const cur = document.getElementById('destInput').value.trim();
  const cityMap = I18N[_lang]?.city_map || {};
  const list = filter
    ? _ALL_DESTS.filter(c => c.includes(filter) || (cityMap[c] || '').toLowerCase().includes(filter.toLowerCase()))
    : _ALL_DESTS;
  document.getElementById('destPickerGrid').innerHTML = list.map(c => {
    const display = _lang === 'en' ? (cityMap[c] || c) : c;
    return `<button class="cp-city ${c === cur ? 'cp-selected' : ''}" data-city-dest="${c}">${display}</button>`;
  }).join('');
}

function openDestPicker() {
  const el = document.getElementById('destInput');
  el.removeAttribute('readonly');   // 允许输入以便过滤
  // 不调用 el.select()，避免浏览器滚动页面
  _renderDestGrid('');              // 每次打开都重置为全量城市列表
  document.getElementById('destPicker').classList.add('open');
  // 互斥：关闭出发地选择器
  const op = document.getElementById('originInput');
  op.setAttribute('readonly', '');
  document.getElementById('originPicker').classList.remove('open');
}

// 防抖函数
function _debounce(fn, ms) {
  let t = null;
  return function(...args) {
    clearTimeout(t);
    t = setTimeout(() => fn.apply(this, args), ms);
  };
}

const filterDestPicker = _debounce(function(val) {
  _renderDestGrid(val.trim());
}, 150);

// 国内目的地集合（自驾可达）
const _DOMESTIC_DESTS = new Set([
  // 出发城市（一线/二线）
  '上海','北京','广州','深圳','成都','杭州','武汉','重庆',
  '西安','南京','天津','苏州','厦门','长沙','青岛','大连',
  '济南','哈尔滨','昆明','郑州','香港','台北','澳门',
  // 热门国内目的地
  '三亚','桂林','张家界','丽江','大理','西藏','拉萨','敦煌',
  '黄山','九寨沟','稻城亚丁','乌镇','周庄','西湖','故宫',
  '峨眉山','泰山','华山','庐山','张掖','喀什','吐鲁番',
  '银川','呼和浩特','贵阳','南宁','福州','合肥','石家庄',
  '太原','兰州','西宁','乌鲁木齐','海口','三明','延安',
  '湛江','珠海','汕头','温州','宁波','南昌','长春','沈阳',
  '保定','唐山','包头','洛阳','开封','徐州','扬州','镇江',
  '无锡','常州','绍兴','嘉兴','湖州','漳州','泉州','莆田',
]);

function _isInternational(city) {
  if (!city) return false;
  // 如果城市在国内目的地集合中，则不是国际
  if (_DOMESTIC_DESTS.has(city)) return false;
  // 如果包含常见国内地名关键字，也不算国际
  const domesticKw = ['省','市','区','县','山','岛','湖','江','河','古镇'];
  if (domesticKw.some(k => city.includes(k))) return false;
  return true;
}

function _autoSwitchTransport(city) {
  if (!_isInternational(city)) return;
  const sel = document.getElementById('travelModeInput');
  if (!sel) return;
  const cur = sel.value;
  // 自驾不能出境，自动切换为飞机
  if (cur === '自驾' || cur === 'Self-drive') {
    sel.value = '飞机';
    // 若英文模式 option value 是英文
    const hasPlane = Array.from(sel.options).some(o => o.selected);
    if (!hasPlane) {
      const planeOpt = Array.from(sel.options).find(o => o.value === '飞机' || o.value === 'Flight');
      if (planeOpt) planeOpt.selected = true;
    }
    toast(_lang === 'en' ? '✈ International destination — switched to Flight' : '✈ 跨境目的地，已自动切换为飞机', 'ok');
  }
}

function pickDestCity(city) {
  const el = document.getElementById('destInput');
  // 切换动画
  const prev = el.value.trim();
  if (prev && prev !== city) {
    el.classList.remove('city-switching');
    void el.offsetWidth;
    el.classList.add('city-switching');
    setTimeout(() => el.classList.remove('city-switching'), 320);
  }
  const cityMap = I18N[_lang]?.city_map || {};
  el.value = _lang === 'en' ? (cityMap[city] || city) : city;
  el.dataset.zh = city;  // 始终保存中文名供 API 使用
  el.setAttribute('readonly', '');  // 恢复只读，防止系统键盘弹出
  document.getElementById('destPicker').classList.remove('open');
  // 同步热门按钮高亮（用当前显示文本匹配）
  document.querySelectorAll('.hot-btn').forEach(b =>
    b.classList.toggle('hot-selected', (b.dataset.city || b.textContent.trim()) === city));
  // 国际目的地自动切换交通方式
  _autoSwitchTransport(city);
}

// 点击选择器外部时关闭
document.addEventListener('click', function(e) {
  // 目的地选择器
  if (!e.target.closest('#destPicker') && e.target.id !== 'destInput') {
    const el = document.getElementById('destInput');
    el.setAttribute('readonly', '');
    document.getElementById('destPicker').classList.remove('open');
  }
  // 出发地选择器
  if (!e.target.closest('#originPicker') && e.target.id !== 'originInput') {
    const el = document.getElementById('originInput');
    el.setAttribute('readonly', '');
    document.getElementById('originPicker').classList.remove('open');
  }
}, true);

function quickDest(city) {
  pickDestCity(city);
  // 平滑滚入目的地区域
  document.getElementById('destInput').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
function swapCities() {
  const o = document.getElementById('originInput');
  const d = document.getElementById('destInput');
  // 交换显示值
  const tmpVal = o.value; o.value = d.value; d.value = tmpVal;
  // 交换中文名（data-zh），保持 API 城市名正确
  const tmpZh  = o.dataset.zh || tmpVal;
  o.dataset.zh = d.dataset.zh || d.value;
  d.dataset.zh = tmpZh;
  // 同步热门按钮高亮（按中文名匹配）
  document.querySelectorAll('.hot-btn').forEach(b =>
    b.classList.toggle('hot-selected', b.dataset.city === d.dataset.zh));
  // 交换后重新检测目的地是否为国际（用中文名）
  _autoSwitchTransport(d.dataset.zh || d.value);
}

function toggleMoreDests(btn) {
  const extra = document.getElementById('extraDestCards');
  if (!extra) return;
  const showing = extra.style.display !== 'none';
  extra.style.display = showing ? 'none' : 'contents';
  const t = I18N[_lang];
  btn.textContent = showing ? (t.sec_more_open || '查看全部 ›') : (t.sec_more_close || '收起 ↑');
}

function quickPlan(city, budget, interests, group, days) {
  pickDestCity(city);  // 统一走 pickDestCity，自动处理 data-zh 和英文显示名
  document.getElementById('budgetInput').value = budget;
  document.getElementById('groupInput').value = group;
  document.getElementById('daysInput').value = days;
  handleGroupChange();
  document.querySelectorAll('.itag').forEach(t =>
    t.classList.toggle('on', interests.includes(t.dataset.i)));
  doSearch();
}

function _todayStr() {
  return new Date().toISOString().slice(0, 10);
}
function _getStartDate() {
  const v = document.getElementById('startDateInput')?.value;
  return v || _todayStr();
}

async function doSearch() {
  const destEl  = document.getElementById('destInput');
  const dest    = destEl.dataset.zh || destEl.value.trim();
  if (!dest) { toast('请输入目的地', 'err'); return; }
  if (busy) return;

  const originEl = document.getElementById('originInput');
  const origin   = originEl.dataset.zh || originEl.value.trim();
  const days       = parseInt(document.getElementById('daysInput').value);
  const group      = document.getElementById('groupInput').value;
  const couple     = group === '情侣' || group === '夫妻';
  const solo       = group === '单人';
  const numPeople  = couple ? 2 : solo ? 1 : parseInt(document.getElementById('numPeopleInput').value);
  const budget     = document.getElementById('budgetInput').value;
  const travelMode = document.getElementById('travelModeInput').value;
  const special    = document.getElementById('specialInput').value;
  const interests  = [...document.querySelectorAll('.itag.on')].map(t => t.dataset.i);
  const startDate  = _getStartDate();

  const prefix = origin ? `从${origin}乘${travelMode}出发，` : `乘${travelMode}，`;
  const label = `${prefix}我想去${dest}玩${days}天，共${numPeople}人${group}出行，` +
    `喜欢${interests.join('、') || '观光'}，预算${budget}档${special !== '无' ? '，' + special : ''}，出发日期${startDate}。`;

  await callAPI({
    city: dest, origin, days, num_people: numPeople, budget,
    group, travel_mode: travelMode, special, interests,
    start_date: startDate, agent_type: curSys,
  }, label);
}

async function doChat() {
  const inp = document.getElementById('botInput');
  const txt = inp.value.trim();
  if (!txt || busy) return;
  inp.value = '';

  // 解析并回填表单
  parseAndFill(txt);

  // 短暂延迟让用户看到回填效果，再读取表单值发起搜索
  await new Promise(r => setTimeout(r, 320));

  // 读取表单当前值（已被回填）
  const destEl2   = document.getElementById('destInput');
  const dest      = destEl2.dataset.zh || destEl2.value.trim();
  if (!dest) { toast('未识别目的地，请手动填写后点击「开始规划」', 'err'); return; }

  const originEl2 = document.getElementById('originInput');
  const origin    = originEl2.dataset.zh || originEl2.value.trim();
  const days       = parseInt(document.getElementById('daysInput').value) || 3;
  const group      = document.getElementById('groupInput').value;
  const couple     = group === '情侣' || group === '夫妻';
  const solo       = group === '单人';
  const numPeople  = couple ? 2 : solo ? 1 : (parseInt(document.getElementById('numPeopleInput').value) || 1);
  const budget     = document.getElementById('budgetInput').value;
  const travelMode = document.getElementById('travelModeInput').value;
  const special    = document.getElementById('specialInput').value;
  const interests  = [...document.querySelectorAll('.itag.on')].map(t => t.dataset.i);

  await callAPI({
    city: dest, origin, days, num_people: numPeople,
    budget, group, travel_mode: travelMode, special,
    interests: interests.length ? interests : ['文化', '美食'],
    start_date: _getStartDate(), agent_type: curSys,
  }, txt);
}

function dest_fallback(txt) {
  const cities = [
    '巴黎','东京','纽约','伦敦','罗马','悉尼','迪拜','首尔','曼谷','巴塞罗那',
    '普吉岛','新加坡','阿姆斯特丹','维也纳','布拉格','巴厘岛',
    '大阪','京都','马尔代夫','开罗','伊斯坦布尔','里斯本','哥本哈根','苏黎世','广州',
  ];
  return cities.find(c => txt.includes(c)) || '';
}

// 根据当前模式更新目的地提示文字
function updateDestHint() {
  const hint = document.querySelector('.city-field:last-child .city-hint');
  const destInput = document.getElementById('destInput');
  if (curSys === 'rule_based') {
    destInput.placeholder = '巴黎、东京、纽约...';
    if (hint) hint.textContent = '支持 25 个固定城市';
  } else {
    destInput.placeholder = '巴黎、迪拜、首尔...';
    if (hint) hint.textContent = '点击选择或直接输入城市';
  }
}

// 带动画地回填一个字段
function fillField(el, value) {
  if (!el || value === undefined || value === null || value === '') return;
  el.value = value;
  el.classList.remove('field-filled');
  void el.offsetWidth; // reflow
  el.classList.add('field-filled');
  setTimeout(() => el.classList.remove('field-filled'), 700);
}

// 专用：回填城市输入框（自动处理英文显示名 + data-zh）
function fillCityField(el, zhCity) {
  if (!el || !zhCity) return;
  const cityMap = I18N[_lang]?.city_map || {};
  el.value = _lang === 'en' ? (cityMap[zhCity] || zhCity) : zhCity;
  el.dataset.zh = zhCity;
  el.classList.remove('field-filled');
  void el.offsetWidth;
  el.classList.add('field-filled');
  setTimeout(() => el.classList.remove('field-filled'), 700);
}

// 解析自然语言并回填表单（不触发搜索）
function parseAndFill(txt) {
  // 出发地解析：支持"从X出发/飞"和"X飞Y"/"X直飞Y"两种格式
  let origin = null;
  let city   = null;

  const fromM = txt.match(/(?:从|由|自)\s*(.{2,8}?)(?:出发|飞|乘|前往|到)/);
  if (fromM) {
    origin = fromM[1].trim();
  } else {
    // "上海飞北京" / "上海直飞北京" 格式：左侧为出发地，右侧为目的地
    const flyM = txt.match(/(.{2,4}?)(?:直飞|飞往|飞)(.{2,6})/);
    if (flyM) {
      origin = flyM[1].trim();
      city   = flyM[2].replace(/[，。！？\s玩旅游逛游旅行]/g, '') || null;
    }
  }

  if (!city) {
    const destM = txt.match(/(?:去|到|前往)(.{2,12}?)(?:玩|旅游|逛|游|旅行|\d|，|,|$)/);
    city = destM ? destM[1].replace(/[，。！？\s]/g, '') : null;
  }
  if (!city) city = dest_fallback(txt) || null;

  const daysM = txt.match(/(\d+)\s*天/);
  const days = daysM ? Math.min(parseInt(daysM[1]), 14) : null;

  const _CN_NUMS = {'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10};
  const numM = txt.match(/(\d+)\s*(?:人|位|个人)/);
  // 先匹配"共/一共 X 人"，再匹配普通"X 人"
  const numTotal = txt.match(/(?:共|一共|总共|合计)\s*([一二两三四五六七八九十\d]+)\s*[个]?\s*人/);
  const numCn = txt.match(/([一二两三四五六七八九十]+)\s*[个]?\s*人/);
  let numParsed = numTotal ? (/\d/.test(numTotal[1]) ? parseInt(numTotal[1]) : _CN_NUMS[numTotal[1]] || null)
    : numM ? parseInt(numM[1])
    : numCn ? (_CN_NUMS[numCn[1]] || null)
    : null;

  // 没写总人数但提到孩子 → 从"X个X岁的孩子"推断孩子数，+1（用户本人）
  if (!numParsed && /孩|娃|儿童|小朋友|宝宝|亲子|带.*岁/.test(txt)) {
    const childMatches = txt.match(/([一二两\d]+)\s*个\s*[岁龄]/g);
    if (childMatches) {
      let childCount = 0;
      childMatches.forEach(m => {
        const n = m.match(/([一二两\d]+)/);
        if (n) {
          const digit = n[1];
          childCount += /\d/.test(digit) ? parseInt(digit) : (_CN_NUMS[digit] || 1);
        }
      });
      numParsed = childCount + 1; // 至少 1 个大人
    }
  }

  // 预算：长词优先，负面保护词放最前；"较高/稍高"归高档，"一般/不高"归中档
  const bMap = [
    ['不高','中'], ['不低','中'], ['一般','中'], ['普通','中'],
    ['充裕','高'], ['宽裕','高'], ['豪华','高'], ['奢华','高'], ['奢靡','高'],
    ['很高','高'], ['挺高','高'], ['较高','高'], ['稍高','高'],
    ['高档','高'], ['高消费','高'], ['贵','高'], ['豪','高'], ['奢','高'],
    ['节省','低'], ['省钱','低'], ['经济','低'], ['便宜','低'], ['穷','低'], ['很低','低'],
    ['低','低'], ['高','高'],   // 兜底短词放最后
  ];
  const budget = bMap.find(([k]) => txt.includes(k))?.[1] || null;

  const iKws = ['文化','美食','购物','自然','历史','艺术','夜生活','户外运动'];
  const interests = iKws.filter(k => txt.includes(k));
  // "动漫"归到文化；"徒步/爬山/潜水"归到户外运动
  if (!interests.includes('文化') && /动漫|二次元|漫画|cosplay/.test(txt)) interests.push('文化');
  if (!interests.includes('户外运动') && /徒步|爬山|潜水|骑行|浮潜|冲浪/.test(txt)) interests.push('户外运动');
  if (!interests.includes('自然') && /温泉|热带雨林|海岛|海滩/.test(txt)) interests.push('自然');

  // 出行类型：扩充口语化表达
  const gMap = {
    夫妻:'夫妻', 情侣:'情侣', 老婆:'夫妻', 老公:'夫妻', 男朋友:'情侣', 女朋友:'情侣',
    朋友:'朋友', 同学:'朋友', 闺蜜:'朋友', 兄弟:'朋友', 伙伴:'朋友',
    家庭:'家庭', 家人:'家庭', 全家:'家庭', 孩子:'家庭', 小孩:'家庭',
    儿子:'家庭', 女儿:'家庭', 亲子:'家庭', 儿童:'家庭', 宝宝:'家庭', 娃:'家庭',
    独自:'单人', 一个人:'单人', 单人:'单人', 一人:'单人', 独行:'单人', 自己:'单人',
  };
  // 未识别出行类型时默认独旅
  const group = Object.entries(gMap).find(([k]) => txt.includes(k))?.[1] || '单人';
  const couple = group === '情侣' || group === '夫妻';

  // 特殊需求自动识别
  const specialKw = {
    有儿童: /小孩|孩子|儿童|宝宝|娃|幼儿|婴儿|儿子|女儿|亲子/,
    有老人: /老人|父母|爸妈|爷爷|奶奶|外公|外婆|长辈|老年/,
    轮椅友好: /轮椅|无障碍|残疾|行动不便/,
  };
  const special = Object.entries(specialKw).find(([, re]) => re.test(txt))?.[0] || null;

  const modeMap = { 飞机:'飞机', 航班:'飞机', 高铁:'高铁', 火车:'火车', 动车:'高铁', 自驾:'自驾', 开车:'自驾', 游轮:'游轮', 邮轮:'游轮' };
  const travelMode = Object.entries(modeMap).find(([k]) => txt.includes(k))?.[1] || null;

  // ── 出发日期解析 ──────────────────────────────────────────────────────────
  // 辅助：把 YYYY-M-D 对齐为 YYYY-MM-DD
  function _fmt(y, m, d) {
    return `${y}-${String(m).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
  }
  // 辅助：下一个指定月日（若今年已过则用明年）
  function _nextMD(month, day) {
    const now = new Date();
    const y = now.getFullYear();
    const candidate = new Date(y, month - 1, day);
    return candidate >= now ? _fmt(y, month, day) : _fmt(y + 1, month, day);
  }

  let parsedDate = null;

  // 1) 节假日关键词（优先匹配）
  const HOLIDAYS = [
    [/五一|劳动节/,                () => _nextMD(5, 1)],
    [/国庆|十一(?!月)/,            () => _nextMD(10, 1)],
    [/元旦/,                       () => _nextMD(1, 1)],
    [/清明/,                       () => _nextMD(4, 4)],   // 近似 4/4
    [/端午/,                       () => _nextMD(6, 10)],  // 近似
    [/中秋/,                       () => _nextMD(9, 13)],  // 近似
    [/春节|过年|大年初一/,         () => {
      // 用固定近似：2026年春节为1/28
      const y = new Date().getFullYear();
      const cnny = { 2025:'2025-01-29', 2026:'2026-02-17', 2027:'2027-02-06' };
      return cnny[y] || _nextMD(1, 29);
    }],
    [/暑假/,                       () => _nextMD(7, 10)],
    [/寒假/,                       () => _nextMD(1, 20)],
  ];
  for (const [re, fn] of HOLIDAYS) {
    if (re.test(txt)) { parsedDate = fn(); break; }
  }

  // 2) 具体日期："5月1日" / "5月1号" / "5/1" / "2026年5月1日"
  if (!parsedDate) {
    const fullM = txt.match(/(\d{4})[年\-\/](\d{1,2})[月\-\/](\d{1,2})[日号]?/);
    if (fullM) parsedDate = _fmt(parseInt(fullM[1]), parseInt(fullM[2]), parseInt(fullM[3]));
  }
  if (!parsedDate) {
    const mdM = txt.match(/(\d{1,2})[月\/](\d{1,2})[日号]?/);
    if (mdM) parsedDate = _nextMD(parseInt(mdM[1]), parseInt(mdM[2]));
  }

  // 3) 月份引用："五月" / "3月" / "十月" 等（只有月，无具体日）
  const CN_MON = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,'十一':11,'十二':12};
  if (!parsedDate) {
    // 阿拉伯数字月份："3月" / "12月"（后面没有接数字日期，避免与「3月5日」重复匹配）
    const monArab = txt.match(/(?<![\/\d])(\d{1,2})月(?!\d)/);
    if (monArab) parsedDate = _nextMD(parseInt(monArab[1]), 1);
  }
  if (!parsedDate) {
    // 中文月份："五月" / "三月"
    const monCN = txt.match(/([一二三四五六七八九十]+月)/);
    if (monCN) {
      const key = monCN[1].replace('月','');
      if (CN_MON[key]) parsedDate = _nextMD(CN_MON[key], 1);
    }
  }

  // 4) 相对日期
  if (!parsedDate) {
    const now = new Date();
    const rel = [
      [/明天|明日/,       1],
      [/后天/,            2],
      [/大后天/,          3],
      [/本周末|这周末/,   (6 - now.getDay() + 6) % 7 || 7],  // 下一个周六
      [/下周末|下个周末/, 7 + (6 - now.getDay() + 6) % 7],
      [/下周/,            7],
      [/下下周/,          14],
      [/下个月/,          30],
    ];
    for (const [re, offset] of rel) {
      if (re.test(txt)) {
        const d = new Date(now); d.setDate(d.getDate() + offset);
        parsedDate = _fmt(d.getFullYear(), d.getMonth() + 1, d.getDate());
        break;
      }
    }
  }

  // 回填各字段
  const filled = [];
  if (origin !== null) { fillCityField(document.getElementById('originInput'), origin); filled.push('出发地'); }
  if (city)            { fillCityField(document.getElementById('destInput'), city);   filled.push('目的地'); }
  if (days !== null)   { fillField(document.getElementById('daysInput'), String(days)); filled.push('天数'); }
  if (parsedDate) {
    const dateEl = document.getElementById('startDateInput');
    if (dateEl) { dateEl.value = parsedDate; filled.push('出发日期'); }
  }

  // 先回填人数（在 handleGroupChange 之前，否则会被覆盖为 2）
  if (!couple && numParsed) {
    fillField(document.getElementById('numPeopleInput'), String(Math.min(numParsed, 10)));
    filled.push('人数');
  }

  // 再设置出行类型，handleGroupChange 会根据已有人数做约束（如<2则提升至2）
  if (group)           { fillField(document.getElementById('groupInput'), group); filled.push('出行类型'); handleGroupChange(); }
  if (budget)          { fillField(document.getElementById('budgetInput'), budget); filled.push('预算'); }
  if (travelMode)      { fillField(document.getElementById('travelModeInput'), travelMode); filled.push('出行方式'); }
  if (special)         { fillField(document.getElementById('specialInput'), special); filled.push('特殊需求'); }
  if (interests.length) {
    document.querySelectorAll('.itag').forEach(t => t.classList.toggle('on', interests.includes(t.dataset.i)));
    filled.push('偏好');
  }

  // 智能识别国际目的地，自动切换交通方式
  if (city && !travelMode) _autoSwitchTransport(city);

  // 展示解析提示
  if (filled.length) {
    document.getElementById('parseBannerText').textContent =
      `已识别：${filled.join(' · ')}，可直接修改后开始规划`;
    document.getElementById('parseBanner').classList.add('on');
    // 滚动到卡片顶部
    document.querySelector('.search-card').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  return { city, origin, days, budget, group, travelMode, interests, numM, couple, parsedDate };
}

// 从后端结构化错误中提取用户友好信息
function _extractErrMsg(data) {
  if (data && typeof data.detail === 'object' && data.detail.user_message)
    return data.detail.user_message;
  if (data && typeof data.detail === 'string') return data.detail;
  return '请求失败，请稍后重试';
}

// ── 统一入口：自动选择流式 or 普通请求 ─────────────────────────
// 取消当前请求
function abortCurrent() {
  if (_abortCtrl) { _abortCtrl.abort(); _abortCtrl = null; }
}

// 用户重复点击时：取消旧请求 + 重新开始
function _abortAndRestart() {
  abortCurrent();
  // 清理 loading 状态，让下一次请求能正常启动
  setLoad(false);
  busy = false;
  toast('已取消上次请求，重新开始', 'ok');
}

async function callAPI(params, userText) {
  // 所有 agent 类型均走流式接口（非 goal_based 时后端秒返一次 done 事件）
  return callAPIStream(params, userText);
}

// ── 流式智能自动滚动 ─────────────────────────────────────────────
// 用户手动上划时暂停，回到底部时恢复
let _scrollPaused = false;
(function _initStreamScroll() {
  // 等待 DOM 就绪后绑定
  document.addEventListener('DOMContentLoaded', () => _bindScrollPause());
  // 如果 DOM 已就绪则立即绑定
  if (document.readyState !== 'loading') _bindScrollPause();
  function _bindScrollPause() {
    const body = document.getElementById('itinBody');
    if (!body) { setTimeout(_bindScrollPause, 500); return; }
    body.addEventListener('scroll', () => {
      const distFromBottom = body.scrollHeight - body.scrollTop - body.clientHeight;
      // 距底部 > 80px：用户主动上划，暂停自动滚动
      // 距底部 ≤ 80px：已回到底部，恢复自动滚动
      _scrollPaused = distFromBottom > 80;
    }, { passive: true });
  }
})();

function _streamAutoScroll() {
  if (_scrollPaused) return;
  const body = document.getElementById('itinBody');
  if (body) body.scrollTop = body.scrollHeight;
}

// ── SSE 流式请求 ─────────────────────────────────────────────────
async function callAPIStream(params, userText) {
  busy = true;
  loadStart = Date.now();
  setLoad(true, params.agent_type);
  addMsg('u', userText);

  let fullText = '';
  let _rafPending = false; // rAF 渲染锁
  let streamStarted = false;   // 第一个 chunk 到达标志

  const contentEl = document.getElementById('itinContent');

  try {
    _abortCtrl = new AbortController();
    const resp = await fetch(`${API}/generate/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
      signal: _abortCtrl.signal,
    });
    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}));
      throw new Error(_extractErrMsg(errData));
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '', toolCharBuf = '';

    // 渲染节流：使用 requestAnimationFrame 代替固定 120ms 间隔
    // rAF 在每次屏幕刷新时渲染（60fps=每16ms），输出更顺滑

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buf += decoder.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop(); // 保留不完整行

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        let evt;
        try { evt = JSON.parse(line.slice(6)); } catch { continue; }

        if (evt.error) throw new Error(evt.error);

        if (evt.tool_start) {
          // 工具开始并行查询：在侧边栏规划过程卡的内嵌日志区显示进度
          const contentEl = document.getElementById('toolLogContent');
          if (contentEl) {
            contentEl.textContent = '';
            toolCharBuf = '';
          }
        }

        if (evt.tool_char) {
          toolCharBuf += evt.tool_char;
          const contentEl = document.getElementById('toolLogContent');
          if (contentEl) {
            contentEl.textContent = toolCharBuf;
            contentEl.scrollTop = contentEl.scrollHeight;
          }
        }

        if (evt.chunk) {
          if (!streamStarted) {
            // 第一个 chunk 到达：立即展示结果区，隐藏 loading 动画
            streamStarted = true;
            setLoad(false);
            document.getElementById('welcomeSec').classList.add('gone');
            document.getElementById('resultSec').classList.add('on');
            document.getElementById('itinBody')?.classList.add('streaming');
            // 先用已知参数渲染标题 / 侧边栏骨架
            _renderResultHeader(params);
            renderSide({}, params);
            window.scrollTo({ top: document.querySelector('.main').offsetTop - 16, behavior: 'smooth' });
          }
          fullText += evt.chunk;
          // rAF 节流渲染：每帧渲染一次，避免每个 token 都操作 DOM
          if (!_rafPending) {
            _rafPending = true;
            requestAnimationFrame(() => {
              _renderMarkdown(contentEl, fullText.trimEnd());
              _streamAutoScroll();
              _rafPending = false;
            });
          }
        }

        if (evt.done) {
          // 非流式系统（rule_based/supervised）把行程放在 evt.itinerary 而非 chunks
          if (!fullText && evt.itinerary) fullText = evt.itinerary;
          // 最终完整渲染（关闭流式模式，恢复 max-height 滚动）
          document.getElementById('itinBody')?.classList.remove('streaming');
          _renderMarkdown(contentEl, fullText);
          // 用真实元数据更新侧边栏和 chips
          const syntheticData = {
            itinerary: fullText,
            processing_time: evt.processing_time,
            tool_rounds: evt.tool_rounds || 0,
            agent_steps: evt.agent_steps || [],
            cache_hit: evt.cache_hit || false,
            ...(evt.result_meta || {}),
          };
          if (!streamStarted) {
            // 非 goal_based 的秒返路径：也走这里
            streamStarted = true;
            setLoad(false);
            document.getElementById('welcomeSec').classList.add('gone');
            document.getElementById('resultSec').classList.add('on');
            _renderResultHeader(params);
            window.scrollTo({ top: document.querySelector('.main').offsetTop - 16, behavior: 'smooth' });
          }
          _updateResultChips(params, syntheticData);
          renderSide(syntheticData, params);
          addMsg('a', `行程已生成：${params.city} ${params.days} 天 · ${params.group}`);
          if (syntheticData.coverage_gap && syntheticData.city_used) {
            toast(_L(`「${params.city}」暂不在经典规划覆盖范围内，已为您展示「${syntheticData.city_used}」的行程作为参考。`,
                     `"${params.city}" is not in Classic Planner's coverage. Showing "${syntheticData.city_used}" instead.`), 'warn');
          } else {
            toast('行程生成成功', 'ok');
          }
          // 保存到历史记录
          _histSave({ city: params.city, group: params.group, budget: params.budget,
            interests: params.interests, days: params.days, num_people: params.num_people,
            travel_mode: params.travel_mode });
          break;
        }
      }
    }
  } catch (e) {
    if (e.name === 'AbortError') {
      // 用户主动取消，不报错
      addMsg('a', '已取消请求');
    } else if (streamStarted) {
      toast(`生成中断：${e.message}`, 'err');
    } else {
      setLoad(false);
      toast(e.message, 'err');
    }
    addMsg('a', `生成失败：${e.message}`);
  } finally {
    _abortCtrl = null;
    setLoad(false);
    busy = false;
  }
}

function _renderMarkdown(el, text) {
  const t = (text || '').trimEnd();
  try { el.innerHTML = marked.parse(t); }
  catch { el.innerHTML = t.replace(/\n/g,'<br>'); }
}

function _renderResultHeader(params) {
  const route = params.origin ? `${params.origin} → ${params.city}` : params.city;
  document.getElementById('resultTitle').textContent = `${route} · ${params.days} 天`;
  document.getElementById('itinHeadTitle').textContent = `${params.city} ${params.days}天行程`;
  // 票务快捷入口
  const bkBtn = document.getElementById('bkQuickBtn');
  if (bkBtn) {
    bkBtn.onclick = () => showBookingPanel(params.city, params.origin || '');
    bkBtn.style.display = '';
  }
}

function _updateResultChips(params, data) {
  const sysNames = { goal_based:'实时规划', supervised:'偏好匹配', rule_based:'经典规划' };
  const chips = document.getElementById('resultChips');
  chips.innerHTML = `
    <span class="chip agent">${sysNames[params.agent_type] || params.agent_type}</span>
    <span class="chip">${{ 低:'经济型', 中:'舒适型', 高:'奢华型' }[params.budget] || params.budget}</span>
    <span class="chip">${params.group} · ${params.num_people}人</span>
    ${params.origin ? `<span class="chip">${params.origin}出发</span>` : ''}
    ${data.processing_time ? `<span class="chip">${parseFloat(data.processing_time).toFixed(1)}s</span>` : ''}
    ${params.agent_type === 'goal_based' ? '<span class="chip web">直接生成</span>' : ''}
    ${params.agent_type === 'supervised' ? '<span class="chip ml">ML模型</span>' : ''}
    ${params.agent_type === 'rule_based' ? '<span class="chip info">规则引擎</span>' : ''}
  `;
}

function renderResult(data, params) {
  document.getElementById('welcomeSec').classList.add('gone');
  document.getElementById('resultSec').classList.add('on');
  _renderResultHeader(params);
  _updateResultChips(params, data);
  const content = data.itinerary || data.output || '';
  _renderMarkdown(document.getElementById('itinContent'), content);
  renderSide(data, params);
  window.scrollTo({ top: document.querySelector('.main').offsetTop - 16, behavior: 'smooth' });
}

// 去除 Markdown 标记符号（** __ - > # 等），保留纯文本
function _stripMd(t) {
  return (t || '').replace(/\*{1,2}|_{1,2}|~~|`|#{1,6} ?/g, '').replace(/^\s*[->\s]+/gm, '').trim();
}

// 语言选择器 — 在 renderSide 内用 L(zh, en) 按当前语言取值
function _L(zh, en) { return _lang === 'en' ? en : zh; }

// Translation maps for select values → display text
const _GROUP_EN  = {'单人':'Solo','情侣':'Couple','夫妻':'Married','朋友':'Friends','家庭':'Family'};

// ── 天气/季节查询表（25 主要城市 × 4 季）────────────────────────────────────
const _CLIMATE = {
  '东京':  {spring:'樱花季(3-4月)，10-18°C，需备雨具',summer:'炎热潮湿，28-35°C，注意防暑补水',autumn:'红叶季(11月)，凉爽宜人，12-20°C',winter:'干燥寒冷，2-8°C，可见富士山雪景'},
  '大阪':  {spring:'樱花盛开，10-17°C，适合徒步',summer:'高温潮湿，30-35°C，多室内休憩',autumn:'凉爽少雨，最佳观光季',winter:'偶有降雪，4-10°C'},
  '京都':  {spring:'樱花最佳，8-18°C，人流最旺',summer:'闷热多雨，28-36°C',autumn:'红叶绚烂，10-20°C',winter:'幽静雪景，1-8°C'},
  '首尔':  {spring:'樱花梨花同放，10-18°C',summer:'闷热多雨，25-33°C，梅雨季',autumn:'天高气爽，绝佳旅游季',winter:'干燥严寒，-6-3°C，需厚衣'},
  '新加坡':{spring:'全年28-33°C高温，偶有雷阵雨',summer:'全年高温，7-8月略少雨',autumn:'10-12月东北季风，雨水增多',winter:'12-2月仍热，偶有凉风'},
  '曼谷':  {spring:'最热月(3-4月)，34-38°C',summer:'雨季，5-10月，午后暴雨',autumn:'雨季尾，气温略降至30°C',winter:'最佳旅游季，11-2月，25-32°C'},
  '普吉岛':{spring:'旱季末，28-34°C，海况良好',summer:'雨季，海浪较大，部分海滩关闭',autumn:'雨季，建议选择安达曼海景点',winter:'旱季，最佳海滩季，28-32°C'},
  '马尔代夫':{spring:'旱季尾，清澈海水，能见度极佳',summer:'雨季开始，5-11月，海浪较大',autumn:'雨季，偶有涌浪，价格较低',winter:'旱季，最佳潜水观鱼季'},
  '迪拜':  {spring:'舒适，23-33°C，户外活动最佳',summer:'极热，38-45°C，以室内活动为主',autumn:'逐渐凉爽，28-37°C',winter:'最佳旅游季，14-24°C'},
  '伊斯坦布尔':{spring:'温暖多风，12-20°C，雨水较多',summer:'晴热干燥，25-32°C',autumn:'凉爽宜人，旅游淡季性价比高',winter:'阴冷多雨，3-9°C，偶有降雪'},
  '巴厘岛':{spring:'旱季，26-30°C，最适合出游',summer:'旱季，晴朗少雨，海景最佳',autumn:'雨季开始，仍可游览但需备雨具',winter:'雨季，12-2月降雨增多，气温27°C'},
  '巴黎':  {spring:'温和多雨，10-18°C，郁金香盛开',summer:'晴热，22-28°C，峰值旅游季',autumn:'凉爽，12-18°C，博物馆氛围最佳',winter:'阴冷，3-8°C，节日气氛浓厚'},
  '伦敦':  {spring:'多云时晴，9-15°C，常有阵雨',summer:'温暖舒适，18-24°C，日照时间长',autumn:'多雨转凉，10-15°C',winter:'阴冷潮湿，3-8°C'},
  '罗马':  {spring:'温暖宜人，14-20°C，旅游旺季',summer:'炎热干燥，30-35°C，人流最密',autumn:'凉爽舒适，绝佳旅游季',winter:'温和多雨，6-12°C'},
  '巴塞罗那':{spring:'温和，15-20°C，较少拥挤',summer:'炎热干燥，28-32°C，海滩旺季',autumn:'宜人，18-24°C，音乐节频繁',winter:'温和，9-14°C'},
  '阿姆斯特丹':{spring:'郁金香季(4月)，8-15°C，多风',summer:'温暖，18-24°C，日照长',autumn:'凉爽多雨，10-15°C',winter:'阴冷，0-6°C，偶有降雪'},
  '维也纳':{spring:'温和，10-18°C，音乐会旺季',summer:'温暖，20-28°C，户外音乐节',autumn:'凉爽，10-16°C，葡萄酒季',winter:'寒冷，0-5°C，圣诞市场著名'},
  '布拉格':{spring:'温和，10-18°C，旅游旺季开始',summer:'温暖，22-28°C，啤酒节季节',autumn:'凉爽，8-14°C，旅游淡季',winter:'寒冷，-2-4°C，雪景如童话'},
  '里斯本':{spring:'温暖，15-22°C，最适合徒步',summer:'炎热干燥，28-35°C',autumn:'温和多雨，16-22°C',winter:'温和，10-15°C，欧洲最温暖冬天之一'},
  '悉尼':  {spring:'南半球春，18-24°C(9-11月)，花朵盛开',summer:'南半球夏，26-32°C(12-2月)，海滩旺季',autumn:'南半球秋，15-22°C(3-5月)，宜人少雨',winter:'南半球冬，10-16°C(6-8月)，凉爽'},
  '纽约':  {spring:'温和，10-20°C，中央公园樱花',summer:'炎热潮湿，25-33°C，户外活动密集',autumn:'凉爽宜人，叶色金黄，最佳旅游季',winter:'寒冷多雪，-2-6°C，圣诞氛围浓'},
};
function _monthSeason(m) { return m<=2||m===12?'winter':m<=5?'spring':m<=8?'summer':'autumn'; }
const _SEASON_ZH = {spring:'春季',summer:'夏季',autumn:'秋季',winter:'冬季'};
const _SEASON_EN = {spring:'Spring',summer:'Summer',autumn:'Autumn',winter:'Winter'};

// ── 签证信息查询表（中国公民持普通护照）────────────────────────────────────
const _VISA = {
  '东京':'🟡 旅游签证 · 需提前申请(约5-7工作日)',
  '大阪':'🟡 旅游签证 · 需提前申请(约5-7工作日)',
  '京都':'🟡 旅游签证 · 需提前申请(约5-7工作日)',
  '首尔':'🟡 需 K-ETA 电子授权 · 部分情况免签',
  '新加坡':'🟢 免签 30 天',
  '曼谷':'🟢 免签 30 天(中泰互免)',
  '普吉岛':'🟢 免签 30 天(中泰互免)',
  '马尔代夫':'🟢 落地免签 30 天',
  '迪拜':'🟡 落地签或电子签(约 ¥200-400)',
  '巴厘岛':'🟡 落地签(约 ¥220)',
  '伊斯坦布尔':'🟡 e-Visa 电子签 · 提前网申(约 $51)',
  '巴黎':'🔴 申根签证 · 建议提前 3 个月申请',
  '伦敦':'🔴 英国访客签证(约 ¥1,100 起)',
  '罗马':'🔴 申根签证 · 建议提前 3 个月申请',
  '巴塞罗那':'🔴 申根签证 · 建议提前 3 个月申请',
  '阿姆斯特丹':'🔴 申根签证 · 建议提前 3 个月申请',
  '维也纳':'🔴 申根签证 · 建议提前 3 个月申请',
  '布拉格':'🔴 申根签证 · 建议提前 3 个月申请',
  '里斯本':'🔴 申根签证 · 建议提前 3 个月申请',
  '悉尼':'🟡 ETA 电子旅游签(约 AUD 20)',
  '纽约':'🔴 美国 B2 旅游签证(约 ¥1,200 + 面签)',
};
const _MODE_EN   = {'飞机':'Flight','高铁':'High-speed Rail','火车':'Train','自驾':'Self-drive','游轮':'Cruise'};
const _BUDGET_EN = {'低':'Economy','中':'Comfort','高':'Luxury'};
const _INTEREST_EN = {'文化':'Culture','美食':'Cuisine','购物':'Shopping','自然':'Nature','历史':'History','艺术':'Art','夜生活':'Nightlife','户外运动':'Outdoors'};

function renderSide(data, params) {
  const side = document.getElementById('sideCards');
  const numP = params.num_people || 2;
  // Translate param values for display
  const cityMap   = I18N[_lang]?.city_map || {};
  const dCity     = _lang === 'en' ? (cityMap[params.city]   || params.city)   : params.city;
  const dOrigin   = _lang === 'en' ? (cityMap[params.origin] || params.origin) : params.origin;
  const dGroup    = _lang === 'en' ? (_GROUP_EN[params.group]       || params.group)       : params.group;
  const dMode     = _lang === 'en' ? (_MODE_EN[params.travel_mode]  || params.travel_mode) : params.travel_mode;
  const dInterests = _lang === 'en'
    ? (params.interests || []).map(i => _INTEREST_EN[i] || i)
    : (params.interests || []);

  // ── 目的地分区（影响日均花销和大交通估算）─────────────────────
  // 近程国际（4h内，东北亚/东南亚）
  const _nearIntl = new Set(['东京','首尔','曼谷','新加坡','普吉岛','马尔代夫',
    '巴厘岛','京都','大阪','香港','台北']);
  // 中程国际（6-11h，中东/澳洲/南亚）
  const _midIntl  = new Set(['迪拜','开罗','马来西亚','吉隆坡','悉尼','墨尔本',
    '伊斯坦布尔','阿布扎比','多哈','科伦坡','孟买']);
  // 远程国际（11h+，欧美/非洲）
  const _farIntl  = new Set(['巴黎','伦敦','罗马','巴塞罗那','阿姆斯特丹','维也纳',
    '布拉格','里斯本','冰岛','哥本哈根','苏黎世','纽约','洛杉矶','芝加哥',
    '约翰内斯堡','圣保罗','墨西哥城','法兰克福']);

  const isIntl   = _nearIntl.has(params.city) || _midIntl.has(params.city) || _farIntl.has(params.city);
  const isFar    = _farIntl.has(params.city);
  const isMid    = _midIntl.has(params.city);

  // 日均花费/人（住宿+餐饮+景点+当地交通，人民币）
  const dp = isFar  ? { 低:600, 中:1500, 高:4000 }[params.budget] || 1500
           : isMid  ? { 低:550, 中:1200, 高:3200 }[params.budget] || 1200
           : isIntl ? { 低:400, 中:900,  高:2500 }[params.budget] || 900
           :          { 低:200, 中:550,  高:1500 }[params.budget] || 550;   // 国内

  // 往返大交通/人（含税，人民币）
  const fp = isFar  ? { 低:5000, 中:8000, 高:22000 }[params.budget] || 8000
           : isMid  ? { 低:3500, 中:6000, 高:16000 }[params.budget] || 6000
           : isIntl ? { 低:1800, 中:3500, 高:9000  }[params.budget] || 3500
           :          { 低:300,  中:800,  高:3000  }[params.budget] || 800;

  // data.total_budget_estimate from rule_based/supervised only covers daily costs;
  // add flight/transport cost (fp × numP) so the total is realistic
  const budgetTotal = data.total_budget_estimate
    ? Math.round(data.total_budget_estimate + fp * numP)
    : Math.round((params.days * dp + fp) * numP);
  const perPerson = Math.round(budgetTotal / numP);

  // 行程摘要
  const _d = _L('天','d'), _p = _L('人','ppl');
  let html = `<div class="sc2">
    <div class="sc2-head"><div class="sc2-head-dot"></div>${_L('行程摘要','Trip Summary')}</div>
    <div class="sc2-body">
      ${params.origin ? `<div class="srow"><span class="sk">${_L('出发地','From')}</span><span class="sv">${dOrigin || params.origin}</span></div>` : ''}
      <div class="srow"><span class="sk">${_L('目的地','Destination')}</span><span class="sv org">${dCity}</span></div>
      <div class="srow"><span class="sk">${_L('旅行天数','Duration')}</span><span class="sv">${params.days} ${_d}</span></div>
      <div class="srow"><span class="sk">${_L('出行人数','Travelers')}</span><span class="sv">${numP} ${_p}</span></div>
      <div class="srow"><span class="sk">${_L('出行类型','Group')}</span><span class="sv">${dGroup}</span></div>
      <div class="srow"><span class="sk">${_L('出行方式','Transport')}</span><span class="sv">${dMode || _L('飞机','Flight')}</span></div>
      <div class="srow"><span class="sk">${_L('偏好','Interests')}</span><span class="sv" style="font-size:11px;text-align:right;max-width:180px">${dInterests.join(' · ') || '—'}</span></div>
      <div class="budget-highlight">
        <div><div class="bh-label">${_L('人均预算参考','Est. per person')}</div><div class="bh-value">¥${perPerson.toLocaleString()}</div></div>
        <div style="text-align:right"><div class="bh-label">${_L('总预算','Total budget')}</div><div class="bh-sub" style="font-size:13px;font-weight:700;color:var(--text2)">¥${budgetTotal.toLocaleString()}</div></div>
      </div>
      <div style="font-size:10px;color:var(--text3);margin-top:6px;line-height:1.5">${_L('⚠ 仅供参考，机票价格波动较大，实际费用以票务搜索结果为准。','⚠ Reference only. Flight prices vary; check the booking section for real prices.')}</div>
    </div>
  </div>`;

  if (params.agent_type === 'supervised') {
    const topF = data.top_features || [];
    const conf = data.model_confidence || 0;
    const acc  = data.model_accuracy  || 0.868;
    const dsz  = data.dataset_size    || 10000;
    html += `<div class="sc2">
      <div class="sc2-head"><div class="sc2-head-dot" style="background:var(--green)"></div>${_L('模型决策','Model Decision')}</div>
      <div class="sc2-body">
        <div class="srow"><span class="sk">${_L('推荐类型','Trip Type')}</span><span class="sv org">${data.recommendation_type_zh || '—'}</span></div>
        <div class="conf-wrap">
          <div class="conf-label"><span style="font-size:11px;color:var(--text3)">${_L('模型置信度','Confidence')}</span><span class="conf-pct">${(conf * 100).toFixed(0)}%</span></div>
          <div class="pbar"><div class="pbar-fill" style="width:${conf * 100}%"></div></div>
        </div>
        <div style="margin:12px 0 6px;font-size:10px;font-weight:700;letter-spacing:.5px;color:var(--text3);text-transform:uppercase">${_L('关键影响因素','Key Features')}</div>
        ${topF.map(([k, v]) => `<div class="feat">
          <div class="feat-name">${k}</div>
          <div class="feat-row">
            <div class="feat-bar"><div class="feat-bar-fill" style="width:${Math.min(v * 400, 100)}%"></div></div>
            <div class="feat-val">${(v * 100).toFixed(1)}%</div>
          </div>
        </div>`).join('')}
        <div class="srow" style="margin-top:10px"><span class="sk">${_L('训练集规模','Training Size')}</span><span class="sv">${dsz.toLocaleString()}</span></div>
        <div class="srow"><span class="sk">${_L('测试准确率','Test Accuracy')}</span>
          <span class="sv" style="color:var(--text2)" title="${_L('基于合成数据，非真实用户行为','Synthetic data, not real-world performance')}">${(acc * 100).toFixed(1)}%</span>
        </div>
        <div class="srow"><span class="sk">${_L('模型类型','Model Type')}</span><span class="sv" style="font-size:11px">VotingClassifier</span></div>
      </div>
    </div>
  `;
  }

  if (params.agent_type === 'goal_based') {
    const steps = data.agent_steps || [];
    const totalT = data.processing_time || 0;
    const isStreaming = !data.processing_time; // 初始骨架：尚未完成

    html += `<div class="sc2">
      <div class="sc2-head"><div class="sc2-head-dot" style="background:var(--blue)"></div>${_L('规划过程','Planning Process')}</div>
      <div class="tl">
        <div class="tl-item">
          <div class="tl-dot done">✓</div>
          <div class="tl-content"><div class="tl-label">${_L('需求解析','Request Parsed')}</div><div class="tl-sub">${params.city} ${params.days}${_L('天','d')} · ${params.group} ${numP}${_L('人','ppl')}</div></div>
        </div>
        ${isStreaming
          /* ── 流式阶段：内嵌工具调用实时日志 ── */
          ? `<div class="tl-item tl-item--stream">
              <div class="tl-dot tl-dot--pulse"></div>
              <div class="tl-content" style="flex:1;min-width:0">
                <div class="tl-label">${_L('工具调用中…','Calling Tools…')}</div>
                <pre id="toolLogContent" class="tool-log-inline"></pre>
              </div>
            </div>`
          /* ── 完成后：逐条时间轴 ── */
          : steps.map((s, i) => {
              // 两种工具都优先用参数构成可读描述，result_preview 作备用
              const preview = s.tool === 'search_web'
                ? (s.args?.query || s.result_preview || '')
                : (s.args?.city && s.args?.query
                    ? `${s.args.city} · ${s.args.query}`
                    : (s.args?.query || s.result_preview || ''));
              const timeBadge = s.time_s ? `<span style="float:right;font-size:9.5px;color:var(--text3);font-weight:400">${s.time_s}s</span>` : '';
              return `<div class="tl-item">
                <div class="tl-dot ${s.tool === 'search_web' ? 'search' : 'kb'}">${i + 1}</div>
                <div class="tl-content">
                  <div class="tl-label">${s.tool === 'search_web' ? _L('联网搜索','Web Search') : _L('知识库查询','Knowledge Base')}${timeBadge}</div>
                  <div class="tl-sub">${_stripMd(preview).slice(0, 200)}</div>
                </div>
              </div>`;
            }).join('')
        }
        <div class="tl-item">
          <div class="tl-dot ${isStreaming ? 'tl-dot--wait' : 'done'}">
            ${isStreaming ? '' : '✓'}
          </div>
          <div class="tl-content">
            <div class="tl-label">${isStreaming ? _L('生成行程中…','Generating…') : _L('行程生成完成','Itinerary Ready')}</div>
            ${!isStreaming ? `<div class="tl-sub">${_L('总耗时','Total')} ${totalT.toFixed(1)}s</div>` : ''}
          </div>
        </div>
      </div>
      <div class="sc2-body" style="padding-top:0;border-top:1px solid var(--border)">
        <div class="srow"><span class="sk">${_L('工具调用','Tool Calls')}</span><span class="sv blu">${data.tool_rounds ?? 0} ${_L('轮','rounds')}</span></div>
        <div class="srow"><span class="sk">${_L('本地知识库','Knowledge Base')}</span><span class="sv grn">${steps.some(s => s.tool === 'query_knowledge_base') ? _L('已查询','Queried') : _L('预注入','Pre-injected')}</span></div>
        <div class="srow"><span class="sk">${_L('实时联网','Web Search')}</span><span class="sv">${steps.some(s => s.tool === 'search_web') ? `<span style="color:var(--green)">${_L('已检索','Active')}</span>` : _L('未启用','Disabled')}</span></div>
      </div>
    </div>`;
  }

  if (params.agent_type === 'rule_based') {
    html += `<div class="sc2">
      <div class="sc2-head"><div class="sc2-head-dot" style="background:var(--purple)"></div>${_L('规则引擎','Rule Engine')}</div>
      <div class="sc2-body">
        <div class="srow"><span class="sk">${_L('规则城市库','City Coverage')}</span><span class="sv">25 ${_L('个城市','cities')}</span></div>
        <div class="srow"><span class="sk">${_L('响应时间','Response')}</span><span class="sv grn">&lt;0.1s</span></div>
        <div class="srow"><span class="sk">${_L('可解释性','Explainability')}</span><span class="sv grn">100%</span></div>
        ${((_lang==='en'?data.transport_tip_en:null)||data.transport_tip) ? `<div style="padding:7px 0;border-top:1px solid var(--border)"><div style="font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--text3);text-transform:uppercase;margin-bottom:3px">${_L('交通建议','Transport Tip')}</div><div style="font-size:11.5px;color:var(--text2);line-height:1.7">${(_lang==='en'?data.transport_tip_en:null)||data.transport_tip}</div></div>` : ''}
        ${((_lang==='en'?data.city_tips_en:null)||data.city_tips||[]).map(t=>`<div style="font-size:11px;color:var(--text3);padding:6px 0;border-bottom:1px solid #F5F6F8;line-height:1.6">${t}</div>`).join('')}
      </div>
    </div>`;
  }

  // ── 偏好匹配：概率分布卡（supervised only，生成完成后有数据才显示）──────────
  if (params.agent_type === 'supervised') {
    const probaDist = data.proba_distribution || [];
    const isUncertain = data.is_uncertain;
    if (probaDist.length > 1) {
      const top3 = probaDist.slice(0, 3);
      const maxP = top3[0][1];
      html += `<div class="sc2">
        <div class="sc2-head"><div class="sc2-head-dot" style="background:var(--accent)"></div>${_L('备选方案评估','Alternative Plans')}${isUncertain ? `<span style="margin-left:auto;font-size:9px;padding:1px 6px;background:#FEF9C3;color:#92400E;border-radius:4px;font-weight:600">${_L('置信度较低','Low confidence')}</span>` : ''}</div>
        <div class="sc2-body">
          <div style="font-size:10px;color:var(--text3);margin-bottom:8px">${_L('模型对各旅行类型的概率评分（前3）','Model probability scores for top-3 trip types')}</div>
          ${top3.map(([label, prob], i) => `
            <div style="margin-bottom:8px">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">
                <span style="font-size:11.5px;font-weight:${i===0?'700':'500'};color:${i===0?'var(--text)':'var(--text2)'}">${label}</span>
                <span style="font-size:11px;font-weight:600;color:${i===0?'var(--accent)':'var(--text3)'}">${(prob*100).toFixed(0)}%</span>
              </div>
              <div style="height:4px;background:var(--border);border-radius:2px;overflow:hidden">
                <div style="height:100%;width:${(prob/maxP*100).toFixed(0)}%;background:${i===0?'var(--accent)':'var(--border-dark)'};border-radius:2px;transition:width .4s"></div>
              </div>
            </div>`).join('')}
        </div>
      </div>`;
    }
  }

  // ── 天气/季节卡（所有 agent，有数据时显示）──────────────────────────────────
  const _tMonth = params.start_date ? new Date(params.start_date).getMonth() + 1 : new Date().getMonth() + 1;
  const _tSeason = _monthSeason(_tMonth);
  const _weatherNote = data.weather_note || (_CLIMATE[params.city] && _CLIMATE[params.city][_tSeason]);
  if (_weatherNote) {
    const _seasonLabel = _lang === 'en' ? _SEASON_EN[_tSeason] : _SEASON_ZH[_tSeason];
    html += `<div class="sc2">
      <div class="sc2-head">
        <div class="sc2-head-dot" style="background:#0891B2"></div>
        ${_L('天气参考','Weather Reference')}
        <span style="margin-left:auto;font-size:10px;color:var(--text3);font-weight:500">${_tMonth}${_L('月','月')} · ${_seasonLabel}</span>
      </div>
      <div class="sc2-body">
        <div style="font-size:12px;color:var(--text2);line-height:1.85">${_weatherNote}</div>
        <div style="font-size:10px;color:var(--text3);margin-top:8px;padding-top:8px;border-top:1px solid var(--border)">${_L('建议出行前查看实时天气预报','Check real-time forecast before departure')}</div>
      </div>
    </div>`;
  }

  // ── 签证提醒卡（国际目的地，有签证数据时显示）──────────────────────────────
  const _visaInfo = _VISA[params.city];
  if (_visaInfo && params.city !== (params.origin || '')) {
    const _visaColor = _visaInfo.startsWith('🟢') ? 'var(--green)' : _visaInfo.startsWith('🔴') ? '#DC2626' : '#D97706';
    html += `<div class="sc2">
      <div class="sc2-head"><div class="sc2-head-dot" style="background:${_visaColor}"></div>${_L('签证提醒','Visa Info')}</div>
      <div class="sc2-body">
        <div style="font-size:12px;color:var(--text2);line-height:1.8">${_visaInfo}</div>
        <div style="font-size:10px;color:var(--text3);margin-top:7px;padding-top:7px;border-top:1px solid var(--border)">${_L('以出行时官方政策为准 · 建议提前核实','Verify with official sources before travel')}</div>
      </div>
    </div>`;
  }

  // ── 出行贴士（静态，所有 agent）────────────────────────────────────────────
  html += `<div class="sc2">
    <div class="sc2-head"><div class="sc2-head-dot" style="background:var(--text3)"></div>${_L('出行贴士','Travel Tips')}</div>
    <div class="sc2-body" style="font-size:12px;color:var(--text2);line-height:2.1">
      ${_L('热门景点建议提前在线预约','Book popular attractions online in advance')}<br>
      ${_L('出发前下载目的地离线地图','Download offline maps before departure')}<br>
      ${_L('出入境携带现金通常不超过等值 ¥20,000','Carry no more than equivalent of ¥20,000 cash through customs')}<br>
      ${_L('护照复印件单独保存备用','Keep a separate copy of your passport')}
    </div>
  </div>`;

  side.innerHTML = html;
}

let chatOpen = false;
function toggleChat() {
  chatOpen = !chatOpen;
  document.getElementById('chatToggle').classList.toggle('open', chatOpen);
  document.getElementById('chatHist').classList.toggle('open', chatOpen);
}
function addMsg(role, text) {
  chatMsgs.push({ role, text });
  const hist = document.getElementById('chatHist');
  const d = document.createElement('div');
  d.className = `cmsg ${role}`;
  d.innerHTML = `<div class="cavatar">${role === 'u' ? _L('你','You') : 'AI'}</div><div class="cbubble">${text}</div>`;
  hist.appendChild(d);
  document.getElementById('chatCnt').textContent = `(${chatMsgs.length})`;
  if (chatOpen) hist.scrollTop = hist.scrollHeight;
}

async function copyResult() {
  try {
    await navigator.clipboard.writeText(document.getElementById('itinContent').innerText);
    toast(_L('已复制到剪贴板','Copied to clipboard'), 'ok');
  } catch { toast(_L('复制失败，请手动选择','Copy failed, please select manually'), 'err'); }
}

let stepTimer = null;
function setLoad(show, agentType) {
  document.getElementById('loadBar').classList.toggle('on', show);
  document.getElementById('loadMsg').classList.toggle('on', show);
  document.getElementById('searchBtn').disabled = show;
  document.getElementById('botSendBtn').disabled = show;
  if (show) {
    ['ls1','ls2','ls3'].forEach(s => document.getElementById(s).classList.remove('vis'));
    document.getElementById('ls1').classList.add('vis');
    const isEn = _lang === 'en';
    document.getElementById('ls1').textContent =
      agentType === 'goal_based' ? (isEn ? 'Parsing request, preparing web search...' : '正在解析需求，准备联网搜索...') :
      agentType === 'supervised' ? (isEn ? 'Extracting features, loading ML model...' : '正在提取特征，加载 ML 模型...') :
      (isEn ? 'Rule engine matching...' : '规则引擎匹配中...');
    document.getElementById('ls2').textContent =
      agentType === 'goal_based' ? (isEn ? 'Searching destination in real time...' : '智能搜索目的地实时信息...') :
      agentType === 'supervised' ? (isEn ? 'Ensemble classifier inferring trip type...' : '集成分类器推断旅行类型...') :
      (isEn ? 'Assembling daily itinerary...' : '组装每日行程...');
    document.getElementById('ls3').textContent = isEn ? 'Generating full personalized itinerary...' : '生成完整个性化行程内容...';
    let i = 1;
    stepTimer = setInterval(() => {
      const ids = ['ls1','ls2','ls3'];
      if (i < ids.length) document.getElementById(ids[i++]).classList.add('vis');
      else clearInterval(stepTimer);
    }, 1800);
    // Elapsed timer
    clearInterval(loadTimer);
    loadTimer = setInterval(() => {
      const s = ((Date.now() - loadStart) / 1000).toFixed(0);
      document.getElementById('ltime').textContent = _lang === 'en' ? `Waited ${s}s` : `已等待 ${s}s`;
    }, 1000);
  } else {
    clearInterval(stepTimer);
    clearInterval(loadTimer);
    document.getElementById('ltime').textContent = '';
  }
}

let toastTimer = null;
function toast(msg, type = '') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast ${type} on`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.className = 'toast', 3000);
}

// ── 国际化（中 / EN）────────────────────────────────
const I18N = {
  zh: {
    nav_goal: '实时规划', nav_ml: '偏好匹配', nav_rule: '经典规划',
    status_connecting: '连接中', status_ok: '服务正常', status_err: '服务异常',
    hero_label: 'AI 驱动 · 全球目的地覆盖',
    hero_title: '探索世界<br><em>让 AI 为你规划</em>',
    hero_sub: '世界很大，出发就是答案',
    label_origin: '出发地', hint_origin: '出发城市（可选）', ph_origin: '上海',
    label_dest: '目的地', hint_dest: '可输入任意城市或地区', ph_dest: '巴黎、迪拜、首尔...',
    label_days: '天数', label_people: '人数', label_group: '出行类型',
    label_mode: '出行方式', label_budget: '预算档次', label_special: '特殊需求',
    label_date: '出发日期',
    label_pref: '偏好', btn_plan: '开始规划',
    tag_culture: '文化', tag_food: '美食', tag_shopping: '购物',
    tag_nature: '自然', tag_history: '历史', tag_art: '艺术',
    tag_nightlife: '夜生活', tag_outdoor: '户外运动',
    bot_hint: '快速规划：', bot_ph: '直接描述，如：从北京飞迪拜5天，夫妻，喜欢购物和美食，预算充裕...',
    bk_title: '搜索交通票务', bk_flight: '机票', bk_train: '火车票', bk_orders: '我的订单',
    bk_origin: '出发城市', bk_dest: '目的城市', bk_date: '出发日期', bk_search: '搜索',
    // search card tabs
    sctab_goal: '实时规划', sctab_ml: '偏好匹配', sctab_rule: '经典规划',
    // selects
    select_days: ['1 天','2 天','3 天','4 天','5 天','7 天','10 天','14 天'],
    select_people: ['1 人','2 人','3 人','4 人','5 人','6 人','7~8 人','9+ 人'],
    select_group: ['独旅','情侣','夫妻','朋友','家庭'],
    select_transport: ['飞机','高铁','火车','自驾','游轮'],
    select_budget: ['经济型','舒适型','奢华型'],
    select_special: ['无','有儿童','有老人','无障碍'],
    // hot bar
    hot_label: '热门：',
    // loading steps
    ls1: '正在分析您的旅行需求...',
    ls2: '搜索目的地信息...',
    ls3: '生成个性化行程...',
    // action buttons
    btn_ticket: '搜索票务', btn_copy: '复制',
    // chat
    chat_log: '对话记录',
    // system cards
    sys_rule_badge: '规则系统', sys_rule_name: '经典规划',
    sys_rule_desc: '人工编写的 25 城专家规则库，景点·餐厅·交通·贴士全套内置，每条推荐精准溯源至具体规则，逻辑 100% 透明可审查，无需联网，毫秒响应。',
    sys_rule_k1: '覆盖城市', sys_rule_k2: '响应时间', sys_rule_k3: '可解释性',
    sys_ml_badge: '机器学习', sys_ml_name: '偏好匹配',
    sys_ml_desc: '集成学习模型综合分析出行偏好、预算与人群特征，从 8 种旅行模式中智能匹配最适方案，推荐依据特征权重完全透明可查。',
    sys_ml_k1: '模型准确率', sys_ml_k2: '旅行模式', sys_ml_k3: '偏好维度',
    sys_ai_badge: '推荐使用', sys_ai_name: '实时规划',
    sys_ai_desc: '大模型自主决策，联网搜索目的地最新票价、开放时间与住宿推荐，支持<strong>全球任意目的地</strong>，每份行程都基于当下最新数据生成。',
    sys_ai_k1: '城市覆盖', sys_ai_v2: '实时', sys_ai_k2: '联网获取', sys_ai_v3: 'Qwen', sys_ai_k3: '核心模型',
    // section headings
    sec_systems: '选择 AI 规划模式',
    sec_hot_dest: '热门目的地', sec_more: '查看全部 ›',
    // destination badges
    badge_hot: '热门', badge_luxury: '奢华', badge_value: '性价比', badge_island: '海岛',
    // destination names & subs
    dest_paris: '巴黎', dest_paris_sub: '法国 · 浪漫之都',
    dest_tokyo: '东京', dest_tokyo_sub: '日本 · 都市与传统',
    dest_nyc: '纽约', dest_nyc_sub: '美国 · 城市之巅',
    dest_dubai: '迪拜', dest_dubai_sub: '阿联酋 · 未来之城',
    dest_seoul: '首尔', dest_seoul_sub: '韩国 · 潮流前线',
    dest_phuket: '普吉岛', dest_phuket_sub: '泰国 · 海岛天堂',
    dest_london: '伦敦', dest_london_sub: '英国 · 经典与现代',
    dest_rome: '罗马', dest_rome_sub: '意大利 · 永恒之城',
    dest_singapore: '新加坡', dest_singapore_sub: '新加坡 · 花园城市',
    // price suffix
    price_suffix: '起/人',
    // tools panel
    btn_tools: '工具',
    tp_tab_currency: '汇率', tp_tab_emergency: '紧急', tp_tab_phrases: '短语',
    tp_currency_title: '汇率换算', tp_emergency_title: '紧急联系方式', tp_phrases_title: '常用短语',
    tp_currency_ph: '输入金额，如 100', tp_currency_hint: '输入金额开始换算',
    tp_currency_note: '参考汇率 · 实际以银行为准', tp_city_sel: '选择城市',
    // pickers
    cp_all_origin: '全部出发城市', cp_hot_origin: '热门出发地',
    cp_all_dest: '全部目的地', cp_hot_dest: '热门推荐',
    // history & smart fill
    hist_recent: '最近：', smart_fill: '✦ 智能填写',
    // view more toggle
    sec_more_open: '查看全部 ›', sec_more_close: '收起 ↑',
    // my trips
    sec_my_trips: '我的旅行记录', btn_clear_trips: '清空',
    // extra dest badges
    badge_tropical: '热带',
    // extra dest cards
    dest_sydney: '悉尼',        dest_sydney_sub: '澳大利亚 · 港湾之城',
    dest_barcelona: '巴塞罗那',  dest_barcelona_sub: '西班牙 · 艺术之都',
    dest_bangkok: '曼谷',       dest_bangkok_sub: '泰国 · 微笑之城',
    dest_amsterdam: '阿姆斯特丹', dest_amsterdam_sub: '荷兰 · 运河之城',
    dest_vienna: '维也纳',       dest_vienna_sub: '奥地利 · 音乐之都',
    dest_prague: '布拉格',       dest_prague_sub: '捷克 · 童话古城',
    dest_maldives: '马尔代夫',   dest_maldives_sub: '印度洋 · 蓝色天堂',
    dest_istanbul: '伊斯坦布尔', dest_istanbul_sub: '土耳其 · 东西方交汇',
    dest_lisbon: '里斯本',       dest_lisbon_sub: '葡萄牙 · 法朵古都',
    dest_bali: '巴厘岛',         dest_bali_sub: '印尼 · 神明之岛',
    dest_osaka: '大阪',          dest_osaka_sub: '日本 · 美食之都',
    dest_kyoto: '京都',          dest_kyoto_sub: '日本 · 千年古都',
    // city name map (Chinese → display; zh is identity)
    city_map: {},
  },
  en: {
    nav_goal: 'Live Planner', nav_ml: 'Smart Pick', nav_rule: 'Classic',
    status_connecting: 'Connecting', status_ok: 'Online', status_err: 'Offline',
    hero_label: 'AI-Powered · Global Destinations',
    hero_title: 'Explore the World<br><em>Let AI Plan for You</em>',
    hero_sub: 'The world is vast — just go',
    label_origin: 'From', hint_origin: 'Departure city (optional)', ph_origin: 'Shanghai',
    label_dest: 'To', hint_dest: 'Enter any city or region', ph_dest: 'Paris, Dubai, Seoul...',
    label_days: 'Days', label_people: 'People', label_group: 'Group Type',
    label_mode: 'Transport', label_budget: 'Budget', label_special: 'Special',
    label_date: 'Depart Date',
    label_pref: 'Interests', btn_plan: 'Plan My Trip',
    tag_culture: 'Culture', tag_food: 'Cuisine', tag_shopping: 'Shopping',
    tag_nature: 'Nature', tag_history: 'History', tag_art: 'Art',
    tag_nightlife: 'Nightlife', tag_outdoor: 'Outdoors',
    bot_hint: 'Quick plan:', bot_ph: 'Describe your trip, e.g.: 5 days in Dubai, couple, love food and shopping, flexible budget...',
    bk_title: 'Search Transport', bk_flight: 'Flights', bk_train: 'Trains', bk_orders: 'My Orders',
    bk_origin: 'From City', bk_dest: 'To City', bk_date: 'Date', bk_search: 'Search',
    // search card tabs
    sctab_goal: 'Live Planner', sctab_ml: 'Smart Pick', sctab_rule: 'Classic',
    // selects
    select_days: ['1 Day','2 Days','3 Days','4 Days','5 Days','7 Days','10 Days','14 Days'],
    select_people: ['1 Person','2 People','3 People','4 People','5 People','6 People','7-8 People','9+ People'],
    select_group: ['Solo','Couple','Married','Friends','Family'],
    select_transport: ['Flight','High-speed Rail','Train','Self-drive','Cruise'],
    select_budget: ['Economy','Comfort','Luxury'],
    select_special: ['None','With Children','With Elderly','Wheelchair'],
    // hot bar
    hot_label: 'Popular:',
    // loading steps
    ls1: 'Analyzing your travel needs...',
    ls2: 'Searching destination info...',
    ls3: 'Generating personalized itinerary...',
    // action buttons
    btn_ticket: 'Search Tickets', btn_copy: 'Copy',
    // chat
    chat_log: 'Chat History',
    // system cards
    sys_rule_badge: 'Rule-Based', sys_rule_name: 'Classic Planner',
    sys_rule_desc: 'Precision matching via expert knowledge rules. Fully transparent & explainable logic with millisecond response. Built-in sights, restaurants, transport & tips.',
    sys_rule_k1: 'Cities', sys_rule_k2: 'Response', sys_rule_k3: 'Explainability',
    sys_ml_badge: 'Machine Learning', sys_ml_name: 'Smart Recommender',
    sys_ml_desc: 'Ensemble model trained on 10,000 records (GBT + RandomForest + ExtraTrees), 20 features, 8 trip types, feature importance visualization.',
    sys_ml_k1: 'Test Accuracy', sys_ml_k2: 'Trip Types', sys_ml_k3: 'Features',
    sys_ai_badge: 'Recommended', sys_ai_name: 'Live Planner',
    sys_ai_desc: 'Tongyi Qianwen LLM + real-time web search. AI autonomously decides tool-call strategy to fetch latest prices, hours & accommodation. Supports <strong>any destination worldwide</strong>.',
    sys_ai_k1: 'Cities', sys_ai_v2: 'Live', sys_ai_k2: 'Data Source', sys_ai_v3: 'Qwen', sys_ai_k3: 'Core Model',
    // section headings
    sec_systems: 'Choose AI Planning Mode',
    sec_hot_dest: 'Popular Destinations', sec_more: 'View All ›',
    // destination badges
    badge_hot: 'Hot', badge_luxury: 'Luxury', badge_value: 'Value', badge_island: 'Island',
    // destination names & subs
    dest_paris: 'Paris', dest_paris_sub: 'France · City of Romance',
    dest_tokyo: 'Tokyo', dest_tokyo_sub: 'Japan · Urban & Traditional',
    dest_nyc: 'New York', dest_nyc_sub: 'USA · City on Top',
    dest_dubai: 'Dubai', dest_dubai_sub: 'UAE · City of the Future',
    dest_seoul: 'Seoul', dest_seoul_sub: 'Korea · Trendsetting Hub',
    dest_phuket: 'Phuket', dest_phuket_sub: 'Thailand · Island Paradise',
    dest_london: 'London', dest_london_sub: 'UK · Classic & Contemporary',
    dest_rome: 'Rome', dest_rome_sub: 'Italy · The Eternal City',
    dest_singapore: 'Singapore', dest_singapore_sub: 'Singapore · Garden City',
    // price suffix
    price_suffix: '/pp',
    // tools panel
    btn_tools: 'Tools',
    tp_tab_currency: 'Currency', tp_tab_emergency: 'Emergency', tp_tab_phrases: 'Phrases',
    tp_currency_title: 'Exchange Rates', tp_emergency_title: 'Emergency Contacts', tp_phrases_title: 'Useful Phrases',
    tp_currency_ph: 'Amount, e.g. 100', tp_currency_hint: 'Enter amount to convert',
    tp_currency_note: 'Reference rate · Bank rates may differ', tp_city_sel: 'Select City',
    // pickers
    cp_all_origin: 'All Departure Cities', cp_hot_origin: 'Popular Departures',
    cp_all_dest: 'All Destinations', cp_hot_dest: 'Popular',
    // history & smart fill
    hist_recent: 'Recent:', smart_fill: '✦ Smart Fill',
    // view more toggle
    sec_more_open: 'View All ›', sec_more_close: 'Show Less ↑',
    // my trips
    sec_my_trips: 'My Trips', btn_clear_trips: 'Clear',
    // extra dest badges
    badge_tropical: 'Tropical',
    // extra dest cards
    dest_sydney: 'Sydney',        dest_sydney_sub: 'Australia · Harbour City',
    dest_barcelona: 'Barcelona',  dest_barcelona_sub: 'Spain · City of Art',
    dest_bangkok: 'Bangkok',      dest_bangkok_sub: 'Thailand · City of Smiles',
    dest_amsterdam: 'Amsterdam',  dest_amsterdam_sub: 'Netherlands · City of Canals',
    dest_vienna: 'Vienna',        dest_vienna_sub: 'Austria · City of Music',
    dest_prague: 'Prague',        dest_prague_sub: 'Czech · Fairy-Tale City',
    dest_maldives: 'Maldives',    dest_maldives_sub: 'Indian Ocean · Blue Paradise',
    dest_istanbul: 'Istanbul',    dest_istanbul_sub: 'Turkey · East Meets West',
    dest_lisbon: 'Lisbon',        dest_lisbon_sub: 'Portugal · City of Fado',
    dest_bali: 'Bali',            dest_bali_sub: 'Indonesia · Island of Gods',
    dest_osaka: 'Osaka',          dest_osaka_sub: 'Japan · Food Capital',
    dest_kyoto: 'Kyoto',          dest_kyoto_sub: 'Japan · Ancient Capital',
    // city name map (Chinese → English display)
    city_map: {
      '上海':'Shanghai','北京':'Beijing','广州':'Guangzhou','深圳':'Shenzhen',
      '成都':'Chengdu','杭州':'Hangzhou','武汉':'Wuhan','重庆':'Chongqing',
      '西安':"Xi'an",'南京':'Nanjing','天津':'Tianjin','苏州':'Suzhou',
      '厦门':'Xiamen','长沙':'Changsha','青岛':'Qingdao','大连':'Dalian',
      '济南':'Jinan','哈尔滨':'Harbin','昆明':'Kunming','郑州':'Zhengzhou',
      '香港':'Hong Kong','台北':'Taipei','澳门':'Macao',
      '巴黎':'Paris','东京':'Tokyo','纽约':'New York','伦敦':'London',
      '罗马':'Rome','悉尼':'Sydney','巴塞罗那':'Barcelona','曼谷':'Bangkok',
      '首尔':'Seoul','迪拜':'Dubai','新加坡':'Singapore','阿姆斯特丹':'Amsterdam',
      '马尔代夫':'Maldives','普吉岛':'Phuket','布拉格':'Prague','维也纳':'Vienna',
      '伊斯坦布尔':'Istanbul','里斯本':'Lisbon','开罗':'Cairo','巴厘岛':'Bali',
      '京都':'Kyoto','大阪':'Osaka','哥本哈根':'Copenhagen','苏黎世':'Zurich',
    },
  }
};

let _lang = localStorage.getItem('yy_lang') || 'zh';

function toggleLang() {
  _lang = _lang === 'zh' ? 'en' : 'zh';
  localStorage.setItem('yy_lang', _lang);
  applyLang();
}

function applyLang() {
  const t = I18N[_lang];
  // text nodes
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    if (t[key] !== undefined) el.textContent = t[key];
  });
  // innerHTML (for hero title with <br><em> and sys_ai_desc with <strong>)
  document.querySelectorAll('[data-i18n-html]').forEach(el => {
    const key = el.dataset.i18nHtml;
    if (t[key] !== undefined) el.innerHTML = t[key];
  });
  // placeholders
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.dataset.i18nPlaceholder;
    if (t[key] !== undefined) el.placeholder = t[key];
  });
  // select dropdowns — rebuild option display text, preserving values
  document.querySelectorAll('[data-i18n-select]').forEach(el => {
    const key = el.dataset.i18nSelect;
    const labels = t[key];
    if (!Array.isArray(labels)) return;
    const opts = el.options;
    for (let i = 0; i < opts.length && i < labels.length; i++) {
      opts[i].textContent = labels[i];
    }
  });
  // search card tabs — update only the text span, keep the svg and .tag badge intact
  document.querySelectorAll('[data-i18n-sctab]').forEach(el => {
    const key = el.dataset.i18nSctab;
    if (t[key] === undefined) return;
    const span = el.querySelector('.sc-tab-text');
    if (span) span.textContent = t[key];
  });
  // nav pills (have inner HTML with badge spans)
  const navGoal = document.querySelector('.nav-pill[data-agent="goal_based"]');
  if (navGoal) navGoal.innerHTML = `${t.nav_goal} <span class="nav-badge">AI</span>`;
  const navMl   = document.querySelector('.nav-pill[data-agent="supervised"]');
  if (navMl)   navMl.textContent = t.nav_ml;
  const navRule = document.querySelector('.nav-pill[data-agent="rule_based"]');
  if (navRule) navRule.textContent = t.nav_rule;
  // lang button label
  document.getElementById('langBtn').textContent = _lang === 'zh' ? 'EN' : '中文';
  // html lang attr (also updates native date picker locale in Chrome)
  document.documentElement.lang = _lang === 'zh' ? 'zh-CN' : 'en';
  // date input locale
  const dateInput = document.getElementById('startDateInput');
  if (dateInput) dateInput.lang = _lang === 'zh' ? 'zh-CN' : 'en-US';
  // city buttons (hot-btn with data-city attribute)
  const cityMap = t.city_map || {};
  document.querySelectorAll('.hot-btn[data-city]').forEach(btn => {
    const zh = btn.dataset.city;
    btn.textContent = _lang === 'en' ? (cityMap[zh] || zh) : zh;
  });
  // re-render city picker grids with updated language
  _renderOriginGrid('');
  _renderDestGrid('');
  // health status text (re-apply current state)
  const dot = document.getElementById('statusDot');
  const statusEl = document.getElementById('statusText');
  if (dot && statusEl) {
    if (dot.classList.contains('on')) statusEl.textContent = t.status_ok;
    else if (dot.classList.contains('off')) statusEl.textContent = t.status_err;
    else statusEl.textContent = t.status_connecting;
  }
  // re-render history strip so "最近：" / "✦ 智能填写" update in new language
  if (typeof _histRender === 'function') _histRender();

  // 切换语言时，更新已选中的城市输入框显示名称（cityMap 已在上方声明）
  ['destInput', 'originInput'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    const zh = el.dataset.zh || el.value.trim();
    if (!zh) return;
    el.value = _lang === 'en' ? (cityMap[zh] || zh) : zh;
    el.dataset.zh = zh;  // 保持中文名
  });
}

// Override checkHealth to use i18n
const _origCheckHealth = typeof checkHealth !== 'undefined' ? checkHealth : null;

// ── 票务功能 ────────────────────────────────────────
let _bkType = 'flight';
let _pendingTicket = null;

function showBookingPanel(city, origin) {
  const wrap = document.getElementById('bookingWrap');
  wrap.style.display = 'block';
  // 票务面板已移至行程卡片正下方，平滑滚动到面板顶部
  setTimeout(() => wrap.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 50);
  if (city) document.getElementById('bkDest').value = city;
  if (origin) document.getElementById('bkOrigin').value = origin;
  // 出发日期：优先用表单中选择的出发日期
  const formDate = document.getElementById('startDateInput')?.value;
  document.getElementById('bkDate').value = formDate || _todayStr();
  setBkType('flight');
  showBkSearch();
}

function setBkType(t) {
  _bkType = t;
  ['flight','train'].forEach(k => {
    const tab = document.getElementById(k === 'flight' ? 'bkTabFlight' : 'bkTabTrain');
    if (tab) tab.classList.toggle('active', k === t);
  });
  const ordTab = document.getElementById('bkTabOrders');
  if (ordTab) ordTab.classList.remove('active');
  showBkSearch();
}

function showBkSearch() {
  document.getElementById('bkSearchArea').style.display = '';
  document.getElementById('bkOrdersArea').style.display = 'none';
  const ordTab = document.getElementById('bkTabOrders');
  if (ordTab) ordTab.classList.remove('active');
}

async function searchTickets() {
  const origin = document.getElementById('bkOrigin').value.trim();
  const dest   = document.getElementById('bkDest').value.trim();
  const date   = document.getElementById('bkDate').value;
  if (!origin || !dest || !date) { toast('请填写出发城市、目的地和日期', 'err'); return; }
  const box = document.getElementById('ticketResults');
  box.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text3)">正在搜索…</div>';
  try {
    const r = await fetch(`${API}/booking/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ origin, destination: dest, date, type: _bkType })
    });
    const data = await r.json();
    if (!r.ok) throw new Error(_extractErrMsg(data));
    // 按出发时间升序排列（web_info 类无时间字段，沉底）
    const tickets = (data.tickets || []).sort((a, b) => {
      if (a.type === 'web_info' && b.type !== 'web_info') return 1;
      if (b.type === 'web_info' && a.type !== 'web_info') return -1;
      return (a.dep || '').localeCompare(b.dep || '');
    });
    if (!tickets.length) {
      const bkType = document.getElementById('bkTabFlight')?.classList.contains('active') ? '机票' : '火车票';
      box.innerHTML = `<div style="text-align:center;padding:28px 20px;color:var(--text3);line-height:2">
        <div style="font-size:15px;font-weight:600;color:var(--text2);margin-bottom:6px">暂未覆盖该路线数据</div>
        <div style="font-size:12.5px;margin-bottom:14px">请前往以下平台查询实时${bkType}</div>
        <div style="display:flex;justify-content:center;gap:10px;flex-wrap:wrap">
          <a href="https://www.trip.com/flights/" target="_blank" style="padding:7px 18px;border-radius:8px;background:var(--accent);color:#fff;font-size:12px;font-weight:600;text-decoration:none">携程</a>
          <a href="https://www.qunar.com" target="_blank" style="padding:7px 18px;border-radius:8px;border:1px solid var(--border);color:var(--text2);font-size:12px;font-weight:600;text-decoration:none">去哪儿</a>
          <a href="https://flights.ctrip.com" target="_blank" style="padding:7px 18px;border-radius:8px;border:1px solid var(--border);color:var(--text2);font-size:12px;font-weight:600;text-decoration:none">天巡</a>
        </div>
      </div>`;
      return;
    }
    // 联网搜索结果：加提示横幅
    const webBanner = data.web_sourced
      ? `<div style="display:flex;align-items:center;gap:8px;padding:8px 14px;background:rgba(74,111,168,.07);border-radius:8px;border:1px solid rgba(74,111,168,.18);margin-bottom:12px;font-size:12px;color:var(--blue)">
           <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.3"/><path d="M7 4.5a2.5 2.5 0 0 1 0 5M4.5 7h5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>
           <span>以下为<b>实时联网搜索</b>结果，仅供参考，请点击"查看详情"前往官方平台核实购票</span>
         </div>`
      : '';
    box.innerHTML = webBanner + tickets.map(t => renderTicket(t)).join('');
  } catch (e) {
    box.innerHTML = `<div style="text-align:center;padding:24px;color:#e74c3c">
      <div style="font-size:13px;font-weight:700;color:#e74c3c;margin-bottom:8px;letter-spacing:.5px">搜索失败</div>
      <div style="font-weight:600;margin-bottom:4px;display:none">搜索失败</div>
      <div style="font-size:12px;color:var(--text3)">${e.message}</div>
    </div>`;
  }
}

function renderTicket(t) {
  // 联网搜索结果卡片（非结构化数据）
  if (t.type === 'web_info') {
    const hasUrl = t.url && t.url.startsWith('http');
    return `<div class="ticket-card" style="cursor:${hasUrl ? 'pointer' : 'default'}" ${hasUrl ? `onclick="window.open('${t.url}','_blank')"` : ''}>
      <div class="tc-accent" style="background:var(--blue)"></div>
      <div class="tc-body" style="flex-direction:column;gap:8px;padding:14px 16px">
        <div style="display:flex;align-items:center;gap:8px">
          <svg width="13" height="13" viewBox="0 0 14 14" fill="none" style="color:var(--blue);flex-shrink:0"><circle cx="7" cy="7" r="6" stroke="currentColor" stroke-width="1.3"/><path d="M7 4.5a2.5 2.5 0 0 1 0 5M4.5 7h5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>
          <span style="font-size:12.5px;font-weight:700;color:var(--text2);flex:1">${t.title}</span>
          ${hasUrl ? `<span style="font-size:10px;color:var(--blue);font-weight:600;white-space:nowrap">查看详情 →</span>` : ''}
        </div>
        <div style="font-size:12px;color:var(--text3);line-height:1.7">${t.snippet}</div>
        ${hasUrl ? `<div style="font-size:10px;color:var(--text3);opacity:.6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${t.url}</div>` : ''}
      </div>
    </div>`;
  }
  const isF = t.type === 'flight';
  const cabin = isF ? (t.cabin || '经济舱') : (t.seat || '二等座');
  const cabinClass = cabin.includes('商务') || cabin.includes('一等') ? 'biz' : cabin.includes('头等') ? 'first' : '';
  const stops = isF && t.stops > 0 ? `<div class="tc-stop">经停${t.stops}次</div>` : '';
  // 余票标签：分四级显示
  const s = t.seats ?? 999;
  const seatTag = s <= 5
    ? `<span class="tc-seat-tag low">仅剩 ${s} 张</span>`
    : s <= 20
      ? `<span class="tc-seat-tag tight">余票紧张 (${s})</span>`
      : s <= 60
        ? `<span class="tc-seat-tag warn">有票 (${s})</span>`
        : `<span class="tc-seat-tag ok">余票充足</span>`;
  const carrierName = isF ? (t.airline || '') : (t.train_type || '火车');
  const enc = JSON.stringify(t).replace(/"/g, '&quot;');
  return `<div class="ticket-card" onclick="openModal(${enc})">
    <div class="tc-accent${isF ? '' : ' train'}"></div>
    <div class="tc-body">
      <div class="tc-info">
        <div class="tc-carrier">${carrierName}</div>
        <div class="tc-code">${t.code}</div>
        <div class="tc-cabin-badge ${cabinClass}">${cabin}</div>
      </div>
      <div class="tc-route">
        <div class="tc-loc">
          <div class="tc-time">${t.dep}</div>
          <div class="tc-city">${t.from}</div>
        </div>
        <div class="tc-mid">
          <div class="tc-dur">${t.duration}</div>
          <div class="tc-arr-line"></div>
          ${stops}
        </div>
        <div class="tc-loc right">
          <div class="tc-time">${t.arr}${t.arr && t.arr.includes('+') ? '' : ''}</div>
          <div class="tc-city">${t.to}</div>
        </div>
      </div>
      <div class="tc-right">
        <div class="tc-price"><span>¥</span>${t.price.toLocaleString()}</div>
        ${seatTag}
        <button class="bk-btn" onclick="event.stopPropagation();openModal(${enc})">立即预订</button>
      </div>
    </div>
  </div>`;
}

function openModal(ticket) {
  _pendingTicket = ticket;
  const isF = ticket.type === 'flight';
  document.getElementById('modalTicketInfo').innerHTML =
    `<b>${ticket.code}</b> &nbsp;${ticket.from} → ${ticket.to}&nbsp; ${ticket.dep}→${ticket.arr}&nbsp; <b style="color:var(--accent)">¥${ticket.price.toLocaleString()}</b>`;
  document.getElementById('passengerName').value = '';
  document.getElementById('passengerIdNo').value = '';
  document.getElementById('bookingModal').classList.add('open');
}

function closeModal() {
  document.getElementById('bookingModal').classList.remove('open');
  _pendingTicket = null;
}

async function confirmBooking() {
  const name = document.getElementById('passengerName').value.trim();
  if (!name) { toast('请输入乘客姓名', 'err'); return; }
  if (!_pendingTicket) { closeModal(); return; }
  const btn = document.querySelector('.modal-confirm');
  btn.disabled = true; btn.textContent = '预订中…';
  try {
    const r = await fetch(`${API}/booking/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ticket_id: _pendingTicket.id,
        ticket_data: _pendingTicket,
        passenger_name: name,
        id_number: document.getElementById('passengerIdNo').value.trim()
      })
    });
    const data = await r.json();
    if (!r.ok) throw new Error(_extractErrMsg(data));
    closeModal();
    toast(`预订成功！订单号 ${data.order_id}`, 'ok');
  } catch(e) {
    toast(`预订失败：${e.message}`, 'err');
  } finally {
    btn.disabled = false; btn.textContent = '确认预订';
  }
}

// ── Orders pagination + cache (Issue 2) ─────────────────────────
const ORDERS_CACHE_KEY = 'yy_orders_cache';
const ORDERS_TS_KEY    = 'yy_orders_ts';
const ORDERS_CACHE_TTL = 5 * 60 * 1000; // 5 minutes
const ORDERS_PAGE_SIZE = 10;

let _ordersAll    = [];   // full list (from cache or API)
let _ordersOffset = 0;    // how many rendered so far

function _renderOrderCard(o) {
  const t = o.ticket || {};
  const status = { confirmed:'已确认', cancelled:'已取消' }[o.status] || o.status;
  return `<div class="order-card ${o.status}">
    <div class="order-hd">
      <span class="order-st">${status}</span>
      <span style="font-size:11px;color:var(--text3)">${(o.created_at||'').replace('T',' ').slice(0,16)}</span>
    </div>
    <div class="order-route">${t.code||''} &nbsp; ${t.from||''} → ${t.to||''} &nbsp; ${t.dep||''}→${t.arr||''}</div>
    <div class="order-detail">乘客：${o.passenger?.name||'—'} &nbsp;|&nbsp; 订单号：${o.order_id}</div>
    <div class="order-price">¥${(o.total_price||0).toLocaleString()}</div>
  </div>`;
}

function _renderOrdersPage(box) {
  const slice = _ordersAll.slice(_ordersOffset, _ordersOffset + ORDERS_PAGE_SIZE);
  const html  = slice.map(_renderOrderCard).join('');
  if (_ordersOffset === 0) {
    // First render: replace loading indicator, prepend meta bar
    const total = _ordersAll.length;
    const metaBar = `<div id="ordersMeta" style="font-size:12px;color:var(--text3);padding:0 0 12px;display:flex;justify-content:space-between;align-items:center">
      <span>共 <strong>${total}</strong> 条订单</span>
      <button onclick="_refreshOrders()" style="background:none;border:none;color:var(--accent);font-size:12px;cursor:pointer;font-family:inherit">🔄 刷新</button>
    </div>`;
    box.innerHTML = total === 0
      ? '<div style="text-align:center;padding:32px;color:var(--text3)">暂无订单</div>'
      : metaBar + '<div id="ordersCards">' + html + '</div>';
  } else {
    // Append to existing cards container
    const cards = document.getElementById('ordersCards');
    if (cards) cards.insertAdjacentHTML('beforeend', html);
  }
  _ordersOffset += slice.length;

  // Load-more button
  const existing = document.getElementById('ordersLoadMore');
  if (existing) existing.remove();
  if (_ordersOffset < _ordersAll.length) {
    const btn = document.createElement('button');
    btn.id = 'ordersLoadMore';
    btn.textContent = `加载更多（${_ordersAll.length - _ordersOffset} 条剩余）`;
    btn.style.cssText = 'display:block;width:100%;margin-top:12px;padding:10px;border:1.5px dashed var(--border);border-radius:10px;background:none;color:var(--text2);font-size:13px;cursor:pointer;font-family:inherit;transition:all .15s';
    btn.onmouseenter = () => { btn.style.borderColor = 'var(--accent)'; btn.style.color = 'var(--accent)'; };
    btn.onmouseleave = () => { btn.style.borderColor = 'var(--border)'; btn.style.color = 'var(--text2)'; };
    btn.onclick = () => _renderOrdersPage(box);
    box.appendChild(btn);
  } else if (_ordersAll.length > 0) {
    // Range summary at bottom
    const footer = document.createElement('div');
    footer.style.cssText = 'text-align:center;font-size:11px;color:var(--text3);padding:14px 0 4px';
    footer.textContent = `已显示全部 ${_ordersAll.length} 条订单`;
    box.appendChild(footer);
  }
}

async function _fetchOrders(force) {
  if (!force) {
    const ts   = parseInt(localStorage.getItem(ORDERS_TS_KEY) || '0', 10);
    const raw  = localStorage.getItem(ORDERS_CACHE_KEY);
    if (raw && Date.now() - ts < ORDERS_CACHE_TTL) {
      try { return JSON.parse(raw); } catch(e) { /* cache corrupted */ }
    }
  }
  // Fetch all orders (large limit) for client-side pagination
  const r    = await fetch(`${API}/booking/orders?limit=500&offset=0`);
  const data = await r.json();
  const list = data.orders || [];
  localStorage.setItem(ORDERS_CACHE_KEY, JSON.stringify(list));
  localStorage.setItem(ORDERS_TS_KEY, String(Date.now()));
  return list;
}

async function _refreshOrders() {
  const box = document.getElementById('ordersList');
  if (!box) return;
  box.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text3)">刷新中…</div>';
  _ordersOffset = 0;
  try {
    _ordersAll = await _fetchOrders(true);
    _renderOrdersPage(box);
  } catch(e) {
    box.innerHTML = `<div style="text-align:center;padding:24px;color:#e74c3c">刷新失败：${e.message}</div>`;
  }
}

async function showOrders() {
  document.getElementById('bkSearchArea').style.display = 'none';
  document.getElementById('bkOrdersArea').style.display = '';
  ['bkTabFlight','bkTabTrain'].forEach(id => document.getElementById(id)?.classList.remove('active'));
  document.getElementById('bkTabOrders').classList.add('active');
  const box = document.getElementById('ordersList');
  _ordersOffset = 0;

  // Check cache freshness
  const ts  = parseInt(localStorage.getItem(ORDERS_TS_KEY) || '0', 10);
  const raw = localStorage.getItem(ORDERS_CACHE_KEY);
  const cacheAge = Date.now() - ts;
  const cacheOk  = raw && cacheAge < ORDERS_CACHE_TTL;

  if (cacheOk) {
    try {
      _ordersAll = JSON.parse(raw);
      const ageMin = Math.floor(cacheAge / 60000);
      const ageSec = Math.floor((cacheAge % 60000) / 1000);
      const ageStr = ageMin > 0 ? `${ageMin}分${ageSec}秒前` : `${ageSec}秒前`;
      _renderOrdersPage(box);
      // Show cache badge
      const meta = document.getElementById('ordersMeta');
      if (meta) {
        const badge = document.createElement('span');
        badge.style.cssText = 'font-size:10px;color:var(--text3);margin-left:6px';
        badge.textContent = `(缓存 ${ageStr})`;
        const countSpan = meta.querySelector('span');
        if (countSpan) countSpan.appendChild(badge);
      }
      return;
    } catch(e) { /* fall through to fetch */ }
  }

  box.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text3)">加载中…</div>';
  try {
    _ordersAll = await _fetchOrders(false);
    _renderOrdersPage(box);
  } catch(e) {
    box.innerHTML = `<div style="text-align:center;padding:24px;color:#e74c3c">加载失败：${e.message}</div>`;
  }
}

// ── User Profile / History ────────────────────────────────────
const _HIST_KEY = 'voya_history';
const _HIST_MAX = 20;

function _histSave(params) {
  try {
    const arr = JSON.parse(localStorage.getItem(_HIST_KEY) || '[]');
    arr.unshift({ ...params, ts: Date.now(), id: Date.now().toString(36) });
    if (arr.length > _HIST_MAX) arr.length = _HIST_MAX;
    localStorage.setItem(_HIST_KEY, JSON.stringify(arr));
    _histRender();
  } catch(e) {}
}

function _histLoad() {
  try { return JSON.parse(localStorage.getItem(_HIST_KEY) || '[]'); } catch(e) { return []; }
}

function _histRender() {
  const strip = document.getElementById('profileStrip');
  if (!strip) return;
  const arr = _histLoad();
  if (!arr.length) { strip.style.display = 'none'; return; }
  strip.style.display = 'flex';
  const chips = arr.slice(0, 6).map(h => {
    const d = new Date(h.ts);
    const label = `${h.city} · ${d.getMonth()+1}/${d.getDate()}`;
    return `<button class="history-chip" onclick="_histApply(${JSON.stringify(JSON.stringify(h))})">${label}</button>`;
  }).join('');
  const t = I18N[_lang];
  strip.innerHTML = `<span class="profile-label">${t.hist_recent || '最近：'}</span>${chips}<button class="smart-fill-btn" onclick="_histApply(${JSON.stringify(JSON.stringify(arr[0]))})">${t.smart_fill || '✦ 智能填写'}</button>`;
}

function _histApply(jsonStr) {
  try {
    const h = JSON.parse(jsonStr);
    if (!h || !h.city) { toast(_L('暂无历史记录', 'No history yet'), 'err'); return; }
    // 先滚动到表单区域让用户看到填写动画
    const formEl = document.getElementById('destInput');
    if (formEl) formEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setTimeout(() => {
      if (h.city)        fillCityField(document.getElementById('destInput'), h.city);
      if (h.days)        fillField(document.getElementById('daysInput'), String(h.days));
      if (h.budget)      fillField(document.getElementById('budgetInput'), h.budget);
      if (h.group)       { fillField(document.getElementById('groupInput'), h.group); handleGroupChange(); }
      if (h.num_people)  fillField(document.getElementById('numPeopleInput'), String(h.num_people));
      if (h.travel_mode) fillField(document.getElementById('travelModeInput'), h.travel_mode);
      if (h.interests && h.interests.length) {
        document.querySelectorAll('.itag').forEach(t => t.classList.toggle('on', h.interests.includes(t.dataset.i)));
      }
      if (h.city) _autoSwitchTransport(h.city);
      toast(_L(`已填入「${h.city}」历史偏好 ✓`, `Applied: ${h.city} preferences ✓`), 'ok');
    }, 300); // 等滚动完成后再填写，确保高亮动画可见
  } catch(e) { toast(_L('填写失败', 'Fill failed'), 'err'); }
}

// ── Practical Tools ────────────────────────────────────────────
const _EMERGENCY = {
  '巴黎':       { police:'17', ambulance:'15', fire:'18', embassy:'+33-1-49523000', hospital:'Hôtel-Dieu: +33-1-42348234', tip:'EU emergency: 112' },
  '东京':       { police:'110', ambulance:'119', fire:'119', embassy:'+81-3-35002224', hospital:'St.Luke\'s: +81-3-35416151', tip:'English: 03-3501-0110' },
  '纽约':       { police:'911', ambulance:'911', fire:'911', embassy:'+1-212-4785000', hospital:'NY Presbyterian: +1-212-3056000', tip:'Non-emergency: 311' },
  '伦敦':       { police:'999/112', ambulance:'999/112', fire:'999', embassy:'+44-20-74999000', hospital:'UCH: +44-20-73809300', tip:'Non-emergency: 101' },
  '罗马':       { police:'113', ambulance:'118', fire:'115', embassy:'+39-06-8531', hospital:'Policlinico Umberto I: +39-06-49971', tip:'EU: 112' },
  '悉尼':       { police:'000', ambulance:'000', fire:'000', embassy:'+61-2-92686644', hospital:'RPA: +61-2-95156111', tip:'Non-emergency: 131 444' },
  '巴塞罗那':   { police:'091/112', ambulance:'061/112', fire:'080', embassy:'+34-93-4902977', hospital:'Hospital Clinic: +34-93-2275400', tip:'Mossos (regional): 088' },
  '曼谷':       { police:'191', ambulance:'1554', fire:'199', embassy:'+66-2-2457044', hospital:'Bumrungrad: +66-2-0669555', tip:'Tourist police: 1155' },
  '新加坡':     { police:'999', ambulance:'995', fire:'995', embassy:'+65-64180233', hospital:'SGH: +65-62224321', tip:'Non-emergency: 1800-2550000' },
  '首尔':       { police:'112', ambulance:'119', fire:'119', embassy:'+82-2-7382600', hospital:'Asan Medical: +82-2-30103114', tip:'Tourist hotline: 1330' },
  '迪拜':       { police:'999', ambulance:'998', fire:'997', embassy:'+971-4-4069900', hospital:'Dubai Hospital: +971-4-2198787', tip:'Non-emergency: 901' },
  '阿姆斯特丹': { police:'0900-8844', ambulance:'112', fire:'112', embassy:'+31-70-3469515', hospital:'AMC: +31-20-5669111', tip:'EU: 112' },
  '维也纳':     { police:'133', ambulance:'144', fire:'122', embassy:'+43-1-71316', hospital:'AKH Vienna: +43-1-40400', tip:'EU: 112' },
  '布拉格':     { police:'158/112', ambulance:'155', fire:'150', embassy:'+420-233374831', hospital:'Motol Hospital: +420-224433681', tip:'EU: 112' },
  '普吉岛':     { police:'191', ambulance:'1554', fire:'199', embassy:'+66-76-601800', hospital:'Bangkok Hospital Phuket: +66-76-254425', tip:'Tourist police: 1155' },
  '马尔代夫':   { police:'119', ambulance:'102', fire:'118', embassy:'+960-3323015', hospital:'ADK Hospital: +960-3313553', tip:'Coast guard: 191' },
  '伊斯坦布尔': { police:'155', ambulance:'112', fire:'110', embassy:'+90-212-5252438', hospital:'American Hospital: +90-212-3116010', tip:'EU: 112 (emergencies)' },
  '里斯本':     { police:'112', ambulance:'112', fire:'112', embassy:'+351-213928440', hospital:'Hospital de Sta Maria: +351-217805000', tip:'EU: 112' },
  '巴厘岛':     { police:'110', ambulance:'118', fire:'113', embassy:'+62-361-233600', hospital:'BIMC Hospital: +62-361-3000911', tip:'Tourist police: 0361-224111' },
  '大阪':       { police:'110', ambulance:'119', fire:'119', embassy:'+81-6-64453834', hospital:'Osaka City General Hospital: +81-6-66923531', tip:'English: 06-6944-8181' },
  '京都':       { police:'110', ambulance:'119', fire:'119', embassy:'+81-75-7441111', hospital:'Kyoto University Hospital: +81-75-7511111', tip:'Tourist support: 075-752-2670' },
  '开罗':       { police:'122', ambulance:'123', fire:'180', embassy:'+20-2-25321218', hospital:'As-Salam International: +20-2-25247000', tip:'Tourist police: 126' },
  '哥本哈根':   { police:'112', ambulance:'112', fire:'112', embassy:'+45-39276022', hospital:'Rigshospitalet: +45-35454500', tip:'Non-emergency: 114' },
  '苏黎世':     { police:'117', ambulance:'144', fire:'118', embassy:'+41-44-2544400', hospital:'UniversitätsSpital: +41-44-2551111', tip:'EU: 112 also works' },
};

const _RATES = { EUR:7.80, USD:7.20, GBP:9.10, JPY:0.048, KRW:0.0053, THB:1.98, SGD:5.30, AED:1.96, AUD:4.70, HKD:0.92, TWD:0.22, TRY:0.22, CZK:0.31, MVR:4.40, IDR:0.00044, EGP:0.14, DKK:1.04, CHF:8.20, CNY:1.00 };
const _CITY_CURRENCY = { '巴黎':'EUR','伦敦':'GBP','罗马':'EUR','巴塞罗那':'EUR','阿姆斯特丹':'EUR','维也纳':'EUR','布拉格':'CZK','里斯本':'EUR','哥本哈根':'DKK','苏黎世':'CHF','东京':'JPY','大阪':'JPY','京都':'JPY','首尔':'KRW','新加坡':'SGD','曼谷':'THB','普吉岛':'THB','马尔代夫':'MVR','迪拜':'AED','伊斯坦布尔':'TRY','开罗':'EGP','悉尼':'AUD','纽约':'USD','巴厘岛':'IDR','广州':'CNY' };

const _PHRASES = {
  '日语': [
    { zh:'您好', local:'こんにちは', phonetic:'Konnichiwa' },
    { zh:'谢谢', local:'ありがとうございます', phonetic:'Arigatou gozaimasu' },
    { zh:'请问...在哪里？', local:'...はどこですか？', phonetic:'...wa doko desu ka?' },
    { zh:'多少钱？', local:'いくらですか？', phonetic:'Ikura desu ka?' },
    { zh:'帮我叫救护车', local:'救急車を呼んでください', phonetic:'Kyuukyuusha wo yonde kudasai' },
    { zh:'我迷路了', local:'道に迷いました', phonetic:'Michi ni mayoimashita' },
  ],
  '韩语': [
    { zh:'您好', local:'안녕하세요', phonetic:'Annyeonghaseyo' },
    { zh:'谢谢', local:'감사합니다', phonetic:'Gamsahamnida' },
    { zh:'...在哪里？', local:'...어디에 있어요?', phonetic:'...eodi-e isseoyo?' },
    { zh:'多少钱？', local:'얼마에요?', phonetic:'Eolmaeyo?' },
    { zh:'帮我叫救护车', local:'구급차를 불러주세요', phonetic:'Gugeupcha-reul bulleo juseyo' },
    { zh:'我迷路了', local:'길을 잃었어요', phonetic:'Gil-eul ilheosseoyo' },
  ],
  '英语': [
    { zh:'您好', local:'Hello / Good day', phonetic:'' },
    { zh:'谢谢', local:'Thank you very much', phonetic:'' },
    { zh:'...在哪里？', local:'Where is...?', phonetic:'' },
    { zh:'多少钱？', local:'How much is this?', phonetic:'' },
    { zh:'帮我叫救护车', local:'Please call an ambulance!', phonetic:'' },
    { zh:'我迷路了', local:"I'm lost, can you help?", phonetic:'' },
    { zh:'我需要看医生', local:'I need to see a doctor', phonetic:'' },
  ],
  '泰语': [
    { zh:'您好', local:'สวัสดีครับ/ค่ะ', phonetic:'Sawasdee khrap/kha' },
    { zh:'谢谢', local:'ขอบคุณครับ/ค่ะ', phonetic:'Khob khun khrap/kha' },
    { zh:'...在哪里？', local:'...อยู่ที่ไหน?', phonetic:'...yuu thii nai?' },
    { zh:'多少钱？', local:'เท่าไหร่ครับ?', phonetic:'Thao rai khrap?' },
    { zh:'帮我叫救护车', local:'ช่วยเรียกรถพยาบาล', phonetic:'Chuay riak rot phayaban' },
  ],
  '阿拉伯语': [
    { zh:'您好', local:'مرحبا', phonetic:'Marhaba' },
    { zh:'谢谢', local:'شكراً جزيلاً', phonetic:'Shukran jazelan' },
    { zh:'...在哪里？', local:'أين...؟', phonetic:'Ayna...?' },
    { zh:'帮我叫救护车', local:'اتصل بالإسعاف', phonetic:"Ittasil bil-is'aaf" },
  ],
  '法语': [
    { zh:'您好', local:'Bonjour', phonetic:'邦就' },
    { zh:'谢谢', local:'Merci beaucoup', phonetic:'梅尔西博库' },
    { zh:'...在哪里？', local:'Où est...?', phonetic:'乌 艾...?' },
    { zh:'多少钱？', local:'Combien ça coûte?', phonetic:'康比安 萨 库特?' },
    { zh:'帮我叫救护车', local:"Appelez une ambulance !", phonetic:'阿普雷 于纳 安布朗斯' },
    { zh:'我迷路了', local:'Je suis perdu(e)', phonetic:'热 絮伊 培尔迪' },
    { zh:'我需要看医生', local:"J'ai besoin d'un médecin", phonetic:'热 贝索安 当 梅德散' },
    { zh:'我不说法语', local:'Je ne parle pas français', phonetic:'热 纳 帕尔勒 帕 弗朗塞' },
  ],
  '意大利语': [
    { zh:'您好', local:'Buongiorno', phonetic:'布翁 乔尔诺' },
    { zh:'谢谢', local:'Grazie mille', phonetic:'格拉兹耶 米勒' },
    { zh:'...在哪里？', local:'Dov\'è...?', phonetic:'多 维是...?' },
    { zh:'多少钱？', local:'Quanto costa?', phonetic:'夸恩托 科斯塔?' },
    { zh:'帮我叫救护车', local:"Chiami un'ambulanza!", phonetic:'基亚米 乌南布兰扎' },
    { zh:'我迷路了', local:'Mi sono perso/a', phonetic:'米 索诺 佩尔索' },
    { zh:'我需要看医生', local:'Ho bisogno di un medico', phonetic:'奥 比佐尼奥 迪 乌恩 梅迪克' },
    { zh:'我不说意大利语', local:'Non parlo italiano', phonetic:'农 帕尔洛 意大利阿诺' },
  ],
  '西班牙语': [
    { zh:'您好', local:'Buenos días', phonetic:'布埃诺斯 迪阿斯' },
    { zh:'谢谢', local:'Muchas gracias', phonetic:'穆查斯 格拉西阿斯' },
    { zh:'...在哪里？', local:'¿Dónde está...?', phonetic:'栋德 艾斯塔...?' },
    { zh:'多少钱？', local:'¿Cuánto cuesta?', phonetic:'夸恩托 夸斯塔?' },
    { zh:'帮我叫救护车', local:'¡Llame una ambulancia!', phonetic:'亚梅 乌纳 安布兰西亚' },
    { zh:'我迷路了', local:'Estoy perdido/a', phonetic:'艾斯托伊 佩尔迪多' },
  ],
  '葡萄牙语': [
    { zh:'您好', local:'Bom dia', phonetic:'蹦迪亚' },
    { zh:'谢谢', local:'Muito obrigado/a', phonetic:'穆伊图奥布里嘎度' },
    { zh:'...在哪里？', local:'Onde fica...?', phonetic:'翁德菲卡...?' },
    { zh:'多少钱？', local:'Quanto custa?', phonetic:'夸托库斯塔?' },
    { zh:'帮我叫救护车', local:'Chame uma ambulância!', phonetic:'沙梅乌马安布兰西亚' },
    { zh:'我迷路了', local:'Estou perdido/a', phonetic:'艾斯托佩尔迪度' },
  ],
  '印尼语': [
    { zh:'您好', local:'Selamat pagi / siang', phonetic:'斯拉马帕基 / 斯亚昂' },
    { zh:'谢谢', local:'Terima kasih', phonetic:'特里玛卡西' },
    { zh:'...在哪里？', local:'Di mana...?', phonetic:'迪马纳...?' },
    { zh:'多少钱？', local:'Berapa harganya?', phonetic:'贝拉帕哈尔嘎亚?' },
    { zh:'帮我叫救护车', local:'Tolong panggil ambulans!', phonetic:'托隆棒吉尔安布兰斯' },
    { zh:'我迷路了', local:'Saya tersesat', phonetic:'萨亚特色萨特' },
  ],
  '土耳其语': [
    { zh:'您好', local:'Merhaba', phonetic:'梅尔哈巴' },
    { zh:'谢谢', local:'Teşekkür ederim', phonetic:'特谢居尔艾德里姆' },
    { zh:'...在哪里？', local:'...nerede?', phonetic:'...内热德?' },
    { zh:'多少钱？', local:'Bu ne kadar?', phonetic:'布内卡达尔?' },
    { zh:'帮我叫救护车', local:'Ambulans çağırın!', phonetic:'安布兰斯恰尔林' },
    { zh:'我迷路了', local:'Kayboldum', phonetic:'卡伊博尔杜姆' },
  ],
  '荷兰语': [
    { zh:'您好', local:'Goedendag', phonetic:'胡登 达赫' },
    { zh:'谢谢', local:'Dank u wel', phonetic:'当克 于 维尔' },
    { zh:'...在哪里？', local:'Waar is...?', phonetic:'瓦尔 伊斯...?' },
    { zh:'多少钱？', local:'Hoeveel kost het?', phonetic:'胡费尔 科斯特 黑特?' },
    { zh:'帮我叫救护车', local:'Bel een ambulance!', phonetic:'贝尔 恩 安布兰斯' },
    { zh:'我迷路了', local:'Ik ben de weg kwijt', phonetic:'伊克 本 德 维赫 克维特' },
  ],
  '德语': [
    { zh:'您好', local:'Guten Tag', phonetic:'咕腾 塔克' },
    { zh:'谢谢', local:'Vielen Dank', phonetic:'飞伦 当克' },
    { zh:'...在哪里？', local:'Wo ist...?', phonetic:'沃 伊斯特...?' },
    { zh:'多少钱？', local:'Was kostet das?', phonetic:'瓦斯 科斯特 达斯?' },
    { zh:'帮我叫救护车', local:'Rufen Sie einen Krankenwagen!', phonetic:'鲁芬 泽 艾嫩 克兰肯瓦根' },
    { zh:'我迷路了', local:'Ich habe mich verirrt', phonetic:'伊希 哈伯 米希 费里尔特' },
  ],
  '捷克语': [
    { zh:'您好', local:'Dobrý den', phonetic:'多布里典' },
    { zh:'谢谢', local:'Děkuji moc', phonetic:'嘉库伊莫茨' },
    { zh:'...在哪里？', local:'Kde je...?', phonetic:'克德耶...?' },
    { zh:'多少钱？', local:'Kolik to stojí?', phonetic:'科利克托斯托伊?' },
    { zh:'帮我叫救护车', local:'Zavolejte záchranku!', phonetic:'扎沃雷特扎赫兰库' },
    { zh:'我迷路了', local:'Ztratil/a jsem se', phonetic:'兹特拉提尔依森斯' },
  ],
};

const _CITY_LANG = {
  '东京':'日语', '大阪':'日语', '京都':'日语',
  '首尔':'韩语',
  '曼谷':'泰语', '普吉岛':'泰语', '巴厘岛':'印尼语',
  '巴黎':'法语', '罗马':'意大利语',
  '巴塞罗那':'西班牙语', '里斯本':'葡萄牙语',
  '迪拜':'阿拉伯语', '开罗':'阿拉伯语', '伊斯坦布尔':'土耳其语',
  '阿姆斯特丹':'荷兰语', '维也纳':'德语', '苏黎世':'德语', '布拉格':'捷克语',
  '哥本哈根':'英语',  // 丹麦语未收录，丹麦人英语普及率极高
  '伦敦':'英语', '纽约':'英语', '悉尼':'英语',
  '新加坡':'英语', '马尔代夫':'英语',
};

function toggleTools() {
  document.getElementById('toolsPanel').classList.toggle('open');
  // populate city selects
  const cities = Object.keys(_EMERGENCY);
  ['emCitySel','phraseCitySel'].forEach(id => {
    const sel = document.getElementById(id);
    if (sel && sel.options.length <= 1) {
      cities.forEach(c => { const o = document.createElement('option'); o.value = o.textContent = c; sel.appendChild(o); });
    }
  });
  // auto-select current dest city if known
  const dest = document.getElementById('destInput')?.value.trim();
  if (dest && _EMERGENCY[dest]) {
    ['emCitySel','phraseCitySel'].forEach(id => {
      const sel = document.getElementById(id);
      if (sel) { sel.value = dest; }
    });
    renderEmergency(); renderPhrases();
  }
}

function switchTpTab(btn, sectionId) {
  document.querySelectorAll('.tp-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tp-section').forEach(s => s.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(sectionId)?.classList.add('active');
}

function swapCurrency() {
  const f = document.getElementById('cxFrom');
  const t = document.getElementById('cxTo');
  [f.value, t.value] = [t.value, f.value];
  calcCurrency();
}

function calcCurrency() {
  const amt = parseFloat(document.getElementById('cxAmount').value) || 0;
  const from = document.getElementById('cxFrom').value;
  const to = document.getElementById('cxTo').value;
  if (!amt) { document.getElementById('cxResult').textContent = '输入金额开始换算'; return; }
  const _R = {..._RATES, CNY: 1};
  const cny = from === 'CNY' ? amt : amt / (_R[from] || 1);
  const result = to === 'CNY' ? cny : cny * (_R[to] || 1);
  const sym = { EUR:'€', USD:'$', GBP:'£', JPY:'¥', KRW:'₩', SGD:'S$', AED:'AED ', THB:'฿', AUD:'A$', TRY:'₺', HKD:'HK$', CNY:'¥' };
  document.getElementById('cxResult').textContent = `${sym[from]||''}${amt.toLocaleString()} = ${sym[to]||''}${result.toFixed(to==='JPY'||to==='KRW'?0:2)}`;
}

function renderEmergency() {
  const city = document.getElementById('emCitySel')?.value;
  const box = document.getElementById('emContent');
  if (!city || !_EMERGENCY[city]) { if(box) box.innerHTML = '<div style="color:var(--text-light);font-size:12px;text-align:center;padding:20px 0">请选择城市</div>'; return; }
  const e = _EMERGENCY[city];
  box.innerHTML = `
    <div class="em-grid">
      <div class="em-item"><div class="em-label">警察</div><div class="em-val sos">${e.police}</div></div>
      <div class="em-item"><div class="em-label">急救</div><div class="em-val sos">${e.ambulance}</div></div>
      <div class="em-item"><div class="em-label">消防</div><div class="em-val sos">${e.fire}</div></div>
      <div class="em-item"><div class="em-label">当地医院</div><div class="em-val" style="font-size:10px">${e.hospital.split(':')[0]}</div></div>
    </div>
    <div class="em-item" style="margin-top:6px"><div class="em-label">中国驻当地大使馆/领事馆</div><div class="em-val embassy">${e.embassy}</div></div>
    <div class="em-tip">${e.tip}</div>`;
}

function renderPhrases() {
  const city = document.getElementById('phraseCitySel')?.value;
  const box = document.getElementById('phraseList');
  if (!city) { if(box) box.innerHTML = ''; return; }
  const lang = _CITY_LANG[city] || '英语';
  const phrases = _PHRASES[lang] || _PHRASES['英语'];
  box.innerHTML = phrases.map(p => `
    <div class="phrase-item" onclick="copyText('${p.local.replace(/'/g, "\\'")}')">
      <div class="phrase-zh">${p.zh}</div>
      <div class="phrase-local">${p.local}</div>
      ${p.phonetic ? `<div class="phrase-phonetic">${p.phonetic}</div>` : ''}
    </div>`).join('');
}

// ── Export & Share ────────────────────────────────────────────
function shareTrip() {
  const content = document.getElementById('itinContent')?.innerText || '';
  if (!content) { toast('暂无行程内容', 'err'); return; }
  try {
    const dest = document.getElementById('destInput').value;
    const days = document.getElementById('daysInput').value;
    const budget = document.getElementById('budgetInput').value;
    const group = document.getElementById('groupInput').value;
    const num = document.getElementById('numPeopleInput').value;
    const mode = document.getElementById('travelModeInput').value;
    const shareData = btoa(encodeURIComponent(JSON.stringify({ dest, days, budget, group, num, mode })));
    const url = `${location.origin}${location.pathname}#share=${shareData}`;
    navigator.clipboard.writeText(url).then(() => toast('分享链接已复制到剪贴板', 'ok')).catch(() => {
      copyText(content);
      toast('链接复制失败，已复制行程文本', 'ok');
    });
  } catch(e) {
    copyText(content);
    toast('行程内容已复制', 'ok');
  }
}

function printTrip() {
  window.print();
}

function copyText(text) {
  navigator.clipboard.writeText(text).catch(() => {
    const el = document.createElement('textarea');
    el.value = text; document.body.appendChild(el); el.select();
    document.execCommand('copy'); document.body.removeChild(el);
  });
}

// Parse share URL on load
(function() {
  const hash = location.hash;
  if (hash.startsWith('#share=')) {
    try {
      const data = JSON.parse(decodeURIComponent(atob(hash.slice(7))));
      setTimeout(() => {
        if (data.dest) fillCityField(document.getElementById('destInput'), data.dest);
        if (data.days) fillField(document.getElementById('daysInput'), data.days);
        if (data.budget) fillField(document.getElementById('budgetInput'), data.budget);
        if (data.group) { fillField(document.getElementById('groupInput'), data.group); handleGroupChange(); }
        if (data.num) fillField(document.getElementById('numPeopleInput'), data.num);
        if (data.mode) fillField(document.getElementById('travelModeInput'), data.mode);
        toast('已还原分享的行程参数，点击「开始规划」', 'ok');
      }, 500);
    } catch(e) {}
  }
})();

// ── Trip Archive ──────────────────────────────────────────────
const _TRIPS_KEY = 'voya_trips';

function saveTrip() {
  const content = document.getElementById('itinContent')?.innerHTML || '';
  if (!content) { toast('暂无行程内容', 'err'); return; }
  const dest = document.getElementById('destInput')?.value || '';
  const days = document.getElementById('daysInput')?.value || '3';
  const group = document.getElementById('groupInput')?.value || '';
  const budget = document.getElementById('budgetInput')?.value || '';
  const id = Date.now().toString(36);
  const trip = { id, dest, days, group, budget, content, savedAt: Date.now(), rating: 0, note: '' };
  try {
    const trips = JSON.parse(localStorage.getItem(_TRIPS_KEY) || '[]');
    trips.unshift(trip);
    if (trips.length > 30) trips.length = 30;
    localStorage.setItem(_TRIPS_KEY, JSON.stringify(trips));
    toast('行程已保存到「我的旅行」', 'ok');
    _renderMyTrips();
  } catch(e) { toast('保存失败', 'err'); }
}

function _renderMyTrips() {
  let trips;
  try { trips = JSON.parse(localStorage.getItem(_TRIPS_KEY) || '[]'); }
  catch(e) { trips = []; }
  const sec = document.getElementById('myTripsSection');
  const grid = document.getElementById('myTripsGrid');
  if (!sec || !grid) return;
  if (!trips.length) { sec.style.display = 'none'; return; }
  sec.style.display = 'block';
  grid.innerHTML = trips.map(t => {
    const d = new Date(t.savedAt);
    const dateStr = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    const stars = [1,2,3,4,5].map(s => `<span class="tc-star ${s<=t.rating?'on':''}" onclick="rateTripStar('${t.id}',${s});event.stopPropagation()">★</span>`).join('');
    return `<div class="trip-card" onclick="loadTrip('${t.id}')">
      <div class="tc-city">${t.dest}</div>
      <div class="tc-meta">${t.days}天 · ${t.group} · ${t.budget}预算</div>
      <div class="tc-date">保存于 ${dateStr}</div>
      <div class="tc-rating">${stars}</div>
      <textarea class="tc-note" placeholder="添加出行备注..." onclick="event.stopPropagation()"
        onchange="noteTripSave('${t.id}',this.value)">${t.note||''}</textarea>
    </div>`;
  }).join('');
}

function loadTrip(id) {
  try {
    const trips = JSON.parse(localStorage.getItem(_TRIPS_KEY) || '[]');
    const t = trips.find(x => x.id === id);
    if (!t) return;
    document.getElementById('itinContent').innerHTML = t.content;
    document.getElementById('resultSec').classList.add('on');
    document.getElementById('welcomeSec').classList.add('gone');
    document.getElementById('itinHeadTitle').textContent = `${t.dest} ${t.days}日行程（已保存）`;
    toast(`已加载 ${t.dest} 行程`, 'ok');
  } catch(e) {}
}

function rateTripStar(id, rating) {
  try {
    const trips = JSON.parse(localStorage.getItem(_TRIPS_KEY) || '[]');
    const t = trips.find(x => x.id === id);
    if (t) { t.rating = rating; localStorage.setItem(_TRIPS_KEY, JSON.stringify(trips)); _renderMyTrips(); }
  } catch(e) {}
}

function noteTripSave(id, note) {
  try {
    const trips = JSON.parse(localStorage.getItem(_TRIPS_KEY) || '[]');
    const t = trips.find(x => x.id === id);
    if (t) { t.note = note; localStorage.setItem(_TRIPS_KEY, JSON.stringify(trips)); }
  } catch(e) {}
}

function clearTrips() {
  if (!confirm('确认清空所有已保存的旅行记录？')) return;
  localStorage.removeItem(_TRIPS_KEY);
  _renderMyTrips();
}
