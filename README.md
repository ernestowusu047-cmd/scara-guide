# SCARA sports guide

Builds a small TV guide for SCARA's live sports channels twice a day, for free, on GitHub.

`build_guide.py` downloads epg.pw's full free guide (about 50 MB compressed, 500 MB of XML),
keeps only the programmes of the channels in `live.m3u` and in the Sports group of iptv-org's
list, for the next day and a half, and saves them as `guide.xml.gz` (tens of KB). The app reads
that small file instead of the huge one.

## Set it up (once)

1. On github.com: **New repository**, name it `scara-guide`, choose **Public**, then **Create repository**.
2. Click **uploading an existing file** and drag in `build_guide.py`, `live.m3u` and this
   `README.md`. Click **Commit changes**.
3. **Add file > Create new file**. As the name, type `.github/workflows/build-guide.yml` (the
   slashes create the folders). Paste in the contents of `.github/workflows/build-guide.yml` from
   this folder, then **Commit changes**.
4. Open the **Actions** tab. If GitHub asks, allow workflows. Click **Build guide**, then
   **Run workflow**. After a few minutes, `guide.xml` and `guide.xml.gz` appear in the repository.
5. The guide's address is then:

   `https://raw.githubusercontent.com/<your-github-name>/scara-guide/main/guide.xml.gz`

   Put it in the app (`GUIDE_URL` in `app/src/main/java/com/streamflix/tv/data/LiveGuide.kt`),
   or add it to m3u4u as your EPG source.

From then on it rebuilds itself at 05:20 and 17:20 UTC every day.

## When you change the channels

If you edit the app's `app/src/main/assets/live.m3u`, upload the new copy over `live.m3u` here
too, so the guide follows. The iptv-org channels are picked up by themselves.

## Run it on a PC instead

`python build_guide.py` (Python 3.9 or newer, nothing else to install). It takes a few minutes and
writes `guide.xml` and `guide.xml.gz` next to it.
