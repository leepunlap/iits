using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;
using IitsNews.Data;
using IitsNews.Services;

namespace IitsNews.Pages;

public class SectionModel : PageModel
{
    private readonly AppDb _db; private readonly SiteMenu _menu;
    public SectionModel(AppDb db, SiteMenu menu) { _db = db; _menu = menu; }

    public Section? Current { get; private set; }
    public Section? Parent { get; private set; }
    public List<Section> Children { get; private set; } = new();
    public List<Article> Items { get; private set; } = new();
    public string CurrentLang { get; private set; } = Data.Lang.Hant;

    public async Task<IActionResult> OnGetAsync(int legacyId, string? lang)
    {
        CurrentLang = Data.Lang.IsKnown(lang) ? lang! : Data.Lang.Hant;

        Current = await _db.Sections.AsNoTracking().FirstOrDefaultAsync(s => s.LegacyId == legacyId);
        if (Current is null) return NotFound();

        if (Current.LegacyParentId != 0)
            Parent = await _db.Sections.AsNoTracking().FirstOrDefaultAsync(s => s.LegacyId == Current.LegacyParentId);

        Children = await _db.Sections.AsNoTracking()
            .Where(s => s.LegacyParentId == legacyId)
            .OrderByDescending(s => s.Order).ToListAsync();

        // A parent section shows its whole branch, so a top-level menu entry is never empty.
        var ids = await _menu.BranchIdsAsync(legacyId);
        Items = await _db.Articles.AsNoTracking().Include(a => a.Translations)
            .Where(a => a.Status == "published" && a.LegacySectionId != null && ids.Contains(a.LegacySectionId.Value))
            .OrderByDescending(a => a.PublishedAt).ThenByDescending(a => a.Id)
            .Take(120).ToListAsync();

        ViewData["Title"] = Current.Name;
        ViewData["Lang"] = CurrentLang;
        return Page();
    }
}
