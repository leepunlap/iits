using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;
using IitsNews.Data;

namespace IitsNews.Pages.News;

public class ItemModel : PageModel
{
    private readonly AppDb _db;
    public ItemModel(AppDb db) => _db = db;

    public Article? Item { get; private set; }
    public ArticleTranslation? Text { get; private set; }
    public string CurrentLang { get; private set; } = Data.Lang.Hant;

    public async Task<IActionResult> OnGetAsync(int id, string? lang)
    {
        CurrentLang = Data.Lang.IsKnown(lang) ? lang! : Data.Lang.Hant;

        Item = await _db.Articles
            .Include(a => a.Translations)
            .FirstOrDefaultAsync(a => a.Id == id && a.Status == "published");

        if (Item is null) return NotFound();

        Text = Item.For(CurrentLang);
        ViewData["Lang"] = Text?.Lang ?? CurrentLang;
        ViewData["Title"] = Text?.Title ?? "新聞";
        return Page();
    }
}
