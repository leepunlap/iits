using Microsoft.EntityFrameworkCore;

namespace IitsNews.Data;

public class AppDb : DbContext
{
    public AppDb(DbContextOptions<AppDb> options) : base(options) { }

    public DbSet<Article> Articles => Set<Article>();
    public DbSet<ArticleTranslation> Translations => Set<ArticleTranslation>();
    public DbSet<Section> Sections => Set<Section>();
    public DbSet<User> Users => Set<User>();
    public DbSet<SchoolClass> Classes => Set<SchoolClass>();
    public DbSet<Enrolment> Enrolments => Set<Enrolment>();

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<Article>(e =>
        {
            e.HasIndex(x => x.LegacyId).IsUnique().HasFilter("\"LegacyId\" IS NOT NULL");
            e.HasIndex(x => x.Status);
            e.HasIndex(x => x.PublishedAt);
            e.HasMany(x => x.Translations)
             .WithOne(t => t.Article!)
             .HasForeignKey(t => t.ArticleId)
             .OnDelete(DeleteBehavior.Cascade);
        });

        // One translation per language per article. This is what makes the three
        // languages siblings rather than duplicated documents.
        b.Entity<ArticleTranslation>()
         .HasIndex(x => new { x.ArticleId, x.Lang })
         .IsUnique();

        b.Entity<Section>().HasIndex(x => x.LegacyId).IsUnique();

        b.Entity<User>().HasIndex(x => x.Username).IsUnique();
        b.Entity<SchoolClass>().HasIndex(x => x.Code).IsUnique();

        b.Entity<Enrolment>(e =>
        {
            e.HasIndex(x => new { x.UserId, x.ClassId }).IsUnique();
            e.HasOne(x => x.User).WithMany(u => u.Enrolments).HasForeignKey(x => x.UserId);
            e.HasOne(x => x.Class).WithMany(c => c.Enrolments).HasForeignKey(x => x.ClassId);
        });
    }
}
