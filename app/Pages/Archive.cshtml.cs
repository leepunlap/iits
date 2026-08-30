using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;
using IitsNews.Data;
using IitsNews.Services;

namespace IitsNews.Pages;

/// <summary>Everything in one strand, paged. This is where the long tail lives so the
/// landing pages can stay short — nothing is dropped, it is just one click deeper.</summary>
public class ArchiveModel : PageModel
{
    private readonly AppDb _db;
    public ArchiveModel(AppDb db) => _db = db;

    public CatDef Cat { get; private set; } = default!;
    public SubDef? Sub { get; private set; }
    public List<Article> Items { get; private set; } = new();
    public int Page1 { get; private set; } = 1;
    public int Pages { get; private set; } = 1;
    public int Total { get; private set; }
    public string CurrentLang { get; private set; } = Data.Lang.Hant;
    private const int PerPage = 24;

    public async Task<IActionResult> OnGetAsync(string cat, string sub, string? lang, int page = 1)
    {
        CurrentLang = Data.Lang.IsKnown(lang) ? lang! : Data.Lang.Hant;
        var cd = Taxonomy.Cat(cat); if (cd is null) return NotFound();
        Cat = cd; Sub = Taxonomy.Sub(cat, sub);
        if (cd.Subs.Length > 0 && Sub is null) return NotFound();

        var q = _db.Articles.AsNoTracking().Include(a => a.Translations)
                 .Where(a => a.Status == "published" && a.Kind != "partner" && a.Cat == cat && a.Sub == sub);
        Total = await q.CountAsync();
        Pages = Math.Max(1, (int)Math.Ceiling(Total / (double)PerPage));
        Page1 = Math.Clamp(page, 1, Pages);
        Items = await q.OrderByDescending(a => a.PublishedAt).ThenByDescending(a => a.Id)
                       .Skip((Page1 - 1) * PerPage).Take(PerPage).ToListAsync();

        ViewData["Title"] = Sub is null ? Taxonomy.Name(cd, CurrentLang) : Taxonomy.Name(Sub, CurrentLang);
        ViewData["Lang"] = CurrentLang;
        return Page();
    }
}
