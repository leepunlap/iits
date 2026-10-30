using System.Text;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using IitsNews.Data;

namespace IitsNews.Services;

/// <summary>
/// Seeds the database from the Phase 03 extraction produced on the Windows box:
///   articles/*.md          one file per old News row, YAML front-matter + raw body HTML
///   data/navigation.json   the 148-entry ColumnList tree
///
/// Idempotent: matches on Article.LegacyId, so re-running updates rather than duplicates.
/// Everything lands as Status=draft. Nothing publishes itself.
/// </summary>
public class ContentImporter
{
    private readonly AppDb _db;
    public ContentImporter(AppDb db) => _db = db;

    public record Result(int ArticlesCreated, int ArticlesUpdated, int Sections, int Skipped, List<string> Warnings);

    public async Task<Result> ImportAsync(string root)
    {
        var warnings = new List<string>();
        var articlesDir = Path.Combine(root, "articles");
        var navFile = Path.Combine(root, "data", "navigation.json");

        if (!Directory.Exists(articlesDir))
            throw new DirectoryNotFoundException($"No articles directory at {articlesDir}");

        var sections = await ImportSectionsAsync(navFile, warnings);

        int created = 0, updated = 0, skipped = 0;

        foreach (var path in Directory.EnumerateFiles(articlesDir, "*.md").OrderBy(p => p))
        {
            var raw = await File.ReadAllTextAsync(path, Encoding.UTF8);
            var (meta, body) = SplitFrontMatter(raw);

            if (meta.Count == 0)
            {
                warnings.Add($"{Path.GetFileName(path)}: no front-matter, skipped");
                skipped++;
                continue;
            }

            if (!int.TryParse(Get(meta, "id"), out var legacyId))
            {
                warnings.Add($"{Path.GetFileName(path)}: unparseable id, skipped");
                skipped++;
                continue;
            }

            var kind = Get(meta, "kind");

            // 'empty' rows are shells in the old CMS with no usable content. They are
            // imported as drafts so the record exists and the URL can still 301, but
            // they are not something anyone should have to review.
            var lang = Get(meta, "lang");
            if (!Lang.IsKnown(lang))
            {
                // 'und' means the detector found no distinguishing characters either way.
                // Park it as zh-Hant (the site's primary) and flag it for review.
                if (kind != "empty")
                    warnings.Add($"id {legacyId}: language undetermined, parked as {Lang.Hant}");
                lang = Lang.Hant;
            }

            var article = await _db.Articles
                .Include(a => a.Translations)
                .FirstOrDefaultAsync(a => a.LegacyId == legacyId);

            var isNew = article is null;
            article ??= new Article { LegacyId = legacyId };

            article.LegacySectionId = int.TryParse(Get(meta, "classId"), out var cid) ? cid : null;
            article.Section = Get(meta, "section");
            article.Kind = string.IsNullOrWhiteSpace(kind) ? "article" : kind;
            article.Pinned = Get(meta, "pinned") == "true";
            article.PublishedAt = ParseLegacyDate(Get(meta, "date"));
            article.Status = "draft";
            article.UpdatedAt = DateTime.UtcNow;

            var title = Get(meta, "title");
            if (string.IsNullOrWhiteSpace(title))
                title = article.Kind == "pageBody"
                    ? $"[page content] {article.Section}".Trim()
                    : $"[untitled #{legacyId}]";

            var tr = article.Translations.FirstOrDefault(t => t.Lang == lang);
            if (tr is null)
            {
                tr = new ArticleTranslation { Lang = lang };
                article.Translations.Add(tr);
            }
            tr.Title = title;
            tr.BodyHtml = body;
            tr.Keywords = Get(meta, "keywords");
            tr.Provenance = "human";      // this is the original authored text
            tr.UpdatedAt = DateTime.UtcNow;

            if (isNew) { _db.Articles.Add(article); created++; } else updated++;
        }

        await _db.SaveChangesAsync();
        return new Result(created, updated, sections, skipped, warnings);
    }

    private async Task<int> ImportSectionsAsync(string navFile, List<string> warnings)
    {
        if (!File.Exists(navFile))
        {
            warnings.Add($"navigation.json not found at {navFile}; sections not imported");
            return 0;
        }

        using var doc = JsonDocument.Parse(await File.ReadAllTextAsync(navFile, Encoding.UTF8));
        var count = 0;

        // Entities Added in this loop are NOT yet visible to FirstOrDefaultAsync (it queries
        // the database, and SaveChanges only runs at the end). Without a local index, two
        // entries sharing a LegacyId each get Added and the insert dies on IX_Sections_LegacyId.
        var pending = new Dictionary<int, Section>();
        var blank = 0;

        foreach (var el in doc.RootElement.EnumerateArray())
        {
            var legacyId = el.TryGetProperty("id", out var idEl) && idEl.ValueKind == JsonValueKind.Number
                ? idEl.GetInt32() : 0;

            // An id of 0 with no name carries no information — skip rather than manufacture
            // meaningless rows. Counted and reported so a bad extraction is loud, not silent.
            if (legacyId == 0 && string.IsNullOrWhiteSpace(Str(el, "name"))) { blank++; continue; }

            if (!pending.TryGetValue(legacyId, out var s))
            {
                s = await _db.Sections.FirstOrDefaultAsync(x => x.LegacyId == legacyId)
                    ?? new Section { LegacyId = legacyId };
                pending[legacyId] = s;
            }

            s.LegacyParentId = el.TryGetProperty("parentId", out var p) ? p.GetInt32() : 0;
            s.Name = Str(el, "name");
            s.Type = Str(el, "type");
            s.Order = el.TryGetProperty("order", out var o) && o.ValueKind == JsonValueKind.Number ? o.GetInt32() : 0;
            s.LegacyUrl = Str(el, "legacyUrl");

            if (s.Id == 0 && _db.Entry(s).State == EntityState.Detached) _db.Sections.Add(s);
            count++;
        }

        if (blank > 0)
            warnings.Add($"navigation.json: {blank} of {blank + count} entries had no id and no name — " +
                         "the ColumnList extraction produced empty records; sections need re-extracting");

        await _db.SaveChangesAsync();
        return count;
    }

    private static string Str(JsonElement el, string name) =>
        el.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String ? (v.GetString() ?? "") : "";

    /// <summary>
    /// Minimal front-matter reader. The format is the one Phase 03 emitted, not general YAML:
    /// flat `key: value` lines, single-quoted strings with '' for a literal quote.
    /// Deliberately dependency-free — the input is known and regular.
    /// </summary>
    private static (Dictionary<string, string> meta, string body) SplitFrontMatter(string raw)
    {
        var meta = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var norm = raw.Replace("\r\n", "\n");

        if (!norm.StartsWith("---\n")) return (meta, raw);

        var end = norm.IndexOf("\n---\n", 4, StringComparison.Ordinal);
        if (end < 0) return (meta, raw);

        foreach (var line in norm[4..end].Split('\n'))
        {
            var colon = line.IndexOf(':');
            if (colon <= 0) continue;

            var key = line[..colon].Trim();
            var val = line[(colon + 1)..].Trim();

            // Skip the inline-object fields (langEvidence, needsCleaning, translations);
            // they are review metadata, not content.
            if (val.StartsWith('{')) continue;

            if (val.Length >= 2 && val[0] == '\'' && val[^1] == '\'')
                val = val[1..^1].Replace("''", "'");

            meta[key] = val;
        }

        return (meta, norm[(end + 5)..]);
    }

    private static string Get(Dictionary<string, string> m, string k) =>
        m.TryGetValue(k, out var v) ? v : "";

    /// <summary>
    /// The old Putdate column is nvarchar, holding a mix of '2026-08-13' and
    /// '2026/5/7 16:55:56'. Anything unparseable becomes null rather than throwing.
    /// </summary>
    private static DateTime? ParseLegacyDate(string s)
    {
        if (string.IsNullOrWhiteSpace(s)) return null;
        return DateTime.TryParse(s, System.Globalization.CultureInfo.InvariantCulture,
                                 System.Globalization.DateTimeStyles.AssumeUniversal |
                                 System.Globalization.DateTimeStyles.AdjustToUniversal,
                                 out var dt)
            ? dt
            : null;
    }
}
