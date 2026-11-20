"""Unit tests for mental-map skill."""

import pytest
from pathlib import Path
import sys

# Add scripts directory to sys.path
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from parser import clean_title, parse_markdown_or_text, extract_gdoc_id
from layout import calculate_card_height, build_layout


def test_clean_title():
    assert clean_title("Gráficos e Interpretações Gráficas.map") == "Gráficos e Interpretações Gráficas"
    assert clean_title("Documento.map.gdoc") == "Documento"
    assert clean_title("Anotações.md") == "Anotações"
    assert clean_title("Resumo.txt") == "Resumo"
    assert clean_title("SimpleTitle") == "SimpleTitle"


def test_extract_gdoc_id():
    url = "https://docs.google.com/document/d/1xcUXvf1w9cKB0zySMu1ukOsSBLOD-mVQfCfV-RlFZkU/edit?usp=sharing"
    assert extract_gdoc_id(url) == "1xcUXvf1w9cKB0zySMu1ukOsSBLOD-mVQfCfV-RlFZkU"

    raw_id = "1xcUXvf1w9cKB0zySMu1ukOsSBLOD-mVQfCfV-RlFZkU"
    assert extract_gdoc_id(raw_id) == "1xcUXvf1w9cKB0zySMu1ukOsSBLOD-mVQfCfV-RlFZkU"

    assert extract_gdoc_id("not-an-id") is None


def test_parse_markdown_basic_hierarchy():
    sample = """# Álgebra Linear.map

**Espaços Vetoriais**
Definição formal sobre um corpo K
Vetor nulo
- Elemento neutro da adição
- Multiplicação por escalar zero resulta no vetor nulo

**Subespaços**
Condições de existência:
- Contém o vetor nulo
  - Exemplo: origem no R3
- Fechado sob adição
"""
    model = parse_markdown_or_text(sample)

    assert model.title == "Álgebra Linear"
    assert len(model.sections) == 2

    # Section 1
    s1 = model.sections[0]
    assert s1.title == "Espaços Vetoriais"
    assert len(s1.concepts) == 2
    assert s1.concepts[0].text == "Definição formal sobre um corpo K"
    assert not s1.concepts[0].is_parent

    # Concept with bullets
    assert s1.concepts[1].text == "Vetor nulo"
    assert s1.concepts[1].is_parent
    assert len(s1.concepts[1].bullets) == 2
    assert s1.concepts[1].bullets[0].text == "Elemento neutro da adição"
    assert s1.concepts[1].bullets[0].nesting_level == 0
    assert s1.concepts[1].bullets[1].text == "Multiplicação por escalar zero resulta no vetor nulo"

    # Section 2 with multi-tier nested bullets
    s2 = model.sections[1]
    assert s2.title == "Subespaços"
    assert len(s2.concepts) == 1
    assert s2.concepts[0].text == "Condições de existência:"
    assert len(s2.concepts[0].bullets) == 3

    b0 = s2.concepts[0].bullets[0]
    assert b0.text == "Contém o vetor nulo"
    assert b0.nesting_level == 0

    b1 = s2.concepts[0].bullets[1]
    assert b1.text == "Exemplo: origem no R3"
    assert b1.nesting_level == 1
    assert b1.parent_id == b0.id
    assert len(b0.children) == 1
    assert b0.children[0].text == "Exemplo: origem no R3"


def test_parse_markdown_headings():
    sample = """## Seção 1
Conceito A
- Detalhe 1

## Seção 2
Conceito B
"""
    model = parse_markdown_or_text(sample, default_title="Teste de Cabeçalhos.map")
    assert model.title == "Teste de Cabeçalhos"
    assert len(model.sections) == 2
    assert model.sections[0].title == "Seção 1"
    assert model.sections[1].title == "Seção 2"


def test_dynamic_card_height():
    short_h = calculate_card_height("Texto curto", width=300)
    long_text = "Este é um texto consideravelmente longo elaborado para testar que o cálculo dinâmico de altura aumenta com o número de linhas sem truncar o conteúdo visual na caixa do diagrama."
    long_h = calculate_card_height(long_text, width=300)
    assert long_h > short_h
    assert short_h >= 40


def test_panoramic_layout_1_to_3_sections():
    sample = """# Teste Panorâmico
**Sec 1**
Item 1
**Sec 2**
Item 2
**Sec 3**
Item 3
"""
    model = parse_markdown_or_text(sample)
    layout = build_layout(model)

    sec_headers = [n for n in layout.nodes if n.node_type == "section_header"]
    assert len(sec_headers) == 3
    # All 3 headers must be on the same horizontal row
    assert sec_headers[0].y == sec_headers[1].y == sec_headers[2].y
    # Ordered horizontally
    assert sec_headers[0].x < sec_headers[1].x < sec_headers[2].x


def test_adaptive_grid_wrapping_4_and_5_sections():
    sample_4 = """# Teste 4 Seções
**Sec 1**\nItem 1
**Sec 2**\nItem 2
**Sec 3**\nItem 3
**Sec 4**\nItem 4
"""
    model_4 = parse_markdown_or_text(sample_4)
    layout_4 = build_layout(model_4)
    headers_4 = [n for n in layout_4.nodes if n.node_type == "section_header"]
    assert len(headers_4) == 4
    # Sec 1 and Sec 2 in Row 1; Sec 3 and Sec 4 in Row 2
    assert headers_4[0].y == headers_4[1].y
    assert headers_4[2].y == headers_4[3].y
    assert headers_4[2].y > headers_4[0].y

    sample_5 = """# Teste 5 Seções
**Sec 1**\nItem 1
**Sec 2**\nItem 2
**Sec 3**\nItem 3
**Sec 4**\nItem 4
**Sec 5**\nItem 5
"""
    model_5 = parse_markdown_or_text(sample_5)
    layout_5 = build_layout(model_5)
    headers_5 = [n for n in layout_5.nodes if n.node_type == "section_header"]
    assert len(headers_5) == 5
    # Row 1 has 3 headers; Row 2 has 2 headers
    assert headers_5[0].y == headers_5[1].y == headers_5[2].y
    assert headers_5[3].y == headers_5[4].y
    assert headers_5[3].y > headers_5[0].y


def test_card_coordinates_no_overlap():
    sample = """# Teste Sem Sobreposição
**Sec 1**
Texto A
Texto B
Pai C
- Bala 1
- Bala 2

**Sec 2**
Texto D
Pai E
- Detalhe 1
  - Subdetalhe 1.1
Texto F
"""
    model = parse_markdown_or_text(sample)
    layout = build_layout(model)

    # Exclude banner when checking section nodes pairwise, or check all
    nodes = layout.nodes
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            n1 = nodes[i]
            n2 = nodes[j]

            # Bounding box overlap check
            overlap_x = (n1.x < n2.x + n2.width) and (n1.x + n1.width > n2.x)
            overlap_y = (n1.y < n2.y + n2.height) and (n1.y + n1.height > n2.y)
            assert not (overlap_x and overlap_y), f"Overlap detected between node '{n1.id}' ({n1.x},{n1.y},{n1.width},{n1.height}) and '{n2.id}' ({n2.x},{n2.y},{n2.width},{n2.height})"


def test_emitter_strict_xml_validation_and_special_chars(tmp_path):
    from emitter import emit_drawio_xml, save_diagram, get_versioned_path
    import xml.etree.ElementTree as ET

    sample = """# Símbolos & Caracteres Especiais <XML> "Teste"
**Seção 1: Operadores Matemáticos**
Intervalo aberto ]-∞, +∞[ e desigualdade x < y & a > b
Expressão:
- Caso 1: f(x) <= g(x) && x != "nulo"
- Caso 2: cotação com aspas simples 'teste' e duplas "ok"
"""
    model = parse_markdown_or_text(sample)
    layout = build_layout(model)

    xml_output = emit_drawio_xml(layout)
    assert isinstance(xml_output, str)

    # ElementTree must parse with zero errors
    tree = ET.fromstring(xml_output)
    assert tree.tag == "mxfile"

    diagram = tree.find("diagram")
    assert diagram is not None
    assert "Símbolos & Caracteres Especiais <XML> \"Teste\"" in diagram.attrib["name"]


def test_versioning_and_overwrite(tmp_path):
    from emitter import get_versioned_path, save_diagram

    test_file = tmp_path / "diagram.drawio"
    test_file.write_text("<mxfile/>", encoding="utf-8")

    # get_versioned_path on existing file
    v2_path = get_versioned_path(test_file)
    assert v2_path.name == "diagram (v2).drawio"

    v2_path.write_text("<mxfile/>", encoding="utf-8")
    v3_path = get_versioned_path(test_file)
    assert v3_path.name == "diagram (v3).drawio"

    # save_diagram without overwrite (v3 does not exist yet on disk, so it will be v3)
    res1 = save_diagram("<mxfile><diagram/></mxfile>", test_file, overwrite=False, sync_gdrive=False)
    assert Path(res1["local_path"]).name == "diagram (v3).drawio"
    assert res1["overwritten"] is False

    # save_diagram with overwrite
    res2 = save_diagram("<mxfile><diagram/></mxfile>", test_file, overwrite=True, sync_gdrive=False)
    assert Path(res2["local_path"]).name == "diagram.drawio"
    assert res2["overwritten"] is True


def test_horizontal_concept_card_and_zero_arrows():
    """Verify that Regras de inferência (or [horizontal]) renders as a horizontal card with zero arrow edges."""
    from emitter import emit_drawio_xml
    import xml.etree.ElementTree as ET

    sample = """# Lógica Proposicional
**Implicação e Regras**
Implicação lógica
- Se p então q
Regras de inferência
- Regra da Adição (AD):
  - Estrutura: A partir de premissa p, conclui-se p ou q
  - Exemplo: Temperatura baixa
- Modus Ponens (MP):
  - Estrutura: p -> q e p infere q
  - Exemplo: Se chover então molha
"""
    model = parse_markdown_or_text(sample)
    layout = build_layout(model)

    # Find the Regras de inferência node
    regras_nodes = [n for n in layout.nodes if "regras de inferência" in n.label.lower() or "regras de inferência" in n.tooltip.lower()]
    assert len(regras_nodes) == 1
    rn = regras_nodes[0]
    assert rn.node_type == "horizontal_card"
    assert "<table" in rn.label

    # Verify zero edges have rn.id as source or target
    rn_edges = [e for e in layout.edges if e.source_id == rn.id or e.target_id == rn.id]
    assert len(rn_edges) == 0

    # Ensure XML validates strictly
    xml_str = emit_drawio_xml(layout)
    tree = ET.fromstring(xml_str)
    assert tree.tag == "mxfile"


def test_parse_document_missing_file_raises(tmp_path):
    from parser import parse_document

    missing = tmp_path / "does_not_exist.map"
    with pytest.raises(FileNotFoundError):
        parse_document(missing)


