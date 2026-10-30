using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;
using IitsNews.Data;

namespace IitsNews.Pages.News;

/// <summary>
/// Permanent redirect from an old ycltesthk News.ID to wherever that article now lives.
///
/// The 308 rows in url-map.csv are keyed on the OLD id, but /news/item/{id} is keyed on the
/// internal Id, and the two differ (legacy 187 is internal 93). Baking the internal ids into
/// a static redirect map would break on any re-import that renumbers them.
///
/// Resolving through this route instead means url-map.csv only ever needs the legacy id,
/// which never changes. nginx rewrites News.aspx?ID=187 to /news/legacy/187 and the lookup
/// happens here.
/// </summary>
public class LegacyModel : PageModel
{
    private readonly AppDb _db;
    public LegacyModel(AppDb db) => _db = db;

    public async Task<IActionResult> OnGetAsync(int legacyId, string? lang)
    {
        var article = await _db.Articles
            .AsNoTracking()
            .FirstOrDefaultAsync(a => a.LegacyId == legacyId);

        if (article is null) return NotFound();

        var suffix = Data.Lang.IsKnown(lang) ? $"?lang={lang}" : "";
        return RedirectPermanent($"/news/item/{article.Id}{suffix}");
    }
}
