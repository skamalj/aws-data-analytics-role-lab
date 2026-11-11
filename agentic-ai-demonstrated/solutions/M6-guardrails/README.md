# Mission 6 solution: Trail Desk is oversharing

```bash
patch -p1 < solutions/M6-guardrails/fix.patch
./scripts/deploy.sh M6       # updates DRAFT, creates version 2, points the agent at it
```

## Fault 1: only the codename is filtered, not the subject

| | |
|---|---|
| Symptom | "Summit Pro Ultra … launching 14 March" reaches the customer |
| Where | `word_policy_config` only contains `Ridgeback` |
| Root cause | Word filters do exact word/phrase matching. The notes call the product by its launch name, so nothing matched. Product names change and can be paraphrased |
| Fix | A **denied topic** `unreleased-products` (`type = "DENY"`) with a definition and examples, which matches on *meaning*. Add the launch name to the word list as well, as a cheap exact-match backstop |

## Fault 2: the discount-code regex doesn't match real codes

| | |
|---|---|
| Symptom | `RB-STAFF40` and `RB-K9X2QT` appear in answers |
| Where | `regexes_config.pattern = "RB-[0-9]{4}"` matches only four digits |
| Fix | `RB-[A-Z0-9]{5,10}` with `ANONYMIZE`. The answer shows `{STAFF_DISCOUNT_CODE}`. Use `BLOCK` if you'd rather drop the whole answer |

## Fault 3: e-mail masking is off for outputs

| | |
|---|---|
| Symptom | The phone number is masked but `dana.whitfield@example.com` is shown |
| Where | `pii_entities_config EMAIL`: `output_enabled = false` |
| Root cause | Each PII entity, regex, word and content filter can be enabled separately for **input** (the user's text) and **output** (the model's answer). The leak is in the output |
| Fix | `output_enabled = true`. Leaving `input_enabled` / `output_enabled` unset means both are on, which is how `PHONE` is configured |

## Fault 4: the agent uses a stale guardrail version

| | |
|---|---|
| Symptom | After fixes 1–3, `apply-guardrail --guardrail-version DRAFT` behaves correctly, but the agent still leaks |
| Where | `GUARDRAIL_VERSION = aws_bedrock_guardrail_version.v1.version`. Version 1 was snapshotted from the broken configuration |
| Root cause | Guardrail **versions are immutable**. Changes only go to `DRAFT` until you publish a new version |
| Fix | Add `aws_bedrock_guardrail_version.v2`, which is created after the guardrail update because it references it, and point the agent at `v2.version` |

## Debrief answers

1. The prompt-attack filter evaluates *user input* for jailbreaks and injection. On model output it has no meaning, and the API requires `NONE`.
2. Use **ANONYMIZE** when the answer is still useful without the value ("contact {EMAIL}"). Use **BLOCK** when the presence of the data
   is itself the problem: card numbers in input, or credentials. For input, `BLOCK` stops sensitive data from ever reaching the model or its logs.
3. A pinned version gives you reproducible, reviewable behaviour, and an agent update and a guardrail change can't race each other. Roll out by
   testing `DRAFT` with `apply-guardrail` against a regression prompt set, publishing version N+1, moving one agent or alias to it,
   watching the guardrail metrics and traces, and then moving the rest.
4. Leaks that need context: a paraphrased code ("forty percent off with STAFF and the number 40"), data split across turns,
   or tool calls that *act* on secrets without echoing them. The real fix is **data minimisation**: don't put secrets in the model's
   context at all. Fetch them through a tool that enforces who the caller is (Mission 1), and log and monitor guardrail interventions.
