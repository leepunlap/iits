using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;
using IitsNews.Data;
using IitsNews.Services;

namespace IitsNews.Pages;

/// <summary>
/// A category is ONE long page with anchored sections, not a hub that scatters its own
/// content across a page per subcategory. The submenu scrolls; it does not navigate.
///
/// That is only affordable because the imported bodies were sanitised: 518 KB of WYSIWYG
/// debris across the published pages became 35 KB of actual markup, so every section's
/// standing text can sit inline without the page becoming unloadable.
/// </summary>
public class CategoryModel : PageModel
{
    private readonly AppDb _db;
    public CategoryModel(AppDb db) => _db = db;

    public record Block(SubDef Sub, List<Article> Pages, List<Article> Items, int Total, TrackPage? Track);

    public CatDef Cat { get; private set; } = default!;
    public List<Block> Blocks { get; private set; } = new();
    public List<Article> Loose { get; private set; } = new();
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

        var all = await _db.Articles.AsNoTracking().Include(a => a.Translations)
                     .Where(a => a.Status == "published" && a.Cat == cat).ToListAsync();

        foreach (var sd in def.Subs)
        {
            // Experts and partners are their own kinds; asking for articles in their section
            // is what used to make both report "nothing published".
            var kind = sd.Key switch { "experts" => "expert", "partners" => "partner", _ => "article" };
            // Pinned first: a section's illustrated summary should lead, with the detailed
            // text under it, rather than landing wherever its import id happened to fall.
            var pages = all.Where(a => a.Kind == "page" && a.Sub == sd.Key)
                           .OrderByDescending(a => a.Pinned).ThenBy(a => a.Id).ToList();
            var items = all.Where(a => a.Kind == kind && a.Sub == sd.Key).ToList();
            var total = items.Count;
            items = kind == "article"
                ? items.OrderByDescending(a => a.PublishedAt).ThenByDescending(a => a.Id).Take(PerBlock).ToList()
                : items.OrderBy(a => a.Id).ToList();     // people and logos have no news order
            TrackContent.All.TryGetValue(sd.Key, out var tp);
            if (pages.Count == 0 && items.Count == 0 && tp is null && !(cat == "about" && sd.Key == "overview"))
                continue;
            Blocks.Add(new Block(sd, pages, items, total, tp));
        }

        // Anything filed to the category but to no subcategory would otherwise be invisible.
        var claimed = def.Subs.Select(s => s.Key).ToHashSet();
        Loose = all.Where(a => a.Kind == "article" && !claimed.Contains(a.Sub ?? ""))
                   .OrderByDescending(a => a.PublishedAt).ThenByDescending(a => a.Id).Take(PerBlock).ToList();
        return Page();
    }
}
