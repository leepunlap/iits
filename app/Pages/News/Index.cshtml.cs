using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;
using IitsNews.Data;

namespace IitsNews.Pages.News;

public class IndexModel : PageModel
{
    private readonly AppDb _db;
    private readonly IConfiguration _cfg;
    public IndexModel(AppDb db, IConfiguration cfg) { _db = db; _cfg = cfg; }

    public string CurrentLang { get; private set; } = Data.Lang.Hant;
    public List<Article> Items { get; private set; } = new();

    /// <summary>
    /// Staging-only: list drafts alongside published items so content can be reviewed
    /// before the admin realm exists. Off unless explicitly enabled, and it must stay off
    /// in production — see the warning banner in the view.
    /// </summary>
    public bool ShowDrafts => _cfg.GetValue<bool>("ShowDrafts");

    public async Task OnGetAsync(string? lang)
    {
        CurrentLang = Data.Lang.IsKnown(lang) ? lang! : Data.Lang.Hant;
        ViewData["Lang"] = CurrentLang;
        ViewData["Title"] = "新聞";

        var q = _db.Articles.Include(a => a.Translations).Where(a => a.Kind == "article");
        if (!ShowDrafts) q = q.Where(a => a.Status == "published");

        Items = await q
            .OrderByDescending(a => a.Pinned)
            .ThenByDescending(a => a.PublishedAt)
            .Take(300)
            .ToListAsync();
    }
}
