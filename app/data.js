// === 二次元 Top10 选品数据（来自 Linkfox 1688 货源 + 闲鱼文案优化器）===
window.SHOPS = [
  { id: "youzan",   name: "有赞",       color: "#ff5b5b", icon: "👍" },
  { id: "weidian",  name: "微店",       color: "#ff3b30", icon: "店" },
  { id: "taote",    name: "淘特",       color: "#ff6a00", icon: "淘" },
  { id: "wxshop",   name: "微信小商店", color: "#07c160", icon: "微" },
  { id: "alipay",   name: "支付宝",     color: "#1677ff", icon: "支" },
  { id: "suning",   name: "苏宁",       color: "#ffa500", icon: "苏" },
  { id: "xianyu",   name: "闲鱼",       color: "#ffcd00", icon: "闲" },
  { id: "eleme",    name: "饿了么",     color: "#0099ff", icon: "饿" },
  { id: "dudian",   name: "度小店",     color: "#2932e1", icon: "度" },
  { id: "weiqing",  name: "微擎",       color: "#10aeff", icon: "擎" },
  { id: "weixiang", name: "微购相册",   color: "#7ed321", icon: "册" },
  { id: "qunjielong", name: "群接龙",   color: "#b8b8b8", icon: "龙" }
];

window.PRICING = {
  versions: [
    { id: "free", name: "免费版", color: "#aaa" },
    { id: "pro",  name: "高级版", color: "#ff8800" },
    { id: "best", name: "出单宝版", color: "#ff5000", hot: true }
  ],
  features: [
    { cat: "出单宝专享", rows: [
      { name: "专属客服代绑店", v: { free: false, pro: false, best: true }, d: "专属客服绑定,新手0门槛" },
      { name: "下游首月接口免费(首7店铺)", v: { free: false, pro: false, best: true } },
      { name: "7天免费私享货源", v: { free: false, pro: false, best: true } },
      { name: "7天不出单保障", v: { free: false, pro: false, best: true } },
      { name: "分销专属消息APP", v: { free: false, pro: false, best: true } },
      { name: "售后服务仓", v: { free: false, pro: true, best: true } }
    ]},
    { cat: "AI小工具 - 加商品曝光", rows: [
      { name: "AI标题违规词过滤", v: { free: false, pro: true, best: true } },
      { name: "AI智能标题优化", v: { free: false, pro: true, best: true } },
      { name: "AI白底图", v: { free: false, pro: true, best: true } },
      { name: "AI商品违规词过滤", v: { free: false, pro: true, best: true } },
      { name: "AI主图背景图优化", v: { free: false, pro: true, best: true } },
      { name: "AI商品视频生成", v: { free: false, pro: true, best: true } },
      { name: "AI小红书笔记", v: { free: false, pro: true, best: true } }
    ]},
    { cat: "店铺管理", rows: [
      { name: "支持用户多渠道、多店铺", v: { free: true, pro: true, best: true }, d: "淘宝/拼多多/抖音/闲鱼..." }
    ]},
    { cat: "铺货", rows: [
      { name: "智能出单货源推荐", v: { free: false, pro: true, best: true } },
      { name: "库存管理", v: { free: false, pro: true, best: true } },
      { name: "智能出单计划", v: { free: true, pro: true, best: true } },
      { name: "1688官方供应链", v: { free: true, pro: true, best: true } },
      { name: "1688低价货源推荐/搜索", v: { free: true, pro: true, best: true } },
      { name: "链接铺货/铺货记录", v: { free: true, pro: true, best: true } },
      { name: "商品信息修改", v: { free: true, pro: true, best: true } },
      { name: "类目匹配", v: { free: true, pro: true, best: true } }
    ]},
    { cat: "回流采购", rows: [
      { name: "订单自动备注", v: { free: false, pro: true, best: true } },
      { name: "订单管理", v: { free: true, pro: true, best: true } },
      { name: "自动回流、订单同步", v: { free: true, pro: true, best: true } },
      { name: "密文下单、同款提供", v: { free: true, pro: true, best: true } },
      { name: "批量支付", v: { free: true, pro: true, best: true } },
      { name: "免密支付", v: { free: true, pro: true, best: true } }
    ]},
    { cat: "售后服务", rows: [
      { name: "发货前自动售后", v: { free: true, pro: true, best: true } },
      { name: "发货后半自动售后", v: { free: false, pro: true, best: true } },
      { name: "发货后全自动售后", v: { free: false, pro: false, best: true } }
    ]},
    { cat: "专属服务", rows: [
      { name: "出单必听课", v: { free: false, pro: true, best: true } },
      { name: "用户教程", v: { free: true, pro: true, best: true } },
      { name: "人工客服", v: { free: true, pro: true, best: true } }
    ]}
  ]
};

window.MOCK_ORDERS = [
  { shop: "闲鱼-二次元铺", buyer: "小丸子**987", addr: "北京市****1号",
    title: "空崎日奈蔚蓝档案手办", spec: "晚礼服款 · 1件", price: 105.9, profit: 55.9, time: "2026-08-12 09:30", status: "待支付" },
  { shop: "闲鱼-二次元铺", buyer: "芝麻馅**", addr: "上海市****",
    title: "尘白禁区动漫福袋", spec: "大礼包 · 1件", price: 24.8, profit: 11.8, time: "2026-08-12 10:12", status: "待发货" },
  { shop: "闲鱼-二次元铺", buyer: "兔兔酱**", addr: "广州市****",
    title: "百忍佩恩火影手办", spec: "共鸣款 · 1件", price: 21.9, profit: 10.0, time: "2026-08-12 11:05", status: "待发货" }
];

// ===== 商家入驻 / 分销员 数据 =====
window.MERCHANT = {
  role: null,            // 'supply'(货源商家) | 'sell'(分销商家) | null
  status: 'none',        // none | reviewing | passed | rejected
  name: '',
  phone: '137****8442',
  shop: '闲鱼-二次元铺',
  joinedAt: '',
  level: 'Lv.3 团队长',
  teamSize: 28,
  teamSales: 18640,
  teamCommission: 2236.8
};

window.INVITE = {
  code: 'LY-XY-8842',
  posterTitle: '邀请你成为「灵鱼」分销员',
  posterSub: '0 门槛 · 一件代发 · 出单自动结算',
  commission1: 12,       // 一级佣金 %
  commission2: 5,        // 二级佣金 %
  totalInvited: 28,
  totalOrders: 156,
  totalSales: 18640,
  totalCommission: 2236.8
};

window.DISTRIBUTORS = [
  { id:'d1', name:'小鹿同学', avatar:'🦌', invited:6, orders:42, sales:5230, commission:628, level:'Lv.2', status:'active', joinedAt:'2026-07-02', lastOrder:'2026-08-11 21:30' },
  { id:'d2', name:'阿喵酱', avatar:'🐱', invited:3, orders:31, sales:3980, commission:477, level:'Lv.2', status:'active', joinedAt:'2026-07-10', lastOrder:'2026-08-12 09:12' },
  { id:'d3', name:'二次元老粉', avatar:'🎮', invited:0, orders:27, sales:3120, commission:374, level:'Lv.1', status:'active', joinedAt:'2026-07-15', lastOrder:'2026-08-10 18:45' },
  { id:'d4', name:'闲鱼小铺', avatar:'🏪', invited:2, orders:19, sales:2260, commission:271, level:'Lv.1', status:'active', joinedAt:'2026-07-20', lastOrder:'2026-08-09 14:03' },
  { id:'d5', name:'手办控阿杰', avatar:'🧸', invited:1, orders:15, sales:1980, commission:238, level:'Lv.1', status:'pending', joinedAt:'2026-08-01', lastOrder:'2026-08-08 20:11' },
  { id:'d6', name:'追番少女', avatar:'🌸', invited:4, orders:22, sales:2640, commission:317, level:'Lv.2', status:'active', joinedAt:'2026-07-25', lastOrder:'2026-08-12 08:50' }
];
