# Ludus AI — Architettura (bozza di design)

> ⚠️ **La fonte canonica della documentazione è ora la [Wiki del progetto](../../wiki)**
> (in inglese), generata dai file in [`wiki/`](../wiki). Questo documento resta lo
> **scratchpad italiano** dove sono nate le idee; per il design elaborato (contratto
> `RunResult`, i 5 adapter, Livello C concreto, domande aperte rifatte, roadmap affinata)
> vedi la wiki.

> Documento di lavoro, scritto in italiano per ragionarci sopra.
> Quando il design sarà stabile lo tradurremo/sintetizzeremo nel README pubblico.
> Stato: **bozza** · Caso d'uso pilota: testare il plugin **Sethlans**.

---

## 1. Scopo

Ludus AI è il **banco di prova** per sistemi AI: agenti, plugin, modelli, prompt e
skill. Non costruisce gli agenti — li **mette alla prova** in modo ripetibile e
misurabile, producendo punteggi, gate pass/fail e rilevamento di regressioni.

Terminologia (per fissare il vocabolario, evitando l'ambiguità "hardness"):

| Termine | Significato in Ludus |
|---|---|
| **Eval** | La disciplina: misurare la qualità di un sistema AI |
| **Harness** | L'infrastruttura che *esegue* il sistema sugli scenari e raccoglie i risultati (il "test runner") |
| **Scenario** | Un caso di prova: `input + contesto → output atteso / criteri` |
| **Evaluator (Judge/Check)** | Ciò che giudica un output rispetto alle attese |
| **Gate** | La regola che trasforma i punteggi in pass/fail (per la CI) |

---

## 2. Cosa testiamo: Sethlans come caso pilota

Sethlans orchestra `PO → UX → Architetto → DevOps → Dev → Reviewer/Tester`.
Ogni fase produce un **semilavorato** (artifact) che alimenta la fase successiva.
Questo ci dà due livelli di test naturali — esattamente la tua intuizione
"unit + e2e + revisione dei semilavorati".

### Livello A — Test del singolo agente (tipo *unit*)
Si isola un subagent, gli si dà un input fisso (fixture) e si valuta solo il suo
output. Esempi:
- **Product Owner**: dato un brief → produce epiche/storie ben formate, con
  acceptance criteria, senza ambiguità? (giudizio NL → LLM-as-judge + check di struttura)
- **Architetto**: data una storia → produce una scomposizione in task coerente,
  con scelte tecniche motivate? (LLM-as-judge su rubrica + check di completezza)
- **Backend Developer**: dato un task → produce codice che **compila, passa i test,
  supera il linter/Sonar**? (check deterministici + gate strumentali)

### Livello B — Test della pipeline completa (tipo *e2e*)
Si invoca `/sethlans` su uno use case reale e si valuta il **prodotto finale**:
il codice gira? i test passano? la coverage è sufficiente? Sonar/CodeScene sono verdi?
La feature soddisfa gli acceptance criteria iniziali?

### Livello C — Test degli handoff / gate tra fasi (i "semilavorati vagliati")
Tra una fase e l'altra mettiamo un **gate**: l'artifact prodotto deve superare
criteri minimi prima di passare oltre. Ludus può:
- verificare che ogni handoff rispetti il contratto (lo `tabula-protocol.md` di Sethlans
  è già un contratto formale: ottimo punto d'aggancio per i check di struttura);
- iniettare un semilavorato "noto buono" e testare le fasi a valle in isolamento
  (così un errore della fase 2 non inquina il giudizio sulla fase 5).

---

## 3. Modello concettuale (domain model)

Le entità centrali, indipendenti dalla tecnologia:

```
Suite ──< Scenario ──< Run ──> Artifact
                         │
                         └──< Evaluation ──> Score/Verdict
Gate (policy) ── applica soglie a ──> Score  ──> Report
Target ── è ciò che la Run esegue (agente | pipeline | skill | prompt | modello)
```

- **Target** — *cosa* mettiamo alla prova. Astrazione chiave: un agente singolo,
  l'intera pipeline Sethlans, una skill, un prompt o un modello. Dietro c'è un
  **Adapter** che sa come invocarlo (vedi §4).
- **Scenario** — un caso di prova: `input` (use case), `fixtures/contesto`
  (semilavorati a monte, file, mock), e `expectations` (asserzioni + rubriche).
- **Run** — una singola esecuzione `Target × Scenario`. Non deterministica:
  prevediamo **N ripetizioni** per stimare la stabilità.
- **Artifact** — l'output prodotto (codice, storia, mockup, scomposizione task)
  + la **trace** (step, tool call, token, costo, latenza).
- **Evaluation / Evaluator** — applica uno o più giudici all'artifact (vedi §4).
- **Score / Verdict** — risultato: punteggio numerico, pass/fail, rubrica.
- **Gate** — politica di soglia ("≥ 90% degli scenari passa", "nessuna regressione
  > 5% vs baseline"). È ciò che la CI consulta per bloccare/promuovere.
- **Report** — risultati aggregati + confronto con la **baseline** (regressioni).

Principio guida: gli output AI sono **non-deterministici**. Non ragioniamo in
pass/fail secco sulla singola run, ma in **score aggregati su N run** e soprattutto
in **regressioni** rispetto a una baseline storica.

---

## 4. Architettura a livelli

```
┌─────────────────────────────────────────────────────────────┐
│  CLI / CI (GitHub Actions)  ── orchestrazione, gate, exit code │
├─────────────────────────────────────────────────────────────┤
│  Reporting & Baseline  ── score aggregati, trend, regressioni │
├─────────────────────────────────────────────────────────────┤
│  Evaluators (giudici)                                         │
│   • Deterministici  (regex/contains, JSON schema, file esiste)│
│   • Strumentali     (compila, test, coverage, lint, Sonar)    │
│   • LLM-as-judge    (rubriche su artefatti in linguaggio nat.)│
│   • Human-in-loop   (cattura revisione manuale, opzionale)    │
├─────────────────────────────────────────────────────────────┤
│  Harness  ── esegue Scenario × Target, N ripetizioni, raccolta│
├─────────────────────────────────────────────────────────────┤
│  Adapters (come invoco il Target)                            │
│   • Agente Claude Code singolo   • Pipeline /sethlans         │
│   • Skill / Prompt               • Modello via API            │
├─────────────────────────────────────────────────────────────┤
│  Scenario store  ── definizioni scenari + fixtures (YAML/file)│
└─────────────────────────────────────────────────────────────┘
```

**Tassonomia degli evaluator** (il cuore della qualità):

| Tipo | Quando | Esempio su Sethlans |
|---|---|---|
| Deterministico | output strutturato/verificabile | la storia ha tutti i campi obbligatori |
| Strumentale (gate) | l'output è codice | `pytest` verde, lint pulito, Sonar OK |
| LLM-as-judge | output in linguaggio naturale | qualità/chiarezza delle acceptance criteria |
| Human-in-loop | giudizio finale/calibrazione | spot-check manuale per tarare i judge |

> Nota sul punto **Sonar/CodeScene**: si agganciano come evaluator *strumentali*
> a valle, **solo** sugli artefatti che sono codice (Livello A-dev e Livello B).
> Per gli artefatti di processo (storie, architettura) servono i judge LLM.

---

## 5. Flusso end-to-end (esempio: testare l'agente Architetto)

1. **Scenario**: input = una storia "nota buona"; expectations = rubrica
   ("la scomposizione copre tutti gli acceptance criteria", "le scelte tecniche
   sono motivate", "nessun task orfano") + check di struttura.
2. **Adapter** invoca l'agente Architetto di Sethlans in modalità headless,
   passando la fixture come contesto.
3. **Harness** esegue la run N volte, salva artifact + trace.
4. **Evaluators**: check di struttura (deterministico) + LLM-as-judge su rubrica.
5. **Score**: media su N run + varianza (stabilità).
6. **Gate**: confronto con baseline → pass/fail.
7. **Report**: tabella per scenario, evidenza delle regressioni.

---

## 6. Formato scenario (bozza, da validare)

```yaml
# scenarios/architetto/scomposizione-login.yaml
id: architetto-scomposizione-login
target: sethlans.agent.architect      # quale Adapter usare
description: L'architetto scompone la storia "login utente" in task coerenti
repeat: 5                              # N ripetizioni (non determinismo)

input:
  prompt_fixture: fixtures/stories/login.md

context:
  files:
    - fixtures/repo-skeleton/          # stato del repo a monte

expectations:
  - type: schema                       # deterministico
    must_have_fields: [tasks, rationale]
  - type: contains
    any_of: ["FastAPI", "endpoint", "auth"]
  - type: llm_judge                    # rubrica
    rubric: rubrics/architect.md
    pass_threshold: 0.8

gate:
  min_pass_rate: 0.9                   # ≥ 90% delle run passa
  max_regression_vs_baseline: 0.05
```

---

## 7. Build vs Buy — analisi e raccomandazione

La domanda che hai lasciato aperta. Il punto chiave:

- Il **livello superiore** (eseguire un *plugin Claude Code con subagent* in modo
  ripetibile, iniettare fixture tra le fasi, leggere le trace di Tabula) è **di
  nicchia**: i framework di eval esistenti testano prompt/modelli/chiamate API,
  non "invocazioni di plugin Claude Code multi-agente". Questo strato lo
  **costruiamo noi** — è il valore proprio di Ludus.
- Il **livello inferiore** (LLM-as-judge, scoring, tracing, gate sul codice) è
  **commodity**: esistono ottimi strumenti maturi.

**Raccomandazione: ibrido.** Ludus costruisce harness + modello scenari + adapter
per Sethlans, e **integra** (non reinventa) per il resto:

| Strato | Decisione | Candidati da valutare |
|---|---|---|
| Harness/adapter Claude Code | **Build** | Claude Agent SDK / modalità headless |
| Formato scenari + gate | **Build** | (è il nostro contratto) |
| LLM-as-judge / asserzioni | Buy/integrate | Promptfoo, DeepEval, Inspect AI |
| Tracing/osservabilità | Buy/integrate | Langfuse, Phoenix |
| Gate sul codice | Buy/integrate | pytest, lint, SonarQube, CodeScene |

> Prima di fissare l'adapter Claude Code verificherò la documentazione aggiornata
> dell'Agent SDK / modalità headless (come invocare plugin e singoli subagent da
> script), perché è il dettaglio tecnico su cui si regge tutto il Livello A.

---

## 8. Domande aperte / decisioni da prendere

1. **Invocazione headless**: si può lanciare un *singolo* subagent di Sethlans in
   isolamento, o solo la pipeline `/sethlans` intera? Determina se il Livello A
   è fattibile o se partiamo dal Livello B.
2. **Fixture degli handoff**: dove conserviamo i semilavorati "noti buoni"?
   Servono per testare le fasi a valle in isolamento.
3. **Baseline**: dove vivono i risultati storici (file nel repo? DB?) per il
   calcolo regressioni.
4. **Costo**: le eval consumano token. Definire un budget e quante ripetizioni N.
5. **Linguaggio di implementazione**: Python (ecosistema eval più ricco) sembra
   la scelta naturale, ma da confermare.

---

## 9. Roadmap incrementale (proposta)

- **M0 — Carta** *(qui)*: questo documento, vocabolario e modello concettuale.
- **M1 — Walking skeleton**: 1 scenario reale su 1 target (es. agente Architetto
  o pipeline intera), 1 evaluator deterministico + 1 LLM-judge, report a console.
- **M2 — Gate & baseline**: soglie, baseline, rilevamento regressioni.
- **M3 — CI**: GitHub Action che blocca il merge sotto soglia.
- **M4 — Copertura**: scenari per più agenti, gate strumentali (Sonar/test/lint).
- **M5 — Generalizzazione**: estendere oltre Sethlans (skill, prompt, modelli).
```
