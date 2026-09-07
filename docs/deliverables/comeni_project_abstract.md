---
title: "Augmentation by construction: governed language models across the bioinformatics workflow lifecycle"
author: "Comeni Labs"
date: ""
lang: en-GB
---

Modern biology depends on computation, yet experimental and computational practice remain divided by bioinformatics skill gaps [1]. Generative AI could make analysis more accessible, but direct pipeline generation remains prompt-dependent and transfers opaque code and costly review to specialists [2]. Bioinformaticians also inherit fragmented infrastructure and workflows that decay as tools and dependencies change [3].

Comeni Labs is an open-source, modular platform joining biological intent, workflow construction, execution, observation, and maintenance. It combines the accessibility of low-code systems, community-curated tool knowledge, and portable workflow execution [4,5]. Experimental specialists can participate from the first analytical decision, while bioinformaticians receive inspectable, containerised Nextflow code that they own and can edit, extend, and deploy across local, cluster, and cloud environments.

Its distinguishing method is semi-deterministic construction. Language models translate intent and operate typed application programming interfaces, an approach motivated by both the capabilities and limitations of tool-using models [6]. Deterministic services retain authority over workflow emission, validation, execution, and state. Decisions supported by versioned contracts, controlled vocabularies, scientific rules, or measured data are derived; remaining uncertainties become addressable questions with evidence and legal answers. Once these inputs are settled, the same declared state produces byte-identical workflow code, with each decision’s origin recorded.

Maintenance follows the same division of labour. Upstream changes are detected and adaptations drafted by AI, but shared knowledge changes only after review. Retrieval-backed persistent memory carries approved corrections, analogous cases, and laboratory conventions into later interactions, enabling increasingly context-specific assistance [7]. Together, these mechanisms operationalise augmentation rather than automation [8,9], while preserving human authority, explicit provenance, code ownership, and artifact inspectability.

# References

1. Attwood TK, Blackford S, Brazas MD, Davies A, Schneider MV. A global perspective on evolving bioinformatics and data science training needs. *Briefings in Bioinformatics*. 2019;20:398–404. <https://doi.org/10.1093/bib/bbx100>

2. Alam MR, Roy S. From Prompt to Pipeline: Large Language Models for Scientific Workflow Development in Bioinformatics. *arXiv*. 2025. <https://arxiv.org/abs/2507.20122>

3. Pazos F, Chagoyen M. Characteristics and evolution of the ecosystem of software tools supporting research in molecular biology. *Briefings in Bioinformatics*. 2019;20:1329–1336. <https://doi.org/10.1093/bib/bby001>

4. Afgan E, et al. The Galaxy platform for accessible, reproducible and collaborative biomedical analyses: 2018 update. *Nucleic Acids Research*. 2018;46:W537–W544. <https://doi.org/10.1093/nar/gky379>

5. Wratten L, Wilm A, Göke J. Reproducible, scalable, and shareable analysis pipelines with bioinformatics workflow managers. *Nature Methods*. 2021;18:1161–1168. <https://doi.org/10.1038/s41592-021-01254-9>

6. Li M, et al. API-Bank: A Comprehensive Benchmark for Tool-Augmented LLMs. *Proceedings of EMNLP*. 2023:3102–3116. <https://doi.org/10.18653/v1/2023.emnlp-main.187>

7. Chhikara P, et al. Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory. *arXiv*. 2025. <https://arxiv.org/abs/2504.19413>

8. MIT Ad Hoc Committee on AI Use in Teaching, Learning, and Research Training. *Final Report*. Massachusetts Institute of Technology; 2026. <https://bpb-us-e1.wpmucdn.com/sites.mit.edu/dist/d/2418/files/2026/08/AI-Committee-Final-Report-Aug-13.pdf>

9. Acemoglu D, Autor D, Johnson S. *Building Pro-Worker Artificial Intelligence*. NBER Working Paper 34854. 2026. <https://doi.org/10.3386/w34854>
