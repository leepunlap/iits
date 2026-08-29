using System.Text.RegularExpressions;

namespace IitsNews.Data;

public static class ArticleExtensions
{
    // Old-CMS bodies put images in BOTH src= attributes and inline CSS url(...), so match either.
    private static readonly Regex ImgRx = new(
        """(?:src\s*=\s*["']|url\(\s*["']?)(?<u>[^"')]+\.(?:jpe?g|png|gif|webp))""",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex TagRx = new("<[^>]+>", RegexOptions.Compiled);

    /// <summary>First image in the body, normalised — bodies carry "/../../upload/..." which
    /// the browser resolves to "/upload/...". Returns null when the article has no image.</summary>
    public static string? FirstImage(this ArticleTranslation? t)
    {
        if (t is null || string.IsNullOrEmpty(t.BodyHtml)) return null;
        var m = ImgRx.Match(t.BodyHtml);
        if (!m.Success) return null;
        var u = m.Groups["u"].Value.Trim().Replace("&quot;", "").Replace("&#34;", "");
        if (u.StartsWith("http", StringComparison.OrdinalIgnoreCase)) return u;
        while (u.StartsWith("/..")) u = u[3..];
        if (!u.StartsWith('/')) u = "/" + u;
        return u;
    }

    /// <summary>Plain-text opening of the body, for card summaries.</summary>
    public static string Excerpt(this ArticleTranslation? t, int chars = 88)
    {
        if (t is null || string.IsNullOrEmpty(t.BodyHtml)) return "";
        var s = System.Net.WebUtility.HtmlDecode(TagRx.Replace(t.BodyHtml, " "));
        s = Regex.Replace(s, @"\s+", " ").Trim();
        return s.Length <= chars ? s : s[..chars].TrimEnd() + "…";
    }
}
