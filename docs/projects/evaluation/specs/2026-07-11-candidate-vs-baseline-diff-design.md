# Candidate-vs-Baseline-Differenzanalyse

**Status:** fachlich freigegeben am 2026-07-11

**Dokumenttyp:** Design-Specification

**Repository-Basis:** `c9bb86b`

**Arbeitsbranch:** `codex/analysis-specs`

## 1. Ziel

Zwei Botkonfigurationen sollen unter exakt denselben Evaluationsbedingungen nicht nur anhand ihrer
Winrate verglichen werden. Die Analyse soll zeigen:

- an welchen direkt vergleichbaren Entscheidungen die Versionen auseinanderlaufen,
- welche Art von Entscheidung sich unterscheidet,
- welche Abweichungen mit einem gedrehten Match-Ergebnis verbunden sind,
- in welchen Matchups Verbesserungen oder Regressionen auftreten,
- ob Entscheidungen und Resultate über identische Wiederholungsläufe stabil bleiben,
- und ob ein Candidate neue Fallback-, Timeout- oder Latenzprobleme einführt.

Die Analyse ist eine diagnostische Ergänzung des bestehenden gepaarten Strength-Gates. Sie ersetzt
weder McNemar noch die vorhandenen Safety-Gates und macht keine kausale Behauptung, die nur durch
eine spätere Counterfactual-/Regret-Analyse gestützt werden könnte.

## 2. Leitprinzipien

1. **Gleiche Situation vor gleichem Urteil.** Zwei Aktionen werden nur dann direkt verglichen, wenn
   beide Bots nachweislich denselben für sie sichtbaren Vorzustand erhalten haben.
2. **Erste Abweichung vor Folgeeffekten.** Nach einer unterschiedlichen Aktion können die Battles
   in unterschiedliche Zustände laufen. Spätere Entscheidungen werden dann nicht mehr als
   Entscheidungen in derselben Situation ausgegeben.
3. **Fail-closed statt stiller Datenbereinigung.** Fehlende Paare, Trace-Lücken, doppelte Zeilen und
   Provenance-Abweichungen brechen die vollständige Analyse ab.
4. **Beobachtung ist keine Kausalität.** Ein Win/Loss-Flip nach einer Entscheidungsabweichung ist
   zunächst eine Assoziation. Die Counterfactual-/Regret-Analyse ist für stärkere Kausalaussagen
   zuständig.
5. **Diagnostik ist kein Strength-Gate.** Die endgültige Strength-Aussage bleibt bei gepaarter
   Ergebnisstatistik und den bestehenden Sicherheitsbedingungen.
6. **Kein versteckter Informationsvorteil.** Zustandsfingerprints und Decision-Sidecars enthalten
   ausschließlich Informationen, die dem jeweiligen Bot zum Entscheidungszeitpunkt vorlagen.

## 3. Bestehende Bausteine

Die Umsetzung erweitert vorhandene Verträge und führt keine konkurrierende Evaluationspipeline ein:

- `showdown_bot.eval.pairing.pair_runs` bleibt die verbindliche Battle-Paarung. Es validiert
  Schedule-, Seed-, Panel- und Formatgleichheit, unterschiedliche `config_hash`-Werte, vollständige
  `battle_id`-Mengen und identische Seeds.
- `showdown_bot.eval.result_jsonl` bleibt die Quelle für Battle-Outcomes, Provenance,
  Safety-Metriken und `decision_latency_p95_ms`.
- `showdown_bot.battle.decision_trace.DecisionTrace` bleibt die Quelle für Kandidaten,
  Heuristik-Scores, Kandidatenränge, Gegnerantworten und die gewählte Aktion.
- Die vorhandene Reranker-Shadow-Telemetrie liefert bereits Modellwahl, Heuristikwahl,
  Modell-Scores, Fallback-Gründe, Feature-Hashes und Shadow-Latenz. Diese Felder werden
  weiterverwendet, soweit sie zum allgemeinen Vertrag passen.
- `showdown_bot.eval.identity` und die T4/T4c-Provenance bleiben für Run- und Logidentität
  maßgeblich.

## 4. Analysearchitektur

Die Analyse besteht aus zwei verbundenen Ebenen.

### 4.1 Gepaarte Battle-Ebene

Baseline und Candidate spielen dieselbe versionierte Schedule mit identischem Panel, Format,
Seed-Base und denselben Seed-Indizes. `pair_runs()` validiert und erzeugt die Battle-Paare. Aus den
Result-Zeilen werden Outcome-Kategorien, Safety-Signale und Matchup-Metadaten abgeleitet.

### 4.2 Gepaarte Entscheidungs-Ebene

Beide Runs erzeugen optional ein versioniertes Decision-Sidecar. Die Sidecars werden innerhalb
eines bereits validierten Battle-Paars über `(battle_id, decision_index, our_side)` verbunden.
Vor jedem Aktionsvergleich wird der kanonische Hash des sichtbaren Vorzustands geprüft.

- gleicher Hash, gleiche normalisierte Aktion: direkte Übereinstimmung; unterschiedliche interne
  Scores oder Ränge werden dabei separat als Scoring-Divergenz markiert;
- gleicher Hash, unterschiedliche Aktion: direkte Policy-Abweichung;
- unterschiedlicher Hash: Folgezustandsabweichung, kein direkter Aktionsvergleich;
- fehlender oder doppelter Schlüssel innerhalb eines einzelnen Sidecars oder vor der ersten
  Zustandsdivergenz: Integritätsfehler im vollständigen Modus. Nach einer bestätigten
  Zustandsdivergenz oder wenn eine direkte Aktionsdivergenz einen Run beendet, dürfen die beiden
  Battles unterschiedlich lange Entscheidungssuffixe besitzen; diese werden als nicht direkt
  vergleichbare Baseline- beziehungsweise Candidate-Suffixe gezählt.

Die erste direkte Policy-Abweichung eines Battles wird als Divergenzursprung gespeichert. Sobald
der nächste gepaarte Entscheidungspunkt unterschiedliche Vorzustände besitzt, werden weitere
Entscheidungen nur noch als nachgelagerte, nicht direkt vergleichbare Zustände gezählt.

## 5. Decision-Sidecar-Vertrag

Das Sidecar ist ein optionales, standardmäßig deaktiviertes JSONL-Artefakt, komprimierbar als
`decision-trace.jsonl.gz`. Aktivierung und Ausgabepfad müssen explizit erfolgen. Ist Capture
deaktiviert, bleiben Entscheidungen, Result-Zeilen und bisherige Runs unverändert.

Jede Zeile enthält mindestens:

### 5.1 Identität und Provenance

- `trace_schema_version`
- `battle_id`
- `seed_index`
- `decision_index`
- `turn_number`
- `our_side`
- `config_id`
- `config_hash`
- `schedule_hash`
- `format_id`
- `git_sha`

### 5.2 Vorzustand

- `observable_state_hash`
- `request_hash`
- `decision_phase`, beispielsweise Team Preview, regulärer Zug oder Forced Replacement
- optional eine versionierte, kanonische Zusammenfassung ausschließlich sichtbarer Felder für
  Debugging; niemals vollständige verborgene Serverwahrheit

Der `observable_state_hash` basiert auf einer kanonischen Serialisierung mit stabiler
Schlüsselreihenfolge. Er umfasst nur den State und Request, die dem Bot unmittelbar vor der
Entscheidung vorlagen. Outcome, zukünftige Logs, nicht enthüllte Items/Moves/Sets und andere
Oracle-Daten sind ausgeschlossen.

### 5.3 Entscheidung

- `actual_choose_string`
- `normalized_action`
- `action_signature`
- `chosen_candidate_id`, wenn verfügbar
- `chosen_candidate_index`, wenn verfügbar
- `chosen_rank`, wenn verfügbar
- relevante Kandidaten-Scores und Score-Abstände
- `fallback_stage` und `fallback_reason`
- `decision_latency_ms`, sofern auf Entscheidungsebene erfasst

`normalized_action` bildet die tatsächlich gesendete Aktion strukturiert ab. Die Struktur muss
Moves, Zielslots, Switch-Ziele, Protect, Tera, Pass und Forced-Replacement-Aktionen eindeutig
unterscheiden. Stringformatierung oder Slotreihenfolge darf keine falsche Abweichung erzeugen.

### 5.4 Datenschutz und Leakage-Schutz

Der Sidecar-Writer besitzt eine explizite Feld-Allowlist. Unbekannte Felder werden nicht
automatisch serialisiert. Ein Test muss belegen, dass outcome-tragende und verborgene Felder nicht
im Zustandsfingerprint oder in der optionalen Zustandszusammenfassung landen.

## 6. Divergenzklassifikation

Eine direkte Policy-Abweichung wird in genau eine primäre Klasse und beliebig viele sekundäre
Marker eingeordnet.

Primärklassen in verbindlicher Prioritätsreihenfolge:

- `FALLBACK`: mindestens eine Version entscheidet über eine andere Fallback-Stufe;
- `TERA`: Unterschied in Tera-Nutzung oder Tera-Slot;
- `SWITCH`: anderer Wechsel oder Wechsel statt Bleiben;
- `PROTECT`: Protect-Unterschied ohne vorrangige Switch-Klasse;
- `ATTACK_MOVE`: mindestens eine andere Attacke bei sonst gleicher Aktionsstruktur;
- `ATTACK_TARGET`: gleiche Attacke, aber anderes Ziel;
- `OTHER_ACTION`: legaler, validierter Unterschied außerhalb der bekannten Klassen.

Sekundäre Marker halten Mehrfachunterschiede fest, zum Beispiel `target_changed`,
`slot1_changed`, `slot2_changed`, `tera_changed`, `protect_changed` oder `switch_changed`. Die
Prioritätsreihenfolge der Primärklassen ist versioniert und wird im JSON-Report angegeben. Eine
andere Score- oder Rangfolge bei identischer normalisierter Aktion ist keine Policy-Abweichung,
sondern eine direkte Aktionsübereinstimmung mit dem sekundären Marker `score_rank_changed`.

## 7. Ergebnisverknüpfung

Jedes Battle-Paar erhält genau eine Outcome-Kategorie aus Sicht des Candidates:

- `BOTH_WIN`
- `BOTH_LOSS`
- `CANDIDATE_FLIP_TO_WIN`
- `CANDIDATE_REGRESSION_TO_LOSS`

Ties, Crashes, Timeouts und nicht normale Endgründe werden separat ausgewiesen und nicht still in
Win/Loss-Gruppen umgedeutet. Die vorhandenen Safety-Gates bestimmen weiterhin, ob ein Strength-
Report überhaupt zulässig ist.

Die Analyse verbindet Outcome-Kategorien mit der ersten direkten Policy-Abweichung. Formulierungen
im Report lauten beispielsweise „mit positiven Match-Flips verbunden“, nicht „hat den Sieg
verursacht“.

## 8. Metriken

### 8.1 Integrität und Coverage

- Battle-Paare insgesamt
- vollständige Decision-Sidecar-Paare
- direkt vergleichbare Entscheidungen
- direkte Übereinstimmungen
- direkte Policy-Abweichungen
- Folgezustandsabweichungen
- Legacy- oder Outcome-only-Paare
- Trace-, Schema- und Provenance-Fehler

### 8.2 Entscheidungsdifferenzen

- Abweichungsrate über direkt vergleichbare Entscheidungen
- erste Divergenz nach Turn und Entscheidungsphase
- Häufigkeit der Primärklassen und sekundären Marker
- Score-Rang und Score-Abstand der unterschiedlichen Optionen
- Candidate-only- und Baseline-only-Fallbacks

### 8.3 Outcomes und Stärke

- vollständige 2x2-Kontingenztafel
- Candidate-minus-Baseline-Winrate
- Zahl diskordanter Paare
- exakter zweiseitiger McNemar-/Binomial-p-Wert über diskordante Paare
- vorhandene positive-evidence- und Losing-cell-Regeln aus dem Strength-Report

Die Differenzanalyse rendert diese Werte, implementiert aber keinen konkurrierenden Strength-
Verdictbaum.

### 8.4 Matchups und Regressionen

Soweit die Schedule-Metadaten es erlauben, werden die Ergebnisse mindestens nach folgenden
Dimensionen gruppiert:

- Hero-Team und Hero-Archetyp
- Gegnerteam und Gegner-Archetyp
- Gegnerpolicy
- Lead-Kombination, abgeleitet ausschließlich aus den initialen öffentlichen Switch-Zeilen vor
  Turn 1; fehlen pro Seite zwei eindeutige Starts, wird der Wert als `unavailable` ausgewiesen
- Entscheidungsphase und Turn-Bucket
- Divergenzklasse

Pro Bucket werden Stichprobengröße, Winraten, Flip-Zahlen und Wilson-Intervalle angegeben. Buckets
mit weniger als 10 Battle-Paaren werden als deskriptiv beziehungsweise unterpowert markiert, nicht
ausgeblendet. Diese Grenze gehört zur Analyseversion und darf nur über eine neue Version geändert
werden.

Regressionen umfassen mindestens:

- `CANDIDATE_REGRESSION_TO_LOSS`
- eine Verschlechterung in einem zuvor positiven Matchup-Cell
- zusätzliche Fallbacks, Timeouts, Crashes oder ungültige Entscheidungen
- Überschreitung des vorhandenen Latenzbudgets
- Verbesserung nur gegen schwache Policies bei flacher oder negativer Entwicklung gegen stärkere
  Policies

## 9. Stabilität über Wiederholungen

Es gibt zwei getrennte Stabilitätsbegriffe:

1. **Identische Wiederholung:** gleiche Konfiguration, gleiche Provenance und gleiche Seeds müssen
   identische normalisierte Decision-Sidecars und Battle-Logs erzeugen. Die Identitätsnormalisierung
   schließt ausschließlich ausdrücklich volatile Telemetrie wie Wall-Clock-Latenzen und lokale
   Ausgabepfade aus; Entscheidungen, Zustands-Hashes, Kandidaten, Scores, Fallbacks und Reihenfolgen
   bleiben enthalten. Jede andere Abweichung ist ein Reproduzierbarkeitsfehler, keine statistische
   Streuung.
2. **Panel-/Seed-Stabilität:** über unterschiedliche Seeds werden Effektgröße, Flip-Richtung und
   Matchup-Buckets mit Stichprobengröße und Intervallen ausgewiesen. Ein Vorteil, der nur in einem
   kleinen Cell auftritt, gilt nicht als allgemein stabil.

Die vollständige Reproduzierbarkeits-Stresstest-Spec wird später zusätzliche Neustart-, Langspiel-
und Umgebungsdimensionen definieren. Diese Spec verlangt nur die für einen ehrlichen
Candidate-vs-Baseline-Vergleich notwendige Identität.

## 10. Ausgaben

### 10.1 Maschinenlesbarer Report

Ein deterministischer JSON-Report enthält:

- Schema- und Analyseversion
- Provenance beider Runs
- Integritäts- und Coverage-Block
- Battle-Paar-Datensätze mit Outcome-Kategorie
- erste direkte Divergenz pro Battle
- Aggregationen nach Divergenzklasse und Matchup
- Stability- und Regressionsergebnisse
- explizite Limitationen und Capability-Modus

Schlüssel und Listen besitzen eine definierte Sortierung. Nicht endliche Zahlen sind verboten.

### 10.2 Markdown-Report

Der Markdown-Report ist verdict-first, ohne selbst ein neues Strength-Verdict zu erfinden. Er
enthält:

1. Inputs und Provenance
2. Integrity/Coverage
3. bestehendes gepaartes Strength-Ergebnis
4. Outcome-Kategorien
5. erste Divergenzen
6. Divergenzklassen
7. Matchup- und Stabilitäts-Buckets
8. neue Regressionen
9. priorisierte positive und negative Flip-Assoziationen
10. Grenzen der Aussage

## 11. Modi und Rückwärtskompatibilität

- **Full mode:** Result-JSONLs und vollständige Decision-Sidecars sind Pflicht. Jede Lücke bricht
  ab.
- **Outcome-only mode:** muss explizit angefordert werden und arbeitet ausschließlich mit
  vorhandenen Result-Zeilen. Der Report kennzeichnet, dass keine Entscheidungsaussage möglich ist.
- **Capture disabled:** bisheriges Bot- und Eval-Verhalten bleibt unverändert.
- Legacy-Sidecars mit unbekannter Version werden nicht geraten oder automatisch migriert.

## 12. Fehlerbehandlung

Die vollständige Analyse bricht mindestens bei folgenden Bedingungen ab:

- unterschiedliche Schedule-, Panel-, Format- oder Seed-Provenance;
- identische `config_hash`-Werte beider Runs;
- fehlende, zusätzliche oder doppelte Battle-Paare;
- Lücken oder doppelte Decision-Schlüssel innerhalb eines Runs sowie fehlende Cross-Run-Schlüssel
  vor der ersten Zustandsdivergenz; unterschiedlich lange Suffixe nach bestätigter
  Zustandsdivergenz oder nach einem durch direkte Aktionsdivergenz beendeten Run sind zulässig und
  werden sichtbar berichtet;
- nicht monotone `decision_index`-Folgen innerhalb eines Battles;
- unbekannte Trace-Schema-Version;
- Sidecar-Provenance, die nicht zur Result-Zeile passt;
- ungültige normalisierte Aktionen;
- nicht endliche Scores, Abstände oder Latenzen;
- Ergebnis- oder Logintegritätsfehler aus dem vorhandenen T4c-Pfad.

Ein unterschiedlicher `observable_state_hash` ist kein Analyseabbruch. Er beendet lediglich den
direkten Entscheidungsvergleich für diesen Battle-Zweig und wird als Folgezustandsabweichung
ausgewiesen.

## 13. Teststrategie

Die Umsetzung wird testgetrieben und überwiegend fixture-basiert geplant. Erforderlich sind:

- reihenfolgeunabhängiger kanonischer Zustands- und Request-Hash;
- Leakage-Test gegen Outcome- und Hidden-Truth-Felder;
- gleiche Zustände mit gleichen Aktionen;
- gleiche Zustände mit unterschiedlichen Moves, Zielen, Switches, Protects und Tera;
- Forced-Replacement und Team-Preview als eigene Entscheidungsphasen;
- korrekte erste Divergenz und anschließende Folgezustandsmarkierung;
- keine direkte Policy-Klassifikation nach unterschiedlichem Vorzustand;
- alle Outcome-Kategorien einschließlich Tie/Crash/Timeout-Behandlung;
- fehlende, doppelte und falsch provenancierte Trace-Zeilen;
- unbekannte Schema-Version und nicht endliche Zahlen;
- Full mode gegenüber explizitem Outcome-only mode;
- deterministische JSON- und Markdown-Ausgabe;
- Regressionstest gegen das vorhandene `pair_runs()`-Verhalten;
- kleine Offline-Integration aus Result- und Sidecar-Fixtures ohne lokale Battles;
- Capture-off-Golden-Test für unverändertes bisheriges Verhalten.

## 14. Abnahmekriterien

Die Umsetzung gilt als fachlich vollständig, wenn:

1. zwei pairbare Runs mit vollständigen Sidecars deterministisch analysiert werden;
2. direkte Entscheidungsabweichungen ausschließlich bei identischen sichtbaren Vorzuständen
   entstehen;
3. der erste Divergenzursprung und spätere Folgezustände sauber getrennt sind;
4. alle definierten Aktionsklassen fixture-basiert nachgewiesen sind;
5. positive und negative Outcome-Flips getrennt nach Matchup und Divergenzklasse erscheinen;
6. Wiederholungsidentität sowie Seed-/Panel-Stabilität getrennt berichtet werden;
7. Fallback-, Safety- und Latenzregressionen sichtbar sind;
8. JSON und Markdown deterministisch und ohne nicht endliche Werte entstehen;
9. Full mode bei unvollständigen Daten fail-closed arbeitet;
10. kein Held-out-Budget verbraucht und keine neue Strength-Entscheidungslogik eingeführt wird.

## 15. Nicht-Ziele

- keine automatische Freigabe oder Ablehnung eines Candidates;
- keine Änderung des McNemar-/Strength-Gates;
- keine Gegenfaktualsimulation alternativer Zukunftsverläufe;
- keine Attribution „diese einzelne Aktion verursachte den Sieg“;
- kein Held-out-Zugriff ohne separate Nutzerfreigabe;
- keine Veränderung des Live-Verhaltens bei deaktiviertem Capture;
- keine Ablösung der vorhandenen Result-, Pairing-, Identity- oder DecisionTrace-Verträge.

## 16. Abgrenzung zu den folgenden Analyse-Specs

- **Datensatz-/Reranker-Audit:** prüft Datenqualität, Leakage, Duplikate, Verteilung und
  Kalibrierung; es bewertet nicht primär gepaarte Live-Battles.
- **Opponent Modeling:** trennt Entscheidungsfehler von falschen Annahmen über verborgene
  Gegnerinformationen.
- **Team-/Matchup-Generalisation:** baut die hier begonnenen Matchup-Buckets zu einer vollständigen
  Generalisationsmatrix aus.
- **Counterfactual-/Regret-Analyse:** simuliert Alternativen und liefert die stärkere kausale
  Evidenz, die diese Spec bewusst nicht behauptet.
- **Reproduzierbarkeits-Stresstest:** erweitert Identität um Neustarts, lange Matches,
  Umgebungswechsel und First-Divergence-Diagnostik.
- **Performance-/Zeitbudgetanalyse:** zerlegt Latenz und Search-Budget in Komponenten statt nur
  Regressionen auf Battle-Ebene zu melden.
