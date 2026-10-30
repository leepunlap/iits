using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;
using IitsNews.Data;
using IitsNews.Services;

namespace IitsNews.Pages;

public class IndexModel : PageModel
{
    private readonly AppDb _db; private readonly SiteMenu _menu;
    public IndexModel(AppDb db, SiteMenu menu) { _db = db; _menu = menu; }

    public Article? Lead { get; private set; }
    /// <summary>The latest posts that actually carry an image — the ones the lead slideshow
    /// can show. An article with no picture would render as a caption over an empty box.</summary>
    public List<Article> LeadSlides { get; private set; } = new();
    public List<Article> NewsList { get; private set; } = new();
    public List<(string Code, string Name, int? SectionId)> Tracks { get; private set; } = new();
    public Dictionary<string,int> CatCounts { get; private set; } = new();
    public string CurrentLang { get; private set; } = Data.Lang.Hant;

    // The five assessment tracks the design puts across the top. Section ids are resolved
    // from the imported tree so each tile links somewhere real; a track with no section
    // still renders, it just does not link.
    private static readonly (string Code, string Zh)[] TrackDefs =
    {
        ("YAI", "青少年人工智能技术水平测试"),
        ("YCL", "青少年人工智能编程水平测试"),
        ("ECL", "青少年无屏编程水平测试"),
        ("SCL", "青少年科技素养水平测试"),
        ("YUL", "青少年无人机技术水平测试"),
    };

    public async Task OnGetAsync(string? lang)
    {
        CurrentLang = Data.Lang.IsKnown(lang) ? lang! : Data.Lang.Hant;
        ViewData["Title"] = Ui.T(CurrentLang, "home");
        ViewData["Lang"] = CurrentLang;

        var latest = await _db.Articles.AsNoTracking().Include(a => a.Translations)
            .Where(a => a.Status == "published" && a.Kind == "article")
            .OrderByDescending(a => a.PublishedAt).ThenByDescending(a => a.Id)
            // Enough for the five-slide lead AND a full side list — at nine, the slideshow
            // ate five and the column beside it fell to four rows with a hole underneath.
            .Take(16).ToListAsync();

        LeadSlides = latest.Where(a => a.For(CurrentLang).FirstImage() != null).Take(5).ToList();
        Lead = LeadSlides.FirstOrDefault() ?? latest.FirstOrDefault();
        var shown = LeadSlides.Select(a => a.Id).ToHashSet();
        NewsList = latest.Where(a => !shown.Contains(a.Id)).Take(7).ToList();

        CatCounts = await _db.Articles.AsNoTracking()
            .Where(a => a.Status == "published" && a.Cat != "" && a.Kind != "partner")
            .GroupBy(a => a.Cat).Select(g => new { g.Key, N = g.Count() })
            .ToDictionaryAsync(x => x.Key, x => x.N);

        var sections = await _db.Sections.AsNoTracking().ToListAsync();
        foreach (var (code, zh) in TrackDefs)
        {
            var s = sections.FirstOrDefault(x => x.Name == zh);
            Tracks.Add((code, s?.Name ?? zh, s?.LegacyId));
        }
    }
}
