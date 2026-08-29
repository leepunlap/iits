using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;
using IitsNews.Data;
using IitsNews.Services;

namespace IitsNews.Pages;

public class IndexModel : PageModel
{
    private readonly AppDb _db; private readonly SiteMenu _menu;
    public IndexModel(AppDb db, SiteMenu menu) { _db = db; _menu = menu; }

    public List<Article> Latest { get; private set; } = new();
    public List<(MenuItem Section, List<Article> Items)> Blocks { get; private set; } = new();
    public int TotalPublished { get; private set; }
    public string CurrentLang { get; private set; } = Data.Lang.Hant;

    public async Task OnGetAsync(string? lang)
    {
        CurrentLang = Data.Lang.IsKnown(lang) ? lang! : Data.Lang.Hant;
        ViewData["Title"] = "首頁";
        ViewData["Lang"] = CurrentLang;

        TotalPublished = await _db.Articles.CountAsync(a => a.Status == "published");

        Latest = await _db.Articles.AsNoTracking().Include(a => a.Translations)
            .Where(a => a.Status == "published")
            .OrderByDescending(a => a.PublishedAt).ThenByDescending(a => a.Id)
            .Take(7).ToListAsync();

        var latestIds = Latest.Select(a => a.Id).ToHashSet();

        foreach (var m in (await _menu.GetAsync()).Take(4))
        {
            var ids = await _menu.BranchIdsAsync(m.LegacyId);
            var items = await _db.Articles.AsNoTracking().Include(a => a.Translations)
                .Where(a => a.Status == "published" && a.LegacySectionId != null
                            && ids.Contains(a.LegacySectionId.Value) && !latestIds.Contains(a.Id))
                .OrderByDescending(a => a.PublishedAt).Take(3).ToListAsync();
            if (items.Count > 0) Blocks.Add((m, items));
        }
    }
}
