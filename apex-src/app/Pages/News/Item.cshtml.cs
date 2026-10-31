using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;
using IitsNews.Data;

namespace IitsNews.Pages.News;

public class ItemModel : PageModel
{
    private readonly AppDb _db;
    private readonly IConfiguration _cfg;
    public ItemModel(AppDb db, IConfiguration cfg) { _db = db; _cfg = cfg; }

    public Article? Item { get; private set; }
    public ArticleTranslation? Text { get; private set; }
    public string CurrentLang { get; private set; } = Data.Lang.Hant;

    /// <summary>Staging-only draft visibility. See IndexModel.ShowDrafts.</summary>
    public bool ShowDrafts => _cfg.GetValue<bool>("ShowDrafts");

    public async Task<IActionResult> OnGetAsync(int id, string? lang)
    {
        CurrentLang = Data.Lang.IsKnown(lang) ? lang! : Data.Lang.Hant;

        var q = _db.Articles.Include(a => a.Translations).Where(a => a.Id == id);
        if (!ShowDrafts) q = q.Where(a => a.Status == "published");

        Item = await q.FirstOrDefaultAsync();
        if (Item is null) return NotFound();

        Text = Item.For(CurrentLang);
        ViewData["Lang"] = Text?.Lang ?? CurrentLang;
        ViewData["Title"] = Text?.Title ?? "新聞";
        // A share card for an article has to say it is an article: Facebook and
        // LinkedIn lay out og:type=article completely differently from website.
        ViewData["OgType"] = "article";
        return Page();
    }
}
