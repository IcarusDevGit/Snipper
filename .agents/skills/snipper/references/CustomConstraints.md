# CONFIG: CUSTOM_CONSTRAINTS
DOCUMENT_VERSION: 2.0.0
FORMAT: YAML_FRONTMATTER_EMBEDDED

```yaml
configuration:
  # Language selection for spaCy NLP tokenization and lemmatization
  # Values: "auto" (detect language), "pt-BR" (pt_core_news_sm), "en" (en_core_web_sm)
  language: "auto"

  # Web search policy for terminology disambiguation
  # Values: true | false
  allow_web_search: false

  # Noun matching restriction
  # Values: false (all NOUN and PROPN), true (PROPN only)
  proper_nouns_only: false

  # Highlight color mode
  # Values: "hex" (Word <w:shd> shading) | "named" (Word native <w:highlight>)
  palette_mode: "hex"

  # Color assignment sequence when |Palette| > |Questions|
  # Values: "sequential" | "random"
  palette_order: "sequential"
  