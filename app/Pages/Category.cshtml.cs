using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;
using IitsNews.Data;
using IitsNews.Services;

namespace IitsNews.Pages;

/// <summary>
/// Category landing: the LATEST few from each strand, with a link into the full archive.
/// The old site put every article of a section on one endless page; showing the recent work
/// and keeping the rest one click away is the difference between a site and a filing cabinet.
/// </summary>
public class CategoryModel : PageModel
{
    private readonly AppDb _db;
    public CategoryModel(AppDb db) => _db = db;

    public CatDef Cat { get; private set; } = default!;
    public List<(SubDef? Sub, List<Article> Items, int Total)> Blocks { get; private set; } = new();
    public string CurrentLang { get; private set; } = Data.Lang.Hant;
    private const int PerBlock = 6;

    public async Task<IActionResult> OnGetAsync(string cat, string? lang)
    {
        CurrentLang = Data.Lang.IsKnown(lang) ? lang! : Data.Lang.Hant;
        var def = Taxonomy.Cat(cat);
        if (def is null) return NotFound();
        Cat = def;
        ViewData["Title"] = Taxonomy.Name(def, CurrentLang);
        ViewData["Lang"] = CurrentLang;

        if (def.Subs.Length == 0)
        {
            var all = await Query(cat, null).Take(60).ToListAsync();
            Blocks.Add((null, all, all.Count));
            return Page();
        }
        foreach (var sd in def.Subs)
        {
            var q = Query(cat, sd.Key);
            var total = await q.CountAsync();
            if (total == 0) continue;
            Blocks.Add((sd, await q.Take(PerBlock).ToListAsync(), total));
        }
        return Page();
    }

    private IQueryable<Article> Query(string cat, string? sub) =>
        _db.Articles.AsNoTracking().Include(a => a.Translations)
           .Where(a => a.Status == "published" && a.Kind != "partner" && a.Cat == cat && (sub == null || a.Sub == sub))
           .OrderByDescending(a => a.PublishedAt).ThenByDescending(a => a.Id);
}
