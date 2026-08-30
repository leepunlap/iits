using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;
using IitsNews.Data;
using IitsNews.Services;

namespace IitsNews.Pages;

/// <summary>
/// The expert roster is its own thing, not news. Carried over from the old CMS it was just
/// another article row in the 专家团队 section, so it landed in the news feed interleaved with
/// competition reports — twelve professors dated like press releases. Kind='expert' takes them
/// out of every article listing and gives them this page.
/// </summary>
public class ExpertsModel : PageModel
{
    private readonly AppDb _db;
    public ExpertsModel(AppDb db) => _db = db;

    public List<Article> Items { get; private set; } = new();
    public string CurrentLang { get; private set; } = Data.Lang.Hant;

    public async Task OnGetAsync(string? lang)
    {
        CurrentLang = Data.Lang.IsKnown(lang) ? lang! : Data.Lang.Hant;
        ViewData["Title"] = Ui.T(CurrentLang, "experts");
        ViewData["Lang"] = CurrentLang;

        Items = await _db.Articles.AsNoTracking().Include(a => a.Translations)
            .Where(a => a.Kind == "expert" && a.Status == "published")
            .OrderBy(a => a.Id).ToListAsync();
    }
}
