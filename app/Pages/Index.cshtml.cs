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
    public List<Article> NewsList { get; private set; } = new();
    public List<MenuItem> Pillars { get; private set; } = new();
    public List<(string Code, string Name, int? SectionId)> Tracks { get; private set; } = new();
    public List<Article> Partners { get; private set; } = new();
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
            .Where(a => a.Status == "published" && a.Kind != "expert" && a.Kind != "partner")
            .OrderByDescending(a => a.PublishedAt).ThenByDescending(a => a.Id)
            .Take(9).ToListAsync();

        Lead = latest.FirstOrDefault(a => a.For(CurrentLang).FirstImage() != null) ?? latest.FirstOrDefault();
        NewsList = latest.Where(a => a.Id != Lead?.Id).Take(7).ToList();

        Pillars = (await _menu.GetAsync()).ToList();

        CatCounts = await _db.Articles.AsNoTracking()
            .Where(a => a.Status == "published" && a.Cat != "" && a.Kind != "partner")
            .GroupBy(a => a.Cat).Select(g => new { g.Key, N = g.Count() })
            .ToDictionaryAsync(x => x.Key, x => x.N);

        Partners = await _db.Articles.AsNoTracking().Include(a => a.Translations)
            .Where(a => a.Kind == "partner" && a.Status == "published")
            .OrderBy(a => a.Id).ToListAsync();

        var sections = await _db.Sections.AsNoTracking().ToListAsync();
        foreach (var (code, zh) in TrackDefs)
        {
            var s = sections.FirstOrDefault(x => x.Name == zh);
            Tracks.Add((code, s?.Name ?? zh, s?.LegacyId));
        }
    }
}
