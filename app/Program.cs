using Microsoft.EntityFrameworkCore;
using IitsNews.Data;
using IitsNews.Services;

var builder = WebApplication.CreateBuilder(args);

// The unit is Type=notify, which requires the app to signal readiness via sd_notify.
// Without this it would start, never notify, and systemd would time it out as failed.
// Also routes logging to journald with proper priority levels. No-op off systemd.
builder.Host.UseSystemd();

builder.Services.AddRazorPages();
builder.Services.AddDbContext<AppDb>(o =>
    o.UseNpgsql(builder.Configuration.GetConnectionString("Default")));
builder.Services.AddScoped<ContentImporter>();

// Bind to loopback only. The app trusts nginx to have authenticated /admin/ via
// auth_request; that trust is only safe because nothing else can reach this port.
builder.WebHost.UseUrls(builder.Configuration["Listen"] ?? "http://127.0.0.1:5099");

var app = builder.Build();

// --- one-shot CLI modes, so there is no separate migration tool to keep in sync ---
if (args.Contains("--migrate") || args.Contains("--import"))
{
    using var scope = app.Services.CreateScope();
    var db = scope.ServiceProvider.GetRequiredService<AppDb>();

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
