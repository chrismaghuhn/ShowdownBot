# ShowdownBot Studio source, license, and privacy audit

**Status:** engineering gate; not legal advice

**Date:** 2026-07-16

**Scope:** sources discussed for Studio code, reference research, assets, replay import, and external
data ingestion

## 1. How to read this audit

This document separates three questions that must not be collapsed into one:

1. **License fact:** what the source's own repository or documentation says.
2. **Unresolved legal question:** what the primary source does not grant or explain.
3. **Studio policy:** the conservative engineering rule used until a qualified legal review or
   written permission changes it.

`APPROVED` therefore means approved for the stated Studio use, not that every artifact associated
with the project is freely reusable. Public access, a documented API, CORS, or common community
practice is not a copyright, privacy, trademark, or database license.

## 2. Audit table

| Source | Verified primary-source fact | Unresolved scope | Studio policy verdict |
|---|---|---|---|
| `smogon/pokemon-showdown` server/simulator source | Repository is MIT-licensed; the license permits use, modification, distribution, sublicensing, and sale when its notice is preserved | The software license does not grant rights to separate Pokémon artwork, audio, trademarks, replay content, or third-party data | **APPROVED — CODE ONLY**, preserve the exact MIT license and notices |
| `smogon/pokemon-showdown-client` source | Repository is AGPL-3.0; its README says the copyright holder may relicense AGPL portions to MIT on request | AGPL redistribution is allowed, but requires AGPL compliance; integrating its code into Studio would change current source/distribution obligations | **RESEARCH-ONLY** under the current architecture; code reuse requires an AGPL-compliant release design or written relicensing |
| Official Pokémon artwork, sprites, cries, models, and logos | Pokémon's official support asks projects not to use Pokémon names, characters, and designs; official website terms reserve service artwork and graphics | No Studio redistribution permission was found | **BLOCKED** for bundled Studio assets without written permission or a separately verified license |
| Community sprite packs | Attribution and authorship vary by pack; no single verified license covers every community and derivative asset | Artist permission does not by itself resolve underlying Pokémon rights | **UNKNOWN — LEGAL REVIEW REQUIRED**; do not bundle or hotlink |
| Pokémon Showdown runtime sprite URLs | `@pkmn/img` is MIT-licensed URL/rendering logic and ships no sprite image payload; its README supports configurable domains and recommends self-hosting to avoid using Showdown bandwidth | The package license covers its code/data, not the remotely fetched Pokémon images; no permission for Studio hotlinking, caching, or mirroring was found | **FUTURE RESEARCH CANDIDATE — NOT APPROVED**; v0 stays offline and asset-free |
| `pkmn/ps` repository and packages built from that repository | Repository license is MIT | A repository code license is not a blanket license for externally sourced analyses, usage data, sprites, or hosted content consumed by a package | **APPROVED PER EXACT CODE PACKAGE/RELEASE** after artifact-level provenance review; no blanket `@pkmn/*` data approval |
| `smogon/damage-calc` / `@smogon/calc` | Repository is MIT-licensed | Pinned build provenance and required notice must remain reproducible | **APPROVED — CODE**, retain the exact MIT license and pin provenance |
| Showdex source | Repository is AGPL-3.0 | Same copyleft/distribution issue as other AGPL code under Studio's current release design | **RESEARCH-ONLY** for behavior and UX ideas; code reuse requires AGPL compliance or permission |
| Smogon usage statistics at `smogon.com/stats` | Public directory is accessible; no explicit redistribution license was found on the stats index | Repackaging or redistributing snapshots, and any database-right implications, require legal review | **UNKNOWN — LOCAL-FETCH-ONLY**; no snapshots in Studio releases, fixtures, or default bundles |
| Limitless tournament API | Official developer docs expose API endpoints, response schemas, rate-limit headers, and optional API keys for higher limits or restricted endpoints | No broad license permitting redistribution of harvested tournament/team datasets was found in the reviewed docs; responses contain stable player identifiers and sometimes names/countries | **UNKNOWN — DOCUMENTED API USE ONLY** within published limits; no scraping or bundled snapshots until terms/privacy review |
| Public Pokémon Showdown replay API | Official `WEB-API.md` documents `.json`, `.log`, replay search, and CORS; it explicitly directs callers to the API rather than scraping replay HTML | The API documentation does not grant a general redistribution license or settle privacy obligations for player names/chat | **LOCAL IMPORT ONLY** by default; no bulk crawling, no public raw-replay corpus, and only privacy-normalized portable bundles |
| gdUnit4 v6.1.3 (`1579130d73f15f628fd0cfdbf7d60bdc39144a26`) vendored at `showdownbot_studio/godot/addons/gdUnit4/` | Upstream `LICENSE` is MIT; commit pin and notice recorded in `godot/THIRD_PARTY_NOTICES.md` | No additional data/assets beyond the test framework code | **APPROVED — CODE**, preserve MIT license text under `addons/gdUnit4/LICENSE` |
| Godot Engine 4.5.2-stable (Windows x64 editor + console) | Engine is MIT-licensed; Studio pins digests in `godot/tools/ENGINE_SHA256SUMS` and does not commit binaries | Engine upgrade requires ADR-001 revisit | **APPROVED — RUNTIME PIN**, local install only under `godot/tools/engine/` (gitignored) |

## 3. Corrections to the incoming audit

### 3.1 AGPL does not prohibit redistribution

The AGPL permits copying, modification, and redistribution under its conditions. Describing it as
"redistribution forbidden" is incorrect. The practical Studio conclusion remains conservative:
the current project does not adopt AGPL client or Showdex code because doing so would require an
explicit AGPL-compatible source and distribution plan. Studying documented behavior and producing
an independent implementation remains the current research path.

### 3.2 MIT code does not automatically license data or assets

`pkmn/ps`, Pokémon Showdown, and `@smogon/calc` have verified permissive code licenses at the
reviewed repositories. That does not automatically license Pokémon assets, Smogon analyses,
third-party usage snapshots, tournament submissions, or replay content. Studio approves exact
software artifacts, not project-name wildcards.

### 3.3 A public API is not a redistribution grant

Showdown and Limitless document programmatic interfaces. This supports interoperability and
moderate API use within documented limits. It does not, by itself, permit Studio to publish a
mirror, redistribute a corpus, or expose personal data. CORS is a browser access mechanism, not a
content license.

### 3.4 Do not rely on a private-household exemption

Studio is intended to become a distributable tool. Its architecture and release policy must not
depend on a jurisdiction-specific household exemption. Legal bases, retention, deletion, data
subject rights, database rights, and cross-border distribution remain external legal-review topics.

### 3.5 Runtime loading reduces bundling but does not clear the asset gate

Loading an image from `play.pokemonshowdown.com` would mean that the Studio installer does not
contain that image. That is a materially different distribution path, but it does not prove that
embedding, automated retrieval, or caching is authorized. The cache is still a reproduction
initiated by Studio, and the upstream service has not promised stable URLs, bandwidth, or terms for
third-party clients. The EU Court's `GS Media` decision also makes blanket claims about links to
unauthorized works unsafe, especially when knowledge and commercial purpose enter the analysis.

`@pkmn/img` is useful evidence for the technical pattern only: it computes sprite/icon rendering
information and URLs without shipping the images. Its MIT license does not extend to the remote
assets. Its own self-hosting recommendation is not a safe Studio workaround because a Studio mirror
would again copy and distribute the images.

If later approved through legal and upstream-service review, remote sprites must be a separate
post-v0 capability with all of these controls:

- disabled by default and never required for battle comprehension;
- explicit host allowlist and HTTPS-only URLs;
- no bulk prefetch, crawler, or Studio-operated mirror;
- bounded, user-clearable cache with documented location and retention;
- content-type, size, redirect, and decode limits for untrusted responses;
- deterministic fallback to the abstract board when offline, blocked, missing, or invalid;
- no sprite bytes in viewer bundles, diagnostics, fixtures, screenshots generated by Studio, or
  other sharing/export artifacts.

This is a product research gate, not approval to implement the network feature.

### 3.6 Mechanics data is not categorically risk-free

MIT-licensed Showdown or `pkmn` code and generated tables are easier to review than artwork, but
"only artwork is protected" is too broad. Repository authors cannot grant rights they do not own;
Pokémon names and marks, externally sourced analyses, and a compiled dataset may raise separate
questions. Studio therefore keeps the same artifact-level rule for Pokédex, move, learnset, and
format data: approve the exact source, fields, provenance, and release use rather than assuming the
repository's software license resolves every content right.

## 4. Binding privacy boundary for viewer bundles

### 4.1 Preserve evidence without publishing raw source

- An imported source replay/log is never edited in place.
- If retained, the untouched source stays in user-controlled local storage outside the portable
  viewer bundle.
- The exporter reads the source and writes a separate normalized presentation artifact.
- Source hashes may be retained for integrity; the source bytes, raw HTML, local paths, and source
  URL are excluded from the default portable bundle.

This resolves the apparent conflict between evidence preservation and privacy. "Strip on import"
must not mean destroying the source artifact. Filtering occurs at the normalization/export boundary.

### 4.2 Default portable privacy profile

Bundle schema 1.0 uses `portable-pseudonymous-v1`:

- chat and private-message protocol lines are excluded;
- player display names and user IDs are deterministically mapped to seat labels such as `p1` and
  `p2` in every exported file;
- no reversible name map is included;
- replay URLs, raw HTML, credentials, session tokens, IP-like metadata, and absolute paths are
  excluded;
- annotations are included only after the same validation and privacy transformation;
- private or hidden replays require documented user authorization and are never shareable by
  default.

Cleartext-name export is outside v0 until it has a separate consent/authorization UX and legal
review. The local source library may remember a source URL or display name for the importing user,
but those fields remain outside the portable-bundle contract.

## 5. External-data ingestion policy

| Operation | Current rule |
|---|---|
| Smogon stats | Ship an importer, not snapshots; user initiates local retrieval; record URL, month, format, response hash, and review status |
| Limitless | Use documented endpoints and rate-limit headers only after a source-specific terms/privacy check; never screen-scrape; keep API keys out of bundles and logs |
| Showdown replays | User-initiated import of specific public replays; no bulk archive crawler; keep untouched source local and export only the privacy-normalized DTO |
| Third-party sets/analyses | Source-by-source license and provenance review; no inference from a library's code license |
| Sprites/audio | No bundled, mirrored, or runtime-loaded assets until the exact delivery path has legal/upstream-service approval; abstract board remains mandatory |

## 6. Release gates

Before the first public Studio release:

1. Generate an artifact-level dependency inventory with package name, version/commit, source URL,
   license identifier, and use in Studio.
2. Distribute the exact required license texts and copyright notices for every copied dependency or
   substantial source portion. A hand-written `NOTICE` summary alone is not a substitute.
3. Verify that generated fixtures and release archives contain no blocked assets, raw replays,
   chats, player names, credentials, local paths, or unapproved external data snapshots.
4. Run a privacy fixture containing chat, PMs, player names, a source URL, and an absolute path; the
   portable bundle must contain none of those values while retaining deterministic protocol state.
5. Obtain legal review before distributing external stats/replay corpora, enabling cleartext-name
   sharing, or bundling Pokémon/community assets.

## 7. Primary sources reviewed

- [Pokémon Showdown server license (MIT)](https://github.com/smogon/pokemon-showdown/blob/master/LICENSE)
- [Pokémon Showdown client README and relicensing note](https://github.com/smogon/pokemon-showdown-client/blob/master/README.md)
- [Pokémon Showdown client license (AGPL-3.0)](https://github.com/smogon/pokemon-showdown-client/blob/master/LICENSE)
- [Pokémon Showdown website/replay API documentation](https://github.com/smogon/pokemon-showdown-client/blob/master/WEB-API.md)
- [`pkmn/ps` license (MIT)](https://github.com/pkmn/ps/blob/main/LICENSE)
- [`smogon/damage-calc` license (MIT)](https://github.com/smogon/damage-calc/blob/master/LICENSE)
- [Showdex license (AGPL-3.0)](https://github.com/doshidak/showdex/blob/master/LICENSE)
- [Smogon stats index](https://www.smogon.com/stats/)
- [Limitless developer/API guide](https://docs.limitlesstcg.com/developer.html)
- [Limitless tournament endpoint documentation](https://docs.limitlesstcg.com/developer/tournaments)
- [Pokémon Support: use of Pokémon images/materials](https://support.pokemon.com/hc/en-us/articles/360000634094-Can-I-use-Pok%C3%A9mon-images-or-materials)
- [`@pkmn/img` README and runtime URL behavior](https://github.com/pkmn/ps/tree/main/img)
- [Court of Justice of the European Union, `GS Media`, C-160/15](https://infocuria.curia.europa.eu/tabs/redirect/juris/liste.jsf?num=C-160%2F15%3B)

## 8. Re-review triggers

Repeat this audit when Studio adds a dependency, bundles an external dataset or asset, enables
network import, supports public sharing, changes its project license, or receives written
permission/relicensing from a rights holder.
