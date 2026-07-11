# Wiederverwendbares Datensatz- und Reranker-Audit

**Status:** fachlich freigegeben am 2026-07-11

**Dokumenttyp:** Design-Specification

**Repository-Basis:** `c9bb86b`

**Arbeitsbranch:** `codex/analysis-specs`

## 1. Ziel

Das Projekt erhält ein reproduzierbares, fail-closed Auditwerkzeug für gegenwärtige und zukünftige
Reranker-Datensätze. Das Audit prüft nicht nur die JSONL-Syntax, sondern die vollständige
Vertrauenskette von Decision-Gruppen über Splits und Labels bis zu Modellmanifest, OOD-Verhalten und
Kalibrierung.

`data/datasets/phase3-slice2b25a/dataset.jsonl.gz` ist die erste Referenzanwendung. Architektur,
Schwellenwerte und Reports dürfen jedoch keine historischen Row-, Decision- oder Game-Zahlen dieses
Datensatzes voraussetzen.

Das Audit soll insbesondere beantworten:

- Sind Train, Validation und Test wirklich voneinander getrennt?
- Gibt es identische oder nahezu identische Situationen über Splitgrenzen?
- Sind Feature- und Labelverträge intern konsistent?
- Welche Features sind konstant, fast konstant, fehlend, redundant oder driftend?
- Sind Teams, Archetypen, Action-Klassen und Spielsituationen ausreichend vertreten?
- Wie stark weichen Validation/Test oder ein externer Referenzdatensatz von Train ab?
- Sind Reranker-Scores bezüglich Teacher-Treffern zuverlässig kalibriert?
- Stimmen Datensatz, Modell, Feature-Schema und Manifest kryptografisch und semantisch zusammen?

## 2. Abgrenzung zum vorhandenen Code

Vorhandene Bausteine bleiben maßgeblich und werden wiederverwendet:

- `learning.schema.validate_row` validiert die exakten Feature-, Metadata- und Label-Keysets.
- `learning.dataset.load_rows` lädt `.jsonl` und `.jsonl.gz` schema-validiert.
- `learning.dataset.group_decisions` gruppiert über `(game_id, decision_id)`.
- `learning.dataset.split_by_game` erzeugt deterministische, gameweise Splits.
- `learning.reranker_features` enthält Feature-Allowlist, Label-/Metadata-Denylist,
  Kategoriekodierung und Feature-Schema-Hash.
- `learning.reranker_train` erzeugt Modellmanifeste und trainiert LambdaRank.
- `learning.reranker_eval` misst Regret gegen den Rollout-Teacher.
- `learning.reranker_ablation` liefert LOCO-/SCO-Evidenz zur Feature-Nützlichkeit.
- Der bestehende Held-out-Leakage-Test schützt Eval-Schedules. Das neue Audit schützt zusätzlich
  Datensatz- und Splitinhalte; beide Ebenen bleiben getrennt.

Das Audit ersetzt keinen dieser Verträge. Es orchestriert sie, ergänzt fehlende Cross-Split-,
Ähnlichkeits-, Drift-, OOD- und Kalibrierungsprüfungen und liefert einen einheitlichen Befundbericht.

## 3. Leitprinzipien

1. **Decision statt Row als kleinste fachliche Einheit.** Kandidaten einer Decision dürfen niemals
   über Splits verteilt oder isoliert beurteilt werden.
2. **Gameweise Splits.** Train, Validation und Test werden ausschließlich auf Game-Ebene gebildet
   oder über ein explizites Split-Manifest eingelesen.
3. **Harte Integrität blockiert.** Leakage, widersprüchliche Labels, defekte Gruppen und
   Manifest-Mismatches erzeugen `FAIL`.
4. **Statistische Risiken bleiben sichtbar.** Drift, OOD, kleine Subgruppen, Redundanz und schlechte
   Kalibrierung erzeugen `WARN`, aber keine automatische Datenmutation.
5. **Test bleibt unangetastet.** Kalibrierungsparameter und Schwellenwertentscheidungen werden nur
   mit Train/Validation bestimmt; Test wird ausschließlich einmalig ausgewertet.
6. **Kein Strength-Claim.** Ein sauberes Audit belegt Daten- und Modellvertrauen, nicht allgemeine
   Spielstärke.
7. **Reproduzierbarkeit.** Dataset-Hash, Auditkonfiguration, Splitzuordnung, Toolversion und optionale
   Modellartefakte werden vollständig gebunden.
8. **Offline-Isolation.** Das Auditpaket wird nicht vom Live-, Decision-, Gauntlet-, Teacher- oder
   Reranker-Inferenzpfad importiert.

## 4. Eingaben

### 4.1 Pflicht

- Dataset-Pfad zu `.jsonl` oder `.jsonl.gz`
- Auditkonfiguration mit `audit_schema_version`
- entweder ein Split-Manifest oder explizite `split_seed` und `split_ratios`

### 4.2 Optional

- LightGBM-Modellpfad
- Modellmanifestpfad
- Teamkatalog
- ein oder mehrere Referenzdatensätze für Drift-/OOD-Vergleiche
- explizite Ausgabepfade für JSON, Markdown und Splitmanifest

### 4.3 Teamkatalog

Der optionale Katalog ordnet `team_hash` genau einem Datensatz zu:

```text
team_hash -> team_id, archetype, declared_split
```

Unbekannte zusätzliche Felder werden abgelehnt. Doppelte Hashes mit widersprüchlichen Metadaten sind
ein `FAIL`. Fehlt der Katalog, laufen alle anderen Prüfer weiter; Team-/Archetypdimensionen werden
als `unavailable` ausgewiesen. Ein teilweise abdeckender Katalog erzeugt für unbekannte Hashes ein
`WARN`.

### 4.4 Splitquelle

Priorität:

1. explizites Split-Manifest;
2. andernfalls `split_by_game` mit versioniertem Seed und Ratios.

Ein Split-Manifest enthält Dataset-Hash, Split-Schema-Version und genau eine Zuordnung jedes
`game_id` zu `train`, `validation` oder `test`. Fehlende, zusätzliche oder doppelte Games sind ein
`FAIL`. Das Audit erzeugt in jedem Modus eine kanonische Splitzuordnung und deren SHA-256.

## 5. Auditarchitektur

Das neue, vollständig offline arbeitende Paket liegt unter `showdown_bot.learning.audit`:

- `contracts.py` — AuditConfig, Finding, Severity und Reportschema
- `integrity.py` — Schema, Provenance, Gruppen, IDs und Splits
- `duplicates.py` — exakte, semantische und ähnliche Duplikate
- `features.py` — Feature-Gesundheit, Redundanz und Drift
- `labels.py` — Teacher-, Rank-, Tie- und Gap-Konsistenz
- `distribution.py` — Action-Klassen, Teams, Archetypen und OOD
- `model.py` — Manifest, Predictions, Regret und Kalibrierung
- `report.py` — deterministisches JSON und Markdown
- `runner.py` — Orchestrierung und CLI

Jeder Prüfer ist eine pure Funktion über validierte Eingabestrukturen und liefert Findings sowie
seinen Metrikblock. Prüfer verändern weder Rows noch Splits noch Modellartefakte.

## 6. Finding-Vertrag

Jedes Finding besitzt exakt folgende semantische Felder:

- `code` — stabiler, versionierter Bezeichner
- `severity` — `FAIL`, `WARN` oder `INFO`
- `scope` — Dataset, Split, Decision, Feature, Label, Team, OOD, Model oder Calibration
- `message` — kompakte menschenlesbare Aussage
- `count` und `denominator`
- `rate`, falls ein Nenner vorhanden ist
- `split`, falls der Befund splitbezogen ist
- `feature`, falls der Befund featurebezogen ist
- `examples` — deterministisch sortierte, begrenzte IDs
- `evidence` — strukturierte Metriken und verwendete Schwellenwerte
- `remediation` — konkrete Handlungsempfehlung

`examples` ist standardmäßig auf 20 Einträge begrenzt. Gesamtzahlen bleiben vollständig. Findings
werden nach `(severity_rank, code, split, feature, examples)` sortiert. Die Reihenfolge ist nie von
Dateireihenfolge, Hash-Iteration oder Wall-Clock-Zeit abhängig.

### 6.1 Schweregrade

`FAIL` bedeutet: Der Datensatz oder das Modell darf auf Basis dieses Audits nicht für Training,
Freigabe oder belastbare Evaluation verwendet werden, bis der Befund behoben oder durch eine neue
Auditversion fachlich reklassifiziert wurde.

`WARN` bedeutet: Das Artefakt ist formal nutzbar, aber die Aussagekraft ist eingeschränkt. Warnungen
werden niemals still unterdrückt oder automatisch in `INFO` umgewandelt.

`INFO` dokumentiert Coverage, Verteilungen und bestandene Prüfungen.

## 7. Schema-, Provenance- und Gruppenintegrität

Der Integritätsprüfer validiert:

- jede Row über den eingefrorenen Schemavertrag;
- Dataset-SHA-256 über den unkomprimierten JSONL-Inhalt;
- nichtleeres Dataset;
- eindeutige `(game_id, decision_id, candidate_index)`-Schlüssel;
- gruppenweise identische Decision-Metadaten, soweit sie decisionweit sein müssen;
- zusammenhängende Kandidatenindizes `0..n-1`;
- mindestens eine Kandidatenzeile pro Decision;
- genau eine Splitzuordnung pro Game;
- keine Game- oder Decision-Überschneidung zwischen Splits;
- konsistente `schema_version`, `feature_extractor_version`, `teacher_version`, `format_id`,
  `config_hash` und Teacher-Konfiguration innerhalb der jeweils erlaubten Provenance-Gruppen;
- keine Label- oder outcome-tragenden Metadata-Keys in der effektiven Modellfeatureliste.

Gemischte Provenance in einem Dataset ist nicht pauschal verboten. Sie wird nach vollständiger
Provenance-Signatur gruppiert und berichtet. Ein Mix wird `FAIL`, wenn das Modellmanifest oder die
Auditkonfiguration einen homogenen Corpus verlangt oder wenn semantisch inkompatible Schema-/Teacher-
Versionen ohne explizite Allowlist zusammengeführt wurden.

## 8. Duplikate und Split-Leakage

### 8.1 Row-Duplikate

Der kanonische Row-Hash umfasst Features, Metadata und Labels. Doppelte vollständige Rows werden
unabhängig von der Dateiposition erkannt.

### 8.2 Vollständige Decision-Duplikate

Der vollständige Decision-Hash umfasst die nach `candidate_index` sortierten Rows. IDs werden für den
reinen Byte-/Content-Duplikatpfad beibehalten.

### 8.3 Semantische Decision-Duplikate

Der semantische Hash entfernt:

- `game_id`, `decision_id` und `candidate_index` als Identitäten;
- Outcome-Felder und andere nicht modellverfügbare Metadata;
- sämtliche Labels.

Er enthält:

- alle decisionweit verfügbaren Features;
- die sortierte Multimenge der kandidatenspezifischen Featurevektoren;
- Format- und Feature-Extractor-Version;
- Teacher-/Config-Provenance nur als separate Vergleichsdimension.

Gleiche semantische Inputs in verschiedenen Splits sind ein `FAIL`. Gleiche Inputs im selben Split
werden als Duplikatquote berichtet. Haben semantisch gleiche Inputs unter derselben Teacher-
Konfiguration widersprüchliche Labels, entsteht zusätzlich ein Label-`FAIL`.

### 8.4 Near-Duplicates

Eine globale unbeschränkte paarweise Suche ist verboten. Kandidatenpaare werden deterministisch
geblockt nach:

- `format_id`
- Kandidatenzahl
- `game_mode`
- Multimenge der Slot-Aktionsarten

Innerhalb eines Blocks wird eine gemischte Distanz berechnet:

- numerische Features: absolute Differenz nach robuster Skalierung über Train-IQR;
- kategorische Features: Hamming-Distanz;
- kombinierte Distanz: `0.6 * numeric_distance + 0.4 * categorical_distance`.

Kandidaten einer Decision werden dafür über ihren kanonischen kandidatenspezifischen Featurehash
sortiert und positionsweise verglichen. Decisionweite Features werden einmal verglichen,
kandidatenspezifische Distanzen anschließend über alle Kandidaten gemittelt. Die Blocking-Regel
garantiert gleiche Kandidatenzahl; eine nicht eindeutig kanonisierbare Candidate-Struktur erzeugt
ein Integritätsfinding statt eines geratenen Alignments.

Numerische Distanzen werden pro Feature bei 10 gekappt, bevor der Mittelwert gebildet wird. Ein IQR
von null verwendet als Skala `max(abs(train_median), 1.0)`. Fehlende Features erzeugen keinen
willkürlichen Nullwert, sondern einen eigenen Missing-Mismatch.

Defaultschwelle `distance <= 0.05`. Cross-Split-Near-Duplicates erzeugen `WARN`, exakte semantische
Cross-Split-Duplikate bleiben `FAIL`. Schwelle und Gewichte gehören zur Auditkonfiguration und werden
im Report ausgegeben.

## 9. Labelkonsistenz

Pro Decision gelten folgende harten Invarianten:

- mindestens eine `teacher_best`-Row;
- mindestens eine `chosen_by_current_heuristic`-Row;
- Ties und äquivalente Forced-Switch-Auswahlen dürfen mehrere Rows markieren;
- kein Zwang `chosen_by_current_heuristic ⇔ heuristic_rank == 0`;
- `value_gap_to_best <= 0` für jede gelabelte Row;
- jede `teacher_best`-Row besitzt `value_gap_to_best == 0` innerhalb Toleranz `1e-9`;
- jede Row mit positivem Teacher-Regret ist unmöglich;
- `counterfactual_value_normalized_within_decision` hat Mittelwert null innerhalb `1e-9`;
- `value_gap_to_best` entspricht `raw_value - max(raw_values)` innerhalb `1e-9`;
- `teacher_rank` und `counterfactual_rank` sind mit Werten und Ties konsistent;
- Bool-, Rank- und Gap-Felder besitzen die erwarteten Typen und endliche Werte;
- `teacher_config.trainable_label` ist innerhalb einer Decision konsistent.

Semantisch gleiche Decisions werden nur dann auf Labelwiderspruch verglichen, wenn Teacher-Version,
Teacher-Konfiguration, Feature-Extractor-Version und Config-Provenance übereinstimmen. Unterschiede
über bewusst verschiedene Teacher-Konfigurationen werden als Provenance-Vergleich berichtet, nicht
als falsches Label.

## 10. Feature-Gesundheit

Für jedes Feature und jeden Split werden Typ, Anzahl unterschiedlicher Werte, Missing-/Sentinel-
Rate und Verteilung erfasst.

### 10.1 Harte Fehler

- nicht endliche numerische Werte;
- Typwechsel, der nicht durch das Schema erlaubt ist;
- Feature-/Denylist-Verletzung;
- Modell erwartet ein nicht vorhandenes Feature;
- kategorische Encodings ohne `__unk__` oder mit ungültigen Codes.

### 10.2 Warnungen

- konstant in Train;
- fast konstant: häufigster Wert `>= 99.5 %`;
- Sentinel-/Missing-Anteil `>= 95 %`;
- paarweise numerische Spearman-Korrelation `|rho| >= 0.98`;
- Unseen-Category-Anteil in Validation oder Test `> 5 %`;
- numerischer Out-of-Train-Range-Anteil `> 5 %`;
- PSI `>= 0.25`;
- Jensen-Shannon-Divergenz `>= 0.10`.

Numerisches PSI verwendet bis zu 10 durch Train-Quantile definierte Bins; identische Quantilgrenzen
werden zusammengelegt. Kategorische Drift verwendet die Vereinigungsmenge der Kategorien. Für PSI
und Jensen-Shannon wird ausschließlich zur numerischen Stabilität ein dokumentiertes Epsilon
`1e-6` verwendet. Validation/Test beeinflussen weder Bins noch Kategoriegrundlage von Train.

Konstante Features sind keine automatische Löschanweisung. Das Audit dokumentiert sie und gleicht
sie, falls ein Modellmanifest vorliegt, gegen `dropped_constant_columns` ab.

## 11. Verteilung, Teams und Archetypen

Der Coverage-Block enthält mindestens:

- Games, Decisions und Rows pro Split;
- Kandidatenzahlverteilung;
- Action-Klassen über die vorhandene `action_class`-Logik;
- `game_mode` und Turn-Buckets `1-3`, `4-6`, `7+`;
- Format, Config- und Teacher-Version;
- Team-Hash, Team-ID und Archetyp, falls Katalogdaten vorliegen;
- trainierbare gegenüber nicht trainierbaren Labels;
- strict-unique, Tie-, Forced- und Multi-Candidate-Anteile.

Warnschwellen:

- Team-/Archetyp-/Action-Bucket mit weniger als 10 Games;
- Anteil eines Action- oder Archetyp-Buckets verschiebt sich zwischen Train und Test um mindestens
  15 Prozentpunkte;
- unbekannte Team-Hashes bei vorhandenem Katalog;
- Split ohne mindestens zwei Action-Klassen;
- Test-Bucket ohne entsprechende Train-Abdeckung.

Kleine Buckets werden nie ausgeblendet; sie werden als deskriptiv beziehungsweise unterpowert
markiert.

## 12. Drift und Out-of-Distribution

Train definiert ausschließlich die Referenzstatistiken. Validation, Test und optionale externe
Referenzdatensätze werden dagegen gemessen.

Pro Decision entsteht ein OOD-Score aus:

- Anteil ungesehener kategorischer Werte;
- Anteil numerischer Features außerhalb des Train-Min/Max-Bereichs;
- mittlerer robuster numerischer Distanz zum Train-Median;
- Anteil fehlender beziehungsweise Sentinel-Features.

Alle Komponenten werden auf `[0, 1]` gekappt und gleich gewichtet. `OOD` bedeutet standardmäßig
Score `>= 0.50`. Die Schwelle ist versioniert und konfigurierbar. Das Audit berichtet Score-
Quantile, OOD-Anteil und die häufigsten beitragenden Features.

Falls ein Modell vorliegt, werden Regret, Teacher-Topset-Accuracy und Fehlerquote getrennt für
In-Distribution und OOD berichtet. Ein Performanceabfall wird als Effektgröße dokumentiert; bei
weniger als 10 Decisions in einer Gruppe wird keine belastbare Vergleichsaussage formuliert.

## 13. Modell- und Manifestprüfung

Wenn Modell oder Manifest angegeben wird, müssen beide angegeben werden. Geprüft werden:

- Dataset-SHA-256 gegen `manifest.dataset_sha256`;
- Feature-Schema-Hash;
- Trainingsconfig-Hash-Form und vorhandene Configangaben;
- Modelltyp;
- Featureliste als Teilmenge der eingefrorenen Feature-Allowlist;
- keine Label-/Metadata-Denylist-Felder;
- exakte Feature-Reihenfolge zwischen Modell und Manifest;
- kategorische Featureliste und Encodings;
- `dropped_constant_columns` gegen Train-Statistik;
- Eval-Report-Pfad und Metrics-Summary vorhanden;
- deterministische Prediction bei identischer Matrix;
- Prediction-Anzahl gleich Kandidatenanzahl;
- ausschließlich endliche Scores.

Dataset-, Feature-Schema-, Denylist- oder Modellreihenfolge-Mismatch sind `FAIL`. Ein nicht mehr
existierender historischer Eval-Report-Pfad ist `WARN`, sofern dessen Hash nicht als verbindlich im
Manifest gespeichert wurde; ein gespeicherter, aber falscher Report-Hash wäre `FAIL`.

## 14. Modellmetriken und Kalibrierung

Ranking-Scores werden nicht als Wahrscheinlichkeiten missverstanden. Für jede Decision werden die
Scores über Softmax mit Temperatur `T` in eine Verteilung über Kandidaten umgewandelt.

### 14.1 Temperaturfit

- `T` wird ausschließlich auf Validation gefittet;
- Zielfunktion ist die negative Log-Likelihood des Teacher-Best-Sets;
- bei Teacher-Ties wird die Zielmasse gleichmäßig über alle Best-Rows verteilt;
- Suche deterministisch per Golden-Section über 80 Iterationen auf `log(T)` im Intervall `[-5, 5]`;
- kein Testwert beeinflusst `T` oder eine Schwelle.

### 14.2 Testmetriken

- Teacher-Topset-Accuracy
- Mean Regret der Modellwahl
- NDCG@1 und NDCG@2
- NLL
- multiclass Brier Score
- ECE mit 10 nach Decision-Anzahl möglichst gleich häufig besetzten Confidence-Bins; sortiert nach
  Confidence und bei Gleichstand nach `(game_id, decision_id)`
- Accuracy und Regret nach Confidence-Bin
- Modell-Topmargin gegen empirische Teacher-Trefferquote

`ECE > 0.10` erzeugt `WARN`. ECE bleibt auch bei kleinen Testsplits sichtbar; bei weniger als 100
Test-Decisions wird zusätzlich eine Small-N-Warnung ausgegeben. Kalibrierung ist diagnostisch und
ändert weder Modell noch Live-Scores.

## 15. Reports und Exitcodes

Ausgaben:

- `audit.json`
- `audit.md`
- `split-manifest.json`

Der JSON-Report enthält:

- Audit- und Reportschema-Version;
- Dataset-Pfad nur als informativen, normalisierten Namen und Dataset-SHA-256;
- vollständige Auditkonfiguration;
- Splitmanifest und Splitmanifest-Hash;
- Corpus-/Provenance-Zusammenfassung;
- alle Findings;
- alle Prüfermetriken;
- Modell-/Manifestblock, falls vorhanden;
- Kalibrierungsblock, falls vorhanden;
- Limitationen und Capability-Marker.

Markdown beginnt mit dem Auditstatus:

- `AUDIT PASS` — keine `FAIL`-Findings;
- `AUDIT FAIL` — mindestens ein `FAIL`-Finding.

Warnungen verändern den Status nicht zu `FAIL`, werden aber direkt nach der Zusammenfassung
aufgelistet. Exitcode `0` bei PASS, Exitcode `1` bei FAIL.

Ein unlesbarer oder fundamental unparsebarer Input erzeugt einen minimalen Fatal-Report mit
Datasetname, Auditversion, `FATAL_INPUT`-Finding und Exitcode `1`. Es wird kein scheinbar
vollständiger Metrikblock erfunden.

## 16. Determinismus und Skalierung

- alle Hashes verwenden kanonisches JSON und SHA-256;
- Findings, Beispiele, Features, Splits und Buckets werden explizit sortiert;
- keine Zeitstempel innerhalb deterministisch verglichener Inhalte;
- Wall-Clock-Laufzeit darf separat außerhalb des Identitätshashs erscheinen;
- Near-Duplicate-Vergleich ausschließlich innerhalb deterministischer Blocks;
- Beispielanzahl begrenzt, Gesamtmetriken vollständig;
- große Referenzdatensätze dürfen blockweise eingelesen werden, ohne die fachlichen Ergebnisse zu
  ändern;
- gleiche Inputs und gleiche Auditkonfiguration müssen byte-identische JSON-/Markdown-Inhalte
  erzeugen.

## 17. Fehlerbehandlung

Prüfer sammeln fachliche Findings und laufen nach Möglichkeit weiter, damit ein vollständiges Bild
entsteht. Folgende Fehler beenden nur den betroffenen Prüfer, nicht automatisch alle anderen:

- fehlender optionaler Teamkatalog;
- nicht ladbares optionales Modell bei weiterhin auditierbarem Dataset;
- nicht verfügbare Archetypdimension;
- zu kleine Kalibrierungsgruppe.

Der Orchestrator setzt den Gesamtstatus dennoch auf FAIL, wenn der betroffene Fehler die
Vertrauenskette bricht, beispielsweise Modell angefordert, aber nicht ladbar.

Fundamentale Parser-/Schemafehler dürfen keine nachgelagerten Feature-, Label- oder Modellmetriken
auf erfundenen Teilmengen erzeugen. Der Fatal-Report nennt klar, welche Prüfer `not_run` sind.

## 18. Teststrategie

Jeder Finding-Code erhält mindestens einen positiven und einen negativen synthetischen Test.

Pflichtfälle:

- valides Mini-Dataset;
- malformed Row und unbekannte Keys;
- doppelte Row, Decision und ID;
- Cross-Split-Game-/Decision-/Semantik-Leakage;
- Near-Duplicate knapp unter und über Schwelle;
- nicht zusammenhängende Kandidatenindizes;
- Teacher-Tie und mehrere äquivalente Heuristikauswahlen;
- positive Gaps, falsche Best-Gaps, inkonsistente Ränge und nicht-null Mittelwert;
- gleiche semantische Inputs mit widersprüchlichen Labels;
- konstante, fast konstante, hoch korrelierte und nicht endliche Features;
- Sentinel-, Unseen-Category-, PSI- und JS-Warnungen;
- vollständiger, teilweiser und widersprüchlicher Teamkatalog;
- Action-/Archetyp-Unterabdeckung;
- ID- und OOD-Gruppen;
- Dataset-/Schema-/Featureorder-/Encoding-Manifest-Mismatch;
- deterministische Modellprediction;
- Temperature-Fit ausschließlich auf Validation;
- Ties im Kalibrierungsziel;
- ECE, Brier und NLL ausschließlich auf Test;
- PASS-/FAIL-Exitcodes und Fatal-Report;
- byteidentische Reports bei permutierter Eingabereihenfolge;
- Import-Guard gegen `battle`, `client.gauntlet`, Teacher und Live-Reranker.

Ein Real-Dataset-Smoke lädt `phase3-slice2b25a`, führt alle datasetbezogenen Prüfer aus und prüft
nur Struktur und interne Metrikkonsistenz. Historische Counts werden nicht als Goldenwerte
festgeschrieben.

## 19. Abnahmekriterien

Die Implementierung gilt als fachlich vollständig, wenn:

1. beliebige schema-kompatible Dataset-Pfade ohne corpus-spezifische Konstanten auditierbar sind;
2. Splits gameweise, vollständig, disjunkt und reproduzierbar sind;
3. exakte und semantische Cross-Split-Duplikate zuverlässig blockieren;
4. Near-Duplicates deterministisch und blockweise gefunden werden;
5. alle Labelinvarianten Ties und äquivalente Heuristikauswahlen korrekt behandeln;
6. Feature-, Coverage-, Drift- und OOD-Metriken splitweise entstehen;
7. Modell und Manifest kryptografisch und semantisch geprüft werden;
8. Kalibrierung Validation und Test strikt trennt;
9. Reports bei identischen Inputs byteidentisch sind;
10. `FAIL` Exitcode 1 und ausschließlich `WARN`/`INFO` Exitcode 0 erzeugt;
11. der Referenz-Smoke ohne Battles, Training oder Held-out-Zugriff läuft;
12. kein Live-Pfad das Auditpaket importiert.

## 20. Nicht-Ziele

- keine automatische Änderung oder Bereinigung von Dataset-Rows;
- keine automatische Entfernung konstanter oder korrelierter Features;
- kein Training oder Retraining;
- keine Anpassung des produktiven Reranker-Modells;
- keine Live-Kalibrierung;
- kein GO/NO-GO anhand von Winrate oder allgemeiner Spielstärke;
- kein Held-out-Zugriff;
- keine Battle-Ausführung;
- keine Ersetzung des bestehenden Schemavertrags, Splithelpers, Feature-Denylists oder
  Modellmanifests.

## 21. Referenzanwendung `phase3-slice2b25a`

Die erste Anwendung soll vorhandene Erkenntnisse reproduzierbar einordnen:

- 7 derzeit konstante und gedroppte Features werden als Feature-Health-Befund sichtbar;
- die bestehende LOCO-/SCO-Ablation bleibt eine separate Feature-Nützlichkeitsanalyse;
- Teacher-Disagreement bleibt eine separate Regret-/Entscheidungsanalyse;
- der gameweise Seed-42-Split wird explizit manifestiert und gehasht;
- Team-/Archetypmetriken werden nur ausgegeben, soweit ein passender Katalog vorliegt;
- das Audit darf bestehende Offline-GO- oder Live-NO-GO-Berichte weder überschreiben noch als
  Strength-Beleg umdeuten.
