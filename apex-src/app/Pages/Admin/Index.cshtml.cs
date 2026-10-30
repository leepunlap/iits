using Microsoft.EntityFrameworkCore;
using IitsNews.Data;

namespace IitsNews.Pages.Admin;

public class IndexModel : AdminPageModel
{
    private readonly AppDb _db;
    public IndexModel(AppDb db) => _db = db;

    public List<Article> Items { get; private set; } = new();
    public string Filter { get; private set; } = "article";
    public int CountDraft { get; private set; }
    public int CountPublished { get; private set; }
    public string Who => AdminUser;

    public async Task OnGetAsync(string? kind, string? q)
    {
        ViewData["Title"] = "管理";
        Filter = string.IsNullOrWhiteSpace(kind) ? "article" : kind;

        var query = _db.Articles.Include(a => a.Translations).AsQueryable();
        if (Filter != "all") query = query.Where(a => a.Kind == Filter);

        if (!string.IsNullOrWhiteSpace(q))
            query = query.Where(a => a.Translations.Any(t => t.Title.Contains(q)));

        Items = await query
            .OrderByDescending(a => a.PublishedAt)
            .ThenByDescending(a => a.Id)
            .Take(300)
            .ToListAsync();

        CountDraft = await _db.Articles.CountAsync(a => a.Status == "draft");
        CountPublished = await _db.Articles.CountAsync(a => a.Status == "published");
    }
}
