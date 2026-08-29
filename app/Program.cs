using Microsoft.EntityFrameworkCore;
using IitsNews.Data;
using IitsNews.Services;

var builder = WebApplication.CreateBuilder(args);

// systemd integration for the Linux/staging host. Harmless under IIS on Windows —
// the unit is Type=notify, so without this systemd waits for a readiness signal that
// never arrives and marks the service failed.
builder.Host.UseSystemd();

builder.Services.AddRazorPages();

// SQLite. Resolve a relative Data Source against ContentRootPath so the working
// directory cannot decide which database file gets opened, and create the directory
// if it is missing — otherwise the first run fails with an unhelpful "unable to open
// database file".
var cs = builder.Configuration.GetConnectionString("Default");
if (string.IsNullOrWhiteSpace(cs))
    cs = "Data Source=data/iits.db";

var csb = new Microsoft.Data.Sqlite.SqliteConnectionStringBuilder(cs);
if (!Path.IsPathRooted(csb.DataSource))
    csb.DataSource = Path.Combine(builder.Environment.ContentRootPath, csb.DataSource);
Directory.CreateDirectory(Path.GetDirectoryName(csb.DataSource)!);
cs = csb.ToString();

builder.Services.AddDbContext<AppDb>(o => o.UseSqlite(cs));
builder.Services.AddScoped<ContentImporter>();

builder.WebHost.UseUrls(builder.Configuration["Listen"] ?? "http://127.0.0.1:5099");

var app = builder.Build();

// --- one-shot CLI modes, so there is no separate migration tool to keep in sync ---
if (args.Contains("--migrate") || args.Contains("--import"))
{
    using var scope = app.Services.CreateScope();
    var db = scope.ServiceProvider.GetRequiredService<AppDb>();

    Console.WriteLine($"Database: {csb.DataSource}");
    Console.WriteLine("Applying schema...");
    await db.Database.EnsureCreatedAsync();

    if (args.Contains("--import"))
    {
        var i = Array.IndexOf(args, "--import");
        var root = (i >= 0 && i + 1 < args.Length && !args[i + 1].StartsWith("--"))
            ? args[i + 1]
            : app.Configuration["ImportRoot"] ?? "./migration";

        Console.WriteLine($"Importing from {root} ...");
        var res = await scope.ServiceProvider.GetRequiredService<ContentImporter>().ImportAsync(root);

        Console.WriteLine($"  articles created : {res.ArticlesCreated}");
        Console.WriteLine($"  articles updated : {res.ArticlesUpdated}");
        Console.WriteLine($"  sections         : {res.Sections}");
        Console.WriteLine($"  skipped          : {res.Skipped}");
        if (res.Warnings.Count > 0)
        {
            Console.WriteLine($"  warnings         : {res.Warnings.Count}");
            foreach (var w in res.Warnings.Take(25)) Console.WriteLine($"    - {w}");
            if (res.Warnings.Count > 25) Console.WriteLine($"    ... and {res.Warnings.Count - 25} more");
        }
    }
    return;
}

app.UseStaticFiles();
app.UseRouting();
app.MapRazorPages();
app.MapGet("/healthz", () => Results.Ok(new { status = "ok", utc = DateTime.UtcNow }));

app.Run();
