using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;

namespace IitsNews.Pages.News;

/// <summary>
/// This route used to list every published article on the site under the OLD CMS section
/// names — 圖片集, 媒體電視, 通知公告 — which made it a second, competing navigation of the
/// whole site, reached from the most prominent link on the home page. Every article is now
/// on its category page, with the long tail behind that section's "view all".
/// The route survives only to carry old links; /news/item/{id} is unaffected.
/// </summary>
public class IndexModel : PageModel
{
    public IActionResult OnGet(string? lang)
    {
        var l = Data.Lang.IsKnown(lang) ? lang! : Data.Lang.Hant;
        return RedirectPermanent($"/c/news?lang={l}");
    }
}
