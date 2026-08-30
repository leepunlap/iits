namespace IitsNews.Data;

/// <summary>
/// Language tags used throughout. Kept as plain strings so adding a language
/// is data, not a schema change.
/// </summary>
public static class Lang
{
    public const string Hant = "zh-Hant";
    public const string Hans = "zh-Hans";
    public const string En = "en";

    public static readonly string[] All = { Hant, Hans, En };

    /// <summary>Compact label for the nav selector — the reader's own name for each script.</summary>
    public static string Short(string code) => code switch
    {
        Hant => "繁",
        Hans => "简",
        En   => "EN",
        _    => code
    };

    public static string Label(string code) => code switch
    {
        Hant => "繁體",
        Hans => "简体",
        En => "English",
        _ => code
    };

    public static bool IsKnown(string? code) =>
        code is not null && Array.IndexOf(All, code) >= 0;
}

/// <summary>
/// One piece of content, independent of language.
/// Translations hang off this, so no language is privileged. Which one is
/// "canonical" is a policy decision that can change without a migration.
/// </summary>
public class Article
{
    public int Id { get; set; }

    /// <summary>News.ID from the old ycltesthk SQL Server database. Null for anything authored here.</summary>
    public int? LegacyId { get; set; }

    /// <summary>ColumnList.ID the item belonged to in the old CMS.</summary>
    public int? LegacySectionId { get; set; }

    /// <summary>Section name as it appeared in the old nav, for reference during review.</summary>
    public string Section { get; set; } = "";

    /// <summary>Simplified taxonomy replacing the old CMS's 50 sections. Five categories
    /// (tests / courses / news / experts / about); Sub is the track or strand within one.
    /// The original Section is kept untouched as provenance.</summary>
    public string Cat { get; set; } = "";
    public string Sub { get; set; } = "";

    /// <summary>article = titled news item; pageBody = untitled content block; empty = shell row.</summary>
    public string Kind { get; set; } = "article";

    public DateTime? PublishedAt { get; set; }
    public bool Pinned { get; set; }

    /// <summary>draft | published. Imported rows land as draft so nothing publishes itself.</summary>
    public string Status { get; set; } = "draft";

    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;

    public List<ArticleTranslation> Translations { get; set; } = new();

    /// <summary>
    /// Best translation for a requested language: exact match, then any other
    /// available one so a half-translated article still renders rather than 404s.
    /// </summary>
    public ArticleTranslation? For(string lang)
    {
        var exact = Translations.FirstOrDefault(t => t.Lang == lang);
        if (exact is not null) return exact;

        foreach (var fallback in Lang.All)
        {
            var t = Translations.FirstOrDefault(x => x.Lang == fallback);
            if (t is not null) return t;
        }
        return Translations.FirstOrDefault();
    }
}

/// <summary>One language version of an Article.</summary>
public class ArticleTranslation
{
    public int Id { get; set; }
    public int ArticleId { get; set; }
    public Article? Article { get; set; }

    // NOTE: this property shadows the static class `Lang` inside this type, so the
    // initializer must be fully qualified or it resolves to the property (CS0236).
    public string Lang { get; set; } = global::IitsNews.Data.Lang.Hant;
    public string Title { get; set; } = "";
    public string BodyHtml { get; set; } = "";
    public string Keywords { get; set; } = "";

    /// <summary>
    /// machine = mechanically converted or translated, not yet reviewed.
    /// human   = written or reviewed by a person. Publishing English requires this.
    /// </summary>
    public string Provenance { get; set; } = "human";

    public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;
}

/// <summary>A navigation section carried over from the old ColumnList tree.</summary>
public class Section
{
    public int Id { get; set; }
    public int LegacyId { get; set; }
    public int LegacyParentId { get; set; }
    public string Name { get; set; } = "";
    public string Type { get; set; } = "";
    public int Order { get; set; }
    public string LegacyUrl { get; set; } = "";
}

// ---------------------------------------------------------------------------
// Access model.
//
// Nothing below is used by the article pages. It exists now so that adding
// individual student logins later is INSERTs rather than a rewrite: access is
// decided by class membership, never by which account you happen to be.
// ---------------------------------------------------------------------------

public class User
{
    public int Id { get; set; }
    public string Username { get; set; } = "";
    public string DisplayName { get; set; } = "";

    /// <summary>admin | teacher | class | student</summary>
    public string Role { get; set; } = "student";

    public bool IsActive { get; set; } = true;

    /// <summary>True for the shared per-class credentials (L1..L4, yai) that predate individual accounts.</summary>
    public bool IsSharedAccount { get; set; }

    public List<Enrolment> Enrolments { get; set; } = new();
}

public class SchoolClass
{
    public int Id { get; set; }
    public string Code { get; set; } = "";   // L1, L2, L3, L4, yai
    public string Name { get; set; } = "";
    public int? Year { get; set; }
    public List<Enrolment> Enrolments { get; set; } = new();
}

public class Enrolment
{
    public int Id { get; set; }
    public int UserId { get; set; }
    public User? User { get; set; }
    public int ClassId { get; set; }
    public SchoolClass? Class { get; set; }

    /// <summary>teacher | student</summary>
    public string RoleInClass { get; set; } = "student";
}
