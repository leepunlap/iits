# Mirroring WeChat-hosted images

## The symptom

Article images rendered as a grey WeChat placeholder reading
**「此圖片來自微信公眾平台 未經允許不可引用」** — *this image is from the WeChat Official
Accounts platform, may not be cited without permission.*

## The cause

Bodies carried over from the old CMS embed images straight from WeChat's CDN,
`mmbiz.qpic.cn`. That host applies **Referer-based hotlink protection**: it serves the
real bytes to a request with no Referer, and the placeholder to a request whose Referer
is any other site. So a browser on our domain gets the placeholder, and the images look
permanently broken.

## Why that matters more than it looks

It is a silent dependency on somebody else's CDN. Even if the placeholder were not shown,
the pages would break the day WeChat expired those URLs, and nothing in the site would
have recorded that the images were never ours to begin with.

## The fix

Fetched every referenced image **server-side**, where the Referer check does not apply,
stored them locally, and rewrote the bodies to point at the local copies.

    48 distinct URLs fetched · 0 failures · 38 unique files after content-hash dedup · 21 MB
    114 URL occurrences rewritten across 11 translation rows / 5 articles
    0 references to mmbiz.qpic.cn remain

Files land in `/var/www/iits-staging/media/wx/`, named by the **sha256 of their content**
(first 20 hex). Content addressing means the same image referenced from several articles
is stored once, and a re-run is idempotent — the same bytes produce the same filename.

`wx_map.json` records the original URL for every mirrored file, so provenance is not lost.

## Still external

Two references to `statics.xiumi.us` (a Chinese article-layout service) remain. They are
in draft articles only and were left alone; mirror them the same way if those drafts are
ever published.

## Rights

These are the organisation's own WeChat posts, re-hosted on the organisation's own site.
The WeChat notice is aimed at third-party reuse, not at the account owner. If any image
turns out to have come from elsewhere, it should be removed rather than kept mirrored.
