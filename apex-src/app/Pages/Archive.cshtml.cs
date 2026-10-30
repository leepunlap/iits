using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;
using IitsNews.Data;
using IitsNews.Services;

namespace IitsNews.Pages;

/// <summary>
/// The paginated long tail of one strand, and nothing more.
///
/// Everything a strand IS — its track detail, its standing text, its people, its logos —
/// now sits inline on the category's single long page. This route survives only for strands
/// with more articles than that page shows, and redirects to the anchor otherwise, so there
/// is never a second half-empty copy of a section to land on.
/// </summary>
public class ArchiveModel : PageModel
{
    private readonly AppDb _db;
    public ArchiveModel(AppDb db) => _db = db;

    public CatDef Cat { get; private set; } = default!;
    public SubDef? Sub { get; private set; }
    public List<Article> Items { get; private set; } = new();
    public string Kind { get; private set; } = "article";
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

        // Experts and partners are their own kinds. Asking for articles in their section is
        // what made both look empty.
        Kind = sub switch { "experts" => "expert", "partners" => "partner", _ => "article" };

        // A category is one long page. This route survives only as the paginated long tail
        // for strands that have more articles than the section shows; anything whose whole
        // content already sits on the category page redirects to its anchor there rather
        // than existing as a second, half-empty copy of it.
        var articleCount = await _db.Articles.AsNoTracking()
            .CountAsync(a => a.Status == "published" && a.Kind == "article" && a.Cat == cat && a.Sub == sub);
        if (articleCount <= 6)
            return Redirect($"/c/{cat}?lang={CurrentLang}#{sub}");
        var q = _db.Articles.AsNoTracking().Include(a => a.Translations)
                 .Where(a => a.Status == "published" && a.Kind == Kind && a.Cat == cat && a.Sub == sub);
        Total = await q.CountAsync();
        Pages = Math.Max(1, (int)Math.Ceiling(Total / (double)PerPage));
        Page1 = Math.Clamp(page, 1, Pages);
        q = Kind == "article"
            ? q.OrderByDescending(a => a.PublishedAt).ThenByDescending(a => a.Id)
            : q.OrderBy(a => a.Id);          // people and logos have no news order
        Items = await q.Skip((Page1 - 1) * PerPage).Take(PerPage).ToListAsync();

        ViewData["Title"] = Sub is null ? Taxonomy.Name(cd, CurrentLang) : Taxonomy.Name(Sub, CurrentLang);
        ViewData["Lang"] = CurrentLang;
        return Page();
    }
}
