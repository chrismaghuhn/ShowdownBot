# Deep-Research-Auswertung für ShowdownBot

**Stand der Prüfung:** 10. Juli 2026  
**Gegenstand:** Pokémon Showdown, VGC/Doubles, Reproduzierbarkeit, Search, RL, LLM-Bots, Datensätze und Evaluationsinfrastruktur  
**Methode:** Jede im Ressourcenpaket genannte Quelle wurde gegen eine Primärquelle geprüft: offizielles Repository, offizielle Dokumentation, Paper, Projektseite, Dataset Card oder ursprünglicher Community-Thread. Externe Projekte wurden nicht lokal ausgeführt und ihre Selbstaussagen daher als solche gekennzeichnet.

## Kurzfazit

Der wichtigste Befund ist nicht, dass ShowdownBot seine Architektur wechseln sollte. Im Gegenteil: Der aktuelle Kern — eigener Client, gepinnter Showdown-Commit, versionierter Seed-Patch, deterministische Entscheidungspfade, byteweiser Logvergleich, Provenance-Manifeste, Held-out-Ledger und ein Heuristik-Sicherheitsboden — liegt für reproduzierbare VGC-Forschung bereits ungewöhnlich weit vorn.

Die externen Quellen zeigen vier klare nächste Hebel:

1. **Die Reproduzierbarkeit jetzt als unveränderliche Evaluationsbasis behandeln.** Die lokalen 51/51- und 34/34-Doppelruns sowie die 10/10-Reproduktion auf Kaggle sind starke Evidenz. Die verbleibende Provenance-Lücke sind exakte Python-/Node-/Paket-/Plattformversionen im Run-Manifest oder ein gepinntes Container-Image.
2. **Generalisierung über Teams wird zum Hauptproblem.** VGC-Bench zeigt, dass gute Single-Team-Policies beim Skalieren auf viele Teams deutlich abbauen und auch starke Policies ausnutzbar bleiben. Das passt exakt zu eurem geplanten panel-diversen Datensatz und spricht gegen weitere Optimierung auf einem engen Mirror- oder Fixed-Team-Setup.
3. **Belief Tracking ist wahrscheinlich der nächste strategische Hebel nach dem Reranker-Gate.** Foul Play gewinnt nicht nur durch Search, sondern durch laufende Eingrenzung unbekannter Sets über Schaden, Speed-Reihenfolge, Items und Usage-Priors. Diese Prinzipien sind auf VGC übertragbar, seine Singles-Engine dagegen nicht.
4. **Human-Replay-Daten sind interessant, aber nicht direkt trainingsfertig.** VGC-Bench stellt inzwischen große Open-Team-Sheet-Datensätze bereit. Öffentliche Replays zeigen jedoch die Zuschauerperspektive, lassen private Entscheidungen teilweise aus und können Format- und Zeitdrift enthalten. Sie sollten zuerst für einen isolierten Ingestion-/Rekonstruktions-Prototyp genutzt werden, nicht sofort den bestehenden Rollout-Teacher ersetzen.

**Empfohlene Reihenfolge:** vollständiges Environment-Pinning → 2b-2.5a-Datensatz und Retrain abschließen → gepaarter Candidate-vs-Baseline-Gate → größeres Dev-Generalization-Panel → VGC-Bench-OTS-Prototyp → probabilistisches Belief Tracking → erst danach breitere World-Sampling/Search-Arbeit.

## 1. Abgleich mit dem aktuellen Projektstand

Aus den vorhandenen Projektartefakten ergibt sich folgender belastbarer Stand:

- Die lokale Evaluationsstrecke reproduziert zwei unabhängige 51er-Runs bytegleich; der Held-out-Meilenstein dokumentiert 34/34 in zwei Runs. Ein Kaggle-Lauf reproduziert zusätzlich 10/10 Kämpfe samt normalisierten Room-Logs auf fremder Hardware.
- Der Baseline-/Gate-Unterbau ist fertig: feste Schedules und Panels, per-Battle-Seeds, keine Retries, Run-Manifeste, Safety Gates, Wilson-Intervalle, gepaarter McNemar, positive-evidence-only, ein unveränderliches Baseline-Manifest und ein append-only Held-out-Ledger.
- Der LightGBM-LambdaRank-Reranker ist offline vielversprechend, aber noch kein Strength-Claim: Der ursprüngliche Datensatz umfasst 100 Spiele, 951 Entscheidungen und 4.658 Kandidatenzeilen. Der ATTACK-strict-Test enthält nur 63 Entscheidungen; 28 Features waren konstant oder unbefüllt. Das Modell bleibt deshalb richtigerweise offline beziehungsweise im Shadow-Pfad.
- 2b-2.5a ist sinnvoll angesetzt: 300 panel-diverse Spiele mit vier Hero-Teams und drei Dev-Gegnerteams sollen die Mirror-Artefakte beseitigen. Im Repository liegt derzeit noch kein fertiges `phase3-slice2b25a`-Manifest oder Retrain-Report; die Arbeit ist also noch nicht abgeschlossen.
- Die Northstar-Invarianten sind mit den Research-Befunden kompatibel: Legalität und Heuristik bleiben Sicherheitsboden, Memory liefert nur Priors, Search muss anytime/timeout-safe sein und jede neue Schicht braucht eine Ablation. Das explizite LLM-Verbot ist eine bewusste Projektentscheidung und wird in den Empfehlungen respektiert.

### Ein wichtiger Reproducibility-Nachtrag

Der aktuelle Run-Manifest-Code erfasst unter anderem `git_sha`, Dirty-Status, Schedule-/Panel-/Config-Hash, `PYTHONHASHSEED`, Showdown-Commit und Patch-Hash. `pyproject.toml` verwendet jedoch überwiegend Mindestversionen wie `websockets>=12.0`, `pydantic>=2.0` und `lightgbm>=4.0`; das Run-Manifest erfasst keine exakte Python-, Node-, Betriebssystem- oder Dependency-Version.

Das entwertet die bewiesene Byte-Reproduktion nicht. Es bedeutet nur: **Der getestete Zustand ist reproduzierbar, aber das Manifest beschreibt die gesamte Laufzeitumgebung noch nicht vollständig genug, um zukünftige Drift sicher zu diagnostizieren.** Metagrok, Metamon und VGC-Bench bestätigen unabhängig voneinander, dass neben dem Seed auch die komplette Softwareumgebung gepinnt werden sollte.

## 2. Quellenprüfung im Detail

### 2.1 Pokémon Showdown und Client-/Simulator-Grundlagen

#### [Pokémon Showdown Hauptrepository](https://github.com/smogon/pokemon-showdown)

**Bestätigt:** Showdown ist Website, JavaScript-Bibliothek, CLI-Werkzeugkasten, Simulationsserver und Source of Truth für Formate und Mechaniken. Es unterstützt Singles, Doubles und Triples über Generation 1 bis 9. Das Repository verlinkt ausdrücklich Protokoll-, Simulator-, Team- und Architektur-Dokumentation.

**Für ShowdownBot:** Weiterhin die richtige Referenz. Der gepinnte Commit plus versionierter Patch ist besser als eine unversionierte Abhängigkeit auf `master`. Keine Engine aus dem Ressourcenpaket rechtfertigt derzeit einen Wechsel für Gen-9-VGC.

#### [PROTOCOL.md](https://github.com/smogon/pokemon-showdown/blob/master/PROTOCOL.md)

**Bestätigt:** Der Server verwendet SockJS als Kompatibilitätsschicht über WebSocket; Clients können direkt per WebSocket verbinden. Dokumentiert werden Room-Framing, Client-/Server-Nachrichten und Login-Grundlagen.

**Wichtige Ergänzung:** Für einen Battle-Bot reicht `PROTOCOL.md` allein nicht. Die eigentliche Battle-Semantik, `|request|`-JSON, Doubles-Slotorientierung und alle Battle-Events stehen im [SIM-PROTOCOL](https://github.com/smogon/pokemon-showdown/blob/master/sim/SIM-PROTOCOL.md). Dieses Dokument fehlt im Ressourcenpaket, ist für euren Parser aber mindestens ebenso wichtig.

**Für ShowdownBot:** Keine Migration nötig. Sinnvoll wäre langfristig eine Coverage-Matrix „SIM-PROTOCOL-Ereignis → Parser-/State-Test“, besonders für seltene Events wie `replace`, `detailschange`, Itemtransfer, Redirects und erzwungene Wechsel.

#### [Showdown RNG-Dokumentation](https://pokemonshowdown.com/pages/rng)

**Bestätigt:** Gespeicherte Replays können Inputlogs mit Seeds enthalten. Bei Random Battles kann der Inputlog aus dem Replay bezogen werden. Bei Nicht-Random-Teams werden Seeds aus Datenschutzgründen nicht öffentlich gezeigt; dafür sind Zustimmung des Gegners und `/exportinputlog` nötig.

**Für ShowdownBot:** Euer Scope ist korrekt formuliert: lokale, kontrollierte Bot-vs-Bot-Evaluation — nicht beliebige Ladder-Replays. Der lokale Seed-Patch widerspricht der offiziellen Doku nicht, sondern macht den bereits vorhandenen Showdown-Seedpfad für einen privaten Evaluationsserver explizit steuerbar und auditierbar.

#### [Showdown `sim/README.md`](https://github.com/smogon/pokemon-showdown/blob/master/sim/README.md)

**Bestätigt:** Showdown warnt ausdrücklich, dass undokumentierte Node-APIs instabil sind, keinem SemVer-Vertrag folgen und bei Nutzung auf eine exakte Showdown-Version gepinnt werden sollten.

**Für ShowdownBot:** Das ist die stärkste externe Begründung für euren Commit-/Patch-Hash-Ansatz. Diese Quelle sollte später in README, Technical Report oder Paper direkt neben der Reproducibility-Behauptung stehen.

#### [poke-env Repository](https://github.com/hsahovic/poke-env) und [Dokumentation](https://poke-env.readthedocs.io/en/stable/)

**Bestätigt:** poke-env bietet Python-Abstraktionen für Player, Battle, Pokémon und Moves, Self-Play, Gymnasium-Interfaces sowie einen eigenen `DoublesEnv`. Für Training und Entwicklung wird ein lokaler Showdown-Server mit `--no-security` empfohlen.

**Für ShowdownBot:** Sehr guter API- und Testdesign-Vergleich, aber kein Grund, den eigenen Client auszutauschen. Euer Client ist bereits eng mit reproduzierbaren Runs, DecisionTrace, Export und Safety-Fallbacks verzahnt. Eine Migration würde viel validierten Code riskieren, ohne den zentralen strategischen Engpass zu lösen.

### 2.2 VGC-Bench und moderne VGC-Evaluation

#### [VGC-Bench Paper](https://arxiv.org/abs/2506.10326) und [Repository](https://github.com/cameronangliss/VGC-Bench)

**Bestätigt:** VGC-Bench ist die wichtigste direkte Quelle für euren Use Case. Es baut auf poke-env auf und umfasst heuristische Baselines, LLM-Spieler, Behavior Cloning, RL sowie populationsbasierte Verfahren wie Self-Play, Fictitious Play, Double Oracle und Policy Exploitation. Das Repository pinnt Showdown als Submodule und fordert ausdrücklich die gepinnte Version.

Die zentrale Aussage des Papers ist robust: Im engen Single-Team-Setting können Agents sehr stark werden, aber die Leistung sinkt beim Training über mehr Teams deutlich. Der aktuelle Repository-Readout vergleicht 1-, 4-, 16- und 64-Team-Settings und testet Generalisierung zusätzlich auf 72 ungesehenen Teams. Das Paper zeigt außerdem, dass trainierte Policies durch einen nachtrainierten Exploiter nahezu vollständig ausgenutzt werden konnten. Eine hohe Cross-Play-Elo ist daher nicht gleich Robustheit.

**Für ShowdownBot:**

- Eure Panel-/Schedule-Architektur geht in die richtige Richtung, ist aber mit drei Dev- und zwei Held-out-Teams noch klein.
- Ein zukünftiges Panel v2 sollte Archetypen, Matchups und Team-Perspektiven systematisch abdecken, ohne das vorhandene Held-out-Budget rückwirkend zu verwässern.
- Neben Winrate sollten Cross-Play-Matrix, schlechteste Zelle, Varianz über Teams und ein Exploiter-/Best-Response-Test betrachtet werden.
- VGC-Bench ist als Referenz für Evaluationsdesign wertvoller als als Drop-in-Codebasis.

#### [VGC-Bench Battle-Log-Datensatz](https://huggingface.co/datasets/cameronangliss/vgc-battle-logs)

**Aktueller Stand:** Der Datensatz wurde seit dem ursprünglichen Ressourcenpaket weiterentwickelt. Die aktive Dataset Card enthält rund **88.905** Open-Team-Sheet-Logs für vier Champions-VGC-Formate (Reg M-A/M-B, jeweils inklusive BO3), etwa 177.810 Spielerperspektiven und rund 1,47 Millionen Transitions. Ältere Scarlet/Violet-Regulationsdaten wurden in [`vgc-battle-logs-sv`](https://huggingface.co/datasets/cameronangliss/vgc-battle-logs-sv) archiviert; die frühere Sammlung umfasste knapp 948.000 Logs über 20 Formate.

**Für ShowdownBot:** Das ist der beste externe Kandidat für einen isolierten Human-Data-Prototyp. Wegen eures Ziel-Formats `gen9vgc2025regi` sollte zuerst nur die passende archivierte Regulation betrachtet werden. Champions-Daten dürfen nicht ohne getrennte `format_id`- und Mechanikbehandlung mit Scarlet/Violet-Daten vermischt werden.

#### [PokéAgent Challenge – Battling](https://pokeagentchallenge.com/battling.html)

**Bestätigt:** Die aktuelle Challenge betreibt einen AI-fokussierten Showdown-Server, um Bots direkt gegeneinander und gegen Organizer-Baselines zu testen. Unterstützt werden Gen1OU bis Gen4OU, Gen9OU und Gen9 VGC Regulation I. Die öffentlich hervorgehobenen Leaderboards konzentrieren sich derzeit jedoch auf Gen1OU und Gen9OU. Der Server hat einen Standardtimer mit maximal acht Sekunden pro Turn und einen Long-Timer für LLMs.

**Für ShowdownBot:** Der Server ist eine gute externe Validitätsprüfung, aber momentan kein standardisiertes VGC-Leaderboard auf dem Niveau eures internen gepaarten Gates. Eure dokumentierte p95-Latenz liegt deutlich innerhalb des Standardtimers. Vor einer Einreichung sollten Format-ID, Team-Upload, Auth und Timerverhalten in einem separaten Adaptertest geprüft werden.

#### [The PokéAgent Challenge Paper](https://arxiv.org/abs/2603.15563)

**Bestätigt:** Das Paper positioniert Pokémon als Benchmark für Partial Observability, spieltheoretisches Denken und Long-Horizon Planning. Der Battling Track nennt mehr als 20 Millionen Trajektorien sowie heuristische, RL- und LLM-Baselines.

**Für ShowdownBot:** Stark für die wissenschaftliche Motivation und für eine spätere Projektbeschreibung. Es ist keine Quelle, die unmittelbar einen Architekturwechsel erzwingt.

### 2.3 Metamon und Offline RL

#### [Metamon Repository](https://github.com/UT-Austin-RPL/metamon), [Paper](https://arxiv.org/abs/2504.04395) und [Projektseite](https://metamon.tech/)

**Bestätigt:** Metamon bietet laut aktuellem Repository mehr als 5 Millionen rekonstruierte Human-Trajektorien, mehr als 20 Millionen Self-Play-Trajektorien, standardisierte Teamsets und über 40 Baseline-Policies. Das Paper trainiert Sequence Models mit Imitation Learning und Offline RL und evaluiert vor allem ältere Singles-Generationen. Das aktuelle Repository hat Gen9OU ergänzt, aber kein VGC.

Metamon klont Showdown als Submodule und warnt, dass Showdown laufend aktualisiert wird; die mitgelieferte Version wird als unterstützte Serverversion behandelt. Das bestätigt euren Pinning-Ansatz. Besonders wichtig ist Metamons Rekonstruktion der **Spielerperspektive** aus öffentlichen Zuschauerlogs. Unbeobachtete Aktionen werden maskiert oder modellbasiert aufgefüllt — genau die Art Problem, die bei naiver Replay-Nutzung sonst Label-Fehler erzeugt.

**Für ShowdownBot:**

- Methodisch sehr wertvoll für Replay-Rekonstruktion, Observation-/Action-Masking und getrennte Human-/Self-Play-Datenpfade.
- Die Modelle und Resultate sind wegen Singles, langer Horizonte und anderer Action Spaces nicht direkt übertragbar.
- Die Idee mehrerer diskontierter Value-Horizonte ist langfristig interessant, aber erst nach dem aktuellen Reranker-Gate.

#### [Metamon Parsed Replays](https://huggingface.co/datasets/jakegrigsby/metamon-parsed-replays)

**Bestätigt:** Die veröffentlichte Sammlung enthält Gen1–4 sowie Gen9OU, ist groß und als RL-Trajektoriendatensatz strukturiert. Die Dataset Card weist **CC BY-NC 4.0** aus.

**Für ShowdownBot:** Kein VGC-Trainingsdatensatz. Nützlich zum Studium von Schema, Missing-Action-Flags, Legal-Action-Repräsentation und Rekonstruktions-Checks. Eine Vermischung mit eurem VGC-Datensatz wäre fachlich falsch.

### 2.4 Search-Bots und Opponent Modeling

#### [Foul Play Repository](https://github.com/pmariglia/foul-play), [technischer Artikel](https://pmariglia.github.io/posts/foul-play/) und [Smogon-Thread](https://www.smogon.com/forums/threads/re-introducing-foul-play-a-competitive-pokemon-battle-bot.3767378/)

**Bestätigt:** Foul Play ist ein starker Singles-Bot. Er verwendet root-parallelisierte Monte-Carlo-Tree-Search, eine handgebaute Evaluation und mehrere determinisierte mögliche Gegnerzustände. Der aktuelle Bot unterstützt Singles über mehrere Generationen; Dynamax und Z-Moves sind laut README nicht unterstützt. Der Autor betont selbst, dass die Engine Mechaniken nicht zu 100 Prozent korrekt abbildet und gezielt ausnutzbar ist.

Der wertvollste Teil ist das Hidden-Information-System:

- Schadensrollen grenzen Stats und Sets ein.
- Zugreihenfolge begrenzt gegnerische Speed-Werte.
- lange Wetterdauer verrät passende Items.
- Statusmoves schließen Assault Vest aus.
- Hazard-Schaden schließt Heavy-Duty Boots aus.
- Usage Stats, Forenteams und Replays liefern gewichtete Set-Priors.

Der Smogon-Thread bestätigt außerdem, dass starke Runs ressourcenintensiv sind und Peak-Elo allein als Qualitätsmaß täuschen kann.

**Für ShowdownBot:** Belief-Updates und gewichtete Set-Samples sind hochrelevant. Die Singles-Search-Engine ist nicht direkt übertragbar, weil VGC simultane Joint Actions, zwei aktive Slots, Redirection, Spread Moves, Protect-Interaktionen und erheblich größere Verzweigung hat.

#### [pmariglia/poke-engine](https://github.com/pmariglia/poke-engine)

**Bestätigt:** Rust-Engine mit reversiblen Instructions, Schaden, Expectiminimax, Iterative Deepening und MCTS. Das Repository nennt sie ausdrücklich Singles-only und „not a perfect engine“, deutlich weniger vollständig als Showdown.

**Für ShowdownBot:** Sehr gute Referenz für reversible State-Mutationen und Search-Engineering; keine geeignete Gen-9-VGC-Engine und keine neue Source of Truth.

#### [Metagrok](https://github.com/yuzeh/metagrok)

**Bestätigt:** Historisches Self-Play-RL-System. Es kann über WebSocket oder `pokemon-showdown simulate-battle` spielen, strukturiert Showdown-Nachrichten über einen headless JavaScript-Client und friert im Docker-Workflow Python-/Conda-Umgebung, Node-Version und Showdown-Commit ein. Doubles wird im Repository ausdrücklich als noch offene Erweiterung genannt.

**Für ShowdownBot:** Die Container-/Environment-Provenance ist direkt relevant; das RL-System selbst ist historisch und Singles-fokussiert.

#### [Meloetta](https://github.com/spktrm/meloetta)

**Bestätigt:** Python Battle Client und RL-Bibliothek, die den offiziellen JavaScript-Client headless über PyMiniRacer nutzt. Das Repository wurde am 13. Oktober 2023 archiviert und ist read-only.

**Für ShowdownBot:** Nur Architektur-Referenz. Keine neue Abhängigkeit auf ein archiviertes Projekt einführen.

#### [Nebraskinator/ps-ppo](https://github.com/Nebraskinator/ps-ppo)

**Bestätigt als Projekt-Selbstaussage:** Reiner Gen-9-Random-Battle-PPO-Ansatz mit entity-artiger Transformer-Repräsentation, Behavior-Cloning-Start und anschließendem verteiltem Self-Play. Das Repository nennt mehr als 250 Millionen Trainingszustände, über 85 Prozent gegen `SimpleHeuristicsPlayer` und mehr als 1900 Ladder-Elo ohne Search oder externen Damage Calc. Es bezeichnet sich selbst als methodisches Archiv, nicht als Consumer-App oder Tutorial.

**Für ShowdownBot:** Die Repräsentation „Field Token + Pokémon-/Move-Entitäten“ ist eine interessante spätere Modellhypothese. Die Leistungswerte sind nicht peer-reviewt, betreffen Random Singles und dürfen nicht als VGC-Benchmark übernommen werden.

### 2.5 LLM- und Hybrid-Bots

#### [PokéChamp Paper](https://arxiv.org/abs/2503.04094), [Repository](https://github.com/sethkarten/pokechamp) und [Projektseite](https://sites.google.com/view/pokechamp-llm)

**Bestätigt:** PokéChamp setzt LLMs als Module in einer Search-Pipeline ein: Action Sampling, Opponent Modeling und Value Estimation. Das Paper evaluiert **Gen9OU**, nicht VGC. Die berichteten 76 Prozent gegen den besten damaligen LLM-Bot, 84 Prozent gegen den stärksten Rule-based-Bot und das projizierte Elo von 1300–1500 gelten nur für dieses Setup.

Das aktuelle Repository enthält inzwischen `llm_vgc_player.py` und einen VGC-Runner. Das ist Implementierungsunterstützung, aber noch kein im Paper belegter VGC-Strength-Claim.

**Für ShowdownBot:** Die modulare Grundidee bestätigt euren Hybridansatz „Heuristik/Search als Sicherheits- und Kandidatenschicht, Learned Model als Zusatz“. Wegen der bindenden Projektinvariante `INV-5: No LLM anywhere` ist PokéChamp jedoch nur eine Forschungsreferenz, keine Implementierungsempfehlung.

#### [PokéChamp Dataset](https://huggingface.co/datasets/milkkarten/pokechamp)

**Bestätigt:** Rund 2,13 Millionen bereinigte Battle-Logs, 39 Formatklassen, Elo-Buckets und Daten aus 2024–2025. Das Paper spricht von mehr als drei Millionen gesammelten Rohspielen; die Dataset Card erklärt die Reduktion auf ungefähr zwei Millionen saubere Battles. VGC ist enthalten.

**Risiko:** Die Dataset Card weist aktuell kein klares Lizenzfeld aus. Außerdem sind es Zuschauerlogs und keine fertig rekonstruierten VGC-Spielertrajektorien.

**Für ShowdownBot:** Für Formatstatistik, Replay-Parser-Stresstests, Opponent-Action-Priors und Battle-Puzzles interessant. Für direktes Policy-Training deutlich schwächer als VGC-Bench-OTS-Daten.

#### [PokéLLMon Paper](https://arxiv.org/abs/2402.01118), [Repository](https://github.com/git-disl/PokeLLMon) und [Projektseite](https://poke-llm-on.github.io/)

**Bestätigt:** In-context Reinforcement Learning, Knowledge-Augmented Generation und Self-Consistency gegen „panic switching“. Die Projektseite dokumentiert zugleich Schwächen gegen Attrition und Deception. Die berichteten Resultate stammen aus Singles-Setups.

**Für ShowdownBot:** Gute Failure-Mode-Lektüre, aber kein Grund, ein LLM in den Live-Pfad zu bringen. Eure deterministischen, strukturierten Features und Safety-Gates adressieren viele dieser Probleme besser.

#### [PsyMew Repository](https://github.com/professor-conifer/PsyMew) und [Smogon-Thread](https://www.smogon.com/forums/threads/psymew-open-source-ai-battle-bot-project.3781351/)

**Bestätigt:** Aktueller Foul-Play-Fork mit Gemini-/Claude-Unterstützung, strukturiertem Battle-Prompt, Threat Scores und MCTS-Fallback. Im ursprünglichen Projektpost ist Doubles ausdrücklich „WIP“ beziehungsweise „needs serious work“. Es liegen keine belastbaren VGC-Benchmarkresultate vor.

**Für ShowdownBot:** Community-Signal und Beispiel dafür, Search-Ausgaben als Modellkontext zu nutzen. Wegen Doubles-Reifegrad, Latenz, Kosten, Nichtdeterminismus und `INV-5` nicht in euren aktiven Plan aufnehmen.

#### [Hugging Face – Build Your Own Pokémon Battle Agent](https://huggingface.co/learn/agents-course/en/bonus-unit3/building_your_pokemon_agent)

**Bestätigt:** Ein Lernmodul, das poke-env, Showdown, eine `LLMAgentBase`-Klasse und Tool Calls für Move/Switch kombiniert. Der bereitgestellte Template-Code ist ausdrücklich ein Blueprint und läuft nicht unverändert.

**Für ShowdownBot:** Nützlich für zukünftiges Contributor-Onboarding oder eine vereinfachte Demo, nicht für SOTA- oder Architekturentscheidungen.

### 2.6 Alternative Engines und modulare Showdown-Pakete

#### [pkmn/engine](https://github.com/pkmn/engine)

**Bestätigt:** Sehr performante Zig-Engine mit Showdown-Kompatibilitätsmodus und einem Claim von mehr als 1000-facher Geschwindigkeit in **unterstützten** Formaten. Das aktuelle Repository warnt vor Breaking Changes vor Version 0.1. Generation 1/2 ist der aktuelle Implementierungsfokus; moderne Generationen sind nicht kurzfristig verfügbar und teilweise von hochwertigen Decompilations abhängig.

**Für ShowdownBot:** Langfristige Beobachtung wert, heute keine Gen-9-VGC-Lösung. Der Performance-Claim darf nicht ohne die Einschränkung „unterstützte Formate“ zitiert werden.

#### [@pkmn/protocol](https://www.npmjs.com/package/@pkmn/protocol)

**Bestätigt:** Typed Parsing und strukturelle Verifikation für Showdowns `PROTOCOL` und `SIM-PROTOCOL` in TypeScript. Es prüft die Form von Protokollnachrichten, nicht die vollständige Domänenrichtigkeit.

**Für ShowdownBot:** Als Differential-Oracle oder Testvektorgenerator interessant. Ein direkter Einbau in den Python-Livepfad würde zusätzliche JS-Grenzen schaffen und ist aktuell nicht nötig.

#### [pkmn/ps](https://github.com/pkmn/ps)

**Bestätigt:** Modularisiert Showdown in Pakete wie `@pkmn/sim`, `@pkmn/dex`, `@pkmn/data`, `@pkmn/protocol`, `@pkmn/client` und `@pkmn/sets`.

**Für ShowdownBot:** Gute Referenz, falls einzelne Showdown-Komponenten in Node-Tools benötigt werden. Die vorhandene `@smogon/calc`-Bridge und das Python-System sollten nicht ohne konkreten Nutzen umgebaut werden.

#### [pokemon-showdown-rs](https://github.com/vjeux/pokemon-showdown-rs)

**Bestätigt:** Aktiver Rust-Port mit dem Ziel exakter Verhaltensparität. Der aktuelle Scope nennt Gen-9-Random-Battles; verbleibende Callbacks, bekannte Unterschiede und zusätzliche Testabdeckung sind ausdrücklich noch Arbeitspunkte.

**Für ShowdownBot:** Beobachten, nicht integrieren. „Ziel auf Behavioral Parity“ ist korrekt; „bereits vollständige Parity“ wäre derzeit eine Übertreibung. Kein belegter VGC-Scope.

#### [battler](https://github.com/jackson-nestelroad/battler)

**Bestätigt:** Allgemeine Rust-Battle-Engine mit mehreren Crates für Engine, AI, Damage Calc, Client, Daten, PRNG und Services. Das Projekt behauptet keine Showdown-Parität.

**Für ShowdownBot:** Interessante modulare Engine-Architektur, aber keine Source of Truth und kein aktueller Ersatz.

### 2.7 Datensätze, Replays und Community

#### [Kaggle Gen9 Randbats Dataset](https://www.kaggle.com/datasets/thephilliplin/pokemon-showdown-battles-gen9-randbats)

**Bestätigt:** Etwa 13.000 geparste Gen-9-Random-Battle-Replays mit JSON-Schema und MIT-Kennzeichnung auf der Dataset Card.

**Für ShowdownBot:** Nur für schnelle Parser- oder Datenpipeline-Prototypen. Kein VGC, kein OTS und kein sinnvoller Trainingsdatensatz für den aktuellen Bot.

#### [Offizielle Showdown Replay Search](https://replay.pokemonshowdown.com/)

**Bestätigt:** Suche nach Nutzern und Formaten sowie Zugriff auf öffentliche Replays. Die RNG-/Privacy-Grenzen gelten weiterhin. Öffentliche Replays sind nicht dasselbe wie vollständige, seedbare Inputlogs.

**Für ShowdownBot:** Gut für manuelle Fehleranalyse, Community-Replays und Datenquellen. Nicht als Reproducibility-Beweis für Nicht-Random-Ladderkämpfe verwenden.

#### Smogon AI-/Bot-Threads

Die Threads zu [Foul Play](https://www.smogon.com/forums/threads/re-introducing-foul-play-a-competitive-pokemon-battle-bot.3767378/) und [PsyMew](https://www.smogon.com/forums/threads/psymew-open-source-ai-battle-bot-project.3781351/) sind nützlich, weil dort reale Einschränkungen, Ressourcenbedarf, Replays und technische Einwände diskutiert werden. Sie sind Community-Evidenz, kein standardisierter Benchmark.

**Für ShowdownBot:** Der beste Ort für einen späteren technischen Projektpost, sobald eine klar abgegrenzte Behauptung, Reproduktionsanleitung und öffentliche Evidenz vorliegen.

#### PokéAgent Community

Die [aktuelle Battling-Seite](https://pokeagentchallenge.com/battling.html) verlinkt Server, Leaderboard, Replays und Discord. Sie verlangt für verifizierte Projekte einen technischen Bericht, Battle-Logs und einen identifizierbaren Agent auf dem Challenge-Server.

**Für ShowdownBot:** Sehr gute externe Forschungscommunity und mögliche Verifikationsschiene. Ein öffentlicher Bericht über deterministische VGC-Evaluation könnte dort auch dann wertvoll sein, wenn der VGC-Leaderboard-Fokus noch kleiner ist.

#### GitHub Topics

[pokemon-showdown](https://github.com/topics/pokemon-showdown), [pokemon-showdown-bot](https://github.com/topics/pokemon-showdown-bot) und [pokemon-ai](https://github.com/topics/pokemon-ai) sind brauchbar für Discovery. Aktualität, Qualität, Testabdeckung und Formatbezug schwanken stark.

**Für ShowdownBot:** Ideenquelle, nicht Quelle für SOTA-Claims. Neue Projekte erst nach Primärquellen-, Scope- und Reifeprüfung aufnehmen.

## 3. Korrekturen und wichtige Präzisierungen zum Ressourcenpaket

| Aussage aus dem Paket | Ergebnis der Prüfung |
|---|---|
| Showdown Protocol ist Kernmaterial | Richtig, aber für Battle-Bots muss `SIM-PROTOCOL.md` ausdrücklich ergänzt werden. |
| VGC-Bench ist die wichtigste VGC-Quelle | Bestätigt. Aktuelles Repo und Datensatz sind seitdem deutlich gewachsen. |
| PokeAgent unterstützt Gen9 VGC Reg I | Bestätigt. Die prominent bewerteten Leaderboards fokussieren derzeit trotzdem Gen1OU und Gen9OU. |
| Metamon bietet 5M+ Human- und 20M+ Self-Play-Trajektorien | Vom aktuellen Repository bestätigt; weiterhin primär Singles, nicht VGC. |
| Foul Play ist ein wichtiges Search-Projekt | Bestätigt. Der wertvollste Transfer ist Opponent Modeling; Engine und Search sind Singles-spezifisch. |
| Meloetta ist eine interessante Client-Alternative | Historisch richtig, aber seit Oktober 2023 archiviert. |
| ps-ppo ist ein aktuelles Gen9-Projekt | Bestätigt; Leistungsangaben sind Repository-Selbstaussagen ohne peer-reviewten VGC-Bezug. |
| PokéChamp-Dataset enthält 2M clean battles über 37+ Formate | Im Kern bestätigt; aktuelle Card zeigt ca. 2,13M Zeilen und 39 Formatklassen. Das Paper nennt mehr als 3M Rohspiele. |
| PokéChamp ist für hybride Systeme relevant | Bestätigt. Paperresultate gelten für Gen9OU; aktuelle VGC-Codeunterstützung ist kein VGC-Strength-Beweis. |
| PsyMew ist ein aktueller Open-Source-LLM-Bot | Bestätigt. Doubles ist ausdrücklich noch unfertig, Benchmarks fehlen. |
| pkmn/engine könnte schnelle Rollouts ermöglichen | Prinzipiell richtig, aber moderne Generationen sind derzeit nicht einsatzbereit; `main` ist vor 0.1 instabil. |
| pokemon-showdown-rs zielt auf Behavioral Parity | Bestätigt als Ziel. Aktuell Gen9 Random Battles und noch in aktiver Paritätsarbeit. |
| Battler ist eine Rust-Alternative | Bestätigt als allgemeine Engine; keine Showdown-Paritätsgarantie. |
| Kaggle-Randbats ist für ML-Prototypen brauchbar | Ja, aber nur ca. 13k Random-Singles-Replays und für VGC strategisch nachrangig. |

## 4. Was die Quellen konkret für ShowdownBot bedeuten

### 4.1 Reproducibility: Der Durchbruch ist strategisch wertvoll

Viele veröffentlichte Projekte pinnen lediglich einen Server-Commit oder verwenden einen lokalen Server. ShowdownBot geht weiter: abgeleitete per-Battle-Seeds, feste Reihenfolge, frischer Server je Run, keine Retries, Seedlog-Ausrichtung, deterministic client fallbacks, Bytevergleich, Provenance-Hashes und Held-out-Disziplin.

Das ist nicht nur Infrastruktur. Es ermöglicht erstmals faire, gepaarte Bot-Vergleiche, bei denen sich Candidate und Baseline denselben Zufallsverlauf teilen. Dadurch wird eure 2b-4-Entscheidung viel aussagekräftiger als gewöhnliche kleine Winrate-Vergleiche.

**Noch zu schließen:**

- exakte Python-Version,
- exakte Node-Version,
- `pip freeze` oder Hash eines Lockfiles,
- Hash des Calc-`package-lock.json`,
- OS/Architektur oder Container-Image-Digest,
- optional CPU-/Runtime-Metadaten für Performancevergleiche.

Diese Felder sollten Provenance ergänzen, aber nicht in `config_hash` einfließen, wenn sie keinen Policy-Unterschied darstellen. Für Reproduction Gates können sie als Environment-Compatibility-Block geprüft werden.

### 4.2 Evaluation: Vom kleinen Panel zur Generalisierungs-Matrix

VGC-Bench zeigt, dass Durchschnittsleistung über ein kleines bekanntes Teamset robuste Leistung vortäuschen kann. Für ShowdownBot sollte das nächste größere Dev-Panel daher nicht einfach „mehr Spiele mit denselben drei Teams“ sein, sondern eine kontrollierte Matrix:

- archetypische Hero-Teams: Balance, Rain, Sun, Trick Room, Tailwind/Hyper Offense;
- mehrere gegnerische Archetypen;
- mehrere Gegner-Policies mit klar unterschiedlichem Verhalten;
- beide sinnvollen Seiten-/Team-Perspektiven;
- feste, gepaarte Seeds;
- Auswertung pro Zelle und als Worst-Cell, nicht nur gepoolt;
- eine separate Exploiter-/Best-Response-Schiene, die nicht als normale Strength-Metrik vermischt wird.

Das vorhandene Held-out-Panel sollte nicht nachträglich vergrößert und erneut betrachtet werden. Besser ist ein neues, größeres **Dev-Generalization-Panel**, während das existierende Held-out-Gate unverändert bleibt oder später sauber versioniert wird.

### 4.3 Daten: Human-Replays ergänzen, nicht den Teacher ersetzen

Der aktuelle Rollout-Teacher liefert Kandidatenwerte innerhalb eures eigenen, reproduzierbaren State-/Action-Modells. Human-Replays liefern dagegen nur die tatsächlich gespielte Aktion und sind durch Skill, Teamwahl, Meta, unvollständige Information und Auswahlbias geprägt.

Ein sauberer Einsatz wäre:

1. VGC-Bench-OTS-Logs einer kompatiblen Regulation isoliert laden.
2. Beide Spielerperspektiven rekonstruieren und unbekannte beziehungsweise nicht beobachtbare Aktionen explizit maskieren.
3. Legal-Action-Rekonstruktion gegen Showdown prüfen.
4. Leakage-Tests für vollständige Sets, OTS-Information und erst später offenbarte Daten schreiben.
5. Human-Aktionen zunächst für Behavior-Cloning-Priors oder ein Opponent-Response-Modell nutzen.
6. Erst danach testen, ob Human-Priors dem Rollout-Teacher oder Reranker messbar helfen.

Die Self-Play-/Teacher-Daten und Human-Daten sollten getrennte Provenance, Schemas und Splits behalten.

### 4.4 Belief Tracking: Die stärkste übertragbare Foul-Play-Idee

Euer aktueller Belief-Layer nutzt kuratierte Sets und Reveal-Precedence. Der nächste Schritt sollte keine ungebremste MCTS sein, sondern **probabilistische Set-Eingrenzung**:

- initiale Set-/Spread-/Item-Priors pro Format;
- Speed-Unter- und Obergrenzen aus Zugreihenfolge, Tailwind, Trick Room und Priority;
- Likelihood-Update aus beobachteten Damage Rolls;
- harte Ausschlüsse aus Moves, Items, Abilities und Immunitäten;
- konsistente Behandlung von Tera und Open Team Sheets;
- normalisierte Hypothesengewichte;
- Entropie und Top-k-Masse als Features für Reranker und späteres World Sampling.

Wichtig: Beliefs dürfen gemäß INV-2 nie direkt einen Zug auswählen. Sie speisen nur Response Prediction, Features und World Sampling.

### 4.5 Search und Engines: Heute nicht umsteigen

Keine geprüfte alternative Engine erfüllt gleichzeitig:

- Gen-9-VGC-Abdeckung,
- Showdown-Parität,
- Doubles-Joint-Actions,
- Tera, Redirection und erzwungene Phasen,
- reproduzierbare Seeds,
- stabile API und belastbare Tests.

Darum ist eure aktuelle Richtung sinnvoll: internes, begrenztes Modell für taktische Rollouts und Showdown als Referenz-/Evaluation-Engine. Ein späterer Search-Ausbau sollte leichte Determinisierungen und World Sampling auf dem vorhandenen Belief-Layer verwenden, jederzeit abbrechbar sein und stets eine legale Heuristikaktion bereithalten.

### 4.6 LLMs: Forschungsreferenz, nicht Projektpfad

PokéChamp zeigt überzeugend, dass LLMs als Module besser funktionieren können als ein LLM als alleiniger Spieler. PokeLLMon und PsyMew dokumentieren zugleich Kosten, Latenz, Halluzinationen, Panic Switching und Deception-Probleme. Für einen deterministischen Live-Bot mit Subsekundenbudget sind diese Eigenschaften ungünstig.

Da ShowdownBots Northstar LLMs sogar offline verbietet, ist die saubere Entscheidung: Ergebnisse lesen, aber keine LLM-Abhängigkeit einführen. Die nützlichen Prinzipien — strukturierte Features, Opponent Modeling, Value-Horizonte, Tool-verifizierte Berechnungen — können ohne LLM umgesetzt werden.

## 5. Priorisierter Maßnahmenplan

### P0 — vor dem nächsten Strength-Claim

1. **Environment-Provenance vervollständigen.** Exakte Runtime-/Dependency-Versionen oder einen reproduzierbaren Container-Digest in jedes Run-Manifest aufnehmen.
2. **2b-2.5a abschließen.** Die vier Kaggle-Datagen-Schedules zusammenführen, Datensatz manifestieren, konstante Features prüfen, neu trainieren und den vorgesehenen Offline-Report erstellen.
3. **Keinen Live-Override aus Offline-Regret ableiten.** Erst ein gepaarter Candidate-vs-Baseline-Lauf auf dem bestehenden T4/T6-Unterbau darf 2b-4 entscheiden.
4. **Candidate-Run ebenfalls reproduzieren.** Vor Strength-Auswertung muss nicht nur die Baseline, sondern auch die Candidate-Konfiguration im Doppelrun byte-/row-identisch sein.

### P1 — größter erwarteter Spielstärke-Hebel

5. **Dev-Generalization-Panel v2 entwerfen.** Mehr Teams und Archetypen, aber getrennt vom bestehenden Held-out-Set.
6. **Belief-Layer probabilistisch erweitern.** Speed-Bounds, Damage-Likelihood, harte Item-/Move-/Ability-Ausschlüsse und gewichtete Hypothesen.
7. **VGC-Bench-OTS-Ingestion als isolierten Prototyp bauen.** Zuerst nur eine kompatible Regulation und eine kleine, auditierbare Stichprobe.
8. **Human-Daten für Opponent Response oder BC-Priors testen.** Nicht direkt mit dem Rollout-Teacher vermischen.

### P2 — nach bestandenem Reranker-Gate

9. **Leichtes World Sampling / determinized Search.** Top-k-Belief-Welten, feste Budgets, CVaR-/Worst-Case-Fusion und jederzeit gültige Fallback-Aktion.
10. **Exploiter-Test ergänzen.** Eine gezielt gegen den Candidate optimierte Response-Policy getrennt von normalen Strength-Metriken ausweisen.
11. **PokéAgent als externe Validierung nutzen.** Erst nach Format-/Timer-/Auth-Probe und mit klarer Abgrenzung zwischen internem gepaarten Gate und öffentlicher Ladder-Rating.
12. **Entity-/Transformer-Modell nur als spätere Ablation.** Erst wenn diverse Datenmengen und Baselines groß genug sind, um LightGBM fair zu schlagen.

## 6. Was jetzt ausdrücklich nicht empfohlen wird

- den eigenen Client durch poke-env oder Meloetta ersetzen;
- Gen-9-VGC auf `poke-engine`, `pkmn/engine`, `pokemon-showdown-rs` oder battler umstellen;
- Singles-Replays von Metamon oder Kaggle in den VGC-Policy-Datensatz mischen;
- PokéChamp-/PokeLLMon-/PsyMew-Werte als VGC-SOTA zitieren;
- ein LLM in Live-, Teacher- oder Analysepfade aufnehmen, solange INV-5 gilt;
- aus dem 100-Spiel-Datensatz oder 63 ATTACK-strict-Entscheidungen Spielstärke ableiten;
- das vorhandene Held-out-Set wiederholt für Feature- oder Hyperparameterentscheidungen öffnen;
- einen gepoolten Winrate-Wert über stark unterschiedliche Teams/Policies als Hauptmetrik berichten.

## 7. Datensatz-Entscheidungsmatrix

| Quelle | VGC direkt? | Spielerperspektive fertig? | Lizenz-/Nutzungsstatus | Empfehlung |
|---|---:|---:|---|---|
| VGC-Bench OTS Logs | Ja | Nein, Rekonstruktion nötig | Dataset Card: MIT | **Bester externer Prototyp** |
| VGC-Bench SV-Archiv | Ja | Nein | Dataset Card/Archiv prüfen | Für `gen9vgc2025regi` zuerst ansehen |
| PokéChamp Dataset | Teilweise | Nein | Kein klares Lizenzfeld auf aktueller Card | Parser/Priors, vorsichtig nutzen |
| Metamon Parsed Replays | Nein, Singles | Ja beziehungsweise rekonstruiert | CC BY-NC 4.0 | Nur Methoden-/Schema-Referenz |
| Kaggle Gen9 Randbats | Nein | Geparstes Zuschauerlog | Card: MIT | Nur schneller Parser-Prototyp |
| Eigene seeded Self-Play-/Teacher-Daten | Ja | Ja | Eigenes Projektartefakt | **Primäre kontrollierte Trainingsquelle** |

## 8. Empfohlene Lesereihenfolge ab heute

1. [VGC-Bench Paper](https://arxiv.org/abs/2506.10326), danach [aktuelles Repository](https://github.com/cameronangliss/VGC-Bench) und [OTS-Datensatz](https://huggingface.co/datasets/cameronangliss/vgc-battle-logs).
2. [Showdown RNG](https://pokemonshowdown.com/pages/rng), [SIM-PROTOCOL](https://github.com/smogon/pokemon-showdown/blob/master/sim/SIM-PROTOCOL.md) und [`sim/README.md`](https://github.com/smogon/pokemon-showdown/blob/master/sim/README.md).
3. [Foul Play – technischer Artikel](https://pmariglia.github.io/posts/foul-play/) mit Fokus auf Hidden Information und Set Prediction.
4. [Metamon Paper](https://arxiv.org/abs/2504.04395) mit Fokus auf Replay-Rekonstruktion, Missing Actions und getrennte Human-/Self-Play-Daten.
5. [PokéAgent Battling](https://pokeagentchallenge.com/battling.html) für aktuellen Server, Datensätze, Baselines und Einreichungsweg.
6. [ps-ppo](https://github.com/Nebraskinator/ps-ppo) erst danach als spätere Modellarchitektur-Idee.
7. PokéChamp, PokeLLMon und PsyMew nur als Hybrid-/Failure-Mode-Lektüre, nicht als unmittelbaren Bauplan.

## Schlussurteil

Die Quellen sprechen dafür, den aktuellen Kurs **nicht** zu wechseln, sondern ihn zu schärfen. Euer Reproducibility-Harness ist kein Nebenprojekt mehr, sondern der zentrale Wettbewerbsvorteil des Bots: Er macht kleine, saubere, gepaarte Verbesserungsnachweise möglich und verhindert, dass RNG oder versteckte Fallbacks als „Modellfortschritt“ erscheinen.

Der nächste reale Durchbruch wird wahrscheinlich nicht aus einer neuen Engine oder einem LLM kommen. Er wird aus der Kombination entstehen aus:

- vollständig gepinnter Laufzeitumgebung,
- breiterer VGC-Teamgeneralisierung,
- besserem probabilistischem Opponent Modeling,
- einem diversen, reproduzierbaren Reranker-Datensatz,
- und einem streng gepaarten Candidate-vs-Baseline-Gate.

Genau dafür ist der jetzige Projektstand bereits vorbereitet.
