namespace IitsNews.Services;

/// <summary>
/// Affiliation and role for each adviser, keyed by the Traditional Chinese name.
///
/// Held here rather than parsed out of the biography at render time: the bodies are imported
/// prose whose first sentence sometimes opens with the person's institution and sometimes
/// with their research interests, so a regex would print "mainly works on computer science"
/// where an institution belongs. Every entry below is taken from the organisers page (#17)
/// or from the adviser's own biography.
///
/// 蔡自興 is deliberately left without an affiliation: his biography records where he
/// GRADUATED (Xi'an Jiaotong, 1962) and his academy fellowships, but never states his
/// institution, and inventing one would be worse than leaving the line out.
/// </summary>
public record ExpertMeta(string OrgHant, string OrgHans, string OrgEn,
                         string RoleHant, string RoleHans, string RoleEn)
{
    public string Org(string l)  => l == "zh-Hans" ? OrgHans  : l == "en" ? OrgEn  : OrgHant;
    public string Role(string l) => l == "zh-Hans" ? RoleHans : l == "en" ? RoleEn : RoleHant;
}

public static class ExpertRoster
{
    public static readonly Dictionary<string, ExpertMeta> All = new()
    {
        ["樊磊"]   = new("首都師範大學教育學院", "首都师范大学教育学院", "Capital Normal University, School of Education",
                         "教授", "教授", "Professor"),
        ["翁愷"]   = new("浙江大學電腦學院", "浙江大学计算机学院", "Zhejiang University, College of Computer Science",
                         "副教授", "副教授", "Associate Professor"),
        ["彭圖"]   = new("北京理工大學網絡空間安全學院", "北京理工大学网络空间安全学院", "Beijing Institute of Technology, School of Cyberspace Science and Technology",
                         "副教授", "副教授", "Associate Professor"),
        ["梁孔明"] = new("北京郵電大學人工智能學院", "北京邮电大学人工智能学院", "Beijing University of Posts and Telecommunications, School of Artificial Intelligence",
                         "副教授", "副教授", "Associate Professor"),
        ["李瑞峯"] = new("哈爾濱工業大學機器人研究所", "哈尔滨工业大学机器人研究所", "Harbin Institute of Technology, Robotics Institute",
                         "副所長 · 教授", "副所长 · 教授", "Deputy Director · Professor"),
        ["王巍"]   = new("北京航空航天大學機器人研究所", "北京航空航天大学机器人研究所", "Beihang University, Robotics Institute",
                         "教授", "教授", "Professor"),
        ["肖俊"]   = new("中國科學院大學人工智能學院", "中国科学院大学人工智能学院", "University of Chinese Academy of Sciences, School of Artificial Intelligence",
                         "副院長 · 教授", "副院长 · 教授", "Deputy Dean · Professor"),
        ["趙衞東"] = new("復旦大學電腦科學技術學院", "复旦大学计算机科学技术学院", "Fudan University, School of Computer Science",
                         "副教授", "副教授", "Associate Professor"),
        ["謝廣明"] = new("北京大學工學院", "北京大学工学院", "Peking University, College of Engineering",
                         "教授 · 博士生導師", "教授 · 博士生导师", "Professor · Doctoral Supervisor"),
        ["李雙壽"] = new("清華大學基礎工業訓練中心", "清华大学基础工业训练中心", "Tsinghua University, Basic Industry Training Center",
                         "主任 · 教授", "主任 · 教授", "Director · Professor"),
        ["顧建軍"] = new("南京師範大學教育科學學院", "南京师范大学教育科学学院", "Nanjing Normal University, School of Education Science",
                         "院長 · 教授", "院长 · 教授", "Dean · Professor"),
    };

    public static ExpertMeta? For(string? hantName) =>
        hantName is not null && All.TryGetValue(hantName.Trim(), out var m) ? m : null;
}
