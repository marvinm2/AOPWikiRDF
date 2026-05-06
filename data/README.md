# AOP-Wiki RDF — generated data

This directory holds the RDF outputs produced by the conversion scripts in the parent repository.

## Files

| File | Contents |
|---|---|
| `AOPWikiRDF.ttl` | Main dataset — AOPs, Key Events, Key Event Relationships, Stressors. |
| `AOPWikiRDF-Genes.ttl` | Gene mappings (HGNC + BridgeDb-resolved external identifiers). |
| `AOPWikiRDF-Enriched.ttl` | Cross-reference enrichments. |
| `AOPWikiRDF-Void.ttl` | VoID metadata describing the datasets. |
| `ServiceDescription.ttl` | SPARQL service description (auto-generated). |
| `HGNCgenes.txt` | HGNC reference table used by the gene-mapping algorithm. |
| `promapping.txt` | Protein Ontology mapping table. |
| `qc-status.txt` | Validation status from the latest QC run. |
| `aop-wiki-xml-YYYY-MM-DD` | Source XML snapshot (input to the conversion). |

## Licence

The generated RDF files in this directory (`*.ttl`) are released under
**Creative Commons Attribution 4.0 International (CC-BY 4.0)**. See `LICENSE-DATA`
for the full statement and citation guidance.

The conversion code in the parent repository is licensed under MIT — see the
top-level `LICENSE` file.

## Citation

Martens M., Evelo C.T., Willighagen E.L. (2022). *Providing Adverse Outcome Pathways
from the AOP-Wiki in a Semantic Web Format to Increase Usability and Accessibility
of the Content.* Applied In Vitro Toxicology 8(1):2–13.
[doi:10.1089/aivt.2021.0010](https://doi.org/10.1089/aivt.2021.0010)

Dataset releases are archived on Zenodo: [10.5281/zenodo.13353286](https://doi.org/10.5281/zenodo.13353286)

## Update cadence

Generated weekly on Saturdays 08:00 UTC by the
[`rdfgeneration.yml`](../.github/workflows/rdfgeneration.yml) GitHub Action,
followed by an automated Turtle quality-control run.
