using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using IitsNews.Data;

namespace IitsNews.Pages.Admin;

public class EditModel : AdminPageModel
{
    private readonly AppDb _db;
    public EditModel(AppDb db) => _db = db;

    public Article Item { get; private set; } = new();
    public string EditLang { get; private set; } = Data.Lang.Hant;
    public ArticleTranslation? Text { get; private set; }
    public string? Saved { get; private set; }

    public async Task<IActionResult> OnGetAsync(int id, string? lang, string? saved)
    {
        EditLang = Data.Lang.IsKnown(lang) ? lang! : Data.Lang.Hant;
        Saved = saved;
        ViewData["Title"] = id == 0 ? "新增文章" : "編輯文章";

        if (id == 0)
        {
            Item = new Article { Kind = "article", Status = "draft" };
            return Page();
        }

        var found = await _db.Articles.Include(a => a.Translations).FirstOrDefaultAsync(a => a.Id == id);
        if (found is null) return NotFound();

        Item = found;
        Text = found.Translations.FirstOrDefault(t => t.Lang == EditLang);
        return Page();
    }

    public async Task<IActionResult> OnPostAsync(
        int id, string lang, string title, string bodyHtml,
        string? keywords, string? publishedAt, string? action)
    {
        if (!Data.Lang.IsKnown(lang)) lang = Data.Lang.Hant;

        Article? article = id == 0
            ? null
            : await _db.Articles.Include(a => a.Translations).FirstOrDefaultAsync(a => a.Id == id);

        if (article is null)
        {
            article = new Article { Kind = "article", Status = "draft", CreatedAt = DateTime.UtcNow };
            _db.Articles.Add(article);
        }

        if (DateTime.TryParse(publishedAt, out var pub))
            article.PublishedAt = DateTime.SpecifyKind(pub, DateTimeKind.Utc);

        var tr = article.Translations.FirstOrDefault(t => t.Lang == lang);
        if (tr is null)
        {
            tr = new ArticleTranslation { Lang = lang, Provenance = "human" };
            article.Translations.Add(tr);
        }

        tr.Title = title?.Trim() ?? "";
        tr.BodyHtml = bodyHtml ?? "";
        tr.Keywords = keywords?.Trim() ?? "";
        tr.UpdatedAt = DateTime.UtcNow;

        // Editing a machine-translated version by hand is what makes it reviewed.
        // This is the mechanism behind "English pages editable after translation".
        if (tr.Provenance == "machine") tr.Provenance = "human";

        if (action == "publish") article.Status = "published";
        if (action == "unpublish") article.Status = "draft";
        article.UpdatedAt = DateTime.UtcNow;

        await _db.SaveChangesAsync();
        return Redirect($"/admin/edit/{article.Id}?lang={lang}&saved=1");
    }
}
