using System.Text.RegularExpressions;

namespace IitsNews.Data;

public static class ArticleExtensions
{
    // Old-CMS bodies put images in BOTH src= attributes and inline CSS url(...), so match either.
    private static readonly Regex ImgRx = new(
        """(?:src\s*=\s*["']|url\(\s*["']?)(?<u>[^"')]+\.(?:jpe?g|png|gif|webp))""",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex TagRx = new("<[^>]+>", RegexOptions.Compiled);

    // A video article has no <img> at all, so the image extractor below finds nothing and the
    // listing card comes out blank. data-poster carries the mirrored video cover, letting the
    // card show a thumbnail without duplicating the image inside the article body.
    private static readonly Regex PosterRx = new(
        """data-poster\s*=\s*["'](?<u>[^"']+)["']""", RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex VideoRx = new(
        """<div[^>]*class\s*=\s*["'][^"']*\bvideo\b""", RegexOptions.IgnoreCase | RegexOptions.Compiled);

    /// <summary>True when the body embeds a video, so a card can badge it.</summary>
    public static bool HasVideo(this ArticleTranslation? t) =>
        t?.BodyHtml is { Length: > 0 } b && VideoRx.IsMatch(b);

    /// <summary>First image in the body, normalised — bodies carry "/../../upload/..." which
    /// the browser resolves to "/upload/...". Returns null when the article has no image.</summary>
    public static string? FirstImage(this ArticleTranslation? t)
    {
        if (t is null || string.IsNullOrEmpty(t.BodyHtml)) return null;
        var pm = PosterRx.Match(t.BodyHtml);          // an explicit poster wins over any inline image
        if (pm.Success) return pm.Groups["u"].Value.Trim();
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
