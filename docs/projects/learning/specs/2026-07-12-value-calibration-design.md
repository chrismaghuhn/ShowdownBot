# Value-Calibration-Studie (ADR-0004-De-Risk) — Design

**Date:** 2026-07-12 · **Branch:** `feat/slice-value-calibration` (worktree at plan time, off local main) · **Status:** design, planungsreif (Revision 2, s. Changelog)

## Ziel & Framing

Vor jedem Value-Head-Bau (Kaggle-GPU-Training, die große Wette) offline und billig **zwei getrennte Vorfragen** beantworten — sie brauchen zwei unterschiedliche Vergleiche und folgen nicht auseinander:

1. **Trägt die konkrete Aktion — über die reine Brettstellung hinaus — Signal, das den späteren Spielausgang vorhersagt?** Primäres Gate, Vergleich `T3 − T1`.
2. **Falls ja: geht davon etwas verloren, wenn die Heuristik es zu einem Skalar aggregiert, statt die granularen Prädiktionen direkt zu nutzen?** Sekundär, Vergleich `T3 − T3A`. **Nicht** aus einem positiven `T3 − T1` allein ableitbar (Revision-1-Fehler, siehe Changelog) — braucht seinen eigenen, expliziten Test.

Das ist explizit *nicht* dieselbe Frage wie "wie gut sagt eine Stellung unter der bestehenden Policy den Sieger vorher" — letzteres wird vom Stellungswert dominiert (wer gerade gewinnt), nicht von der Diskriminierung zwischen Aktionen. Die Studie isoliert den **inkrementellen Beitrag der Aktion über den Stellungswert hinaus**, nicht eine globale AUC.

**Framing:** Outcome-Prediction-Klassifikation. Einheit = die von der aktuellen Heuristik **gespielte** Kandidatin einer Entscheidung; Label = der reale Spielausgang (Sieg/Niederlage) des Spiels, zu dem die Entscheidung gehört. Kein Ranking-Framing (keine kontrafaktischen Outcomes ungespielter Aktionen vorhanden), keine Regression (Outcome ist binär).

**Harte Grenze, die die ganze Studie prägt:** Es gibt nur Outcomes der tatsächlich gespielten Aktionen — keine Outcomes von Alternativen. Jeder gemessene Zugewinn ist daher eine **obere Schranke** auf das echte Aktions-Signal (die gewählte Aktion kann Stellungsinformation kodieren, die dem State-only-Modell entgeht — ein Proxy-Konfound, siehe Limitations) und bleibt **diagnostisch**, nicht beweisend. Der positive Ausgang dieser Studie ist deshalb **„GO für kontrafaktische Value-Head-Datenerhebung/-Experiment"**, niemals „Value-Head gerechtfertigt" — ein Value-Head selbst braucht Outcomes alternativer Aktionen, die dieser beobachtende Datensatz nicht liefert.

## Daten & Datenqualität (verifiziert gegen `data/datasets/phase3-slice2b25a/`)

- **Basis:** `dataset.jsonl.gz`, 17.458 Kandidaten-Zeilen über 299 Spiele, 4 Team-Archetypen (fixed/trickroom/sun/rain, Schlüssel `metadata.team_hash`). Schema fixiert in `learning/schema.py` (`CONTEXT_FEATURES`, `ACTION_FEATURES`, `HEURISTIC_FEATURES`, `TEMPO_FEATURES`).
- **Analyseeinheit:** eine Zeile pro Entscheidung — die von `chosen_by_current_heuristic==true` markierte Kandidatin. Verifiziert: 3.302 eindeutige `(game_id, decision_id)`-Paare, jede mit ≥1 chosen-Zeile (keine Entscheidung ohne Chosen-Zeile).
- **Outcome-Labels kommen NICHT aus `dataset.jsonl.gz`** — dessen `metadata.game_outcome` ist für alle Zeilen der Platzhalter `"__pending__"`. Die echten Labels liefert `run_outcome_join()` (`showdown_bot.learning.outcome_join.runner`, sauber importierbar, kein Subprozess) als Pipeline-Schritt 1 dieser Studie, aufgerufen mit denselben 4 `results.jsonl`-Dateien, die 04's Referenz-Smoke bereits validiert hat (`data/datasets/phase3-slice2b25a/evidence/{fixed,trickroom,sun,rain}/results.jsonl`). Der Sidecar liefert `game_id → {game_outcome ∈ {1.0, -1.0, 0.0}, team_hash, winner, final_turn, battle_id}`, eine Zeile pro Spiel (299 Zeilen, verifiziert). `team_hash` liegt damit direkt für LOTO bereit, kein zusätzliches Mapping nötig.

### Action-Identity-Kollision (verifiziert, kein Score-Tie)

253 der 3.302 Entscheidungen (~7,7 %) haben **zwei** als `chosen_by_current_heuristic` markierte Zeilen. Direkt an den Daten geprüft: **jede** dieser 253 Gruppen hat Größe genau 2, und die beiden Zeilen unterscheiden sich in **keinem** Feld außer `slot1_switch_target_species_id` (136 Fälle) bzw. `slot2_switch_target_species_id` (126 Fälle) — auch `heuristic_aggregate_score` ist byte-identisch zwischen den beiden. Das ist **keine** Score-Gleichheit zweier echt unterschiedlicher Kandidaten, sondern eine switch-target-blinde Zeilen-Duplikation: zwei verschiedene Switch-Ziele teilen sich offenbar dieselbe interne Kandidaten-Identität beim Schreiben des Datasets und erben dadurch gemeinsam das Chosen-Label. Root Cause ist außerhalb des Scopes dieser Studie (Feature-Extraktions-Pipeline, nicht die Kalibrierung selbst).

**Handhabung:**
- **Primär:** nur die 3.302 − 253 = **3.049 eindeutigen** Entscheidungen (genau eine Chosen-Zeile). Alle Modellstufen (T1/T2/T3/T3A/T4) werden ausschließlich auf dieser Menge gefittet/evaluiert — identische Entscheidungsmenge über alle Stufen hinweg, damit Vergleiche nicht durch unterschiedliche Populationen konfundiert werden.
- **Sensitivität:** T1 (State-only) zusätzlich auf **allen 3.302** Entscheidungen (für die 253 Kollisionsfälle beide Zeilen hier unproblematisch identisch dedupliziert auf eine, z. B. niedrigster `candidate_index` — sicher, weil T1-Features nachweislich nicht vom Kandidaten abhängen). Vergleich gegen das 3.049er-Ergebnis prüft, ob der Ausschluss der 253 eine Selektionsverzerrung einführt.
- **Bedingte Aufnahme:** die 253 Fälle fließen nur in die Primäranalyse ein, falls die tatsächlich gespielte Switch-Aktion aus Logs/Traces (`metadata.teacher_trace`, ggf. ein Per-Decision-Replay-Log) eindeutig rekonstruierbar ist. **Machbarkeit ungeprüft** — im Stichprobenbeispiel war `teacher_trace` ein leerer String; ob ein per-Entscheidung `/choose`-Log für 2b-2.5a überhaupt existiert, muss die Implementierung zuerst klären. Fail-closed: nicht rekonstruierbar ⇒ bleibt ausgeschlossen.
- **Reporting:** im Report konsequent **„Action-Identity-Kollision"** nennen, nicht „Score-Tie". Es gibt keine literale `candidate_id`-Spalte im Schema (nur `candidate_index`) — der Report beschreibt den Mechanismus präzise (switch-target-blinde Duplikation), ohne ein nicht-existentes Feld zu behaupten.

## Fünf Modellstufen: vier verschachtelt + ein Parallelarm

`HEURISTIC_FEATURES` aus `schema.py` bündelt für den Reranker zwei konzeptuell verschiedene Dinge (rohe kalkulierte Konsequenzen der Aktion vs. die Heuristik-eigenen Aggregations-Outputs) — für diese Studie feiner getrennt. Jede Feldzugehörigkeit unten ist gegen `learning/features.py` verifiziert: `_group3_eval(candidate, trace)` liest ausschließlich aus `candidate.*` (also echt aktionsabhängig); `_group4_tempo(candidate, trace, state, ctx)` liest bis auf eine Ausnahme aus `trace`/`ctx` (also entscheidungs-level/state-only).

Zwei Feature-Bausteine, benannt für die Tabelle unten:
- **PRED** (12 Felder, 12 von `HEURISTIC_FEATURES`): `predicted_outgoing_damage`, `predicted_incoming_damage`, `out_in_ratio`, `predicted_kos_for`, `predicted_kos_against`, `ko_secured_count`, `ko_threatened_count`, `survives_for_sure_count`, `protect_stall_penalty`, `partner_abandon_penalty`, `fakeout_invalid_penalty`, `action_economy_score` — granulare, aktionsabhängige Prädiktionen.
- **AGG** (8 Felder, 7 von `HEURISTIC_FEATURES` + 1 aus `TEMPO_FEATURES`): `heuristic_aggregate_score`, `score_gap_to_top`, `score_gap_to_second`, `score_min_vs_opp`, `score_mean_vs_opp`, `score_var_vs_opp`, `score_worst_response`, `value_range_across_opp_responses` — die Heuristik-eigenen Aggregations-Outputs (Statistiken des Score-Vektors bzw. der finale Skalar selbst). `value_range_across_opp_responses` gehört trotz seiner `TEMPO_FEATURES`-Zugehörigkeit im Reranker-Schema hierher: verifiziert `= max(sv) - min(sv)` von `candidate.score_vector` — eine Score-Vektor-Statistik, kein Stellungsmerkmal.

| Stufe | Feature-Zusammensetzung | Rolle |
|---|---|---|
| **T1** | `CONTEXT_FEATURES` (17) + `TEMPO_FEATURES` minus `value_range_across_opp_responses` (10) = **State-only** | Baseline |
| **T2** | T1 + `ACTION_FEATURES` (27) = **+ Aktions-Identität** | konzeptuelle Zwischenstufe (Feld-Dokumentation; kein eigener Fit/Vergleich nötig) |
| **T3** | T2 + PRED = **+ granulare aktionsabhängige Prädiktionen** | primärer Vergleichsarm |
| **T3A** | T2 + AGG, **ohne PRED** = **+ Heuristik-Aggregation, ohne die granularen Prädiktionen** | Parallelarm — gleiche Feature-*Menge* wie T2, aber die AGG- statt der PRED-Bausteine oben drauf |
| **T4** | T2 + PRED + AGG = T3 + AGG = **volle Feature-Menge** | sekundärer Vergleichsarm |

`ACTION_FEATURES` (T2-Zusatz, für beide Zweige gleich): slot1/2 `action_type`, `move_id`, `move_type`, `move_category`, `target_kind`, `target_slot`, `priority`, `is_damaging`, `is_protect`, `is_switch`, `actor_species_id`, `switch_target_species_id`, `target_species_id_if_known`; `tera_used`.

**Vier tatsächlich gefittete Modelle: T1, T3, T3A, T4** (T2 ist nur die dokumentierte Zwischenmenge, kein eigener Vergleichspunkt — niemand hat danach gefragt und es beantwortet keine der beiden Forschungsfragen). Damit ergeben sich die drei Vergleiche:

- **`T3 − T1`**: Aktionssignal über State hinaus (**primäres Gate**).
- **`T3 − T3A`**: granulare Prädiktionen gegenüber ihrer komprimierten Aggregation — **die tatsächliche Informationsverlust-Frage**. T3A hat exakt dieselbe Feature-*Anzahl-Kategorie* wie T3 (T2 + 8 zusätzliche Felder statt T2 + 12), ersetzt aber PRED durch AGG, statt PRED zu ergänzen — beide Modelle sehen also "T2 plus eine gleich große zusätzliche Informationsquelle", nur einmal granular und einmal komprimiert.
- **`T4 − T3`**: komplementärer Zusatznutzen der Aggregation **on top of** den granularen Prädiktionen (fügt AGG zusätzlich zu PRED hinzu — testet NICHT, ob Information verloren geht, sondern ob AGG *zusätzliches, nicht-redundantes* Signal beisteuert).

Zwei Felder (`fakeout_invalid_penalty`, `action_economy_score`, beide in PRED) sind im Code hart auf `0.0` gepinnt (Kommentar: „sentinel, future task“) und tragen aktuell keine Varianz. Im Report vermerken, damit ihr Nullbeitrag zu T3/T4 nicht als Befund missverstanden wird.

## Gewichtung

`row_weight = 1 / decisions_in_game` (primär) — verifiziert 3.049 bereinigte Entscheidungen über 299 Spiele, 1–53 Entscheidungen/Spiel (Mittel ~12); ohne Normierung würden lange Spiele das Training dominieren. Entscheidungs-gewichtet (`row_weight=1`) nur als Sensitivitätsanalyse, explizit gekennzeichnet.

## Primärer, vorab fixierter Endpunkt

Genau **ein** Gate-Endpunkt: **gepaarte, game-geclusterte ΔAUC(T3 − T1)** auf den 3.049 bereinigten Entscheidungen.

**Prozedur:**
1. **5-fold `GroupKFold` nach `game_id`** (nicht nach Team — das ist der separate LOTO-Check unten) über die 3.049 Entscheidungen. Dieselben Folds werden für **alle vier Modelle** (T1, T3, T3A, T4) verwendet, damit jeder paarweise Vergleich (`T3−T1`, `T3−T3A`, `T4−T3`) auf identischen Train/Test-Splits beruht.
2. Primäre Modellklasse: **LightGBM-Klassifikator** (bestehende Dependency, verträgt kategoriale Move-/Species-IDs nativ, kein One-Hot-Blowup). Hyperparameter ausschließlich auf den Trainings-Folds gewählt (nested CV oder feste konservative Defaults angesichts des kleinen n) — nie unter Sicht des jeweiligen Test-Folds.
3. Out-of-fold-Predictions aller vier Modelle sammeln → gepoolte, game-gewichtete AUC pro Stufe.
4. **Game-geclusterter Bootstrap** (Details s. „Technische Grundlage" unten): Spiele resamplen, für jedes Resample die relevanten AUCs aus den zugehörigen OOF-Predictions neu berechnen ⇒ ΔAUC-Verteilung, 95 %-CI, für `T3−T1`, `T3−T3A` und `T4−T3` je einzeln. Effektives n = 299 Spiele (bzw. die Teilmenge der Spiele mit ≥1 bereinigter Entscheidung), nicht 17.458 unabhängige Zeilen.
5. **Sekundäres Modell (Robustheit):** dieselbe Prozedur mit Logistic Regression statt LightGBM — prüft, ob der `T3−T1`-Befund an ein flexibles Modell gebunden ist oder auch unter einem einfachen linearen Modell hält (Sorge: LightGBM-Overfitting bei ~2.400 Trainings-Entscheidungen pro Fold).

**Primärkriterium (nur für `T3−T1`):** Punktschätzer > 0, CI schließt 0 vollständig aus, **und** übersteht den LOTO-Robustheitscheck (siehe unten). Alle drei Bedingungen müssen erfüllt sein — genaue Verdikt-Logik im Abschnitt „Verdikt".

`T3 − T3A` und `T4 − T3` sind **sekundäre** Analysen (eigene CIs berichtet, gleiche Bootstrap-Prozedur, aber **kein Teil des Primär-Gates** und **kein eigener LOTO-Pflichtcheck** — LOTO gilt ausschließlich für den Primärvergleich).

## LOTO-Robustheitscheck (Pflicht für `T3 − T1`, vorab präzisiert)

**Prozedur:** 4 Folds, je ein Team-Archetyp (`team_hash`) als Holdout. Pro Fold: T1 und T3 auf den 3 übrigen Teams trainieren (game-gewichtet), ΔAUC auf dem Holdout-Team allein auswerten (game-gewichtet innerhalb des Folds via `row_weight`).

**„Robust" ist vorzeichenbasiert definiert, nicht über eine erfundene Magnitude-Schwelle** (dieselbe Disziplin wie bei den verworfenen 0.05/0.70-Cutoffs, jetzt konsequent auf diesen Check angewendet):

- **Macro-ΔAUC = ungewichteter Mittelwert der 4 Fold-ΔAUCs** (jedes Archetyp zählt gleich — das ist der Zweck von LOTO; ein nach Spielanzahl gewichtetes Makro-Mittel würde die ohnehin fast balancierten Teams [74–75 Spiele je] nur unnötig wieder in Richtung Mehrheitsteam verzerren).
- **Robust ⟺ Macro-ΔAUC > 0 UND alle 4 Fold-ΔAUCs einzeln > 0.** Kein Fold darf negativ ausschlagen — sign-basiert, nichts an Magnitude zu rechtfertigen.
- Jeder Fold-Wert wird **einzeln ausgewiesen** (nicht nur das Makro-Mittel), zusätzlich mit einem game-geclusterten Bootstrap-CI **innerhalb** der jeweiligen Holdout-Spiele (~75 Spiele je Fold — CIs werden breit sein; das ist Kontext, kein zusätzliches Gate).
- **Terminologie:** die Differenz (gemischt-CV-AUC − LOTO-AUC) heißt **„Archetypen-Generalisierungslücke"**, nicht „Basisraten-Memorisierungs-Anteil" — Distribution-Shift, unbekannte Team-Kombinationen und kleinere effektive Trainingsmenge sind mögliche Mitursachen, nicht nur Memorisierung der Team-Basisrate.

## Sekundär / explorativ (kein Gate)

- **`T3 − T3A`:** granulare Prädiktionen vs. ihre komprimierte Aggregation — die Informationsverlust-Frage (s. Ziel & Framing).
- **`T4 − T3`:** komplementärer Zusatznutzen der Aggregation on top of den granularen Prädiktionen.
- **Brier Score, Log Loss, Reliability-Kurven** für alle vier gefitteten Stufen (aus denselben OOF-Predictions).
- **Früh- vs. Spät-Züge separat** ausgewertet (Credit-Assignment-Frage: trägt die Aktion früh im Spiel weniger Outcome-Signal als spät?).
- **Sensitivität:** (a) T1 auf allen 3.302 vs. auf den 3.049 bereinigten Entscheidungen (Selektionsverzerrung durch den Ausschluss?); (b) entscheidungs-gewichtet (`row_weight=1`) vs. spiel-gewichtet.

## Verdikt

Drei **disjunkte** Ausgänge für das Primärkriterium (`T3−T1`), definiert über den Punktschätzer, sein CI, und LOTO — keine Überlappung zwischen den Fällen:

- **GO** (für kontrafaktische Value-Head-Datenerhebung/-Experiment): Punktschätzer `T3−T1` > 0 **und** CI schließt 0 vollständig aus **und** LOTO robust (Macro-ΔAUC > 0 **und** alle 4 Folds > 0). Bedeutet ausschließlich: die Aktion trägt nachweisbar Outcome-Signal über die Stellung hinaus — genug Grund, in eine kontrafaktische Datenerhebung zu investieren. **Sagt nichts darüber aus, ob die Heuristik-Aggregation dabei Signal verliert** — das ist die separat berichtete `T3−T3A`-Analyse, die eigenständig positiv/negativ ausfallen kann und den GO/NO-GO-Status nicht verändert.
- **NO-GO:** Punktschätzer `T3−T1` ≤ 0, **oder** LOTO-Macro-ΔAUC ≤ 0 (unabhängig von der CI-Breite — ein nicht-positiver Punktschätzer oder ein nicht-positives LOTO-Makro-Mittel ist ein eigenständiger Negativ-Befund, keine Unsicherheit). Bedeutet: kein belastbares Signal jenseits der Stellung gefunden — Such-Hebel statt Eval-Hebel bleibt die Priorität.
- **INCONCLUSIVE:** (a) Punktschätzer `T3−T1` > 0, aber CI enthält 0 (Vorzeichen unsicher trotz positivem Punktschätzer); **oder** (b) LOTO-Macro-ΔAUC > 0, aber nicht alle 4 Folds einzeln > 0 — Untertyp **„team-abhängig"**, ein echter, nützlicher Befund, aber kein GO. Gültiger, kein Fehlschlag-Ausgang — verknüpft mit 05's Panel-Erweiterung (mehr Archetypen/Spiele) als Voraussetzung für einen erneuten Versuch.

Die drei Fälle sind erschöpfend und überschneidungsfrei: NO-GOs Bedingungen greifen zuerst (Punktschätzer ≤0 ODER LOTO-Macro ≤0); ist keine davon erfüllt, ist der Punktschätzer positiv und LOTO-Macro positiv — dann entscheidet CI-Breite bzw. Fold-Einheitlichkeit zwischen GO und INCONCLUSIVE.

## Technische Grundlage (explizit gemacht)

- **`scikit-learn`-Dependency fehlt aktuell** in `showdown_bot/pyproject.toml` (`[project.optional-dependencies] learning = ["lightgbm>=4.0", "numpy>=1.24"]` — kein `scikit-learn`). Wird für `GroupKFold`, `LogisticRegression`, `roc_auc_score`, `brier_score_loss`, `log_loss` gebraucht → als Task 1 der Implementierung zur `learning`-Extra hinzufügen (gleiches Muster: nur für Trainings-/Analyse-Code, niemals im Live-Bot-Pfad importiert).
- **Binäre Outcome-Abbildung:** Sidecar liefert `game_outcome ∈ {1.0 (Hero-Sieg), −1.0 (Villain-Sieg), 0.0 (Tie)}`. Für das binäre Klassifikationslabel: Hero(1.0) → **1**, Villain(−1.0) → **0**. **Ties (0.0) werden aus der Primäranalyse ausgeschlossen und separat gezählt/berichtet** (kein Tie in 04's Referenz-Smoke über alle 299 Spiele beobachtet, aber die Pipeline darf nicht stillschweigend falsch abbilden, falls ein künftiger Lauf einen liefert).
- **Kategoriale Encodings ausschließlich auf dem jeweiligen Trainings-Fold fitten** (Vokabular für `move_id`, `actor_species_id`, `switch_target_species_id` etc. NUR aus den Trainings-Fold-Zeilen ableiten — nicht aus dem vollen Datensatz vorab, sonst Leakage der Test-Fold-Kategorien in die Encoding-Struktur). Unbekannte Kategorien im Test-Fold (im Training nie gesehen) auf einen festen `__UNKNOWN__`-Wert abbilden, nicht verwerfen oder crashen. Gilt für LightGBM (kategoriale Spalten) und Logistic Regression (One-Hot/Target-Encoding) gleichermaßen.
- **Outcome-Join fail-closed validieren, zweistufig:** (1) `run_outcome_join()`s eigener Report: `report["status"] == "COMPLETE"` **und** `report["total_labelled"] == 299` (exakt, cross-checked gegen `data/datasets/phase3-slice2b25a/manifest.json`s eigenes `games_with_rows`-Feld — kein Magic Number). **Verifiziert: `build_report()` (outcome_join/report.py) liefert diese Zählung, aber KEINE Liste der abgedeckten `game_id`s** — deshalb (2) zusätzlich **im eigenen Modul**: die `game_id`-Menge aus dem geschriebenen `outcome-labels.jsonl`-Sidecar gegen die `game_id`-Menge der Basisdaten abgleichen (muss exakt übereinstimmen — jedes Dataset-Spiel hat ein Label, kein verwaistes Label ohne Dataset-Spiel). Beide Prüfungen fail-closed: jede Abweichung bricht die Studie ab, statt mit Teildaten weiterzurechnen.
- **Bootstrap-Multiplizität:** der game-geclusterte Bootstrap zieht Spiele **mit Zurücklegen** — ein Resample ist ein Multiset, manche Spiele werden 0×, manche 2×+ gezogen. Beim Berechnen der Resample-Metrik muss jedes gezogene Spiel entsprechend seiner **Ziehungshäufigkeit in diesem Resample** gewichtet werden (`effective_weight = row_weight × draw_count`), nicht nur als Menge/Set einmalig berücksichtigt — sonst ist die Resample-Verteilung verzerrt und die CI-Breite unterschätzt.

## Deliverable & Struktur

Ein **offline, import-guarded Modul** `showdown_bot.learning.value_calibration` (Muster wie `learning.outcome_join`, `learning.reranker_ablation`), das `run_outcome_join()` als Bibliotheksaufruf wiederverwendet (kein Subprozess). Rührt den Live-Pfad nicht an. Deliverables: das Modul, ein committeter Report (JSON+MD, deterministisch), Tests je Baustein (Feature-Split T1/T2/T3/T3A/T4, Kollisions-Erkennung/-Ausschluss, Outcome-Join-Validierung inkl. Game-ID-Abdeckung, Tie-Ausschluss, Gewichtung, kategoriale Fold-Encodings, gepaarter/multiplizitätsgewichteter Bootstrap, LOTO-Fold-Logik, disjunkte Verdikt-Klassifikation), eine Referenz-Smoke auf `phase3-slice2b25a` (analog zu 04's Smoke).

## Non-Goals

Kein Value-Head-Training, kein Kaggle, kein Held-out-Zugriff, keine Live-Pfad-Änderung, keine kontrafaktische Ranking-Kalibrierung (Daten fehlen), keine Root-Cause-Behebung der Action-Identity-Kollision in der Feature-Extraktions-Pipeline (nur Erkennung + sichere Handhabung in dieser Studie).

## Changelog

- **Revision 2 (2026-07-12):** vier Korrekturen nach User-Review: (1) `T3A`-Parallelarm ergänzt, damit `T3−T3A` statt `T4−T3` die Informationsverlust-Frage beantwortet (Revision 1 hatte `T4−T3` fälschlich als Informationsverlust-Test präsentiert, obwohl es Zusatznutzen testet); (2) GO-Verdikt darf aus positivem `T3−T1` keine Aussage über Aggregations-Informationsverlust mehr ableiten; (3) NO-GO/INCONCLUSIVE disjunkt neu definiert; (4) technische Grundlage explizit: `scikit-learn`-Dependency, binäre Outcome-Abbildung + Tie-Ausschluss, fold-lokale kategoriale Encodings, zweistufige fail-closed Outcome-Join-Validierung (inkl. Game-ID-Abdeckungscheck, den `outcome_join`s Report nicht selbst liefert), Bootstrap-Multiplizitätsgewichtung.
- **Revision 1 (2026-07-12):** initiale Fassung nach Brainstorm.
