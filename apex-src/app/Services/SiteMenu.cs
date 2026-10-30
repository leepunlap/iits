using Microsoft.EntityFrameworkCore;
using IitsNews.Data;

namespace IitsNews.Services;

public record MenuItem(int LegacyId, string Name, int ArticleCount, List<MenuItem> Children);

/// <summary>
/// Builds the site navigation by MERGING the two sites: the top-level section tree carried
/// over from the old ycltesthk CMS (148 ColumnList rows), filtered to the branches that
/// actually hold published articles, so the menu reflects real content rather than the old
/// site's dead menu parents.
///
/// Cached for the process lifetime of a request scope — the tree changes only on import.
/// </summary>
public class SiteMenu
{
    private readonly AppDb _db;
    private static List<MenuItem>? _cache;
    private static readonly object _lock = new();

    public SiteMenu(AppDb db) => _db = db;

    // Old-site sections that are structural plumbing, not navigation a reader should see.
    private static readonly HashSet<string> Hidden = new()
    { "首頁", "首页内容", "手机首页内容", "登录", "注册", "轮播图下方", "右侧悬浮" };

    public static void Invalidate() { lock (_lock) _cache = null; }

    public async Task<List<MenuItem>> GetAsync()
    {
        if (_cache is not null) return _cache;

        var sections = await _db.Sections.AsNoTracking().ToListAsync();
        var counts = await _db.Articles.AsNoTracking()
            .Where(a => a.Status == "published" && a.LegacySectionId != null)
            .GroupBy(a => a.LegacySectionId!.Value)
            .Select(g => new { Id = g.Key, N = g.Count() })
            .ToDictionaryAsync(x => x.Id, x => x.N);

        int Count(int id) => counts.TryGetValue(id, out var n) ? n : 0;

        var byParent = sections.GroupBy(s => s.LegacyParentId).ToDictionary(g => g.Key, g => g.ToList());

        List<MenuItem> Build(int parent)
        {
            if (!byParent.TryGetValue(parent, out var kids)) return new();
            var outp = new List<MenuItem>();
            foreach (var s in kids.OrderByDescending(s => s.Order).ThenBy(s => s.LegacyId))
            {
                if (Hidden.Contains(s.Name)) continue;
                var children = Build(s.LegacyId);
                var total = Count(s.LegacyId) + children.Sum(c => c.ArticleCount);
                if (total == 0) continue;               // a branch with nothing to read is not navigation
                outp.Add(new MenuItem(s.LegacyId, s.Name, total, children));
            }
            return outp;
        }

        var menu = Build(0);
        lock (_lock) _cache = menu;
        return menu;
    }

    /// <summary>Every section id in a branch, so a parent page lists its children's articles too.</summary>
    public async Task<List<int>> BranchIdsAsync(int legacyId)
    {
        var all = await _db.Sections.AsNoTracking()
            .Select(s => new { s.LegacyId, s.LegacyParentId }).ToListAsync();
        var ids = new List<int> { legacyId };
        for (var i = 0; i < ids.Count; i++)
            ids.AddRange(all.Where(s => s.LegacyParentId == ids[i]).Select(s => s.LegacyId));
        return ids.Distinct().ToList();
    }
}
