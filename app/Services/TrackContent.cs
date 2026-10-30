using System.Linq;

namespace IitsNews.Services;

public record Fact(string LabelHant, string LabelHans, string LabelEn,
                   string ValHant, string ValHans, string ValEn)
{
    public string Label(string l) => l == "zh-Hans" ? LabelHans : l == "en" ? LabelEn : LabelHant;
    public string Val(string l)   => l == "zh-Hans" ? ValHans   : l == "en" ? ValEn   : ValHant;
}
public record TrackPage(
    string Code, string BlurbHant, string BlurbHans, string BlurbEn,
    Fact[] Facts, string[] Dates, string FeesHant, string FeesHans, string FeesEn)
{
    public string Blurb(string l) => l == "zh-Hans" ? BlurbHans : l == "en" ? BlurbEn : BlurbHant;
    public string Fees(string l)  => l == "zh-Hans" ? FeesHans  : l == "en" ? FeesEn  : FeesHant;

    /// <summary>
    /// Dates are held once, in the source form "3月21、22日", and rendered per language.
    /// They used to be printed raw, so the English fact sheet read
    /// "National exam dates  3月21、22日 · 6月13、14日" — English label, Chinese value.
    /// </summary>
    public string DateLine(string l)
    {
        if (l != "en") return string.Join(" · ", Dates);
        var months = new[]{ "Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec" };
        var outp = Dates.Select(d =>
        {
            var m = System.Text.RegularExpressions.Regex.Match(d, @"^(\d+)月(.+)日$");
            if (!m.Success) return d;
            var mon = months[int.Parse(m.Groups[1].Value) - 1];
            var days = m.Groups[2].Value.Replace("、", "–");
            return $"{days} {mon}";
        });
        return string.Join(" · ", outp);
    }
}

/// <summary>
/// Full detail for each assessment track, digested from the exam pages on the parent site
/// and written out in three languages.
///
/// One caveat recorded here rather than buried: the parent site's own pages and the live
/// iits.giftedintl.com home page DISAGREE on YAI's ceiling — 啟蒙級 + 1–8 on the exam page,
/// 啟蒙級 + 1–10 on the home page. The exam page is used here because it is the operational
/// source, but the discrepancy is real and worth resolving with the issuing body rather than
/// quietly picking one.
///
/// The Fees and Dates fields are the MAINLAND schedule and are NO LONGER RENDERED. A Hong
/// Kong candidate registers through this branch, so a national RMB price and a national
/// sitting calendar are not their price or their dates; the assessment pages now say
/// "contact us for information" instead. The values are kept here as source — they are
/// accurate for the mainland programme — but must not be shown as HK figures.
/// </summary>
public static class TrackContent
{
    public static readonly Dictionary<string, TrackPage> All = new()
    {
        ["YAI"] = new("YAI",
            "考查學生在人工智能關鍵技術、產品、服務及應用方面的能力水平，適用於小學、初中、高中的青少年。體系包括啟蒙級與 1 至 8 級，難度逐級提升。",
            "考查学生在人工智能关键技术、产品、服务及应用方面的能力水平，适用于小学、初中、高中的青少年。体系包括启蒙级与 1 至 8 级，难度逐级提升。",
            "Assesses a student's grasp of core AI technologies, products, services and applications. For primary, junior and senior secondary students, across a foundation level and levels 1–8, rising in difficulty.",
            new Fact[]{
              new("測評方式","测评方式","Format","上機理論 ＋ 實踐操作，兩場分別合格","上机理论 ＋ 实践操作，两场分别合格","Written theory and practical, each passed separately"),
              new("等級","等级","Levels","啟蒙級（入門）· 1–4 進階 · 5–6 提升 · 7–8 拔高","启蒙级（入门）· 1–4 进阶 · 5–6 提升 · 7–8 拔高","Foundation · 1–4 intermediate · 5–6 advanced · 7–8 higher"),
              new("題庫","题库","Question bank","北京大學","北京大学","Peking University"),
              new("報考規則","报考规则","Entry rule","三級必考；三級及以上須逐級報考，或通過定級測試","三级必考；三级及以上须逐级报考，或通过定级测试","Level 3 is compulsory; level 3 and above must be taken in sequence, or by placement test"),
              new("題型","题型","Question types","客觀題（選擇、判斷）＋ 現場命題實操","客观题（选择、判断）＋ 现场命题实操","Objective questions plus an on-the-day practical brief"),
              new("適齡","适龄","Ages","6–16 歲","6–16 岁","6–16"),
            },
            new[]{"3月21、22日","6月13、14日","9月12、13日","12月5、6日"},
            "啟蒙級 ¥260 · 一、二級 ¥300 · 三至八級 ¥400",
            "启蒙级 ¥260 · 一、二级 ¥300 · 三至八级 ¥400",
            "Foundation ¥260 · Levels 1–2 ¥300 · Levels 3–8 ¥400"),

        ["YCL"] = new("YCL",
            "考查學生在程序思維、編程語言、數據處理及人工智能算法方面的能力水平。體系分為 1–8 級，難度逐級提升。",
            "考查学生在程序思维、编程语言、数据处理及人工智能算法方面的能力水平。体系分为 1–8 级，难度逐级提升。",
            "Assesses programming thinking, languages, data handling and AI algorithms. Eight levels, rising in difficulty.",
            new Fact[]{
              new("等級","等级","Levels","1–3 級 Scratch／低代碼 · 4–8 級 Python／C++","1–3 级 Scratch／低代码 · 4–8 级 Python／C++","Levels 1–3 Scratch/low-code · levels 4–8 Python/C++"),
              new("題庫","题库","Question bank","中國科學院計算技術研究所","中国科学院计算技术研究所","Institute of Computing Technology, Chinese Academy of Sciences"),
              new("合格","合格","Pass mark","60 分","60 分","60"),
              new("評價維度","评价维度","Assessed on","計算思維、創造性思維、算法設計與實現","计算思维、创造性思维、算法设计与实现","Computational thinking, creative thinking, algorithm design and implementation"),
              new("適齡","适龄","Ages","8–16 歲","8–16 岁","8–16"),
            },
            new[]{"3月14、15日","6月6、7日","9月12、13日","12月12、13日"},
            "一、二級 ¥300 · 三至八級 ¥400",
            "一、二级 ¥300 · 三至八级 ¥400",
            "Levels 1–2 ¥300 · Levels 3–8 ¥400"),

        ["ECL"] = new("ECL",
            "考查學生在無屏編程平台的應用能力、邏輯思維、程序設計與解決問題能力。共四個等級，難度逐級提升。",
            "考查学生在无屏编程平台的应用能力、逻辑思维、程序设计与解决问题能力。共四个等级，难度逐级提升。",
            "Assesses screen-free programming, logical thinking, program design and problem solving. Four levels, rising in difficulty.",
            new Fact[]{
              new("測評方式","测评方式","Format","實踐操作，現場完成指定任務","实践操作，现场完成指定任务","Practical only — a set task completed on the day"),
              new("等級","等级","Levels","一至四級","一至四级","Levels 1–4"),
              new("特色","特色","Approach","將圖形化編程的代碼塊實物化，脫離屏幕操作","将图形化编程的代码块实物化，脱离屏幕操作","Block programming made physical, worked without a screen"),
              new("適齡","适龄","Ages","4–14 歲","4–14 岁","4–14"),
            },
            new[]{"3月14、15日","6月6、7日","9月12、13日","12月12、13日"},
            "一至四級 ¥300", "一至四级 ¥300", "Levels 1–4 ¥300"),

        ["SCL"] = new("SCL",
            "考查學生在物質科學、生命科學、地球與宇宙科學、技術與工程等方面的創新設計能力。體系包括 1–6 級。",
            "考查学生在物质科学、生命科学、地球与宇宙科学、技术与工程等方面的创新设计能力。体系包括 1–6 级。",
            "Assesses innovative design across physical science, life science, earth and space science, and technology and engineering. Six levels.",
            new Fact[]{
              new("測評方式","测评方式","Format","實踐操作，現場完成指定任務","实践操作，现场完成指定任务","Practical only — a set task completed on the day"),
              new("等級","等级","Levels","一至六級；三級必考，三級以上逐級報考","一至六级；三级必考，三级以上逐级报考","Levels 1–6; level 3 compulsory, above that in sequence"),
              new("合格","合格","Pass mark","滿分 100，60 分合格","满分 100，60 分合格","60 out of 100"),
              new("適齡","适龄","Ages","小學至高中","小学至高中","Primary to senior secondary"),
            },
            new[]{"3月21、22日","6月13、14日","9月12、13日","12月5、6日"},
            "一、二級 ¥260 · 三至六級 ¥300",
            "一、二级 ¥260 · 三至六级 ¥300",
            "Levels 1–2 ¥260 · Levels 3–6 ¥300"),

        ["YUL"] = new("YUL",
            "考查學生的無人機基本知識、程序思維、編程語言與無人機基本操作。分五級，一級可跳級，二級及以上須逐級報考。",
            "考查学生的无人机基本知识、程序思维、编程语言与无人机基本操作。分五级，一级可跳级，二级及以上须逐级报考。",
            "Assesses drone fundamentals, programming thinking, languages and piloting. Five levels; level 1 may be skipped, level 2 and above are taken in sequence.",
            new Fact[]{
              new("等級","等级","Levels","一至五級","一至五级","Levels 1–5"),
              new("題庫","题库","Question bank","中國電子教育學會青少年教育分會","中国电子教育学会青少年教育分会","Youth Education Branch, China Electronics Education Society"),
              new("能力層次","能力层次","Levels of mastery","了解 · 理解 · 掌握","了解 · 理解 · 掌握","Aware · understands · applies"),
              new("內容","内容","Covers","無人機知識、遙控與編程飛行、傳感器、圖形化編程","无人机知识、遥控与编程飞行、传感器、图形化编程","Drone fundamentals, radio and programmed flight, sensors, block programming"),
            },
            new[]{"3月21、22日","6月13、14日","9月12、13日","12月5、6日"},
            "以官方公布為準", "以官方公布为准", "Per official announcement"),
    };

}
