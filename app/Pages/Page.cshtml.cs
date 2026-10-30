using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;
using IitsNews.Data;
using IitsNews.Services;

namespace IitsNews.Pages;

/// <summary>
/// A standing page — 簡介, 主辦單位, 聯繫我們, the assessment overviews.
///
/// These arrived from the old CMS as News rows, because that CMS had only one content type,
/// so everything it held was an article whether it was one or not. They are pages: no
/// publication date, no place in a feed, no "latest" ordering. Modelling them as articles is
/// what put a date stamp on 「聯繫我們」 and left the About category showing zero.
/// </summary>
public class PageModel_ : PageModel
{
    private readonly AppDb _db;
    public PageModel_(AppDb db) => _db = db;

    public Article? Item { get; private set; }
    public ArticleTranslation? Text { get; private set; }
    public CatDef? Cat { get; private set; }
    public string CurrentLang { get; private set; } = Data.Lang.Hant;

    public async Task<IActionResult> OnGetAsync(int id, string? lang)
    {
        CurrentLang = Data.Lang.IsKnown(lang) ? lang! : Data.Lang.Hant;
        Item = await _db.Articles.AsNoTracking().Include(a => a.Translations)
            .FirstOrDefaultAsync(a => a.Id == id && a.Kind == "page" && a.Status == "published");
        if (Item is null) return NotFound();
        Text = Item.For(CurrentLang);
        Cat = Taxonomy.Cat(Item.Cat);
        ViewData["Title"] = Text?.Title ?? "";
        ViewData["Lang"] = CurrentLang;
        return Page();
    }
}
