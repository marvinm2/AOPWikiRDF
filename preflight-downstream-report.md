# Downstream SPARQL Pre-flight Report

**Generated**: 2026-06-19 16:02:24 UTC

**Total queries**: 123

**PASS**: 121

**FAIL (D-05 literal)**: 2

**Flip-attributable regressions**: 0

**Result**: FAIL (D-05 bar: no error, no >=1-row-to-0-row regression)

**Flip verdict**: SAFE — flip-attributable regressions are failures (error or >=1->0 row drop) present on flags-on but NOT on the flags-off baseline. D-05-literal FAILs that fail identically on both loads are environmental (federation privileges, external SERVICE endpoints, heavy-query timeouts), not caused by the flip.

## Failures

| Source | Name | Pre | Post | Errored(on) | Errored(off) | Flip-attributable |
|---|---|---|---|---|---|---|
| SNORQL | count-entities | 0 | 0 | True | True | False |
| SNORQL | toxcast-assays-for-kes | 0 | 0 | True | True | False |

## All Queries

| Status | Source | Name | Pre | Post | Errored |
|---|---|---|---|---|---|
| FAIL | SNORQL | count-entities | 0 | 0 | True |
| FAIL | SNORQL | toxcast-assays-for-kes | 0 | 0 | True |
| PASS | SNORQL | all-aops | 587 | 587 | False |
| PASS | SNORQL | all-aops-full | 587 | 587 | False |
| PASS | SNORQL | all-chemicals | 414 | 414 | False |
| PASS | SNORQL | all-ke-components | 1785 | 1785 | False |
| PASS | SNORQL | all-ke-full | 1583 | 1583 | False |
| PASS | SNORQL | ao-for-mie | 531 | 531 | False |
| PASS | SNORQL | aop-to-ao | 645 | 645 | False |
| PASS | SNORQL | applicable-to-taxon-tree | 11 | 11 | False |
| PASS | SNORQL | chemicals-for-ao | 303 | 303 | False |
| PASS | SNORQL | chemicals-for-aop | 433 | 433 | False |
| PASS | SNORQL | count-aops | 1 | 1 | False |
| PASS | SNORQL | count-kers | 1 | 1 | False |
| PASS | SNORQL | count-kes | 1 | 1 | False |
| PASS | SNORQL | count-objects-aop-ontology | 1 | 1 | False |
| PASS | SNORQL | count-predicates-aop-ontology | 1 | 1 | False |
| PASS | SNORQL | count-stressors | 1 | 1 | False |
| PASS | SNORQL | count-triples | 1 | 1 | False |
| PASS | SNORQL | dataset-metadata | 4 | 4 | False |
| PASS | SNORQL | gene-detection-method-summary | 1 | 1 | False |
| PASS | SNORQL | genes-for-aop-annotated | 178 | 178 | False |
| PASS | SNORQL | genes-for-aop-mapped | 19263 | 19263 | False |
| PASS | SNORQL | genes-found-only-by-ner | 6738 | 6738 | False |
| PASS | SNORQL | get-ao-for-mie | 18 | 18 | False |
| PASS | SNORQL | get-aop-for-ao | 4 | 4 | False |
| PASS | SNORQL | get-matching-ids-for-chems | 3240 | 3240 | False |
| PASS | SNORQL | ke-to-aop | 3692 | 3692 | False |
| PASS | SNORQL | kes-and-ensembl | 4351 | 4351 | False |
| PASS | SNORQL | kes-and-hgnc | 4366 | 4366 | False |
| PASS | SNORQL | kes-and-ncbi | 4372 | 4372 | False |
| PASS | SNORQL | kes-and-ncbi-annotated | 78 | 78 | False |
| PASS | SNORQL | kes-and-uniprot | 20408 | 20408 | False |
| PASS | SNORQL | kes-and-uniprot-annotated | 833 | 833 | False |
| PASS | SNORQL | list-kers-for-aop | 8 | 8 | False |
| PASS | SNORQL | methods-for-aops | 8 | 8 | False |
| PASS | SNORQL | pathways-with-chem | 200895 | 200895 | False |
| PASS | SNORQL | search-ke-by-level | 1583 | 1583 | False |
| PASS | SNORQL | stressors-for-ao | 660 | 660 | False |
| PASS | SNORQL | stressors-for-ao-searched | 9 | 9 | False |
| PASS | SNORQL | text-search | 21 | 21 | False |
| PASS | methodology_notes | aop_authors | 1 | 1 | False |
| PASS | methodology_notes | aop_completeness_boxplot::Per-version AOP→KE / AOP→KER network structure — used to weight linked-entity completeness | 587 | 587 | False |
| PASS | methodology_notes | aop_completeness_boxplot::Per-version entity totals (AOP, KE, KER) — issued once per snapshot | 3 | 3 | False |
| PASS | methodology_notes | aop_completeness_boxplot::Per-version property presence per entity type — ?p restricted to property_labels.csv URIs (substitute your own list) | 3 | 3 | False |
| PASS | methodology_notes | aop_entity_counts | 1 | 1 | False |
| PASS | methodology_notes | aop_lifetime | 0 | 0 | False |
| PASS | methodology_notes | aop_network_density | 0 | 0 | False |
| PASS | methodology_notes | aop_property_presence::Count AOPs with each property, per version | 0 | 0 | False |
| PASS | methodology_notes | aop_property_presence::Total AOPs per version (denominator for percentage view) | 0 | 0 | False |
| PASS | methodology_notes | aops_per_stressor_distribution | 0 | 0 | False |
| PASS | methodology_notes | average_components_per_aop | 1 | 1 | False |
| PASS | methodology_notes | bio_annotations | 558 | 558 | False |
| PASS | methodology_notes | entity_birth_death | 1583 | 1583 | False |
| PASS | methodology_notes | entity_completeness_trends::Per-entity property counts (numerator for completeness) | 0 | 0 | False |
| PASS | methodology_notes | entity_completeness_trends::Property-presence counts per version (used to drop properties that hit 100% in any version) | 0 | 0 | False |
| PASS | methodology_notes | entity_completeness_trends::Total entities per version (denominator) — shown for AOP; plot also runs against KE, KER, Stressor | 0 | 0 | False |
| PASS | methodology_notes | entity_cumulative_removed | 1583 | 1583 | False |
| PASS | methodology_notes | ke_component_annotations | 1 | 1 | False |
| PASS | methodology_notes | ke_components_percentage | 1 | 1 | False |
| PASS | methodology_notes | ke_migration_map::KE titles for the y-axis labels (latest snapshot) | 1583 | 1583 | False |
| PASS | methodology_notes | ke_migration_map::Per-snapshot KE → AOP membership (drives the heatmap) | 0 | 0 | False |
| PASS | methodology_notes | ke_mmo_coverage | 0 | 0 | False |
| PASS | methodology_notes | ke_property_presence::Count KEs with each property, per version | 0 | 0 | False |
| PASS | methodology_notes | ke_property_presence::Total KEs per version (denominator for percentage view) | 0 | 0 | False |
| PASS | methodology_notes | ker_property_presence::Count KERs with each property, per version | 0 | 0 | False |
| PASS | methodology_notes | ker_property_presence::Total KERs per version (denominator for percentage view) | 0 | 0 | False |
| PASS | methodology_notes | kes_by_kec_count | 0 | 0 | False |
| PASS | methodology_notes | latest_aop_aop_overlap::AOP pairs sharing ≥5 KEs (run on the latest graph) | 205 | 205 | False |
| PASS | methodology_notes | latest_aop_aop_overlap::Per-AOP metadata (title, KE count, OECD status) for nodes | 536 | 536 | False |
| PASS | methodology_notes | latest_aop_aop_overlap::Resolve latest snapshot graph URI | 0 | 0 | False |
| PASS | methodology_notes | latest_aop_completeness::Count AOPs per property in latest graph | 29 | 29 | False |
| PASS | methodology_notes | latest_aop_completeness::Total AOPs in latest graph | 0 | 0 | False |
| PASS | methodology_notes | latest_aop_completeness_by_status::AOPs with each property, grouped by OECD status | 115 | 115 | False |
| PASS | methodology_notes | latest_aop_completeness_by_status::Identify latest graph (AOP anchor) | 0 | 0 | False |
| PASS | methodology_notes | latest_aop_completeness_by_status::Total AOPs per OECD status (denominator) | 4 | 4 | False |
| PASS | methodology_notes | latest_aop_connectivity | 0 | 0 | False |
| PASS | methodology_notes | latest_avg_per_aop::Count AOPs in latest graph | 0 | 0 | False |
| PASS | methodology_notes | latest_avg_per_aop::Count Key Event Relationships in latest graph | 0 | 0 | False |
| PASS | methodology_notes | latest_avg_per_aop::Count Key Events in latest graph | 0 | 0 | False |
| PASS | methodology_notes | latest_entity_by_oecd_status::Count AOPs per OECD status | 4 | 4 | False |
| PASS | methodology_notes | latest_entity_by_oecd_status::Count KERs per parent-AOP OECD status | 4 | 4 | False |
| PASS | methodology_notes | latest_entity_by_oecd_status::Count KEs per parent-AOP OECD status | 4 | 4 | False |
| PASS | methodology_notes | latest_entity_by_oecd_status::Identify latest graph (AOP anchor) | 0 | 0 | False |
| PASS | methodology_notes | latest_entity_counts | 0 | 0 | False |
| PASS | methodology_notes | latest_ke_annotation_depth::Count biological-event annotations per Key Event | 1583 | 1583 | False |
| PASS | methodology_notes | latest_ke_annotation_depth::Identify latest graph (KE anchor) | 0 | 0 | False |
| PASS | methodology_notes | latest_ke_by_bio_level::Count KEs per biological level of organisation | 6 | 6 | False |
| PASS | methodology_notes | latest_ke_by_bio_level::Identify latest graph (KE anchor) | 0 | 0 | False |
| PASS | methodology_notes | latest_ke_completeness_by_status::Identify latest graph (AOP anchor) | 0 | 0 | False |
| PASS | methodology_notes | latest_ke_completeness_by_status::KEs with each property, grouped by parent AOP OECD status | 100 | 100 | False |
| PASS | methodology_notes | latest_ke_completeness_by_status::Total KEs per OECD status (denominator) | 4 | 4 | False |
| PASS | methodology_notes | latest_ke_components::Count distinct process/object/action terms via biological events | 1 | 1 | False |
| PASS | methodology_notes | latest_ke_components::Identify latest graph (KE anchor) | 0 | 0 | False |
| PASS | methodology_notes | latest_ke_mmo_coverage | 1 | 1 | False |
| PASS | methodology_notes | latest_ke_reuse::Identify latest graph (AOP anchor) | 0 | 0 | False |
| PASS | methodology_notes | latest_ke_reuse::Top 30 KEs by AOP membership count (HAVING > 1) | 30 | 30 | False |
| PASS | methodology_notes | latest_ke_reuse_distribution::AOP count per Key Event (full distribution) | 1583 | 1583 | False |
| PASS | methodology_notes | latest_ke_reuse_distribution::Identify latest graph (AOP anchor) | 0 | 0 | False |
| PASS | methodology_notes | latest_ker_completeness_by_status::Identify latest graph (AOP anchor) | 0 | 0 | False |
| PASS | methodology_notes | latest_ker_completeness_by_status::KERs with each property, grouped by parent AOP OECD status | 108 | 108 | False |
| PASS | methodology_notes | latest_ker_completeness_by_status::Total KERs per OECD status (denominator) | 4 | 4 | False |
| PASS | methodology_notes | latest_life_stage | 661 | 661 | False |
| PASS | methodology_notes | latest_multi_organ_aops | 6197 | 6197 | False |
| PASS | methodology_notes | latest_object_usage::Distribution of biological-object terms by ontology source | 6 | 6 | False |
| PASS | methodology_notes | latest_object_usage::Identify latest graph (KE anchor) | 0 | 0 | False |
| PASS | methodology_notes | latest_ontology_diversity::Distinct ontology terms attached to KEs via biological events | 1045 | 1045 | False |
| PASS | methodology_notes | latest_ontology_diversity::Identify latest graph (KE anchor) | 0 | 0 | False |
| PASS | methodology_notes | latest_ontology_usage::Distribution of process/object/action terms by ontology source | 8 | 8 | False |
| PASS | methodology_notes | latest_ontology_usage::Identify latest graph (KE anchor) | 0 | 0 | False |
| PASS | methodology_notes | latest_organ_coverage_unified | 6197 | 6197 | False |
| PASS | methodology_notes | latest_process_usage::Distribution of biological-process terms by ontology source | 8 | 8 | False |
| PASS | methodology_notes | latest_process_usage::Identify latest graph (KE anchor) | 0 | 0 | False |
| PASS | methodology_notes | latest_taxonomic_groups::Identify latest graph (AOP anchor) | 0 | 0 | False |
| PASS | methodology_notes | latest_taxonomic_groups::Pull raw (AOP, taxon) pairs for client-side aggregation | 798 | 798 | False |
| PASS | methodology_notes | oecd_completeness_trend | 0 | 0 | False |
| PASS | methodology_notes | oecd_status_distribution | 0 | 0 | False |
| PASS | methodology_notes | ontology_term_growth | 1 | 1 | False |
| PASS | methodology_notes | organ_coverage | 4435 | 4435 | False |
| PASS | methodology_notes | stressor_coverage_growth | 0 | 0 | False |
| PASS | methodology_notes | stressor_property_presence::Count Stressors with each property, per version | 0 | 0 | False |
| PASS | methodology_notes | stressor_property_presence::Total Stressors per version (denominator for percentage view) | 0 | 0 | False |
| PASS | methodology_notes | unique_ke_components | 1 | 1 | False |

