# Rethink NInfer : perf et ressources, config réelle (2026-11-17)

Étude `/rethink` sur le moteur NInfer tel qu'il tourne sur cette machine (RTX 5090 32 Go,
Qwen3.8-27B NVFP4 + DFlash2 K=7, serveur :8000). Rapport produit par Claude Fable 5.1 avec
deux divergences à l'aveugle de l'IA locale (qwen3.8-27b). Rien n'a été modifié.

**But** : servir un modèle ~27B dense sur une 5090 aux agents locaux, meilleur débit, moins de
VRAM / RAM hôte / CPU, sans dégrader la qualité.

**Trace** : 30 idées brutes (Claude 14, IA locale 16), 16 écartées, 9 vérifs lancées (2 benchs HTTP
sur le serveur, 4 agrégations du log de requêtes sur 113 h / 7769 requêtes, `--help` du binaire,
lecture manifeste et docs, 1 A/B sampling).

**Vu en passant** : binaire du 7 novembre, 68 commits derrière HEAD. Process avec 2,1 GB en swap.
Poids compagnons DFlash2 en BF16 (2,4 GiB). Second artefact `…-v3.ninfer` (23,7 GB) non servi.

## Hypothèses remises en cause

- Decode borné par la bande passante GPU, hôte ~30 % d'un cœur, prefill 5 % du temps / decode 90 % : **vérifié** (log).
- NInfer déjà plus rapide que les concurrents sur une 5090 : 245 à 300 tok/s C=1 mesurés ici, contre
  SGLang DFlash2 140 à 221, vLLM MTP 101, llama.cpp ~59 : **vérifié** (bench +
  https://suhailmohebi.com/insights/rtx-5090-llm-serving/ ,
  https://github.com/darksidewalker/qwen3.8-27b-sglang-dspark-blackwell ,
  https://runtimewire.com/article/sglang-qwen3-8-27b-nvfp4-dflash2-cookbook ).
- Cache hôte 22 GiB utile : relecture KV 2,7 GB pour 105 GB écrits, restauration d'images d'état sur
  17 % des requêtes : volumes **vérifiés**, utilité du dimensionnement à 22 GiB **supposée**.
- Vision inutile pour les agents : **faux**, 4,5 % des requêtes portent une image.
- Trafic mono-flux : batch decode moyen 1,0, préfixe réutilisé à 95 % des tokens de prompt,
  prompts p50 23,6k / p99 166k / max 203k : **vérifié**.
- Sampling client T=1,0 / presence 1,5 donne une acceptance DFlash2 de 42 % (3,96 tok/round) contre
  54 % en greedy publié. Le thinking fait 75 % des tokens générés : **vérifié** (log).
- HEAD apporte du gain decode NVFP4 (tiles FFN 5090, staging, overlap quantization) : **supposé**.
- Un drafter NVFP4 garde l'acceptance : **supposé** (publié côté SGLang :
  https://huggingface.co/maurienne-ai/Qwen3.8-27B-DFlash2-NVFP4-RTNcal , 215 vers 228 tok/s, 3,5 vers 1,4 GB).

## Options

| # | Option | Gain | Coût | Risque / réversibilité | Contraintes cassées | Preuve | Origine |
|---|---|---|---|---|---|---|---|
| 0 | Statu quo | 245 à 300 tok/s C=1, 680 agrégé C=4, 30,8 GB VRAM, 22 GiB RAM épinglée + 2,1 GB swap | 0 | — | — | mesuré | — |
| 1 | **Incrémental** : rebuild sur HEAD via le launcher hominfer | tuning decode NVFP4 + fix de partage des préfixes ; mesurer avec le même bench avant/après | 1 build + restart | faible, ancien binaire conservé ; vérifier taille graph/workspace au démarrage | aucune | estimé | Claude |
| 2 | **Incrémental** : `--host-cache-capacity` 22 GiB vers 8 GiB (défaut), `--memory-headroom` 2 GiB vers 512 MiB | −14 GB de RAM épinglée, swap résorbé ; +1,5 GiB de pool contexte (+25 % de tokens) | 2 flags | éviction des images d'état chaudes donc TTFT en hausse sur ces requêtes ; surveiller `h2d`/TTFT une semaine, retour trivial | aucune | mesuré (volumes), estimé (hot set) | Claude + locale |
| 3 | **Incrémental, côté agents** : profil Qwen T 0,6 / top_p 0,95 / presence 1,0 ; thinking conditionnel par type de tâche | acceptance 42 % vers jusqu'à 54 % ; A/B 2×2 : 275 à 318 vs 316 à 358 tok/s (bruité) ; le thinking est le levier n°1 du temps par requête | config des agents | qualité : presence 1,5 et thinking peuvent être porteurs | « ne pas dégrader la qualité » | mesuré (acceptance), estimé (A/B) | Claude |
| 4 | **Structurel** : poids compagnons DFlash2 en FP8/NVFP4 dans l'artefact | −1 à −1,8 GiB VRAM, drafter moins gourmand en bande passante (+6 % publié sur SGLang) | convertisseur + loader + validation acceptance, quelques jours | baisse d'acceptance sous T=1,0 ; vérification reste exacte ; réversible | aucune | publié, spéculatif pour NInfer | locale + Claude |
| 5 | **Rupture** : drafter DSpark ou vérification en arbre DDTree sur DFlash2 | longueur d'acceptation 5,3 vs 4,6 sur Qwen3-8B (https://arxiv.org/pdf/2607.05147 , https://arxiv.org/abs/2604.12989) ; mais sur 27B/5090 : SparkInfer 216 vs 210, darksidewalker 126 vs 221 | nouveau backend spéculatif + graphes CUDA, des semaines | gain non transféré au modèle hybride ; l'arbre ajoute du trafic mémoire par round | aucune | spéculatif, publié contradictoire | Claude + locale |

Le pool contexte n'est pas le goulot : 317k tokens de capacité pour un max observé de 203k, hit
préfixe 95 %. Toute économie VRAM est réinjectée dans le pool par construction, donc « moins de
VRAM » ne change presque rien. Le vrai gain ressources est la RAM hôte (option 2).

## Écartées

- Prefill chunks 32k : prefill = 5 % du temps.
- Graph CUDA batch 4 pour les rafales : batch moyen 1,0.
- MTP à la place de DFlash2 : 205 vs 285 tok/s publiés dans le repo.
- KV 2 bits déporté sur l'hôte / KV TurboQuant 3,5 bits (https://github.com/OnlyTerp/turboquant) :
  risque qualité, correction à prouver, pool déjà suffisant.
- Réduire `--max-context` : le pool est dimensionné en octets, rien n'est réservé.
- Épingler les préfixes partagés : déjà 95 % de hit.
- Cache de blocs de proposition (n-grams) et contexte « LOD » pour le drafter : spéculatif, tokens de
  thinking trop stochastiques.
- K=15 : positions 8+ acceptées à moins de 18 %, temps de vérification doublé ; K=7 reste bon.
- Vision chargée à la demande : le GiB libéré va dans un pool qui ne manque pas, TTFT en hausse pour
  4,5 % des requêtes.
- Spéculation sur états récurrents (idée de l'IA locale) : viole la correction numérique et « pas de
  chemin par checkpoint » d'AGENTS.md.
- Changer de moteur : aucune preuve d'un gain sur une 5090 ; seul le TP2 sur 2×5090 fait mieux
  (264 tok/s C=1, 2649 agrégé, https://yage.ai), c'est du matériel.
- Réécriture Rust : non. Le decode est GPU-bound et l'hôte consomme 30 % d'un cœur ; réécrire le
  code hôte ne déplace rien.

## Verdict

- **Maintenant** : option 2 (deux flags) + option 1 (rebuild HEAD, bench identique avant/après).
  Tant que le serveur n'est pas redémarré, rien d'autre n'est mesurable.
- **Prototype** : option 4 (DFlash2 en FP8/NVFP4), validation la moins chère = A/B de 30 requêtes
  identiques sur acceptance et tok/s.
- **Explorer** : option 5, seulement après une mesure publiée sur Qwen3.8-27B hybride.

Questions hors contraintes : l'option 3 touche la qualité (presence 1,5 et thinking à 75 % des
tokens). Les agents acceptent-ils un profil Qwen et un thinking conditionnel ? Une seconde 5090
est-elle envisageable, puisque c'est la seule voie publiée au-dessus du débit actuel ?

## Addendum : dual boot Linux à la place de Windows + WSL2

Faits mesurés (2026-11-17) : 64 Go physiques ; `.wslconfig` plafonne WSL à 40 Go ; swap WSL
10 Go dont 4 Go utilisés ; Windows a 26 Go libres au même instant, donc sa part de 24 Go est
presque inutilisée pendant que NInfer swappe.

| Levier | Gain attendu | Preuve |
|---|---|---|
| RAM : tout le 64 Go pour le moteur, plus de swap | +20 Go utilisables ; le cache hôte 22 GiB tient sans swap | estimé (arithmétique) |
| VRAM : plus de réservation WDDM / compositeur Windows | ~0,5 à 1 GiB, réinjecté dans le pool contexte, qui ne manque pas | estimé |
| Latence : CUDA natif vs couche WSL2 (lancement de kernels, H2D, pinned) | quelques % au mieux à batch 1 ; les graphes CUDA masquent déjà l'essentiel | estimé, à mesurer |
| CPU : pas de VM, pas de Windows résident | marginal, l'hôte fait 30 % d'un cœur | mesuré (hôte), estimé (gain) |

Lecture : le dual boot règle surtout le problème RAM, mais l'option 2 (cache hôte 8 GiB) ou une
ligne dans `.wslconfig` (`memory=52GB`, Windows idle tient dans ~10 Go) le règlent aussi, sans
redémarrer dans un autre OS ni perdre Windows en parallèle. Le dual boot ne devient intéressant
que si (a) le gain de latence natif est mesuré et significatif, ou (b) la machine devient un
serveur Linux permanent (headless, pilotage à distance), auquel cas ce n'est plus un dual boot
mais un changement d'OS principal. Validation la moins chère : clé USB live Ubuntu + pilote
NVIDIA + le même bench HTTP C=1 (TTFT, tok/s), une soirée.

## Décisions (2026-11-17, après le verdict)

Le but est reprécisé par Tony : **qualité et stabilité d'abord, vitesse ensuite**. Une autre session
mène en parallèle un plan stabilité (`~/llm/PLAN-stabilite.md`) : les gels sont des timeouts du
pilote GPU (TDR), pas un manque de RAM. Les actions ci-dessous s'alignent sur ce plan.

| Option | Décision | Action faite |
|---|---|---|
| 1 rebuild HEAD | retenue | compilé d'abord dans le worktree `~/llm/ninfer-next` (test), puis `~/llm/ninfer` avancé en ff sur ebdc67e5 et rebuild en place, ancien binaire gardé en `ninfer-serve.prev` ; bascule au redémarrage autorisé |
| 2 cache hôte | retenue, 8 GiB | `~/.config/hominfer/engines.json` : `host_cache` par défaut 22368MiB → 8GiB (sauvegarde `.bak-2026-11-17`) ; prend effet au prochain lancement |
| 2 headroom VRAM | **3 GiB** (sens inverse de l'option) | la carte était à 0,25 GiB libre (NInfer 28 GiB + Windows 4 GiB) ; 3 GiB rend ~1 GiB à Windows contre −17 % de capacité KV (~263k tokens, toujours > 240k). Pool laissé en auto. |
| `.wslconfig` | inchangé | 40 Go WSL / 24 Go Windows respecte déjà « au moins 16 Go pour Windows » ; sans le cache de 22 GiB le swap disparaît sans toucher au partage |
| 3 sampling / thinking | écartée | qualité avant tout |
| seconde 5090 | écartée | hors budget |

## Addendum : écran sur l'iGPU

Compteurs Windows `GPU Process Memory / Dedicated Usage` sur la 5090 (2026-11-17, approximatifs) :

| Process | VRAM dédiée |
|---|---|
| dwm (compositeur bureau) | 1,5 Go |
| ProtonVPN.Client (WebView2) | 2,1 Go |
| Firefox | 0,4 Go |
| Terminal, explorer, csrss, overlay NVIDIA | 0,35 Go |

Brancher l'écran sur l'iGPU déplace dwm et le rendu des applications sur l'iGPU : environ 2,5 à
4 Go rendus à la 5090, et surtout plus de TDR liés à l'affichage (étape D du plan stabilité).
Gain immédiat sans câblage : désactiver l'accélération GPU de ProtonVPN ou le fermer, 2 Go.
La VRAM libérée doit aller dans un `--context-capacity` fixé (étape A), pas dans un pool `auto`
qui remplit la carte jusqu'au headroom.
