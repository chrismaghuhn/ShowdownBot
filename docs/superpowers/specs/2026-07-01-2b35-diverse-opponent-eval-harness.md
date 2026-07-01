# 2b-3.5 — Diverse-Opponent-Eval-Harness (Slice-Spec)

> **Einordnung:** Schiebt sich zwischen **2b-3 (Shadow Mode)** und **2b-4 (Gated Override)**.
> **Zweck:** eine *wiederholbare Proxy-Metrik für Spielstärke*, weil Ladder-Elo unzuverlässig
> verfügbar ist (`08 R9`) und Mirror-vs-`max_damage` **kein** Steuerungssignal ist (bewegt sich mit
> Belief/Sampling um null, weil im Mirror keine Hidden Info existiert).
> **Kein** RL-/Self-Play-Plan. Reiner **Eval-Slice** auf dem vorhandenen `gauntlet` + lokalen Server.
> Pfad: **B/C** (Analyse/Infra) — der Live-Battle-Pfad bleibt unangetastet.

---

## 0. Was dieser Slice liefert — und was nicht

- **Ist:** ein **frozen Gegner-Panel**, ein **seed-fixierter, gepaarter Match-Schedule**, ein
  **Report** mit Per-Gegner-Confidence-Intervallen, ein **Vergleichsprotokoll** für
  Heuristik-only / Shadow / Override, und **Gates**, gegen die alle späteren Slices gemessen werden.
- **Ist nicht:** kein Training, kein Self-Play, keine neue Sim, keine Reflection-Engine. Wo möglich
  **Reuse** des `gauntlet`-Harness und der `--strict`-Exit-Kriterien.

---

## 1. Gegner-Panel (Baselines)

Ein **fixes, versioniertes** Roster (`panel_v001`). Jeder Gegner ist ein Paar **(Policy × Team)**.
Alle Policies sind **deterministisch gegeben den Battle-Seed** (interner RNG aus dem Seed) — sonst
ist Pairing wertlos.

| Policy | Was es testet | Aufwand | Pool |
|--------|---------------|---------|------|
| `random` | Floor-Tripwire (muss ~immer verloren gehen) | vorhanden | dev |
| `max_damage` | taktische Solidität (klickt max Schaden, kein Switch/Protect) | vorhanden | dev + held-out |
| `greedy_protect` | Anti-Stall / Bait (max_damage + situatives Protect) | klein (Regel) | dev |
| `simple_heuristic` | **die eigentliche Kompetenz-Latte** — Typ-Effektivität + Switch-on-bad-matchup + Boosts (poke-env `SimpleHeuristicsPlayer`-Äquivalent) | klein (Regel) | dev + held-out |
| `scripted_vgc` | **Doubles-Mechanik unter Druck** — Lead mit Fake-Out + Redirect, situatives Protect, Tera; Sets aus Meta gesampelt | mittel (Regel) | dev + held-out |
| `prev_version` | Regressions-Anker — der eigene **Heuristik-only-Checkpoint**, cross-team | vorhanden (Config-Flag) | gate |

**Warum diese Mischung:** `random`/`max_damage` sind Sanity/Taktik-Floor. `simple_heuristic` ist der
Standard-„ist der Bot überhaupt kompetent?"-Test. `scripted_vgc` ist der einzige, der Redirection /
Protect / Spread / Tera **gegen einen Gegner, der sie nutzt** prüft — die Mechanik, um die's in
Doubles geht. `prev_version` macht Cross-Version-Regression messbar.

> **Anti-Mirror-Prinzip:** Panel-Teams sind **andere Teams** als unser eigenes. Es geht ausdrücklich
> **nicht** um Mirror. Ein Panel-Gegner darf nie unser eigenes Team spielen.

---

## 2. Team-Auswahl

- **Eigene Seite:** fixes Team (`teams/fixed_team.txt`, MVP-Annahme A aus `09`). Team-Pool auf
  unserer Seite ist V2.
- **Gegner-Team-Pool:** **~8–12 archetyp-diverse** Teams, kuratiert aus öffentlichen VGC-Quellen
  (VGCPastes / Pikalytics / Usage-Sample-Teams — **mit echten Spreads**, nicht invertiert). Archetypen
  breit streuen: Trick Room, Hyper Offense, Balance, Wetter, Redirect-Control, Tailwind-Offense.
- **Split (Kern des Anti-Overfit, `§8`):**
  - **Dev-Pool** (~6 Teams) — dagegen wird iteriert/getunt.
  - **Held-out-Gate-Pool** (~4 Teams) — **nur am Gate**, nie zum Tunen angeschaut.
- **Matchup-Zelle** = (opp_policy × opp_team). Report immer **per Zelle + aggregiert**.

> **Annahme A-POOL (reversibel):** ~10 Gegner-Teams reichen für ein brauchbares Signal bei einem
> fixen eigenen Team. Wenn V2 mehrere eigene Teams bringt, wird der Pool zur Matrix erweitert.

---

## 3. Match-Format

- `gen9vgc2025regi`, **Bring-4-of-6**, Level 50, **Tera an** — identisch zum Ziel-Format. **Bo1**
  (Ladder-realistisch). Teampreview wird **mitgespielt** → prüft nebenbei den Teampreview-Hebel (`08 R7`).
- **Ein Battle pro (config, opp_policy, opp_team, seed)**, über den vorhandenen Local-Server-`gauntlet`
  mit `--strict`.

---

## 4. Seed-/Randomness-Kontrolle

- **Seed-Schedule** `S = [s_1 … s_G]`, **fix + versioniert** (Teil von `panel_v001`).
- **Sim-PRNG** je Battle aus `s_i` gesetzt → **Integrationspunkt #1**, siehe unten. Ohne das ist
  Wiederholbarkeit unmöglich — höchste Priorität. **⚠️ Read-only-Erkundung (2026-07-01):** der
  gauntlet-`/challenge` ist aktuell **seedlos** (`gauntlet.py:386`), der Server-Sim-PRNG ungeseedet, die
  Ergebnisse aggregat-only, der `random`-Gegner unseeded. Ob Showdowns Challenge-/Format-/Server-Pfad
  überhaupt einen Battle-Seed pro Battle durchreicht, ist **unverifiziert** — **`T0b` muss es belegen,
  bevor T1+ startet** (siehe **`§T0`**).
- **Bot-RNG** deterministisch aus `(s_i, config)` geseedet (Belief-Sampling reproduzierbar);
  **Gegner-RNG** aus `s_i`. Ergebnis: ein Battle ist durch `(config, opp_policy, opp_team, s_i)`
  **vollständig determiniert**.
- **Gepaarter Vergleich (der Varianz-Trick):** Configs werden auf **identischen**
  `(opp_policy, opp_team, s_i)`-Tripeln verglichen.
  > **Ehrlicher Caveat:** Sobald zwei Configs im ersten Zug divergieren, forkt die Trajektorie und
  > „gleicher Seed" heißt **nicht mehr** „gleiche Situation". Der Seed kontrolliert **Startbedingung +
  > RNG-Stream bis zur Divergenz**, nicht Post-Divergenz-Identität. Trotzdem drastisch geringere
  > Varianz als unpaired — weil der geteilte Luck-Anteil (Rolls/Crits bis zur Gabelung, Gegner-Team,
  > Seed) herausfällt.
- **Optionaler Sekundär-Modus „low-variance"** (Rolls fix auf Mittel, Crits aus): isoliert
  Entscheidungsqualität von Glück. **Nur Diagnose**, nicht die Primärmetrik (verändert das Spiel).

---

## 5. Metriken

**Primär**
- **Winrate** per Zelle + aggregiert, mit **Wilson-95%-CI** (Bernoulli/Bo1).

**Safety (aus `--strict`, muss immer halten)**
- **0** Crashes · **0** invalide Choices · **0** Timeouts · **p95-Decision-Latenz < 3 s**.

**Margin (billigeres Signal, weniger Games nötig)**
- Turns-to-Result (Mittel) · End-HP-Differenz (Mittel). Zeigt „knapp vs. deutlich", wo Winrate noch rauscht.

**Version-Vergleich (gepaart)**
- **McNemar-Δwinrate** über die **diskordanten Paare** + CI. Der eigentliche Cross-Version-Test.

**Optional (nur wenn aus dem `DecisionTrace` billig)**
- `avoidable_faint` / `missed_ko` / `overprotect`-Raten (die Reflection-Patterns aus `03/05`). Messen
  Entscheidungsqualität **unabhängig vom Win/Loss-Münzwurf**.
  > **Wichtig:** **keine Abhängigkeit** — die volle Reflection-Engine wird für diesen Slice **nicht**
  > gebaut. Nur nutzen, was der Trace eh hergibt.

---

## 6. Mindestanzahl Games (mit Power-Begründung)

- **Varianz-Realität:** Bo1 → jede Winrate ist ein verrauschter Bernoulli-Schätzer.
- **Unpaired-Ballpark:** 0.55 vs. 0.50 bei ~80 % Power / α=.05 zu unterscheiden ≈ **~800 Games/Arm**
  — für einen lokalen Loop zu teuer.
- **Gepaart ist der Ausweg:** McNemar zählt nur **diskordante** Paare; geteiltes Rauschen kürzt sich.
  Ähnliche Versionen (Override divergiert nur auf wenigen Decisions) → wenige **Total**-Games reichen,
  um einen echten Effekt zu sehen, weil die meisten Battles ohnehin identisch ausgehen.
- **Konkrete Empfehlung (Knöpfe, dreh selbst):**
  - **Smoke (Dev-Loop):** ~**50 Games** — Subset der Zellen × ~10 Seeds, ~20–40 min. Für schnelles Feedback.
  - **Full/Gate:** **~30 Games/Zelle**. Gate fährt die **3 diskriminierenden** Policies
    (`max_damage`, `simple_heuristic`, `scripted_vgc`) × **Held-out-4-Teams** × 30 = **360 Held-out-Games**,
    plus dev-seitig vergleichbar → **~600–800 Games/Version**. Über Nacht auf dem Local-Server machbar.
  - **Floors:** Zelle **≥ 30** (brauchbares Per-Gegner-CI); Aggregat **≥ ~500** (enges Aggregat + enge gepaarte Δ).

> **Annahme A-N-GAMES (reversibel):** 30/Zelle, ~600–800/Version am Gate. Wenn die CIs zu breit sind
> oder ein echter Effekt knapp verfehlt wird, hochdrehen — die Schedule-Datei ist ein Parameter.

---

## 7. Vergleichsprotokoll — die drei Configs *fair*

Ein Config-Flag, **identischer Schedule** für alle:

```
--brain heuristic   # spielt Heuristik-Kern (Baseline)
--brain shadow      # spielt Heuristik, LOGGT reranker_choice + Counterfactual (aus 2b-3)
--brain override    # spielt Heuristik + Gated-Override (2b-4)
```

- **`heuristic`** → **reale Winrate** auf dem Panel = die Referenz.
- **`shadow`** → **exakt dieselben Games** wie `heuristic` (spielt ja heuristisch) → **keine
  Winrate-Änderung**. Liefert stattdessen das **Divergenz-Set** + **Per-Divergenz-Counterfactual-Value**
  **auf genau dem Panel, das Override später sieht**. Das ist der **Go/No-Go-Prior für 2b-4**: auf
  welchen Gegnern / Decision-Klassen weicht der Reranker ab, und ist der geschätzte Value-Delta positiv?
- **`override`** → **reale Winrate**, **gepaart** gegen die `heuristic`-Baseline → der **gemessene**
  Effekt, der die Shadow-Vorhersage **validiert**.

```
heuristic  ── Baseline-Winrate ─────────────────────────────►  Referenz
shadow     ── Divergenz + Counterfactual auf demselben Panel ─►  Override-Prior (Upside-Schätzung)
override   ── reale Winrate, gepaart vs. Baseline ───────────►  misst, was Shadow vorhergesagt hat
```

**Warum das sauber ist:** Shadow „macht Arbeit" statt nur zu loggen — seine Ausgabe ist der Input für
Overrides Gate. Deine Reihenfolge (Shadow now → Harness → Override) ist damit die einzig richtige.

---

## 8. Anti-Overfit (nicht auf einen bekannten Gegner overfitten)

- **Held-out-Pool** (Teams **+ mind. eine Policy**, z. B. `scripted_vgc`-Variante) — **nie** zum Tunen,
  nur am Gate.
- **Keine Hyperparam-Tunung** (Override-Threshold, K, λ, Fusion-Gewichte) **auf dem Held-out-Pool** —
  nur auf dev. (Gleiche Disziplin wie INV-6 fürs Feature-Leakage.)
- **Report per Gegner + Varianz**, nie nur Aggregat → Fragilität kann sich nicht im Mittel verstecken.
- **Per-Gegner-Floor-Gate** (`§9`): kein einzelner Gegner, gegen den die neue Version **signifikant**
  abfällt. Fängt „im Schnitt besser, aber gegen Archetyp X plötzlich exploitbar".
- **Optionale „Surprise"-Zelle am Gate:** ein Team/eine Policy, die während der Entwicklung nie lief —
  Generalisierungs-Probe.

---

## 9. Akzeptanz-Gates

**(a) Harness-Gate — die Abnahme *dieses* Slices**
- **Reproduzierbarkeit:** fixe `(config, schedule)` → **identische** Ergebnisse über Läufe (bit-stabil
  bei fixer Version).
- **Held-out-Split erzwungen**; Report **auto-generiert** (Per-Gegner-Wilson-CIs, gepaarte Δ, Safety-Rollup).
- Panel läuft mit `--strict`: **0** Crashes/invalid/timeout, **p95 < 3 s**.
- **Heuristik-only-Baseline** auf dev **und** held-out **festgehalten** → die Referenz, gegen die alles
  Spätere misst. *(Nebeneffekt: liefert endlich die faire Nicht-Mirror-Zahl fürs Fundament.)*

**(b) Gates, die *spätere* Slices auf diesem Harness bestehen müssen**
- **Non-Inferiority:** neue Aggregat-Winrate **≥** Vorversion auf **held-out**, gepaarte Δ-CI **nicht
  signifikant negativ**.
- **Verbesserung wo erwartet (für 2b-4):** Gewinn **konzentriert auf ATTACK/contestable**-Zellen
  (deckt sich mit dem 2b-4-Gate in `10`), **nicht** aus trivialen/forced Zellen.
- **Per-Gegner-Floor:** kein signifikanter Abfall gegen **irgendeinen** Einzelgegner.
- **Safety immer:** 0 Crashes/invalid, p95 < 3 s.
- **Report = versioniertes Artefakt** mit `panel_hash` / `schedule_hash` / `config_hash` (analog zur
  INV-7-Model-Artifact-Safety) → Gates werden **mechanisch** prüfbar.

---

## 10. Einordnung in die Roadmap

- Sitzt als **2b-3.5** **nach Shadow (2b-3), vor Override (2b-4)** — exakt deine Priorität.
- **Warum Voraussetzung für ein *sinnvolles* 2b-4:** Overrides Gate braucht ein **faires,
  nicht-Mirror**-Gegner-Set. Ohne diesen Harness fällt 2b-4 auf den **irreführenden Mirror** zurück.
  Shadow (2b-3) erzeugt die Divergenz-/Counterfactual-Daten → der Harness macht daraus den
  Override-Prior → 2b-4 misst die Realität dagegen.
- **2b-4-Unblock-Bedingung (gespiegelt aus dem Implementation-Plan):** ein 2b-4 Gated Override darf
  **erst** geplant/versucht werden, wenn **`T0-Verdict ∈ {PASS_STRONG, PASS_WEAK}` ∧ `T4 grün` ∧
  `T6 grün`**. Bis dahin bleibt 2b-4 blockiert (sonst Rückfall auf den irreführenden Mirror). Dieselbe
  Triple steht im Plan (§2b-4 Unblock) und in Doc 10 (`10-execution-slices.md`, Slice 2b-3.5).
- **Retro-Fill:** liefert nebenbei die fehlende **erste faire Baseline** für Heuristik-only (die
  „trägt das Fundament?"-Frage aus dem Review — billig beantwortet, **bevor** ML echten Einfluss bekommt).
- **Ablationsleiter (`10 §5`):** dieser Harness ist das **Messinstrument** für jede Sprosse
  (Heuristik → +Reranker(gated) → +Sampling → +CVaR → +Memory-Prior). Ohne ihn ist die Leiter nicht messbar.

---

## T0 — Determinism-/Seed-Feasibility-Probe (BLOCKER — vor jedem Harness-Bau)

Bevor irgendetwas gebaut wird, MUSS T0 klären, ob ein Battle überhaupt reproduzierbar gemacht werden kann.
Read-only-Erkundung (2026-07-01, s. §4) zeigt: `/challenge` seedlos, Server-Sim-PRNG ungeseedet, Ergebnisse
aggregat-only, `random`-Gegner unseeded → der Ist-Zustand ist **nicht** reproduzierbar. T0 misst das und
prüft die Seed-Machbarkeit — **kein Harness-Bau, nur Probe + Verdict.** Drei Sub-Probes:

- **T0a — Baseline-Determinismus ohne Seed.** Gleiche Config (same hero/villain agent, same team, same
  format, same local server, same nominal seed/config) **R≈5–8×** fahren. Pro Lauf `room_raw` (voller
  Protokoll-Stream) + `winner` erfassen. Vergleichen: `room_raw` identisch? `winner` identisch?
  `first_divergence_frame` + `divergence_reason` (soweit erkennbar: damage roll / crit / speed-tie /
  secondary / accuracy). Ziel: **quantifizieren, wie** nicht-deterministisch der Ist-Zustand ist + die
  RNG-Quelle lokalisieren.
- **T0b — Seed-Injection-Feasibility.** **Nicht implementieren — NACHWEISEN**, ob es einen Weg gibt, den
  Battle-PRNG-Seed **pro Battle** zu setzen. Kandidaten NUR prüfen, nicht voraussetzen: `/challenge`-Syntax
  (Seed-Parameter?), custom Format-Options, Server-Launch/-Config, Room/Battle-Init-Options, notfalls ein
  minimaler Showdown-Server-Patch. **Belegen**, welcher (falls einer) funktioniert.
- **T0c — Verdict.** Genau eines:
  ```
  PASS_STRONG : room_raw + result bit-stabil bei fixem Seed → volle Reproduzierbarkeit
  PASS_WEAK   : nur Startbedingungen stabil kontrollierbar, Battle-Log/Result NICHT bit-stabil
  FAIL        : Startbedingungen selbst nicht stabil kontrollierbar → seeds_dont_control
  ```
  **`PASS_WEAK` ist kein voller Erfolg.** Bei PASS_WEAK MUSS jeder spätere Report dauerhaft tragen:
  *„Determinism status: start_conditions_only — paired comparison is variance-reducing, not
  bit-reproducible."* Bei **`FAIL`** ist die ganze Harness (T1+) **blockiert**, bis eine Seed-Kontrolle
  gefunden ist (Re-Scope: low-variance-Modus §4 als Fallback, oder Server-Patch).

**Design-Regel:** T1 (Non-Mirror-Scheduling), T2 (Result-JSONL), T3 (Panel) usw. starten **erst nach dem
T0-Verdict**. T0 ist der einzige echte Blocker; T1+ sind kleine, isolierte gauntlet-Zusätze.

---

## 11. Konkrete Bauliste (Reihenfolge bindend — T1+ starten ERST nach T0-Verdict)

> **Nummerierung — Spec vs Plan (Alignment):** Diese Spec-Bauliste ist **feingranular (Items 0–8)**;
> der **Implementation-Plan** bündelt sie in **PR-Slices `T0–T6`**. Mapping: **T0** = Item 0 (Probe) ·
> **T1** Non-Mirror-Scheduling = Items 1 (Sim-Seed) + 2 (Non-Mirror) (+ 7 `--brain` teils) · **T2**
> Per-Battle-JSONL = Item 5 · **T3** Panel v001 = Items 3 (Policies) + 4 (Team-Pool) · **T4** Smoke = Item 8
> · **T5** Report-Generator = Item 6 · **T6** Held-out-Gate + Heuristik-Baseline = §8/§9. Der Plan (`T0–T6`)
> ist die verbindliche Ausführungs-Sicht; diese Item-Liste ist die Design-Detaillierung darunter.

0. **T0 (siehe `§T0`) — der einzige echte BLOCKER.** Determinism-/Seed-Feasibility-Probe (T0a/T0b/T0c)
   VOR allem. Bei `FAIL` sind T1+ blockiert.
1. **Sim-Seed im `gauntlet` plumben** (Integrationspunkt #1) — **nur wenn T0b PASS.** Wiederholbarkeit hängt daran.
2. **Non-Mirror-Setup:** zwei **verschiedene** Teams je Battle + **Schedule-Datei**
   (`opp_policy × opp_team × seed`) laden. Erweitert den vorhandenen Mirror-`gauntlet`.
3. **Gegner-Policies:** `simple_heuristic` + `scripted_vgc` + `greedy_protect` — regelbasiert, docken an
   das vorhandene `max_damage`/`random`-Muster an (`choose_with_fallback`-artige Entry-Funktion).
   `random`/`max_damage`/`prev_version` existieren bereits.
4. **Team-Pool kuratieren** (öffentliche Quellen, echte Spreads), **dev/held-out splitten**, als
   `panel_v001` einfrieren + hashen.
5. **Per-Battle-Result-Record** (winner, turns, end-HP, seed, config, trace-path) → JSONL. Nötig fürs Pairing.
6. **Report-Generator:** Wilson-CI + McNemar + Safety-Rollup → Markdown/JSON, mit Panel-/Schedule-/Config-Hash.
7. **`--brain {heuristic|shadow|override}`-Flag** verdrahten (heuristic/shadow aus 2b-3; override = Stub bis 2b-4).
8. **Presets:** `smoke` (~50) und `full` (~600–800) Schedules.

---

## Integrationspunkte (checken / ggf. kleiner Zusatz — markiert **unsicher**, weil ich deine `gauntlet`-Interna nicht sehe)

- **Sim-PRNG-Seed je Battle** im `gauntlet` setzbar? (Showdown-Sim unterstützt es — Frage ist, ob der
  Harness es durchreicht.) → **blockierend für Wiederholbarkeit**.
- **`gauntlet` mit zwei verschiedenen Teams** (non-Mirror) + Team je Battle aus Schedule?
- **Granulares Per-Battle-Ergebnis** (nicht nur Aggregat-Winrate wie `--strict`) für Pairing verfügbar?
- **Gegner-RNG aus Battle-Seed** seedbar (deterministische Gegner)?

Wenn einer dieser vier „nein" ist, ist es jeweils ein kleiner, isolierter Zusatz am `gauntlet` — kein
neues System.
