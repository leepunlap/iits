namespace IitsNews.Services;

public record SubDef(string Key, string Hant, string Hans, string En);
public record CatDef(string Key, string Hant, string Hans, string En, SubDef[] Subs);

/// <summary>
/// The site's five categories, replacing the old CMS's fifty sections.
///
/// Defined in code rather than in the database because a taxonomy is structure, not content:
/// it changes when someone decides it should, not when an editor writes an article. Keeping
/// it here means the navigation cannot drift as rows are added, and the labels stay
/// translated in all three languages without a migration.
/// </summary>
public static class Taxonomy
{
    public static readonly CatDef[] All =
    {
        new("tests", "測評", "测评", "Assessments", new SubDef[]
        {
            new("YAI", "人工智能技術", "人工智能技术", "AI Technology"),
            new("YCL", "人工智能編程", "人工智能编程", "AI Programming"),
            new("ECL", "無屏編程",     "无屏编程",     "Screen-free Programming"),
            new("SCL", "科技素養",     "科技素养",     "Technology Literacy"),
            new("YUL", "無人機技術",   "无人机技术",   "Drone Technology"),
            new("overview", "測評總覽", "测评总览", "About the Assessments"),
        }),
        new("courses", "課程", "课程", "Programmes", new SubDef[]
        {
            new("series",  "課程系列", "课程系列", "Course Series"),
            new("teacher", "師資培訓", "师资培训", "Teacher Training"),
            new("study",   "研學活動", "研学活动", "Study Tours"),
            new("contest", "競賽",     "竞赛",     "Competitions"),
        }),
        new("news", "消息", "消息", "News", new SubDef[]
        {
            new("news",   "最新消息", "最新消息", "Latest"),
            new("policy", "政策法規", "政策法规", "Policy"),
        }),
        // Experts sits UNDER About rather than beside it. Twelve advisers are evidence about
        // who the organisation is, which is what About is for — as a top-level peer of
        // Assessments and Programmes it claimed more of the nav than a roster warrants.
        new("about", "關於我們", "关于我们", "About", new SubDef[]
        {
            new("overview",  "簡介",     "简介",     "Overview"),
            new("experts",   "專家團隊", "专家团队", "Experts"),
            new("partners",  "合作夥伴", "合作伙伴", "Partners"),
        }),
    };

    public static CatDef? Cat(string? key) => All.FirstOrDefault(c => c.Key == key);
    public static SubDef? Sub(string? cat, string? sub) => Cat(cat)?.Subs.FirstOrDefault(s => s.Key == sub);

    public static string Name(CatDef c, string lang) => lang switch
        { "zh-Hans" => c.Hans, "en" => c.En, _ => c.Hant };
    public static string Name(SubDef s, string lang) => lang switch
        { "zh-Hans" => s.Hans, "en" => s.En, _ => s.Hant };

    /// <summary>Category a track code belongs to, for linking an assessment tile.</summary>
    public static string TrackHref(string code, string lang) => $"/c/tests/{code}?lang={lang}";
}
