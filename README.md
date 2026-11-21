# Bulk Tool — Downloader + Uploader + Pipeline + Multi-Page

Soban ka apna, full-fledged bulk tool — aik hi project, aik hi folder.
SkillNova ka koi code copy nahi: downloader open-source **yt-dlp** pe hai,
uploader **official YouTube Data API v3** pe, aur Facebook wala hissa
**Graph API** pe. Sirf personal use — apne / licensed content ke liye.

Pehle ye chaar hisse alag folders mein thay (V1 downloader, V2 uploader,
pipeline, multi-page) — ab sab **aik flat project** mein hai. Har script
akela bhi chalta hai, aur pipeline/multi in ko jodte hain.

## GUI App (buttons wali window)

Terminal ki bajaye buttons se chalana ho to **`run.bat` pe
double-click** karo — ya terminal se `python app.py`. Nayi GUI
**dark modern theme** mein hai: teen alag section cards
(**Download**, **YouTube Upload**, **Multi Upload**) — har
section ka apna rang aur baray saaf buttons. Upar **status**
nazar aata hai (● Ready / ● Chal raha hai / ● Ho gaya / ● Error)
aur neeche **progress bar** download ka percent live dikhati
hai. Andar se ye wahi terminal commands chalata hai, output
neeche **Live Log** mein live nazar aata hai:

| Button | Peeche wala command |
|---|---|
| Links Download Karo (Paste Wale) (Download card) | links `paste_links.txt` mein save, phir `python pipeline.py --download-only --quality <quality> --downloads <folder> --urls paste_links.txt` |
| Download Only (urls.txt wali list) (Download card) | `python pipeline.py --download-only --quality <quality> --downloads <folder>` |
| Sirf Check (Download card) | `python pipeline.py --check --downloads <folder>` |
| Pipeline Test — Pehli 1 Video (YouTube card) | `python pipeline.py --limit 1 --privacy <privacy> --quality <quality> --downloads <folder>` |
| Pipeline — Download + Upload (YouTube card) | `python pipeline.py --privacy <privacy> --quality <quality> --downloads <folder>` |
| Multi Check (Multi card) | `python multi_upload.py --check` |
| Multi Upload (Multi card) | `python multi_upload.py` |

- **Video Links box** (Download card) — **SAB SE AASAN tareeqa:**
  links seedha box mein paste karo (aik line = aik link —
  YouTube / TikTok / Facebook…) aur **Links Download Karo
  (Paste Wale)** dabao; `urls.txt` edit karne ki zaroorat nahi.
  Links `paste_links.txt` mein save ho ke download hoti hain
  (Quality aur Download Folder upar wale fields se lagte hain,
  Limit paste pe nahi lagta). Purana tareeqa — `urls.txt` wali
  list aur **Download Only (urls.txt wali list)** button — bhi
  mojood hai.
- **Limit** (optional, Download card): kitni videos — khaali =
  saari. Download Only aur Pipeline pe lagta hai (Pipeline Test
  pe hamesha 1 fix hai).
- **Target** (Multi card): sirf aik destination — preset
  `mind-maze-yt` / `mind-maze-fb` / `horror-fb` chuno ya khud
  likho; khaali = saare targets.
- **Privacy** (YouTube card): private / unlisted / public
  (default **private**) — sirf Pipeline wale buttons pe; Multi
  mein privacy queue ki har row se aati hai.
- **Quality** (Download card): 2160 = **4K** (default), 1440 =
  **2K**, 1080, 720 — sirf download wale actions pe lagti hai.
  Bari quality = bari file, slow download.
- **Download Folder** (Download card): **Browse…** se koi bhi
  folder chun sakte ho — downloads wahan jayengi. Entry mein
  default project ka `downloads/` folder pehle se likha hota
  hai, **Reset** usay wapas le aata hai. Upload flow bhi **usi
  folder** se videos uthata hai (`uploads.csv` wahi se banti
  hai), is liye folder badlo to pehle wali downloads naye folder
  mein nahi milengi — unhein wahan pehle se hona chahiye.
- **Stop** button chalti hui command ko band kar deta hai, aur
  command khatam honay pe log mein `KHATAM — exit code X` ata
  hai. **Project Folder Kholo** button project ka folder khol
  deta hai.
- tkinter Python ke sath **free** aata hai (python.org installer) —
  kuch alag install nahi karna. Agar window na khule to app saaf
  message de gi, aur terminal commands waise hi chalte rahenge.

## Features

- **Bulk Download (downloader.py)** — `urls.txt` se poori queue, hundreds
  of links; quality **selectable hai — default 2160 (4K), 1440 (2K),
  1080, 720** (`--quality` flag); download folder `--downloads`
  se badal sakte ho (default `downloads/`); 3 parallel fragments per video; aik
  sath max 3 videos; **3 retries**; videos ke beech 5s sleep;
  `download_archive.txt` se jo download ho gaya wo dobara nahi hota;
  aadhi download resume; live per-video progress; fail hui URLs
  `failed.txt` mein.
- **YouTube Upload (uploader.py)** — official YouTube Data API v3
  (`videos.insert`, OAuth 2.0, scope sirf `youtube.upload`), resumable
  upload (10 MB chunks), `uploads.csv` queue (title/description/tags/
  category/privacy), default privacy **private**, `uploaded.csv` archive
  (dobara upload nahi), `failed_uploads.csv`, aur `--check` mode
  (files + metadata validate — NO upload, NO login).
  Quota: **100 uploads/day** (Google docs, June 2026 se alag bucket);
  max file 256 GB.
- **End-to-End Pipeline (pipeline.py)** — `urls.txt` → download (uper
  wali settings + har video ki `.info.json` metadata save) →
  `uploads.csv` **khud ban jati hai** (title ≤100, description ≤5,000,
  tags ≤500, category auto-map) → uploader chal jata hai, default
  private. Modes: `--check`, `--download-only`, `--upload-only`,
  `--limit N`, `--privacy`, `--quality` (download quality,
  default 2160 = 4K), `--downloads <folder>` (download folder —
  check bhi usi folder ko scan karta hai).
- **Multi-Page (multi_upload.py + fb_uploader.py)** — Facebook Pages +
  YouTube channels, **aik hi tool**: `pages.json` registry (aik entry =
  aik page/channel, har destination ka alag token/auth aur alag data),
  queue mein **`target` column**, per-target records
  (`state/uploaded-<target>.csv`) — aik hi video do targets pe ja sakti
  hai, doosre pe galat skip nahi hoti. YouTube: per-channel OAuth
  folders. Facebook: Reels Graph API se publish, 3 phases
  (start → upload → finish, `video_state=PUBLISHED`).

## File map

| File | Kaam |
|---|---|
| `downloader.py` | Bulk downloader (yt-dlp + FFmpeg) |
| `uploader.py` | YouTube uploader — single channel (official API) |
| `pipeline.py` | End-to-end glue: download → uploads.csv → upload |
| `multi_upload.py` | Multi-page orchestrator (FB Pages + YT channels) |
| `fb_uploader.py` | Facebook Reels module (akela bhi chal sakta hai) |
| `pages.example.json` | Multi-page registry ki misaal → copy karke `pages.json` banao |
| `pages.json` | Tumhari asal registry — **GitHub pe NAHI** (.gitignore covered) |
| `uploads.example.csv` | Multi/target queue ki misaal → copy karke `uploads.csv` banao |
| `uploads.csv` | Asal queue — **GitHub pe NAHI**. Do formats neeche dekho |
| `urls.example.txt` | Download queue ki misaal → copy karke `urls.txt` banao |
| `urls.txt` | Download queue (aik line = aik URL) — **GitHub pe NAHI** |
| `requirements.txt` | yt-dlp + Google libs (FB ke liye sirf stdlib) |
| `tests/` | Logic tests — saari suites, no network, no login |
| `downloads/` | Downloaded videos + `.info.json` + thumbnails yahan |
| `videos/` | Uploader ke liye local videos yahan rakh sakte ho |
| `tokens/` | FB Page token files (per page) — **GitHub pe NAHI** |
| `auth/<channel-id>/` | YT OAuth per channel — **GitHub pe NAHI** |
| `state/` | Multi-page ke per-target uploaded/failed records |

### uploads.csv ke do formats (ye samajhna zaroori hai)

- **Pipeline/uploader format** (target ke baghair):
  `file,title,description,tags,category_id,privacy` — `pipeline.py`
  yahi format **likhta** hai aur `uploader.py` yahi parhta hai.
- **Multi format** (target ke sath): upar wale columns + `,target` —
  `uploads.example.csv` yahi hai, `multi_upload.py` yahi parhta hai.
- `uploader.py` multi wali queue bhi parh leta hai (target column ko
  ignore kar deta hai), lekin `multi_upload.py` ko pipeline wali queue
  pe **`--default-target <id>`** dena padta hai, warna target khaali
  honay pe error ayega.
- ⚠️ `pipeline.py` jab bhi chalta hai (—check समेत), wo `uploads.csv`
  ko **apne format mein overwrite** kar deta hai. Multi queue alag
  naam se save rakhna ho to `--queue` flag se doosri file use karo.

## Setup (Windows laptop — PowerShell)

1. **Python 3.10+** install karo (python.org ya `winget install Python.Python.3.12`)
2. Is folder mein:
   ```
   pip install -r requirements.txt
   ```
3. **FFmpeg** (video+audio merge ke liye — khaas tor pe 2K/4K pe
   video aur audio alag streams mein ate hain):
   ```
   winget install Gyan.FFmpeg
   ```
   Phir PowerShell band karke dobara kholo.

## QUICK START (isi order mein)

### Step 1 — Example files se asal files banao
```
copy pages.example.json pages.json
copy uploads.example.csv uploads.csv
copy urls.example.txt urls.txt
```
- `uploads.csv` mein aik `#` wali row **uncomment** karo aur `file`
  column mein apni asal video ka naam/path likho (video is folder
  ya `videos/` mein rakho). Baghair `uploads.csv` ke har `--check`
  FAIL hoga — queue pehle, check baad mein.
- `pages.json` mein placeholders abhi rehne do — `--check` sirf
  warning dega. Asal IDs/tokens account setup (neeche) se milenge.

### Step 2 — Downloader ka dry run (network chahiye)
```
python downloader.py --dry-run
```
Ye `urls.txt` ki URLs ko yt-dlp se sirf check karta hai, download
nahi karta — **network lazmi hai**. Kuch environments (jaise is VM)
se YouTube/Google hosts blocked hote hain (403) — wahan dry run ka
fail hona code ki ghalti nahi hai; asal dry run laptop pe hoga.

### Step 3 — Pipeline check
```
python pipeline.py --check
```
Ye `downloads/` scan karke `uploads.csv` banata hai aur phir
`uploader.py --check` chalata hai (NO download, NO upload, NO login).
**Note:** is ke liye `downloads/` mein kam az kam aik video **aur
us ki `.info.json`** honi chahiye — khaali `downloads/` pe ye
"koi video tayyar nahi" keh ke ruk jayega (ye expected hai).
Aur yaad rahe: ye step `uploads.csv` ko pipeline format mein
**overwrite** kar deta hai (uper wala note dekho).

### Step 4 — Multi-page check
```
python multi_upload.py --check
```
Registry + queue + files + limits validate karke per-target summary
deta hai (NO network, NO login). Agar Step 3 ne tumhari target wali
queue overwrite kar di hai to ya to example se `uploads.csv` wapas
copy karo, ya pipeline wali queue pe yun chalao:
```
python multi_upload.py --check --default-target mind-maze-yt
```

### Step 5 — Pehle asal tests (aik video, aik target)

**YouTube (single channel) — pehle one-time OAuth setup (neeche
"YouTube account setup" ke 7 steps), phir:**
```
python pipeline.py --limit 1
```
Pehli video **private** upload hogi. YouTube Studio mein check
karke phir public karna. Success = terminal pe `OK: https://youtu.be/...`
aur `uploaded.csv` mein entry.

**Facebook (aik page) — pehle Meta setup (neeche "Facebook account
setup"), `pages.json` mein asal Page ID + token file bharo, phir:**
```
python fb_uploader.py --check --file reel.mp4 --page-id <PAGE_ID> --token-file tokens/mind-maze-fb.page_token.txt
python multi_upload.py --target mind-maze-fb --limit 1
```
Success = Reel us page pe PUBLISHED, aur
`state/uploaded-mind-maze-fb.csv` mein entry.

## Command reference

```
# Downloader
python downloader.py                     # urls.txt ki poori queue download (default quality 2160 = 4K)
python downloader.py --quality 1440      # 2K pe download (choices: 720 / 1080 / 1440 / 2160)
python downloader.py --downloads "D:\Mind maze\Videos"   # downloads is folder me (default: project ka downloads/)
python downloader.py --dry-run           # sirf check (network chahiye)

# YouTube uploader (single channel)
python uploader.py --check               # files + metadata validate, NO upload/login
python uploader.py                       # asal upload (pehli dafa browser login)
python uploader.py --queue <file.csv>    # doosri queue file
python uploader.py --force               # pehle se uploaded bhi dobara

# Pipeline (end-to-end)
python pipeline.py --check               # uploads.csv banao + uploader --check
python pipeline.py --limit 1             # pehla test: sirf 1 URL, poora flow
python pipeline.py                       # poora end-to-end
python pipeline.py --download-only       # sirf download + uploads.csv
python pipeline.py --upload-only         # download skip, upload karo
python pipeline.py --privacy unlisted    # default private hai
python pipeline.py --quality 1440        # download quality: 2160=4K (default), 1440=2K, 1080, 720
python pipeline.py --downloads "D:\Mind maze\Videos"   # downloads is folder me + upload bhi wahi se (check pe bhi yahi folder scan hota hai)

# Multi-page
python multi_upload.py --check                       # sab validate, NO upload/login
python multi_upload.py --target mind-maze-yt --limit 1   # 1 video, 1 channel
python multi_upload.py --target mind-maze-fb --limit 1   # 1 Reel, 1 page
python multi_upload.py                               # poori queue, saare targets
python multi_upload.py --default-target mind-maze-yt # target khaali rows ke liye
python multi_upload.py --force                       # per-target archive ignore

# Facebook module akela
python fb_uploader.py --check --file <video> --page-id <ID> --token-file <file>
python fb_uploader.py --file <video> --page-id <ID> --token-file <file> --description "..."
```

## Queue formats

**urls.txt** — aik line = aik URL, `#` wali lines comment:
```
https://www.youtube.com/watch?v=aqz-KE-bpKQ
```

**uploads.csv (multi)** — `uploads.example.csv` dekho. Aik hi video
do targets pe bhejni ho to us ki **do rows** banao, sirf `target`
alag rakho.

## YouTube account setup (one-time, ~10 min)

Single-channel uploader ke liye (`client_secrets.json` **is folder**
mein) — multi-page ke liye wahi file har channel ke
`auth/<channel-id>/` folder mein jati hai, bas login har channel
ke apne Google account se hoga:

1. [Google Cloud Console](https://console.cloud.google.com/) → naya project banao
2. APIs & Services → Library → **YouTube Data API v3** → Enable
3. APIs & Services → Credentials → Create Credentials → **OAuth client ID**
4. Application type: **Desktop app** → Create
5. `client_secrets.json` download karke is folder mein rakho
   (multi ke liye: `auth/mind-maze-yt/client_secrets.json`)
6. `pip install -r requirements.txt`, phir `python uploader.py --check`
   (ya pipeline/multi wala check) — login nahi chahiye
7. Pehli asal run pe browser khulega — apne YouTube channel wale
   Google account se **Allow** karo. `token.json` save ho jayega,
   dobara login nahi mangega (jab tak revoke na karo).

Limits: title max 100 chars, description max 5,000, tags total
max 500, category default 22 (People & Blogs), privacy default
private. Quota **100 uploads/day**, midnight Pacific pe reset.

## Facebook account setup (per page, one-time)

1. **Meta developer account + aik Facebook app** banao
   (developers.facebook.com) — aik dafa hi karna hai.
2. Long-lived user token lo, phir Graph API Explorer / API call se
   `GET /me/accounts` chalao — saare pages ki list milegi, har page
   ke sath us ka **Page ID + Page access token**
   (permission: `pages_manage_posts`). Long-lived user token se
   bana Page token timer pe expire nahi hota.
3. Har page ka token alag file mein save karo, e.g.
   `tokens/mind-maze-fb.page_token.txt`, aur wahi path + Page ID
   `pages.json` mein bharo.
4. Tumhare **apne** pages ke liye Standard Access kaafi hai —
   App Review / Business Verification / Advanced Access sirf
   doosron ke pages connect karne pe chahiye.

Facebook pe queue ki `privacy`/`category_id`/`tags` columns use
nahi hotin — Reel ki description = `description` column (khaali
ho to title), aur video seedha PUBLISHED jati hai.

## Caveats — saaf baat

- **4K files bohat bari hoti hain** — download slow hoga aur disk
  space bhi zyada lagega; roz ke kaam ke liye 1080 ya 1440 aksar
  kaafi hota hai. YouTube ki 4K aam tor pe **webm** format mein
  aati hai (mp4 lazmi nahi) — uploader webm bhi accept karta hai.
  Aur agar source video hi 1080p ki hai to `--quality 2160` select
  karne se quality **nahi** barhe gi — best available (1080p) hi
  milegi, upscale nahi hota.
- **Facebook upload LIVE TEST nahi hua** — flow Meta docs/guides se
  verified hai (2026-11-19), asal pehla test laptop pe
  `--target mind-maze-fb --limit 1` se hoga.
- **Asal download/upload is VM se verify nahi ho saka** — VM se
  YouTube/Google hosts blocked hain (HTTP 403), aur asal upload ke
  liye tumhara Google OAuth / FB Page token laptop pe chahiye.
  Pehla asli verdict hamesha laptop test ka hoga.
- **Unverified YouTube API project** se upload ki hui videos
  **private hi rehti hain jab tak project audit na ho** — ye
  Google ki pabandi hai, tool ki nahi. Pehli video private rakh
  ke Studio mein check karna is liye bhi zaroori hai.
- **Secrets/tokens KABHI share mat karo, GitHub pe kabhi mat
  daalo:** `pages.json`, `tokens/`, `auth/`, `client_secrets.json`,
  `token.json` — `.gitignore` in sab ko cover karta hai, lekin
  push se pehle `git status` mein aik nazar phir bhi daal lena.
- Downloader ka 3-parallel download aur pipeline ka sequential
  flow alag hain: pipeline metadata (`.info.json`) ke liye
  sequential chalti hai; sirf download chahiye to `downloader.py`
  tez hai, lekin us se `.info.json` nahi banti.
- Sirf apne / licensed content ke liye — doosron ke videos
  re-upload karne ke liye nahi.

## Tests

```
python tests/test_downloader.py  # downloader logic (build_format) — ALL LOGIC TESTS PASS
python tests/test_uploader.py    # uploader logic — ALL LOGIC TESTS PASS
python tests/test_pipeline.py    # pipeline logic — ALL LOGIC TESTS PASS
python tests/test_multi.py       # multi + FB logic — ALL LOGIC TESTS PASS
python tests/test_app.py         # GUI command logic — ALL LOGIC TESTS PASS
```
Saari suites no-network / no-login hain. Downloader ka asal smoke
test Step 2 wala `--dry-run` hai, jo network mangta hai (uska
engine yt-dlp khud hai); test_downloader sirf us ki pure logic
(build_format, quality defaults) check karta hai.
