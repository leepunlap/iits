using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;

namespace IitsNews.Pages;

/// <summary>The roster moved under About. /experts was linked from the nav for a while, so
/// it redirects rather than 404s — a moved page should never punish whoever kept the link.</summary>
public class ExpertsRedirectModel : PageModel
{
    public IActionResult OnGet(string? lang) =>
        RedirectPermanent("/c/about/experts" + (string.IsNullOrEmpty(lang) ? "" : "?lang=" + Uri.EscapeDataString(lang)));
}
