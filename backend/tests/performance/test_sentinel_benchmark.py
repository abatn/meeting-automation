#!/usr/bin/env python3
"""Sentinel LLM Benchmark - Config Comparison.
Run: python3 backend/tests/performance/test_sentinel_benchmark.py
"""
import gc, json, os, sys, time, platform

MODEL_PATH = os.environ.get("SENTINEL_MODEL_PATH",
    "/home/opc/meeting-automation/qwen2.5-1.5b-instruct-q4_k_m.gguf")

CONFIGS = {
    "A_baseline": {"n_threads": 2, "n_ctx": 2048, "max_tokens": 256, "label": "Baseline (2t/2048ctx/256tok)"},
    "B_threads":  {"n_threads": 4, "n_ctx": 2048, "max_tokens": 256, "label": "4 Threads (4t/2048ctx/256tok)"},
    "C_context":  {"n_threads": 2, "n_ctx": 1024, "max_tokens": 128, "label": "Reduced Ctx (2t/1024ctx/128tok)"},
    "D_combined": {"n_threads": 4, "n_ctx": 1024, "max_tokens": 128, "label": "Combined (4t/1024ctx/128tok)"},
}
RUNS = 3

SYSTEM_PROMPT = (
    "Summarize this meeting segment in 2-3 sentences. "
    "CRITICAL: Preserve speaker names exactly as written "
    "(e.g. 'Ahmed proposed X', 'Fatima agreed'). "
    "Do NOT merge speakers or use generic terms like 'the team'. Language: fr"
)


def _make_texts():
    short = ("Ahmed: Bonjour a tous, merci d etre presents. Nous allons commencer par le point "
             "sur l avancement du projet. Fatima, pouvez-vous nous faire un retour sur les "
             "developpements cette semaine? "
             "Fatima: Oui bien sur. Nous avons termine l integration de l API de transcription "
             "et les tests unitaires passent a 98 pour cent. Il reste a finaliser le deploiement "
             "sur le cluster de staging. "
             "Ahmed: Excellent. Y a-t-il des blocages a signaler? "
             "Fatima: Non, tout est en bonne voie. Nous prevoyons de livrer vendredi.")

    medium = ("Ahmed: Bonjour a tous, bienvenue a cette reunion hebdomadaire. Commencons par le "
              "point sur l avancement du projet de pipeline d automatisation. Fatima, pouvez-vous "
              "nous faire un retour detaille sur les developpements de cette semaine? "
              "Fatima: Oui bien sur. Nous avons termine l integration de l API Gladia pour la "
              "transcription automatique. Les tests unitaires passent a 98 pour cent de couverture. "
              "Cote backend, l endpoint de creation de reunion fonctionne correctement avec "
              "l authentification JWT. Nous avons aussi corrige un bug dans le service de "
              "diarisation qui causait des erreurs sur les audios de moins de 30 secondes. "
              "Ahmed: Tres bien. Y a-t-il des blocages ou des dependances? "
              "Fatima: Oui, nous avons un point de blocage sur l integration avec le service "
              "LiveKit pour l enregistrement. La connexion WebSocket tombe apres 15 secondes "
              "ce qui interrompt l enregistrement. Nous avons besoin de l aide de Karim. "
              "Karim: Je peux regarder cela. Je pense que c est lie a la configuration du "
              "load balancer. Je vais ajuster le timeout a 60 secondes et tester. "
              "Ahmed: Parfait. Qu en est-il du deploiement en production? "
              "Karim: Le cluster de production est pret. Nous avons 8 coeurs AMD EPYC disponibles "
              "mais le conteneur est limite a 1 coeur CPU. "
              "Fatima: Pour la partie IA, le modele Qwen de 1.5 milliards fonctionne bien. "
              "Le temps d inference est d environ 120 secondes par chunk. "
              "Nous pourrions reduire la fenetre de contexte de 2048 a 1024 tokens. "
              "Ahmed: Pouvez-vous faire un test de benchmark? "
              "Fatima: Oui, je lance les tests. 2 et 4 threads, 1024 et 2048 tokens. "
              "Ahmed: Excellent. Nous devons finaliser l identification des intervenants. "
              "Fatima: Le matching phonetique fonctionne deja. "
              "Karim: Prometheus et Grafana sont configures. "
              "Ahmed: Parfait. Bonne semaine a tous.")

    long_text = ("Ahmed: Bonjour a tous, bienvenue a cette reunion hebdomadaire du projet "
                 "d automatisation de reunions. Nous avons plusieurs points importants a aborder. "
                 "Fatima, pouvez-vous nous faire un retour detaille sur les developpements? "
                 "Fatima: Cette semaine a ete tres productive. Nous avons termine l integration "
                 "complete de l API Gladia pour la transcription automatique des reunions. "
                 "Les tests unitaires passent a 98 pour cent de couverture. Cote backend, "
                 "l endpoint POST /api/v1/meetings fonctionne correctement avec JWT. "
                 "Nous avons aussi implemente le rafraichissement automatique des tokens. "
                 "Pour le service de diarisation, nous avons corrige un bug critique. "
                 "Le probleme venait du calcul de la distance cosinus entre les embeddings. "
                 "Ahmed: Y a-t-il des blocages? "
                 "Fatima: Oui, un point de blocage majeur sur l integration LiveKit. "
                 "La connexion WebSocket tombe apres 15 secondes. "
                 "Karim: Je peux regarder cela. C est lie au load balancer Traefik. "
                 "Le timeout est de 10 secondes, insuffisant pour WebSocket. "
                 "Je vais ajuster a 60 secondes avec ping automatique. "
                 "Ahmed: Qu en est-il du deploiement? "
                 "Karim: Le cluster de production a 8 coeurs AMD EPYC avec 23 GB RAM. "
                 "Mais le conteneur Celery est limite a 1 coeur CPU et 6 GB RAM. "
                 "Le threading sur 1 coeur provoque du thread thrashing. "
                 "Le calcul est 9.7 fois plus lent qu avec 1 seul thread. "
                 "Fatima: Pour Sentinel Qwen 1.5B, le temps d inference est 120 secondes. "
                 "Le debit est de 1.2 tokens par seconde. Avec 2 threads sur 1 coeur, "
                 "pas d amelioration significative. "
                 "Ahmed: Quelles options pour optimiser? "
                 "Fatima: Trois approches. Premierement, augmenter les threads a 4 "
                 "mais cela necessite plus de coeurs CPU. Deuxiemement, reduire le contexte "
                 "de 2048 a 1024 tokens. Troisiemement, reduire max_tokens de 256 a 128. "
                 "Karim: Je recommande d augmenter les coeurs a 2 ou 4. "
                 "Fatima: D accord, je lance un benchmark avec 4 configurations. "
                 "Textes courts, moyens et longs, 2 et 4 threads, 1024 et 2048 tokens. "
                 "Ahmed: Nous devons finaliser l identification des intervenants. "
                 "Fatima: Le matching phonetique Double Metaphone fonctionne. "
                 "Le scoring de confiance a un seuil de 0.65 avec fallback Mistral. "
                 "Karim: Prometheus et Grafana surveillent le pipeline. "
                 "Alertes configurees pour les depassements de seuils. "
                 "Fatima: Cache Redis pour les embeddings de speakers implemente. "
                 "Ahmed: Concernant la securite? "
                 "Karim: Chiffrement AES-256 pour les enregistrements dans MinIO. "
                 "Cles gerees via Kubernetes Secrets, rotation tous les 90 jours. "
                 "Audit ISO 27001 pour toutes les operations. "
                 "Fatima: Frontend migre vers React 18 avec TypeScript. "
                 "MeetingRoom gere les etats LiveKit avec reconnexion auto. "
                 "Support RTL pour l arabe ajoute. "
                 "Ahmed: Parfait. Assurez-vous que le pipeline fonctionne "
                 "en moins de 90 secondes. Bonne semaine a tous.")

    return {"short": short, "medium": medium, "long": long_text}

