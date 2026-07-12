# Value-Calibration-Studie (ADR-0004-De-Risk) — Design

**Date:** 2026-07-12 · **Branch:** `feat/slice-value-calibration` (worktree at plan time, off local main) · **Status:** design, awaiting final user review

## Ziel & Framing

Vor jedem Value-Head-Bau (Kaggle-GPU-Training, die große Wette) offline und billig eine Vorfrage beantworten: **Trägt die konkrete Aktion — über die reine Brettstellung hinaus — Signal, das den späteren Spielausgang vorhersagt, und geht davon etwas verloren, wenn die Heuristik es zu einem Skalar aggregiert?**

Das ist explizit *nicht* dieselbe Frage wie "wie gut sagt eine Stellung unter der bestehenden Policy den Sieger vorher" — letzteres wird vom Stellungswert dominiert (wer gerade gewinnt), nicht von der Diskriminierung zwischen Aktionen. Die Studie isoliert den **inkrementellen Beitrag der Aktion über den Stellungswert hinaus**, nicht eine globale AUC.

**Framing:** Outcome-Prediction-Klassifikation. Einheit = die von der aktuellen Heuristik **gespielte** Kandidatin einer Entscheidung; Label = der reale Spielausgang (Sieg/Niederlage) des Spiels, zu dem die Entscheidung gehört. Kein Ranking-Framing (keine kontrafaktischen Outcomes ungespielter Aktionen vorhanden), keine Regression (Outcome ist binär).

**Harte Grenze, die die ganze Studie prägt:** Es gibt nur Outcomes der tatsächlich gespielten Aktionen — keine Outcomes von Alternativen. Jeder gemessene Zugewinn ist daher eine **obere Schranke** auf das echte Aktions-Signal (die gewählte Aktion kann Stellungsinformation kodieren, die dem State-only-Modell entgeht — ein Proxy-Konfound, siehe Limitations) und bleibt **diagnostisch**, nicht beweisend. Der positive Ausgang dieser Studie ist deshalb **„GO für kontrafaktische Value-Head-Datenerhebung/-Experiment"**, niemals „Value-Head gerechtfertigt" — ein Value-Head selbst braucht Outcomes alternativer Aktionen, die dieser beobachtende Datensatz nicht liefert.

## Daten & Datenqualität (verifiziert gegen `data/datasets/phase3-slice2b25a/`)

- **Basis:** `dataset.jsonl.gz`, 17.458 Kandidaten-Zeilen über 299 Spiele, 4 Team-Archetypen (fixed/trickroom/sun/rain, Schlüssel `metadata.team_hash`). Schema fixiert in `learning/schema.py` (`CONTEXT_FEATURES`, `ACTION_FEATURES`, `HEURISTIC_FEATURES`, `TEMPO_FEATURES`).
- **Analyseeinheit:** eine Zeile pro Entscheidung — die von `chosen_by_current_heuristic==true` markierte Kandidatin. Verifiziert: 3.302 eindeutige `(game_id, decision_id)`-Paare, jede mit ≥1 chosen-Zeile (keine Entscheidung ohne Chosen-Zeile).
- **Outcome-Labels kommen NICHT aus `dataset.jsonl.gz`** — dessen `metadata.game_outcome` ist für alle Zeilen der Platzhalter `"__pending__"`. Die echten Labels liefert `run_outcome_join()` (`showdown_bot.learning.outcome_join.runner`, sauber importierbar, kein Subprozess) als Pipeline-Schritt 1 dieser Studie, aufgerufen mit denselben 4 `results.jsonl`-Dateien, die 04's Referenz-Smoke bereits validiert hat (`data/datasets/phase3-slice2b25a/evidence/{fixed,trickroom,sun,rain}/results.jsonl`). Der Sidecar liefert `game_id → {game_outcome ∈ {1.0, -1.0, 0.0}, team_hash, winner, final_turn, battle_id}`, eine Zeile pro Spiel (299 Zeilen, verifiziert). `0.0` (Tie) ist im Schema zulässig, kam aber in 04's Referenz-Smoke über alle 299 Spiele nicht vor — kein Tie-Sonderfall in dieser Panel-Auflage zu erwarten, aber die Verarbeitung sollte ihn nicht stillschweigend falsch behandeln, falls ein künftiger Lauf doch einen liefert. `team_hash` liegt damit direkt für LOTO bereit, kein zusätzliches Mapping nötig.

### Action-Identity-Kollision (verifiziert, kein Score-Tie)

253 der 3.302 Entscheidungen (~7,7 %) haben **zwei** als `chosen_by_current_heuristic` markierte Zeilen. Direkt an den Daten geprüft: **jede** dieser 253 Gruppen hat Größe genau 2, und die beiden Zeilen unterscheiden sich in **keinem** Feld außer `slot1_switch_target_species_id` (136 Fälle) bzw. `slot2_switch_target_species_id` (126 Fälle) — auch `heuristic_aggregate_score` ist byte-identisch zwischen den beiden. Das ist **keine** Score-Gleichheit zweier echt unterschiedlicher Kandidaten, sondern eine switch-target-blinde Zeilen-Duplikation: zwei verschiedene Switch-Ziele teilen sich offenbar dieselbe interne Kandidaten-Identität beim Schreiben des Datasets und erben dadurch gemeinsam das Chosen-Label. Root Cause ist außerhalb des Scopes dieser Studie (Feature-Extraktions-Pipeline, nicht die Kalibrierung selbst).

**Handhabung:**
- **Primär:** nur die 3.302 − 253 = **3.049 eindeutigen** Entscheidungen (genau eine Chosen-Zeile). Tier 1–4 werden ausschließlich auf dieser Menge gefittet/evaluiert — identische Entscheidungsmenge über alle vier Stufen hinweg, damit Tier-Vergleiche nicht durch unterschiedliche Populationen konfundiert werden.
- **Sensitivität:** State-only (Tier 1) zusätzlich auf **allen 3.302** Entscheidungen (für die 253 Kollisionsfälle beide Zeilen sind hier unproblematisch identisch dedupliziert auf eine, z. B. niedrigster `candidate_index` — sicher, weil Tier-1-Features nachweislich nicht vom Kandidaten abhängen). Vergleich gegen das 3.049er-Ergebnis prüft, ob der Ausschluss der 253 eine Selektionsverzerrung einführt.
- **Bedingte Aufnahme:** die 253 Fälle fließen nur in die Primäranalyse ein, falls die tatsächlich gespielte Switch-Aktion aus Logs/Traces (`metadata.teacher_trace`, ggf. ein Per-Decision-Replay-Log) eindeutig rekonstruierbar ist. **Machbarkeit ungeprüft** — im Stichprobenbeispiel war `teacher_trace` ein leerer String; ob ein per-Entscheidung `/choose`-Log für 2b-2.5a überhaupt existiert, muss die Implementierung zuerst klären. Fail-closed: nicht rekonstruierbar ⇒ bleibt ausgeschlossen.
- **Reporting:** im Report konsequent **„Action-Identity-Kollision"** nennen, nicht „Score-Tie". Es gibt keine literale `candidate_id`-Spalte im Schema (nur `candidate_index`) — der Report beschreibt den Mechanismus präzise (switch-target-blinde Duplikation), ohne ein nicht-existentes Feld zu behaupten.

## Vier strikt verschachtelte Modellstufen

`HEURISTIC_FEATURES` aus `schema.py` bündelt für den Reranker zwei konzeptuell verschiedene Dinge (rohe kalkulierte Konsequenzen der Aktion vs. die Heuristik-eigenen Aggregations-Outputs) — für diese Studie feiner getrennt. Jede Feldzugehörigkeit unten ist gegen `learning/features.py` verifiziert: `_group3_eval(candidate, trace)` liest ausschließlich aus `candidate.*` (also echt aktionsabhängig); `_group4_tempo(candidate, trace, state, ctx)` liest bis auf eine Ausnahme aus `trace`/`ctx` (also entscheidungs-level/state-only).

| Tier | + Feature-Gruppe | Felder |
|---|---|---|
| **1 State-only** | `CONTEXT_FEATURES` (17) + `TEMPO_FEATURES` minus 1 (10) | `game_mode`, `turn_number`, `endgame_flag`, `our/opp_alive_count`, `our/opp_total_hp_frac`, `field_weather`, `field_terrain`, `tailwind_ours/opp`, `trick_room_active`, `screens_ours/opp`, `speed_control_state`, `format_id`, `mirror_flag`; `we/they_outspeed_count`, `speed_tie_count`, `our/opp_fastest_active_speed`, `must_react_reason_flags`, `protect_prior_target1/2`, `response_count`, `opponent_response_entropy` |
| **2 + Aktions-Identität** | `ACTION_FEATURES` (27) | slot1/2 `action_type`, `move_id`, `move_type`, `move_category`, `target_kind`, `target_slot`, `priority`, `is_damaging`, `is_protect`, `is_switch`, `actor_species_id`, `switch_target_species_id`, `target_species_id_if_known`; `tera_used` |
| **3 + aktionsabhängige Prädiktionen** | 12 von `HEURISTIC_FEATURES` | `predicted_outgoing_damage`, `predicted_incoming_damage`, `out_in_ratio`, `predicted_kos_for`, `predicted_kos_against`, `ko_secured_count`, `ko_threatened_count`, `survives_for_sure_count`, `protect_stall_penalty`, `partner_abandon_penalty`, `fakeout_invalid_penalty`, `action_economy_score` |
| **4 + Heuristik-Aggregation** | 7 von `HEURISTIC_FEATURES` + 1 aus `TEMPO_FEATURES` | `heuristic_aggregate_score`, `score_gap_to_top`, `score_gap_to_second`, `score_min_vs_opp`, `score_mean_vs_opp`, `score_var_vs_opp`, `score_worst_response`, **`value_range_across_opp_responses`** |

`value_range_across_opp_responses` gehört trotz seiner `TEMPO_FEATURES`-Zugehörigkeit im Reranker-Schema hierher: verifiziert `= max(sv) - min(sv)` von `candidate.score_vector` — eine Score-Vektor-Statistik, kein Stellungsmerkmal.

Zwei Felder (`fakeout_invalid_penalty`, `action_economy_score`) sind im Code hart auf `0.0` gepinnt (Kommentar: „sentinel, future task“) und tragen aktuell keine Varianz. Im Report vermerken, damit ihr Nullbeitrag zu Tier 3 nicht als Befund missverstanden wird.

## Gewichtung

`row_weight = 1 / decisions_in_game` (primär) — verifiziert 3.049 bereinigte Entscheidungen über 299 Spiele, 1–53 Entscheidungen/Spiel (Mittel ~12); ohne Normierung würden lange Spiele das Training dominieren. Entscheidungs-gewichtet (`row_weight=1`) nur als Sensitivitätsanalyse, explizit gekennzeichnet.

## Primärer, vorab fixierter Endpunkt

Genau **ein** Gate-Endpunkt: **gepaarte, game-geclusterte ΔAUC(Tier 3 − Tier 1)** auf den 3.049 bereinigten Entscheidungen.

**Prozedur:**
1. **5-fold `GroupKFold` nach `game_id`** (nicht nach Team — das ist der separate LOTO-Check unten) über die 3.049 Entscheidungen.
2. Tier 1 und Tier 3 werden auf **denselben** Folds trainiert (identische Trainings-/Test-Aufteilung für beide ⇒ gepaart). Primäre Modellklasse: **LightGBM-Klassifikator** (bestehende Dependency, verträgt kategoriale Move-/Species-IDs nativ, kein One-Hot-Blowup). Hyperparameter ausschließlich auf den Trainings-Folds gewählt (nested CV oder feste konservative Defaults angesichts des kleinen n) — nie unter Sicht des jeweiligen Test-Folds.
3. Out-of-fold-Predictions beider Modelle sammeln → gepoolte, game-gewichtete AUC pro Tier.
4. **Game-geclusterter Bootstrap:** Spiele (nicht Zeilen) resamplen, für jedes Resample beide AUCs aus den zugehörigen OOF-Predictions neu berechnen ⇒ ΔAUC-Verteilung, 95%-CI. Effektives n = 299 Spiele (bzw. die Teilmenge der Spiele mit ≥1 bereinigter Entscheidung), nicht 17.458 unabhängige Zeilen.
5. **Sekundäres Modell (Robustheit):** dieselbe Prozedur mit Logistic Regression statt LightGBM — prüft, ob der Befund an ein flexibles Modell gebunden ist oder auch unter einem einfachen linearen Modell hält (Sorge: LightGBM-Overfitting bei ~2.400 Trainings-Entscheidungen pro Fold).

Primärkriterium: ΔAUC(Tier3−Tier1)-CI schließt 0 aus (positiv) **und** übersteht den LOTO-Robustheitscheck (siehe unten). Beide Bedingungen müssen erfüllt sein.

Tier 4 − Tier 3 (verliert die Heuristik-Aggregation Signal gegenüber den granularen Tier-3-Features?) ist eine **sekundäre** Analyse, kein Teil des Primär-Gates.

## LOTO-Robustheitscheck (Pflicht, vorab präzisiert)

**Prozedur:** 4 Folds, je ein Team-Archetyp (`team_hash`) als Holdout. Pro Fold: Tier 1 und Tier 3 auf den 3 übrigen Teams trainieren (game-gewichtet), ΔAUC auf dem Holdout-Team allein auswerten (game-gewichtet innerhalb des Folds via `row_weight`).

**„Robust" ist vorzeichenbasiert definiert, nicht über eine erfundene Magnitude-Schwelle** (dieselbe Disziplin wie bei den verworfenen 0.05/0.70-Cutoffs, jetzt konsequent auf diesen neuen Check angewendet):

- **Macro-ΔAUC = ungewichteter Mittelwert der 4 Fold-ΔAUCs** (jedes Archetyp zählt gleich — das ist der Zweck von LOTO; ein nach Spielanzahl gewichtetes Makro-Mittel würde die ohnehin fast balancierten Teams [74–75 Spiele je] nur unnötig wieder in Richtung Mehrheitsteam verzerren).
- **Robust ⟺ Macro-ΔAUC > 0 UND alle 4 Fold-ΔAUCs einzeln > 0.** Kein Fold darf negativ ausschlagen — sign-basiert, nichts an Magnitude zu rechtfertigen.
- Falls Macro-ΔAUC > 0, aber nicht alle 4 Folds positiv: als **„gemischt/team-abhängig"** berichten — eine echte, nützliche Information, aber das Primär-Gate gilt dann als **nicht bestanden** (kein stilles Wegmitteln).
- Jeder Fold-Wert wird **einzeln ausgewiesen** (nicht nur das Makro-Mittel), zusätzlich mit einem game-geclusterten Bootstrap-CI **innerhalb** der jeweiligen Holdout-Spiele (~75 Spiele je Fold — CIs werden breit sein; das ist Kontext, kein zusätzliches Gate).
- **Terminologie:** die Differenz (gemischt-CV-AUC − LOTO-AUC) heißt **„Archetypen-Generalisierungslücke"**, nicht „Basisraten-Memorisierungs-Anteil" — Distribution-Shift, unbekannte Team-Kombinationen und kleinere effektive Trainingsmenge sind mögliche Mitursachen, nicht nur Memorisierung der Team-Basisrate.

## Sekundär / explorativ (kein Gate)

- **Brier Score, Log Loss, Reliability-Kurven** für alle 4 Tiers (aus denselben OOF-Predictions).
- **Früh- vs. Spät-Züge separat** ausgewertet (Credit-Assignment-Frage: trägt die Aktion früh im Spiel weniger Outcome-Signal als spät?).
- **Tier 4 − Tier 3:** verliert die finale Heuristik-Aggregation Signal, das in den granularen Tier-3-Features noch steckt?
- **Sensitivität:** (a) State-only auf allen 3.302 vs. auf den 3.049 bereinigten Entscheidungen (Selektionsverzerrung durch den Ausschluss?); (b) entscheidungs-gewichtet (`row_weight=1`) vs. spiel-gewichtet.

## Verdikt

Drei mögliche Ausgänge, alle vorab benannt:

1. **GO für kontrafaktische Value-Head-Datenerhebung/-Experiment:** Primärkriterium erfüllt (CI schließt 0 aus, LOTO-robust). Bedeutet: die Aktion trägt nachweisbar Outcome-Signal über die Stellung hinaus, das (mindestens teilweise) über die aktuelle Heuristik-Aggregation hinausgeht — genug Grund, in eine kontrafaktische Datenerhebung zu investieren (nicht: genug Grund für ein Value-Head selbst).
2. **NO-GO:** Primärkriterium nicht erfüllt (CI enthält 0, oder LOTO nicht robust). Bedeutet: kein belastbares Signal jenseits der Stellung gefunden — Such-Hebel statt Eval-Hebel bleibt die Priorität.
3. **Inconclusive:** CIs zu breit, um bei nur 4 Archetypen/n=299 Spielen zwischen 1 und 2 zu unterscheiden. Gültiger, kein Fehlschlag-Ausgang — verknüpft mit 05's Panel-Erweiterung (mehr Archetypen/Spiele) als Voraussetzung für einen erneuten Versuch.

## Deliverable & Struktur

Ein **offline, import-guarded Modul** `showdown_bot.learning.value_calibration` (Muster wie `learning.outcome_join`, `learning.reranker_ablation`), das `run_outcome_join()` als Bibliotheksaufruf wiederverwendet (kein Subprozess). Rührt den Live-Pfad nicht an. Deliverables: das Modul, ein committeter Report (JSON+MD, deterministisch), Tests je Baustein (Tier-Feature-Split, Kollisions-Erkennung/-Ausschluss, Gewichtung, gepaarter Bootstrap, LOTO-Fold-Logik), eine Referenz-Smoke auf `phase3-slice2b25a` (analog zu 04's Smoke).

## Non-Goals

Kein Value-Head-Training, kein Kaggle, kein Held-out-Zugriff, keine Live-Pfad-Änderung, keine kontrafaktische Ranking-Kalibrierung (Daten fehlen), keine Root-Cause-Behebung der Action-Identity-Kollision in der Feature-Extraktions-Pipeline (nur Erkennung + sichere Handhabung in dieser Studie).
