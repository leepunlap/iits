using System.IO;
namespace IitsNews.Services;

/// <summary>
/// Interface strings and section names per language.
///
/// A language selector that translates the ARTICLES but leaves the navigation, headings and
/// buttons in Chinese is not an English site — it is a Chinese site with English content in
/// it. The chrome has to move too.
///
/// Section names come from the old CMS in Chinese only. They are translated here rather than
/// in the database because they are navigation, not content: they are not article text, they
/// are not versioned per article, and an editor renaming a section should not have to think
/// about three rows.
/// </summary>
public static class Ui
{
    private static readonly Dictionary<string, Dictionary<string, string>> S = new()
    {
        ["zh-Hant"] = new()
        {
            ["heroBadge"]="工信部青少年信息技術培訓項目 · 國際窗口", ["heroA"]="培育下一代", ["heroB"]="科技創新者", ["heroP"]="工信學堂（香港）IITS —— 由啟蒙探索到創新實踐，銜接國家級認證與 GBA 競賽平台，把工信部青少年信息技術培訓帶到香港與國際。", ["heroCta1"]="探索課程 →", ["heroCta2"]="聯絡我們", ["heroStat"]="MIIT 認證階梯",
            ["aboutUs"]="關於我們",
            ["programmes"]="網站內容",
            ["partners"]="合作夥伴",
            ["experts"]="專家團隊", ["expertsLede"]="來自清華、北大、復旦、浙大、哈工大等院校的學術顧問。",
            ["orgLine"]="工業和信息化部教育與考試中心 · 青少年信息技術培養工程香港分站", ["sitemap"]="網站導覽", ["assessments"]="銜接測評", ["programmes"]="業務體系", ["news"]="新聞資訊", ["assessLede"]="五大測評軌道與工信部證書體系銜接，香港考生可就近報考。", ["enter"]="點擊進入 →", ["more"]="更多 →", ["heroKicker"]="HONG KONG · SCIENCE PARK", ["heroTitle"]="青少年信息技術培養工程<br />香港分站", ["heroLede"]="課程體系、師資培訓、賽事、研學與銜接測評，一體貫通內地與香港。", ["ftWeb"]="官方網站：www.ycltesthk.com", ["ftTel"]="業務合作：+852 2524 8248", ["ftMail"]="投訴郵箱：youth.itt@gmail.com", ["ftHours"]="服務時間：工作日 上午9:00~11:30，下午14:00~17:30", ["ftAddr"]="香港科學園科技大道西2號2W大樓3樓24室",
            ["latest"]="最新消息", ["all"]="全部", ["home"]="首頁", ["viewAll"]="查看全部",
            ["student"]="學生專區", ["teacher"]="教師專區", ["mainSite"]="主網站",
            ["admin"]="內容管理", ["sections"]="專區", ["newest"]="最新",
            ["noContent"]="這個分類目前沒有已發布的內容。", ["notFound"]="找不到內容。",
            ["nothingPublished"]="尚無已發布的內容。", ["untitled"]="（無標題）",
            ["tagline"]="由啟蒙探索到創新實踐，銜接國家級認證與大灣區競賽平台。",
            ["eyebrow"]="工信部青少年信息技術培訓項目 · 國際窗口",
            ["siteName"]="工信學堂（香港）", ["allNews"]="全部已發布內容",
            ["items"]="篇內容", ["subcats"]="個子分類", ["holding"]="目前收錄",
            ["staging"]="STAGING · 合併預覽",
        },
        ["zh-Hans"] = new()
        {
            ["heroBadge"]="工信部青少年信息技术培训项目 · 国际窗口", ["heroA"]="培育下一代", ["heroB"]="科技创新者", ["heroP"]="工信学堂（香港）IITS —— 由启蒙探索到创新实践，衔接国家级认证与 GBA 竞赛平台，把工信部青少年信息技术培训带到香港与国际。", ["heroCta1"]="探索课程 →", ["heroCta2"]="联络我们", ["heroStat"]="MIIT 认证阶梯",
            ["aboutUs"]="关于我们",
            ["programmes"]="网站内容",
            ["partners"]="合作伙伴",
            ["experts"]="专家团队", ["expertsLede"]="来自清华、北大、复旦、浙大、哈工大等院校的学术顾问。",
            ["orgLine"]="工业和信息化部教育与考试中心 · 青少年信息技术培养工程香港分站", ["sitemap"]="网站导览", ["assessments"]="衔接测评", ["programmes"]="业务体系", ["news"]="新闻资讯", ["assessLede"]="五大测评轨道与工信部证书体系衔接，香港考生可就近报考。", ["enter"]="点击进入 →", ["more"]="更多 →", ["heroKicker"]="HONG KONG · SCIENCE PARK", ["heroTitle"]="青少年信息技术培养工程<br />香港分站", ["heroLede"]="课程体系、师资培训、赛事、研学与衔接测评，一体贯通内地与香港。", ["ftWeb"]="官方网站：www.ycltesthk.com", ["ftTel"]="业务合作：+852 2524 8248", ["ftMail"]="投诉邮箱：youth.itt@gmail.com", ["ftHours"]="服务时间：工作日 上午9:00~11:30，下午14:00~17:30", ["ftAddr"]="香港科学园科技大道西2号2W大楼3楼24室",
            ["latest"]="最新消息", ["all"]="全部", ["home"]="首页", ["viewAll"]="查看全部",
            ["student"]="学生专区", ["teacher"]="教师专区", ["mainSite"]="主网站",
            ["admin"]="内容管理", ["sections"]="专区", ["newest"]="最新",
            ["noContent"]="这个分类目前没有已发布的内容。", ["notFound"]="找不到内容。",
            ["nothingPublished"]="尚无已发布的内容。", ["untitled"]="（无标题）",
            ["tagline"]="由启蒙探索到创新实践，衔接国家级认证与大湾区竞赛平台。",
            ["eyebrow"]="工信部青少年信息技术培训项目 · 国际窗口",
            ["siteName"]="工信学堂（香港）", ["allNews"]="全部已发布内容",
            ["items"]="篇内容", ["subcats"]="个子分类", ["holding"]="目前收录",
            ["staging"]="STAGING · 合并预览",
        },
        ["en"] = new()
        {
            ["heroBadge"]="MIIT Youth IT Training Project · International Window", ["heroA"]="Educating the next", ["heroB"]="generation of innovators", ["heroP"]="IITS Hong Kong — from first discovery to applied innovation, linked to national certification and the Greater Bay Area competition circuit, bringing MIIT youth IT training to Hong Kong and beyond.", ["heroCta1"]="Explore programmes →", ["heroCta2"]="Contact us", ["heroStat"]="MIIT certification levels",
            ["aboutUs"]="About",
            ["programmes"]="Sections",
            ["partners"]="Partners",
            ["experts"]="Experts", ["expertsLede"]="Academic advisers from Tsinghua, Peking, Fudan, Zhejiang, Harbin Institute of Technology and other universities.",
            ["orgLine"]="MIIT Education & Examination Center · Youth IT Training Project, Hong Kong Branch", ["sitemap"]="Site map", ["assessments"]="Assessments", ["programmes"]="Programmes", ["news"]="News", ["assessLede"]="Five assessment tracks aligned to the MIIT certification framework, sittable in Hong Kong.", ["enter"]="Enter →", ["more"]="More →", ["heroKicker"]="HONG KONG · SCIENCE PARK", ["heroTitle"]="Youth IT Training Project<br />Hong Kong Branch", ["heroLede"]="Curriculum, teacher training, competitions, study tours and assessment — one pathway across the Mainland and Hong Kong.", ["ftWeb"]="Website: www.ycltesthk.com", ["ftTel"]="Enquiries: +852 2524 8248", ["ftMail"]="Email: youth.itt@gmail.com", ["ftHours"]="Hours: Weekdays 09:00–11:30, 14:00–17:30", ["ftAddr"]="Room 24, 3/F, Building 2W, 2 Science Park West Avenue, Hong Kong Science Park",
            ["latest"]="Latest", ["all"]="All", ["home"]="Home", ["viewAll"]="View all",
            ["student"]="Student Area", ["teacher"]="Teacher Area", ["mainSite"]="Main site",
            ["admin"]="Content admin", ["sections"]="Areas", ["newest"]="Latest",
            ["noContent"]="Nothing has been published in this section yet.",
            ["notFound"]="Not found.", ["nothingPublished"]="Nothing published yet.",
            ["untitled"]="(untitled)",
            ["tagline"]="From first discovery to applied innovation — linked to national certification and the Greater Bay Area competition circuit.",
            ["eyebrow"]="MIIT Youth IT Training Project · International Window",
            ["siteName"]="Industry and Information Technology Class (Hong Kong)",
            ["allNews"]="All published articles",
            ["items"]="articles", ["subcats"]="sub-sections", ["holding"]="Currently holding",
            ["staging"]="STAGING · MERGE PREVIEW",
        },
    };

    /// <summary>Section names from the old CMS, in English. Anything not listed falls back
    /// to the Chinese name — visibly untranslated rather than silently wrong.</summary>
    private static readonly Dictionary<string, string> SectionEn = new()
    {
        ["新聞中心"]="News Centre", ["新闻中心"]="News Centre",
        ["新聞資訊"]="News", ["新闻资讯"]="News",
        ["AI科创中心"]="AI Innovation Centre", ["AI科創中心"]="AI Innovation Centre",
        ["研學活動"]="Study Tours", ["研学活动"]="Study Tours",
        ["師資培訓"]="Teacher Training", ["师资培训"]="Teacher Training",
        ["落地案例"]="Case Studies", ["落地案例 "]="Case Studies",
        ["賽事體系"]="Competitions", ["赛事体系"]="Competitions",
        ["課程體系"]="Curriculum", ["课程体系"]="Curriculum",
        ["關於我们"]="About", ["关于我们"]="About", ["關於我們"]="About",
        ["銜接測評"]="Assessment", ["衔接测评"]="Assessment",
        ["媒體電視"]="Media & TV", ["媒体电视"]="Media & TV",
        ["通知公告"]="Notices", ["政策法规"]="Policy", ["政策法規"]="Policy",
        ["地方动态"]="Regional", ["地方動態"]="Regional",
        ["专家团队"]="Experts", ["專家團隊"]="Experts",
        ["合作单位"]="Partners", ["合作單位"]="Partners",
        ["圖片集"]="Gallery", ["图片集"]="Gallery",
        ["中國香港"]="Hong Kong, China", ["中国香港"]="Hong Kong, China",
        ["青少年人工智能技术水平测试"]="YAI · AI Technology Test",
        ["青少年人工智能编程水平测试"]="YCL · AI Programming Test",
        ["青少年无屏编程水平测试"]="ECL · Screen-free Programming Test",
        ["青少年科技素养水平测试"]="SCL · Technology Literacy Test",
        ["青少年无人机技术水平测试"]="YUL · Drone Technology Test",
    };

    /// <summary>Section names arrive from the old CMS in ONE script — mostly Simplified —
    /// so a Traditional reader was seeing 简体 navigation. Generated with the same s2hk
    /// pipeline and protected-name rules as the article text (see i18n/TRANSLATION.md),
    /// then frozen here: navigation should not depend on a converter at request time.</summary>
    private static readonly Dictionary<string, (string Hant, string Hans)> SectionScript = new()
    {
        ["AI互動魔方"] = ("AI互動魔方", "AI互动魔方"),
        ["AI科创中心"] = ("AI科創中心", "AI科创中心"),
        ["YAI测评"] = ("YAI測評", "YAI测评"),
        ["下载Scratch3"] = ("下載Scratch3", "下载Scratch3"),
        ["专家团队"] = ("專家團隊", "专家团队"),
        ["中國內地"] = ("中國內地", "中国内地"),
        ["中國香港"] = ("中國香港", "中国香港"),
        ["主办单位"] = ("主辦單位", "主办单位"),
        ["二维码"] = ("二維碼", "二维码"),
        ["人才培养基地"] = ("人才培養基地", "人才培养基地"),
        ["关于器材"] = ("關於器材", "关于器材"),
        ["关于考评"] = ("關於考評", "关于考评"),
        ["关于证书"] = ("關於證書", "关于证书"),
        ["北京研學"] = ("北京研學", "北京研学"),
        ["友情链接"] = ("友情鏈接", "友情链接"),
        ["右侧悬浮"] = ("右側懸浮", "右侧悬浮"),
        ["合作单位"] = ("合作單位", "合作单位"),
        ["圖片集"] = ("圖片集", "图片集"),
        ["在线课程"] = ("在線課程", "在线课程"),
        ["地方动态"] = ("地方動態", "地方动态"),
        ["培训中心查询"] = ("培訓中心查詢", "培训中心查询"),
        ["培训合作"] = ("培訓合作", "培训合作"),
        ["培训报名"] = ("培訓報名", "培训报名"),
        ["培训简介"] = ("培訓簡介", "培训简介"),
        ["基本简介"] = ("基本簡介", "基本简介"),
        ["大灣區研學"] = ("大灣區研學", "大湾区研学"),
        ["媒體電視"] = ("媒體電視", "媒体电视"),
        ["学习教材"] = ("學習教材", "学习教材"),
        ["專家團隊"] = ("專家團隊", "专家团队"),
        ["工信部證書"] = ("工信部證書", "工信部证书"),
        ["师资培训"] = ("師資培訓", "师资培训"),
        ["师资证书查询"] = ("師資證書查詢", "师资证书查询"),
        ["師資培訓"] = ("師資培訓", "师资培训"),
        ["底部信息"] = ("底部資訊", "底部信息"),
        ["底部导航"] = ("底部導航", "底部导航"),
        ["建設AI中心"] = ("建設AI中心", "建设AI中心"),
        ["手机首页内容"] = ("手機首頁內容", "手机首页内容"),
        ["报名入口"] = ("報名入口", "报名入口"),
        ["授牌體系"] = ("授牌體系", "授牌体系"),
        ["推荐器材"] = ("推薦器材", "推荐器材"),
        ["收费标准"] = ("收費標準", "收费标准"),
        ["政策法规"] = ("政策法規", "政策法规"),
        ["教材图书"] = ("教材圖書", "教材图书"),
        ["教材资料"] = ("教材資料", "教材资料"),
        ["新聞中心"] = ("新聞中心", "新闻中心"),
        ["新聞資訊"] = ("新聞資訊", "新闻资讯"),
        ["新賽項"] = ("新賽項", "新赛项"),
        ["模拟题库"] = ("模擬題庫", "模拟题库"),
        ["注册"] = ("註冊", "注册"),
        ["活动报名"] = ("活動報名", "活动报名"),
        ["海外研學"] = ("海外研學", "海外研学"),
        ["測評體系"] = ("測評體系", "测评体系"),
        ["無屏編程"] = ("無屏編程", "无屏编程"),
        ["登录"] = ("登錄", "登录"),
        ["研學活動"] = ("研學活動", "研学活动"),
        ["簡介"] = ("簡介", "简介"),
        ["考生成绩查询"] = ("考生成績查詢", "考生成绩查询"),
        ["考生证书查询"] = ("考生證書查詢", "考生证书查询"),
        ["考评合作"] = ("考評合作", "考评合作"),
        ["考评大纲"] = ("考評大綱", "考评大纲"),
        ["考评指南"] = ("考評指南", "考评指南"),
        ["考评服务中心"] = ("考評服務中心", "考评服务中心"),
        ["考评简介"] = ("考評簡介", "考评简介"),
        ["考评系统点击进入"] = ("考評系統點擊進入", "考评系统点击进入"),
        ["考评计划"] = ("考評計劃", "考评计划"),
        ["联系我们"] = ("聯繫我們", "联系我们"),
        ["課程體系"] = ("課程體系", "课程体系"),
        ["试题下载"] = ("試題下載", "试题下载"),
        ["賽事體系"] = ("賽事體系", "赛事体系"),
        ["轮播图下方"] = ("輪播圖下方", "轮播图下方"),
        ["近期培训"] = ("近期培訓", "近期培训"),
        ["銜接測評"] = ("銜接測評", "衔接测评"),
        ["關於我们"] = ("關於我們", "关于我们"),
        ["防伪查询"] = ("防偽查詢", "防伪查询"),
        ["青少年人工智能技术水平测试"] = ("青少年人工智能技術水平測試", "青少年人工智能技术水平测试"),
        ["青少年人工智能编程水平测试"] = ("青少年人工智能編程水平測試", "青少年人工智能编程水平测试"),
        ["青少年无人机技术水平测试"] = ("青少年無人機技術水平測試", "青少年无人机技术水平测试"),
        ["青少年无屏编程水平测试"] = ("青少年無屏編程水平測試", "青少年无屏编程水平测试"),
        ["青少年科技素养水平测试"] = ("青少年科技素養水平測試", "青少年科技素养水平测试"),
        ["项目开展单位"] = ("項目開展單位", "项目开展单位"),
        ["首頁"] = ("首頁", "首页"),
        ["首页内容"] = ("首頁內容", "首页内容"),
        ["香港研學"] = ("香港研學", "香港研学"),
    };

    /// <summary>Assessment track names split into two lines at the natural break: the
    /// qualifier stays on line one, the test's own name drops to line two. Held as an
    /// explicit pair rather than letting the box wrap, because CSS breaks wherever the
    /// column happens to end and would split 水平測試 or "Technology Test" mid-phrase.</summary>
    private static readonly Dictionary<string, Dictionary<string, (string A, string B)>> TrackLines = new()
    {
        ["zh-Hant"] = new()
        {
            ["YAI"] = ("青少年人工智能", "技術水平測試"),
            ["YCL"] = ("青少年人工智能", "編程水平測試"),
            ["ECL"] = ("青少年無屏",     "編程水平測試"),
            ["SCL"] = ("青少年科技",     "素養水平測試"),
            ["YUL"] = ("青少年無人機",   "技術水平測試"),
        },
        ["zh-Hans"] = new()
        {
            ["YAI"] = ("青少年人工智能", "技术水平测试"),
            ["YCL"] = ("青少年人工智能", "编程水平测试"),
            ["ECL"] = ("青少年无屏",     "编程水平测试"),
            ["SCL"] = ("青少年科技",     "素养水平测试"),
            ["YUL"] = ("青少年无人机",   "技术水平测试"),
        },
        ["en"] = new()
        {
            ["YAI"] = ("AI",          "Technology Test"),
            ["YCL"] = ("AI",          "Programming Test"),
            ["ECL"] = ("Screen-free", "Programming Test"),
            ["SCL"] = ("Technology",  "Literacy Test"),
            ["YUL"] = ("Drone",       "Technology Test"),
        },
    };

    /// <summary>Cache-busting stamp for a static asset.
    ///
    /// /assets/ is served with max-age=604800, so replacing a file in place leaves everyone
    /// who already visited holding the old one for a WEEK — which is exactly what happened
    /// when the track artwork went greyscale and kept rendering in colour. Appending the
    /// file's last-write time makes the URL change whenever the bytes do, so the long cache
    /// stays (it is the right setting) but never serves something stale.</summary>
    private static readonly Dictionary<string, string> _stamp = new();
    public static string V(string webPath)
    {
        if (_stamp.TryGetValue(webPath, out var v)) return v;
        var full = Path.Combine("/var/www/iits-staging", webPath.TrimStart('/'));
        try { v = "?v=" + File.GetLastWriteTimeUtc(full).Ticks.ToString("x"); }
        catch { v = ""; }
        _stamp[webPath] = v;
        return v;
    }

    public static (string A, string B) TrackName(string lang, string code)
    {
        var l = TrackLines.ContainsKey(lang) ? lang : "zh-Hant";
        return TrackLines[l].TryGetValue(code, out var v) ? v : (code, "");
    }

    public static string T(string lang, string key) =>
        S.TryGetValue(lang, out var d) && d.TryGetValue(key, out var v) ? v
        : S["zh-Hant"].TryGetValue(key, out var f) ? f : key;

    public static string Section(string lang, string? name)
    {
        if (name is null) return "";
        var n = name.Trim();
        if (lang == "en" && SectionEn.TryGetValue(n, out var en)) return en;
        if (SectionScript.TryGetValue(n, out var sc))
            return lang == "zh-Hans" ? sc.Hans : lang == "zh-Hant" ? sc.Hant : n;
        return n;   // unknown name: shown as-is rather than silently mangled
    }
}
