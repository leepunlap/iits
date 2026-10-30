using Microsoft.AspNetCore.Mvc.RazorPages;

namespace IitsNews.Pages;

/// <summary>
/// Admin pages inherit their identity from nginx, not from any login this app performs.
///
/// nginx guards /admin/ with auth_request against the existing checker.py service and,
/// if that service can return a username, passes it down as X-Auth-User. This app never
/// sees a password and never issues a session.
///
/// The safety of trusting a request header rests entirely on the app binding to
/// 127.0.0.1, so only nginx can reach it. If that ever changes, this becomes a
/// full authentication bypass — see README.
/// </summary>
public abstract class AdminPageModel : PageModel
{
    protected string AdminUser =>
        Request.Headers.TryGetValue("X-Auth-User", out var v) && !string.IsNullOrWhiteSpace(v)
            ? v.ToString()
            : "admin";

    public override void OnPageHandlerExecuting(Microsoft.AspNetCore.Mvc.Filters.PageHandlerExecutingContext ctx)
    {
        ViewData["IsAdmin"] = true;
        base.OnPageHandlerExecuting(ctx);
    }
}
