# AInstein

An automated science feed that respects both your attention and other
people's copyright.

It pulls from about sixty sources — arXiv, Crossref, open-access journals, space agencies, labs and science magazines — scores what's worth
reading, rewrites the openly-licensed parts into plain language, and
publishes a scrollable feed — four tabs, a searchable directory of the
world's particle physics experiments, and a daily refresh that runs itself.

**[Live feed →](https://AyaRudek.github.io/ainstein/)** · built in public
[@AyaSciComm](https://x.com/AyaSciComm)

---

## Why it exists

Keeping up with science is work: the good material is scattered across
preprint servers, agency press rooms and paywalled journals, and none of it
is shaped like something you'd read on a phone. Meanwhile every other app on
that phone is engineered to be effortless. AInstein takes the engineering
seriously in the other direction.

## The interesting design decision

Most aggregators either scrape article text (legally dicey) or show bare
headlines (useless). AInstein splits the difference by asking, per source,
*what am I actually allowed to do with this?*

| Policy | What the AI sees | What gets published |
|---|---|---|
| `abstract_ok` | the abstract | a full rewritten card + link |
| `headline_only` | **nothing** | headline, date, link |

The split is enforced in code, not in a prompt — `headline_only` text is
discarded at the network boundary, so it can't reach the model even by
accident.

This is also how AInstein covers *Nature*, *Science* and *PRL* without
touching them: it asks **Crossref** — open CC0 metadata — which papers those
journals published, then takes the abstract only where the publisher
deposited one for reuse. The journal becomes a *quality filter* rather than a
content source, which solves the real weakness of an arXiv-only feed: nothing
there has been peer reviewed.

Full reasoning per source in **[SOURCES.md](SOURCES.md)**.

## Structure

```
ainstein/
  models.py        Item, Experiment, and the Policy enum that governs both
  sources/
    arxiv.py       preprints, Atom API, 1 req / 3 s
    crossref.py    the peer-review filter
    feeds.py       agency RSS; drops text it has no right to
  score.py         the taste layer — the file worth tuning
  link.py          attaches items to experiments, and vetoes name collisions
  rewrite.py       abstract -> card, via Claude
  build.py         entry point
config.yaml        sources, interests, limits, experiment directory
data/feed.json     the output; the front end reads only this
web/template.html  the page source, with a __FEED_JSON__ placeholder
tools/embed.py     inlines the feed into index.html
index.html         what GitHub Pages serves
```

`index.html` fetches `./data/feed.json` when served, and falls back to an
inlined snapshot so the page still works opened as a bare file. After a
rebuild, run `python tools/embed.py` to refresh that snapshot.

Two layers of content, deliberately:

- **Inventory** — the experiment directory in `config.yaml`. ATLAS and DUNE
  don't have news every day, but they always have an identity: where they
  are, what they measure, what stage they're at.
- **Pulse** — what actually moved this week, attached to that inventory. If
  nothing moved, the card says so instead of disappearing.

`link.py` joins the two by matching experiment names in free text, and it is
built for precision over recall: a wrong link on a directory card is worse
than a missing one. Short or all-caps acronyms must match case-sensitively;
a leading `/` or `-` disqualifies a match; and known collisions are vetoed
outright — the comet **3I/ATLAS** is not the detector at CERN, and the first
version of the matcher cheerfully confused the two.

## Today: a feed that ends

The page has two halves. The **Library** is what lasts — the directory,
the classics, what to watch, what to read. **Today** is the feed: a short
daily set of cards, one screen at a time, and it borrows what makes
scrolling pull you in while refusing the part that makes it corrosive.

- **A finish line, and then more if you want it.** A set of 10, 20 or 40
  cards a day — this week's stories, one classic paper, one thing to watch
  — with a progress bar and a closing card. Past it, *Keep going* opens the
  rest of the week ten cards at a time. The streak counts days you
  *finished*, not minutes spent.
- **Two kinds of card.** Rewritten stories from openly licensed sources,
  and headline cards — the source's own title and a link — from everyone
  else, so every field shows up even in a week with no open text.
- **A mix, not a firehose.** Fields take turns, so the busiest field of the
  week can't fill the whole set. Pick up to three focus fields and they get
  two turns per round.
- **A diary, one swipe away.** Swipe right from Today (or press `[`) and
  you land on a calendar. Each day is shaded by how much you learned; a dot
  means you finished the set. Tap a day to see what you learned that day and
  write a line in your own words. Exportable as Markdown.
- **Want to learn.** Under the calendar, a private list of things that
  popped into your head. Type one in, or tap *Remember* on a message in
  Talk or a comment. Tick it when you've learned it and it joins that day
  in the diary; *Ask* hands it to the science guide.
- **A generated picture on every card**, drawn from the card's id — orbits
  for astrophysics, bubble-chamber tracks for particle physics, a helix for
  biotech. No stock imagery, nobody else's photographs.

State is per person and written only when something happens (a card read,
kept or noted), never on a timer. On GitHub Pages it lives in the browser;
inside claude.ai it lives in the viewer's private store.

## The social layer

Double-tap a card to like it, the way everyone already knows. Every card
has a comment thread with one level of replies, and every comment takes an
emoji reaction (one per reader, changeable). Each reader has a page — a
line about themselves, what fascinates them and why, the fields they
follow, "ask me about" — reachable from their name anywhere, with a strip
of people at the top of Talk.

**A profile photo.** Tap the circle at the top right, then the photo. The
page crops it to a square and shrinks it to 256 px (about 20 KB) in the
browser before saving it in your own profile document, so the original
never leaves your device. Only a plain image data URL is ever rendered
from someone's profile.

**Following and collaborating.** Follow anyone from their page; people you
follow come first in the strip. A page can say what you're working on or
just published (with a link), what you're looking for help with, and carry
an *Open to collaborate* badge — the seed of finding a co-author, a second
pair of eyes on a thesis chapter, or someone who knows the detector you're
stuck on. Follows are public, one document per reader (`follows/<id>`).

**What is public and what isn't is deliberate.** Likes, comments and pages
are public. The diary, what you marked as learned, your streak and your
minutes are private. Learning shouldn't turn into performing.

Storage: `likes/<id>` and `profiles/<id>` are one document per reader,
writable only by that reader (a `{self}` rule), so nobody can like or edit
on someone else's behalf. `comments/<id>` is one document per comment, so
simultaneous replies never overwrite each other.

### Suggest a source

Readers can suggest a site, feed, API or channel. It is checked in two
layers, because the page itself cannot visit a website:

1. **In the page, immediately:** Claude assesses it from what is known
   about the publisher — reputation, peer review, licensing, whether a feed
   or API exists, red flags — and lists what a live check must confirm.
   It is told it has not seen the site.
2. **Before anything is added:** `python tools/vet_source.py <url>` fetches
   it: does it answer, is it a feed or an API, does robots.txt allow us,
   what does it say about reuse. It proposes a `config.yaml` entry, always
   as `headline_only`; upgrading a source to `abstract_ok` stays a human
   decision made after reading its licence.

## Ask and Talk

**Ask** is a science guide in the page. It knows today's set and can search
the library through two small tools (`search_library`, `card_details`), so
its answers point at real cards, papers and entries. Every card has *Ask
about this*, and the empty state offers a quiz on today's cards.

**Talk** has two halves.

- **Rooms by topic.** A fixed list of 46 science rooms in seven groups —
  from *Neutrinos* and *Fusion* to *Grad school & research life*. Nobody
  can create a room, so the list stays scientific. Tap **+** to join; your
  rooms sit in a bar at the top and show on your page.
- **Messages between two people.** *Message* on someone's page. The first
  message is a **request**: one message, then nothing more until they
  reply or accept. Each reader chooses who can write to them — anyone (as a
  request), only people they follow, or no one.

**Against harassment**, in layers:

1. Text only. Nothing in Talk is ever rendered as an image or a link.
2. A local filter for the unmistakable, plus rate limits (one message every
   few seconds, twenty per ten minutes).
3. Before sending, Claude checks the message — sexual or suggestive
   content, pickup lines, asking for photos, insults, spam, and in rooms,
   being off topic — and says why when it blocks. It runs on the sender's
   own Claude access; if they decline it, only the local filter applies.
4. **Block** (private — they aren't told) and **Report**. A message three
   different people report is hidden for everyone; reporting a direct
   message also blocks its sender.
5. The page's editors can hide any message for everyone or ban a member
   (`mod/state`, writable only at the editor level).

Every author writes only their own document — `chat/<id>`, `dm/<id>`,
`reports/<id>` under `{self}` rules — so nobody can post, edit or delete
as someone else. Blocks and read markers live in the reader's private
store.

**Messages are not end-to-end private.** They live in the page's shared
store, which other members' browsers can read, and the page says so where
you write them. Private messaging needs a real backend with per-row
access rules (for example Supabase row-level security).

### Where they work today

Inside claude.ai, with no server at all: Ask runs on the reader's own
Claude account (the page asks permission the first time), and Talk uses the
page's own shared store and live room.

### Ask and Talk on the public site

A static GitHub Pages site can do neither on its own, and the page says so
rather than pretending. The path to each:

- **Ask** needs a small server that holds an API key — a Cloudflare Worker
  or Vercel function of ~40 lines that forwards the conversation to the
  Claude API. Never put the key in the page. Budget for it: every question
  is paid by you, so add a per-visitor rate limit before you share the link.
- **Talk** with strangers needs accounts and moderation. The lowest-effort
  honest option is **Giscus**, which puts GitHub Discussions on the page:
  readers sign in with GitHub, you moderate from GitHub, and it costs
  nothing. It needs the repository's id and a discussion category, set up
  at https://giscus.app.

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env          # add your ANTHROPIC_API_KEY
python -m ainstein.build --days 3
```

`--no-ai` runs everything except the rewrite step, which is useful while
you're tuning `score.py` and don't want to pay for tokens.

Then open `index.html`, or serve the folder:

```bash
python -m http.server -d . 8000
```

## Deploying

### Vercel + Supabase (recommended)

The site is static, so Vercel just serves the folder; Supabase keeps each
visitor's diary, streak and saved cards.

1. **Supabase → SQL Editor:** paste and run `supabase/schema.sql`. It
   creates `user_data` with row-level security, so each visitor can read
   and write only their own row.
2. **Supabase → Authentication → Sign In / Providers:** turn on
   *Allow anonymous sign-ins*. Every visitor gets an anonymous account on
   their first visit — no sign-up form.
3. **`cloud.json`:** your project URL and the **publishable** key
   (`sb_publishable_…`). That key is meant to be public; row-level security
   is what protects the data. Never put the secret key (`sb_secret_…`)
   here — `tools/embed.py` refuses to build if you do.
4. `python tools/embed.py`, commit, push.
5. **Vercel → Add New → Project →** import the repository. `vercel.json`
   tells it there is nothing to build; it serves `index.html` as is.

The GitHub Action keeps refreshing `data/feed.json` every morning, and
Vercel redeploys on each commit.

On the public site, visitors read, keep a diary and see everything
without an account. To like, comment, follow, join rooms or send messages
they sign in with an email link. All of it lives in one Supabase table,
`docs`, and the rules in `supabase/schema.sql` do what `{self}` rules do
inside Claude: each person writes only their own documents, comments carry
their real author, and private documents stay private.

**Ask** on the public site runs through `api/ask.js`, a small Vercel
function that holds the API key (Vercel → Settings → Environment Variables →
`ANTHROPIC_API_KEY`). Each visitor gets `ASK_PER_HOUR` questions an hour
(default 20); set a monthly spend limit in the Anthropic console as the hard
cap. The same function runs the Claude check on chat messages.

### GitHub Pages

1. Push to GitHub.
2. **Settings → Pages → Source: Deploy from branch**, `main` / root.
3. **Settings → Secrets and variables → Actions** → add `ANTHROPIC_API_KEY`
   and `CROSSREF_MAILTO`.
4. `.github/workflows/daily.yml` rebuilds the feed at 05:00 UTC, commits
   `data/feed.json` only when it changed, and Pages redeploys.

## Roadmap

- [ ] Verify and enable the CERN and opportunities feeds (`verified: false`
      in `config.yaml`)
- [x] Attach pulse items to experiments, so a DUNE card shows DUNE news
- [ ] Per-reader interest weights, saved locally
- [ ] Email or Telegram digest
- [ ] Deadline reminders for the opportunities tab

## Licence

Code: MIT. Retrieved content stays under its own terms — see
[SOURCES.md](SOURCES.md).
