# ycltesthk.com — static export for IIS

Exported from the NUC's IITS staging app (127.0.0.1:5099, .NET/Kestrel) on 2026-09-10 22:39.

* 732 pages in three languages: default (zh-Hant) at the root, `zh-Hans/` and `en/` beside it
* `/assets/` and `/media/` copied from /var/www/iits-staging
* `/upload/...` is not duplicated — `web.config` rewrites it to `/media/...` (same files)
* every page is a directory with `index.html`, so IIS default documents serve clean URLs

## IIS setup
1. Copy this whole folder to e.g. `C:\inetpub\ycltesthk`.
2. IIS Manager → Sites → Add Website: name `ycltesthk`, physical path that folder,
   binding `http` on port 80 with hostname `ycltesthk.com` (add `www.ycltesthk.com` as a second binding).
3. Application pool: .NET CLR version **No Managed Code** (it is pure static), pipeline Integrated.
4. Install the **URL Rewrite** module (needed for the /upload/ rule). If you cannot install it,
   tell me and I will duplicate the media tree instead.
5. Make sure the `web.config` above sits in the site root (it does).
6. Browse `http://localhost/` on the box: the homepage must render with images.
   Test an article, e.g. `http://localhost/news/item/103/` and `http://localhost/en/`.

## Not included on purpose
* `/admin/` and the article CMS: those are services on the NUC (auth realm :8790, app :5099).
  Static IIS cannot host them. Say the word and we either (a) keep the CMS on the NUC and
  reverse-proxy just `/admin/` from IIS to the NUC, or (b) take the CMS off the public site.
* Language switcher: rewritten to the static `/en/` and `/zh-Hans/` trees.

## After it works on the Windows box
Point `ycltesthk.com` (+`www`) A records at the Windows server's IP, then issue a certificate
there for both names. The old 騰雲 site should be kept in a folder, not deleted, until the new
one is verified in a browser.
