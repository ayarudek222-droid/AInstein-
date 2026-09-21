# Sources and licensing

The rule this project is built around:

> **Facts are free. Someone else's sentences are not.**

You cannot copyright the fact that a detector measured a value, or that a
paper was published in *Nature* on a given day. You *can* copyright the
paragraphs a journalist wrote about it. So AInstein collects facts, metadata
and openly-licensed text, writes its own sentences, and links out for
everything else.

Every source declares a **policy**, in `config.yaml`, and the pipeline
refuses to treat an item more permissively than its source allows
(`Item.may_rewrite` in `ainstein/models.py`).

| Policy | What we store | What the AI sees | What gets published |
|---|---|---|---|
| `abstract_ok` | title, metadata, abstract | the abstract | our own card + link |
| `headline_only` | title, date, link | **nothing** | headline + link |

For `headline_only` sources the summary text is discarded at the network
boundary, in `sources/feeds.py` — not filtered later. It never reaches the
model and never reaches the feed.

---

## Per source

### arXiv — `abstract_ok`
arXiv publishes an API for exactly this purpose. Metadata is CC0; abstracts
are served for reuse with attribution. We link to the abstract page and never
mirror the PDF, and we respect the one-request-per-three-seconds rate limit.
→ https://info.arxiv.org/help/api/tou.html

### Crossref — `abstract_ok` *when an abstract is deposited*, else `headline_only`
This is how AInstein covers *Nature*, *Science* and *PRL* without touching
them. Crossref holds open (CC0) metadata for nearly every published paper:
which journal published what, when, by whom, with the DOI. Publishers
*deposit* abstracts into Crossref deliberately, for reuse — when one is
there, we may summarise it. When it is not, the item stays a headline and a
DOI link.

The journal therefore acts as a **quality filter**, not as a content source.
That is the whole point: it gets you peer-reviewed work without scraping a
paywalled site.

Set `CROSSREF_MAILTO` in your environment — Crossref asks for a contact
address and gives faster service in return.
→ https://www.crossref.org/documentation/retrieve-metadata/rest-api/

### NASA — `abstract_ok`
NASA-produced material is generally not protected by copyright in the US and
may be reused. Two caveats worth knowing: the NASA insignia and logos are
restricted, and imagery containing identifiable people cannot be used to
imply endorsement. Feed verified live.
→ https://www.nasa.gov/nasa-brand-center/images-and-media/

### ESA — `abstract_ok`
ESA releases most web content under **CC BY-SA 3.0 IGO**. Share-alike matters:
attribute ESA, and note that derivative text inherits the licence. Feed
verified live.
→ https://www.esa.int/Services/Terms_and_conditions

### CERN — `abstract_ok`
Content on home.cern is published under **CC BY 4.0** unless marked
otherwise. *The RSS endpoint in `config.yaml` did not return valid XML when
last checked*, so it ships with `verified: false`; the loader skips
non-XML responses and logs it rather than parsing garbage. Confirm the
current endpoint before relying on it.
→ https://home.cern/copyright

### CERN Courier, Fermilab newsroom, and any magazine — `headline_only`
Editorial writing, all rights reserved unless stated otherwise. Headline,
date and link only. If you later confirm a specific outlet publishes under
CC-BY, change its policy in `config.yaml` — one line, no code change.

---

## Things to keep doing

- **Attribute per item.** Every card carries its source name and links back.
  The front end shows it; don't remove it.
- **Identify yourself.** The User-Agent includes the project URL. Keep it.
- **Stay inside rate limits.** arXiv 1 req / 3 s; Crossref polite pool.
- **Never fetch article bodies** from sites you only have headline rights to
  — not for "just summarising", not with a browser, not via a cache.
- **Re-check before you monetise.** Non-commercial personal use and a paid
  product are different conversations, especially for CC BY-SA and for any
  source whose terms restrict commercial reuse.

*This is a considered engineering policy, not legal advice. If AInstein
becomes a business, have a lawyer read this page.*

---

## Added in 0.4: breaking news and attention

### ESO — `abstract_ok`
ESO releases press releases, captions and images under **CC BY 4.0**, with
the credit "ESO". This is the rare observatory whose text we may summarise,
not just link. → https://www.eso.org/public/outreach/copyright/

### NASA JPL — `headline_only`
A nuance worth knowing. JPL's use policy frees its **images and video**
("may be used for any purpose without prior permission"), but says nothing
about article text — and JPL is run by Caltech, so its writing is not
automatically a US government work. Headline and link only.
→ https://www.jpl.nasa.gov/jpl-image-use-policy/

### Nature, Google DeepMind, Hugging Face — `headline_only`
News, papers and company blogs. Valid feeds, other people's writing.

### Hacker News — attention, not content
Algolia's public HN search tells us what a technical audience upvoted this
week. It is used as a **signal**: a story we already carry gets its score
raised; a story we don't carry is added as a headline and link, with the
HN thread linked too. Nothing enters on attention alone — a trending story
must route into one of the configured fields, which filters out the large
majority of HN that is about software rather than science.

### Wikipedia pageviews — attention on the directory
The Wikimedia REST API's most-read articles are matched against directory
names, so an entry people are suddenly looking up is marked as trending.

### Considered and left out
- **Altmetric** now requires an API key; worth adding with one.
- **X / Twitter**: the API is priced beyond a personal project.
- **Reddit**: its API now needs OAuth and has usage terms to review first.
- **New Scientist, SpaceNews, Ars Technica, EurekAlert!, bioRxiv**: each
  refused or timed out for our checker. They may work fine from a normal
  client; they ship as `verified: false` or not at all until confirmed.

---

## Images

Images are a separate licence question from text, and the answer is often
different: **JPL's article text is headline-only here, but its images are
free to use** ("may be used for any purpose without prior permission",
credit NASA/JPL-Caltech).

| Source | Images? | Credit shown on the image |
|---|---|---|
| NASA | yes, except APOD | NASA |
| ESA | yes, except third-party characters and brands | ESA (CC BY-SA 3.0 IGO) |
| ESO | yes | ESO (CC BY 4.0) |
| NASA JPL | yes | NASA/JPL-Caltech |
| Magazines, journals, arXiv, YouTube | **no** | — |

Two exceptions found in real feeds on the day this was built, and the
reason `image_skip` exists:

- **NASA's feed carries Astronomy Picture of the Day.** APOD photographs
  belong to the photographers who took them, not to NASA. Anything under
  `/apod/` is skipped.
- **ESA published "Pikachu in the Cupola".** A CC licence covers what ESA
  owns; it cannot license someone else's character. Brand and character
  terms are skipped.

Also true of NASA and JPL, and not automatable: logos and insignia are
restricted, and photos of identifiable people can't be used to imply
endorsement. The card shows the image beside a science story, which is
neither.

Images are downloaded at build time, resized to 960px, and served from
this repository. Hotlinking would spend the agency's bandwidth, break when
they move a file, and is blocked outright inside claude.ai. Images no
current story uses are deleted on each run, so the repository doesn't grow.


## 0.5 additions (verified 2026-09-21)

Forty-eight more feeds, each fetched before being added. The rule is
unchanged: `abstract_ok` only where the text itself is under a licence that
allows derivatives (CC BY, CC0, public domain) — the open-access journals
(eLife, PLOS, Physical Review X, Physical Review Research, Quantum) and the
ESA/Webb and ESA/Hubble press offices. Everything else is a headline and a
link, which is what the feed now shows as a *headline card*.

Two traps worth knowing:

- **Nature Communications** is mostly CC BY, but some articles are CC BY-NC-ND.
  The feed does not say which, so it stays `headline_only`.
- **Astrobites** is CC BY-NC: derivatives are allowed only non-commercially,
  so it stays `headline_only` too.

Tried and not added: Science, Science Advances, PNAS, New Scientist, Ars
Technica, The Conversation, SpaceNews (all refuse automated fetching);
Space.com (empty feed); Symmetry, CERN, Weizmann, Chandra, Nature Energy
(stale feeds); NOIRLab (bot check); Anthropic (no feed).

| Source | Policy | Why |
|---|---|---|
| Google Research Blog | `headline_only` | Copyright Google, all rights reserved |
| Microsoft Research | `headline_only` | Copyright Microsoft, all rights reserved |
| BAIR Blog | `headline_only` | Author/UC Berkeley copyright; no open licence stated |
| MIT News AI | `headline_only` | Text copyright MIT, all rights reserved (images CC BY-NC-ND 3.0 per MIT News policy) |
| Import AI | `headline_only` | Copyright Jack Clark, all rights reserved |
| AI Alignment Forum | `headline_only` | Author content; open licence not verified, treat as all rights reserved |
| NVIDIA Technical Blog | `headline_only` | Copyright NVIDIA, all rights reserved |
| eLife | `abstract_ok` | CC BY 4.0 |
| PLOS Biology | `abstract_ok` | CC BY 4.0 |
| PLOS Computational Biology | `abstract_ok` | CC BY 4.0 |
| STAT | `headline_only` | Editorial journalism, all rights reserved |
| Nature Biotechnology | `headline_only` | Copyright Springer Nature, all rights reserved |
| The Transmitter | `headline_only` | Editorial journalism (Simons Foundation), all rights reserved |
| bioRxiv Neuroscience | `headline_only` | Varies per preprint (CC BY, CC BY-NC, CC BY-NC-ND, CC0 or no reuse); not stated in feed |
| Broad Institute News | `headline_only` | Copyright Broad Institute, all rights reserved |
| ScienceDaily Health & Medicine | `headline_only` | Copyright ScienceDaily / source institutions, all rights reserved |
| ScienceDaily Neuroscience | `headline_only` | Copyright ScienceDaily / source institutions, all rights reserved |
| Nature Neuroscience | `headline_only` | Copyright Springer Nature, all rights reserved |
| ESA/Webb | `abstract_ok` | CC BY 4.0 (ESA/Webb press releases and images, unless stated otherwise) |
| ESA/Hubble | `abstract_ok` | CC BY 4.0 (ESA/Hubble press releases and images, unless stated otherwise) |
| AAS Nova | `headline_only` | All rights reserved (footer: '(c) American Astronomical Society. All rights reserved.') |
| Astrobites | `headline_only` | CC BY-NC 4.0 (astrobites.org/copyright-permissions); site footer also says All Rights Reserved |
| Universe Today | `headline_only` | All rights reserved (journalism) |
| NASASpaceflight | `headline_only` | All rights reserved (journalism) |
| Spaceflight Now | `headline_only` | All rights reserved (journalism) |
| Payload | `headline_only` | All rights reserved (journalism) |
| European Spaceflight | `headline_only` | All rights reserved (journalism) |
| SpacePolicyOnline | `headline_only` | All rights reserved (journalism) |
| Physical Review X | `abstract_ok` | Articles CC BY 4.0 (fully open-access APS journal); note feed <rights> element says 'Personal use only' (APS boilerplate) |
| Physical Review Research | `abstract_ok` | Articles CC BY 4.0 (open-access APS journal); feed rights boilerplate says personal use only |
| Quantum (journal) | `abstract_ok` | CC BY 4.0 (stated on each paper page) |
| APS Physics | `headline_only` | Copyright APS; feed rights: 'Personal use only, all commercial or other reuse prohibited'. No CC licence found (article page 403 to fetcher). |
| Nature Communications — physics | `headline_only` | Per-article: many CC BY 4.0, some CC BY-NC-ND — headline only until checked per article |
| Nature Communications — energy | `headline_only` | Per-article: many CC BY 4.0, some CC BY-NC-ND — headline only until checked per article |
| Nature Physics | `headline_only` | All rights reserved (Springer Nature, subscription journal) |
| Physics World | `headline_only` | All rights reserved (IOP Publishing journalism) |
| Carbon Brief | `headline_only` | Journalism; reuse terms not verified - treat as no-derivatives/all rights reserved |
| Canary Media | `headline_only` | All rights reserved (journalism) |
| Nature Climate Change | `headline_only` | All rights reserved (subscription journal) |
| Fusion Industry Association | `headline_only` | All rights reserved (items belong to linked publishers) |
| Scientific American | `headline_only` | All rights reserved (Scientific American / Springer Nature) |
| ScienceDaily | `headline_only` | All rights reserved (ScienceDaily / source institutions) |
| Knowable Magazine | `headline_only` | CC BY-ND 4.0 (Annual Reviews) - no derivatives |
| Nautilus | `headline_only` | All rights reserved (NautilusNext) |
| Nature Communications | `headline_only` | Per-article: many CC BY 4.0, some CC BY-NC-ND — headline only until checked per article |
| PLOS ONE | `abstract_ok` | CC BY 4.0 (verified on article pages; occasional CC0) |
| ESA Education | `headline_only` | ESA copyright (text all rights reserved; some images CC BY-SA 3.0 IGO) |
| Opportunity Desk | `headline_only` | All rights reserved (Opportunity Desk) |
