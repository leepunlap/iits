using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;
using IitsNews.Data;

namespace IitsNews.Pages.News;

public class IndexModel : PageModel
{
    private readonly AppDb _db;
    public IndexModel(AppDb db) => _db = db;

    public string CurrentLang { get; private set; } = Data.Lang.Hant;
    public List<Article> Items { get; private set; } = new();

    public async Task OnGetAsync(string? lang)
    {
        CurrentLang = Data.Lang.IsKnown(lang) ? lang! : Data.Lang.Hant;
        ViewData["Lang"] = CurrentLang;
        ViewData["Title"] = "新聞";

        // Only published, titled articles are listed. Imported page-body blocks and
        // empty shells exist as records but are not news items.
        Items = await _db.Articles
            .Include(a => a.Translations)
            .Where(a => a.Status == "published" && a.Kind == "article")
            .OrderByDescending(a => a.Pinned)
            .ThenByDescending(a => a.PublishedAt)
            .Take(100)
            .ToListAsync();
    }
}
