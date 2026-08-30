namespace IitsNews.Services;

public record Pillar(string Img, string Kicker, string Hant, string Hans, string En,
                     string DHant, string DHans, string DEn);
public record Panel(string Kicker, string Hant, string Hans, string En,
                    string BHant, string BHans, string BEn);
public record Track(string Code, string Hant, string Hans, string En, string[] Hant2, string[] Hans2, string[] En2);

/// <summary>
/// The narrative blocks from the live iits.giftedintl.com home page, brought across.
///
/// Held as data rather than markup so all three languages come from one place: the original
/// is Traditional-only, and duplicating the markup per language is how translations drift.
/// Simplified is generated with the same s2hk/hk2s rules as the article corpus; English is
/// written, not converted — see i18n/TRANSLATION.md §5.
/// </summary>
public static class HomeContent
{
    public static readonly Pillar[] Pillars =
    {
        new("card-ed.jpg", "EARLY DISCOVERY", "啟蒙探索", "启蒙探索", "Early Discovery",
            "以遊戲化與動手實驗點燃興趣，建立運算思維與數字素養的基礎。",
            "以游戏化与动手实验点燃兴趣，建立运算思维与数字素养的基础。",
            "Play and hands-on experiment to spark interest, building the foundations of computational thinking and digital literacy."),
        new("card-ip.jpg", "INNOVATION PRACTICE", "創新實踐", "创新实践", "Innovation Practice",
            "由概念到原型，透過「生產性失敗」教學法帶領學員完成真實項目。",
            "由概念到原型，透过「生产性失败」教学法带领学员完成真实项目。",
            "From concept to prototype, guiding students through real projects with the productive-failure method."),
        new("card-wl.jpg", "WONDER LAB", "奇趣實驗室", "奇趣实验室", "Wonder Lab",
            "跨學科探究空間，結合 AI、機械人與創客工具，鼓勵大膽嘗試。",
            "跨学科探究空间，结合 AI、机器人与创客工具，鼓励大胆尝试。",
            "A cross-disciplinary space combining AI, robotics and maker tools, where trying something bold is the point."),
        new("card-cc.jpg", "IITC COMPETITION", "IITC 競賽", "IITC 竞赛", "IITC Competition",
            "對接大灣區與國際賽事管道，讓學員在舞台上展示與驗證成果。",
            "对接大湾区与国际赛事管道，让学员在舞台上展示与验证成果。",
            "Connected to Greater Bay Area and international competition circuits, so students can show and test their work on a real stage."),
    };

    public static readonly Panel[] Panels =
    {
        new("NATIONAL BACKING", "國家級體系", "国家级体系", "National Backing",
            "依託工信部的教育基礎設施：全部認證由<b>工業和信息化部教育與考試中心</b>頒發，題庫由<b>北京大學</b>、<b>中國科學院計算技術研究所</b>等權威機構開發。五大認證軌道涵蓋電子信息（ECL）、人工智能（YAI）、編程（YCL）、科學素養（SCL）與無人機（YUL）。",
            "依托工信部的教育基础设施：全部认证由<b>工业和信息化部教育与考试中心</b>颁发，题库由<b>北京大学</b>、<b>中国科学院计算技术研究所</b>等权威机构开发。五大认证轨道涵盖电子信息（ECL）、人工智能（YAI）、编程（YCL）、科学素养（SCL）与无人机（YUL）。",
            "Built on MIIT's education infrastructure: every certificate is issued by the <b>MIIT Education and Examination Center</b>, with question banks developed by <b>Peking University</b> and the <b>Institute of Computing Technology, Chinese Academy of Sciences</b>. Five tracks cover electronics (ECL), AI (YAI), programming (YCL), science literacy (SCL) and drones (YUL)."),
        new("PRODUCTIVE FAILURE", "教學理念", "教学理念", "Teaching Approach",
            "課程建基於「<b>生產性失敗</b>」教學法（Manu Kapur, ETH Zürich），糅合建構主義（Papert）與體驗式學習（Kolb），並承接「因材施教、工匠精神」的中華教育根源。核心是四步循環 —— <b>預測 → 建構 → 觀察 → 調整</b>，讓孩子在動手之中，學會提出下一個問題。",
            "课程建基于「<b>生产性失败</b>」教学法（Manu Kapur, ETH Zürich），糅合建构主义（Papert）与体验式学习（Kolb），并承接「因材施教、工匠精神」的中华教育根源。核心是四步循环 —— <b>预测 → 建构 → 观察 → 调整</b>，让孩子在动手之中，学会提出下一个问题。",
            "Courses are built on <b>productive failure</b> (Manu Kapur, ETH Zürich), combined with constructionism (Papert) and experiential learning (Kolb), and rooted in the Chinese educational traditions of teaching to the individual and craftsmanship. The core is a four-step loop — <b>predict → build → observe → adjust</b> — so that in the making, a child learns to ask the next question."),
        new("LEARNING STREAMS", "四大學習流", "四大学习流", "Four Learning Streams",
            "<b>啟蒙探索</b>（4–8 歲・無屏編程，64 課）、<b>創新實踐</b>（6–12 歲・機械與 AI 建構，160 課／10 級）、<b>奇趣實驗室 Wonder Lab</b>（AI 互動魔方，14 模組）與 <b>IITC 競賽</b>（6–16 歲・每年舉行），構成由興趣到實戰的完整成長路徑。",
            "<b>启蒙探索</b>（4–8 岁・无屏编程，64 课）、<b>创新实践</b>（6–12 岁・机械与 AI 建构，160 课／10 级）、<b>奇趣实验室 Wonder Lab</b>（AI 互动魔方，14 模组）与 <b>IITC 竞赛</b>（6–16 岁・每年举行），构成由兴趣到实战的完整成长路径。",
            "<b>Early Discovery</b> (ages 4–8, screen-free programming, 64 lessons), <b>Innovation Practice</b> (6–12, mechanical and AI construction, 160 lessons across 10 levels), <b>Wonder Lab</b> (AI interactive cube, 14 modules) and the <b>IITC Competition</b> (6–16, held annually) form a complete path from first curiosity to competing for real."),
        new("GBA PIPELINE", "大灣區聯動", "大湾区联动", "Greater Bay Area Pipeline",
            "設有政府認可的「<b>珠港澳青年就業創業校外實踐基地</b>」（珠海金灣，2024 年）及珠海學習中心，支援跨境交流、大灣區科技體驗與競賽集訓，賽事管道直達<b>珠海橫琴省級決賽</b>。課程並可銜接香港「<b>全方位學習及姊妹學校津貼（LWLSSG）</b>」。",
            "设有政府认可的「<b>珠港澳青年就业创业校外实践基地</b>」（珠海金湾，2024 年）及珠海学习中心，支援跨境交流、大湾区科技体验与竞赛集训，赛事管道直达<b>珠海横琴省级决赛</b>。课程并可衔接香港「<b>全方位学习及姊妹学校津贴（LWLSSG）</b>」。",
            "A government-accredited <b>Zhuhai–Hong Kong–Macau Youth Employment and Entrepreneurship Practice Base</b> (Jinwan, Zhuhai, 2024) and a Zhuhai learning centre support cross-border exchange, Greater Bay Area technology experiences and competition training, with a route straight through to the <b>Zhuhai Hengqin provincial final</b>. Courses also align with Hong Kong's <b>Life-wide Learning and Sister School Grant (LWLSSG)</b>."),
        new("LOCALIZED FOR HK", "本地化教學", "本地化教学", "Localised for Hong Kong",
            "國家級課程全面<b>繁體中文本地化</b>，並按香港學制與學童發展階段調適；啟蒙級採用適齡、可親手操作的題型設計，服務本地幼稚園、小學與家庭。",
            "国家级课程全面<b>繁体中文本地化</b>，并按香港学制与学童发展阶段调适；启蒙级采用适龄、可亲手操作的题型设计，服务本地幼稚园、小学与家庭。",
            "The national curriculum is fully localised into <b>Traditional Chinese</b> and adapted to the Hong Kong school system and to how children develop; the foundation level uses age-appropriate, hands-on task design, serving local kindergartens, primary schools and families."),
        new("TEACHER DEVELOPMENT", "師資與資源", "师资与资源", "Teachers and Resources",
            "提供<b>導師培訓、逐課授課指引與教學資源</b>，配合「奇思工房」教學法，讓學校與老師能穩妥落地課程；教師專區另設完整教材下載。",
            "提供<b>导师培训、逐课授课指引与教学资源</b>，配合「奇思工房」教学法，让学校与老师能稳妥落地课程；教师专区另设完整教材下载。",
            "<b>Instructor training, lesson-by-lesson teaching guides and classroom resources</b> accompany the Wonder Workshop method, so schools and teachers can deliver the courses with confidence; the teacher area holds the full set of materials for download."),
    };

    public static readonly Track[] Tracks =
    {
        new("YAI", "青少年人工智能技術水平測試", "青少年人工智能技术水平测试", "Youth AI Technology Test",
            new[]{"題庫：<b>北京大學</b>","啟蒙級 ＋ 1–10 級","理論 ＋ 實操，兩場合格","適齡 6–16 歲"},
            new[]{"题库：<b>北京大学</b>","启蒙级 ＋ 1–10 级","理论 ＋ 实操，两场合格","适龄 6–16 岁"},
            new[]{"Question bank: <b>Peking University</b>","Foundation + levels 1–10","Theory and practical, both must pass","Ages 6–16"}),
        new("YCL", "青少年人工智能編程水平測試", "青少年人工智能编程水平测试", "Youth Coding Level Test",
            new[]{"題庫：<b>中國科學院計算技術研究所</b>","1–8 級（1–3 圖形化 Scratch，4–8 Python／C++）","60 分合格","適齡 8–16 歲"},
            new[]{"题库：<b>中国科学院计算技术研究所</b>","1–8 级（1–3 图形化 Scratch，4–8 Python／C++）","60 分合格","适龄 8–16 岁"},
            new[]{"Question bank: <b>Institute of Computing Technology, CAS</b>","Levels 1–8 (1–3 Scratch, 4–8 Python/C++)","Pass mark 60","Ages 8–16"}),
        new("ECL", "青少年電子信息技術等級考試", "青少年电子信息技术等级考试", "Electronics & Info Tech",
            new[]{"無屏編程與邏輯思維","共 4 級","適齡 4–8 歲"},
            new[]{"无屏编程与逻辑思维","共 4 级","适龄 4–8 岁"},
            new[]{"Screen-free programming and logical thinking","4 levels","Ages 4–8"}),
        new("SCL", "科學素養水平測試", "科学素养水平测试", "Science Literacy Test",
            new[]{"科學素養與工程設計","共 6 級"},
            new[]{"科学素养与工程设计","共 6 级"},
            new[]{"Science literacy and engineering design","6 levels"}),
        new("YUL", "無人機水平測試", "无人机水平测试", "UAV Level Test",
            new[]{"無人機組裝、操控與編程","共 5 級"},
            new[]{"无人机组装、操控与编程","共 5 级"},
            new[]{"Drone assembly, piloting and programming","5 levels"}),
    };

    public static string P(Pillar p, string l) => l switch { "zh-Hans" => p.Hans, "en" => p.En, _ => p.Hant };
    public static string PD(Pillar p, string l) => l switch { "zh-Hans" => p.DHans, "en" => p.DEn, _ => p.DHant };
    public static string N(Panel p, string l) => l switch { "zh-Hans" => p.Hans, "en" => p.En, _ => p.Hant };
    public static string NB(Panel p, string l) => l switch { "zh-Hans" => p.BHans, "en" => p.BEn, _ => p.BHant };
    public static string TN(Track t, string l) => l switch { "zh-Hans" => t.Hans, "en" => t.En, _ => t.Hant };
    public static string[] TB(Track t, string l) => l switch { "zh-Hans" => t.Hans2, "en" => t.En2, _ => t.Hant2 };
}
