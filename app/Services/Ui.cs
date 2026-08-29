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

    public static string T(string lang, string key) =>
        S.TryGetValue(lang, out var d) && d.TryGetValue(key, out var v) ? v
        : S["zh-Hant"].TryGetValue(key, out var f) ? f : key;

    public static string Section(string lang, string? name) =>
        lang == "en" && name is not null && SectionEn.TryGetValue(name.Trim(), out var v) ? v : (name ?? "");
}
