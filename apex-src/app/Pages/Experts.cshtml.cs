using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using IitsNews.Data;

namespace IitsNews.Pages;

/// <summary>
/// The expert roster used to be its own page. It now sits inline on the one About page, so
/// this route exists only to carry old links to the anchor.
/// </summary>
public class ExpertsModel : PageModel
{
    public IActionResult OnGet(string? lang)
    {
        var l = Data.Lang.IsKnown(lang) ? lang! : Data.Lang.Hant;
        return RedirectPermanent($"/c/about?lang={l}#experts");
    }
}
